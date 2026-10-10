#!/usr/bin/env python3
"""
Upload to Sanity: push the filter results for a run date to Sanity as structured documents.

Each dataset is stored as one `screenerSnapshot` document per date, holding the CSV rows:
  - allStocks: Filter1 OHLC for equities, one document per candle date
  - indices:   Filter1 OHLC for indices, one document per candle date
  - topStocks: Filter2 (Minervini trend template), one document per run date
  - breakouts: Filter3 (above last pivot), one document per run date
  - allStocksList: every equity in src/static/instruments/nse-other-instruments.csv with its
    true/false index membership flags (nifty_50, nifty_bank, nifty_smallcap_50, nifty_midcap_50).
    One document (`screenerSnapshot-allStocksList`), replaced on each upload; the website's
    heat map uses it to pick the stocks of each index.

Document ids are deterministic (`screenerSnapshot-<dataset>-<date>`) and written with
createOrReplace, so re-running a day overwrites that day instead of duplicating it. Ids must
not contain dots: Sanity treats dotted ids as private, even in a public dataset.

topStocks and breakouts are dated by the market day in their rows, not the day the script ran,
so a run on a weekend, a holiday or after midnight overwrites the market day it screened. Any
other document of the same dataset holding that market day is deleted, which also cleans up
duplicates left by earlier runs: re-running the upload is enough to fix them.

Configuration comes from the root .env:
  SANITY_PROJECT_ID, SANITY_DATASET (default: production), SANITY_API_TOKEN (write token),
  SANITY_API_VERSION (default: 2025-02-19)

Usage:
  python src/upload_to_sanity.py [YYYY-MM-DD] [--dry-run]
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests

from kite_service import RESULTS_DIR  # also loads the root .env

DOCUMENT_TYPE = 'screenerSnapshot'

# Row column holding the market day of each run-date dataset
MARKET_DATE_COLUMNS = {
    'topStocks': 'date',
    'breakouts': 'currentDate',
}

# dataset -> (CSV file suffix, whether rows are split by candle date)
DATASETS = {
    'allStocks': ('ohlc-nse-other-instruments.csv', True),
    'indices': ('ohlc-nse-indices.csv', True),
    'topStocks': ('filter2_minervini_filter_list.csv', False),
    'breakouts': ('filter3_above_pivot.csv', False),
}

# Instrument list with index membership flags (kept up to date by update_index_membership.py)
INSTRUMENTS_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'static', 'instruments', 'nse-other-instruments.csv'
)
STOCK_LIST_DATASET = 'allStocksList'
STOCK_LIST_COLUMNS = {
    'tradingsymbol': 'trading_symbol',  # same name as the Filter1 rows, so the site can join them
    'name': 'name',
    'instrument_token': 'instrument_token',
    'nifty_50': 'nifty_50',
    'nifty_bank': 'nifty_bank',
    'nifty_smallcap_50': 'nifty_smallcap_50',
    'nifty_midcap_50': 'nifty_midcap_50',
}

# Sanity field names cannot start with a digit
RENAMED_COLUMNS = {
    '52wh': 'week52High',
    '52wl': 'week52Low',
}

# Keep each mutate request well under Sanity's request size limit
MAX_REQUEST_BYTES = 3 * 1024 * 1024


def _clean_value(value):
    """Convert a pandas/numpy cell into a JSON-safe value."""
    if value is None:
        return None
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def csv_to_rows(csv_path):
    """Read a results CSV into a list of plain dicts with Sanity-safe keys."""
    df = pd.read_csv(csv_path).rename(columns=RENAMED_COLUMNS)
    if 'date' in df.columns:
        # Kite candle dates look like "2025-10-09 00:00:00+05:30"; keep the day only
        df['date'] = df['date'].astype(str).str[:10]

    rows = []
    for index, record in enumerate(df.to_dict(orient='records')):
        row = {'_key': f'r{index}'}
        row.update({key: _clean_value(value) for key, value in record.items()})
        rows.append(row)
    return rows


def market_date(dataset, rows, run_date):
    """Latest market day in a run-date dataset's rows, or the run date if the rows have none."""
    column = MARKET_DATE_COLUMNS.get(dataset)
    dates = [str(row[column])[:10] for row in rows if column and row.get(column)]
    return max(dates) if dates else run_date


def build_documents(run_date, results_dir=RESULTS_DIR):
    """Build the Sanity documents for every results CSV of a run date."""
    generated_at = datetime.now(timezone.utc).isoformat()
    documents = []

    for dataset, (suffix, split_by_candle_date) in DATASETS.items():
        csv_path = os.path.join(results_dir, f'{run_date}_{suffix}')
        if not os.path.exists(csv_path):
            print(f'⚠️ Skipping {dataset}: {csv_path} not found')
            continue

        rows = csv_to_rows(csv_path)
        if split_by_candle_date and rows and 'date' in rows[0]:
            groups = {}
            for row in rows:
                groups.setdefault(row['date'], []).append(row)
        else:
            groups = {market_date(dataset, rows, run_date): rows}

        for date, date_rows in sorted(groups.items()):
            for index, row in enumerate(date_rows):
                row['_key'] = f'r{index}'
            documents.append({
                '_id': f'{DOCUMENT_TYPE}-{dataset}-{date}',
                '_type': DOCUMENT_TYPE,
                'dataset': dataset,
                'date': date,
                'runDate': run_date,
                'generatedAt': generated_at,
                'rowCount': len(date_rows),
                'rows': date_rows,
            })

    stock_list = build_stock_list_document(run_date, generated_at)
    if stock_list:
        documents.append(stock_list)

    return documents


def build_stock_list_document(run_date, generated_at, csv_path=INSTRUMENTS_CSV):
    """Build the allStocksList document: every equity with its index membership flags."""
    if not os.path.exists(csv_path):
        print(f'⚠️ Skipping {STOCK_LIST_DATASET}: {csv_path} not found')
        return None

    df = pd.read_csv(csv_path)
    columns = [column for column in STOCK_LIST_COLUMNS if column in df.columns]
    df = df[columns].rename(columns=STOCK_LIST_COLUMNS)
    for flag in ('nifty_50', 'nifty_bank', 'nifty_smallcap_50', 'nifty_midcap_50'):
        if flag in df.columns:
            df[flag] = df[flag].astype(str).str.strip().str.lower().isin(['true', '1'])

    rows = []
    for index, record in enumerate(df.to_dict(orient='records')):
        row = {'_key': f'r{index}'}
        row.update({key: _clean_value(value) for key, value in record.items()})
        rows.append(row)

    return {
        '_id': f'{DOCUMENT_TYPE}-{STOCK_LIST_DATASET}',
        '_type': DOCUMENT_TYPE,
        'dataset': STOCK_LIST_DATASET,
        'date': run_date,
        'runDate': run_date,
        'generatedAt': generated_at,
        'rowCount': len(rows),
        'rows': rows,
    }


class SanityUploader:
    """Writes documents to Sanity through the HTTP mutations API."""

    def __init__(self, project_id=None, dataset=None, token=None, api_version=None):
        self.project_id = project_id or os.getenv('SANITY_PROJECT_ID')
        self.dataset = dataset or os.getenv('SANITY_DATASET') or 'production'
        self.token = token or os.getenv('SANITY_API_TOKEN')
        self.api_version = api_version or os.getenv('SANITY_API_VERSION') or '2025-02-19'

        if not self.project_id:
            raise ValueError('SANITY_PROJECT_ID environment variable is required')
        if not self.token:
            raise ValueError('SANITY_API_TOKEN environment variable is required')

        self.mutate_url = (
            f'https://{self.project_id}.api.sanity.io/v{self.api_version}'
            f'/data/mutate/{self.dataset}'
        )

    def _post(self, mutations):
        response = requests.post(
            self.mutate_url,
            headers={'Authorization': f'Bearer {self.token}'},
            json={'mutations': mutations},
            params={'visibility': 'sync'},
            timeout=120,
        )
        if not response.ok:
            raise RuntimeError(f'Sanity mutate failed ({response.status_code}): {response.text[:500]}')
        return response.json()

    def upload(self, documents):
        """createOrReplace the documents, batching requests by size. Returns the count written."""
        batch, batch_bytes, written = [], 0, 0
        for document in documents:
            # Earlier uploads used dotted ids, which the public website cannot read; drop them
            legacy_id = f"{DOCUMENT_TYPE}.{document['dataset']}.{document['date']}"
            mutation = [{'createOrReplace': document}, {'delete': {'id': legacy_id}}]
            if document['dataset'] in MARKET_DATE_COLUMNS:
                mutation.append(duplicates_delete(document))
            size = len(json.dumps(mutation))
            if batch and batch_bytes + size > MAX_REQUEST_BYTES:
                self._post(batch)
                written += sum(1 for m in batch if 'createOrReplace' in m)
                batch, batch_bytes = [], 0
            batch.extend(mutation)
            batch_bytes += size
        if batch:
            self._post(batch)
            written += sum(1 for m in batch if 'createOrReplace' in m)
        return written


def duplicates_delete(document):
    """Mutation deleting other documents of the dataset that hold the same market day."""
    column = MARKET_DATE_COLUMNS[document['dataset']]
    return {'delete': {
        'query': (
            f'*[_type == "{DOCUMENT_TYPE}" && dataset == $dataset && _id != $id'
            f' && (date == $date || rows[0].{column} == $date)]'
        ),
        'params': {'dataset': document['dataset'], 'id': document['_id'], 'date': document['date']},
    }}


def push_results_to_sanity(run_date=None, results_dir=RESULTS_DIR):
    """Push a run date's results to Sanity. Returns a result dict; never raises."""
    run_date = run_date or datetime.now().strftime('%Y-%m-%d')
    if not os.getenv('SANITY_PROJECT_ID') or not os.getenv('SANITY_API_TOKEN'):
        print('ℹ️ Sanity not configured (SANITY_PROJECT_ID / SANITY_API_TOKEN); skipping upload')
        return {'success': False, 'skipped': True, 'error': 'Sanity not configured'}

    try:
        documents = build_documents(run_date, results_dir)
        if not documents:
            return {'success': False, 'error': f'No results found for {run_date}'}
        uploader = SanityUploader()
        written = uploader.upload(documents)
        print(f'✅ Pushed {written} documents for {run_date} to Sanity dataset "{uploader.dataset}"')
        return {'success': True, 'documents': written}
    except Exception as e:
        print(f'❌ Sanity upload failed: {e}')
        return {'success': False, 'error': str(e)}


def main():
    args = [arg for arg in sys.argv[1:] if arg != '--dry-run']
    dry_run = '--dry-run' in sys.argv[1:]
    run_date = args[0] if args else datetime.now().strftime('%Y-%m-%d')

    if dry_run:
        documents = build_documents(run_date)
        output_path = os.path.join(RESULTS_DIR, f'{run_date}_sanity_documents.json')
        with open(output_path, 'w') as f:
            json.dump(documents, f, indent=2)
        for document in documents:
            print(f"{document['_id']}: {document['rowCount']} rows")
        print(f'📝 Dry run: wrote {len(documents)} documents to {output_path}')
        return

    result = push_results_to_sanity(run_date)
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()

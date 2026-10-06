#!/usr/bin/env python3
"""
Upload to Sanity: push the filter results for a run date to Sanity as structured documents.

Each dataset is stored as one `screenerSnapshot` document per date, holding the CSV rows:
  - allStocks: Filter1 OHLC for equities, one document per candle date
  - indices:   Filter1 OHLC for indices, one document per candle date
  - topStocks: Filter2 (Minervini trend template), one document per run date
  - breakouts: Filter3 (above last pivot), one document per run date

Document ids are deterministic (`screenerSnapshot-<dataset>-<date>`) and written with
createOrReplace, so re-running a day overwrites that day instead of duplicating it. Ids must
not contain dots: Sanity treats dotted ids as private, even in a public dataset.

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

# dataset -> (CSV file suffix, whether rows are split by candle date)
DATASETS = {
    'allStocks': ('ohlc-nse-other-instruments.csv', True),
    'indices': ('ohlc-nse-indices.csv', True),
    'topStocks': ('filter2_minervini_filter_list.csv', False),
    'breakouts': ('filter3_above_pivot.csv', False),
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
            groups = {run_date: rows}

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

    return documents


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
            size = len(json.dumps(mutation))
            if batch and batch_bytes + size > MAX_REQUEST_BYTES:
                self._post(batch)
                written += len(batch) // 2
                batch, batch_bytes = [], 0
            batch.extend(mutation)
            batch_bytes += size
        if batch:
            self._post(batch)
            written += len(batch) // 2
        return written


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

#!/usr/bin/env python3
"""
Update index membership: set the nifty_50, nifty_bank, nifty_smallcap_50 and nifty_midcap_50
columns of src/static/instruments/nse-other-instruments.csv to True/False from NSE's published
constituent lists, matching each list's Symbol to the instrument's tradingsymbol.

Index constituents change at NSE's rebalances (usually March and September), so re-run this then
and commit the diff.

Usage:
  python src/update_index_membership.py              # download the lists from NSE
  python src/update_index_membership.py --from-dir D # use ind_<index>list.csv files already in D
"""

import io
import os
import sys

import pandas as pd
import requests

from filter1 import INSTRUMENTS_DIR

INSTRUMENTS_CSV = os.path.join(INSTRUMENTS_DIR, 'nse-other-instruments.csv')

# column -> NSE constituent list file name
INDEX_LISTS = {
    'nifty_50': 'ind_nifty50list.csv',
    'nifty_bank': 'ind_niftybanklist.csv',
    'nifty_smallcap_50': 'ind_niftysmallcap50list.csv',
    'nifty_midcap_50': 'ind_niftymidcap50list.csv',
}

# Tried in order; NSE rejects requests without a browser-like User-Agent
SOURCE_URLS = [
    'https://archives.nseindia.com/content/indices/{file}',
    'https://www.niftyindices.com/IndexConstituent/{file}',
]
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}


def download_list(file_name):
    """Download one constituent list, returning its CSV text."""
    errors = []
    for url in SOURCE_URLS:
        url = url.format(file=file_name)
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.ok and 'Symbol' in response.text[:500]:
                return response.text
            errors.append(f'{url}: HTTP {response.status_code}')
        except requests.RequestException as e:
            errors.append(f'{url}: {e}')
    raise RuntimeError(f'Could not download {file_name}: ' + '; '.join(errors))


def load_symbols(file_name, from_dir=None):
    """Symbols in one NSE constituent list."""
    if from_dir:
        with open(os.path.join(from_dir, file_name)) as f:
            text = f.read()
    else:
        text = download_list(file_name)
    constituents = pd.read_csv(io.StringIO(text))
    constituents.columns = [column.strip() for column in constituents.columns]
    return set(constituents['Symbol'].astype(str).str.strip())


def update_membership(instruments_csv=INSTRUMENTS_CSV, from_dir=None):
    """Rewrite the membership columns in place and return {column: (members, unmatched symbols)}."""
    instruments = pd.read_csv(instruments_csv)
    symbols = instruments['tradingsymbol'].astype(str)
    summary = {}
    for column, file_name in INDEX_LISTS.items():
        members = load_symbols(file_name, from_dir)
        instruments[column] = symbols.isin(members)
        summary[column] = (len(members), sorted(members - set(symbols)))
    instruments.to_csv(instruments_csv, index=False)
    return summary


def main():
    args = sys.argv[1:]
    from_dir = args[args.index('--from-dir') + 1] if '--from-dir' in args else None
    summary = update_membership(from_dir=from_dir)
    for column, (count, unmatched) in summary.items():
        line = f'{column}: {count - len(unmatched)}/{count} constituents flagged'
        if unmatched:
            line += f' (not in the instrument list: {", ".join(unmatched)})'
        print(line)
    print(f'💾 Updated {INSTRUMENTS_CSV}')


if __name__ == '__main__':
    main()

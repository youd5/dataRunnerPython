#!/usr/bin/env python3
"""
Tests for filling the index membership columns from NSE constituent lists (no network).
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('KITE_API_KEY', 'test-key')
os.environ.setdefault('KITE_API_SECRET', 'test-secret')

import pandas as pd

import update_index_membership
from update_index_membership import INDEX_LISTS, update_membership

NSE_HEADER = 'Company Name,Industry,Symbol,Series,ISIN Code\n'


def nse_list(*symbols):
    return NSE_HEADER + ''.join(f'{s} Ltd,Sector,{s},EQ,INE000000000\n' for s in symbols)


class UpdateMembershipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.csv = os.path.join(self.tmp.name, 'nse-other-instruments.csv')
        pd.DataFrame({
            'instrument_token': [1, 2, 3],
            'tradingsymbol': ['RELIANCE', 'HDFCBANK', 'SMALLCO'],
            'name': ['Reliance', 'HDFC Bank', 'Small Co'],
            'nifty_50': [False, False, True],
            'nifty_bank': [False, False, False],
            'nifty_smallcap_50': [False, False, False],
            'nifty_midcap_50': [False, False, False],
        }).to_csv(self.csv, index=False)
        self.lists = {
            'ind_nifty50list.csv': nse_list('RELIANCE', 'HDFCBANK', 'NEWCO'),
            'ind_niftybanklist.csv': nse_list('HDFCBANK'),
            'ind_niftysmallcap50list.csv': nse_list('SMALLCO'),
            'ind_niftymidcap50list.csv': nse_list('MIDCO'),
        }

    def assert_flags(self, summary):
        df = pd.read_csv(self.csv).set_index('tradingsymbol')
        self.assertEqual(df['nifty_50'].to_dict(), {'RELIANCE': True, 'HDFCBANK': True, 'SMALLCO': False})
        self.assertEqual(df['nifty_bank'].to_dict(), {'RELIANCE': False, 'HDFCBANK': True, 'SMALLCO': False})
        self.assertEqual(df['nifty_smallcap_50'].to_dict(), {'RELIANCE': False, 'HDFCBANK': False, 'SMALLCO': True})
        self.assertFalse(df['nifty_midcap_50'].any())
        self.assertEqual(df['name'].tolist(), ['Reliance', 'HDFC Bank', 'Small Co'])
        self.assertEqual(summary['nifty_50'], (3, ['NEWCO']))
        self.assertEqual(summary['nifty_midcap_50'], (1, ['MIDCO']))

    def test_from_local_lists(self):
        for name, text in self.lists.items():
            with open(os.path.join(self.tmp.name, name), 'w') as f:
                f.write(text)
        self.assert_flags(update_membership(self.csv, from_dir=self.tmp.name))

    def test_downloads_with_fallback_source(self):
        def get(url, headers, timeout):
            name = url.rsplit('/', 1)[1]
            if 'archives.nseindia.com' in url:
                return mock.Mock(ok=False, status_code=403, text='denied')
            return mock.Mock(ok=True, status_code=200, text=self.lists[name])

        with mock.patch.object(update_index_membership.requests, 'get', side_effect=get):
            self.assert_flags(update_membership(self.csv))

    def test_covers_every_column(self):
        self.assertEqual(sorted(INDEX_LISTS), ['nifty_50', 'nifty_bank', 'nifty_midcap_50', 'nifty_smallcap_50'])


if __name__ == '__main__':
    unittest.main()

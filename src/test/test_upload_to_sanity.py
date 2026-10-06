#!/usr/bin/env python3
"""
Tests for the Sanity upload, using sample result CSVs and a mocked Sanity API.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import upload_to_sanity
from upload_to_sanity import SanityUploader, build_documents, push_results_to_sanity

RUN_DATE = '2026-10-06'

SAMPLE_CSVS = {
    'ohlc-nse-other-instruments.csv': (
        'trading_symbol,instrument_token,date,open,high,low,close,volume,change,changePercent,marketCap,trend,sector\n'
        'ABC,101,2026-10-05 00:00:00+05:30,100,110,95,105,200000,5.0,5.0,Unknown,UP,Unknown\n'
        'ABC,101,2026-10-06 00:00:00+05:30,105,112,104,111,250000,6.0,5.71,Unknown,UP,Unknown\n'
        'XYZ,102,2026-10-06 00:00:00+05:30,50,52,49,51,300000,,,Unknown,UP,Unknown\n'
    ),
    'filter2_minervini_filter_list.csv': (
        'trading_symbol,name,instrument_token,currentClose,ma_200,ma_50,52wh,52wl,new_52_week_high,pct_away_from_52wh,date\n'
        'ABC,ABC,101,111,90.5,100.2,111,70,True,0.0,2026-10-06\n'
    ),
    'filter3_above_pivot.csv': (
        'trading_symbol,name,instrument_token,currentClose,current_high,latestPivot,lastPivotDate,currentDate,above_pivot_by,above_pivot_percent,pivot_count\n'
        'ABC,ABC,101,111,112,108,2026-09-20,2026-10-06,3,2.78,12\n'
    ),
}


def write_sample_results(results_dir):
    for suffix, content in SAMPLE_CSVS.items():
        with open(os.path.join(results_dir, f'{RUN_DATE}_{suffix}'), 'w') as f:
            f.write(content)


class BuildDocumentsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        write_sample_results(self.tmp.name)
        self.documents = {d['_id']: d for d in build_documents(RUN_DATE, self.tmp.name)}

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_document_per_dataset_and_date(self):
        self.assertEqual(sorted(self.documents), [
            'screenerSnapshot-allStocks-2026-10-05',
            'screenerSnapshot-allStocks-2026-10-06',
            'screenerSnapshot-breakouts-2026-10-06',
            'screenerSnapshot-topStocks-2026-10-06',
        ])

    def test_ohlc_rows_split_by_candle_date(self):
        latest = self.documents['screenerSnapshot-allStocks-2026-10-06']
        self.assertEqual(latest['rowCount'], 2)
        self.assertEqual([r['date'] for r in latest['rows']], ['2026-10-06', '2026-10-06'])
        self.assertEqual([r['_key'] for r in latest['rows']], ['r0', 'r1'])
        # Missing values become null rather than NaN
        self.assertIsNone(latest['rows'][1]['change'])

    def test_filter2_columns_renamed_and_typed(self):
        row = self.documents['screenerSnapshot-topStocks-2026-10-06']['rows'][0]
        self.assertEqual(row['week52High'], 111)
        self.assertEqual(row['week52Low'], 70)
        self.assertNotIn('52wh', row)
        self.assertIs(row['new_52_week_high'], True)
        self.assertIsInstance(row['instrument_token'], int)


class UploadTest(unittest.TestCase):
    def test_upload_posts_create_or_replace(self):
        uploader = SanityUploader(project_id='proj', dataset='test', token='tok', api_version='2025-02-19')
        documents = [
            {'_id': 'screenerSnapshot-allStocks-2026-10-06', 'dataset': 'allStocks', 'date': '2026-10-06'},
            {'_id': 'screenerSnapshot-topStocks-2026-10-06', 'dataset': 'topStocks', 'date': '2026-10-06'},
        ]
        with mock.patch.object(upload_to_sanity.requests, 'post') as post:
            post.return_value.ok = True
            post.return_value.json.return_value = {}
            self.assertEqual(uploader.upload(documents), 2)

        url = post.call_args.args[0]
        self.assertEqual(url, 'https://proj.api.sanity.io/v2025-02-19/data/mutate/test')
        self.assertEqual(post.call_args.kwargs['headers'], {'Authorization': 'Bearer tok'})
        self.assertEqual(post.call_args.kwargs['json'], {'mutations': [
            {'createOrReplace': documents[0]},
            {'delete': {'id': 'screenerSnapshot.allStocks.2026-10-06'}},
            {'createOrReplace': documents[1]},
            {'delete': {'id': 'screenerSnapshot.topStocks.2026-10-06'}},
        ]})

    def test_upload_batches_large_payloads(self):
        uploader = SanityUploader(project_id='proj', token='tok')
        documents = [{'_id': str(i), 'dataset': 'allStocks', 'date': str(i), 'blob': 'x' * 1000} for i in range(5)]
        with mock.patch.object(upload_to_sanity, 'MAX_REQUEST_BYTES', 2500), \
                mock.patch.object(upload_to_sanity.requests, 'post') as post:
            post.return_value.ok = True
            self.assertEqual(uploader.upload(documents), 5)
        self.assertEqual(post.call_count, 3)

    def test_push_skips_when_not_configured(self):
        with mock.patch.dict(os.environ, {'SANITY_PROJECT_ID': '', 'SANITY_API_TOKEN': ''}), \
                mock.patch.object(upload_to_sanity.requests, 'post') as post:
            result = push_results_to_sanity(RUN_DATE)
        self.assertTrue(result['skipped'])
        post.assert_not_called()

    def test_push_reports_api_errors_without_raising(self):
        with tempfile.TemporaryDirectory() as results_dir:
            write_sample_results(results_dir)
            with mock.patch.dict(os.environ, {'SANITY_PROJECT_ID': 'proj', 'SANITY_API_TOKEN': 'tok'}), \
                    mock.patch.object(upload_to_sanity.requests, 'post') as post:
                post.return_value.ok = False
                post.return_value.status_code = 401
                post.return_value.text = 'Unauthorized'
                result = push_results_to_sanity(RUN_DATE, results_dir)
        self.assertFalse(result['success'])
        self.assertIn('401', result['error'])


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Tests for reusing Filter1's history in Filter2/Filter3, the vectorised pivot search and the
throttled historical-data calls, all against a mocked Kite API.
"""

import os
import random
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('KITE_API_KEY', 'test-key')
os.environ.setdefault('KITE_API_SECRET', 'test-secret')

import pandas as pd
from kiteconnect.exceptions import InputException, NetworkException

import history_cache
import kite_service
from filter1 import Filter1
from filter2 import Filter2
from filter3 import Filter3
from history_cache import HistoryCache, history_date_range

IST = timezone(timedelta(hours=5, minutes=30))


def make_candles(days, seed=1, start_price=100.0):
    rng = random.Random(seed)
    candles, price = [], start_price
    day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    while day.date() <= datetime.now().date():
        if day.weekday() < 5:
            open_price = price
            price = price * (1 + 0.002 + rng.gauss(0, 0.02))
            candles.append({
                'date': day.replace(tzinfo=IST),
                'open': round(open_price, 2),
                'high': round(max(open_price, price) * 1.01, 2),
                'low': round(min(open_price, price) * 0.99, 2),
                'close': round(price, 2),
                'volume': 500000,
            })
        day += timedelta(days=1)
    return candles


def reference_pivots(highs, lookback):
    """The original row-by-row pivot search."""
    flags = [False] * len(highs)
    for i in range(lookback, len(highs) - lookback):
        prev_highs = highs[i - lookback:i]
        next_highs = highs[i + 1:i + lookback + 1]
        flags[i] = all(highs[i] > h for h in prev_highs) and all(highs[i] > h for h in next_highs)
    return flags


class PivotTest(unittest.TestCase):
    def test_matches_row_by_row_search(self):
        filter3 = Filter3.__new__(Filter3)
        rng = random.Random(7)
        for lookback in (2, 5):
            for _ in range(50):
                # Few distinct values so ties are common
                highs = [float(rng.randint(1, 12)) for _ in range(rng.randint(0, 60))]
                if highs and rng.random() < 0.3:
                    highs[rng.randrange(len(highs))] = float('nan')
                df = filter3.find_pivot_points(pd.DataFrame({'high': highs}), lookback=lookback)
                expected = reference_pivots(highs, lookback) if len(highs) >= 2 * lookback + 1 else [False] * len(highs)
                self.assertEqual(list(df['is_pivot']) if highs else [], expected)


class SharedHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(history_cache, 'HISTORY_DIR', self.tmp.name),
            mock.patch.object(HistoryCache, '_memory', {}),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.tmp.cleanup()

    def test_filters_read_cached_history_without_calling_kite(self):
        from_date, to_date = history_date_range()
        candles = make_candles(365)
        HistoryCache(from_date, to_date).put_all({101: pd.DataFrame(candles)})
        # A fresh process (CLI run) only has the file on disk
        HistoryCache._memory.clear()

        for filter_class in (Filter2, Filter3):
            instance = filter_class.__new__(filter_class)
            instance.kite_service = mock.Mock()
            df = instance.fetch_historical_data(101, 'ABC', from_date, to_date)
            instance.kite_service.historical_data.assert_not_called()
            self.assertEqual(list(df.columns[:2]), ['trading_symbol', 'instrument_token'])
            pd.testing.assert_frame_equal(df.drop(columns=['trading_symbol', 'instrument_token']),
                                          pd.DataFrame(candles))

    def test_uncached_instrument_falls_back_to_kite(self):
        from_date, to_date = history_date_range()
        HistoryCache(from_date, to_date).put_all({})
        instance = Filter2.__new__(Filter2)
        instance.kite_service = mock.Mock()
        instance.kite_service.historical_data.return_value = {'success': True, 'data': make_candles(30)}
        df = instance.fetch_historical_data(202, 'XYZ', from_date, to_date)
        instance.kite_service.historical_data.assert_called_once()
        self.assertFalse(df.empty)

    def test_filter1_screens_last_ten_days_and_caches_the_year(self):
        candles = make_candles(365)
        instruments_path = os.path.join(self.tmp.name, 'instruments.csv')
        pd.DataFrame([{'instrument_token': 101, 'tradingsymbol': 'ABC', 'name': 'Abc Ltd'}]).to_csv(
            instruments_path, index=False)

        filter1 = Filter1.__new__(Filter1)
        filter1.kite_service = mock.Mock()
        filter1.kite_service.historical_data.return_value = {
            'success': True, 'data': candles, 'count': len(candles)}
        with mock.patch('filter1.RESULTS_DIR', self.tmp.name):
            filter1.fetch_instruments_and_historical_data(instruments_path, 'ohlc.csv', cache_history=True)

        from_date, to_date = history_date_range()
        call = filter1.kite_service.historical_data.call_args.kwargs
        self.assertEqual((call['from_date'], call['to_date']), (from_date, to_date))

        ohlc = pd.read_csv(os.path.join(self.tmp.name, f'{to_date}_ohlc.csv'))
        ten_days_ago = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        recent = [c for c in candles if str(c['date'])[:10] >= ten_days_ago]
        self.assertEqual(len(ohlc), len(recent))
        self.assertEqual(ohlc['close'].tolist(), [c['close'] for c in recent])

        HistoryCache._memory.clear()
        self.assertEqual(len(HistoryCache(from_date, to_date).get(101)), len(candles))


class ProcessCsvTest(unittest.TestCase):
    def test_splits_indices_and_tradable_equities(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'instruments'))
            pd.DataFrame([
                {'instrument_token': 1, 'tradingsymbol': 'NIFTY 50', 'name': 'NIFTY 50', 'lot_size': 0, 'segment': 'INDICES'},
                {'instrument_token': 2, 'tradingsymbol': 'ABC', 'name': 'Abc Ltd', 'lot_size': 1, 'segment': 'NSE'},
                {'instrument_token': 3, 'tradingsymbol': 'FUT', 'name': 'Fut', 'lot_size': 50, 'segment': 'NSE'},
                {'instrument_token': 4, 'tradingsymbol': 'NONAME', 'name': None, 'lot_size': 1, 'segment': 'NSE'},
                {'instrument_token': 5, 'tradingsymbol': 'BLANK', 'name': '  ', 'lot_size': 1, 'segment': 'NSE'},
            ]).to_csv(os.path.join(tmp, 'instruments', 'nse-instruments.csv'), index=False)

            with mock.patch('filter1.RESULTS_DIR', tmp), \
                    mock.patch('filter1.INSTRUMENTS_DIR', os.path.join(tmp, 'static')):
                Filter1.__new__(Filter1).process_csv()

            indices = pd.read_csv(os.path.join(tmp, 'static', 'nse-indices.csv'))
            others = pd.read_csv(os.path.join(tmp, 'static', 'nse-other-instruments.csv'))
            self.assertEqual(indices['tradingsymbol'].tolist(), ['NIFTY 50'])
            self.assertEqual(others['tradingsymbol'].tolist(), ['ABC'])


class HistoricalDataRetryTest(unittest.TestCase):
    def setUp(self):
        self.service = kite_service.KiteService()
        self.service.kite = mock.Mock()
        patch = mock.patch.object(kite_service.time, 'sleep')
        self.sleep = patch.start()
        self.addCleanup(patch.stop)

    def test_retries_rate_limited_requests(self):
        self.service.kite.historical_data.side_effect = [NetworkException('Too many requests'), [{'close': 1}]]
        result = self.service.historical_data(101, '2026-01-01', '2026-01-10', 'day')
        self.assertTrue(result['success'])
        self.assertEqual(self.service.kite.historical_data.call_count, 2)

    def test_does_not_retry_other_errors(self):
        self.service.kite.historical_data.side_effect = InputException('invalid token')
        result = self.service.historical_data(101, '2026-01-01', '2026-01-10', 'day')
        self.assertFalse(result['success'])
        self.assertEqual(self.service.kite.historical_data.call_count, 1)

    def test_requests_are_spaced_to_the_rate_limit(self):
        with mock.patch.object(kite_service, 'HISTORICAL_REQUESTS_PER_SECOND', 3), \
                mock.patch.object(kite_service.KiteService, '_historical_last_call', 0.0), \
                mock.patch.object(kite_service.time, 'monotonic', side_effect=[100.0, 100.0, 100.1, 100.4]):
            kite_service.KiteService._wait_for_historical_slot()
            kite_service.KiteService._wait_for_historical_slot()
        self.assertAlmostEqual(self.sleep.call_args.args[0], 1 / 3 - 0.1)


if __name__ == '__main__':
    unittest.main()

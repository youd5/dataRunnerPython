#!/usr/bin/env python3
"""
Tests for the intraday cache, Filter4's acceptance verdicts and the acceptance backtest,
against a mocked Kite API.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest import mock

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('KITE_API_KEY', 'test-key')
os.environ.setdefault('KITE_API_SECRET', 'test-secret')

import pandas as pd

import backtest_acceptance
import history_cache
import intraday_cache
from filter4 import Filter4, acceptance_verdict, evaluate_breakout
from market_profile import session_profiles
from history_cache import HistoryCache
from intraday_cache import IntradayCache, fetch_intraday, normalise_bars


def session_bars(day, ranges):
    """Kite-style 30-minute candles for one session from (low, high) pairs; closes at the last high."""
    times = pd.date_range(f'{day} 09:15', periods=len(ranges), freq='30min', tz='Asia/Kolkata')
    return [{'date': t.to_pydatetime(), 'open': float(low), 'high': float(high), 'low': float(low),
             'close': float(high), 'volume': 10000} for t, (low, high) in zip(times, ranges)]


def flat_session(day, low, high, close=None):
    candles = session_bars(day, [(low, high)] * 13)
    if close is not None:
        candles[-1]['close'] = float(close)
    return candles


def daily_from(candles):
    df = pd.DataFrame(candles)
    df['day'] = df['date'].map(lambda d: d.strftime('%Y-%m-%d'))
    return [{'date': pd.Timestamp(day, tz='Asia/Kolkata').to_pydatetime(), 'open': g['open'].iloc[0],
             'high': g['high'].max(), 'low': g['low'].min(), 'close': g['close'].iloc[-1], 'volume': 130000}
            for day, g in df.groupby('day')]


DAYS = [d.strftime('%Y-%m-%d') for d in pd.bdate_range('2026-09-01', periods=10)]


def accepted_stock():
    """Eight sessions at 95-100, then value builds above the 100 pivot."""
    candles = []
    for day in DAYS[:7]:
        candles += flat_session(day, 95, 100)
    candles += flat_session(DAYS[7], 101, 105)
    candles += flat_session(DAYS[8], 103, 107)
    candles += flat_session(DAYS[9], 104, 108)
    return candles


def rejected_stock():
    """Value stays at 97-100; the last session spikes to 106 in one period and closes at 100.3."""
    candles = []
    for day in DAYS[:9]:
        candles += flat_session(day, 95, 100)
    last = session_bars(DAYS[9], [(97, 100)] * 12 + [(100, 106)])
    last[-1]['close'] = 100.3
    return candles + last


class IntradayCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patch = mock.patch.object(IntradayCache, '_memory', {})
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)
        self.kite = mock.Mock()
        self.kite.historical_data.return_value = {'success': True, 'data': flat_session(DAYS[0], 95, 100)}

    def fetch(self, tokens):
        return fetch_intraday(self.kite, tokens, run_date=datetime(2026, 10, 9), history_dir=self.tmp.name)

    def test_fetches_only_missing_tokens_and_reloads_from_disk(self):
        self.fetch([1])
        call = self.kite.historical_data.call_args.kwargs
        self.assertEqual((call['interval'], call['to_date']), ('30minute', '2026-10-09 15:30:00'))
        self.assertEqual(call['from_date'], '2026-09-04 09:15:00')

        self.fetch([1, 2])
        tokens = [c.kwargs['instrument_token'] for c in self.kite.historical_data.call_args_list]
        self.assertEqual(tokens, [1, 2])

        # A new process only has the file
        IntradayCache._memory.clear()
        self.kite.reset_mock()
        result = self.fetch([1, 2])
        self.kite.historical_data.assert_not_called()
        self.assertEqual(len(result[2]), 13)

    def test_backtest_cache_does_not_replace_the_daily_one(self):
        self.fetch([1])
        fetch_intraday(self.kite, [1], run_date=datetime(2026, 10, 9), kind='backtest', history_dir=self.tmp.name)
        self.assertEqual(sorted(os.listdir(self.tmp.name)),
                         ['2026-10-09_30minute.pkl', '2026-10-09_30minute_backtest.pkl'])

    def test_normalise_keeps_regular_session_in_market_time(self):
        candles = [{'date': datetime(2026, 10, 9, 9, 0), 'open': 1, 'high': 1, 'low': 1, 'close': 1, 'volume': 1},
                   {'date': datetime(2026, 10, 9, 9, 15), 'open': 1, 'high': 2, 'low': 1, 'close': 2, 'volume': 1},
                   {'date': datetime(2026, 10, 9, 15, 30), 'open': 1, 'high': 1, 'low': 1, 'close': 1, 'volume': 1}]
        bars = normalise_bars(candles)
        self.assertEqual(len(bars), 1)
        self.assertEqual(str(bars['date'].dt.tz), 'Asia/Kolkata')
        self.assertEqual(bars['session'].tolist(), ['2026-10-09'])


class VerdictTest(unittest.TestCase):
    def profile(self, **kw):
        p = {'val': 98, 'vah': 104, 'poc': 101, 'close': 103, 'selling_tail': 0, 'poor_high': False}
        p.update(kw)
        return p

    def test_value_above_the_level_is_accepted(self):
        self.assertEqual(acceptance_verdict(self.profile(val=100.5), 'overlapping', 100), 'ACCEPTED')
        self.assertEqual(acceptance_verdict(self.profile(), 'overlapping-higher', 100), 'ACCEPTED')

    def test_straddling_value_is_testing(self):
        self.assertEqual(acceptance_verdict(self.profile(), 'overlapping', 100), 'TESTING')

    def test_value_or_close_below_is_rejected(self):
        self.assertEqual(acceptance_verdict(self.profile(poc=99), 'overlapping', 100), 'REJECTED')
        self.assertEqual(acceptance_verdict(self.profile(close=99.5), 'overlapping', 100), 'REJECTED')

    def test_selling_tail_back_at_the_level_is_rejected(self):
        p = self.profile(close=100.3, selling_tail=3)
        self.assertEqual(acceptance_verdict(p, 'overlapping', 100), 'REJECTED')
        self.assertEqual(acceptance_verdict(dict(p, close=103), 'overlapping', 100), 'TESTING')


class BreakoutLevelTest(unittest.TestCase):
    def test_level_is_the_pivot_even_below_a_balance_bracket(self):
        # 20 days falling to 114, then 8 days balancing at 100-104; the pivot (100) is below the bracket top
        ranges = [(130 - i, 133 - i) for i in range(20)] + [(100, 104), (101, 103.5), (100.5, 104), (100, 103),
                                                            (101, 104), (100.2, 103.8), (100.5, 103), (101, 104)]
        ranges.append((101, 103))
        daily = pd.DataFrame({'date': pd.bdate_range('2026-08-03', periods=len(ranges)),
                              'high': [h for _, h in ranges], 'low': [l for l, _ in ranges],
                              'close': [h - 0.5 for _, h in ranges]})
        profiles = session_profiles(normalise_bars(accepted_stock()), 0.05)
        row = evaluate_breakout(profiles, daily, pivot_high=100)
        self.assertEqual(row['breakoutLevel'], 100)
        self.assertGreater(row['bracketHigh'], 100)


class Filter4RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for patch in (mock.patch.object(IntradayCache, '_memory', {}),
                      mock.patch.object(HistoryCache, '_memory', {}),
                      mock.patch.object(intraday_cache, 'HISTORY_DIR', self.tmp.name),
                      mock.patch.object(history_cache, 'HISTORY_DIR', self.tmp.name)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_ranks_accepted_breakouts_first(self):
        candles = {101: accepted_stock(), 102: rejected_stock()}
        breakouts = os.path.join(self.tmp.name, 'filter3.csv')
        pd.DataFrame([
            {'trading_symbol': 'REJ', 'instrument_token': 102, 'currentClose': 100.3, 'latestPivot': 100,
             'lastPivotDate': '2026-08-20'},
            {'trading_symbol': 'ACC', 'instrument_token': 101, 'currentClose': 108, 'latestPivot': 100,
             'lastPivotDate': '2026-08-20'},
        ]).to_csv(breakouts, index=False)

        def historical_data(instrument_token, interval, **_):
            data = candles[instrument_token] if interval == '30minute' else daily_from(candles[instrument_token])
            return {'success': True, 'data': data}

        filter4 = Filter4.__new__(Filter4)
        filter4.kite_service = mock.Mock()
        filter4.kite_service.historical_data.side_effect = historical_data
        output = os.path.join(self.tmp.name, 'filter4.csv')
        result = filter4.run_filter(csv_path=breakouts, output_path=output)

        saved = pd.read_csv(output)
        self.assertEqual(saved['trading_symbol'].tolist(), ['ACC', 'REJ'])
        self.assertEqual(saved['verdict'].tolist(), ['ACCEPTED', 'REJECTED'])
        acc = result.iloc[0]
        self.assertEqual(acc['valueRelationship'], 'overlapping-higher')
        self.assertEqual(acc['higherValueDays'], 3)
        self.assertEqual(acc['sessionDate'], DAYS[9])
        self.assertTrue(acc['profileComplete'])
        rej = result.iloc[1]
        self.assertTrue(rej['sellingTail'])
        self.assertLessEqual(rej['poc'], 100)  # value never left the old range


class BacktestTest(unittest.TestCase):
    def test_signals_only_use_confirmed_pivots(self):
        highs = [100] * 10 + [110] + [100] * 10
        daily = pd.DataFrame({'high': highs, 'low': [h - 5 for h in highs], 'close': [h - 1 for h in highs]})
        daily.loc[13, 'close'] = 111  # above the pivot, but it is only confirmed after day 15
        daily.loc[16, 'close'] = 112
        daily.loc[17, 'close'] = 113  # not fresh: the previous close was already above
        signals = backtest_acceptance.find_signals(daily)
        self.assertEqual([s['index'] for s in signals], [16])
        self.assertEqual(signals[0]['pivot_high'], 110)
        self.assertEqual(len(backtest_acceptance.find_signals(daily, fresh_only=False)), 2)

    def test_trend_template_matches_filter2_on_each_day(self):
        from filter2 import Filter2
        import random
        rng = random.Random(3)
        closes, price = [], 100.0
        for _ in range(400):
            price *= 1 + 0.002 + rng.gauss(0, 0.015)
            closes.append(price)
        flags = backtest_acceptance.trend_template_flags(pd.DataFrame({'close': closes}))
        filter2 = Filter2.__new__(Filter2)
        for end in (250, 300, 350, 400):
            df = filter2.calculate_moving_averages_and_52wh_52wl(pd.DataFrame({'close': closes[:end]}))
            self.assertEqual(flags.iloc[end - 1], filter2.is_minervini_condition_fulfilled(df))
        self.assertTrue(flags.any())
        self.assertFalse(flags.iloc[:244].any())  # not enough history for a 52-week range

    def test_long_daily_is_fetched_once_and_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            kite = mock.Mock()
            kite.historical_data.return_value = {'success': True, 'data': [{'date': '2026-10-09', 'close': 1}]}
            backtest_acceptance.fetch_long_daily(kite, [1], '2026-10-10', history_dir=tmp)
            self.assertEqual(kite.historical_data.call_args.kwargs['from_date'], '2024-10-10')
            backtest_acceptance.fetch_long_daily(kite, [1, 2], '2026-10-10', history_dir=tmp)
            tokens = [c.kwargs['instrument_token'] for c in kite.historical_data.call_args_list]
            self.assertEqual(tokens, [1, 2])

    def test_backtest_stock_scores_signals_with_forward_returns(self):
        days = [d.strftime('%Y-%m-%d') for d in pd.bdate_range('2026-06-01', periods=40)]
        candles = []
        for i, day in enumerate(days):
            if i == 12:
                candles += flat_session(day, 104, 110)  # the pivot day
            elif i < 25:
                candles += flat_session(day, 100, 104)
            else:
                # Breakout on day 25, then value keeps rising
                candles += flat_session(day, 109 + (i - 25), 115 + (i - 25))
        bars = normalise_bars(candles)
        daily = pd.DataFrame(daily_from(candles))

        rows = backtest_acceptance.backtest_stock('ABC', 1, daily, bars)
        self.assertEqual([r['signalDate'] for r in rows], [days[25]])
        row = rows[0]
        self.assertEqual(row['latestPivot'], 110)
        self.assertEqual(row['verdict'], 'ACCEPTED')
        self.assertAlmostEqual(row['ret5'], round((120 / 115 - 1) * 100, 2))
        self.assertIsNone(row['ret20'])  # only 14 sessions after the signal

        summary = backtest_acceptance.summarise(pd.DataFrame(rows))
        self.assertEqual(summary.loc['ACCEPTED', 'signals'], 1)


if __name__ == '__main__':
    unittest.main()

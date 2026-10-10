#!/usr/bin/env python3
"""
Tests for the Market Profile engine, on small hand-built sessions whose profile is worked out
in the comments.
"""

import os
import sys
import unittest

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd

import market_profile as mp


def bars(ranges, close=None, volume=1000, session='2026-10-09'):
    """30-minute bars from (low, high) pairs; open at the first low, close as given."""
    times = pd.date_range(f'{session} 09:15', periods=len(ranges), freq='30min', tz='Asia/Kolkata')
    rows = []
    for t, (low, high) in zip(times, ranges):
        rows.append({'date': t, 'open': low, 'high': high, 'low': low, 'close': high, 'volume': volume})
    df = pd.DataFrame(rows).astype({c: float for c in ('open', 'high', 'low', 'close')})
    df.loc[0, 'open'] = ranges[0][0]
    if close is not None:
        df.loc[len(df) - 1, 'close'] = close
    df['session'] = session
    return df


class PriceStepTest(unittest.TestCase):
    def test_about_a_tenth_of_a_percent_in_whole_ticks(self):
        self.assertEqual(mp.price_step(3000, 0.05), 3.0)
        self.assertEqual(mp.price_step(50, 0.05), 0.05)  # 0.05 is already 0.1%
        self.assertEqual(mp.price_step(20, 0.05), 0.05)  # never below a tick
        self.assertEqual(mp.price_step(1234, 0.1), 1.2)


class ProfileTest(unittest.TestCase):
    def test_tpo_counts_letters_and_volume(self):
        # A: 10-12, B: 11-13 with step 1 -> 10:A 11:AB 12:AB 13:B
        profile = mp.build_tpo_profile(bars([(10, 12), (11, 13)], volume=300), step=1)
        self.assertEqual(profile['price'].tolist(), [10, 11, 12, 13])
        self.assertEqual(profile['tpo_count'].tolist(), [1, 2, 2, 1])
        self.assertEqual(profile['letters'].tolist(), ['A', 'AB', 'AB', 'B'])
        self.assertEqual(profile['approx_volume'].tolist(), [100, 200, 200, 100])

    def test_poc_tie_goes_to_the_middle(self):
        # A 10-12, B 11-13, C 11-14 -> counts 1,3,3,2,1 at 10..14
        profile = mp.build_tpo_profile(bars([(10, 12), (11, 13), (11, 14)]), step=1)
        self.assertEqual(profile['tpo_count'].tolist(), [1, 3, 3, 2, 1])
        # Tie at 11 and 12; the middle of the range is 12
        self.assertEqual(mp.poc(profile), 12)

    def test_value_area_adds_the_heavier_pair_of_buckets(self):
        # Counts at 10..18: 1 1 2 3 5 3 2 1 1 = 19 TPOs; 70% = 13.3
        counts = [1, 1, 2, 3, 5, 3, 2, 1, 1]
        profile = pd.DataFrame({'price': range(10, 19), 'tpo_count': counts,
                                'letters': [''] * 9, 'approx_volume': [0.0] * 9})
        # POC 14 (5). Up 15+16 = 5, down 13+12 = 5: tie adds both -> 12..16 = 15 TPOs >= 13.3
        self.assertEqual(mp.value_area(profile), (12.0, 16.0))
        # 25% = 4.75: the POC alone (5) is enough
        self.assertEqual(mp.value_area(profile, pct=0.25), (14.0, 14.0))

    def test_value_area_one_sided(self):
        counts = [1, 1, 1, 6, 2]
        profile = pd.DataFrame({'price': range(5), 'tpo_count': counts,
                                'letters': [''] * 5, 'approx_volume': [0.0] * 5})
        # POC at 3 (6 of 11; 70% = 7.7). Up: only bucket 4 (2). Down 2+1 = 2: tie -> both
        self.assertEqual(mp.value_area(profile), (1.0, 4.0))

    def test_selling_tail_and_poor_low(self):
        # A,B,C build 100-102 (3 TPOs each); D spikes 102-106 alone -> singles 103..106 at the top
        session = bars([(100, 102), (100, 102), (100, 102), (102, 106)], close=102.5)
        profile = mp.build_tpo_profile(session, step=1)
        t = mp.tails(profile)
        self.assertEqual(t['selling_tail'], 4)
        self.assertEqual(t['buying_tail'], 0)
        self.assertTrue(t['poor_low'])
        self.assertFalse(t['poor_high'])

    def test_short_single_run_is_not_a_tail(self):
        profile = mp.build_tpo_profile(bars([(100, 102), (100, 103)]), step=1)
        self.assertEqual(mp.tails(profile)['selling_tail'], 0)  # one single print only

    def test_interior_single_prints(self):
        # Two distributions joined by single prints 103-105 (only period C traded there)
        session = bars([(100, 102), (100, 102), (101, 106), (106, 108), (106, 108)])
        profile = mp.build_tpo_profile(session, step=1)
        self.assertEqual(mp.single_prints(profile), [(103, 105)])


class DayTypeTest(unittest.TestCase):
    def profile(self, ranges, close, step=1):
        session = bars(ranges, close=close)
        p = mp.session_profile(session, tick_size=step)
        return p

    def test_up_trend_day(self):
        # Narrow IB 100-101, then steady extension up to 110 and a close at the high
        p = self.profile([(100, 101), (100, 101), (101, 103), (103, 105), (105, 107), (107, 109), (108, 110)], close=110)
        self.assertEqual(p['day_type'], 'trend')
        self.assertEqual(p['direction'], 'up')

    def test_non_trend_day(self):
        p = self.profile([(100, 100.4), (100, 100.4), (100.1, 100.3)], close=100.2, step=0.05)
        self.assertEqual(p['day_type'], 'non-trend')

    def test_normal_day(self):
        # Wide IB 100-110 that holds all day
        p = self.profile([(100, 106), (104, 110), (103, 108), (102, 107)], close=105)
        self.assertEqual(p['day_type'], 'normal')

    def test_neutral_center(self):
        p = self.profile([(100, 104), (101, 104), (103, 106), (98, 102), (100, 103)], close=102)
        self.assertEqual(p['day_type'], 'neutral-center')

    def test_double_distribution_trend(self):
        # IB 100-102, a fast move through 103-106 in one period, then a second distribution at 107-110
        p = self.profile([(100, 102), (100, 102), (102, 107), (107, 110), (107, 110), (107, 110)], close=109)
        self.assertEqual(p['day_type'], 'double-distribution-trend')

    def test_normal_variation(self):
        # IB 100-106, extension to 109 (50% of IB), close mid-range
        p = self.profile([(100, 104), (102, 106), (104, 109), (103, 106)], close=105)
        self.assertEqual(p['day_type'], 'normal-variation')


def make_profile(val, vah, poc, low=None, high=None, close=None, session=None):
    return {'val': val, 'vah': vah, 'poc': poc, 'low': low if low is not None else val - 1,
            'high': high if high is not None else vah + 1, 'close': close if close is not None else poc,
            'session': session}


class ValueTest(unittest.TestCase):
    def test_relationships(self):
        prev = make_profile(100, 110, 105)
        self.assertEqual(mp.value_relationship(prev, make_profile(111, 120, 115)), 'higher')
        self.assertEqual(mp.value_relationship(prev, make_profile(90, 99, 95)), 'lower')
        self.assertEqual(mp.value_relationship(prev, make_profile(105, 115, 110)), 'overlapping-higher')
        self.assertEqual(mp.value_relationship(prev, make_profile(95, 105, 100)), 'overlapping-lower')
        self.assertEqual(mp.value_relationship(prev, make_profile(102, 108, 105)), 'overlapping')

    def test_migration_counts_higher_days_ending_today(self):
        profiles = [make_profile(100, 110, 105), make_profile(95, 105, 100),  # lower
                    make_profile(98, 108, 103), make_profile(109, 115, 112),  # overlapping-higher, higher
                    make_profile(112, 118, 115)]  # overlapping-higher
        migration = mp.value_migration(profiles, window=5)
        self.assertEqual(migration['relationships'],
                         ['overlapping-lower', 'overlapping-higher', 'higher', 'overlapping-higher'])
        self.assertEqual(migration['higher_days'], 3)
        self.assertGreater(migration['poc_slope_pct'], 0)

    def test_naked_pocs(self):
        profiles = [make_profile(100, 110, 105, low=99, high=111, session='d1'),
                    make_profile(112, 118, 115, low=111.5, high=119, session='d2'),
                    make_profile(120, 125, 122, low=114, high=126, session='d3')]
        # d1's POC 105 was never revisited; d2's 115 was traded through on d3
        self.assertEqual(mp.naked_pocs(profiles), [{'session': 'd1', 'poc': 105}])


class BalanceTest(unittest.TestCase):
    def daily(self, ranges, closes):
        return pd.DataFrame({'date': pd.date_range('2026-09-01', periods=len(ranges), freq='B'),
                             'high': [h for _, h in ranges], 'low': [l for l, _ in ranges],
                             'close': closes})

    def test_bracket_then_breakout(self):
        # 20 days falling from 133 to 114 to build an ATR, 8 days of 100-104 balance, then a close at 108
        trend = [(130 - i, 133 - i) for i in range(20)]
        balance = [(100, 104), (101, 103.5), (100.5, 104), (100, 103), (101, 104), (100.2, 103.8),
                   (100.5, 103), (101, 104)]
        ranges = trend + balance + [(104, 108.5)]
        closes = [h - 1 for _, h in ranges[:-1]] + [108]
        daily = self.daily(ranges, closes)
        bracket = mp.detect_balance(daily, atr_mult=2)
        self.assertEqual((bracket['bracket_low'], bracket['bracket_high']), (100, 104))
        self.assertEqual(bracket['days'], 8)
        self.assertEqual(mp.breakout_from_balance(daily, bracket), {'position': 'above', 'closes_above': 1})

    def test_no_bracket_in_a_trend(self):
        ranges = [(100 + 3 * i, 102 + 3 * i) for i in range(30)]
        daily = self.daily(ranges, [h for _, h in ranges])
        self.assertIsNone(mp.detect_balance(daily))


if __name__ == '__main__':
    unittest.main()

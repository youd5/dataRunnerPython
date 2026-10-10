#!/usr/bin/env python3
"""
Filter4: does the market accept Filter3's breakouts? ("Mind Over Markets": price advertises,
time and volume confirm.)

For each stock above its last pivot (Filter3), build a Market Profile of the last ~20 sessions
from Kite 30-minute candles (one request per stock) and check whether value has moved above the
breakout level, or whether price only poked above it and was rejected.

Breakout level L = the Filter3 pivot high, or the top of the balance bracket the stock is leaving
if that is higher. Verdict:
- ACCEPTED: today's value area is above L (VAL >= L), or the POC is above L with value
  migrating higher
- REJECTED: the close or POC is below L, or the session left a selling tail / poor high and
  closed back near L
- TESTING: anything in between (the close is above L, the value area straddles it)
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from kite_service import KiteService, RESULTS_DIR
from history_cache import HistoryCache, history_date_range
from intraday_cache import fetch_intraday, INTRADAY_INTERVAL, INTRADAY_CALENDAR_DAYS
from market_profile import (HIGHER_VALUE, breakout_from_balance, detect_balance, naked_pocs,
                            session_profiles, value_migration)

INSTRUMENTS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'instruments',
                               'nse-other-instruments.csv')

# A close within this fraction above L still counts as "back near the breakout level"
NEAR_LEVEL_PCT = 0.005
# The last 30-minute bar of a complete NSE session starts at 15:15
LAST_BAR_START = (15, 15)
MIGRATION_WINDOW = 5

VERDICT_SCORE = {'ACCEPTED': 300, 'TESTING': 200, 'REJECTED': 100}
# Small tie-breaker by how the latest session auctioned (only when it extended upwards or not at all)
DAY_TYPE_SCORE = {
    'trend': 5, 'double-distribution-trend': 5, 'normal-variation': 4, 'neutral-extreme': 3,
    'normal': 2, 'neutral-center': 1, 'non-trend': 0,
}


def acceptance_verdict(today: Dict[str, Any], relationship: Optional[str], level: float) -> str:
    """ACCEPTED / TESTING / REJECTED for today's profile against breakout level L."""
    if today['val'] >= level or (today['poc'] > level and relationship in HIGHER_VALUE):
        return 'ACCEPTED'
    if today['close'] < level or today['poc'] < level:
        return 'REJECTED'
    if (today['selling_tail'] or today['poor_high']) and today['close'] <= level * (1 + NEAR_LEVEL_PCT):
        return 'REJECTED'
    return 'TESTING'


def profile_complete(today: Dict[str, Any]) -> bool:
    last_bar = today.get('last_bar')
    if last_bar is None:
        return False
    return (last_bar.hour, last_bar.minute) >= LAST_BAR_START


def evaluate_breakout(profiles: List[Dict[str, Any]], daily: pd.DataFrame, pivot_high: float,
                      window: int = MIGRATION_WINDOW) -> Dict[str, Any]:
    """
    Filter4's columns for one stock, from its session profiles (oldest first) and daily candles,
    both ending on the day being judged. Used by Filter4 and by the backtest.
    """
    today = profiles[-1]
    migration = value_migration(profiles, window)
    bracket = detect_balance(daily) if daily is not None and len(daily) else None
    balance = breakout_from_balance(daily, bracket)
    bracket_high = bracket['bracket_high'] if bracket else None
    level = max(pivot_high, bracket_high) if bracket_high is not None else pivot_high
    verdict = acceptance_verdict(today, migration['today'], level)

    naked = naked_pocs(profiles)
    above = [n['poc'] for n in naked if n['poc'] > today['close']]
    below = [n['poc'] for n in naked if n['poc'] < today['close']]

    day_score = DAY_TYPE_SCORE.get(today['day_type'], 0) if today['direction'] in ('up', None) else 0
    score = VERDICT_SCORE[verdict] + 10 * migration['higher_days'] + day_score

    return {
        'breakoutLevel': round(level, 2),
        'poc': today['poc'],
        'vah': today['vah'],
        'val': today['val'],
        'ibHigh': today['ib_high'],
        'ibLow': today['ib_low'],
        'dayType': today['day_type'],
        'dayDirection': today['direction'],
        'valueRelationship': migration['today'],
        'higherValueDays': migration['higher_days'],
        'pocSlopePct': migration['poc_slope_pct'],
        'sellingTail': bool(today['selling_tail']),
        'buyingTail': bool(today['buying_tail']),
        'poorHigh': bool(today['poor_high']),
        'nakedPocAbove': min(above) if above else None,
        'nakedPocBelow': max(below) if below else None,
        'bracketHigh': bracket_high,
        'bracketLow': bracket['bracket_low'] if bracket else None,
        'bracketDays': bracket['days'] if bracket else None,
        'closesAboveBracket': balance['closes_above'] if bracket else None,
        'verdict': verdict,
        'score': score,
        'profileComplete': profile_complete(today),
        'sessionDate': today['session'],
    }


def load_tick_sizes(csv_path: str = INSTRUMENTS_CSV) -> Dict[int, float]:
    try:
        df = pd.read_csv(csv_path, usecols=['instrument_token', 'tick_size'])
        return dict(zip(df['instrument_token'].astype(int), df['tick_size'].astype(float)))
    except Exception as e:
        print(f"⚠️ Could not read tick sizes from {csv_path} ({e}); using 0.05")
        return {}


class Filter4:
    """Filter4: Market Profile acceptance of Filter3's breakouts."""

    def __init__(self):
        try:
            self.kite_service = KiteService()
            print("✅ Filter4 initialized with KiteService")
        except Exception as e:
            print(f"❌ Failed to initialize Filter4: {e}")
            self.kite_service = None

    def fetch_daily(self, instrument_token: int, from_date: str, to_date: str) -> pd.DataFrame:
        """Daily candles from Filter1's history cache, or from Kite if they are not cached."""
        cached = HistoryCache(from_date, to_date).get(instrument_token)
        if cached is not None:
            return cached.copy()
        result = self.kite_service.historical_data(
            instrument_token=instrument_token, from_date=from_date, to_date=to_date, interval='day')
        if result.get('success') and result.get('data'):
            return pd.DataFrame(result['data'])
        return pd.DataFrame()

    def run_filter(self, csv_path: str = None, output_path: str = None,
                   calendar_days: int = INTRADAY_CALENDAR_DAYS) -> pd.DataFrame:
        """
        Profile every Filter3 breakout and write
        results/<date>_filter4_profile_acceptance.csv, sorted by score.
        """
        if not self.kite_service:
            print("❌ KiteService not initialized. Cannot run filter.")
            return pd.DataFrame()

        run_date = datetime.now().strftime('%Y-%m-%d')
        csv_path = csv_path or f"{RESULTS_DIR}/{run_date}_filter3_above_pivot.csv"
        try:
            breakouts = pd.read_csv(csv_path)
        except Exception as e:
            print(f"❌ Error loading Filter3 results from {csv_path}: {e}")
            return pd.DataFrame()
        if breakouts.empty:
            print("⚠️ No Filter3 breakouts to profile")
            return pd.DataFrame()

        print(f"📊 Profiling {len(breakouts)} breakouts with {INTRADAY_INTERVAL} candles...")
        tokens = breakouts['instrument_token'].astype(int).tolist()
        bars_by_token = fetch_intraday(self.kite_service, tokens, calendar_days=calendar_days)
        tick_sizes = load_tick_sizes()
        from_date, to_date = history_date_range()

        rows = []
        for breakout in breakouts.to_dict(orient='records'):
            symbol, token = breakout['trading_symbol'], int(breakout['instrument_token'])
            try:
                bars = bars_by_token.get(token)
                if bars is None or bars.empty:
                    print(f"⚠️ Skipping {symbol} - no intraday candles")
                    continue
                profiles = session_profiles(bars, tick_sizes.get(token, 0.05))
                daily = self.fetch_daily(token, from_date, to_date)
                row = {
                    'trading_symbol': symbol,
                    'instrument_token': token,
                    'currentClose': breakout['currentClose'],
                    'latestPivot': breakout['latestPivot'],
                    'lastPivotDate': breakout.get('lastPivotDate'),
                }
                row.update(evaluate_breakout(profiles, daily, float(breakout['latestPivot'])))
                rows.append(row)
                print(f"{'✅' if row['verdict'] == 'ACCEPTED' else '⏭️'} {symbol}: {row['verdict']} "
                      f"(VA {row['val']}-{row['vah']}, POC {row['poc']}, level {row['breakoutLevel']}, {row['dayType']})")
            except Exception as e:
                print(f"❌ Error profiling {symbol}: {e}")

        result_df = pd.DataFrame(rows)
        if result_df.empty:
            print("\n⚠️ No breakouts could be profiled")
            return result_df

        result_df = result_df.sort_values('score', ascending=False).reset_index(drop=True)
        output_path = output_path or f"{RESULTS_DIR}/{run_date}_filter4_profile_acceptance.csv"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        result_df.to_csv(output_path, index=False)
        print(f"\n💾 Results saved to: {output_path}")
        print(result_df['verdict'].value_counts().to_string())
        if not result_df['profileComplete'].all():
            print("⚠️ Some profiles are from an unfinished session; rerun after 15:30 IST for final verdicts")
        return result_df


def main():
    """Main function to run Filter4."""
    print("=" * 80)
    print("🔍 Filter4: Market Profile acceptance of Filter3 breakouts")
    print("=" * 80)

    Filter4().run_filter(
        csv_path=f"{RESULTS_DIR}/{datetime.now().strftime('%Y-%m-%d')}_filter3_above_pivot.csv")
    print("\n✅ Filter4 execution complete!")

    # Publish today's results to Sanity for the website (skipped if not configured)
    from upload_to_sanity import push_results_to_sanity
    push_results_to_sanity()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Backtest Filter4: do ACCEPTED breakouts do better than REJECTED ones?

For every session in the 30-minute window (Kite allows ~200 calendar days, ~135 sessions), find
the days a stock first closed above its last pivot (Filter3's rule), judge each with Filter4's
verdict using only data up to that day, and measure what happened next:
+5/+10/+20 session returns and the worst low over the next 20 sessions (max adverse excursion).

No lookahead: a pivot needs 5 later sessions to be confirmed, so on day d only pivots at or
before d-5 count (exactly what Filter3 would have seen on d), and profiles and balance brackets
use data up to d only.

Daily candles come from Filter1's latest history cache (results/history/<date>_daily.pkl); run
Filter1 first. Filter2's trend template is not applied: a year of history leaves too few days
with a full 245-session lookback.

Universe:
  --universe filter1 (default)  every stock in the history cache: one Kite call each, ~3/s
  --universe filter2            today's Filter2 list: quick, but biased towards today's winners
  --limit N                     only the first N stocks

Usage:
  python src/backtest_acceptance.py [--universe filter1|filter2] [--limit N] [--all-days]
"""

import argparse
import glob
import os
import pickle
import sys
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from kite_service import KiteService, RESULTS_DIR
from history_cache import HISTORY_DIR
from intraday_cache import MAX_CALENDAR_DAYS, INTRADAY_INTERVAL, fetch_intraday
from filter3 import Filter3
from filter4 import evaluate_breakout, load_tick_sizes
from market_profile import session_profiles

PIVOT_LOOKBACK = 5
PROFILE_SESSIONS = 20
MIN_PROFILE_SESSIONS = 6  # today plus a value-migration window of 5
HORIZONS = (5, 10, 20)


def load_latest_daily_history(history_dir: str = HISTORY_DIR) -> Dict[int, pd.DataFrame]:
    """Candles from the newest results/history/<date>_daily.pkl, whatever its date."""
    paths = sorted(glob.glob(os.path.join(history_dir, '*_daily.pkl')))
    if not paths:
        return {}
    with open(paths[-1], 'rb') as f:
        saved = pickle.load(f)
    print(f"📦 Using daily history for {len(saved['candles'])} instruments from {paths[-1]}")
    return saved['candles']


def find_signals(daily: pd.DataFrame, lookback: int = PIVOT_LOOKBACK, fresh_only: bool = True) -> List[dict]:
    """
    Days the close was above the last pivot confirmed by then. With fresh_only, only the first
    such day per pivot (the previous close was not above it).
    """
    daily = Filter3.__new__(Filter3).find_pivot_points(daily.reset_index(drop=True), lookback=lookback)
    if 'is_pivot' not in daily.columns:
        return []
    pivot_rows = np.flatnonzero(daily['is_pivot'].to_numpy())
    signals = []
    for d in range(len(daily)):
        confirmed = pivot_rows[pivot_rows <= d - lookback]
        if not len(confirmed):
            continue
        pivot = int(confirmed[-1])
        pivot_high = float(daily['high'].iloc[pivot])
        if daily['close'].iloc[d] <= pivot_high:
            continue
        if fresh_only and d > 0 and daily['close'].iloc[d - 1] > pivot_high:
            continue
        signals.append({'index': d, 'pivot_index': pivot, 'pivot_high': pivot_high})
    return signals


def forward_outcomes(daily: pd.DataFrame, d: int) -> dict:
    close = float(daily['close'].iloc[d])
    outcomes = {}
    for horizon in HORIZONS:
        target = d + horizon
        outcomes[f'ret{horizon}'] = (round(float(daily['close'].iloc[target] / close - 1) * 100, 2)
                                     if target < len(daily) else None)
    future = daily['low'].iloc[d + 1:d + 1 + max(HORIZONS)]
    outcomes['mae20'] = round(float(future.min() / close - 1) * 100, 2) if len(future) else None
    return outcomes


def backtest_stock(symbol: str, token: int, daily: pd.DataFrame, bars: pd.DataFrame,
                   tick_size: float = 0.05, fresh_only: bool = True) -> List[dict]:
    """One row per breakout signal that falls inside the intraday window."""
    daily = daily.sort_values('date').reset_index(drop=True)
    profiles = session_profiles(bars, tick_size)
    position = {p['session']: i for i, p in enumerate(profiles)}
    dates = daily['date'].astype(str).str[:10]

    rows = []
    for signal in find_signals(daily, fresh_only=fresh_only):
        d = signal['index']
        session = dates.iloc[d]
        i = position.get(session)
        if i is None or i + 1 < MIN_PROFILE_SESSIONS:
            continue
        window = profiles[max(0, i + 1 - PROFILE_SESSIONS):i + 1]
        verdict = evaluate_breakout(window, daily.iloc[:d + 1], signal['pivot_high'])
        row = {
            'trading_symbol': symbol,
            'instrument_token': token,
            'signalDate': session,
            'pivotDate': dates.iloc[signal['pivot_index']],
            'latestPivot': signal['pivot_high'],
            'close': float(daily['close'].iloc[d]),
            'verdict': verdict['verdict'],
            'score': verdict['score'],
            'dayType': verdict['dayType'],
            'valueRelationship': verdict['valueRelationship'],
            'higherValueDays': verdict['higherValueDays'],
            'breakoutLevel': verdict['breakoutLevel'],
        }
        row.update(forward_outcomes(daily, d))
        rows.append(row)
    return rows


def summarise(results: pd.DataFrame) -> pd.DataFrame:
    """Count, 20-session win rate, median returns and median MAE per verdict."""
    def stats(group):
        done = group['ret20'].dropna()
        return pd.Series({
            'signals': len(group),
            'winRate20': round((done > 0).mean() * 100, 1) if len(done) else None,
            'medianRet5': group['ret5'].median(),
            'medianRet10': group['ret10'].median(),
            'medianRet20': group['ret20'].median(),
            'medianMae20': group['mae20'].median(),
        })
    groups = dict(tuple(results.groupby('verdict')))
    order = [v for v in ('ACCEPTED', 'TESTING', 'REJECTED') if v in groups]
    return pd.DataFrame([stats(groups[v]) for v in order], index=pd.Index(order, name='verdict'))


def run_backtest(kite_service, universe: str = 'filter1', limit: Optional[int] = None,
                 fresh_only: bool = True, output_dir: Optional[str] = None) -> pd.DataFrame:
    history = load_latest_daily_history()
    if not history:
        print("❌ No daily history cache found; run Filter1 first")
        return pd.DataFrame()

    run_date = datetime.now().strftime('%Y-%m-%d')
    if universe == 'filter2':
        listing = pd.read_csv(f"{RESULTS_DIR}/{run_date}_filter2_minervini_filter_list.csv")
        stocks = list(zip(listing['trading_symbol'], listing['instrument_token'].astype(int)))
        stocks = [(s, t) for s, t in stocks if t in history]
    else:
        names = {}
        try:
            df = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static',
                                          'instruments', 'nse-other-instruments.csv'),
                             usecols=['instrument_token', 'tradingsymbol'])
            names = dict(zip(df['instrument_token'].astype(int), df['tradingsymbol']))
        except Exception:
            pass
        # Indices have no volume, so they are not profiled
        stocks = [(names[t], t) for t in history if t in names]
    if limit:
        stocks = stocks[:limit]
    print(f"📊 Backtesting {len(stocks)} stocks ({universe})")

    bars_by_token = fetch_intraday(kite_service, [t for _, t in stocks],
                                   calendar_days=MAX_CALENDAR_DAYS[INTRADAY_INTERVAL], kind='backtest')
    tick_sizes = load_tick_sizes()

    rows = []
    for symbol, token in stocks:
        bars = bars_by_token.get(token)
        if bars is None or bars.empty:
            continue
        try:
            rows.extend(backtest_stock(symbol, token, history[token], bars,
                                       tick_sizes.get(token, 0.05), fresh_only))
        except Exception as e:
            print(f"❌ Error backtesting {symbol}: {e}")

    results = pd.DataFrame(rows)
    if results.empty:
        print("⚠️ No breakout signals inside the intraday window")
        return results

    output_dir = output_dir or os.path.join(RESULTS_DIR, 'backtest')
    os.makedirs(output_dir, exist_ok=True)
    results.to_csv(os.path.join(output_dir, f'acceptance_{run_date}.csv'), index=False)
    summary = summarise(results)
    summary.to_csv(os.path.join(output_dir, f'acceptance_{run_date}_summary.csv'))
    print(f"\n💾 {len(results)} signals saved to {output_dir}/acceptance_{run_date}.csv\n")
    print(summary.to_string())
    return results


def main():
    parser = argparse.ArgumentParser(description='Backtest Filter4 acceptance verdicts')
    parser.add_argument('--universe', choices=['filter1', 'filter2'], default='filter1')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--all-days', action='store_true',
                        help='judge every day above the pivot, not just the first')
    args = parser.parse_args()
    run_backtest(KiteService(), args.universe, args.limit, fresh_only=not args.all_days)


if __name__ == '__main__':
    main()

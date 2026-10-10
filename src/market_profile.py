#!/usr/bin/env python3
"""
Market Profile (Dalton, Jones & Dalton, "Mind Over Markets") from 30-minute candles.

Pure functions, no Kite or file I/O:
- session_profile(): one session's TPO profile, POC, value area, initial balance, range
  extension, tails, poor highs/lows and day type
- value_relationship() / value_migration() / naked_pocs(): how value moves across sessions
- detect_balance() / breakout_from_balance(): multi-day balance brackets from daily candles

Each 30-minute bar is one TPO period (letter A, B, C...). A bar marks every price bucket between
its low and high, which is how a TPO chart is drawn from bars. Kite has no volume-at-price data,
so the volume profile spreads each bar's volume evenly across its buckets: an approximation.

Thresholds below are a reading of the book, not values it states; tune them with the backtest.
"""

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

VALUE_AREA_PCT = 0.70
# Price bucket is about 0.1% of price (but never below the tick size)
BUCKET_PCT = 0.001
# Bars in the initial balance: the first hour (09:15-10:15)
IB_PERIODS = 2
# Single-TPO buckets needed at an extreme to call it a tail (excess)
MIN_TAIL_BUCKETS = 2

# Day types
NON_TREND_RANGE_PCT = 0.01  # range under 1% of price with no range extension
NORMAL_MAX_EXTENSION = 0.25  # range extension up to 25% of the IB is still a Normal day
TREND_MAX_IB_SHARE = 0.35  # on a Trend day the IB is a small part of the range...
TREND_CLOSE_SHARE = 0.25  # ...and the close is in the outer quarter, in the trend's direction
EXTREME_CLOSE_SHARE = 0.20  # Neutral-extreme closes in the outer 20% of the range
DOUBLE_DISTRIBUTION_SINGLES = 3  # interior single prints separating two distributions...
DOUBLE_DISTRIBUTION_SHARE = 0.15  # ...covering at least 15% of the range

# Balance brackets
BALANCE_ATR_MULT = 3.0
ATR_PERIOD = 20
BALANCE_MAX_GAP = 5  # the bracket may end up to this many sessions before the latest day

HIGHER_VALUE = ('higher', 'overlapping-higher')
LOWER_VALUE = ('lower', 'overlapping-lower')

_EPS = 1e-9


def _letter(index: int) -> str:
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return letters[index] if index < len(letters) else f'P{index + 1}'


def price_step(close: float, tick_size: float = 0.05) -> float:
    """Bucket size for a stock: about 0.1% of price, rounded to whole ticks, at least one tick."""
    tick_size = tick_size if tick_size and tick_size > 0 else 0.05
    ticks = max(1, round(close * BUCKET_PCT / tick_size))
    return round(ticks * tick_size, 4)


def _bucket(price: float, step: float) -> int:
    return int(math.floor(price / step + _EPS))


def build_tpo_profile(bars: pd.DataFrame, step: float) -> pd.DataFrame:
    """
    TPO profile of one session, one row per price bucket (ascending), with columns
    price (bucket floor), tpo_count, letters and approx_volume.
    """
    counts: Dict[int, int] = {}
    letters: Dict[int, str] = {}
    volume: Dict[int, float] = {}
    for period, bar in enumerate(bars.itertuples(index=False)):
        low, high = _bucket(bar.low, step), _bucket(bar.high, step)
        buckets = range(low, high + 1)
        bar_volume = float(getattr(bar, 'volume', 0) or 0) / len(buckets)
        for bucket in buckets:
            counts[bucket] = counts.get(bucket, 0) + 1
            letters[bucket] = letters.get(bucket, '') + _letter(period)
            volume[bucket] = volume.get(bucket, 0.0) + bar_volume
    if not counts:
        return pd.DataFrame(columns=['price', 'tpo_count', 'letters', 'approx_volume'])
    buckets = range(min(counts), max(counts) + 1)
    return pd.DataFrame({
        'price': [round(b * step, 4) for b in buckets],
        'tpo_count': [counts.get(b, 0) for b in buckets],
        'letters': [letters.get(b, '') for b in buckets],
        'approx_volume': [volume.get(b, 0.0) for b in buckets],
    })


def _basis_column(basis: str) -> str:
    return 'approx_volume' if basis == 'volume' else 'tpo_count'


def poc_index(profile: pd.DataFrame, basis: str = 'tpo') -> int:
    """Row of the Point of Control. Ties go to the bucket nearest the middle of the range."""
    values = profile[_basis_column(basis)].to_numpy(dtype=float)
    candidates = np.flatnonzero(np.isclose(values, values.max()))
    middle = (len(values) - 1) / 2
    return int(min(candidates, key=lambda i: (abs(i - middle), i)))


def poc(profile: pd.DataFrame, basis: str = 'tpo') -> float:
    return float(profile['price'].iloc[poc_index(profile, basis)])


def value_area(profile: pd.DataFrame, pct: float = VALUE_AREA_PCT, basis: str = 'tpo'):
    """
    (VAL, VAH) by the book's method: start at the POC and keep adding whichever side's next two
    buckets hold more, until the area holds pct of the total. A tie adds both sides.
    """
    values = profile[_basis_column(basis)].to_numpy(dtype=float)
    low = high = poc_index(profile, basis)
    total, inside = values.sum(), values[low]
    while inside < pct * total - _EPS and (low > 0 or high < len(values) - 1):
        up = values[high + 1:high + 3].sum()
        down = values[max(low - 2, 0):low].sum()
        if high < len(values) - 1 and (up >= down or low == 0):
            high = min(high + 2, len(values) - 1)
            inside += up
            if up == down and low > 0:
                low = max(low - 2, 0)
                inside += down
        else:
            low = max(low - 2, 0)
            inside += down
    prices = profile['price']
    return float(prices.iloc[low]), float(prices.iloc[high])


def initial_balance(bars: pd.DataFrame, periods: int = IB_PERIODS):
    """(IB high, IB low): the range of the first hour."""
    first = bars.iloc[:periods]
    return float(first['high'].max()), float(first['low'].min())


def range_extension(bars: pd.DataFrame, ib_high: float, ib_low: float, periods: int = IB_PERIODS):
    """How far the session traded beyond its IB, and which periods did it."""
    later = bars.iloc[periods:]
    up_periods = [_letter(periods + i) for i, high in enumerate(later['high']) if high > ib_high]
    down_periods = [_letter(periods + i) for i, low in enumerate(later['low']) if low < ib_low]
    return {
        're_up': round(max(0.0, float(bars['high'].max()) - ib_high), 4),
        're_down': round(max(0.0, ib_low - float(bars['low'].min())), 4),
        're_up_periods': ''.join(up_periods),
        're_down_periods': ''.join(down_periods),
    }


def _single_runs(counts: Sequence[int]) -> List[tuple]:
    """(start, end) rows of each run of single-TPO buckets."""
    runs, start = [], None
    for i, count in enumerate(list(counts) + [0]):
        if count == 1 and start is None:
            start = i
        elif count != 1 and start is not None:
            runs.append((start, i - 1))
            start = None
    return runs


def tails(profile: pd.DataFrame, min_buckets: int = MIN_TAIL_BUCKETS) -> Dict[str, Any]:
    """
    Buying tail (single prints at the low) and selling tail (at the high), in buckets.
    A poor high/low is an extreme that two or more periods traded flat into, with no tail.
    """
    counts = profile['tpo_count'].tolist()
    runs = _single_runs(counts)
    buying = next((end - start + 1 for start, end in runs if start == 0), 0)
    selling = next((end - start + 1 for start, end in runs if end == len(counts) - 1), 0)
    # A one-bucket range is all "single prints" but is not a tail
    if len(counts) == 1:
        buying = selling = 0
    return {
        'buying_tail': buying if buying >= min_buckets else 0,
        'selling_tail': selling if selling >= min_buckets else 0,
        'poor_high': bool(counts) and counts[-1] >= 2,
        'poor_low': bool(counts) and counts[0] >= 2,
    }


def single_prints(profile: pd.DataFrame) -> List[tuple]:
    """(low, high) price ranges of single prints inside the range (not at either extreme)."""
    counts = profile['tpo_count'].tolist()
    prices = profile['price'].tolist()
    return [(prices[start], prices[end]) for start, end in _single_runs(counts)
            if start > 0 and end < len(counts) - 1]


def _longest_interior_single_run(profile: pd.DataFrame) -> int:
    counts = profile['tpo_count'].tolist()
    runs = [end - start + 1 for start, end in _single_runs(counts) if start > 0 and end < len(counts) - 1]
    return max(runs, default=0)


def classify_day_type(p: Dict[str, Any]) -> str:
    """
    Mind Over Markets day type from a session_profile() dict: non-trend, normal,
    normal-variation, trend, double-distribution-trend, neutral-center or neutral-extreme.
    """
    day_range = p['high'] - p['low']
    if day_range <= 0:
        return 'non-trend'
    ib = p['ib_high'] - p['ib_low']
    re_up, re_down = p['re_up'], p['re_down']
    close_share = (p['close'] - p['low']) / day_range  # 0 at the low, 1 at the high

    if re_up > 0 and re_down > 0:
        at_extreme = close_share >= 1 - EXTREME_CLOSE_SHARE or close_share <= EXTREME_CLOSE_SHARE
        return 'neutral-extreme' if at_extreme else 'neutral-center'

    extension = max(re_up, re_down)
    if extension == 0:
        return 'non-trend' if day_range / p['close'] < NON_TREND_RANGE_PCT else 'normal'

    closes_with_trend = (close_share >= 1 - TREND_CLOSE_SHARE) if re_up > 0 else (close_share <= TREND_CLOSE_SHARE)
    singles = p.get('interior_single_run', 0)
    separated = singles >= DOUBLE_DISTRIBUTION_SINGLES and singles >= DOUBLE_DISTRIBUTION_SHARE * p.get('buckets', 0)
    if separated and extension >= ib:
        return 'double-distribution-trend'
    if ib / day_range <= TREND_MAX_IB_SHARE and closes_with_trend:
        return 'trend'
    if extension <= NORMAL_MAX_EXTENSION * ib:
        return 'normal'
    return 'normal-variation'


def session_profile(bars: pd.DataFrame, tick_size: float = 0.05, pct: float = VALUE_AREA_PCT,
                    basis: str = 'tpo') -> Dict[str, Any]:
    """Everything Filter4 needs about one session, from its 30-minute bars (in time order)."""
    bars = bars.reset_index(drop=True)
    close = float(bars['close'].iloc[-1])
    step = price_step(close, tick_size)
    profile = build_tpo_profile(bars, step)
    val, vah = value_area(profile, pct, basis)
    ib_high, ib_low = initial_balance(bars)
    p = {
        'session': str(bars['session'].iloc[0]) if 'session' in bars.columns else None,
        'open': float(bars['open'].iloc[0]),
        'high': float(bars['high'].max()),
        'low': float(bars['low'].min()),
        'close': close,
        'step': step,
        'poc': poc(profile, basis),
        'val': val,
        'vah': vah,
        'ib_high': ib_high,
        'ib_low': ib_low,
        'periods': len(bars),
        'last_bar': bars['date'].iloc[-1] if 'date' in bars.columns else None,
        'single_prints': single_prints(profile),
        'interior_single_run': _longest_interior_single_run(profile),
        'buckets': len(profile),
        'profile': profile,
    }
    p.update(range_extension(bars, ib_high, ib_low))
    p.update(tails(profile))
    p['day_type'] = classify_day_type(p)
    p['direction'] = 'up' if p['re_up'] > p['re_down'] else 'down' if p['re_down'] > p['re_up'] else None
    return p


def session_profiles(bars: pd.DataFrame, tick_size: float = 0.05, basis: str = 'tpo') -> List[Dict[str, Any]]:
    """One profile per session in bars (which need a 'session' column), oldest first."""
    if bars.empty:
        return []
    return [session_profile(day, tick_size, basis=basis) for _, day in bars.groupby('session', sort=True)]


def value_relationship(prev: Dict[str, Any], cur: Dict[str, Any]) -> str:
    """Today's value area against yesterday's: higher, overlapping-higher, overlapping, overlapping-lower or lower."""
    if cur['val'] > prev['vah']:
        return 'higher'
    if cur['vah'] < prev['val']:
        return 'lower'
    if cur['vah'] > prev['vah'] and cur['val'] > prev['val']:
        return 'overlapping-higher'
    if cur['vah'] < prev['vah'] and cur['val'] < prev['val']:
        return 'overlapping-lower'
    return 'overlapping'


def value_migration(profiles: List[Dict[str, Any]], window: int = 5) -> Dict[str, Any]:
    """
    How value moved over the last `window` sessions: each day's relationship to the day before,
    consecutive higher-value days ending today, and the POC's slope (% of price per session).
    """
    recent = profiles[-(window + 1):]
    relationships = [value_relationship(a, b) for a, b in zip(recent, recent[1:])]
    higher_days = 0
    for relationship in reversed(relationships):
        if relationship not in HIGHER_VALUE:
            break
        higher_days += 1
    pocs = [p['poc'] for p in recent[1:]] or [p['poc'] for p in recent]
    slope = float(np.polyfit(range(len(pocs)), pocs, 1)[0]) if len(pocs) > 1 else 0.0
    last_close = profiles[-1]['close'] if profiles else 0
    return {
        'relationships': relationships,
        'today': relationships[-1] if relationships else None,
        'higher_days': higher_days,
        'poc_slope_pct': round(slope / last_close * 100, 3) if last_close else 0.0,
    }


def naked_pocs(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Earlier sessions' POCs that no later session has traded through (today's own POC excluded)."""
    naked = []
    for i, p in enumerate(profiles[:-1]):
        later = profiles[i + 1:]
        if not any(q['low'] <= p['poc'] <= q['high'] for q in later):
            naked.append({'session': p['session'], 'poc': p['poc']})
    return naked


def average_true_range(daily: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    prev_close = daily['close'].shift(1)
    true_range = pd.concat([daily['high'] - daily['low'],
                            (daily['high'] - prev_close).abs(),
                            (daily['low'] - prev_close).abs()], axis=1).max(axis=1)
    return float(true_range.tail(period).mean())


def detect_balance(daily: pd.DataFrame, min_days: int = 5, max_days: int = 30,
                   atr_mult: float = BALANCE_ATR_MULT, max_gap: int = BALANCE_MAX_GAP) -> Optional[Dict[str, Any]]:
    """
    The most recent balance bracket before the latest daily candle: a run of at least min_days
    sessions that each overlap the bracket, with the bracket no taller than atr_mult x ATR(20).
    The bracket may end up to max_gap sessions before the latest day (time spent outside it).
    """
    daily = daily.reset_index(drop=True)
    last = len(daily) - 1
    for end in range(last - 1, max(last - 1 - max_gap, -1), -1):
        atr = average_true_range(daily.iloc[:end + 1])
        if not atr or math.isnan(atr):
            continue
        high, low = float(daily['high'].iloc[end]), float(daily['low'].iloc[end])
        start = end
        while start - 1 >= 0 and end - start + 1 < max_days:
            day = daily.iloc[start - 1]
            new_high, new_low = max(high, day['high']), min(low, day['low'])
            if day['low'] > high or day['high'] < low or new_high - new_low > atr_mult * atr:
                break
            high, low, start = new_high, new_low, start - 1
        if end - start + 1 >= min_days:
            return {
                'bracket_high': round(float(high), 4),
                'bracket_low': round(float(low), 4),
                'start': str(daily['date'].iloc[start])[:10] if 'date' in daily.columns else start,
                'end': str(daily['date'].iloc[end])[:10] if 'date' in daily.columns else end,
                'days': end - start + 1,
                'end_index': end,
            }
    return None


def breakout_from_balance(daily: pd.DataFrame, bracket: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Where the latest close is against the bracket, and how many closes in a row it has held above it."""
    if not bracket:
        return {'position': None, 'closes_above': 0}
    closes = daily['close'].reset_index(drop=True)
    after = closes.iloc[bracket['end_index'] + 1:]
    closes_above = 0
    for close in reversed(after.tolist()):
        if close <= bracket['bracket_high']:
            break
        closes_above += 1
    latest = float(closes.iloc[-1])
    position = ('above' if latest > bracket['bracket_high']
                else 'below' if latest < bracket['bracket_low'] else 'inside')
    return {'position': position, 'closes_above': closes_above}

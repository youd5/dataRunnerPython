#!/usr/bin/env python3
"""
Intraday cache: recent 30-minute candles for the few stocks Filter4 profiles.

Market Profile needs the shape of each session, which one daily candle cannot give. Kite's
30-minute candles map one-to-one onto Market Profile's 30-minute TPO periods (NSE 09:15-15:30 is
13 periods, the last one 15 minutes long).

Like HistoryCache, the candles are kept in memory and on disk at
results/history/<run date>_<interval>[_<kind>].pkl, so a rerun on the same day only fetches stocks that
are not cached yet.
"""

import os
import pickle
from datetime import datetime, time, timedelta
from typing import Dict, Iterable, Optional

import pandas as pd

from kite_service import RESULTS_DIR

INTRADAY_INTERVAL = '30minute'
# ~20 trading sessions: enough for value migration, balance and naked POCs
INTRADAY_CALENDAR_DAYS = 35
# Kite's largest window per historical request, by interval
MAX_CALENDAR_DAYS = {
    'minute': 60, '3minute': 100, '5minute': 100, '10minute': 100,
    '15minute': 200, '30minute': 200, '60minute': 400,
}

SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)
MARKET_TZ = 'Asia/Kolkata'

HISTORY_DIR = os.path.join(RESULTS_DIR, 'history')


class IntradayCache:
    """Intraday candles (one DataFrame per instrument token) for one run date and interval."""

    _memory: Dict[tuple, Dict[int, pd.DataFrame]] = {}

    def __init__(self, run_date: str, interval: str = INTRADAY_INTERVAL, history_dir: Optional[str] = None,
                 kind: str = ''):
        self.run_date = run_date
        self.interval = interval
        # kind keeps separate caches (e.g. the backtest's longer window) from replacing each other
        self.suffix = f"_{interval}{'_' + kind if kind else ''}.pkl"
        self.path = os.path.join(history_dir or HISTORY_DIR, f'{run_date}{self.suffix}')
        self._key = self.path

    def _candles(self) -> Dict[int, pd.DataFrame]:
        if self._key not in IntradayCache._memory:
            IntradayCache._memory[self._key] = self._load()
        return IntradayCache._memory[self._key]

    def _load(self) -> Dict[int, pd.DataFrame]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, 'rb') as f:
                saved = pickle.load(f)
            print(f"📦 Loaded cached {self.interval} candles for {len(saved['candles'])} instruments from {self.path}")
            return saved['candles']
        except Exception as e:
            print(f"⚠️ Ignoring unreadable intraday cache {self.path}: {e}")
            return {}

    def get(self, instrument_token: int) -> Optional[pd.DataFrame]:
        """Cached candles for a token, or None if they were never fetched."""
        return self._candles().get(int(instrument_token))

    def put_many(self, candles_by_token: Dict[int, pd.DataFrame]):
        """Add candles to the cache and write it to disk."""
        candles = self._candles()
        candles.update({int(token): data for token, data in candles_by_token.items()})
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'wb') as f:
            pickle.dump({'run_date': self.run_date, 'interval': self.interval, 'candles': candles}, f)
        # Older days are never read again; keep only the latest file of this interval and kind
        history_dir = os.path.dirname(self.path)
        for name in os.listdir(history_dir):
            path = os.path.join(history_dir, name)
            if name.endswith(self.suffix) and path != self.path:
                os.remove(path)


def normalise_bars(candles) -> pd.DataFrame:
    """Kite candles as a DataFrame in market time, regular session only, with a 'session' column."""
    df = pd.DataFrame(candles)
    if df.empty:
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'session'])
    dates = pd.to_datetime(df['date'])
    if dates.dt.tz is None:
        dates = dates.dt.tz_localize(MARKET_TZ)
    else:
        dates = dates.dt.tz_convert(MARKET_TZ)
    df['date'] = dates
    bar_time = dates.dt.time
    df = df[(bar_time >= SESSION_OPEN) & (bar_time < SESSION_CLOSE)].copy()
    df['session'] = df['date'].dt.strftime('%Y-%m-%d')
    return df.sort_values('date').reset_index(drop=True)


def fetch_intraday(kite_service, tokens: Iterable[int], run_date: Optional[datetime] = None,
                   interval: str = INTRADAY_INTERVAL, calendar_days: int = INTRADAY_CALENDAR_DAYS,
                   kind: str = '', history_dir: Optional[str] = None) -> Dict[int, pd.DataFrame]:
    """
    Intraday candles for each token, fetched from Kite only when not already cached.

    One historical request per uncached token. Requests go through KiteService.historical_data,
    so they share Filter1's rate limit and retries. Tokens Kite returns nothing for are left out.
    """
    run_date = run_date or datetime.now()
    calendar_days = min(calendar_days, MAX_CALENDAR_DAYS.get(interval, calendar_days))
    cache = IntradayCache(run_date.strftime('%Y-%m-%d'), interval, history_dir, kind)
    # Intraday requests need times: a bare date means midnight and would drop the run date itself
    from_date = (run_date - timedelta(days=calendar_days)).strftime('%Y-%m-%d 09:15:00')
    to_date = run_date.strftime('%Y-%m-%d 15:30:00')

    result, fetched = {}, {}
    for token in tokens:
        token = int(token)
        cached = cache.get(token)
        if cached is not None:
            result[token] = cached
            continue
        response = kite_service.historical_data(
            instrument_token=token, from_date=from_date, to_date=to_date, interval=interval)
        if not response.get('success'):
            print(f"❌ Failed to fetch {interval} candles for {token}: {response.get('error', 'Unknown error')}")
            continue
        bars = normalise_bars(response.get('data') or [])
        if bars.empty:
            print(f"⚠️ No {interval} candles for {token}")
            continue
        fetched[token] = bars
        result[token] = bars

    if fetched:
        cache.put_many(fetched)
        print(f"💾 Cached {interval} candles for {len(fetched)} instruments at {cache.path}")
    return result

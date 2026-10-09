#!/usr/bin/env python3
"""
History cache: one year of daily candles, fetched once by Filter1 and reused by Filter2 and Filter3.

Filter1 already calls Kite once per instrument. Asking for a year in that call costs the same
request (Kite allows up to 2000 days of daily candles per call), so Filter2 and Filter3 can read
the candles from here instead of downloading them again.

The cache is keyed by run date and kept both in memory (web route: all filters run in one process)
and on disk at results/history/<run date>_daily.pkl (CLI: each filter is its own process).
"""

import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd

from kite_service import RESULTS_DIR

# Calendar days of history Filter2 and Filter3 need (52-week high/low, 200-day MA, pivots)
HISTORY_DAYS = 365

HISTORY_DIR = os.path.join(RESULTS_DIR, 'history')


def history_date_range(run_date: Optional[datetime] = None):
    """The (from_date, to_date) strings Filter2 and Filter3 have always requested."""
    run_date = run_date or datetime.now()
    return ((run_date - timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d'),
            run_date.strftime('%Y-%m-%d'))


class HistoryCache:
    """Daily candles (one DataFrame per instrument token) for one date range."""

    _memory: Dict[tuple, Dict[int, pd.DataFrame]] = {}

    def __init__(self, from_date: str, to_date: str, history_dir: Optional[str] = None):
        self.from_date = from_date
        self.to_date = to_date
        self.path = os.path.join(history_dir or HISTORY_DIR, f'{to_date}_daily.pkl')
        self._key = (from_date, to_date)

    def _candles(self) -> Dict[int, pd.DataFrame]:
        if self._key not in HistoryCache._memory:
            HistoryCache._memory[self._key] = self._load()
        return HistoryCache._memory[self._key]

    def _load(self) -> Dict[int, pd.DataFrame]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, 'rb') as f:
                saved = pickle.load(f)
            if (saved.get('from_date'), saved.get('to_date')) != self._key:
                return {}
            print(f"📦 Loaded cached history for {len(saved['candles'])} instruments from {self.path}")
            return saved['candles']
        except Exception as e:
            print(f"⚠️ Ignoring unreadable history cache {self.path}: {e}")
            return {}

    def get(self, instrument_token: int) -> Optional[pd.DataFrame]:
        """Cached candles for a token, or None if Filter1 did not store it."""
        return self._candles().get(int(instrument_token))

    def put_all(self, candles_by_token: Dict[int, pd.DataFrame]):
        """Replace the cache contents and write them to disk."""
        candles = {int(token): data for token, data in candles_by_token.items()}
        HistoryCache._memory[self._key] = candles
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'wb') as f:
            pickle.dump({'from_date': self.from_date, 'to_date': self.to_date, 'candles': candles}, f)
        # Older days are never read again; keep only the latest file
        history_dir = os.path.dirname(self.path)
        for name in os.listdir(history_dir):
            path = os.path.join(history_dir, name)
            if name.endswith('_daily.pkl') and path != self.path:
                os.remove(path)
        print(f"💾 Cached history for {len(candles)} instruments at {self.path}")

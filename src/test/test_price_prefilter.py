#!/usr/bin/env python3
"""
Tests for Filter1's last-price prefilter, against a mocked Kite quote API.
"""

import os
import sys
import unittest
from unittest import mock

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('KITE_API_KEY', 'test-key')
os.environ.setdefault('KITE_API_SECRET', 'test-secret')

import filter1
from filter1 import Filter1


def instrument(symbol):
    return {'instrument_token': hash(symbol) % 100000, 'tradingsymbol': symbol, 'exchange': 'NSE'}


class PricePrefilterTest(unittest.TestCase):
    def setUp(self):
        self.filter1 = Filter1.__new__(Filter1)
        self.filter1.kite_service = mock.Mock()
        patch = mock.patch.object(filter1.time, 'sleep')
        self.sleep = patch.start()
        self.addCleanup(patch.stop)

    def test_drops_only_quoted_prices_below_minimum(self):
        self.filter1.kite_service.get_ohlc.return_value = {'success': True, 'ohlc': {
            'NSE:CHEAP': {'last_price': 12.5},
            'NSE:EDGE': {'last_price': 30},
            'NSE:DEAR': {'last_price': 950},
            'NSE:ZERO': {'last_price': 0},
        }}
        kept = self.filter1.prefilter_by_last_price(
            [instrument(s) for s in ['CHEAP', 'EDGE', 'DEAR', 'ZERO', 'NOQUOTE']])
        self.assertEqual([i['tradingsymbol'] for i in kept], ['EDGE', 'DEAR', 'ZERO', 'NOQUOTE'])

    def test_batches_of_1000_and_keeps_a_failed_batch(self):
        instruments = [instrument(f'S{i}') for i in range(2500)]
        self.filter1.kite_service.get_ohlc.side_effect = [
            {'success': True, 'ohlc': {f'NSE:S{i}': {'last_price': 5} for i in range(1000)}},
            {'success': False, 'error': 'Too many requests'},
            {'success': True, 'ohlc': {}},
        ]
        kept = self.filter1.prefilter_by_last_price(instruments)
        batch_sizes = [len(call.args[0]) for call in self.filter1.kite_service.get_ohlc.call_args_list]
        self.assertEqual(batch_sizes, [1000, 1000, 500])
        self.assertEqual(len(kept), 1500)
        self.assertEqual(self.sleep.call_count, 2)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Simple test runner for historical data API.
Run this script from the project root directory.
"""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the test
from test.test_historical_data import main

if __name__ == "__main__":
    main()

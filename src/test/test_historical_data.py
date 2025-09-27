#!/usr/bin/env python3
"""
Test script for the historical data API endpoint.
"""

import sys
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kite_service import KiteService

class HistoricalDataTester:
    """Test class for historical data functionality."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        """Initialize the tester with base URL."""
        self.base_url = base_url
        self.kite_service = None
        
    def setup_kite_service(self):
        """Initialize KiteService for direct testing."""
        try:
            self.kite_service = KiteService()
            print("✅ KiteService initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize KiteService: {e}")
            return False
    
    def test_historical_data_method(self):
        """Test the historical_data method directly."""
        print("\n🔍 Testing historical_data method directly...")
        
        if not self.kite_service:
            print("❌ KiteService not initialized")
            return False
        
        # Test with NIFTY 50 token (738561)
        instrument_token = 738561
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        try:
            result = self.kite_service.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="day"
            )
            
            if result['success']:
                print(f"✅ Historical data fetched successfully")
                print(f"   📊 Data points: {result['count']}")
                print(f"   📅 Date range: {from_date} to {to_date}")
                print(f"   ⏰ Interval: {result['interval']}")
                
                if result['data']:
                    # Show sample data
                    sample = result['data'][0]
                    print(f"   📈 Sample data point:")
                    print(f"      Date: {sample.get('date', 'N/A')}")
                    print(f"      Open: {sample.get('open', 'N/A')}")
                    print(f"      High: {sample.get('high', 'N/A')}")
                    print(f"      Low: {sample.get('low', 'N/A')}")
                    print(f"      Close: {sample.get('close', 'N/A')}")
                    print(f"      Volume: {sample.get('volume', 'N/A')}")
                
                return True
            else:
                print(f"❌ Failed to fetch historical data: {result['error']}")
                return False
                
        except Exception as e:
            print(f"❌ Exception during historical data test: {e}")
            return False
    
    def test_historical_data_api_endpoint(self):
        """Test the historical data API endpoint."""
        print("\n🔍 Testing historical data API endpoint...")
        
        # Test with NIFTY 50 token (738561)
        instrument_token = 738561
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        url = f"{self.base_url}/api/kite/historical-data"
        
        payload = {
            "instrument_token": instrument_token,
            "from_date": from_date,
            "to_date": to_date,
            "interval": "day",
            "continuous": False,
            "oi": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            print(f"📡 API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print("✅ API endpoint working correctly")
                    print(f"   📊 Data points: {data.get('count', 0)}")
                    print(f"   📅 Date range: {from_date} to {to_date}")
                    print(f"   ⏰ Interval: {data.get('interval', 'N/A')}")
                    
                    if data.get('data'):
                        # Show sample data
                        sample = data['data'][0]
                        print(f"   📈 Sample data point:")
                        print(f"      Date: {sample.get('date', 'N/A')}")
                        print(f"      Open: {sample.get('open', 'N/A')}")
                        print(f"      High: {sample.get('high', 'N/A')}")
                        print(f"      Low: {sample.get('low', 'N/A')}")
                        print(f"      Close: {sample.get('close', 'N/A')}")
                        print(f"      Volume: {sample.get('volume', 'N/A')}")
                    
                    return True
                else:
                    print(f"❌ API returned error: {data.get('error', 'Unknown error')}")
                    return False
            else:
                print(f"❌ API request failed with status: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection failed. Make sure the Flask server is running on localhost:8080")
            return False
        except Exception as e:
            print(f"❌ Exception during API test: {e}")
            return False
    
    def test_parameter_validation(self):
        """Test parameter validation."""
        print("\n🔍 Testing parameter validation...")
        
        if not self.kite_service:
            print("❌ KiteService not initialized")
            return False
        
        # Test missing instrument_token
        result = self.kite_service.historical_data(
            instrument_token=None,
            from_date="2024-01-01",
            to_date="2024-01-31",
            interval="day"
        )
        
        if not result['success'] and 'instrument_token is required' in result['error']:
            print("✅ Missing instrument_token validation works")
        else:
            print("❌ Missing instrument_token validation failed")
            return False
        
        # Test missing dates
        result = self.kite_service.historical_data(
            instrument_token=738561,
            from_date=None,
            to_date="2024-01-31",
            interval="day"
        )
        
        if not result['success'] and 'from_date and to_date are required' in result['error']:
            print("✅ Missing dates validation works")
        else:
            print("❌ Missing dates validation failed")
            return False
        
        # Test invalid interval
        result = self.kite_service.historical_data(
            instrument_token=738561,
            from_date="2024-01-01",
            to_date="2024-01-31",
            interval="invalid_interval"
        )
        
        if not result['success'] and 'Invalid interval' in result['error']:
            print("✅ Invalid interval validation works")
        else:
            print("❌ Invalid interval validation failed")
            return False
        
        return True
    
    def test_different_intervals(self):
        """Test different interval types."""
        print("\n🔍 Testing different interval types...")
        
        if not self.kite_service:
            print("❌ KiteService not initialized")
            return False
        
        instrument_token = 738561
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        intervals = ["day", "60minute", "15minute", "5minute"]
        success_count = 0
        
        for interval in intervals:
            try:
                result = self.kite_service.historical_data(
                    instrument_token=instrument_token,
                    from_date=from_date,
                    to_date=to_date,
                    interval=interval
                )
                
                if result['success']:
                    print(f"✅ {interval} interval works - {result['count']} data points")
                    success_count += 1
                else:
                    print(f"❌ {interval} interval failed: {result['error']}")
                    
            except Exception as e:
                print(f"❌ {interval} interval exception: {e}")
        
        # Return True if at least half the intervals worked
        return success_count >= len(intervals) // 2
    
    def test_with_symbol_conversion(self):
        """Test historical data with symbol to token conversion."""
        print("\n🔍 Testing symbol to token conversion...")
        
        if not self.kite_service:
            print("❌ KiteService not initialized")
            return False
        
        # Get instrument token for NIFTY 50
        token = self.kite_service.get_instrument_token("NIFTY 50")
        
        if token:
            print(f"✅ NIFTY 50 token found: {token}")
            
            to_date = datetime.now().strftime("%Y-%m-%d")
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            result = self.kite_service.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval="day"
            )
            
            if result['success']:
                print(f"✅ Historical data with converted token works - {result['count']} data points")
                return True
            else:
                print(f"❌ Historical data with converted token failed: {result['error']}")
                return False
        else:
            print("❌ Could not find NIFTY 50 token")
            return False
    
    def run_all_tests(self):
        """Run all tests."""
        print("🚀 Starting Historical Data API Tests")
        print("=" * 50)
        
        # Initialize KiteService
        if not self.setup_kite_service():
            print("❌ Cannot proceed without KiteService initialization")
            return
        
        # Run tests
        tests = [
            ("Parameter Validation", self.test_parameter_validation),
            ("Symbol to Token Conversion", self.test_with_symbol_conversion),
            ("Different Intervals", self.test_different_intervals),
            ("Historical Data Method", self.test_historical_data_method),
            ("API Endpoint", self.test_historical_data_api_endpoint),
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                if callable(test_func):
                    result = test_func()
                    results.append((test_name, result))
                else:
                    print("❌ Invalid test function")
                    results.append((test_name, False))
            except Exception as e:
                print(f"❌ Test failed with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "="*50)
        print("📊 TEST SUMMARY")
        print("="*50)
        
        passed = 0
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n🎯 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print("⚠️  Some tests failed. Check the output above for details.")

def main():
    """Main function to run the tests."""
    print("Historical Data API Tester")
    print("This script tests both the KiteService method and the API endpoint")
    print("Make sure your Flask server is running on localhost:8080")
    print()
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8080", timeout=15)
        print("✅ Flask server is running")
    except:
        print("⚠️  Flask server not detected on localhost:8080")
        print("   Some tests may fail. Start the server with: python src/main.py")
        print()
    
    tester = HistoricalDataTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()

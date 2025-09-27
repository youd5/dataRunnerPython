#!/usr/bin/env python3
"""
Filter1: Fetches instruments and historical data for analysis.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from kite_service import KiteService

class Filter1:
    """Filter1 class for fetching instruments and historical data."""
    
    def __init__(self):
        """Initialize Filter1 with KiteService."""
        try:
            self.kite_service = KiteService()
            print("✅ Filter1 initialized with KiteService")
        except Exception as e:
            print(f"❌ Failed to initialize Filter1: {e}")
            self.kite_service = None
    
    def fetch_instruments_and_historical_data(self, max_instruments: int = 5) -> Dict[str, Any]:
        """
        Fetch all instruments from NSE and get historical data for up to max_instruments.
        
        Args:
            max_instruments (int): Maximum number of instruments to process (default: 5)
            
        Returns:
            Dict[str, Any]: Results with instruments and historical data
        """
        if not self.kite_service:
            return {
                'success': False,
                'error': 'KiteService not initialized'
            }
        
        print(f"\n🔍 Fetching instruments from NSE exchange...")
        
        try:
            # Step 1: Fetch all instruments from NSE exchange
            instruments_result = self.kite_service.get_instruments(exchange='NSE')
            
            if not instruments_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to fetch instruments: {instruments_result['error']}"
                }
            
            instruments = instruments_result['instruments']
            print(f"✅ Fetched {len(instruments)} instruments from NSE")
            
            # Step 2: Process up to max_instruments
            processed_instruments = []
            historical_data_results = []
            
            # Calculate date range (today - 8 days to today)
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
            
            print(f"📅 Date range: {start_date} to {end_date}")
            print(f"🔄 Processing up to {max_instruments} instruments...")
            
            # Iterate over instruments (limit to max_instruments)
            for i, instrument in enumerate(instruments[:max_instruments]):
                try:
                    instrument_token = instrument.get('instrument_token')
                    trading_symbol = instrument.get('tradingsymbol', 'Unknown')
                    name = instrument.get('name', 'Unknown')
                    
                    print(f"\n📊 Processing instrument {i+1}/{max_instruments}:")
                    print(f"   Symbol: {trading_symbol}")
                    print(f"   Name: {name}")
                    print(f"   Token: {instrument_token}")
                    
                    # Store instrument info
                    instrument_info = {
                        'instrument_token': instrument_token,
                        'tradingsymbol': trading_symbol,
                        'name': name,
                        'exchange': instrument.get('exchange', 'NSE'),
                        'instrument_type': instrument.get('instrument_type', 'Unknown'),
                        'segment': instrument.get('segment', 'Unknown'),
                        'lot_size': instrument.get('lot_size', 0),
                        'tick_size': instrument.get('tick_size', 0.0)
                    }
                    processed_instruments.append(instrument_info)
                    
                    # Step 3: Fetch historical data
                    if instrument_token:
                        print(f"   📈 Fetching historical data...")
                        
                        historical_result = self.kite_service.historical_data(
                            instrument_token=instrument_token,
                            from_date=start_date,
                            to_date=end_date,
                            interval="day"
                        )
                        
                        if historical_result['success']:
                            print(f"   ✅ Historical data fetched: {historical_result['count']} data points")
                            
                            # Store historical data result
                            historical_data_results.append({
                                'instrument_token': instrument_token,
                                'trading_symbol': trading_symbol,
                                'historical_data': historical_result['data'],
                                'count': historical_result['count'],
                                'date_range': {
                                    'from_date': start_date,
                                    'to_date': end_date
                                },
                                'interval': historical_result['interval']
                            })
                            
                            # Show sample data
                            if historical_result['data']:
                                sample = historical_result['data'][0]
                                print(f"   📊 Sample data:")
                                print(f"      Date: {sample.get('date', 'N/A')}")
                                print(f"      Open: {sample.get('open', 'N/A')}")
                                print(f"      High: {sample.get('high', 'N/A')}")
                                print(f"      Low: {sample.get('low', 'N/A')}")
                                print(f"      Close: {sample.get('close', 'N/A')}")
                                print(f"      Volume: {sample.get('volume', 'N/A')}")
                        else:
                            print(f"   ❌ Failed to fetch historical data: {historical_result['error']}")
                            historical_data_results.append({
                                'instrument_token': instrument_token,
                                'trading_symbol': trading_symbol,
                                'error': historical_result['error'],
                                'historical_data': None
                            })
                    else:
                        print(f"   ⚠️ No instrument token found")
                        
                except Exception as e:
                    print(f"   ❌ Error processing instrument: {e}")
                    continue
            
            print("historical_data_results", historical_data_results)
            # Return comprehensive results
            return {
                'success': True,
                'total_instruments_available': len(instruments),
                'processed_instruments': len(processed_instruments),
                'instruments': processed_instruments,
                'historical_data': historical_data_results,
                'date_range': {
                    'from_date': start_date,
                    'to_date': end_date
                },
                'interval': 'day',
                'exchange': 'NSE'
            }
            
        except Exception as e:
            print(f"❌ Error in fetch_instruments_and_historical_data: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def analyze_historical_data(self, historical_data_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the fetched historical data.
        
        Args:
            historical_data_results (List[Dict[str, Any]]): List of historical data results
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        if not historical_data_results:
            return {
                'success': False,
                'error': 'No historical data to analyze'
            }
        
        print(f"\n📊 Analyzing historical data for {len(historical_data_results)} instruments...")
        
        analysis_results = []
        
        for result in historical_data_results:
            if result.get('historical_data') is None:
                continue
                
            trading_symbol = result['trading_symbol']
            data = result['historical_data']
            
            if not data:
                continue
            
            # Calculate basic statistics
            prices = [d.get('close', 0) for d in data if d.get('close')]
            volumes = [d.get('volume', 0) for d in data if d.get('volume')]
            
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                avg_price = sum(prices) / len(prices)
                
                # Calculate price change
                first_price = prices[0]
                last_price = prices[-1]
                price_change = last_price - first_price
                price_change_percent = (price_change / first_price * 100) if first_price > 0 else 0
                
                # Calculate volatility (standard deviation)
                variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
                volatility = variance ** 0.5
                
                avg_volume = sum(volumes) / len(volumes) if volumes else 0
                
                analysis = {
                    'trading_symbol': trading_symbol,
                    'instrument_token': result['instrument_token'],
                    'data_points': len(data),
                    'price_analysis': {
                        'first_price': first_price,
                        'last_price': last_price,
                        'min_price': min_price,
                        'max_price': max_price,
                        'avg_price': avg_price,
                        'price_change': price_change,
                        'price_change_percent': price_change_percent,
                        'volatility': volatility
                    },
                    'volume_analysis': {
                        'avg_volume': avg_volume,
                        'max_volume': max(volumes) if volumes else 0,
                        'min_volume': min(volumes) if volumes else 0
                    }
                }
                
                analysis_results.append(analysis)
                
                print(f"✅ {trading_symbol}:")
                print(f"   Price Change: {price_change:.2f} ({price_change_percent:.2f}%)")
                print(f"   Price Range: {min_price:.2f} - {max_price:.2f}")
                print(f"   Volatility: {volatility:.2f}")
                print(f"   Avg Volume: {avg_volume:,.0f}")
        
        return {
            'success': True,
            'analysis_results': analysis_results,
            'total_analyzed': len(analysis_results)
        }
    
    def run_filter1(self, max_instruments: int = 5) -> Dict[str, Any]:
        """
        Run the complete Filter1 process.
        
        Args:
            max_instruments (int): Maximum number of instruments to process
            
        Returns:
            Dict[str, Any]: Complete results including instruments, historical data, and analysis
        """
        print("🚀 Starting Filter1 Process")
        print("=" * 50)
        
        # Fetch instruments and historical data
        fetch_result = self.fetch_instruments_and_historical_data(max_instruments)
        
        if not fetch_result['success']:
            return fetch_result
        
        # Analyze historical data
        analysis_result = self.analyze_historical_data(fetch_result['historical_data'])
        
        # Combine results
        final_result = {
            'success': True,
            'fetch_result': fetch_result,
            'analysis_result': analysis_result,
            'summary': {
                'total_instruments_available': fetch_result['total_instruments_available'],
                'processed_instruments': fetch_result['processed_instruments'],
                'successful_historical_data': len([r for r in fetch_result['historical_data'] if r.get('historical_data')]),
                'analyzed_instruments': analysis_result.get('total_analyzed', 0)
            }
        }
        
        print(f"\n📊 Filter1 Summary:")
        print(f"   Total NSE instruments available: {final_result['summary']['total_instruments_available']}")
        print(f"   Processed instruments: {final_result['summary']['processed_instruments']}")
        print(f"   Successful historical data fetches: {final_result['summary']['successful_historical_data']}")
        print(f"   Analyzed instruments: {final_result['summary']['analyzed_instruments']}")
        
        return final_result

def main():
    """Main function to run Filter1."""
    print("Filter1: NSE Instruments and Historical Data Fetcher")
    print("This script fetches instruments from NSE and their historical data")
    print()
    
    try:
        # Initialize Filter1
        filter1 = Filter1()
        
        if not filter1.kite_service:
            print("❌ Cannot proceed without KiteService initialization")
            return
        
        # Run Filter1 with default parameters (5 instruments)
        result = filter1.run_filter1(max_instruments=1)
        
        if result['success']:
            print("\n🎉 Filter1 completed successfully!")
            
            # Optionally save results to file
            import json
            with open('filter1_results.json', 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print("💾 Results saved to filter1_results.json")
            
        else:
            print(f"\n❌ Filter1 failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error running Filter1: {e}")

if __name__ == "__main__":
    main()

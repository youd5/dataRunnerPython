#!/usr/bin/env python3
"""
Filter1: Fetches instruments and historical data for analysis.
"""

import sys
import os
import time
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any


# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from kite_service import KiteService, RESULTS_DIR
from history_cache import HistoryCache, history_date_range

# Instruments priced below this are dropped (10-day average close, and last price in the prefilter)
MIN_PRICE = 30
# Kite's quote endpoints take up to 1000 instruments per call and allow 1 call per second
OHLC_BATCH_SIZE = 1000
OHLC_CALL_INTERVAL_SECONDS = 1.0

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
    
    def get_instruments_data(self) -> Dict[str, Any]:
        """
        Get instruments data either from CSV cache or NSE API.
        
        Returns:
            Dict[str, Any]: Instruments result in standard format
        """
        # Check if instruments CSV file exists
        instruments_csv_path = f"{RESULTS_DIR}/instruments/nse-instruments.csv"
        
        if os.path.exists(instruments_csv_path):
            print(f"📁 Found existing instruments file: {instruments_csv_path}")
            print("📊 Loading instruments from CSV file...")
            
            # Load instruments from CSV
            instruments_df = pd.read_csv(instruments_csv_path)
            instruments = instruments_df.to_dict('records')
            
            print(f"✅ Loaded {len(instruments)} instruments from CSV file")
            
            # Create instruments_result in the expected format
            instruments_result = {
                'success': True,
                'instruments': instruments
            }
        else:
            print("📡 CSV file not found, fetching from NSE API...")
            # Step 1: Fetch all instruments from NSE exchange
            instruments_result = self.kite_service.get_instruments(exchange='NSE')

            instruments = instruments_result['instruments']
            
            # Only save to CSV if we fetched from API (not from existing CSV)
            instruments_csv_path = f"{RESULTS_DIR}/instruments/nse-instruments.csv"
            if not os.path.exists(instruments_csv_path):
                # Save instruments to CSV
                instruments_df = pd.DataFrame(instruments)
                
                # Create results/instruments directory if it doesn't exist
                instruments_dir = f"{RESULTS_DIR}/instruments"
                if not os.path.exists(instruments_dir):
                    os.makedirs(instruments_dir)
                    print(f"📁 Created directory: {instruments_dir}")
                
                # Save instruments to CSV
                instruments_df.to_csv(instruments_csv_path, index=False)
                print(f"💾 NSE instruments saved to: {instruments_csv_path}")
                print(f"📊 Total instruments saved: {len(instruments_df)}")
            else:
                print(f"📁 Using existing instruments file: {instruments_csv_path}")
        
        return instruments_result
    
    def process_csv(self) -> Dict[str, Any]:
        """
        Get instruments data either from CSV cache or NSE API.
        
        Returns:
            Dict[str, Any]: Instruments result in standard format
        """
        # Check if instruments CSV file exists
        instruments_csv_path = f"{RESULTS_DIR}/instruments/nse-instruments.csv"
        
        if os.path.exists(instruments_csv_path):
            print(f"📁 Found existing instruments file: {instruments_csv_path}")
            print("📊 Loading instruments from CSV file...")
            
            # Load instruments from CSV
            instruments_df = pd.read_csv(instruments_csv_path)
            instruments = instruments_df.to_dict('records')
            
            print(f"✅ Loaded {len(instruments)} instruments from CSV file")
            
            # Create instruments_result in the expected format
            instruments_result = {
                'success': True,
                'instruments': instruments
            }
            
            # Separate INDICES from the rest in one pass (row-by-row concat was quadratic)
            print(f"🔄 Processing {len(instruments)} instruments...")
            
            # Names that are missing or not text count as empty, as before
            names = instruments_df['name'].apply(lambda name: name if isinstance(name, str) else '')
            is_index = instruments_df['segment'] == 'INDICES'
            # Only add to other instruments if lot_size == 1 and name is not empty
            is_other = ~is_index & (instruments_df['lot_size'] == 1) & (names.str.strip() != '')
            
            indices_df = instruments_df[is_index].reset_index(drop=True)
            other_instruments_df = instruments_df[is_other].reset_index(drop=True)
            print(f"⏭️ Skipped {len(instruments_df) - len(indices_df) - len(other_instruments_df)} instruments with lot_size != 1 or an empty name")
            
            # Save separated dataframes
            if not indices_df.empty:
                indices_csv_path = f"{RESULTS_DIR}/instruments/nse-indices.csv"
                indices_df.to_csv(indices_csv_path, index=False)
                print(f"💾 INDICES instruments saved to: {indices_csv_path}")
                print(f"📊 Total INDICES instruments: {len(indices_df)}")
            
            if not other_instruments_df.empty:
                other_csv_path = f"{RESULTS_DIR}/instruments/nse-other-instruments.csv"
                other_instruments_df.to_csv(other_csv_path, index=False)
                print(f"💾 Other instruments saved to: {other_csv_path}")
                print(f"📊 Total other instruments: {len(other_instruments_df)}")
            
            print(f"✅ Instrument processing completed!")
            print(f"   📊 INDICES sector: {len(indices_df)} instruments")
            print(f"   📊 Other sectors: {len(other_instruments_df)} instruments")
            
            return instruments_result


    def fetch_instruments_list_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Fetch instruments from a file.
        """
        print(f"Fetching instruments from file: {file_path}")
        instruments_df = pd.read_csv(file_path)
        instruments = instruments_df.to_dict('records')
            
        print(f"✅ Loaded {len(instruments)} instruments from CSV file")
            
            # Create instruments_result in the expected format
        instruments_result = {
            'success': True,
            'instruments': instruments
        }
        return instruments_result
    


    def prefilter_by_last_price(self, instruments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Drop instruments whose last price is below MIN_PRICE, using batched OHLC quotes
        (one call per 1000 instruments) instead of a history call each.
        
        Instruments without a usable quote (missing, zero price, or a failed batch) are kept,
        so the 10-day average close check still decides for them.
        """
        kept = []
        dropped = 0
        for batch_start in range(0, len(instruments), OHLC_BATCH_SIZE):
            batch = instruments[batch_start:batch_start + OHLC_BATCH_SIZE]
            if batch_start > 0:
                time.sleep(OHLC_CALL_INTERVAL_SECONDS)
            keys = [f"{instrument.get('exchange') or 'NSE'}:{instrument.get('tradingsymbol')}" for instrument in batch]
            ohlc_result = self.kite_service.get_ohlc(keys)
            if not ohlc_result['success']:
                print(f"⚠️ OHLC prefilter failed for {len(batch)} instruments, keeping them: {ohlc_result['error']}")
                kept.extend(batch)
                continue
            quotes = ohlc_result['ohlc'] or {}
            for key, instrument in zip(keys, batch):
                last_price = (quotes.get(key) or {}).get('last_price') or 0
                if 0 < last_price < MIN_PRICE:
                    dropped += 1
                else:
                    kept.append(instrument)
        print(f"💸 Price prefilter: dropped {dropped} instruments below {MIN_PRICE}, {len(kept)} left")
        return kept

    def fetch_instruments_and_historical_data(self, instruments_file_path: str = f"{RESULTS_DIR}/instruments/nse-indices.csv", output_file_path: str = "ohlc-nse-indices.csv", cache_history: bool = False, prefilter_price: bool = False) -> Dict[str, Any]:
        """
        Fetch all instruments from NSE and get historical data for up to max_instruments.
        
        Args:
            instruments_file_path (str): Path to the instruments file (default: "results/instruments/nse-indices.csv" under the project root)
            max_instruments (int): Maximum number of instruments to process (default: 5)
            cache_history (bool): Fetch a year of candles in the same call and keep them for the
                instruments that pass, so Filter2 and Filter3 do not download them again
            prefilter_price (bool): Skip instruments whose last price is below MIN_PRICE before
                fetching any history
            
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
            # Get instruments data (from CSV cache or API)
            #instruments_result = self.get_instruments_data()
            if not os.path.exists(instruments_file_path):
                # Instrument lists are generated, not committed: download from Kite and split them
                print(f"📁 {instruments_file_path} not found, building instrument lists...")
                self.get_instruments_data()
                self.process_csv()
            instruments_result = self.fetch_instruments_list_from_file(instruments_file_path)
            #instruments_result = self.fetch_instruments_list_from_file(f"{RESULTS_DIR}/instruments/nse-other-instruments.csv")
            
            
            #self.process_csv()
            
            if not instruments_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to fetch instruments: {instruments_result['error']}"
                }
            
            instruments = instruments_result['instruments']
            if prefilter_price:
                instruments = self.prefilter_by_last_price(instruments)
            
            # Step 2: Process up to max_instruments
            
            # Calculate date range (today - 8 days to today)
            now = datetime.now()
            end_date = now.strftime("%Y-%m-%d")
            start_date = (now - timedelta(days=10)).strftime("%Y-%m-%d")
            # One request either way: ask for the year Filter2/Filter3 need and screen the last 10 days of it
            fetch_from_date, fetch_to_date = history_date_range(now) if cache_history else (start_date, end_date)
            history_by_token = {}
            resultFrame = pd.DataFrame(columns=['Symbol', 'name', 'token', "weekAvgVol"])
            count = 0
            max_instruments = 5
            
            # Initialize list to collect all instrument history dataframes
            all_instrument_histories = []
            
            print(f"📅 Date range: {start_date} to {end_date}")
            print(f"🔄 Processing up to {max_instruments} instruments...")
            
            # Iterate over instruments (limit to max_instruments)
            for i, instrument in enumerate(instruments): #instruments[:max_instruments] for partial processing
                try:
                    instrument_token = instrument.get('instrument_token')
                    trading_symbol = instrument.get('tradingsymbol', 'Unknown')
                    name = instrument.get('name', 'Unknown')
                    
                    print(f"\n📊 Processing instrument {i+1}/{max_instruments}:")
                    print(f"   Symbol: {trading_symbol}")
                    
                    # Step 3: Fetch historical data
                    if instrument_token:
                        print(f"   📈 Fetching historical data...")
                        
                        historical_result = self.kite_service.historical_data(
                            instrument_token=instrument_token,
                            from_date=fetch_from_date,
                            to_date=fetch_to_date,
                            interval="day"
                        )
                        
                        if historical_result['success']:
                            print(f"   ✅ Historical data fetched: {historical_result['count']} data points")

                            candles = historical_result['data'] or []
                            recent_candles = [c for c in candles if str(c['date'])[:10] >= start_date]
                            historyData = pd.DataFrame(recent_candles)
                            # print(f"historyData {trading_symbol}, {instrument_token} \n", historyData)

                            # Create dataframe with trading_symbol, instrument_token, and all historyData columns
                            if not historyData.empty:
                                # Create a new dataframe with all the data
                                weekAvgVol = round(historyData["volume"].mean(), 2)
                                weekAvgClose = round(historyData["close"].mean(), 2)
                                print("weekAvgVol, weekAvgClose", weekAvgVol, weekAvgClose)
                                # skip scripts with Volume less than 200000
                                if weekAvgVol < 100000 and weekAvgVol > 0:
                                    print("skipping low volume or zero volume -- " + trading_symbol)
                                    continue
                                if weekAvgClose < MIN_PRICE:
                                    print("skipping low price -- " + trading_symbol)
                                    continue
                                instrument_history_df = historyData.copy()
                                
                                # Add trading_symbol and instrument_token as the first two columns
                                instrument_history_df.insert(0, 'instrument_token', instrument_token)
                                instrument_history_df.insert(0, 'trading_symbol', trading_symbol)

                                # add "change" and "changePercent" columns to instrument_history_df, round to 2 decimal places
                                # Calculate change as current close - previous close, but first row uses close - open
                                instrument_history_df['change'] = (instrument_history_df['close'] - instrument_history_df['close'].shift(1)).round(2)
                                instrument_history_df.loc[0, 'change'] = (instrument_history_df.loc[0, 'close'] - instrument_history_df.loc[0, 'open']).round(2)
                                instrument_history_df['changePercent'] = ((instrument_history_df['change'] / instrument_history_df['close'].shift(1)) * 100).round(2)
                                instrument_history_df.loc[0, 'changePercent'] = ((instrument_history_df.loc[0, 'change'] / instrument_history_df.loc[0, 'open']) * 100).round(2)
                                instrument_history_df['marketCap'] = "Unknown"
                                # insert "trend" column to instrument_history_df, value is "UP" if changePercent > 0, "DOWN" if changePercent < 0, "NEUTRAL" if changePercent == 0
                                instrument_history_df['trend'] = "UP"
                                instrument_history_df['sector'] = "Unknown"

                                # Append to the list of all instrument histories
                                all_instrument_histories.append(instrument_history_df)
                                if cache_history:
                                    history_by_token[instrument_token] = pd.DataFrame(candles)
                                
                                print(f"📊 Added {trading_symbol} data to collection. Shape: {instrument_history_df.shape}")
                                # print(instrument_history_df)
                                
                            else:
                                print(f"⚠️ No historical data available for {trading_symbol}")

                        else:
                            print(f"   ❌ Failed to fetch historical data: {historical_result['error']}")
                            
                    else:
                        print(f"   ⚠️ No instrument token found")
                        
                except Exception as e:
                    print(f"   ❌ Error processing instrument: {e}")
                    continue
            
            # Combine all instrument history dataframes into one
            if all_instrument_histories:
                print(f"\n🔄 Combining {len(all_instrument_histories)} instrument histories...")
                combined_ohlc_df = pd.concat(all_instrument_histories, ignore_index=True)
                
                print(f"📊 Combined OHLC data shape: {combined_ohlc_df.shape}")
                print(f"📊 Columns: {list(combined_ohlc_df.columns)}")
                print(f"📊 Unique instruments: {combined_ohlc_df['trading_symbol'].nunique()}")
                
                # Create results directory if it doesn't exist
                results_dir = RESULTS_DIR
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)
                    print(f"📁 Created directory: {results_dir}")
                
                # Save combined OHLC data to CSV, add date to the output file name
                ohlc_csv_filename = f"{results_dir}/{end_date}_{output_file_path}"
                combined_ohlc_df.to_csv(ohlc_csv_filename, index=False)
                print(f"💾 Combined OHLC data saved to: {ohlc_csv_filename}")
                print(f"📊 Total records: {len(combined_ohlc_df)}")
            else:
                print("⚠️ No instrument history data collected")

            if cache_history:
                HistoryCache(fetch_from_date, fetch_to_date).put_all(history_by_token)
            
            return {
                'success': True,
                'total_instruments_available': len(instruments),
                'processed_instruments': len("processed_instruments"),
                'instruments': "processed_instruments",
                'historical_data': "historical_data_results",
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
        fetch_result = self.fetch_instruments_and_historical_data(instruments_file_path=f"{RESULTS_DIR}/instruments/nse-indices.csv", output_file_path="ohlc-nse-indices.csv")
        fetch_result = self.fetch_instruments_and_historical_data(instruments_file_path=f"{RESULTS_DIR}/instruments/nse-other-instruments.csv", output_file_path="ohlc-nse-other-instruments.csv", cache_history=True, prefilter_price=True)
        
        if not fetch_result['success']:
            return fetch_result
        
        
        # Combine results
        final_result = {
            'success': True,
            'fetch_result': fetch_result
        }
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

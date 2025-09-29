#!/usr/bin/env python3
"""
Filter1: Fetches instruments and historical data for analysis.
"""

import sys
import os
import pandas as pd
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
    
    def get_instruments_data(self) -> Dict[str, Any]:
        """
        Get instruments data either from CSV cache or NSE API.
        
        Returns:
            Dict[str, Any]: Instruments result in standard format
        """
        # Check if instruments CSV file exists
        instruments_csv_path = "results/instruments/nse-instruments.csv"
        
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
            instruments_csv_path = "results/instruments/nse-instruments.csv"
            if not os.path.exists(instruments_csv_path):
                # Save instruments to CSV
                instruments_df = pd.DataFrame(instruments)
                
                # Create results/instruments directory if it doesn't exist
                instruments_dir = "results/instruments"
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
        instruments_csv_path = "results/instruments/nse-instruments.csv"
        
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
            
            # Iterate over instruments and separate INDICES sector
            print(f"🔄 Processing {len(instruments)} instruments...")
            
            # Create separate dataframes for different sectors
            indices_df = pd.DataFrame()
            other_instruments_df = pd.DataFrame()
            
            for i, instrument in enumerate(instruments):
                try:
                    # Get sector information
                    sector = instrument.get('segment', 'Unknown')
                    instrument_type = instrument.get('instrument_type', 'Unknown')
                    
                    # Convert instrument to DataFrame row
                    instrument_row = pd.DataFrame([instrument])
                    
                    # Check if it's an INDICES sector
                    if sector == 'INDICES':
                        if indices_df.empty:
                            indices_df = instrument_row
                        else:
                            indices_df = pd.concat([indices_df, instrument_row], ignore_index=True)
                        print(f"📊 Found INDICES instrument: {instrument.get('tradingsymbol', 'Unknown')}")
                    else:
                        # Check for lot size - only add to other instruments if lot_size == 1
                        lot_size = instrument.get('lot_size', 0)
                        # Check for "name" - do not add to other instruments if name is empty
                        name = instrument.get('name', '')
                        
                        if lot_size == 1 and name.strip() != '':
                            if other_instruments_df.empty:
                                other_instruments_df = instrument_row
                            else:
                                other_instruments_df = pd.concat([other_instruments_df, instrument_row], ignore_index=True)
                            print(f"📊 Added instrument with lot_size=1 and valid name: {instrument.get('tradingsymbol', 'Unknown')}")
                        else:
                            # Determine reason for skipping
                            if lot_size != 1:
                                print(f"⏭️ Skipped instrument with lot_size={lot_size}: {instrument.get('tradingsymbol', 'Unknown')}")
                            elif name.strip() == '':
                                print(f"⏭️ Skipped instrument with empty name: {instrument.get('tradingsymbol', 'Unknown')}")
                            else:
                                print(f"⏭️ Skipped instrument: {instrument.get('tradingsymbol', 'Unknown')}")
                    
                    # Progress indicator
                    if (i + 1) % 500 == 0:
                        print(f"   Processed {i + 1}/{len(instruments)} instruments...")
                        
                except Exception as e:
                    print(f"   ⚠️ Error processing instrument {i}: {e}")
                    continue
            
            # Save separated dataframes
            if not indices_df.empty:
                indices_csv_path = "results/instruments/nse-indices.csv"
                indices_df.to_csv(indices_csv_path, index=False)
                print(f"💾 INDICES instruments saved to: {indices_csv_path}")
                print(f"📊 Total INDICES instruments: {len(indices_df)}")
            
            if not other_instruments_df.empty:
                other_csv_path = "results/instruments/nse-other-instruments.csv"
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
    


    def fetch_instruments_and_historical_data(self, instruments_file_path: str = "results/instruments/nse-indices.csv", output_file_path: str = "results/ohlc-nse-indices.csv") -> Dict[str, Any]:
        """
        Fetch all instruments from NSE and get historical data for up to max_instruments.
        
        Args:
            instruments_file_path (str): Path to the instruments file (default: "results/instruments/nse-indices.csv")
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
            # Get instruments data (from CSV cache or API)
            #instruments_result = self.get_instruments_data()
            instruments_result = self.fetch_instruments_list_from_file(instruments_file_path)
            #instruments_result = self.fetch_instruments_list_from_file("results/instruments/nse-other-instruments.csv")
            
            
            #self.process_csv()
            
            if not instruments_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to fetch instruments: {instruments_result['error']}"
                }
            
            instruments = instruments_result['instruments']
            
            # Step 2: Process up to max_instruments
            
            # Calculate date range (today - 8 days to today)
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
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
                            from_date=start_date,
                            to_date=end_date,
                            interval="day"
                        )
                        
                        if historical_result['success']:
                            print(f"   ✅ Historical data fetched: {historical_result['count']} data points")

                            historyData = pd.DataFrame(historical_result['data'])
                            print(f"historyData {trading_symbol}, {instrument_token} \n", historyData)

                            # Create dataframe with trading_symbol, instrument_token, and all historyData columns
                            if not historyData.empty:
                                # Create a new dataframe with all the data
                                instrument_history_df = historyData.copy()
                                
                                # Add trading_symbol and instrument_token as the first two columns
                                instrument_history_df.insert(0, 'instrument_token', instrument_token)
                                instrument_history_df.insert(0, 'trading_symbol', trading_symbol)

                                # Append to the list of all instrument histories
                                all_instrument_histories.append(instrument_history_df)
                                
                                print(f"📊 Added {trading_symbol} data to collection. Shape: {instrument_history_df.shape}")
                                print(instrument_history_df)
                                
                            else:
                                print(f"⚠️ No historical data available for {trading_symbol}")

                            # weekAvgVol = round(historyData["volume"].mean(), 2)
                            # weekAvgClose = round(historyData["close"].mean(), 2)
                            #print("weekAvgVol, weekAvgClose", weekAvgVol, weekAvgClose)
                            # skip scripts with Volume less than 300000
                            # if weekAvgVol > 200000:
                            #     print("skipping low volume -- " + trading_symbol)
                            #     continue
                            # if weekAvgClose < 30:
                            #     print("skipping low price -- " + trading_symbol)
                            #     continue
                            # print("adding data to resultFrame -- " + trading_symbol)
                            # resultFrame.loc[count] = [trading_symbol, trading_symbol, str(instrument_token), weekAvgVol]
                            # count += 1
                            
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
                results_dir = "results"
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)
                    print(f"📁 Created directory: {results_dir}")
                
                # Save combined OHLC data to CSV
                ohlc_csv_filename = f"{output_file_path}"
                combined_ohlc_df.to_csv(ohlc_csv_filename, index=False)
                print(f"💾 Combined OHLC data saved to: {ohlc_csv_filename}")
                print(f"📊 Total records: {len(combined_ohlc_df)}")
            else:
                print("⚠️ No instrument history data collected")
            
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
        #fetch_result = self.fetch_instruments_and_historical_data(instruments_file_path="results/instruments/nse-indices.csv", output_file_path="results/ohlc-nse-indices.csv")
        fetch_result = self.fetch_instruments_and_historical_data(instruments_file_path="results/instruments/nse-other-instruments.csv", output_file_path="results/ohlc-nse-other-instruments.csv")
        
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

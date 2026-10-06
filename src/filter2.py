#!/usr/bin/env python3
"""
Filter2: Filters instruments below 200-day and 50-day moving average.
Fetches instruments from CSV, gets 1-year historical data, and filters based on 200-day MA.
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from kite_service import KiteService, RESULTS_DIR

# TODO: add a column to the final csv to include how much percentage away from the 52 week high is the current price and sort in descending order of this column 



class Filter2:
    """Filter2 class for filtering instruments below 200-day moving average."""
    
    def __init__(self):
        """Initialize Filter2 with KiteService."""
        try:
            self.kite_service = KiteService()
            print("✅ Filter2 initialized with KiteService")
        except Exception as e:
            print(f"❌ Failed to initialize Filter2: {e}")
            self.kite_service = None
    
    def load_instruments_from_csv(self, csv_path: str) -> List[Dict[str, Any]]:
        """
        Load instruments from CSV file.
        
        Args:
            csv_path (str): Path to CSV file containing instruments
            
        Returns:
            List[Dict[str, Any]]: List of instrument dictionaries
        """
        try:
            print(f"📁 Loading instruments from: {csv_path}")
            
            # Read CSV file
            df = pd.read_csv(csv_path)
            
            # Get unique instruments (trading_symbol and instrument_token)
            # Group by trading_symbol and instrument_token to get unique instruments
            unique_instruments = df[['trading_symbol', 'instrument_token']].drop_duplicates()
            
            # Convert to list of dictionaries
            instruments = []
            for _, row in unique_instruments.iterrows():
                instruments.append({
                    'trading_symbol': row['trading_symbol'],
                    'instrument_token': int(row['instrument_token'])
                })
            
            print(f"✅ Loaded {len(instruments)} unique instruments from CSV")
            return instruments
            
        except Exception as e:
            print(f"❌ Error loading instruments from CSV: {e}")
            return []
    
    def fetch_historical_data(self, instrument_token: int, trading_symbol: str, 
                            from_date: str, to_date: str) -> pd.DataFrame:
        """
        Fetch historical data for an instrument.
        
        Args:
            instrument_token (int): Instrument token
            trading_symbol (str): Trading symbol
            from_date (str): Start date (YYYY-MM-DD)
            to_date (str): End date (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: Historical data as DataFrame
        """
        try:
            print(f"📊 Fetching historical data for {trading_symbol} ({instrument_token})...")
            
            # Fetch historical data from Kite API
            result = self.kite_service.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="day"
            )
            
            if result.get('success') and result.get('data'):
                # Convert to DataFrame
                df = pd.DataFrame(result['data'])
                
                if not df.empty:
                    # Add trading_symbol and instrument_token columns
                    df.insert(0, 'instrument_token', instrument_token)
                    df.insert(0, 'trading_symbol', trading_symbol)
                    
                    print(f"✅ Fetched {len(df)} records for {trading_symbol}")
                    return df
                else:
                    print(f"⚠️ No data available for {trading_symbol}")
                    return pd.DataFrame()
            else:
                print(f"❌ Failed to fetch data for {trading_symbol}: {result.get('error', 'Unknown error')}")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Error fetching historical data for {trading_symbol}: {e}")
            return pd.DataFrame()
    
    def calculate_moving_averages_and_52wh_52wl(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate 200-day moving average and filter instruments below it.
        
        Args:
            df (pd.DataFrame): Historical data DataFrame with 'close' column
            
        Returns:
            pd.DataFrame: DataFrame with 200-day and 50-day MA column added
        """
        if df.empty or 'close' not in df.columns:
            return df
        
        # Calculate 200-day moving average
        df['ma_200'] = round(df['close'].rolling(window=200).mean(), 2)
        df['ma_150'] = round(df['close'].rolling(window=150).mean(), 2)
        df['ma_50'] = round(df['close'].rolling(window=50).mean(), 2)
        df['52wh'] = round(df['close'].rolling(window=245).max(), 2) 
        df['52wl'] = round(df['close'].rolling(window=245).min(), 2)

        max_close_in_52_weeks = max(df['close'][:len(df) - 1])  # max value excluding today
        if df["close"][len(df) - 1] > max_close_in_52_weeks:
            df['new_52_week_high'] = True
        else:
            df['new_52_week_high'] = False
        
        
        return df
    
    def is_minervini_condition_fulfilled(self, df: pd.DataFrame) -> bool:
        """
        close > 50 SMA > 150 SMA > 200 SMA 
        """
        if df.empty or 'close' not in df.columns or 'ma_200' not in df.columns or '52wh' not in df.columns or '52wl' not in df.columns:
            return False
        
        # Get the latest row
        latest = df.iloc[-1]

        # Condition 1: Current Price > 150 SMA and > 200 SMA
        if (latest['close'] > latest['ma_50'] and \
             latest['ma_50'] > latest['ma_150'] and \
             latest['ma_150'] > latest['ma_200']):
            cond_1 = True
        else:
            cond_1 = False
        
        # Condition 2: Current Price is at least 30% above 52 week low (Many of the best are up 100-300% before coming out of consolidation)
        if (latest['close'] >= (1.3 * latest['52wl'])):
            cond_2 = True
        else:
            cond_2 = False
        # Condition 3: Current Price is within 25% of 52 week high
        if (latest['close'] >= (.75 * latest['52wh'])):
            cond_3 = True
        else:
            cond_3 = False
        # # Condition 4: IBD RS rating >70 and the higher the better
        # # if(RS_Rating>70):
        # #	cond_4=True
        # # else:
        # #	cond_4=False
        # # Condition 5: 200 SMA trending up for at least 1 month (ideally 4-5 months)
        # if (latest['ma_200'] > latest['ma_200_20']):
        #     cond_5 = True
        # else:
        #     cond_5 = False
        

        if cond_1 and cond_2 and cond_3:
            return True
        else:
            return False
        
        # Check if we have a valid 200-day MA (not NaN)
        # if pd.isna(latest['ma_200']) or pd.isna(latest['ma_50']) or pd.isna(latest['52wh']) or pd.isna(latest['52wl']):
        #     return False
        
        # # Check if close is above 200-day MA
        # return latest['close'] > latest['ma_200'] and latest['close'] > latest['ma_50']
    
    def run_filter(self, csv_path: str = None, output_path: str = None, max_instruments: int = None) -> pd.DataFrame:
        """
        Run the filter to find instruments above 200-day and 50-day moving average and 200-day MA is above 50-day MA.
        
        Args:
            csv_path (str): Path to input CSV file. Defaults to results/ohlc-nse-other-instruments_2025-10-05.csv
            output_path (str): Path to save filtered results. If None, auto-generates filename.
            max_instruments (int): Maximum number of instruments to process. If None, processes all.
            
        Returns:
            pd.DataFrame: Filtered instruments above 200-day and 50-day MA and 200-day MA is above 50-day MA
        """
        if not self.kite_service:
            print("❌ KiteService not initialized. Cannot run filter.")
            return pd.DataFrame()
        
        # Set default CSV path if not provided
        if csv_path is None:
            csv_path = f"{RESULTS_DIR}/ohlc-nse-other-instruments_2025-10-09.csv"
        
        # Load instruments from CSV
        instruments = self.load_instruments_from_csv(csv_path)
        print(f"Instruments: {len(instruments)}")
        
        if not instruments:
            print("❌ No instruments loaded. Exiting.")
            return pd.DataFrame()
        
        # Limit instruments if max_instruments is specified
        if max_instruments:
            instruments = instruments[:max_instruments]
            print(f"📌 Processing limited to {max_instruments} instruments")
        
        # Calculate date range (1 year from today)
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        print(f"\n📅 Date range: {start_date} to {end_date}")
        print(f"📊 Processing {len(instruments)} instruments...\n")
        
        # List to store instruments above 200-day and 50-day MA and 200-day MA is above 50-day MA
        filtered_instruments = []
        
        # Process each instrument
        for i, instrument in enumerate(instruments):
            try:
                trading_symbol = instrument['trading_symbol']
                instrument_token = instrument['instrument_token']
                
                print(f"\n[{i+1}/{len(instruments)}] Processing {trading_symbol}...")
                
                # Fetch historical data
                hist_df = self.fetch_historical_data(
                    instrument_token=instrument_token,
                    trading_symbol=trading_symbol,
                    from_date=start_date,
                    to_date=end_date
                )
                
                if hist_df.empty:
                    print(f"⚠️ Skipping {trading_symbol} - no data available")
                    continue
                
                # Calculate moving averages and 52 week high and low
                hist_df = self.calculate_moving_averages_and_52wh_52wl(hist_df)
                
                # Check if above 200-day and 50-day MA and 200-day MA is above 50-day MA
                if not self.is_minervini_condition_fulfilled(hist_df):
                    continue
                
                latest = hist_df.iloc[-1]
                
                # Calculate % away from 52-week high
                if pd.notna(latest['52wh']) and latest['52wh'] > 0:
                    pct_away_from_52wh = round(((latest['close'] - latest['52wh']) / latest['52wh']) * 100, 2)
                else:
                    pct_away_from_52wh = None
                
                print(f"adding Latest to filtered instruments: {trading_symbol}")
                filtered_instruments.append({
                    'trading_symbol': trading_symbol,
                    'name': trading_symbol,
                    'instrument_token': instrument_token,
                    'currentClose': latest['close'],
                    'ma_200': latest['ma_200'],
                    'ma_50': latest['ma_50'],
                    '52wh': latest['52wh'],
                    '52wl': latest['52wl'],
                    'new_52_week_high': latest['new_52_week_high'],
                    'pct_away_from_52wh': pct_away_from_52wh,
                    'date': str(latest['date'])[0:10] # get only date part
                })
                
                print(f"✅ {trading_symbol} is ABOVE 200-day and 50-day MA: Close={latest['close']}, MA={latest['ma_200']:.2f}, MA_50={latest['ma_50']:.2f}")
                
            except Exception as e:
                print(f"❌ Error processing {instrument.get('trading_symbol', 'unknown')}: {e}")
                continue
        
        # Create DataFrame from filtered instruments
        result_df = pd.DataFrame(filtered_instruments)
        
        # Sort by % away from 52-week high in descending order
        if not result_df.empty and 'pct_away_from_52wh' in result_df.columns:
            result_df = result_df.sort_values('pct_away_from_52wh', ascending=False, na_position='last')
        
        print(f"\n" + "="*80)
        print(f"✅ Filter complete!")
        print(f"📊 Total instruments processed: {len(instruments)}")
        print(f"📉 Instruments above 200-day and 50-day MA: {len(filtered_instruments)}")
        print("="*80)
        
        # Save results to CSV if output_path is provided or auto-generate
        if result_df.empty:
            print("\n⚠️ No instruments found above 200-day and 50-day MA")
        else:
            if output_path is None:
                # Auto-generate filename with timestamp
                output_path = f"{RESULTS_DIR}/{datetime.now().strftime('%Y-%m-%d')}_filter2_minervini_filter_list.csv"
            
            # Create results directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save to CSV
            result_df.to_csv(output_path, index=False)
            print(f"\n💾 Results saved to: {output_path}")
        
        return result_df


def main():
    """Main function to run Filter2."""
    print("="*80)
    print("🔍 Filter2: Finding instruments below 200-day and 50-day moving average")
    print("="*80)
    
    # Initialize Filter2
    filter2 = Filter2()
    
    # Run the filter
    # You can customize these parameters:
    # - csv_path: Path to input CSV file
    # - output_path: Path to save results
    # - max_instruments: Limit number of instruments to process (useful for testing)
    results_dir = RESULTS_DIR
    end_date = datetime.now().strftime("%Y-%m-%d")
    output_file_path = "ohlc-nse-other-instruments.csv"
    ohlc_csv_filename = f"{results_dir}/{end_date}_{output_file_path}"

    result_df = filter2.run_filter(
        csv_path=ohlc_csv_filename,
        output_path=None,  # Auto-generates filename
        max_instruments=None  # Process all instruments (or set to e.g., 10 for testing)
    )
    
    print("\n✅ Filter2 execution complete!")


if __name__ == "__main__":
    main()


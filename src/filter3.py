#!/usr/bin/env python3
"""
Filter3: Filters instruments above last pivot point.
Fetches instruments from Filter2 results, gets 1-year historical data, and filters based on pivot points.
A pivot is a local maxima where the day's high is higher than the previous 5 and next 5 trading sessions' highs.
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from kite_service import KiteService, RESULTS_DIR


class Filter3:
    """Filter3 class for filtering instruments above last pivot point."""
    
    def __init__(self):
        """Initialize Filter3 with KiteService."""
        try:
            self.kite_service = KiteService()
            print("✅ Filter3 initialized with KiteService")
        except Exception as e:
            print(f"❌ Failed to initialize Filter3: {e}")
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
    
    def find_pivot_points(self, df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
        """
        Find pivot points in the historical data.
        A pivot is a local maxima where the day's high is higher than the previous 
        'lookback' and next 'lookback' trading sessions' highs.
        
        Args:
            df (pd.DataFrame): Historical data DataFrame with 'high' column
            lookback (int): Number of periods to look back and forward (default: 5)
            
        Returns:
            pd.DataFrame: DataFrame with 'is_pivot' column added
        """
        if df.empty or 'high' not in df.columns:
            return df
        
        # Reset index to ensure we have a clean integer index
        df = df.reset_index(drop=True)
        
        # Initialize is_pivot column
        df['is_pivot'] = False
        
        # We need at least (2 * lookback + 1) data points to find pivots
        if len(df) < (2 * lookback + 1):
            print(f"⚠️ Not enough data points ({len(df)}) to find pivots (need at least {2 * lookback + 1})")
            return df
        
        # Iterate through each potential pivot point
        # Start from lookback index and end at len-lookback to ensure we have enough data on both sides
        for i in range(lookback, len(df) - lookback):
            current_high = df.loc[i, 'high']
            
            # Check if current high is greater than previous 'lookback' highs
            prev_highs = df.loc[i - lookback:i - 1, 'high']
            is_higher_than_prev = all(current_high > h for h in prev_highs)
            
            # Check if current high is greater than next 'lookback' highs
            next_highs = df.loc[i + 1:i + lookback, 'high']
            is_higher_than_next = all(current_high > h for h in next_highs)
            
            # Mark as pivot if both conditions are met
            if is_higher_than_prev and is_higher_than_next:
                df.loc[i, 'is_pivot'] = True
        
        return df
    
    def get_last_pivot(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Get the last (most recent) pivot point from the DataFrame.
        
        Args:
            df (pd.DataFrame): Historical data with 'is_pivot' column
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary with pivot information or None
        """
        if df.empty or 'is_pivot' not in df.columns:
            return None
        
        # Filter for pivot points
        pivots = df[df['is_pivot'] == True]
        
        if pivots.empty:
            return None
        
        # Get the last pivot (most recent)
        last_pivot = pivots.iloc[-1]
        
        return {
            'date': last_pivot['date'],
            'high': last_pivot['high'],
            'close': last_pivot['close'],
            'index': last_pivot.name if hasattr(last_pivot, 'name') else None
        }
    
    def is_above_last_pivot(self, df: pd.DataFrame) -> bool:
        """
        Check if the current price is above the last pivot point's high.
        
        Args:
            df (pd.DataFrame): Historical data with pivot information
            
        Returns:
            bool: True if current close is above last pivot high, False otherwise
        """
        if df.empty:
            return False
        
        # Get last pivot
        last_pivot = self.get_last_pivot(df)
        
        if last_pivot is None:
            return False
        
        # Get current close price
        current_close = df.iloc[-1]['close']
        
        # Check if current close is above last pivot's high
        return current_close > last_pivot['high']
    
    def run_filter(self, csv_path: str = None, output_path: str = None, 
                   max_instruments: int = None, lookback: int = 5) -> pd.DataFrame:
        """
        Run the filter to find instruments above last pivot point.
        
        Args:
            csv_path (str): Path to input CSV file. Defaults to results/filter2_above_200ma_and_50ma_2025-10-09.csv
            output_path (str): Path to save filtered results. If None, auto-generates filename.
            max_instruments (int): Maximum number of instruments to process. If None, processes all.
            lookback (int): Number of periods to look back/forward for pivot detection (default: 5)
            
        Returns:
            pd.DataFrame: Filtered instruments above last pivot point
        """
        if not self.kite_service:
            print("❌ KiteService not initialized. Cannot run filter.")
            return pd.DataFrame()
        
        # Set default CSV path if not provided
        if csv_path is None:
            csv_path = f"{RESULTS_DIR}/filter2_above_200ma_and_50ma_2025-10-09.csv"
        
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
        print(f"📊 Processing {len(instruments)} instruments...")
        print(f"🔍 Pivot lookback period: {lookback} days\n")
        
        # List to store instruments above last pivot
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
                
                # Find pivot points
                hist_df = self.find_pivot_points(hist_df, lookback=lookback)
                
                # Count pivots
                pivot_count = hist_df['is_pivot'].sum()
                print(f"📌 Found {pivot_count} pivot points for {trading_symbol}")
                
                # Get last pivot
                last_pivot = self.get_last_pivot(hist_df)
                
                if last_pivot is None:
                    print(f"⚠️ No pivot points found for {trading_symbol}")
                    continue
                
                # Check if above last pivot
                if self.is_above_last_pivot(hist_df):
                    latest = hist_df.iloc[-1]
                    
                    filtered_instruments.append({
                        'trading_symbol': trading_symbol,
                        'name': trading_symbol,
                        'instrument_token': instrument_token,
                        'currentClose': latest['close'],
                        'current_high': latest['high'],
                        'latestPivot': last_pivot['high'],
                        'lastPivotDate': str(last_pivot['date'])[0:10],
                        'currentDate': str(latest['date'])[0:10],
                        'above_pivot_by': round(latest['close'] - last_pivot['high'], 2),
                        'above_pivot_percent': round(((latest['close'] - last_pivot['high']) / last_pivot['high']) * 100, 2),
                        'pivot_count': int(pivot_count)
                    })
                    
                    print(f"✅ {trading_symbol} is ABOVE last pivot: Current={latest['close']}, Pivot High={last_pivot['high']:.2f}, Date={str(last_pivot['date'])[0:10]}")
                else:
                    latest = hist_df.iloc[-1]
                    print(f"⏭️ {trading_symbol} is BELOW last pivot: Current={latest['close']}, Pivot High={last_pivot['high']:.2f}")
                
            except Exception as e:
                print(f"❌ Error processing {instrument.get('trading_symbol', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Create DataFrame from filtered instruments
        result_df = pd.DataFrame(filtered_instruments)
        
        print(f"\n" + "="*80)
        print(f"✅ Filter complete!")
        print(f"📊 Total instruments processed: {len(instruments)}")
        print(f"📈 Instruments above last pivot: {len(filtered_instruments)}")
        print("="*80)
        
        # Save results to CSV if output_path is provided or auto-generate
        if result_df.empty:
            print("\n⚠️ No instruments found above last pivot point")
        else:
            if output_path is None:
                # Auto-generate filename with timestamp
                output_path = f"{RESULTS_DIR}/{datetime.now().strftime('%Y-%m-%d')}_filter3_above_pivot.csv"
            
            # Create results directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save to CSV
            result_df.to_csv(output_path, index=False)
            print(f"\n💾 Results saved to: {output_path}")
            
            # Display top instruments sorted by percentage above pivot
            print(f"\nTop 10 instruments above pivot (sorted by % above pivot):")
            print(result_df.sort_values('above_pivot_percent', ascending=False).head(10).to_string(index=False))
        
        return result_df


def main():
    """Main function to run Filter3."""
    print("="*80)
    print("🔍 Filter3: Finding instruments above last pivot point")
    print("="*80)
    
    # Initialize Filter3
    filter3 = Filter3()
    
    # Run the filter
    # You can customize these parameters:
    # - csv_path: Path to input CSV file (from Filter2 results)
    # - output_path: Path to save results
    # - max_instruments: Limit number of instruments to process (useful for testing)
    # - lookback: Number of periods to look back/forward for pivot detection (default: 5)
    
    result_df = filter3.run_filter(
        csv_path=f"{RESULTS_DIR}/{datetime.now().strftime('%Y-%m-%d')}_filter2_minervini_filter_list.csv",
        output_path=None,  # Auto-generates filename
        max_instruments=None,  # Process all instruments (or set to e.g., 10 for testing)
        lookback=5  # Pivot lookback period
    )
    
    print("\n✅ Filter3 execution complete!")


if __name__ == "__main__":
    main()


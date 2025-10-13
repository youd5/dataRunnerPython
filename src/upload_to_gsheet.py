#!/usr/bin/env python3
"""
Upload to Google Sheets: Upload CSV data to Google Sheets.
Checks if sheet exists and replaces contents with CSV data.
"""

import sys
import os
import pandas as pd
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError


class GoogleSheetUploader:
    """Class for uploading CSV data to Google Sheets."""
    
    def __init__(self, credentials_file: str = None):
        """
        Initialize Google Sheet Uploader with credentials.
        
        Args:
            credentials_file (str): Path to Google service account JSON credentials file.
                                   If None, looks for GOOGLE_CREDENTIALS_FILE env variable.
        """
        # Define the scope for Google Sheets API
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Get credentials file path
        if credentials_file is None:
            credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE')
        
        if not credentials_file:
            raise ValueError(
                "Credentials file not provided. Either pass credentials_file parameter "
                "or set GOOGLE_CREDENTIALS_FILE environment variable."
            )
        
        if not os.path.exists(credentials_file):
            raise FileNotFoundError(f"Credentials file not found: {credentials_file}")
        
        self.credentials_file = credentials_file
        
        # Initialize credentials and client
        try:
            self.creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.scopes
            )
            self.client = gspread.authorize(self.creds)
            print("✅ Google Sheets client initialized successfully")
        except Exception as e:
            raise Exception(f"Failed to initialize Google Sheets client: {e}")
    
    def check_sheet_exists(self, sheet_id: str) -> bool:
        """
        Check if a Google Sheet exists.
        
        Args:
            sheet_id (str): Google Sheet ID
            
        Returns:
            bool: True if sheet exists, False otherwise
        """
        try:
            self.client.open_by_key(sheet_id)
            return True
        except SpreadsheetNotFound:
            return False
        except Exception as e:
            print(f"⚠️ Error checking sheet existence: {e}")
            return False
    
    def read_csv(self, csv_path: str) -> pd.DataFrame:
        """
        Read CSV file into a DataFrame.
        
        Args:
            csv_path (str): Path to CSV file
            
        Returns:
            pd.DataFrame: DataFrame with CSV data
        """
        try:
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSV file not found: {csv_path}")
            
            df = pd.read_csv(csv_path)
            print(f"✅ Successfully read CSV file: {csv_path}")
            print(f"📊 CSV dimensions: {df.shape[0]} rows × {df.shape[1]} columns")
            return df
        except Exception as e:
            raise Exception(f"Failed to read CSV file: {e}")
    
    def upload_to_sheet(self, csv_path: str, sheet_id: str, worksheet_name: str = None) -> bool:
        """
        Upload CSV data to Google Sheet. Replaces existing content.
        
        Args:
            csv_path (str): Path to CSV file
            sheet_id (str): Google Sheet ID
            worksheet_name (str): Name of the worksheet to update. If None, uses first sheet.
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if sheet exists
            print(f"\n🔍 Checking if Google Sheet exists (ID: {sheet_id})...")
            
            if not self.check_sheet_exists(sheet_id):
                raise FileNotFoundError(
                    f"❌ Google Sheet with ID '{sheet_id}' does not exist. "
                    "Please create the sheet first or check the Sheet ID."
                )
            
            print("✅ Google Sheet exists")
            
            # Read CSV file
            print(f"\n📁 Reading CSV file: {csv_path}...")
            df = self.read_csv(csv_path)
            
            # Open the spreadsheet
            print(f"\n📤 Opening Google Sheet...")
            spreadsheet = self.client.open_by_key(sheet_id)
            
            # Get or create worksheet
            if worksheet_name:
                try:
                    worksheet = spreadsheet.worksheet(worksheet_name)
                    print(f"✅ Found worksheet: {worksheet_name}")
                except gspread.exceptions.WorksheetNotFound:
                    print(f"⚠️ Worksheet '{worksheet_name}' not found. Using first sheet instead.")
                    worksheet = spreadsheet.sheet1
            else:
                worksheet = spreadsheet.sheet1
                print(f"✅ Using first worksheet: {worksheet.title}")
            
            # Clear existing content
            print(f"\n🧹 Clearing existing content...")
            worksheet.clear()
            
            # Convert DataFrame to list of lists (including header)
            # Replace NaN values with empty strings
            df_filled = df.fillna('')
            
            # Prepare data: header + rows
            header = df_filled.columns.tolist()
            rows = df_filled.values.tolist()
            data = [header] + rows
            
            # Update the worksheet with new data
            print(f"📤 Uploading {len(rows)} rows to Google Sheet...")
            worksheet.update(data, value_input_option='USER_ENTERED')
            
            # Format header row (bold)
            print(f"🎨 Formatting header row...")
            worksheet.format('1', {'textFormat': {'bold': True}})
            
            print(f"\n✅ Successfully uploaded data to Google Sheet!")
            print(f"📊 Uploaded: {len(rows)} rows × {len(header)} columns")
            print(f"🔗 Sheet URL: https://docs.google.com/spreadsheets/d/{sheet_id}")
            
            return True
            
        except FileNotFoundError as e:
            print(f"\n❌ Error: {e}")
            raise
        except APIError as e:
            print(f"\n❌ Google Sheets API Error: {e}")
            raise
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def upload_multiple_sheets(self, csv_files: list, sheet_id: str) -> bool:
        """
        Upload multiple CSV files to different worksheets in the same Google Sheet.
        
        Args:
            csv_files (list): List of tuples (csv_path, worksheet_name)
            sheet_id (str): Google Sheet ID
            
        Returns:
            bool: True if all uploads successful, False otherwise
        """
        try:
            # Check if sheet exists first
            if not self.check_sheet_exists(sheet_id):
                raise FileNotFoundError(
                    f"❌ Google Sheet with ID '{sheet_id}' does not exist. "
                    "Please create the sheet first or check the Sheet ID."
                )
            
            success_count = 0
            for csv_path, worksheet_name in csv_files:
                try:
                    print(f"\n{'='*80}")
                    print(f"Uploading {csv_path} to worksheet '{worksheet_name}'")
                    print(f"{'='*80}")
                    
                    self.upload_to_sheet(csv_path, sheet_id, worksheet_name)
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ Failed to upload {csv_path}: {e}")
                    continue
            
            print(f"\n{'='*80}")
            print(f"✅ Upload complete: {success_count}/{len(csv_files)} files uploaded successfully")
            print(f"{'='*80}")
            
            return success_count == len(csv_files)
            
        except Exception as e:
            print(f"❌ Error in multiple sheet upload: {e}")
            return False


def main():
    """Main function to demonstrate usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Upload CSV file to Google Sheets')
    parser.add_argument('csv_path', help='Path to CSV file')
    parser.add_argument('sheet_id', help='Google Sheet ID')
    parser.add_argument('--worksheet', '-w', help='Worksheet name (optional, uses first sheet if not specified)')
    parser.add_argument('--credentials', '-c', help='Path to Google credentials JSON file')
    
    args = parser.parse_args()
    
    try:
        print("="*80)
        print("📤 Google Sheets Uploader")
        print("="*80)
        
        # Initialize uploader
        uploader = GoogleSheetUploader(credentials_file=args.credentials)
        
        # Upload CSV to Google Sheet
        uploader.upload_to_sheet(
            csv_path=args.csv_path,
            sheet_id=args.sheet_id,
            worksheet_name=args.worksheet
        )
        
        print("\n✅ Upload completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


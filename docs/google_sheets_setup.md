# Google Sheets Upload Setup Guide

## Overview
The `upload_to_gsheet.py` script allows you to upload CSV data to Google Sheets programmatically.

## Prerequisites

### 1. Install Required Dependencies
```bash
pip install gspread google-auth google-auth-oauthlib google-auth-httplib2 pandas
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

### 2. Set Up Google Cloud Project & Service Account

#### Step 1: Create a Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID

#### Step 2: Enable Google Sheets API
1. In the Google Cloud Console, go to "APIs & Services" > "Library"
2. Search for "Google Sheets API"
3. Click "Enable"
4. Also enable "Google Drive API" (needed for file access)

#### Step 3: Create Service Account
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Enter a name (e.g., "sheets-uploader")
4. Click "Create and Continue"
5. Skip role assignment (optional)
6. Click "Done"

#### Step 4: Create Service Account Key
1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" > "Create new key"
4. Select "JSON" format
5. Click "Create"
6. Save the downloaded JSON file securely (e.g., `credentials.json`)

#### Step 5: Share Google Sheet with Service Account
1. Open your Google Sheet
2. Click "Share" button
3. Copy the service account email from the JSON file (looks like: `xxx@xxx.iam.gserviceaccount.com`)
4. Paste it in the share dialog
5. Give "Editor" access
6. Click "Share"

### 3. Configure Environment Variables
Add to your `.env` file:
```bash
GOOGLE_CREDENTIALS_FILE=/path/to/your/credentials.json
```

## Usage

### Command Line Usage

#### Basic Upload (replaces first sheet)
```bash
python src/upload_to_gsheet.py <csv_file_path> <google_sheet_id>
```

Example:
```bash
python src/upload_to_gsheet.py results/filter2_results.csv 1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```

#### Upload to Specific Worksheet
```bash
python src/upload_to_gsheet.py <csv_file_path> <google_sheet_id> --worksheet "Sheet1"
```

Example:
```bash
python src/upload_to_gsheet.py results/filter2_results.csv 1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890 -w "Filter2 Results"
```

#### Specify Custom Credentials File
```bash
python src/upload_to_gsheet.py <csv_file_path> <google_sheet_id> --credentials /path/to/credentials.json
```

### Python Script Usage

```python
from src.upload_to_gsheet import GoogleSheetUploader

# Initialize uploader
uploader = GoogleSheetUploader(credentials_file='credentials.json')

# Upload CSV to Google Sheet
uploader.upload_to_sheet(
    csv_path='results/filter2_results.csv',
    sheet_id='1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890',
    worksheet_name='Filter2 Results'  # Optional
)
```

### Upload Multiple CSV Files to Different Worksheets

```python
from src.upload_to_gsheet import GoogleSheetUploader

# Initialize uploader
uploader = GoogleSheetUploader(credentials_file='credentials.json')

# Upload multiple files
csv_files = [
    ('results/filter1_results.csv', 'Filter1'),
    ('results/filter2_results.csv', 'Filter2'),
    ('results/filter3_results.csv', 'Filter3')
]

uploader.upload_multiple_sheets(
    csv_files=csv_files,
    sheet_id='1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890'
)
```

## Finding Your Google Sheet ID

The Sheet ID is in the URL of your Google Sheet:
```
https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890/edit
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                         This is your Sheet ID
```

## Features

✅ **Sheet Existence Check**: Verifies the Google Sheet exists before uploading  
✅ **Content Replacement**: Clears existing data and replaces with CSV content  
✅ **Auto-formatting**: Bolds the header row automatically  
✅ **Error Handling**: Throws clear errors if sheet doesn't exist  
✅ **Multiple Worksheets**: Can upload to specific worksheet by name  
✅ **Batch Upload**: Upload multiple CSV files to different worksheets  

## Error Handling

### Sheet Not Found Error
```
❌ Google Sheet with ID 'xxx' does not exist. Please create the sheet first or check the Sheet ID.
```
**Solution**: Create the Google Sheet first or verify the Sheet ID is correct.

### Credentials Error
```
Failed to initialize Google Sheets client: ...
```
**Solution**: Check that:
- Credentials JSON file exists
- Path to credentials is correct
- Service account has necessary permissions

### Permission Error
```
Google Sheets API Error: ...
```
**Solution**: Make sure you've shared the Google Sheet with the service account email.

## Example Integration with Filters

```python
from src.filter2 import Filter2
from src.upload_to_gsheet import GoogleSheetUploader

# Run filter
filter2 = Filter2()
result_df = filter2.run_filter(
    csv_path="results/ohlc-nse-other-instruments_2025-10-09.csv"
)

# Upload to Google Sheets
uploader = GoogleSheetUploader()
uploader.upload_to_sheet(
    csv_path='results/2025-10-09_filter2_minervini_filter_list.csv',
    sheet_id='YOUR_SHEET_ID_HERE',
    worksheet_name='Latest Results'
)
```

## Security Notes

⚠️ **IMPORTANT**: Never commit your credentials JSON file to version control!

Add to `.gitignore`:
```
credentials.json
*.json
!package.json
.env
```

## Troubleshooting

1. **Import errors**: Run `pip install -r requirements.txt`
2. **Authentication errors**: Regenerate service account key
3. **Permission errors**: Re-share the sheet with service account email
4. **API not enabled**: Enable Google Sheets API and Google Drive API in Cloud Console


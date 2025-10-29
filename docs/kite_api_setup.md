# Kite API Setup Guide

## The "incorrect api_key or access_token" Error

This error occurs because your Kite API credentials are not properly configured. Here's how to fix it:

## Step 1: Create .env File

Create a `.env` file in your project root (`/Users/udayshankar/mycode/dataRunnerPython/.env`) with the following content:

```bash
# Zerodha Kite API Configuration
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=
KITE_REDIRECT_URL=http://localhost:8080/apis/broker/login/zerodha
KITE_MODE=paper
```

## Step 2: Get Your Kite Connect App Credentials

1. **Go to Kite Connect**: Visit https://kite.trade/connect/login
2. **Login** with your Zerodha credentials
3. **Create a new app** or use existing app
4. **Copy your API Key and API Secret** from the app settings
5. **Set Redirect URL** to: `http://localhost:8080/apis/broker/login/zerodha`

## Step 3: Update .env File

Replace `your_api_key_here` and `your_api_secret_here` with your actual credentials:

```bash
KITE_API_KEY=abc123def456
KITE_API_SECRET=xyz789uvw012
KITE_ACCESS_TOKEN=
KITE_REDIRECT_URL=http://localhost:8080/apis/broker/login/zerodha
KITE_MODE=paper
```

## Step 4: Login to Get Access Token

1. **Start your Flask app**: `python src/main.py`
2. **Visit**: http://localhost:8080
3. **Click "Login with Zerodha"** button
4. **Complete the login process** on Zerodha's website
5. **You'll be redirected back** and the access token will be automatically saved

## Step 5: Verify Setup

After successful login, your `.env` file should look like:

```bash
KITE_API_KEY=abc123def456
KITE_API_SECRET=xyz789uvw012
KITE_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
KITE_REDIRECT_URL=http://localhost:8080/apis/broker/login/zerodha
KITE_MODE=paper
```

## Troubleshooting

### Error: "KITE_API_KEY environment variable is required"
- Make sure your `.env` file exists in the project root
- Check that `KITE_API_KEY` is set correctly

### Error: "incorrect api_key or access_token"
- Verify your API key and secret are correct
- Make sure you've completed the login process to get an access token
- Check that your redirect URL matches exactly

### Error: "Access token expired"
- Re-login through the web interface to get a new token
- Access tokens expire daily, so you may need to refresh them

## Quick Test

After setup, test your credentials:

```python
from src.kite_service import KiteService

try:
    kite = KiteService()
    print("✅ Kite service initialized successfully")
    
    # Test API call
    profile = kite.get_profile()
    if profile['success']:
        print("✅ API credentials working!")
    else:
        print("❌ API call failed:", profile['error'])
        
except Exception as e:
    print("❌ Setup error:", e)
```

## Security Note

⚠️ **Never commit your `.env` file to version control!** It contains sensitive credentials.

Your `.gitignore` should include:
```
.env
*.env
```

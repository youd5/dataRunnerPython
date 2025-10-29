#!/usr/bin/env python3
"""
Test script to verify Kite API credentials setup.
Run this to check if your .env file is configured correctly.
"""

import os
import sys
from dotenv import load_dotenv

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_kite_credentials():
    """Test if Kite credentials are properly configured."""
    print("🔍 Testing Kite API Credentials Setup")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("📝 Please create a .env file in the project root with your Kite credentials.")
        print("📖 See docs/kite_api_setup.md for detailed instructions.")
        return False
    
    print("✅ .env file found")
    
    # Check required environment variables
    api_key = os.getenv('KITE_API_KEY')
    api_secret = os.getenv('KITE_API_SECRET')
    access_token = os.getenv('KITE_ACCESS_TOKEN')
    
    if not api_key or api_key == 'your_api_key_here':
        print("❌ KITE_API_KEY not set or still has placeholder value")
        print("📝 Please set your actual API key in .env file")
        return False
    
    if not api_secret or api_secret == 'your_api_secret_here':
        print("❌ KITE_API_SECRET not set or still has placeholder value")
        print("📝 Please set your actual API secret in .env file")
        return False
    
    print("✅ API Key and Secret configured")
    
    if not access_token:
        print("⚠️ KITE_ACCESS_TOKEN not set")
        print("📝 You need to login through the web interface to get an access token")
        print("🌐 Visit http://localhost:8080 and click 'Login with Zerodha'")
        return False
    
    print("✅ Access token configured")
    
    # Test KiteService initialization
    try:
        from kite_service import KiteService
        kite_service = KiteService()
        print("✅ KiteService initialized successfully")
        
        # Test API call
        print("🔍 Testing API call...")
        profile_result = kite_service.get_profile()
        
        if profile_result['success']:
            print("✅ API credentials working!")
            print(f"👤 User: {profile_result['profile'].get('user_name', 'Unknown')}")
            print(f"📧 Email: {profile_result['profile'].get('email', 'Unknown')}")
            return True
        else:
            print(f"❌ API call failed: {profile_result.get('error', 'Unknown error')}")
            print("🔄 Try logging in again to refresh your access token")
            return False
            
    except ValueError as e:
        print(f"❌ KiteService initialization failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main function."""
    success = test_kite_credentials()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All credentials are working correctly!")
        print("✅ You can now run the algorithm_triggered endpoint")
    else:
        print("❌ Credentials need to be fixed")
        print("📖 Check docs/kite_api_setup.md for detailed setup instructions")
    
    return success

if __name__ == "__main__":
    main()

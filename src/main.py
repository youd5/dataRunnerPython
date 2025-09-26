#!/usr/bin/env python3
"""
Main entry point for the Python web service with Zerodha Kite integration.
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for
from kite_service import KiteService
import os
import urllib.parse
import re

app = Flask(__name__)

def save_token_to_env(access_token):
    """Save the access token to the .env file."""
    env_file = '.env'
    
    try:
        # Read existing .env file
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                content = f.read()
        else:
            # Create .env file with basic structure if it doesn't exist
            content = """
                        Zerodha Kite API Configuration
                        KITE_API_KEY=your_api_key_here
                        KITE_API_SECRET=your_api_secret_here
                        KITE_ACCESS_TOKEN=
                        KITE_REDIRECT_URL=http://localhost:8080/apis/broker/login/zerodha
                        KITE_MODE=paper
                    """
        
        # Update or add KITE_ACCESS_TOKEN
        if 'KITE_ACCESS_TOKEN=' in content:
            # Update existing token
            content = re.sub(
                r'KITE_ACCESS_TOKEN=.*',
                f'KITE_ACCESS_TOKEN={access_token}',
                content
            )
        else:
            # Add new token
            if content and not content.endswith('\n'):
                content += '\n'
            content += f'KITE_ACCESS_TOKEN={access_token}\n'
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.write(content)
            
        print(f"Access token saved to {env_file}")
        
    except Exception as e:
        print(f"Warning: Could not save access token to .env file: {e}")

# Initialize Kite service
try:
    kite_service = KiteService()
except ValueError as e:
    print(f"Warning: {e}")
    print("Please set up your Kite API credentials in .env file")
    kite_service = None

@app.route('/')
def home():
    """Render the home page with CTA button."""
    return render_template('index.html')

@app.route('/holdings')
def holdings():
    """Render the holdings page."""
    return render_template('holdings.html')

@app.route('/positions')
def positions():
    """Render the positions page."""
    return render_template('positions.html')

@app.route('/algorithm-triggered')
def algorithm_triggered():
    """Render the algorithm triggered page."""
    return render_template('algorithm_triggered.html')

@app.route('/api/hello')
def hello_api():
    """API endpoint that returns hello world."""
    return jsonify({"message": "hello world"})

# Authentication endpoints
@app.route('/api/kite/login-url')
def get_login_url():
    """Get Kite login URL for authentication."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    try:
        login_url = kite_service.get_login_url()
        return jsonify({"login_url": login_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/kite/session', methods=['POST'])
def generate_session():
    """Generate access token from request token."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    data = request.get_json()
    request_token = data.get('request_token')
    
    if not request_token:
        return jsonify({"error": "request_token is required"}), 400
    
    result = kite_service.generate_session(request_token)
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/logout', methods=['POST'])
def logout():
    """Clear the access token from .env file."""
    try:
        # Clear the access token by setting it to empty
        save_token_to_env('')
        return jsonify({"success": True, "message": "Logged out successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/apis/broker/login/zerodha')
def kite_callback():
    """Handle the redirect from Zerodha after successful login."""
    # Get the request token from URL parameters
    request_token = request.args.get('request_token')
    
    if not request_token:
        return render_template('callback_error.html', 
                             error="No request token received from Zerodha")
    
    try:
        # Generate session using the request token
        result = kite_service.generate_session(request_token)
        print(f"Result: {result}")
        
        if result['success']:
            # Optionally save the access token to .env file
            save_token_to_env(result['access_token'])
            print(f"Access token saved to .env file: {result['access_token']}")
            
            return render_template('callback_success.html', 
                                 access_token=result['access_token'],
                                 user_info={
                                     'user_id': result.get('user_id', 'Not available'),
                                     'user_name': result.get('user_name', 'Not available'),
                                     'user_email': result.get('user_email', 'Not available')
                                 })
        else:
            return render_template('callback_error.html', 
                                 error=result.get('error', 'Failed to generate session'))
            
    except Exception as e:
        return render_template('callback_error.html', 
                             error=f"Error processing login: {str(e)}")

# Profile and account endpoints
@app.route('/api/kite/profile')
def get_profile():
    """Get user profile information."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    result = kite_service.get_profile()
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/margins')
def get_margins():
    """Get account margins."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    result = kite_service.get_margins()
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/holdings')
def get_holdings():
    """Get current holdings."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    result = kite_service.get_holdings()
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/positions')
def get_positions():
    """Get current positions."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    result = kite_service.get_positions()
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/orders')
def get_orders():
    """Get all orders."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    result = kite_service.get_orders()
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

# Market data endpoints
@app.route('/api/kite/instruments')
def get_instruments():
    """Get instruments list."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    exchange = request.args.get('exchange')
    result = kite_service.get_instruments(exchange)
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/quote', methods=['POST'])
def get_quote():
    """Get quote for instruments."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    data = request.get_json()
    instruments = data.get('instruments', [])
    
    if not instruments:
        return jsonify({"error": "instruments list is required"}), 400
    
    result = kite_service.get_quote(instruments)
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/ohlc', methods=['POST'])
def get_ohlc():
    """Get OHLC data for instruments."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    data = request.get_json()
    instruments = data.get('instruments', [])
    
    if not instruments:
        return jsonify({"error": "instruments list is required"}), 400
    
    result = kite_service.get_ohlc(instruments)
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/ltp', methods=['POST'])
def get_ltp():
    """Get last traded price for instruments."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    data = request.get_json()
    instruments = data.get('instruments', [])
    
    if not instruments:
        return jsonify({"error": "instruments list is required"}), 400
    
    result = kite_service.get_ltp(instruments)
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

# Trading endpoints
@app.route('/api/kite/place-order', methods=['POST'])
def place_order():
    """Place an order."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    data = request.get_json()
    
    # Required fields
    required_fields = ['variety', 'exchange', 'tradingsymbol', 'transaction_type', 
                      'quantity', 'product', 'order_type']
    
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400
    
    result = kite_service.place_order(
        variety=data['variety'],
        exchange=data['exchange'],
        tradingsymbol=data['tradingsymbol'],
        transaction_type=data['transaction_type'],
        quantity=data['quantity'],
        product=data['product'],
        order_type=data['order_type'],
        price=data.get('price'),
        validity=data.get('validity', 'DAY'),
        disclosed_quantity=data.get('disclosed_quantity', 0),
        trigger_price=data.get('trigger_price'),
        squareoff=data.get('squareoff'),
        stoploss=data.get('stoploss'),
        trailing_stoploss=data.get('trailing_stoploss'),
        tag=data.get('tag')
    )
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/modify-order', methods=['POST'])
def modify_order():
    """Modify an existing order."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    data = request.get_json()
    
    if 'variety' not in data or 'order_id' not in data:
        return jsonify({"error": "variety and order_id are required"}), 400
    
    result = kite_service.modify_order(
        variety=data['variety'],
        order_id=data['order_id'],
        price=data.get('price'),
        quantity=data.get('quantity'),
        order_type=data.get('order_type'),
        validity=data.get('validity'),
        disclosed_quantity=data.get('disclosed_quantity'),
        trigger_price=data.get('trigger_price')
    )
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/cancel-order', methods=['POST'])
def cancel_order():
    """Cancel an order."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    data = request.get_json()
    
    if 'variety' not in data or 'order_id' not in data:
        return jsonify({"error": "variety and order_id are required"}), 400
    
    result = kite_service.cancel_order(
        variety=data['variety'],
        order_id=data['order_id']
    )
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/kite/order-history/<order_id>')
def get_order_history(order_id):
    """Get order history."""
    if not kite_service:
        return jsonify({"error": "Kite service not initialized"}), 500
    
    result = kite_service.get_order_history(order_id)
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

def main():
    """Main function to run the Flask application."""
    print("Starting Flask web service with Zerodha Kite integration...")
    print("Visit http://localhost:8080 to see the home page")
    print("API endpoints available at /api/kite/*")
    app.run(debug=True, host='0.0.0.0', port=8080)

if __name__ == "__main__":
    main()

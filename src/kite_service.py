#!/usr/bin/env python3
"""
Zerodha Kite API integration service.
"""

import os
import json
from typing import Dict, List, Optional, Any
from kiteconnect import KiteConnect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class KiteService:
    """Service class for Zerodha Kite API integration."""
    
    def __init__(self):
        """Initialize Kite service with API credentials."""
        self.api_key = os.getenv('KITE_API_KEY')
        self.api_secret = os.getenv('KITE_API_SECRET')
        self.access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not self.api_key:
            raise ValueError("KITE_API_KEY environment variable is required")
        if not self.api_secret:
            raise ValueError("KITE_API_SECRET environment variable is required")
            
        self.kite = KiteConnect(api_key=self.api_key)
        
        if self.access_token:
            self.kite.set_access_token(self.access_token)
    
    def get_login_url(self) -> str:
        """Get the login URL for Kite authentication."""
        # The redirect URL should be configured in your Kite app settings
        # This method returns the login URL that will redirect to the configured redirect URL
        return self.kite.login_url()
    
    def generate_session(self, request_token: str) -> Dict[str, Any]:
        """Generate access token from request token."""
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            print(f"Kite session data: {data}")  # Debug logging
            self.access_token = data['access_token']
            self.kite.set_access_token(self.access_token)
            return {
                'success': True,
                'access_token': data['access_token'],
                'user_id': data.get('user_id', ''),
                'user_name': data.get('user_name', ''),
                'user_email': data.get('user_email', ''),
                'user_shortname': data.get('user_shortname', ''),
                'broker': data.get('broker', '')
            }
        except Exception as e:
            print(f"Error in generate_session: {e}")  # Debug logging
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile information."""
        try:
            profile = self.kite.profile()
            return {
                'success': True,
                'profile': profile
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_margins(self) -> Dict[str, Any]:
        """Get account margins."""
        try:
            margins = self.kite.margins()
            return {
                'success': True,
                'margins': margins
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_holdings(self) -> Dict[str, Any]:
        """Get current holdings."""
        try:
            holdings = self.kite.holdings()
            return {
                'success': True,
                'holdings': holdings
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_positions(self) -> Dict[str, Any]:
        """Get current positions."""
        try:
            positions = self.kite.positions()
            return {
                'success': True,
                'positions': positions
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_orders(self) -> Dict[str, Any]:
        """Get all orders."""
        try:
            orders = self.kite.orders()
            return {
                'success': True,
                'orders': orders
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_instruments(self, exchange: Optional[str] = None) -> Dict[str, Any]:
        """Get instruments list."""
        try:
            instruments = self.kite.instruments(exchange)
            return {
                'success': True,
                'instruments': instruments
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """Get quote for instruments."""
        try:
            quotes = self.kite.quote(instruments)
            return {
                'success': True,
                'quotes': quotes
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_ohlc(self, instruments: List[str]) -> Dict[str, Any]:
        """Get OHLC data for instruments."""
        try:
            ohlc = self.kite.ohlc(instruments)
            return {
                'success': True,
                'ohlc': ohlc
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_ltp(self, instruments: List[str]) -> Dict[str, Any]:
        """Get last traded price for instruments."""
        try:
            ltp = self.kite.ltp(instruments)
            return {
                'success': True,
                'ltp': ltp
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def place_order(self, variety: str, exchange: str, tradingsymbol: str, 
                   transaction_type: str, quantity: int, product: str, 
                   order_type: str, price: Optional[float] = None, 
                   validity: str = "DAY", disclosed_quantity: int = 0, 
                   trigger_price: Optional[float] = None, squareoff: Optional[float] = None,
                   stoploss: Optional[float] = None, trailing_stoploss: Optional[float] = None,
                   tag: Optional[str] = None) -> Dict[str, Any]:
        """Place an order."""
        try:
            order_id = self.kite.place_order(
                variety=variety,
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                transaction_type=transaction_type,
                quantity=quantity,
                product=product,
                order_type=order_type,
                price=price,
                validity=validity,
                disclosed_quantity=disclosed_quantity,
                trigger_price=trigger_price,
                squareoff=squareoff,
                stoploss=stoploss,
                trailing_stoploss=trailing_stoploss,
                tag=tag
            )
            return {
                'success': True,
                'order_id': order_id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def modify_order(self, variety: str, order_id: str, 
                    price: Optional[float] = None, quantity: Optional[int] = None,
                    order_type: Optional[str] = None, validity: Optional[str] = None,
                    disclosed_quantity: Optional[int] = None, 
                    trigger_price: Optional[float] = None) -> Dict[str, Any]:
        """Modify an existing order."""
        try:
            order_id = self.kite.modify_order(
                variety=variety,
                order_id=order_id,
                price=price,
                quantity=quantity,
                order_type=order_type,
                validity=validity,
                disclosed_quantity=disclosed_quantity,
                trigger_price=trigger_price
            )
            return {
                'success': True,
                'order_id': order_id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_order(self, variety: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        try:
            order_id = self.kite.cancel_order(variety=variety, order_id=order_id)
            return {
                'success': True,
                'order_id': order_id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_order_history(self, order_id: str) -> Dict[str, Any]:
        """Get order history."""
        try:
            history = self.kite.order_history(order_id)
            return {
                'success': True,
                'history': history
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

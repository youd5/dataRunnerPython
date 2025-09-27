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
    
    # Class-level variables for caching instruments data
    _instruments_list = None
    _symbol_to_instrument_map = None
    _token_to_instrument_map = None
    
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
        """Get instruments list with caching and mapping functionality."""
        try:
            # Use cached data if available
            if KiteService._instruments_list is not None:
                return {
                    'success': True,
                    'instruments': KiteService._instruments_list,
                    'symbol_to_instrument_map': KiteService._symbol_to_instrument_map,
                    'token_to_instrument_map': KiteService._token_to_instrument_map
                }
            
            print('Fetching instruments from Kite API...')
            
            # Fetch fresh data from API
            instruments = self.kite.instruments(exchange or 'NSE')
            
            # Cache the data
            KiteService._instruments_list = instruments
            KiteService._symbol_to_instrument_map = {}
            KiteService._token_to_instrument_map = {}
            
            # Build mapping dictionaries
            for instrument in instruments:
                trading_symbol = instrument.get('tradingsymbol')
                instrument_token = instrument.get('instrument_token')
                
                if trading_symbol:
                    KiteService._symbol_to_instrument_map[trading_symbol] = instrument
                if instrument_token:
                    KiteService._token_to_instrument_map[instrument_token] = instrument
            
            print(f'Instruments fetched successfully. Count: {len(instruments)}')
            
            return {
                'success': True,
                'instruments': instruments,
                'symbol_to_instrument_map': KiteService._symbol_to_instrument_map,
                'token_to_instrument_map': KiteService._token_to_instrument_map
            }
        except Exception as e:
            print(f"Error while fetching instruments: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_instrument_token(self, symbol: str) -> Optional[int]:
        """Get instrument token for a given trading symbol."""
        try:
            # Ensure instruments are loaded
            if KiteService._symbol_to_instrument_map is None:
                self.get_instruments()
            
            instrument = KiteService._symbol_to_instrument_map.get(symbol)
            if instrument:
                return instrument.get('instrument_token')
            else:
                print(f"Instrument not found for symbol: {symbol}")
                return None
        except Exception as e:
            print(f"Error getting instrument token for {symbol}: {e}")
            return None
    
    def get_instrument_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get full instrument details for a given trading symbol."""
        try:
            # Ensure instruments are loaded
            if KiteService._symbol_to_instrument_map is None:
                self.get_instruments()
            
            return KiteService._symbol_to_instrument_map.get(symbol)
        except Exception as e:
            print(f"Error getting instrument details for {symbol}: {e}")
            return None
    
    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """Get quote for instruments. Converts symbols to instrument tokens if needed."""
        try:
            # Convert symbols to instrument tokens if they are not already tokens
            instrument_tokens = []
            symbol_to_token_map = {}
            
            for instrument in instruments:
                if instrument.isdigit():
                    # It's already an instrument token
                    instrument_tokens.append(instrument)
                else:
                    # It's a symbol, convert to token
                    token = self.get_instrument_token(instrument)
                    if token:
                        instrument_tokens.append(str(token))
                        symbol_to_token_map[str(token)] = instrument
                    else:
                        print(f"Warning: Could not find instrument token for symbol: {instrument}")
                        continue
            
            if not instrument_tokens:
                return {
                    'success': False,
                    'error': 'No valid instruments found'
                }
            
            # Fetch quotes using instrument tokens
            quotes = self.kite.quote(instrument_tokens)
            
            # Convert token keys back to symbols for easier access
            formatted_quotes = {}
            for token, quote_data in quotes.items():
                symbol = symbol_to_token_map.get(token, token)  # Use symbol if available, otherwise token
                formatted_quotes[symbol] = quote_data
            
            return {
                'success': True,
                'quotes': formatted_quotes,
                'instrument_tokens': instrument_tokens,
                'symbol_mapping': symbol_to_token_map
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
    
    def historical_data(self, instrument_token: int, from_date: str, to_date: str, 
                       interval: str, continuous: bool = False, oi: bool = False) -> Dict[str, Any]:
        """
        Fetch historical data for an instrument.
        
        Args:
            instrument_token (int): Instrument token (e.g., 738561 for NIFTY 50)
            from_date (str): From date (yyyy-mm-dd)
            to_date (str): To date (yyyy-mm-dd)
            interval (str): Data interval. Valid values:
                - "minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute"
                - "day"
            continuous (bool): If True, returns continuous contract data. Default: False
            oi (bool): If True, returns open interest data. Default: False
            
        Returns:
            Dict[str, Any]: Historical data response with success status and data
        """
        try:
            # Validate required parameters
            if not instrument_token:
                return {
                    'success': False,
                    'error': 'instrument_token is required'
                }
            
            if not from_date or not to_date:
                return {
                    'success': False,
                    'error': 'from_date and to_date are required'
                }
            
            if not interval:
                return {
                    'success': False,
                    'error': 'interval is required'
                }
            
            # Validate interval values
            valid_intervals = [
                "minute", "3minute", "5minute", "10minute", "15minute", 
                "30minute", "60minute", "day"
            ]
            if interval not in valid_intervals:
                return {
                    'success': False,
                    'error': f'Invalid interval. Valid values: {", ".join(valid_intervals)}'
                }
            
            # Fetch historical data from Kite API
            historical_data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
                continuous=continuous,
                oi=oi
            )
            
            return {
                'success': True,
                'data': historical_data,
                'instrument_token': instrument_token,
                'from_date': from_date,
                'to_date': to_date,
                'interval': interval,
                'continuous': continuous,
                'oi': oi,
                'count': len(historical_data) if historical_data else 0
            }
            
        except Exception as e:
            print(f"Error fetching historical data: {e}")
            return {
                'success': False,
                'error': str(e)
            }

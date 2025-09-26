# dataRunnerPython

A Flask web service with Zerodha Kite API integration for trading and market data access.

## Features

- 🏠 Beautiful home page with modern UI
- 🚀 RESTful API endpoints for trading operations
- 📈 Zerodha Kite API integration
- 💰 Account management (margins, holdings, positions)
- 📊 Market data access (quotes, OHLC, instruments)
- 🔐 Secure authentication with Kite Connect
- 📱 Responsive design that works on all devices

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Zerodha Kite API credentials:**
   ```bash
   # The .env file will be created automatically when you first run the app
   # Edit .env file with your Kite API credentials
   ```

3. **Run the service:**
   ```bash
   python src/main.py
   ```

4. **Open your browser and visit:**
   ```
   http://localhost:8080
   ```

## Zerodha Kite API Setup

### Getting API Credentials

1. Visit [Kite Connect](https://kite.trade/connect/login)
2. Create a new app or use existing credentials
3. Get your API key and API secret
4. Set up your `.env` file:

```env
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_here
KITE_MODE=paper
```

### Authentication Flow

1. **Get Login URL:**
   ```bash
   curl http://localhost:8080/api/kite/login-url
   ```

2. **Login and get request token:**
   - Visit the login URL in your browser
   - Complete the login process
   - Extract the `request_token` from the redirect URL

3. **Automatic callback handling:**
   - The login URL automatically redirects to `/apis/broker/login/zerodha` after successful login
   - The callback route extracts the `request_token` from the URL
   - Generates the access token and saves it to your `.env` file
   - Shows a success page with your access token and user information

### Manual Token Generation (Alternative)

If you prefer to handle the token manually:

1. **Get Login URL:**
   ```bash
   curl http://localhost:8080/api/kite/login-url
   ```

2. **Login and get request token:**
   - Visit the login URL in your browser
   - Complete the login process
   - Extract the `request_token` from the redirect URL

3. **Generate session:**
   ```bash
   curl -X POST http://localhost:8080/api/kite/session \
     -H "Content-Type: application/json" \
     -d '{"request_token": "your_request_token_here"}'
   ```

## API Endpoints

### Authentication
- `GET /api/kite/login-url` - Get Kite login URL
- `GET /apis/broker/login/zerodha` - Handle redirect from Zerodha after login
- `POST /api/kite/session` - Generate access token from request token

### Account Information
- `GET /api/kite/profile` - Get user profile
- `GET /api/kite/margins` - Get account margins
- `GET /api/kite/holdings` - Get current holdings
- `GET /api/kite/positions` - Get current positions
- `GET /api/kite/orders` - Get all orders

### Market Data
- `GET /api/kite/instruments?exchange=NSE` - Get instruments list
- `POST /api/kite/quote` - Get quotes for instruments
- `POST /api/kite/ohlc` - Get OHLC data for instruments
- `POST /api/kite/ltp` - Get last traded price for instruments

### Trading
- `POST /api/kite/place-order` - Place a new order
- `POST /api/kite/modify-order` - Modify an existing order
- `POST /api/kite/cancel-order` - Cancel an order
- `GET /api/kite/order-history/<order_id>` - Get order history

### Example API Usage

#### Get Market Quote
```bash
curl -X POST http://localhost:8080/api/kite/quote \
  -H "Content-Type: application/json" \
  -d '{"instruments": ["NSE:RELIANCE", "NSE:TCS"]}'
```

#### Place a Buy Order
```bash
curl -X POST http://localhost:8080/api/kite/place-order \
  -H "Content-Type: application/json" \
  -d '{
    "variety": "regular",
    "exchange": "NSE",
    "tradingsymbol": "RELIANCE",
    "transaction_type": "BUY",
    "quantity": 1,
    "product": "CNC",
    "order_type": "MARKET"
  }'
```

#### Get Account Holdings
```bash
curl http://localhost:8080/api/kite/holdings
```

## Project Structure

```
dataRunnerPython/
├── src/
│   ├── main.py              # Flask application with Kite integration
│   ├── kite_service.py      # Kite API service class
│   └── templates/
│       ├── index.html       # Home page template
│       ├── callback_success.html  # Success page after login
│       └── callback_error.html   # Error page after login
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (created automatically)
└── README.md               # This file
```

## Dependencies

- **Flask** - Web framework
- **kiteconnect** - Zerodha Kite API client
- **python-dotenv** - Environment variable management

## Development

### Adding Dependencies

Add new dependencies to `requirements.txt`:
```bash
pip freeze > requirements.txt
```

### Running Tests

```bash
# Add your test commands here
python -m pytest tests/
```

### Environment Variables

The `.env` file will be created automatically when you first run the application. Required environment variables:
- `KITE_API_KEY` - Your Kite Connect API key
- `KITE_API_SECRET` - Your Kite Connect API secret
- `KITE_ACCESS_TOKEN` - Access token (generated after login)
- `KITE_REDIRECT_URL` - Redirect URL after login (default: `http://localhost:8080/apis/broker/login/zerodha`)

## Security Notes

- Never commit your `.env` file to version control
- Keep your API credentials secure
- Use paper trading mode for testing
- Implement proper error handling in production

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

Add your license information here.

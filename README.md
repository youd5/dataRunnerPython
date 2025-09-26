# dataRunnerPython

A simple Flask web service with a beautiful home page and API endpoint.

## Features

- 🏠 Beautiful home page with modern UI
- 🚀 Call-to-action button to trigger API
- 🔗 RESTful API endpoint that returns "hello world"
- 📱 Responsive design that works on all devices

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the service:
   ```bash
   python src/main.py
   ```

3. Open your browser and visit:
   ```
   http://localhost:8080
   ```

## API Endpoints

- `GET /` - Home page with CTA button
- `GET /api/hello` - Returns JSON: `{"message": "hello world"}`

## Project Structure

```
dataRunnerPython/
├── src/
│   ├── main.py              # Flask application
│   └── templates/
│       └── index.html       # Home page template
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

Add your license information here.

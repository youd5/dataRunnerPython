#!/usr/bin/env python3
"""
Main entry point for the Python web service.
"""

from flask import Flask, render_template, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    """Render the home page with CTA button."""
    return render_template('index.html')

@app.route('/api/hello')
def hello_api():
    """API endpoint that returns hello world."""
    return jsonify({"message": "hello world"})

def main():
    """Main function to run the Flask application."""
    print("Starting Flask web service...")
    print("Visit http://localhost:8080 to see the home page")
    app.run(debug=True, host='0.0.0.0', port=8080)

if __name__ == "__main__":
    main()

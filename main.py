import os

from flask import Flask
from flask_cors import CORS
import logging

from routes.stocks import (
    stocks_bp
)

app = Flask(__name__, static_url_path='', static_folder='.')

CORS(app)

app.register_blueprint(
    stocks_bp
)


def initialize_logging():
    """Initialize structured JSON logging for the Flask app."""
    from logger_config import setup_logging
    setup_logging()


@app.route("/")
def index():
    return app.send_static_file('index.html')


if __name__ == "__main__":
    initialize_logging()
    
    # Render injects PORT as an env var; default to 5000 for local dev.
    # host="0.0.0.0" binds to all interfaces — required by Render
    # (localhost-only binding causes the port scan timeout error).
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )

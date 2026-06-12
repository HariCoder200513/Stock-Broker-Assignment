from flask import Flask
from flask_cors import CORS
import logging

from routes.stocks import (
    stocks_bp
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = Flask(__name__, static_url_path='', static_folder='.')

CORS(app)

app.register_blueprint(
    stocks_bp
)


@app.route("/")
def index():
    return app.send_static_file('index.html')


if __name__ == "__main__":

    app.run(
        debug=True
    )

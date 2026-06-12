from flask import Flask
from flask_cors import CORS

from routes.stocks import (
    stocks_bp
)

app = Flask(__name__)

CORS(app)

app.register_blueprint(
    stocks_bp
)


@app.route("/")
def health():

    return {
        "status": "healthy"
    }


if __name__ == "__main__":

    app.run(
        debug=True
    )
"""
Flask blueprint for the /stocks REST endpoint.

This is a thin HTTP adapter — all business logic lives in the
``orchestrator.pipeline`` module.  The route's only job is to:
  1. Trigger an ingestion run.
  2. Serialize the result as JSON.
"""

import logging

from flask import Blueprint, jsonify

from orchestrator.pipeline import run_ingestion

stocks_bp = Blueprint("stocks", __name__)
logger = logging.getLogger(__name__)


@stocks_bp.route("/stocks")
def get_stocks():
    """
    GET /stocks

    Triggers a fresh ingestion run — fetches market data for every ticker
    in the watchlist, validates, persists to SQLite, and returns the full
    result set (including per-ticker success/failure status).
    """
    result = run_ingestion()

    return jsonify(result)

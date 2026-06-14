"""
Centralized constants for the market-data ingestion pipeline.

These magic strings are used across the orchestrator and routes to ensure
consistency and make them easier to find/change in the future.
"""

# Status values returned in the ingestion pipeline result
STATUS_SUCCESS = "success"
STATUS_VALIDATION_FAILED = "validation_failed"
STATUS_FETCH_FAILED = "fetch_failed"
STATUS_SKIPPED = "skipped"

# All possible status values
ALL_STATUSES = {STATUS_SUCCESS, STATUS_VALIDATION_FAILED, STATUS_FETCH_FAILED, STATUS_SKIPPED}

# Result keys
KEY_TICKER = "ticker"
KEY_STATUS = "status"
KEY_NAME = "name"
KEY_SECTOR = "sector"
KEY_MARKET_CAP = "market_cap"
KEY_RETRIES = "retries"
KEY_MESSAGE = "message"

def validate_stock(record: dict) -> bool:

    if record is None:
        return False

    required_fields = [
        "ticker",
        "name",
        "sector",
        "market_cap"
    ]

    for field in required_fields:

        if record.get(field) is None:
            return False

    if not isinstance(
        record["market_cap"],
        int
    ):
        return False

    return True
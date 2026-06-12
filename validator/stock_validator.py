REQUIRED_FIELDS = [
    "ticker",
    "name",
    "sector",
    "market_cap"
]


def validation_errors(record: dict) -> list[str]:
    errors = []

    if record is None:
        return ["Record is missing."]

    for field in REQUIRED_FIELDS:

        if record.get(field) in (None, ""):
            errors.append(
                f"{field} is required."
            )

    if not isinstance(
        record.get("market_cap"),
        int
    ):
        errors.append(
            "market_cap must be an integer."
        )
    elif record["market_cap"] <= 0:
        errors.append(
            "market_cap must be positive."
        )

    return errors


def validate_stock(record: dict) -> bool:
    return len(validation_errors(record)) == 0

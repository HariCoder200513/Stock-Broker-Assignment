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

        value = record.get(field)

        if value is None:
            errors.append(
                f"{field} is required."
            )
            continue

        if isinstance(value, str) and not value.strip():
            errors.append(
                f"{field} is required."
            )

    market_cap = record.get("market_cap")
    
    if market_cap is None:
        errors.append("market_cap is required.")
    else:
        try:
            val = float(market_cap)
            if val <= 0:
                errors.append("market_cap must be positive.")
            elif not val.is_integer() if isinstance(val, float) else False:
                # Optional: decide if we want to allow non-integer market caps
                # and just floor them. For now, let's keep it strict-ish but allow float whole numbers.
                pass 
        except (ValueError, TypeError):
            errors.append("market_cap must be a numeric value.")

    return errors


def validate_stock(record: dict) -> bool:
    return len(validation_errors(record)) == 0

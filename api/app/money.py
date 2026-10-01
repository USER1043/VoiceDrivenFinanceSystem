"""Money is integer paise everywhere. These helpers are the only place rupees appear."""

MAX_AMOUNT_PAISE = 100_000_000_00  # ₹10 crore: rejects typos like an extra few zeros


def format_rupees(paise: int) -> str:
    """12345 -> "123.45" (no currency symbol, no grouping; for CSV and logs)."""
    sign = "-" if paise < 0 else ""
    rupees, rem = divmod(abs(paise), 100)
    return f"{sign}{rupees}.{rem:02d}"

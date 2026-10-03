"""Money is integer paise everywhere. These helpers are the only place rupees appear."""

MAX_AMOUNT_PAISE = 100_000_000_00  # ₹10 crore: rejects typos like an extra few zeros


def format_rupees(paise: int) -> str:
    """12345 -> "123.45" (no currency symbol, no grouping; for CSV and logs)."""
    sign = "-" if paise < 0 else ""
    rupees, rem = divmod(abs(paise), 100)
    return f"{sign}{rupees}.{rem:02d}"


def format_inr(paise: int) -> str:
    """12345650 -> "₹1,23,456.50", 18000 -> "₹180": Indian digit grouping, for speech/UI text."""
    rupees, rem = divmod(abs(paise), 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join([head, *groups, tail]) if head else ",".join([*groups, tail])
    sign = "-" if paise < 0 else ""
    return f"{sign}₹{digits}" + (f".{rem:02d}" if rem else "")


def percent(part: int, whole: int) -> int:
    """Whole percent, rounded half up (the same as the app's Math.round)."""
    return (part * 200 + whole) // (whole * 2)

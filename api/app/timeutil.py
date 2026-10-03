import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
_MONTH_RE = re.compile(MONTH_PATTERN)
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December",
]  # fmt: skip


def current_month(tz: str) -> str:
    return datetime.now(ZoneInfo(tz)).strftime("%Y-%m")


def month_start(month: str) -> date:
    if not _MONTH_RE.match(month):
        raise ValueError(f"Invalid month {month!r}; expected YYYY-MM")
    year, mon = (int(part) for part in month.split("-"))
    return date(year, mon, 1)


def add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def month_bounds(month: str, tz: str) -> tuple[datetime, datetime]:
    """[start, end) of a calendar month in the user's timezone, as aware datetimes."""
    zone = ZoneInfo(tz)
    first = month_start(month)
    nxt = add_months(first, 1)
    return (
        datetime(first.year, first.month, 1, tzinfo=zone),
        datetime(nxt.year, nxt.month, 1, tzinfo=zone),
    )


def days_in_month(month: str) -> int:
    first = month_start(month)
    return (add_months(first, 1) - first).days


def previous_month(month: str) -> str:
    return (month_start(month) - timedelta(days=1)).strftime("%Y-%m")

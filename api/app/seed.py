"""Idempotent seed for the single owner: user, default accounts and categories.

Run with `python -m app.seed`. Safe to run on every deploy; it only inserts what is missing
and never overwrites edits made in the app.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import Account, AccountKind, Category, CategoryKind, User

DEFAULT_ACCOUNTS: list[tuple[str, AccountKind, bool]] = [
    ("UPI", AccountKind.UPI, True),
    ("Cash", AccountKind.CASH, False),
    ("Card", AccountKind.CARD, False),
]

# (name, aliases, children as (name, aliases))
Tree = list[tuple[str, list[str], list[tuple[str, list[str]]]]]

DEFAULT_EXPENSE_CATEGORIES: Tree = [
    (
        "Food",
        ["food", "eating"],
        [
            (
                "Groceries",
                [
                    "groceries",
                    "kirana",
                    "vegetables",
                    "sabzi",
                    "blinkit",
                    "zepto",
                    "bigbasket",
                    "dmart",
                ],
            ),
            (
                "Eating out",
                [
                    "restaurant",
                    "lunch",
                    "dinner",
                    "breakfast",
                    "zomato",
                    "swiggy",
                    "pizza",
                    "burger",
                    "biryani",
                    "dominos",
                    "mcdonalds",
                    "kfc",
                ],
            ),
            ("Tea & snacks", ["chai", "tea", "coffee", "snacks", "biscuits", "juice", "samosa"]),
        ],
    ),
    (
        "Transport",
        ["transport", "travel", "parking", "toll"],
        [
            ("Auto & cab", ["auto", "rickshaw", "cab", "uber", "ola", "rapido"]),
            ("Fuel", ["fuel", "petrol", "diesel"]),
            ("Public transport", ["metro", "metro card", "bus", "train"]),
        ],
    ),
    (
        "Home",
        ["home"],
        [
            ("Rent", ["rent"]),
            ("Electricity", ["electricity", "current bill", "eb bill"]),
            (
                "Mobile & internet",
                ["recharge", "mobile", "phone bill", "internet", "wifi", "broadband"],
            ),
        ],
    ),
    ("Shopping", ["shopping", "amazon", "flipkart", "myntra"], []),
    ("Health", ["health", "medicine", "medicines", "pharmacy", "doctor", "hospital", "gym"], []),
    ("Entertainment", ["movie", "movies", "entertainment"], []),
    ("Subscriptions", ["subscription", "netflix", "spotify", "prime", "hotstar"], []),
    ("Education", ["education", "course", "books", "fees"], []),
    ("Personal care", ["haircut", "salon", "grooming"], []),
    ("Gifts & donations", ["gift", "donation"], []),
    ("Other", ["other", "misc"], []),
]

DEFAULT_INCOME_CATEGORIES: Tree = [
    ("Salary", ["salary", "stipend"], []),
    ("Refunds & cashback", ["refund", "cashback"], []),
    ("Other income", ["income"], []),
]


def _get_or_create_category(
    session: Session,
    user: User,
    kind: CategoryKind,
    name: str,
    aliases: list[str],
    parent: Category | None,
) -> Category:
    existing = session.scalar(
        select(Category).where(
            Category.user_id == user.id,
            Category.kind == kind,
            Category.name == name,
            Category.parent_id.is_(None) if parent is None else Category.parent_id == parent.id,
        )
    )
    if existing:
        return existing
    category = Category(
        user_id=user.id,
        kind=kind,
        name=name,
        aliases=aliases,
        parent_id=parent.id if parent else None,
    )
    session.add(category)
    session.flush()
    return category


def add_defaults(session: Session, user: User) -> None:
    """Give a user the starter accounts and categories. Never overwrites their edits."""
    existing_accounts = set(session.scalars(select(Account.name).where(Account.user_id == user.id)))
    for name, account_kind, is_default in DEFAULT_ACCOUNTS:
        if name not in existing_accounts:
            session.add(
                Account(user_id=user.id, name=name, kind=account_kind, is_default=is_default)
            )

    for kind, tree in (
        (CategoryKind.EXPENSE, DEFAULT_EXPENSE_CATEGORIES),
        (CategoryKind.INCOME, DEFAULT_INCOME_CATEGORIES),
    ):
        for name, aliases, children in tree:
            parent = _get_or_create_category(session, user, kind, name, aliases, None)
            for child_name, child_aliases in children:
                _get_or_create_category(session, user, kind, child_name, child_aliases, parent)
    session.flush()


def seed(session: Session, admin_email: str, timezone: str, password_hash: str = "") -> User:
    """Make sure the admin exists, is an admin, and has the defaults.

    `password_hash` (OWNER_PASSWORD_HASH) is only used when the admin has no password yet,
    so passwords changed in the app are never reset by a redeploy.
    """
    email = admin_email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, timezone=timezone)
        session.add(user)
    user.is_admin = True
    user.disabled = False
    if password_hash and not user.password_hash:
        user.password_hash = password_hash
    session.flush()
    add_defaults(session, user)
    return user


def main() -> None:
    settings = get_settings()
    with get_sessionmaker()() as session:
        seed(session, settings.admin_email, settings.timezone, settings.owner_password_hash)
        session.commit()
    print(f"Admin ready: {settings.admin_email}")


if __name__ == "__main__":
    main()

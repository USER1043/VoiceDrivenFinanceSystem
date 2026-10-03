"""What the parsers may refer to: the owner's categories (with aliases) and accounts.

Only names and aliases are ever sent to an LLM, never amounts, balances or history.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountKind, Category, CategoryKind, User


@dataclass(frozen=True)
class VocabCategory:
    id: int
    name: str
    kind: CategoryKind
    parent: str | None = None
    aliases: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return f"{self.parent} > {self.name}" if self.parent else self.name


@dataclass(frozen=True)
class VocabAccount:
    id: int
    name: str
    kind: AccountKind
    is_default: bool = False


@dataclass(frozen=True)
class Vocabulary:
    categories: tuple[VocabCategory, ...]
    accounts: tuple[VocabAccount, ...]
    _by_id: dict[int, VocabCategory] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        self._by_id.update({c.id: c for c in self.categories})

    def category(self, category_id: int) -> VocabCategory | None:
        return self._by_id.get(category_id)

    def of_kind(self, kind: CategoryKind) -> list[VocabCategory]:
        return [c for c in self.categories if c.kind == kind]

    @property
    def default_account(self) -> VocabAccount:
        return next((a for a in self.accounts if a.is_default), self.accounts[0])

    @classmethod
    def load(cls, session: Session, user: User) -> "Vocabulary":
        rows = session.scalars(
            select(Category).where(Category.user_id == user.id, Category.archived.is_(False))
        ).all()
        names = {c.id: c.name for c in rows}
        categories = tuple(
            VocabCategory(
                id=c.id,
                name=c.name,
                kind=c.kind,
                parent=names.get(c.parent_id) if c.parent_id else None,
                aliases=tuple(c.aliases),
            )
            for c in rows
        )
        accounts = tuple(
            VocabAccount(id=a.id, name=a.name, kind=a.kind, is_default=a.is_default)
            for a in session.scalars(
                select(Account)
                .where(Account.user_id == user.id, Account.archived.is_(False))
                .order_by(Account.id)
            )
        )
        return cls(categories=categories, accounts=accounts)

    @classmethod
    def from_seed(cls) -> "Vocabulary":
        """The default categories and accounts with stand-in ids; used by the eval set."""
        from app.seed import DEFAULT_ACCOUNTS, DEFAULT_EXPENSE_CATEGORIES, DEFAULT_INCOME_CATEGORIES

        categories: list[VocabCategory] = []
        for kind, tree in (
            (CategoryKind.EXPENSE, DEFAULT_EXPENSE_CATEGORIES),
            (CategoryKind.INCOME, DEFAULT_INCOME_CATEGORIES),
        ):
            for name, aliases, children in tree:
                categories.append(
                    VocabCategory(len(categories) + 1, name, kind, None, tuple(aliases))
                )
                for child, child_aliases in children:
                    categories.append(
                        VocabCategory(len(categories) + 1, child, kind, name, tuple(child_aliases))
                    )
        accounts = tuple(
            VocabAccount(i + 1, name, kind, is_default)
            for i, (name, kind, is_default) in enumerate(DEFAULT_ACCOUNTS)
        )
        return cls(categories=tuple(categories), accounts=accounts)

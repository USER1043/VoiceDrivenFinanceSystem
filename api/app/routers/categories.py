from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import CurrentUser
from app.db import get_session
from app.errors import Conflict, Invalid, get_owned
from app.models import Category, CategoryKind, User
from app.schemas import CategoryIn, CategoryOut, CategoryPatch

router = APIRouter(prefix="/categories", tags=["categories"])
DB = Annotated[Session, Depends(get_session)]


def _check_parent(
    session: Session, user: User, kind: CategoryKind, parent_id: int, child: Category | None
) -> None:
    parent = get_owned(session, Category, parent_id, user.id)
    if child is not None and parent.id == child.id:
        raise Invalid("A category can't be its own parent")
    if parent.kind != kind:
        raise Invalid("Parent must be the same kind (expense/income)")
    if parent.parent_id is not None:
        raise Invalid("Categories can only be nested one level deep")
    if parent.archived:
        raise Invalid(f"Parent '{parent.name}' is archived")
    if child is not None and session.scalar(
        select(Category.id).where(Category.parent_id == child.id).limit(1)
    ):
        raise Invalid(f"'{child.name}' has subcategories, so it can't be nested")


def _check_aliases(
    session: Session, user: User, kind: CategoryKind, aliases: list[str], self_id: int | None
) -> None:
    """An alias must point at one category, or voice entry couldn't tell them apart."""
    if not aliases:
        return
    others = session.scalars(
        select(Category).where(
            Category.user_id == user.id,
            Category.kind == kind,
            Category.archived.is_(False),
            Category.aliases.overlap(aliases),
        )
    )
    for other in others:
        if other.id != self_id:
            taken = sorted(set(aliases) & set(other.aliases))
            raise Conflict(f"Alias {', '.join(taken)} already used by '{other.name}'")


@router.get("", response_model=list[CategoryOut])
def list_categories(user: CurrentUser, session: DB) -> list[Category]:
    return list(
        session.scalars(
            select(Category)
            .where(Category.user_id == user.id)
            .order_by(Category.kind, Category.name)
        )
    )


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, user: CurrentUser, session: DB) -> Category:
    if body.parent_id is not None:
        _check_parent(session, user, body.kind, body.parent_id, None)
    _check_aliases(session, user, body.kind, body.aliases, None)
    category = Category(user_id=user.id, **body.model_dump())
    session.add(category)
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action="create",
        entity="category",
        entity_id=category.id,
        after=audit.snapshot(category),
    )
    session.commit()
    return category


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, body: CategoryPatch, user: CurrentUser, session: DB
) -> Category:
    category = get_owned(session, Category, category_id, user.id)
    before = audit.snapshot(category)
    changes = body.model_dump(exclude_unset=True)
    for required in ("name", "aliases", "archived"):
        if required in changes and changes[required] is None:
            raise Invalid(f"{required} cannot be null")

    if changes.get("parent_id") is not None:
        _check_parent(session, user, category.kind, changes["parent_id"], category)
    if "aliases" in changes:
        _check_aliases(session, user, category.kind, changes["aliases"], category.id)

    archived = changes.get("archived")
    if archived is False and category.parent_id is not None and "parent_id" not in changes:
        parent = session.get(Category, category.parent_id)
        if parent is not None and parent.archived:
            raise Invalid(f"Restore the parent '{parent.name}' first")
    if archived is False:
        _check_aliases(session, user, category.kind, category.aliases, category.id)
    if archived:
        # Archiving a group archives everything in it.
        for child in session.scalars(select(Category).where(Category.parent_id == category.id)):
            child.archived = True

    for field, value in changes.items():
        setattr(category, field, value)
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action="update",
        entity="category",
        entity_id=category.id,
        before=before,
        after=audit.snapshot(category),
    )
    session.commit()
    return category

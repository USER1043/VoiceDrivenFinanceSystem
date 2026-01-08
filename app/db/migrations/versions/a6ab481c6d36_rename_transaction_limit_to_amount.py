"""rename transaction limit to amount

Revision ID: a6ab481c6d36
Revises: 10d6a0ff160f
Create Date: 2026-01-08 22:37:50.688996

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6ab481c6d36'
down_revision: Union[str, None] = '10d6a0ff160f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

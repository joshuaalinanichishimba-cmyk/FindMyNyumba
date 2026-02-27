"""Initial migration

Revision ID: 5ea6dac73d85
Revises: fdd26e787d74
Create Date: 2026-02-27 00:20:01.389988

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ea6dac73d85'
down_revision: Union[str, Sequence[str], None] = 'fdd26e787d74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

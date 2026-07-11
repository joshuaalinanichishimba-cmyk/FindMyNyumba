"""add momo fields to transactions (verified access payments)

Revision ID: 20260629_txn_momo
Revises: 20260628_search_logs
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260629_txn_momo"
down_revision = "20260628_search_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("transactions", sa.Column("momo_ref_id", sa.String(), nullable=True))
    op.add_column("transactions", sa.Column("idempotency_key", sa.String(), nullable=True))
    op.create_index("ix_transactions_momo_ref_id", "transactions", ["momo_ref_id"], unique=True)
    op.create_index("ix_transactions_idempotency_key", "transactions", ["idempotency_key"], unique=True)


def downgrade():
    op.drop_index("ix_transactions_idempotency_key", table_name="transactions")
    op.drop_index("ix_transactions_momo_ref_id", table_name="transactions")
    op.drop_column("transactions", "idempotency_key")
    op.drop_column("transactions", "momo_ref_id")

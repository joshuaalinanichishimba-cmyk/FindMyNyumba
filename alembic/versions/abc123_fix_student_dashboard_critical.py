"""
Alembic migration - PHASE 1 CRITICAL FIXES

Migration ID: fix_student_dashboard_critical
Date: 2025-05-21

CHANGES:
1. Rename SavedProperty.property_id → listing_id
2. Add Message attachment fields
3. Add Message read status tracking
4. Add unique constraint on SavedProperty
5. Fix Review FK (property_id → listing_id)
6. Add indexing for performance

RUN:
  alembic upgrade head
ROLLBACK:
  alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = 'abc123def456'
down_revision = 'previous_revision_id'  # Get this from previous migration
branch_labels = None
depends_on = None


def upgrade():
    \"\"\"Apply Phase 1 fixes\"\"\"
    
    # 1. SavedProperty: Rename column property_id → listing_id
    op.alter_column(
        'saved_properties',
        'property_id',
        new_column_name='listing_id',
        existing_type=sa.Integer(),
        existing_nullable=False
    )
    
    # 2. Message: Add attachment fields
    op.add_column(
        'messages',
        sa.Column('attachment_url', sa.String(), nullable=True)
    )
    op.add_column(
        'messages',
        sa.Column('attachment_type', sa.String(), nullable=True)
    )
    op.add_column(
        'messages',
        sa.Column('attachment_name', sa.String(), nullable=True)
    )
    
    # 3. Message: Add read status
    op.add_column(
        'messages',
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # 4. Create index on is_read for unread count queries
    op.create_index(
        'ix_messages_is_read',
        'messages',
        ['is_read']
    )
    
    # 5. Add unique constraint on SavedProperty
    op.create_unique_constraint(
        'uq_user_listing',
        'saved_properties',
        ['user_id', 'listing_id']
    )
    
    # 6. Review: Fix FK (property_id → listing_id)
    op.drop_constraint(
        'reviews_property_id_fkey',
        'reviews',
        type_='foreignkey'
    )
    op.alter_column(
        'reviews',
        'property_id',
        new_column_name='listing_id',
        existing_type=sa.Integer()
    )
    op.create_foreign_key(
        'reviews_listing_id_fkey',
        'reviews',
        'listings',
        ['listing_id'],
        ['id']
    )


def downgrade():
    \"\"\"Rollback Phase 1 fixes\"\"\"
    
    # 1. Review: Revert FK
    op.drop_constraint(
        'reviews_listing_id_fkey',
        'reviews',
        type_='foreignkey'
    )
    op.alter_column(
        'reviews',
        'listing_id',
        new_column_name='property_id',
        existing_type=sa.Integer()
    )
    op.create_foreign_key(
        'reviews_property_id_fkey',
        'reviews',
        'properties',
        ['property_id'],
        ['id']
    )
    
    # 2. SavedProperty: Remove unique constraint
    op.drop_constraint(
        'uq_user_listing',
        'saved_properties',
        type_='unique'
    )
    
    # 3. Message: Remove index
    op.drop_index('ix_messages_is_read', 'messages')
    
    # 4. Message: Remove read status
    op.drop_column('messages', 'is_read')
    
    # 5. Message: Remove attachment fields
    op.drop_column('messages', 'attachment_name')
    op.drop_column('messages', 'attachment_type')
    op.drop_column('messages', 'attachment_url')
    
    # 6. SavedProperty: Revert column name
    op.alter_column(
        'saved_properties',
        'listing_id',
        new_column_name='property_id',
        existing_type=sa.Integer(),
        existing_nullable=False
    )

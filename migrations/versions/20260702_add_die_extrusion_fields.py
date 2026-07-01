"""Add extrusion-specific fields to dies table

Revision ID: 20260702_die_ext
Revises: 20260707_mrm
Create Date: 2026-07-02

Adds extrusion die management columns that were added to the Die model but
not included in the original migration:
- description, die_type, manufacturer, manufactured_date
- press_count, press_count_limit, repair_count, nitriding_count
- last_used_at, last_repaired_at, updated_at
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260702_die_ext'
down_revision = '20260707_mrm'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to dies table
    op.add_column('dies', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('dies', sa.Column('die_type', sa.String(length=64), nullable=True))
    op.add_column('dies', sa.Column('manufacturer', sa.String(length=128), nullable=True))
    op.add_column('dies', sa.Column('manufactured_date', sa.Date(), nullable=True))
    op.add_column('dies', sa.Column('press_count', sa.Integer(), nullable=True))
    op.add_column('dies', sa.Column('press_count_limit', sa.Integer(), nullable=True))
    op.add_column('dies', sa.Column('repair_count', sa.Integer(), nullable=True))
    op.add_column('dies', sa.Column('nitriding_count', sa.Integer(), nullable=True))
    op.add_column('dies', sa.Column('last_used_at', sa.DateTime(), nullable=True))
    op.add_column('dies', sa.Column('last_repaired_at', sa.DateTime(), nullable=True))
    op.add_column('dies', sa.Column('updated_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('dies', 'updated_at')
    op.drop_column('dies', 'last_repaired_at')
    op.drop_column('dies', 'last_used_at')
    op.drop_column('dies', 'nitriding_count')
    op.drop_column('dies', 'repair_count')
    op.drop_column('dies', 'press_count_limit')
    op.drop_column('dies', 'press_count')
    op.drop_column('dies', 'manufactured_date')
    op.drop_column('dies', 'manufacturer')
    op.drop_column('dies', 'die_type')
    op.drop_column('dies', 'description')

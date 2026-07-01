"""Add scheduled_start and scheduled_end to work_orders

Revision ID: 7a42c1b9e2d5
Revises: 322b85370ef9
Create Date: 2026-06-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a42c1b9e2d5'
down_revision = '322b85370ef9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('work_orders', sa.Column('scheduled_start', sa.DateTime(), nullable=True))
    op.add_column('work_orders', sa.Column('scheduled_end',   sa.DateTime(), nullable=True))
    # Back-fill new columns from the latest ProductionSchedule row per WO, if any.
    # This keeps the existing planner's data visible on the Gantt immediately after upgrade.
    op.execute(
        "UPDATE work_orders wo "
        "SET scheduled_start = (SELECT ps.scheduled_start FROM production_schedule ps "
        "                        WHERE ps.wo_id = wo.id ORDER BY ps.scheduled_start ASC LIMIT 1), "
        "    scheduled_end   = (SELECT ps.scheduled_end   FROM production_schedule ps "
        "                        WHERE ps.wo_id = wo.id ORDER BY ps.scheduled_start ASC LIMIT 1) "
        "WHERE wo.scheduled_start IS NULL "
        "  AND EXISTS (SELECT 1 FROM production_schedule ps WHERE ps.wo_id = wo.id)"
    )


def downgrade():
    op.drop_column('work_orders', 'scheduled_end')
    op.drop_column('work_orders', 'scheduled_start')

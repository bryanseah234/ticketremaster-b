"""create ticket logs table

Revision ID: cf27f6a6ac6c
Revises:
Create Date: 2026-03-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf27f6a6ac6c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ticket_logs',
        sa.Column('logId', sa.String(length=36), nullable=False),
        sa.Column('ticketId', sa.String(length=36), nullable=False),
        sa.Column('staffId', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('logId'),
    )
    op.create_index(op.f('ix_ticket_logs_ticketId'), 'ticket_logs', ['ticketId'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_ticket_logs_ticketId'), table_name='ticket_logs')
    op.drop_table('ticket_logs')

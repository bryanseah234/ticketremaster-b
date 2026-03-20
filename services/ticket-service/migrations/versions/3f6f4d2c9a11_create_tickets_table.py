"""create tickets table

Revision ID: 3f6f4d2c9a11
Revises:
Create Date: 2026-03-20 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f6f4d2c9a11'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tickets',
        sa.Column('ticketId', sa.String(length=36), nullable=False),
        sa.Column('inventoryId', sa.String(length=36), nullable=False),
        sa.Column('ownerId', sa.String(length=36), nullable=False),
        sa.Column('venueId', sa.String(length=36), nullable=False),
        sa.Column('eventId', sa.String(length=36), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('qrHash', sa.String(length=64), nullable=True),
        sa.Column('qrTimestamp', sa.DateTime(), nullable=True),
        sa.Column('createdAt', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('ticketId'),
    )
    op.create_index('ix_tickets_ownerId', 'tickets', ['ownerId'], unique=False)
    op.create_index('ix_tickets_qrHash', 'tickets', ['qrHash'], unique=True)


def downgrade():
    op.drop_index('ix_tickets_qrHash', table_name='tickets')
    op.drop_index('ix_tickets_ownerId', table_name='tickets')
    op.drop_table('tickets')

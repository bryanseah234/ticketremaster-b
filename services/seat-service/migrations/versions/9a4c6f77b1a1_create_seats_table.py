"""create seats table

Revision ID: 9a4c6f77b1a1
Revises:
Create Date: 2026-03-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a4c6f77b1a1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'seats',
        sa.Column('seatId', sa.String(length=36), nullable=False),
        sa.Column('venueId', sa.String(length=36), nullable=False),
        sa.Column('seatNumber', sa.String(length=10), nullable=False),
        sa.Column('rowNumber', sa.String(length=5), nullable=False),
        sa.Column('createdAt', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('seatId'),
        sa.UniqueConstraint('venueId', 'seatNumber', name='uq_seats_venue_seat_number'),
    )
    op.create_index(op.f('ix_seats_venueId'), 'seats', ['venueId'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_seats_venueId'), table_name='seats')
    op.drop_table('seats')

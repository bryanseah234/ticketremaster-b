"""create seat inventory table

Revision ID: 98e6517f83b1
Revises:
Create Date: 2026-03-20 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '98e6517f83b1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'seat_inventory',
        sa.Column('inventoryId', sa.String(length=36), nullable=False),
        sa.Column('eventId', sa.String(length=36), nullable=False),
        sa.Column('seatId', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('heldByUserId', sa.String(length=36), nullable=True),
        sa.Column('holdToken', sa.String(length=64), nullable=True),
        sa.Column('heldUntil', sa.DateTime(), nullable=True),
        sa.Column('createdAt', sa.DateTime(), nullable=False),
        sa.Column('updatedAt', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('inventoryId'),
        sa.UniqueConstraint('eventId', 'seatId', name='uq_seat_inventory_event_seat'),
    )
    op.create_index(op.f('ix_seat_inventory_eventId'), 'seat_inventory', ['eventId'], unique=False)
    op.create_index(op.f('ix_seat_inventory_holdToken'), 'seat_inventory', ['holdToken'], unique=False)
    op.create_index(op.f('ix_seat_inventory_status'), 'seat_inventory', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_seat_inventory_holdToken'), table_name='seat_inventory')
    op.drop_index(op.f('ix_seat_inventory_status'), table_name='seat_inventory')
    op.drop_index(op.f('ix_seat_inventory_eventId'), table_name='seat_inventory')
    op.drop_table('seat_inventory')

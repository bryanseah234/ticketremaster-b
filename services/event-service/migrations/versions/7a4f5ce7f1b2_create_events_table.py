"""create events table

Revision ID: 7a4f5ce7f1b2
Revises:
Create Date: 2026-03-20 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7a4f5ce7f1b2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'events',
        sa.Column('eventId', sa.String(length=36), nullable=False),
        sa.Column('venueId', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('image', sa.String(length=500), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('createdAt', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('eventId'),
    )


def downgrade():
    op.drop_table('events')

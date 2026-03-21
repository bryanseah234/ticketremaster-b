"""create venues table

Revision ID: c91a2dfd38bf
Revises:
Create Date: 2026-03-20 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c91a2dfd38bf'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'venues',
        sa.Column('venueId', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=False),
        sa.Column('postalCode', sa.String(length=10), nullable=True),
        sa.Column('coordinates', sa.String(length=50), nullable=True),
        sa.Column('isActive', sa.Boolean(), nullable=False),
        sa.Column('createdAt', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('venueId'),
    )


def downgrade():
    op.drop_table('venues')

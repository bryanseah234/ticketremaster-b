"""create listings table

Revision ID: 6c2b6f22d919
Revises:
Create Date: 2026-03-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6c2b6f22d919'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'listings',
        sa.Column('listingId', sa.String(length=36), nullable=False),
        sa.Column('ticketId', sa.String(length=36), nullable=False),
        sa.Column('sellerId', sa.String(length=36), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('createdAt', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('listingId'),
    )
    op.create_index(op.f('ix_listings_ticketId'), 'listings', ['ticketId'], unique=False)
    op.create_index(op.f('ix_listings_sellerId'), 'listings', ['sellerId'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_listings_sellerId'), table_name='listings')
    op.drop_index(op.f('ix_listings_ticketId'), table_name='listings')
    op.drop_table('listings')

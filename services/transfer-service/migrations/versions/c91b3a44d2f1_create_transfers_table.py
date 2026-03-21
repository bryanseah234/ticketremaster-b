"""create transfers table

Revision ID: c91b3a44d2f1
Revises:
Create Date: 2026-03-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c91b3a44d2f1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'transfers',
        sa.Column('transferId', sa.String(length=36), nullable=False),
        sa.Column('listingId', sa.String(length=36), nullable=False),
        sa.Column('buyerId', sa.String(length=36), nullable=False),
        sa.Column('sellerId', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('creditAmount', sa.Float(), nullable=False),
        sa.Column('buyerOtpVerified', sa.Boolean(), nullable=False),
        sa.Column('sellerOtpVerified', sa.Boolean(), nullable=False),
        sa.Column('buyerVerificationSid', sa.String(length=64), nullable=True),
        sa.Column('sellerVerificationSid', sa.String(length=64), nullable=True),
        sa.Column('completedAt', sa.DateTime(), nullable=True),
        sa.Column('createdAt', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('transferId'),
    )
    op.create_index(op.f('ix_transfers_listingId'), 'transfers', ['listingId'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_transfers_listingId'), table_name='transfers')
    op.drop_table('transfers')

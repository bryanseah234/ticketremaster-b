"""create credit transactions table

Revision ID: 4f6c2a3e9d10
Revises:
Create Date: 2026-03-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f6c2a3e9d10'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'credit_txns',
        sa.Column('txnId', sa.String(length=36), nullable=False),
        sa.Column('userId', sa.String(length=36), nullable=False),
        sa.Column('delta', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(length=50), nullable=False),
        sa.Column('referenceId', sa.String(length=100), nullable=True),
        sa.Column('createdAt', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('txnId'),
    )
    op.create_index(op.f('ix_credit_txns_referenceId'), 'credit_txns', ['referenceId'], unique=False)
    op.create_index(op.f('ix_credit_txns_userId'), 'credit_txns', ['userId'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_credit_txns_userId'), table_name='credit_txns')
    op.drop_index(op.f('ix_credit_txns_referenceId'), table_name='credit_txns')
    op.drop_table('credit_txns')

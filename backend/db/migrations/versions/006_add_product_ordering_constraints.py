"""add_product_ordering_constraints

Revision ID: 006
Revises: 005
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add case_pack_size and moq to products table
    op.add_column('products', sa.Column('case_pack_size', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('products', sa.Column('moq', sa.Integer(), nullable=False, server_default='0'))

def downgrade() -> None:
    op.drop_column('products', 'moq')
    op.drop_column('products', 'case_pack_size')

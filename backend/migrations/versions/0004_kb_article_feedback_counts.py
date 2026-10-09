"""kb article feedback counts

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08 15:24:04.188097
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Counts of chatbot sessions where this article fixed (or failed to fix) the issue
    with op.batch_alter_table('kb_articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('helpful_count', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('not_helpful_count', sa.Integer(), server_default='0', nullable=False))



def downgrade() -> None:
    # Counts of chatbot sessions where this article fixed (or failed to fix) the issue
    with op.batch_alter_table('kb_articles', schema=None) as batch_op:
        batch_op.drop_column('not_helpful_count')
        batch_op.drop_column('helpful_count')


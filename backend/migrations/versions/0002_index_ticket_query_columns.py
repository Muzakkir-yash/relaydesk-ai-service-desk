"""index ticket query columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08 15:04:53.643504
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Indexes for the columns every ticket list, queue and thread query filters on
    with op.batch_alter_table('ai_actions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_actions_ticket_id'), ['ticket_id'], unique=False, if_not_exists=True)

    with op.batch_alter_table('ticket_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ticket_messages_ticket_id'), ['ticket_id'], unique=False, if_not_exists=True)

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tickets_assigned_to'), ['assigned_to'], unique=False, if_not_exists=True)
        batch_op.create_index(batch_op.f('ix_tickets_status'), ['status'], unique=False, if_not_exists=True)
        batch_op.create_index(batch_op.f('ix_tickets_user_id'), ['user_id'], unique=False, if_not_exists=True)



def downgrade() -> None:
    # Indexes for the columns every ticket list, queue and thread query filters on
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tickets_user_id'), if_exists=True)
        batch_op.drop_index(batch_op.f('ix_tickets_status'), if_exists=True)
        batch_op.drop_index(batch_op.f('ix_tickets_assigned_to'), if_exists=True)

    with op.batch_alter_table('ticket_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ticket_messages_ticket_id'), if_exists=True)

    with op.batch_alter_table('ai_actions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ai_actions_ticket_id'), if_exists=True)


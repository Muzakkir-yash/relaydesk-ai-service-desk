"""reconcile schema drift in pre-Alembic databases

Databases created before migrations existed had some columns added by hand
as VARCHAR(32)/nullable and lack two foreign keys. This revision inspects
the live schema and only touches tables that actually differ, so on a
database built from 0001 it does nothing.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KB_SOURCE = sa.Enum('manual', 'ai_drafted')
KB_STATUS = sa.Enum('published', 'pending_approval')
MOOD = sa.Enum('calm', 'neutral', 'frustrated')


def _column(inspector, table, name):
    return next(c for c in inspector.get_columns(table) if c['name'] == name)


def _has_fk(inspector, table, column):
    return any(column in fk['constrained_columns'] for fk in inspector.get_foreign_keys(table))


def _is_enum_like(column):
    # A non-native Enum is stored as VARCHAR sized to its longest value;
    # the legacy columns were VARCHAR(32).
    return getattr(column['type'], 'length', None) != 32


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # Backfill before tightening NOT NULL constraints
    op.execute("UPDATE kb_articles SET source = 'manual' WHERE source IS NULL")
    op.execute("UPDATE kb_articles SET status = 'published' WHERE status IS NULL")
    op.execute("UPDATE users SET support_level = 'L1' WHERE support_level IS NULL")

    source = _column(inspector, 'kb_articles', 'source')
    status = _column(inspector, 'kb_articles', 'status')
    kb_fk = _has_fk(inspector, 'kb_articles', 'source_ticket_id')
    if source['nullable'] or status['nullable'] or not _is_enum_like(source) or not kb_fk:
        with op.batch_alter_table('kb_articles') as batch_op:
            batch_op.alter_column('source', existing_type=source['type'], type_=KB_SOURCE, nullable=False)
            batch_op.alter_column('status', existing_type=status['type'], type_=KB_STATUS, nullable=False)
            if not kb_fk:
                batch_op.create_foreign_key('fk_kb_articles_source_ticket_id', 'tickets', ['source_ticket_id'], ['id'])

    mood = _column(inspector, 'tickets', 'mood')
    ticket_fk = _has_fk(inspector, 'tickets', 'cluster_id')
    if not _is_enum_like(mood) or not ticket_fk:
        with op.batch_alter_table('tickets') as batch_op:
            batch_op.alter_column('mood', existing_type=mood['type'], type_=MOOD, existing_nullable=True)
            if not ticket_fk:
                batch_op.create_foreign_key('fk_tickets_cluster_id', 'problem_clusters', ['cluster_id'], ['id'])

    support_level = _column(inspector, 'users', 'support_level')
    if support_level['nullable']:
        with op.batch_alter_table('users') as batch_op:
            batch_op.alter_column('support_level', existing_type=support_level['type'], nullable=False)


def downgrade() -> None:
    # Reconciliation only moves legacy databases onto the baseline schema;
    # there is nothing meaningful to undo.
    pass

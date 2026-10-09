"""baseline schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-08 15:03:53.336185
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_type', sa.Enum('user', 'technician', 'admin', 'ai'), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=128), nullable=False),
    sa.Column('target_type', sa.String(length=64), nullable=True),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_log_id'), ['id'], unique=False)

    op.create_table('problem_clusters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('likely_cause', sa.Text(), nullable=True),
    sa.Column('ticket_ids', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('open', 'acknowledged', 'resolved'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('problem_clusters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_problem_clusters_id'), ['id'], unique=False)

    op.create_table('sla_policies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('priority', sa.Enum('low', 'medium', 'high', 'critical'), nullable=False),
    sa.Column('response_minutes', sa.Integer(), nullable=False),
    sa.Column('resolution_minutes', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('priority')
    )
    with op.batch_alter_table('sla_policies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sla_policies_id'), ['id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('email', sa.String(length=256), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=False),
    sa.Column('role', sa.Enum('enduser', 'technician', 'admin'), nullable=False),
    sa.Column('team', sa.String(length=64), nullable=True),
    sa.Column('support_level', sa.String(length=16), nullable=False),
    sa.Column('primary_device', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_id'), ['id'], unique=False)

    op.create_table('system_announcements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('severity', sa.Enum('critical', 'warning', 'info', 'maintenance'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('affected_services', sa.JSON(), nullable=True),
    sa.Column('workaround', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('estimated_resolution', sa.String(length=128), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('system_announcements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_system_announcements_id'), ['id'], unique=False)

    op.create_table('tickets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('subject', sa.String(length=256), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('category', sa.Enum('hardware', 'software', 'network', 'access', 'account', 'general', 'other'), nullable=True),
    sa.Column('priority', sa.Enum('low', 'medium', 'high', 'critical'), nullable=True),
    sa.Column('mood', sa.Enum('calm', 'neutral', 'frustrated'), nullable=True),
    sa.Column('language', sa.String(length=64), nullable=True),
    sa.Column('status', sa.Enum('new', 'ai_handling', 'deflected', 'escalated', 'assigned', 'in_progress', 'resolved', 'closed'), nullable=False),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('target_level', sa.String(length=16), nullable=True),
    sa.Column('suggested_team', sa.String(length=64), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=True),
    sa.Column('attachments', sa.JSON(), nullable=True),
    sa.Column('device_name', sa.String(length=128), nullable=True),
    sa.Column('device_os', sa.String(length=128), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('subnet_vlan', sa.String(length=128), nullable=True),
    sa.Column('mac_address', sa.String(length=64), nullable=True),
    sa.Column('asset_tag', sa.String(length=64), nullable=True),
    sa.Column('serial_number', sa.String(length=64), nullable=True),
    sa.Column('last_reboot', sa.String(length=128), nullable=True),
    sa.Column('edr_status', sa.String(length=128), nullable=True),
    sa.Column('hardware_specs', sa.String(length=256), nullable=True),
    sa.Column('domain_join', sa.String(length=128), nullable=True),
    sa.Column('office_location', sa.String(length=128), nullable=True),
    sa.Column('sla_due', sa.DateTime(), nullable=True),
    sa.Column('cluster_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ),
    sa.ForeignKeyConstraint(['cluster_id'], ['problem_clusters.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tickets_id'), ['id'], unique=False)

    op.create_table('ai_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.Enum('classify', 'deflect_attempt', 'handover', 'kb_draft', 'cluster_detect'), nullable=False),
    sa.Column('input_snapshot', sa.Text(), nullable=True),
    sa.Column('output_snapshot', sa.Text(), nullable=True),
    sa.Column('tokens_used', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ai_actions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_actions_id'), ['id'], unique=False)

    op.create_table('handover_briefings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('user_tried', sa.Text(), nullable=True),
    sa.Column('ai_tried', sa.Text(), nullable=True),
    sa.Column('likely_causes', sa.JSON(), nullable=True),
    sa.Column('suggested_steps', sa.JSON(), nullable=True),
    sa.Column('related_ticket_ids', sa.JSON(), nullable=True),
    sa.Column('generated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ticket_id')
    )
    with op.batch_alter_table('handover_briefings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_handover_briefings_id'), ['id'], unique=False)

    op.create_table('kb_articles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('tags', sa.String(length=512), nullable=True),
    sa.Column('category', sa.String(length=64), nullable=True),
    sa.Column('source', sa.Enum('manual', 'ai_drafted'), nullable=False),
    sa.Column('status', sa.Enum('published', 'pending_approval'), nullable=False),
    sa.Column('source_ticket_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['source_ticket_id'], ['tickets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('kb_articles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kb_articles_id'), ['id'], unique=False)

    op.create_table('ticket_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.Column('sender_type', sa.Enum('user', 'ai', 'technician'), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('attachments', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ticket_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ticket_messages_id'), ['id'], unique=False)

    op.create_table('ticket_ratings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ticket_id')
    )
    with op.batch_alter_table('ticket_ratings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ticket_ratings_id'), ['id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('ticket_ratings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ticket_ratings_id'))

    op.drop_table('ticket_ratings')
    with op.batch_alter_table('ticket_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ticket_messages_id'))

    op.drop_table('ticket_messages')
    with op.batch_alter_table('kb_articles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kb_articles_id'))

    op.drop_table('kb_articles')
    with op.batch_alter_table('handover_briefings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_handover_briefings_id'))

    op.drop_table('handover_briefings')
    with op.batch_alter_table('ai_actions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ai_actions_id'))

    op.drop_table('ai_actions')
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tickets_id'))

    op.drop_table('tickets')
    with op.batch_alter_table('system_announcements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_system_announcements_id'))

    op.drop_table('system_announcements')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_id'))
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    with op.batch_alter_table('sla_policies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sla_policies_id'))

    op.drop_table('sla_policies')
    with op.batch_alter_table('problem_clusters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_problem_clusters_id'))

    op.drop_table('problem_clusters')
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_log_id'))

    op.drop_table('audit_log')

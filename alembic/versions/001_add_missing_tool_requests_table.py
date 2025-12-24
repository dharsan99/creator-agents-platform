"""Add missing_tool_requests table

Revision ID: 001_add_missing_tool_requests
Revises:
Create Date: 2025-12-17 19:28:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

# revision identifiers, used by Alembic.
revision = '001_add_missing_tool_requests'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create missing_tool_requests table for tracking tool needs."""
    op.create_table(
        'missing_tool_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False, index=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('use_case', sa.Text(), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('priority', sa.String(), nullable=False, server_default='medium'),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('first_requested_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_requested_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('implemented', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('implemented_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    # Create indexes for common queries
    op.create_index('ix_missing_tool_requests_tool_name', 'missing_tool_requests', ['tool_name'])
    op.create_index('ix_missing_tool_requests_priority', 'missing_tool_requests', ['priority'])
    op.create_index('ix_missing_tool_requests_implemented', 'missing_tool_requests', ['implemented'])
    op.create_index('ix_missing_tool_requests_creator_id', 'missing_tool_requests', ['creator_id'])

    # Create unique constraint to prevent duplicate tool name entries
    op.create_index(
        'uq_missing_tool_requests_tool_name',
        'missing_tool_requests',
        ['tool_name'],
        unique=True
    )


def downgrade() -> None:
    """Drop missing_tool_requests table."""
    op.drop_index('uq_missing_tool_requests_tool_name', table_name='missing_tool_requests')
    op.drop_index('ix_missing_tool_requests_creator_id', table_name='missing_tool_requests')
    op.drop_index('ix_missing_tool_requests_implemented', table_name='missing_tool_requests')
    op.drop_index('ix_missing_tool_requests_priority', table_name='missing_tool_requests')
    op.drop_index('ix_missing_tool_requests_tool_name', table_name='missing_tool_requests')
    op.drop_table('missing_tool_requests')

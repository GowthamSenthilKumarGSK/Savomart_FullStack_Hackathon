"""add property_evaluations table

Revision ID: c3f8e2a91d47
Revises: aa6b3021cbd6
Create Date: 2026-09-29 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c3f8e2a91d47'
down_revision: Union[str, None] = 'aa6b3021cbd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'property_evaluations')"
    ))
    table_exists = result.scalar()

    if not table_exists:
        op.create_table('property_evaluations',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('property_id', sa.Uuid(), nullable=False),
            sa.Column('overall_score', sa.Float(), nullable=True),
            sa.Column('sub_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('ai_narrative', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['property_id'], ['properties.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    op.create_index('idx_prop_eval_property_id', 'property_evaluations', ['property_id'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('idx_prop_eval_property_id', table_name='property_evaluations')
    op.drop_table('property_evaluations')

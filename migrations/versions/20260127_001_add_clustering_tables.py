"""Add story clustering tables

Revision ID: 20260127_001
Revises:
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '20260127_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create story_clusters table
    op.create_table(
        'story_clusters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cluster_hash', sa.BINARY(16), nullable=False),
        sa.Column('representative_story_id', sa.Integer(), nullable=False),
        sa.Column('dominant_tags', sa.JSON(), nullable=True),
        sa.Column('story_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('country_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('first_pub_date', sa.DateTime(), nullable=False),
        sa.Column('last_pub_date', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['representative_story_id'], ['stories.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('cluster_hash', name='uq_cluster_hash'),
    )
    op.create_index('idx_cluster_story_count', 'story_clusters', ['story_count'], unique=False)
    op.create_index('idx_cluster_last_pub_date', 'story_clusters', ['last_pub_date'], unique=False)

    # Create story_cluster_members table
    op.create_table(
        'story_cluster_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=False),
        sa.Column('story_id', sa.Integer(), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['cluster_id'], ['story_clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['story_id'], ['stories.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('cluster_id', 'story_id', name='uq_cluster_story'),
    )
    op.create_index('idx_member_story', 'story_cluster_members', ['story_id'], unique=False)
    op.create_index('idx_member_cluster', 'story_cluster_members', ['cluster_id'], unique=False)


def downgrade():
    op.drop_table('story_cluster_members')
    op.drop_table('story_clusters')

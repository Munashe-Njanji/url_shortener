"""Initial PostgreSQL schema with all tables

Revision ID: 001
Revises: 
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables for production URL shortener."""
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('email_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('account_locked_until', sa.DateTime(), nullable=True),
        sa.Column('tier', sa.String(length=50), server_default='free', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    
    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('owner_id', sa.BigInteger(), nullable=False),
        sa.Column('tier', sa.String(length=50), server_default='free', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Organization Members table
    op.create_table(
        'organization_members',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('invited_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id')
    )
    op.create_index('idx_org_members_org', 'organization_members', ['organization_id'])
    op.create_index('idx_org_members_user', 'organization_members', ['user_id'])
    
    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('organization_id', sa.BigInteger(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('scopes', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_api_keys_hash', 'api_keys', ['key_hash'], unique=True)
    
    # Domains table
    op.create_table(
        'domains',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('verification_token', sa.String(length=255), nullable=True),
        sa.Column('ssl_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_domains_domain', 'domains', ['domain'], unique=True)
    op.create_index('idx_domains_org', 'domains', ['organization_id'])
    
    # Links table (replaces urls table)
    op.create_table(
        'links',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('slug', sa.String(length=30), nullable=False),
        sa.Column('target_url', sa.Text(), nullable=False),
        sa.Column('url_hash', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('organization_id', sa.BigInteger(), nullable=True),
        sa.Column('domain_id', sa.BigInteger(), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('og_image_url', sa.Text(), nullable=True),
        sa.Column('qr_code_url', sa.Text(), nullable=True),
        sa.Column('clicks', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_links_slug', 'links', ['slug'], unique=True)
    op.create_index('idx_links_user', 'links', ['user_id'])
    op.create_index('idx_links_org', 'links', ['organization_id'])
    op.create_index('idx_links_url_hash', 'links', ['url_hash'])
    op.create_index('idx_links_created', 'links', ['created_at'])
    op.create_index('idx_links_active', 'links', ['active'])
    
    # Subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('tier', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_subscriptions_stripe', 'subscriptions', ['stripe_subscription_id'], unique=True)
    
    # Usage Records table
    op.create_table(
        'usage_records',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('links_created', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_clicks', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('api_requests', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'period_start')
    )
    op.create_index('idx_usage_org_period', 'usage_records', ['organization_id', 'period_start'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('usage_records')
    op.drop_table('subscriptions')
    op.drop_table('links')
    op.drop_table('domains')
    op.drop_table('api_keys')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    op.drop_table('users')

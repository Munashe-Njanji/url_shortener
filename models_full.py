"""
Complete database models for URL shortener with all tables.
This will be used for the PostgreSQL migration.
"""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    account_locked_until = Column(DateTime, nullable=True)
    tier = Column(String(50), default='free', nullable=False)

    # Relationships
    organizations_owned = relationship("Organization", back_populates="owner", foreign_keys="Organization.owner_id")
    organization_memberships = relationship("OrganizationMember", back_populates="user")
    api_keys = relationship("APIKey", back_populates="user")
    links = relationship("Link", back_populates="user")


class Organization(Base):
    """Organization model for team management."""
    __tablename__ = "organizations"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    owner_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tier = Column(String(50), default='free', nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    settings = Column(JSONB, default={}, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="organizations_owned", foreign_keys=[owner_id])
    members = relationship("OrganizationMember", back_populates="organization")
    api_keys = relationship("APIKey", back_populates="organization")
    domains = relationship("Domain", back_populates="organization")
    links = relationship("Link", back_populates="organization")
    subscriptions = relationship("Subscription", back_populates="organization")
    usage_records = relationship("UsageRecord", back_populates="organization")


class OrganizationMember(Base):
    """Organization membership with roles."""
    __tablename__ = "organization_members"

    id = Column(BigInteger, primary_key=True, index=True)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # owner, admin, analyst, developer
    invited_at = Column(DateTime, nullable=False, server_default=func.now())
    joined_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="organization_memberships")


class APIKey(Base):
    """API keys for authentication."""
    __tablename__ = "api_keys"

    id = Column(BigInteger, primary_key=True, index=True)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    key_prefix = Column(String(20), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=True)
    scopes = Column(JSONB, default=[], nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="api_keys")
    organization = relationship("Organization", back_populates="api_keys")


class Domain(Base):
    """Custom domains for branded short links."""
    __tablename__ = "domains"

    id = Column(BigInteger, primary_key=True, index=True)
    domain = Column(String(255), unique=True, nullable=False)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    verified = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String(255), nullable=True)
    ssl_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="domains")
    links = relationship("Link", back_populates="domain")


class Link(Base):
    """
    Short links (URLs) - enhanced version with all fields.
    """
    __tablename__ = "links"

    id = Column(BigInteger, primary_key=True, index=True)
    slug = Column(String(30), unique=True, nullable=False, index=True)
    target_url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    domain_id = Column(BigInteger, ForeignKey("domains.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    og_image_url = Column(Text, nullable=True)
    qr_code_url = Column(Text, nullable=True)
    clicks = Column(BigInteger, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime, nullable=True)
    metadata = Column(JSONB, default={}, nullable=False)

    # Relationships
    user = relationship("User", back_populates="links")
    organization = relationship("Organization", back_populates="links")
    domain = relationship("Domain", back_populates="links")


class Subscription(Base):
    """Stripe subscriptions for billing."""
    __tablename__ = "subscriptions"

    id = Column(BigInteger, primary_key=True, index=True)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    tier = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="subscriptions")


class UsageRecord(Base):
    """Usage tracking for billing and limits."""
    __tablename__ = "usage_records"

    id = Column(BigInteger, primary_key=True, index=True)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False)
    links_created = Column(Integer, default=0, nullable=False)
    total_clicks = Column(BigInteger, default=0, nullable=False)
    api_requests = Column(Integer, default=0, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="usage_records")


# Keep the old URL model for backward compatibility during migration
class URL(Base):
    """
    Legacy URL model (for SQLite compatibility).
    This will be migrated to the Link model.
    """
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(Text, nullable=False)
    short_url = Column(String(30), unique=True, index=True, nullable=False)
    url_hash = Column(String(64), index=True, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False, index=True)
    expiration_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

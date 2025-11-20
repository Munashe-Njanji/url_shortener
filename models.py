"""
Database models for URL shortener.
Now using PostgreSQL 'links' table with backward compatibility.
"""
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Boolean, Text, ForeignKey
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


class URL(Base):
    """
    URL model for storing short links.
    Maps to 'links' table in PostgreSQL.
    
    Attributes:
        id: Primary key (BigInteger for PostgreSQL)
        target_url: The original long URL
        slug: The short slug/code (renamed from short_url)
        url_hash: SHA-256 hash of normalized URL for deduplication
        clicks: Number of times the link has been accessed (BigInteger)
        active: Whether the link is active (soft delete flag)
        expires_at: When the link expires (renamed from expiration_date)
        created_at: When the link was created
        updated_at: When the link was last updated
        user_id: Owner user ID (nullable)
        organization_id: Owner organization ID (nullable)
        domain_id: Custom domain ID (nullable)
        title: Page title from metadata
        description: Page description from metadata
        og_image_url: Open Graph image URL
        qr_code_url: QR code image URL
        metadata: Additional metadata (JSONB)
    """
    __tablename__ = "links"

    id = Column(BigInteger, primary_key=True, index=True)
    slug = Column(String(30), unique=True, index=True, nullable=False)
    target_url = Column(Text, nullable=False)
    url_hash = Column(String(64), index=True, nullable=False)
    clicks = Column(BigInteger, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Ownership and organization
    user_id = Column(BigInteger, nullable=True, index=True)
    organization_id = Column(BigInteger, nullable=True, index=True)
    domain_id = Column(BigInteger, nullable=True)
    
    # Metadata fields
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    og_image_url = Column(Text, nullable=True)
    qr_code_url = Column(Text, nullable=True)
    link_metadata = Column('metadata', JSONB, default={}, nullable=False)
    
    # Backward compatibility properties
    @property
    def short_url(self):
        """Alias for slug for backward compatibility."""
        return self.slug
    
    @short_url.setter
    def short_url(self, value):
        """Setter for backward compatibility."""
        self.slug = value
    
    @property
    def expiration_date(self):
        """Alias for expires_at for backward compatibility."""
        return self.expires_at
    
    @expiration_date.setter
    def expiration_date(self, value):
        """Setter for backward compatibility."""
        self.expires_at = value

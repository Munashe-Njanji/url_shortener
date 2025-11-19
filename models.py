"""
Database models for URL shortener.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from database import Base


class URL(Base):
    """
    URL model for storing short links.
    
    Attributes:
        id: Primary key
        target_url: The original long URL
        short_url: The short slug/code
        url_hash: SHA-256 hash of normalized URL for deduplication
        clicks: Number of times the link has been accessed
        active: Whether the link is active (soft delete flag)
        expiration_date: When the link expires (optional)
        created_at: When the link was created
        updated_at: When the link was last updated
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

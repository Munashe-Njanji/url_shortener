from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta, timezone
import models
import hashing

MAX_EXPIRATION_DAYS = 365


def create_short_url(
    db: Session, target_url: str, expiration_date: Optional[datetime] = None
):
    if expiration_date:
        if expiration_date <= datetime.utcnow():
            raise ValueError("Expiration date must be in the future.")
        if expiration_date > datetime.utcnow() + timedelta(days=MAX_EXPIRATION_DAYS):
            raise ValueError(
                f"Expiration date cannot exceed {MAX_EXPIRATION_DAYS} days."
            )
        else:
            expiration_date = expiration_date
    else:
        expiration_date = datetime.now(timezone.utc) + timedelta(
            days=MAX_EXPIRATION_DAYS
        )
    while True:
        short_url = hashing.create_short_hash(target_url)
        if not db.query(models.URL).filter_by(short_url=short_url).first():
            break
    db_url = models.URL(
        target_url=target_url, short_url=short_url, expiration_date=expiration_date
    )
    db.add(db_url)
    db.commit()
    db.refresh(db_url)
    return db_url


def get_url_by_short(db: Session, short_url: str):
    return (
        db.query(models.URL)
        .filter(models.URL.short_url == short_url)
        .filter(
            models.URL.expiration_date.isnot(None) | models.URL.expiration_date
            < datetime.utcnow(),
        )
        .first()
    )


def increment_clicks(db: Session, db_url: models.URL):
    db_url.clicks = db_url.clicks + 1
    db.commit()
    return db_url

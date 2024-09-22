from sqlalchemy import Column, Integer, String, DateTime
from database import Base


class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(String, nullable=False)
    short_url = Column(String, unique=True, index=True)
    clicks = Column(Integer, default=0)
    expiration_date = Column(DateTime, nullable=True)

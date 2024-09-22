from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class URLCreate(BaseModel):
    # target_url: HttpUrl
    target_url: str
    expiration_date: Optional[datetime]

class URLResponse(BaseModel):
    target_url: str
    short_url: str
    clicks: int
    expiration_date: Optional[datetime]

    class Config:
        orm_mode = True

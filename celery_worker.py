from celery import Celery
from sqlalchemy.orm import Session
from datetime import datetime
from database import SessionLocal
from models import URL

app = Celery('tasks', broker='redis://localhost:6379/0')

@app.task
def delete_expired_urls():
    db: Session = SessionLocal()
    expired_urls = db.query(URL).filter(URL.expiration_date < datetime.utcnow()).all()
    for url in expired_urls:
        db.delete(url)
    db.commit()

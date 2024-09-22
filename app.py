from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import models
import crud
import database
import schemas

models.Base.metadata.create_all(bind=database.engine)


class NotFoundOrGoneException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_410_GONE, detail=detail)


app = FastAPI()


@app.post("/shorten/", response_model=schemas.URLResponse)
def shorten_url(url: schemas.URLCreate, db: Session = Depends(database.get_db)):
    try:
        db_url = crud.create_short_url(db, url.target_url, url.expiration_date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return db_url


@app.get("/{short_url}")
def redirect_to_target(short_url: str, db: Session = Depends(database.get_db)):
    db_url = crud.get_url_by_short(db, short_url)
    if db_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="URL not found or has expired"
        )

    # Increment click count and return target URL
    crud.increment_clicks(db, db_url)
    # return {"target_url": db_url.target_url, "clicks": db_url.clicks}
    return RedirectResponse(url=str(db_url.target_url))
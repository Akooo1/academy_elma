from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db import get_db
from app.models import AppUser

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/internal/media-auth", status_code=204)
def media_auth(_: AppUser = Depends(current_user)) -> Response:
    """nginx auth_request target: HLS, subtitles and PDFs are served only to logged-in users."""
    return Response(status_code=204)

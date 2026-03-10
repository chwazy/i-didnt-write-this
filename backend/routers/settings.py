from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Settings
from schemas import SettingsUpdate, SettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    settings = db.query(Settings).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Settings not initialised")
    return settings


@router.put("", response_model=SettingsResponse)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    if not data.git_user_name or not data.git_user_name.strip():
        raise HTTPException(status_code=422, detail="git_user_name must not be empty")
    if not data.git_user_email or not data.git_user_email.strip():
        raise HTTPException(status_code=422, detail="git_user_email must not be empty")
    if data.task_retention_limit < 0:
        raise HTTPException(status_code=422, detail="task_retention_limit must be non-negative")
    if data.max_concurrent_tasks < 0:
        raise HTTPException(status_code=422, detail="max_concurrent_tasks must be non-negative")

    settings = db.query(Settings).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Settings not initialised")

    old_max_concurrent = settings.max_concurrent_tasks

    settings.git_user_name = data.git_user_name.strip()
    settings.git_user_email = data.git_user_email.strip()
    settings.default_merge_option = data.default_merge_option
    settings.task_retention_limit = data.task_retention_limit
    settings.max_concurrent_tasks = data.max_concurrent_tasks
    settings.notifications_enabled = data.notifications_enabled
    settings.default_model = data.default_model
    db.commit()
    db.refresh(settings)

    # If retention limit changed, clean up old tasks immediately
    from services.task_service import cleanup_old_tasks
    cleanup_old_tasks(db)

    # If max concurrent increased (or set to 0/unlimited), start queued tasks
    from services.task_service import start_queued_tasks
    if data.max_concurrent_tasks == 0 or data.max_concurrent_tasks > old_max_concurrent:
        start_queued_tasks(db)

    return settings

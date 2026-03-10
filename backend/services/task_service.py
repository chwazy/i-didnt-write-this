import logging
import threading
from sqlalchemy.orm import Session
from sqlalchemy import case

from models import Task, TaskStatus, Settings

logger = logging.getLogger(__name__)


def cleanup_old_tasks(db: Session):
    """Delete oldest completed (done/failed) tasks beyond the retention limit."""
    settings = db.query(Settings).first()
    if not settings or settings.task_retention_limit <= 0:
        return

    limit = settings.task_retention_limit

    completed = (
        db.query(Task)
        .filter(Task.status.in_([TaskStatus.done, TaskStatus.failed]))
        .order_by(
            case(
                (Task.finished_at.isnot(None), Task.finished_at),
                else_=Task.created_at,
            ).desc()
        )
        .all()
    )

    if len(completed) <= limit:
        return

    to_delete = completed[limit:]
    for task in to_delete:
        db.delete(task)
    db.commit()
    logger.info(f"Cleaned up {len(to_delete)} old completed tasks")


def start_queued_tasks(db: Session):
    """Start queued tasks if there are available concurrency slots."""
    from database import SessionLocal

    settings = db.query(Settings).first()
    if not settings:
        return

    max_concurrent = settings.max_concurrent_tasks
    running_count = db.query(Task).filter(Task.status == TaskStatus.running).count()

    if max_concurrent > 0:
        available_slots = max_concurrent - running_count
        if available_slots <= 0:
            return
    else:
        available_slots = None  # unlimited

    queued_tasks = (
        db.query(Task)
        .filter(Task.status == TaskStatus.queued)
        .order_by(Task.created_at.asc())
        .all()
    )

    if not queued_tasks:
        return

    if available_slots is not None:
        queued_tasks = queued_tasks[:available_slots]

    for task in queued_tasks:
        task.status = TaskStatus.running
        db.commit()
        threading.Thread(
            target=_launch_container_background,
            args=(task.id, SessionLocal),
            daemon=True,
        ).start()


def _launch_container_background(task_id: int, db_factory):
    """Start an agent container in a background thread and update task status."""
    from services.docker_service import start_agent_container
    from datetime import datetime, timezone
    from models import Log

    db = db_factory()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return
        try:
            container_id = start_agent_container(task, db_factory)
            task.container_id = container_id
            db.commit()
        except Exception as e:
            logger.error(f"Failed to start container for task {task_id}: {e}")
            task.status = TaskStatus.failed
            task.finished_at = datetime.now(timezone.utc)
            db.commit()
            log_entry = Log(task_id=task.id, line=f"Failed to start container: {e}")
            db.add(log_entry)
            db.commit()
    except Exception as e:
        logger.error(f"Background container launch error for task {task_id}: {e}")
    finally:
        db.close()

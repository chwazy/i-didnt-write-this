import asyncio
import logging
import threading
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from database import get_db, SessionLocal
from models import Task, TaskStatus, Log, Project, Settings, MergeOption
from schemas import TaskCreate, TaskResponse, LogResponse
from services.docker_service import start_agent_container, stop_agent_container, resolve_model
from services.title_service import generate_task_title

router = APIRouter(tags=["tasks"])


def _launch_container_background(task_id: int, db_factory):
    """Start an agent container in a background thread and update task status."""
    db = db_factory()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        # Check concurrency limit
        settings = db.query(Settings).first()
        max_concurrent = settings.max_concurrent_tasks if settings else 0
        running_count = db.query(Task).filter(Task.status == TaskStatus.running).count()

        should_start = max_concurrent == 0 or running_count < max_concurrent

        if not should_start:
            # Task remains queued
            return

        # Update status to running
        task.status = TaskStatus.running
        db.commit()

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


def _to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        branch_name=task.branch_name,
        title=task.title,
        task_description=task.task_description,
        merge_option=task.merge_option,
        model=task.model,
        status=task.status,
        container_id=task.container_id,
        pr_url=task.pr_url,
        warning=task.warning,
        created_at=task.created_at,
        finished_at=task.finished_at,
        project_name=task.project.name if task.project else None,
    )


@router.get("/api/tasks", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    return [_to_response(t) for t in tasks]


@router.post("/api/tasks", response_model=TaskResponse, status_code=201)
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get global settings for resolution
    settings = db.query(Settings).first()

    # Resolve merge_option: task override > project override > global default
    if data.merge_option is not None:
        resolved_merge_option = data.merge_option
    elif project.merge_option is not None:
        resolved_merge_option = project.merge_option
    else:
        resolved_merge_option = settings.default_merge_option if settings else MergeOption.none

    # Resolve model: task override > project override > global settings > default
    resolved_model = resolve_model(
        data.model,
        project.default_model,
        settings.default_model if settings else None
    )

    task = Task(
        project_id=data.project_id,
        branch_name=data.branch_name,
        title=generate_task_title(data.task_description),
        task_description=data.task_description,
        merge_option=resolved_merge_option,
        git_user_name=data.git_user_name if data.git_user_name and data.git_user_name.strip() else None,
        git_user_email=data.git_user_email if data.git_user_email and data.git_user_email.strip() else None,
        model=resolved_model,
        status=TaskStatus.queued,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    project.last_base_branch = data.branch_name
    db.commit()

    # Start container in background - it will check concurrency and update status
    threading.Thread(
        target=_launch_container_background,
        args=(task.id, SessionLocal),
        daemon=True,
    ).start()

    return _to_response(task)


@router.delete("/api/tasks/{task_id}", status_code=204)
def kill_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in (TaskStatus.done, TaskStatus.failed):
        db.delete(task)
        db.commit()
        return

    if task.status == TaskStatus.queued:
        db.delete(task)
        db.commit()
        return

    if task.status == TaskStatus.running:
        stop_agent_container(task)

    task.status = TaskStatus.failed
    task.finished_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/api/tasks/{task_id}/retry", response_model=TaskResponse, status_code=201)
def retry_task(task_id: int, db: Session = Depends(get_db)):
    original = db.query(Task).filter(Task.id == task_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Task not found")
    can_retry = (
        original.status == TaskStatus.failed
        or (original.status == TaskStatus.done and original.warning)
    )
    if not can_retry:
        raise HTTPException(status_code=400, detail="Only failed or done-with-warning tasks can be retried")

    # Get project and settings for model resolution
    project = db.query(Project).filter(Project.id == original.project_id).first()
    settings = db.query(Settings).first()

    # Ensure model is resolved (in case original task had None)
    resolved_model = resolve_model(
        original.model,
        project.default_model if project else None,
        settings.default_model if settings else None
    )

    task = Task(
        project_id=original.project_id,
        branch_name=original.branch_name,
        title=original.title or generate_task_title(original.task_description),
        task_description=original.task_description,
        merge_option=original.merge_option,
        git_user_name=original.git_user_name,
        git_user_email=original.git_user_email,
        model=resolved_model,
        status=TaskStatus.queued,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Start container in background - it will check concurrency and update status
    threading.Thread(
        target=_launch_container_background,
        args=(task.id, SessionLocal),
        daemon=True,
    ).start()

    try:
        db.delete(original)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to delete original task {task_id} during retry: {e}")
        db.rollback()

    return _to_response(task)


@router.get("/api/tasks/{task_id}/logs", response_model=list[LogResponse])
def get_task_logs(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    logs = db.query(Log).filter(Log.task_id == task_id).order_by(Log.timestamp).all()
    return logs


@router.websocket("/ws/tasks/{task_id}/logs")
async def ws_task_logs(websocket: WebSocket, task_id: int):
    await websocket.accept()
    last_id = 0

    try:
        while True:
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    await websocket.close(code=4004)
                    return

                logs = (
                    db.query(Log)
                    .filter(Log.task_id == task_id, Log.id > last_id)
                    .order_by(Log.id)
                    .all()
                )

                for log in logs:
                    ts = log.timestamp if log.timestamp.tzinfo else log.timestamp.replace(tzinfo=timezone.utc)
                    await websocket.send_json({
                        "id": log.id,
                        "timestamp": ts.isoformat(),
                        "line": log.line,
                    })
                    last_id = log.id

                is_finished = task.status in (TaskStatus.done, TaskStatus.failed)
            finally:
                db.close()

            if is_finished and not logs:
                await websocket.send_json({"type": "done", "status": task.status.value})
                await websocket.close()
                return

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass

import asyncio
import docker
import os
import shutil
import subprocess
import tempfile
import threading
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import Task, TaskStatus, Log, Settings, Project
from services.encryption import decrypt_pat
from services.git_service import build_authenticated_url
from services.branch_service import generate_branch_name

logger = logging.getLogger(__name__)

_client = None
_log_threads: dict[int, threading.Event] = {}

SUPPORTED_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-haiku-4-5-20251001",
]
DEFAULT_MODEL = "claude-sonnet-4-6"


def resolve_model(task_model: str | None, project_model: str | None, settings_model: str | None = None) -> str:
    for candidate in [task_model, project_model, settings_model, DEFAULT_MODEL]:
        if candidate and candidate in SUPPORTED_MODELS:
            return candidate
    return DEFAULT_MODEL


def get_docker_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def _run_async(coro):
    """Run an async coroutine from sync context, handling existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an existing event loop (e.g. FastAPI), create a new one in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def _generate_prompt_sync(task: Task, project, pat: str, db_factory, settings_model: str | None = None) -> str | None:
    """Pre-generate a structured prompt using Anthropic API. Returns None on failure."""
    try:
        from services.prompt_service import get_or_refresh_repo_context, generate_task_prompt
    except ImportError:
        logger.warning("prompt_service not available, skipping prompt generation")
        return None

    resolved_model = resolve_model(task.model, project.default_model, settings_model)
    tmp_dir = None
    repo_context = ""

    try:
        # Check if git is available
        git_available = shutil.which("git") is not None
        if git_available:
            tmp_dir = tempfile.mkdtemp(prefix=f"repo-context-{project.id}-")
            auth_url = build_authenticated_url(
                project.repo_url, pat, project.platform, project.git_host
            )
            result = subprocess.run(
                ["git", "clone", "--depth=1", auth_url, tmp_dir],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                db = db_factory()
                try:
                    repo_context = _run_async(get_or_refresh_repo_context(
                        project.id, tmp_dir, task.task_description, db
                    ))
                finally:
                    db.close()
            else:
                logger.warning(f"Shallow clone failed for project {project.id}: {result.stderr}")
        else:
            logger.warning("git not available in backend container, skipping repo context extraction")

        generated = _run_async(generate_task_prompt(
            task.task_description, repo_context, model=resolved_model
        ))
        return generated
    except Exception as e:
        logger.error(f"Prompt generation failed for task {task.id}: {e}")
        return None
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def start_agent_container(task: Task, db_factory) -> str:
    client = get_docker_client()
    project = task.project

    pat = decrypt_pat(project.encrypted_pat)
    auth_url = build_authenticated_url(
        project.repo_url, pat, project.platform, project.git_host
    )

    image = "claude-agent:latest"
    branch_name = generate_branch_name(task.task_description, task.id)

    # Get global settings for model and git identity resolution
    db = db_factory()
    try:
        settings = db.query(Settings).first()
        settings_model = settings.default_model if settings else None
        git_user_name = settings.git_user_name if settings else "Claude"
        git_user_email = settings.git_user_email if settings else "claude@agent.ai"
    finally:
        db.close()

    # Resolve model: task > project > global settings > default
    resolved_model = resolve_model(task.model, project.default_model, settings_model)

    # Pre-generate prompt via Anthropic API
    generated_prompt = _generate_prompt_sync(task, project, pat, db_factory, settings_model)

    # Save generated prompt to DB
    if generated_prompt:
        db = db_factory()
        try:
            t = db.query(Task).filter(Task.id == task.id).first()
            if t:
                t.generated_prompt = generated_prompt
                db.commit()
        finally:
            db.close()

    # Use generated prompt if available, otherwise fall back to raw description
    task_prompt = generated_prompt or task.task_description

    env = {
        "GIT_REPO_URL": auth_url,
        "GIT_BRANCH": task.branch_name,
        "NEW_BRANCH": branch_name,
        "TASK": task_prompt,
        "TASK_DESCRIPTION": task.task_description,
        "TASK_TITLE": task.title if task.title else task.task_description[:60],
        "TASK_ID": str(task.id),
        "PLATFORM": project.platform.value,
        "REPO_URL": project.repo_url,
        "PAT": pat,
        "MERGE_OPTION": task.merge_option.value,
        "MODEL": resolved_model,
    }

    if project.git_host:
        env["GIT_HOST"] = project.git_host

    # Resolve git identity: task > project > global settings
    if project.git_user_name:
        git_user_name = project.git_user_name
    if project.git_user_email:
        git_user_email = project.git_user_email
    if task.git_user_name:
        git_user_name = task.git_user_name
    if task.git_user_email:
        git_user_email = task.git_user_email

    env["GIT_USER_NAME"] = git_user_name
    env["GIT_USER_EMAIL"] = git_user_email

    # Pass ANTHROPIC_API_KEY to agent container for CLI authentication
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        env["ANTHROPIC_API_KEY"] = anthropic_key

    container_name = f"claude-agent-{task.id}"

    # Remove stale container with the same name if it exists
    try:
        stale = client.containers.get(container_name)
        stale.remove(force=True)
        logger.info(f"Removed stale container {container_name}")
    except docker.errors.NotFound:
        pass

    container = client.containers.run(
        image,
        detach=True,
        environment=env,
        mem_limit="4g",
        nano_cpus=2_000_000_000,
        remove=False,
        name=container_name,
    )

    stop_event = threading.Event()
    _log_threads[task.id] = stop_event

    log_thread = threading.Thread(
        target=_stream_logs,
        args=(container, task.id, db_factory, stop_event),
        daemon=True,
    )
    log_thread.start()

    return container.id


def _stream_logs(container, task_id: int, db_factory, stop_event: threading.Event):
    try:
        for chunk in container.logs(stream=True, follow=True):
            if stop_event.is_set():
                break
            line = chunk.decode("utf-8", errors="replace").rstrip("\n")
            db = db_factory()
            try:
                log_entry = Log(task_id=task_id, line=line)
                db.add(log_entry)
                db.commit()
            finally:
                db.close()

        db = db_factory()
        try:
            container.reload()
            task = db.query(Task).filter(Task.id == task_id).first()
            if task and task.status == TaskStatus.running:
                exit_code = container.attrs.get("State", {}).get("ExitCode", -1)
                task.status = TaskStatus.done if exit_code == 0 else TaskStatus.failed
                task.finished_at = datetime.now(timezone.utc)

                if exit_code == 0:
                    logs = container.logs().decode("utf-8", errors="replace")
                    merge_warning = None
                    for log_line in logs.split("\n"):
                        if log_line.startswith("PR_URL="):
                            task.pr_url = log_line.split("=", 1)[1].strip()
                        if log_line.startswith("MERGE_WARNING="):
                            merge_warning = log_line.split("=", 1)[1].strip()
                    task.warning = merge_warning

                db.commit()

            # Run post-finish hooks: cleanup old tasks and start queued tasks
            try:
                from services.task_service import cleanup_old_tasks, start_queued_tasks
                cleanup_old_tasks(db)
                start_queued_tasks(db)
            except Exception as hook_err:
                logger.error(f"Error in post-finish hooks for task {task_id}: {hook_err}")

            try:
                container.remove(force=True)
            except Exception:
                pass
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error streaming logs for task {task_id}: {e}")
        db = db_factory()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task and task.status == TaskStatus.running:
                task.status = TaskStatus.failed
                task.finished_at = datetime.now(timezone.utc)
                db.commit()
                log_entry = Log(task_id=task_id, line=f"Agent error: {e}")
                db.add(log_entry)
                db.commit()

                try:
                    from services.task_service import cleanup_old_tasks, start_queued_tasks
                    cleanup_old_tasks(db)
                    start_queued_tasks(db)
                except Exception as hook_err:
                    logger.error(f"Error in post-finish hooks for task {task_id}: {hook_err}")
        except Exception:
            logger.error(f"Failed to update task {task_id} status after error")
        finally:
            db.close()
    finally:
        _log_threads.pop(task_id, None)


def stop_agent_container(task: Task):
    client = get_docker_client()
    stop_event = _log_threads.get(task.id)
    if stop_event:
        stop_event.set()
    if task.container_id:
        try:
            container = client.containers.get(task.container_id)
            container.stop(timeout=10)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass


def get_container_status(container_id: str) -> str | None:
    client = get_docker_client()
    try:
        container = client.containers.get(container_id)
        return container.status
    except docker.errors.NotFound:
        return None

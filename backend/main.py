import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect, text
from database import engine, Base, SessionLocal
from models import Settings, Task
from routers import projects, tasks, settings
from services.title_service import generate_task_title

os.makedirs("data", exist_ok=True)
Base.metadata.create_all(bind=engine)

# Migrate existing DB: add missing columns
with engine.connect() as conn:
    task_cols = [c["name"] for c in inspect(engine).get_columns("tasks")]
    if "merge_option" not in task_cols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN merge_option VARCHAR(20) NOT NULL DEFAULT 'none'"))
        conn.commit()
    if "git_user_name" not in task_cols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN git_user_name TEXT"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN git_user_email TEXT"))
        conn.commit()

    if "title" not in task_cols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN title VARCHAR(255)"))
        conn.commit()
    if "warning" not in task_cols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN warning TEXT"))
        conn.commit()

    settings_cols = [c["name"] for c in inspect(engine).get_columns("settings")]
    if "task_retention_limit" not in settings_cols:
        conn.execute(text("ALTER TABLE settings ADD COLUMN task_retention_limit INTEGER NOT NULL DEFAULT 0"))
        conn.commit()
    if "max_concurrent_tasks" not in settings_cols:
        conn.execute(text("ALTER TABLE settings ADD COLUMN max_concurrent_tasks INTEGER NOT NULL DEFAULT 0"))
        conn.commit()
    if "default_merge_option" not in settings_cols:
        conn.execute(text("ALTER TABLE settings ADD COLUMN default_merge_option VARCHAR(20) NOT NULL DEFAULT 'none'"))
        conn.commit()
    if "notifications_enabled" not in settings_cols:
        conn.execute(text("ALTER TABLE settings ADD COLUMN notifications_enabled BOOLEAN NOT NULL DEFAULT 1"))
        conn.commit()
    if "default_model" not in settings_cols:
        conn.execute(text("ALTER TABLE settings ADD COLUMN default_model TEXT"))
        conn.commit()

    project_cols = [c["name"] for c in inspect(engine).get_columns("projects")]
    if "git_user_name" not in project_cols:
        conn.execute(text("ALTER TABLE projects ADD COLUMN git_user_name TEXT"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN git_user_email TEXT"))
        conn.commit()
    if "merge_option" not in project_cols:
        conn.execute(text("ALTER TABLE projects ADD COLUMN merge_option VARCHAR(20)"))
        conn.commit()
    if "last_base_branch" not in project_cols:
        conn.execute(text("ALTER TABLE projects ADD COLUMN last_base_branch VARCHAR(255)"))
        conn.commit()
    if "notifications_enabled" not in project_cols:
        conn.execute(text("ALTER TABLE projects ADD COLUMN notifications_enabled BOOLEAN"))
        conn.commit()
    if "default_model" not in project_cols:
        conn.execute(text("ALTER TABLE projects ADD COLUMN default_model TEXT DEFAULT 'claude-sonnet-4-6'"))
        conn.commit()
    if "repo_context_summary" not in project_cols:
        conn.execute(text("ALTER TABLE projects ADD COLUMN repo_context_summary TEXT"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN repo_context_updated_at TEXT"))
        conn.commit()

    if "model" not in task_cols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN model TEXT"))
        conn.commit()
    if "generated_prompt" not in task_cols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN generated_prompt TEXT"))
        conn.commit()

# Seed default settings row
db = SessionLocal()
try:
    if db.query(Settings).first() is None:
        db.add(Settings(id=1, git_user_name="Claude", git_user_email="claude@agent.ai"))
        db.commit()

    # Backfill titles for existing tasks
    untitled = db.query(Task).filter(Task.title.is_(None)).all()
    for t in untitled:
        t.title = generate_task_title(t.task_description)
    if untitled:
        db.commit()
finally:
    db.close()

app = FastAPI(title="i didn't write this", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:80", "http://frontend:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(settings.router)


@app.get("/api/health")
def health():
    import docker
    docker_ok = False
    anthropic_api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    anthropic_admin_key_set = bool(os.environ.get("ANTHROPIC_ADMIN_API_KEY"))
    try:
        client = docker.from_env()
        client.ping()
        docker_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "docker": docker_ok,
        "anthropic_api_key": anthropic_api_key_set,
        "anthropic_admin_api_key": anthropic_admin_key_set,
    }


# Cost per million tokens in USD (input, output)
_MODEL_PRICING = {
    "claude-opus-4-5": (15.0, 75.0),
    "claude-opus-4": (15.0, 75.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-3-7": (3.0, 15.0),
    "claude-sonnet-3-5": (3.0, 15.0),
    "claude-haiku-4-5": (0.8, 4.0),
    "claude-haiku-3-5": (0.8, 4.0),
    "claude-haiku-3": (0.25, 1.25),
}
_DEFAULT_PRICING = (3.0, 15.0)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _MODEL_PRICING.get(model, None)
    if pricing is None:
        for key in _MODEL_PRICING:
            if key in model or model in key:
                pricing = _MODEL_PRICING[key]
                break
        if pricing is None:
            pricing = _DEFAULT_PRICING
    input_cost = (input_tokens / 1_000_000) * pricing[0]
    output_cost = (output_tokens / 1_000_000) * pricing[1]
    return round(input_cost + output_cost, 4)


@app.get("/api/usage")
def get_usage():
    import httpx
    from datetime import date
    from schemas import UsageResponse, ModelUsage

    # Admin API key required for usage endpoint (falls back to regular key)
    api_key = os.environ.get("ANTHROPIC_ADMIN_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        today = date.today()
        period_start = today.replace(day=1).isoformat()
        period_end = today.isoformat()
        return UsageResponse(
            period_start=period_start,
            period_end=period_end,
            total_input_tokens=0,
            total_output_tokens=0,
            total_estimated_cost_usd=0.0,
            by_model=[],
            error="ANTHROPIC_ADMIN_API_KEY is not configured. The Usage API requires an Admin API key (sk-ant-admin...).",
        )

    today = date.today()
    period_start = today.replace(day=1)
    period_end = today

    all_buckets = []
    next_page = None

    try:
        while True:
            params = {
                "starting_at": period_start.strftime("%Y-%m-%dT00:00:00Z"),
                "ending_at": period_end.strftime("%Y-%m-%dT23:59:59Z"),
                "group_by[]": "model",
                "bucket_width": "1d",
                "limit": 31,
            }
            if next_page:
                params["page"] = next_page

            resp = httpx.get(
                "https://api.anthropic.com/v1/organizations/usage_report/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                params=params,
                timeout=15.0,
            )

            if resp.status_code != 200:
                error_detail = resp.text[:200]
                hint = ""
                if resp.status_code in (401, 403):
                    hint = " Ensure ANTHROPIC_ADMIN_API_KEY is set to an Admin API key (sk-ant-admin...)."
                elif resp.status_code == 404:
                    hint = " Ensure ANTHROPIC_ADMIN_API_KEY is set to an Admin API key (sk-ant-admin...), not a regular API key."
                return UsageResponse(
                    period_start=period_start.isoformat(),
                    period_end=period_end.isoformat(),
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_estimated_cost_usd=0.0,
                    by_model=[],
                    error=f"Anthropic API returned {resp.status_code}: {error_detail}{hint}",
                )

            data = resp.json()
            buckets = data.get("data", [])
            all_buckets.extend(buckets)

            if data.get("has_more"):
                next_page = data.get("next_page")
                if not next_page:
                    break
            else:
                break

    except Exception as exc:
        return UsageResponse(
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            total_input_tokens=0,
            total_output_tokens=0,
            total_estimated_cost_usd=0.0,
            by_model=[],
            error=f"Failed to fetch usage data: {str(exc)}",
        )

    # Aggregate by model across all time buckets
    model_totals: dict[str, dict] = {}
    for bucket in all_buckets:
        for result in bucket.get("results", []):
            model = result.get("model") or "unknown"
            uncached_input = result.get("uncached_input_tokens", 0)
            cache_read = result.get("cache_read_input_tokens", 0)
            output = result.get("output_tokens", 0)
            total_input = uncached_input + cache_read
            if model not in model_totals:
                model_totals[model] = {"input_tokens": 0, "output_tokens": 0}
            model_totals[model]["input_tokens"] += total_input
            model_totals[model]["output_tokens"] += output

    by_model = [
        ModelUsage(
            model=m,
            input_tokens=v["input_tokens"],
            output_tokens=v["output_tokens"],
            estimated_cost_usd=_estimate_cost(m, v["input_tokens"], v["output_tokens"]),
        )
        for m, v in sorted(model_totals.items())
    ]

    total_input = sum(m.input_tokens for m in by_model)
    total_output = sum(m.output_tokens for m in by_model)
    total_cost = round(sum(m.estimated_cost_usd for m in by_model), 4)

    return UsageResponse(
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_estimated_cost_usd=total_cost,
        by_model=by_model,
    )

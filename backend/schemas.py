from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from models import Platform, TaskStatus, MergeOption


def _ensure_utc(v: datetime | None) -> datetime | None:
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class ProjectCreate(BaseModel):
    name: str
    repo_url: str
    platform: Platform
    git_host: str | None = None
    pat: str
    merge_option: MergeOption | None = None
    notifications_enabled: bool | None = None
    default_model: str | None = "claude-sonnet-4-6"


class ProjectUpdate(BaseModel):
    name: str | None = None
    repo_url: str | None = None
    platform: Platform | None = None
    git_host: str | None = None
    pat: str | None = None
    git_user_name: str | None = None
    git_user_email: str | None = None
    merge_option: MergeOption | None = None
    notifications_enabled: bool | None = None
    default_model: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    repo_url: str
    platform: Platform
    git_host: str | None
    masked_pat: str
    git_user_name: str | None = None
    git_user_email: str | None = None
    merge_option: MergeOption | None = None
    notifications_enabled: bool | None = None
    last_base_branch: str | None = None
    default_model: str | None = "claude-sonnet-4-6"
    created_at: datetime

    _ensure_utc = field_validator('created_at', mode='before')(_ensure_utc)

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    project_id: int
    branch_name: str = "main"
    task_description: str
    merge_option: MergeOption | None = None
    git_user_name: str | None = None
    git_user_email: str | None = None
    model: str | None = None


class TaskResponse(BaseModel):
    id: int
    project_id: int
    branch_name: str
    title: str | None = None
    task_description: str
    merge_option: MergeOption
    model: str | None = None
    status: TaskStatus
    container_id: str | None
    pr_url: str | None
    warning: str | None = None
    created_at: datetime
    finished_at: datetime | None
    project_name: str | None = None

    _ensure_utc = field_validator('created_at', 'finished_at', mode='before')(_ensure_utc)

    class Config:
        from_attributes = True


class LogResponse(BaseModel):
    id: int
    task_id: int
    timestamp: datetime
    line: str

    _ensure_utc = field_validator('timestamp', mode='before')(_ensure_utc)

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    git_user_name: str
    git_user_email: str
    default_merge_option: MergeOption = MergeOption.none
    task_retention_limit: int = 0
    max_concurrent_tasks: int = 0
    notifications_enabled: bool = True
    default_model: str | None = None


class SettingsResponse(BaseModel):
    git_user_name: str
    git_user_email: str
    default_merge_option: MergeOption
    task_retention_limit: int = 0
    max_concurrent_tasks: int = 0
    notifications_enabled: bool = True
    default_model: str | None = None

    class Config:
        from_attributes = True


class ModelUsage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class UsageResponse(BaseModel):
    period_start: str
    period_end: str
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: float
    by_model: list[ModelUsage]
    error: str | None = None

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from database import Base


class Platform(str, enum.Enum):
    github = "github"
    gitlab = "gitlab"
    azure = "azure"


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class MergeOption(str, enum.Enum):
    none = "none"
    pull_request = "pull_request"
    auto_squash_merge = "auto_squash_merge"


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    git_user_name = Column(Text, nullable=False, default="Claude")
    git_user_email = Column(Text, nullable=False, default="claude@agent.ai")
    default_merge_option = Column(SAEnum(MergeOption), default=MergeOption.none, nullable=False)
    task_retention_limit = Column(Integer, nullable=False, default=0)
    max_concurrent_tasks = Column(Integer, nullable=False, default=0)
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    default_model = Column(Text, nullable=True)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    repo_url = Column(String(512), nullable=False)
    platform = Column(SAEnum(Platform), nullable=False)
    git_host = Column(String(255), nullable=True)
    encrypted_pat = Column(Text, nullable=False)
    git_user_name = Column(Text, nullable=True)
    git_user_email = Column(Text, nullable=True)
    merge_option = Column(SAEnum(MergeOption), nullable=True)
    notifications_enabled = Column(Boolean, nullable=True)
    last_base_branch = Column(String(255), nullable=True)
    default_model = Column(Text, nullable=True, default="claude-sonnet-4-6")
    repo_context_summary = Column(Text, nullable=True)
    repo_context_updated_at = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    branch_name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    task_description = Column(Text, nullable=False)
    merge_option = Column(SAEnum(MergeOption), default=MergeOption.none, nullable=False)
    git_user_name = Column(Text, nullable=True)
    git_user_email = Column(Text, nullable=True)
    model = Column(Text, nullable=True)
    generated_prompt = Column(Text, nullable=True)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.queued, nullable=False)
    container_id = Column(String(128), nullable=True)
    pr_url = Column(String(512), nullable=True)
    warning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="tasks")
    logs = relationship("Log", back_populates="task", cascade="all, delete-orphan")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    line = Column(Text, nullable=False)

    task = relationship("Task", back_populates="logs")

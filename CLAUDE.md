# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

i didn't write this — a web app that orchestrates multiple Claude Code CLI agents in isolated Docker containers. Users register git projects with encrypted PATs, submit tasks, and monitor parallel agents that clone repos, perform work, run tests, and create PRs.

## Build & Run Commands

```bash
# Full stack (production)
SECRET_KEY="<fernet-key>" docker-compose up --build

# Build agent image (required before first run)
docker build -t claude-agent:latest ./agent

# Backend only (local dev)
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000

# Frontend only (local dev, proxies to backend:8000)
cd frontend && npm install && npm run dev

# Run backend tests
cd backend && python -m pytest tests/ -v

# Generate a Fernet secret key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Architecture

Three deployment units that communicate at runtime:

**Backend (FastAPI, `backend/`)** — REST API + WebSocket server on port 8000. Uses Docker SDK to spawn sibling containers (via mounted Docker socket). SQLite for persistence, Fernet for PAT encryption. Backend Python imports use flat paths from `backend/` as the working directory (e.g., `from models import ...`, not `from backend.models`).

- `main.py` — App initialization, CORS, DB migrations, settings seed, title backfill
- `models.py` — SQLAlchemy ORM: Settings, Project, Task, Log (with Platform/TaskStatus/MergeOption enums)
- `schemas.py` — Pydantic request/response models
- `database.py` — SQLAlchemy engine and session setup
- `routers/` — API endpoints split by domain:
  - `projects.py` — CRUD for projects, branch listing via platform APIs
  - `tasks.py` — Task create/delete/retry, log retrieval, WebSocket log streaming
  - `settings.py` — Global settings GET/PUT with post-save hooks (cleanup, queue start)
- `services/` — Business logic:
  - `docker_service.py` — Container lifecycle: start, stop, log streaming, post-finish hooks
  - `git_service.py` — Platform-specific auth URLs, branch fetching (GitHub/GitLab/Azure)
  - `branch_service.py` — Generates gitflow branch names from task descriptions (`type/slug-id`)
  - `title_service.py` — Generates short task titles from descriptions (first sentence, title case, 60 char max)
  - `task_service.py` — Concurrency control (start queued tasks) and retention cleanup (delete old completed tasks)
  - `encryption.py` — Fernet encrypt/decrypt/mask for PATs

**Frontend (React + Tailwind, `frontend/`)** — Vite dev server on 5173 or nginx on 80 (prod). Uses `@` path alias mapped to `src/`. Zustand for state. All API calls go through `src/lib/api.js`, WebSocket connections through `src/lib/websocket.js`. Nginx reverse-proxies `/api/` and `/ws/` to the backend.

- `store/useStore.js` — Zustand store: projects, tasks, health, settings, theme
- `pages/` — Dashboard (4-column task board), NewTask (form), Projects (CRUD grid), Settings (categorized)
- `components/` — TaskCard, LogDrawer (full-screen right drawer), StatusBadge, AddProjectDialog, EditProjectDialog, ui/Drawer (vaul wrapper)
- `lib/` — api.js (fetch wrapper), websocket.js (WS connector), utils.js (cn, relativeTime, formatDuration)

**Agent Container (`agent/`)** — Ephemeral Docker container per task. node:20-slim with Claude Code CLI. The `entrypoint.sh` script is the entire agent lifecycle: clone → branch → run claude → test → commit → push → create PR via platform API. Communicates results back to the backend by printing `PR_URL=<url>` and optionally `MERGE_WARNING=<msg>` to stdout, which the backend's log-streaming thread parses.

## Key Data Flow

1. `POST /api/tasks` → creates Task row → checks concurrency limit → starts container or leaves queued
2. Container spawned with env vars (auth URL, task description, PAT, git identity). A background thread in `_stream_logs()` follows container stdout and writes each line to the `logs` table.
3. Frontend polls tasks every 5s on Dashboard. Opening a task's log drawer connects a WebSocket to `/ws/tasks/{id}/logs` which polls the `logs` table every 0.5s for new entries.
4. When the container exits, the log thread reads exit code, sets task status to done/failed, extracts `PR_URL`/`MERGE_WARNING` from stdout, runs post-finish hooks (cleanup old tasks, start queued tasks), and removes the container.
5. Failed tasks (or done-with-warning) can be retried — creates a new task with same params and deletes the original.

## Settings System

Global settings stored in the `settings` table (single row, seeded on startup). Configurable via `PUT /api/settings`:
- **Git Identity** — Default commit author name/email for agent containers
- **Default Merge Option** — none / pull_request / auto_squash_merge
- **Task Retention Limit** — Max completed tasks to keep (0 = unlimited)
- **Max Concurrent Tasks** — Concurrency limit (0 = unlimited); excess tasks are queued

Settings cascade: task override > project override > global default (for merge option and git identity).

## PAT Security Model

PATs are Fernet-encrypted in SQLite (`encrypted_pat` column). Decrypted only at runtime in `docker_service.py` to build authenticated git URLs and inject into container env vars. The frontend API never returns raw PATs — only `mask_pat()` output (last 4 chars). The `SECRET_KEY` env var must be set; without it the backend will crash on any PAT operation.

## Platform-Specific Behavior

Git auth URL format and PR creation differ by platform (see `git_service.py` and `entrypoint.sh`):
- **GitHub/GitLab:** `https://oauth2:PAT@host/org/repo.git`
- **Azure DevOps:** `https://user:PAT@dev.azure.com/org/project/_git/repo`
- PR creation uses curl + platform REST APIs inside the agent container

## Docker Container Constraints

Agent containers: 2 CPUs, 4GB RAM, `claude-auth` volume mounted read-only at `/root/.claude`. Container names follow `claude-agent-{task_id}`. Containers are not auto-removed (`remove=False`) so the log thread can read final state before cleanup.

## Git Commit Rules

- **Never** append `Co-authored-by: Claude`, `Co-authored-by: claude`, or any AI/assistant attribution trailer to commit messages. Commit messages must contain only the content explicitly provided or approved by the user.
- **Always** use the git identity (user.name and user.email) defined in the global git configuration (`~/.gitconfig`). Never set or override `user.name`, `user.email`, or `GIT_AUTHOR_*` / `GIT_COMMITTER_*` environment variables. Do not pass `--author` flags to `git commit`.

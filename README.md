# i didn't write this

A web application to orchestrate multiple Claude Code CLI agents running in isolated Docker containers, each working on git tasks in parallel.

## Features

- Register git projects (GitHub, GitLab, self-hosted GitLab, Azure DevOps) with encrypted PATs
- Submit tasks that spin up isolated Docker agent containers
- Monitor parallel agents in real-time with live log streaming via WebSocket
- Each agent clones the repo, performs the task, runs tests, commits, and creates a PR
- Kanban-style dashboard with live status updates

## Prerequisites

- Docker and Docker Compose
- An Anthropic API key (for Claude authentication)

## Quick Start

### 1. Generate a secret key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Create the environment file

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set SECRET_KEY to the key generated above
```

### 3. Build the agent image

```bash
docker build -t claude-agent:latest ./agent
```

### 4. Start the application

```bash
SECRET_KEY="your-fernet-key-here" docker-compose up --build
```

The app will be available by default at:
- **Frontend:** http://localhost (port 80)
- **Backend API:** http://localhost:8000

## Usage

1. **Add a project** - Go to Projects, click "Add Project", enter your repo URL and PAT
2. **Create a task** - Go to New Task, select a project, describe what the agent should do
3. **Monitor** - Watch the Dashboard for real-time status updates and live logs

## Architecture

```
Frontend (React + Tailwind)
    |  REST API + WebSocket
Backend (FastAPI)
    |-- Docker SDK -> spawn/monitor/kill agent containers
    |-- Fernet encryption -> PATs stored encrypted in SQLite
    |-- SQLite -> Projects, Tasks, Logs
    |-- WebSocket -> stream container logs to frontend

Agent Container (Docker)
    |-- Clones repo with PAT-authenticated URL
    |-- Runs: claude --dangerously-skip-permissions -p "$TASK"
    |-- Runs tests if detected
    |-- Commits, pushes, and creates PR
```

## Project Structure

```
i-didnt-write-this/
  backend/          # FastAPI backend
  agent/            # Docker agent image (Dockerfile + entrypoint.sh)
  frontend/         # React + Tailwind frontend
  docker-compose.yml
```

## Security

- PATs are encrypted at rest using Fernet symmetric encryption
- PATs are never logged, exposed in API responses, or written to disk in containers
- Frontend only sees masked PATs (last 4 characters)
- Agent containers are resource-limited (2 CPUs, 4GB RAM)

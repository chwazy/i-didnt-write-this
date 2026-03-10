import os
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior software engineer acting as a task planner for an autonomous coding agent.

Your job is to convert a vague feature or bug description into a detailed, structured,
actionable prompt that a Claude Code CLI agent will execute autonomously inside a cloned
repository.

The agent has full access to the repository and can read any file, run tests, and make
code changes. Your prompt must guide it precisely.

Output format — always produce these sections:

## Objective
One paragraph clearly stating what must be implemented or fixed.

## Files to Create or Modify
List the exact file paths most likely involved. Use the repo context to infer them.
If uncertain, say so and tell the agent to search for them.

## Implementation Steps
Numbered step-by-step instructions. Be specific about function names, variable names,
API shapes, and logic. Do not be vague.

## Acceptance Criteria
Bullet list of conditions that must be true when the task is complete.

## Edge Cases and Warnings
Any gotchas, things to avoid, or special handling required.

## Testing
What tests to run or write to verify the implementation.

IMPORTANT RULES:
- Never instruct the agent to git push, merge, open PRs, or interact with remotes.
  Those operations are handled externally after the agent finishes.
- Never instruct the agent to install global system packages.
- If the task description is ambiguous, make reasonable assumptions and state them."""

_SKIP_DIRS = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.venv'}

_KEY_FILES = [
    'README.md', 'README.rst', 'README.txt',
    'package.json', 'requirements.txt', 'pyproject.toml', 'Pipfile', 'go.mod',
    'docker-compose.yml', 'Dockerfile',
    '.env.example',
]

_STOPWORDS = {
    'this', 'that', 'with', 'from', 'have', 'will', 'been', 'being', 'were',
    'would', 'could', 'should', 'their', 'there', 'these', 'those', 'then',
    'than', 'them', 'they', 'what', 'when', 'where', 'which', 'while', 'about',
    'after', 'before', 'between', 'into', 'through', 'during', 'each', 'some',
    'other', 'also', 'just', 'only', 'very', 'make', 'like', 'does', 'done',
    'need', 'want', 'please', 'update', 'change', 'implement', 'create', 'the',
    'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
}


def _extract_keywords(text: str) -> list[str]:
    words = re.split(r'[\s/\-_.,;:!?()]+', text.lower())
    return [w for w in words if len(w) > 3 and w not in _STOPWORDS]


def _should_skip_dir(name: str) -> bool:
    return name in _SKIP_DIRS or name.startswith('.')


def extract_repo_context(repo_path: str, task_description: str, max_context_bytes: int = 20000) -> str:
    tree_lines = []
    all_files = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not _should_skip_dir(d)]
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, repo_path).replace('\\', '/')
            tree_lines.append(rel)
            all_files.append((rel, full))

    parts = ["=== FILE TREE ===\n" + "\n".join(sorted(tree_lines))]

    # Read key files
    key_file_contents = []
    for kf in _KEY_FILES:
        kf_path = os.path.join(repo_path, kf)
        if os.path.isfile(kf_path):
            try:
                with open(kf_path, 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read(3000)
                key_file_contents.append(f"--- {kf} ---\n{content}")
            except Exception:
                pass

    if key_file_contents:
        parts.append("\n=== KEY FILES ===\n" + "\n\n".join(key_file_contents))

    # Find task-relevant files
    keywords = _extract_keywords(task_description)
    if keywords:
        scored = {}
        for rel, full in all_files:
            score = 0
            rel_lower = rel.lower()
            for kw in keywords:
                if kw in rel_lower:
                    score += 2
            if score > 0:
                scored[rel] = (score, full)

        # If we have fewer than 5 from filenames, scan file contents
        if len(scored) < 5:
            for rel, full in all_files:
                if rel in scored:
                    continue
                try:
                    size = os.path.getsize(full)
                    if size > 100_000 or size == 0:
                        continue
                    with open(full, 'r', encoding='utf-8', errors='replace') as fh:
                        content = fh.read(10_000)
                    score = 0
                    content_lower = content.lower()
                    for kw in keywords:
                        if kw in content_lower:
                            score += 1
                    if score > 0:
                        scored[rel] = (score, full)
                except Exception:
                    pass
                if len(scored) >= 15:
                    break

        top = sorted(scored.items(), key=lambda x: -x[1][0])[:5]
        relevant_contents = []
        for rel, (score, full) in top:
            try:
                with open(full, 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read(2000)
                relevant_contents.append(f"--- {rel} ---\n{content}")
            except Exception:
                pass

        if relevant_contents:
            parts.append("\n=== TASK-RELEVANT FILES ===\n" + "\n\n".join(relevant_contents))

    result = "\n".join(parts)
    if len(result) > max_context_bytes:
        result = result[:max_context_bytes] + "\n\n[... context truncated ...]"
    return result


async def generate_task_prompt(
    task_description: str,
    repo_context: str,
    model: str = "claude-sonnet-4-6"
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    system = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }
    ]

    user_content = [
        {
            "type": "text",
            "text": f"## Repository Context\n\n{repo_context}",
            "cache_control": {"type": "ephemeral"}
        },
        {
            "type": "text",
            "text": f"## Task Description\n\n{task_description}"
        }
    ]

    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )

    # Log cache usage stats if available
    usage = response.usage
    if hasattr(usage, 'cache_creation_input_tokens'):
        logger.info(
            f"Prompt generation cache stats: "
            f"creation={getattr(usage, 'cache_creation_input_tokens', 0)}, "
            f"read={getattr(usage, 'cache_read_input_tokens', 0)}"
        )

    return response.content[0].text


async def get_or_refresh_repo_context(
    project_id: int,
    repo_path: str,
    task_description: str,
    db,
    max_age_hours: int = 6
) -> str:
    from models import Project

    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.repo_context_summary and project.repo_context_updated_at:
        try:
            updated = datetime.fromisoformat(project.repo_context_updated_at)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
            if age_hours < max_age_hours:
                return project.repo_context_summary
        except (ValueError, TypeError):
            pass

    context = extract_repo_context(repo_path, task_description)

    if project:
        project.repo_context_summary = context
        project.repo_context_updated_at = datetime.now(timezone.utc).isoformat()
        db.commit()

    return context

import re
import unicodedata

from services.title_service import _LEADING_RE


_BUGFIX_KEYWORDS = [
    "bug", "fix", "broken", "error", "crash", "issue", "patch", "repair", "resolve",
]

_REFACTOR_KEYWORDS = [
    "refactor", "restructure", "reorganize", "clean up", "cleanup",
]

_DOCS_KEYWORDS = [
    "doc", "documentation", "readme", "comment",
]

_CHORE_KEYWORDS = [
    "chore", "dependency", "dependencies", "upgrade", "update version",
    "ci", "pipeline",
]

_INVALID_SLUG_CHARS = re.compile(r"[^a-z0-9-]")
_MULTI_HYPHENS = re.compile(r"-{2,}")
_VALID_BRANCH_RE = re.compile(r"^(feature|bugfix|refactor|docs|chore)/[a-z0-9][a-z0-9-]*[a-z0-9]-\d+$")

_FILLER_WORDS = frozenset([
    "the", "a", "an", "to", "in", "on", "for", "and", "of", "with",
    "that", "this", "is", "are", "was", "were", "be", "been", "being",
])


def _classify_prefix(description: str) -> str:
    lower = description.lower()
    for kw in _BUGFIX_KEYWORDS:
        if kw in lower:
            return "bugfix/"
    for kw in _REFACTOR_KEYWORDS:
        if kw in lower:
            return "refactor/"
    for kw in _DOCS_KEYWORDS:
        if kw in lower:
            return "docs/"
    for kw in _CHORE_KEYWORDS:
        if kw in lower:
            return "chore/"
    return "feature/"


def _first_line(text: str) -> str:
    line = text.strip().split("\n")[0].strip()
    match = re.search(r"[.!?](\s|$)", line)
    if match:
        line = line[: match.start()].strip()
    return line


def _remove_filler_words(words: list[str]) -> list[str]:
    filtered = [w for w in words if w not in _FILLER_WORDS]
    if len(filtered) >= 2:
        return filtered
    return words


def _slugify(text: str) -> str:
    # Normalize unicode, strip accents
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    # Replace spaces with hyphens
    text = text.replace(" ", "-")
    # Replace all non-alphanumeric/non-hyphen chars (including / . _) with hyphens
    text = _INVALID_SLUG_CHARS.sub("-", text)
    text = _MULTI_HYPHENS.sub("-", text)
    text = text.strip("-")
    return text


def generate_branch_name(task_description: str, task_id: int) -> str:
    desc = task_description.strip() if task_description else ""

    if not desc:
        return f"feature/task-{task_id}"

    prefix = _classify_prefix(desc)

    sentence = _first_line(desc)
    cleaned = _LEADING_RE.sub("", sentence).strip()
    if not cleaned:
        cleaned = sentence

    # Remove filler words before slugifying
    words = cleaned.split()
    words = _remove_filler_words(words)
    cleaned = " ".join(words)

    slug = _slugify(cleaned)

    if not slug:
        return f"{prefix}task-{task_id}"

    # Truncate at word boundary (max 50 chars for slug portion)
    if len(slug) > 50:
        truncated = slug[:50].rsplit("-", 1)[0]
        slug = truncated if truncated else slug[:50]

    slug = slug.strip("-")

    if not slug:
        return f"{prefix}task-{task_id}"

    branch = f"{prefix}{slug}-{task_id}"

    assert _VALID_BRANCH_RE.match(branch), f"Invalid branch name generated: {branch}"

    return branch

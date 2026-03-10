import base64
import logging
import re
from urllib.parse import quote, urlparse

import httpx
from fastapi import HTTPException

from models import Platform

logger = logging.getLogger(__name__)


def build_authenticated_url(repo_url: str, pat: str, platform: Platform, git_host: str | None = None) -> str:
    parsed = urlparse(repo_url)
    host = git_host or parsed.hostname

    if platform == Platform.azure:
        path = parsed.path
        return f"https://user:{pat}@{host}{path}"
    else:
        path = parsed.path
        if not path.endswith(".git"):
            path = path + ".git"
        return f"https://oauth2:{pat}@{host}{path}"


def parse_repo_info(repo_url: str, platform: Platform) -> dict:
    parsed = urlparse(repo_url)
    path = parsed.path.strip("/")

    if path.endswith(".git"):
        path = path[:-4]

    if platform == Platform.github or platform == Platform.gitlab:
        parts = path.split("/")
        if len(parts) >= 2:
            return {"owner": parts[0], "repo": parts[1], "full_path": path}
    elif platform == Platform.azure:
        match = re.match(r"([^/]+)/([^/]+)/_git/(.+)", path)
        if match:
            return {"org": match.group(1), "project": match.group(2), "repo": match.group(3), "full_path": path}

    return {"full_path": path}


def fetch_branches(repo_url: str, pat: str, platform: Platform, git_host: str | None = None) -> list[str]:
    """Fetch branch list from the platform REST API (no local git needed)."""
    parsed = urlparse(repo_url)
    host = git_host or parsed.hostname
    info = parse_repo_info(repo_url, platform)

    try:
        if platform == Platform.github:
            branches = _fetch_branches_github(host, info, pat)
        elif platform == Platform.gitlab:
            branches = _fetch_branches_gitlab(host, info, pat)
        elif platform == Platform.azure:
            branches = _fetch_branches_azure(info, pat)
        else:
            raise HTTPException(status_code=400, detail="Unsupported platform or unrecognised repository URL")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error fetching branches")
        raise HTTPException(status_code=502, detail=f"Failed to fetch branches from platform API: {exc}")

    branches.sort(key=lambda b: (b != "main", b != "master", b.lower()))
    return branches


def _fetch_branches_github(host: str, info: dict, pat: str) -> list[str]:
    owner = info.get("owner")
    repo = info.get("repo")
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="Unsupported platform or unrecognised repository URL")

    api_base = f"https://api.{host}" if host == "github.com" else f"https://{host}/api/v3"
    url = f"{api_base}/repos/{owner}/{repo}/branches?per_page=100"
    headers = {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"}
    branches: list[str] = []

    while url:
        resp = httpx.get(url, headers=headers, timeout=10)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Failed to fetch branches from platform API: {resp.status_code} {resp.text}")
        branches.extend(b["name"] for b in resp.json())
        url = resp.links.get("next", {}).get("url")

    return branches


def _fetch_branches_gitlab(host: str, info: dict, pat: str) -> list[str]:
    full_path = info.get("full_path")
    if not full_path:
        raise HTTPException(status_code=400, detail="Unsupported platform or unrecognised repository URL")

    encoded_path = quote(full_path, safe="")
    url: str | None = f"https://{host}/api/v4/projects/{encoded_path}/repository/branches?per_page=100"
    headers = {"PRIVATE-TOKEN": pat}
    branches: list[str] = []

    while url:
        resp = httpx.get(url, headers=headers, timeout=10)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Failed to fetch branches from platform API: {resp.status_code} {resp.text}")
        branches.extend(b["name"] for b in resp.json())
        next_page = resp.headers.get("X-Next-Page", "")
        if next_page:
            url = f"https://{host}/api/v4/projects/{encoded_path}/repository/branches?per_page=100&page={next_page}"
        else:
            url = None

    return branches


def _fetch_branches_azure(info: dict, pat: str) -> list[str]:
    org = info.get("org")
    project = info.get("project")
    repo = info.get("repo")
    if not org or not project or not repo:
        raise HTTPException(status_code=400, detail="Unsupported platform or unrecognised repository URL")

    url = f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/refs?filter=heads/&api-version=7.0"
    basic = base64.b64encode(f":{pat}".encode()).decode()
    headers = {"Authorization": f"Basic {basic}"}

    resp = httpx.get(url, headers=headers, timeout=10)
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Failed to fetch branches from platform API: {resp.status_code} {resp.text}")

    return [ref["name"].removeprefix("refs/heads/") for ref in resp.json().get("value", [])]

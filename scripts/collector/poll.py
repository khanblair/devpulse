"""
devpulse — Department 1: Collector
poll.py

Replaces collect.py + webhook approach entirely.
Runs on a schedule (every 30 min via poll.yml).
Polls GitHub API for recent commits across ALL of the
user's repos — public and private.
No webhook setup needed on any repo.
New repos are picked up automatically.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT / "data" / "log.json"
SETTINGS_FILE = ROOT / "config" / "settings.json"
GH_API = "https://api.github.com"


def load_json(path: Path) -> dict:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_today(utc_offset: int = 3) -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    return now.strftime("%Y-%m-%d")


def get_headers() -> dict:
    token = os.environ.get("GH_TOKEN", "")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def ensure_day_entry(log: dict, today: str) -> dict:
    if today not in log:
        log[today] = {
            "date": today,
            "commits": [],
            "mood": None,
            "devlog": None,
            "question": None,
            "yoyo": None,
            "target_report": None,
            "weekly_report": None,
        }
    return log


def fetch_user_repos(username: str) -> list[tuple[str, str]]:
    """Fetch all repo names for the authenticated user. Returns (owner, repo) tuples."""
    repos = []
    page = 1
    headers = get_headers()

    while True:
        try:
            resp = httpx.get(
                f"{GH_API}/user/repos",
                headers=headers,
                params={
                    "per_page": 100,
                    "page": page,
                    "sort": "pushed",
                    "affiliation": "owner",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for repo in data:
                # skip the devpulse repo itself
                if repo["name"] != "devpulse":
                    repos.append((username, repo["name"]))
            if len(data) < 100:
                break
            page += 1
        except Exception as e:
            print(f"failed to fetch user repos page {page}: {e}")
            break

    return repos


def fetch_user_orgs() -> list[str]:
    """Fetch all organizations the authenticated user belongs to."""
    orgs = []
    headers = get_headers()

    try:
        resp = httpx.get(
            f"{GH_API}/user/orgs",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        for org in data:
            orgs.append(org["login"])
    except Exception as e:
        print(f"failed to fetch orgs: {e}")

    return orgs


def fetch_org_repos(org: str) -> list[tuple[str, str]]:
    """Fetch all repos for an organization. Returns (owner, repo) tuples."""
    repos = []
    page = 1
    headers = get_headers()

    while True:
        try:
            resp = httpx.get(
                f"{GH_API}/orgs/{org}/repos",
                headers=headers,
                params={
                    "per_page": 100,
                    "page": page,
                    "sort": "pushed",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for repo in data:
                repos.append((org, repo["name"]))
            if len(data) < 100:
                break
            page += 1
        except Exception as e:
            print(f"failed to fetch org {org} repos page {page}: {e}")
            break

    return repos


def fetch_all_repos(username: str) -> list[tuple[str, str]]:
    """Fetch all repos from user and their organizations. Returns (owner, repo) tuples."""
    repos = []

    # Fetch user's own repos
    print(f"fetching repos for user {username}...")
    user_repos = fetch_user_repos(username)
    repos.extend(user_repos)
    print(f"  found {len(user_repos)} user repos")

    # Fetch org repos
    print(f"fetching organizations...")
    orgs = fetch_user_orgs()
    print(f"  found {len(orgs)} orgs: {orgs}")

    for org in orgs:
        org_repos = fetch_org_repos(org)
        repos.extend(org_repos)
        print(f"  found {len(org_repos)} repos for {org}")

    # Deduplicate by (owner, repo)
    seen = set()
    unique_repos = []
    for owner, repo in repos:
        key = (owner, repo)
        if key not in seen:
            seen.add(key)
            unique_repos.append(key)

    return unique_repos


def fetch_commits_since(owner: str, repo: str, since: str) -> list[dict]:
    """Fetch commits from a single repo since a given ISO datetime."""
    headers = get_headers()
    try:
        resp = httpx.get(
            f"{GH_API}/repos/{owner}/{repo}/commits",
            headers=headers,
            params={
                "since": since,
                "per_page": 50,
            },
            timeout=15,
        )
        if resp.status_code == 409:
            # empty repo
            return []
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"failed to fetch commits for {repo}: {e}")
        return []


def fetch_commit_detail(username: str, repo: str, sha: str) -> dict:
    """Fetch a single commit's full detail (files + stats)."""
    headers = get_headers()
    try:
        resp = httpx.get(
            f"{GH_API}/repos/{username}/{repo}/commits/{sha}",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"failed to fetch commit detail {sha}: {e}")
    return {}


def parse_commit(repo: str, raw: dict) -> dict:
    commit = raw.get("commit", {})
    author = commit.get("author", {})
    files_data = raw.get("files", [])

    # extract file extensions
    extensions = []
    for f in files_data:
        ext = Path(f.get("filename", "")).suffix.lstrip(".")
        if ext:
            extensions.append(ext)

    timestamp = author.get("date", "")

    return {
        "repo": repo,
        "branch": "main",
        "sha": raw.get("sha", "")[:7],
        "message": commit.get("message", "").split("\n")[0][:120],
        "author": author.get("name", "unknown"),
        "timestamp": timestamp,
        "files_changed": raw.get("stats", {}).get("total", len(files_data)),
        "added": raw.get("stats", {}).get("additions", 0),
        "modified": 0,
        "removed": raw.get("stats", {}).get("deletions", 0),
        "extensions": extensions,
        "url": raw.get("html_url", ""),
    }


def get_since_datetime(utc_offset: int = 3) -> str:
    """Return ISO datetime for start of today in UTC."""
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # convert back to UTC for the API
    start_utc = start_of_day - timedelta(hours=utc_offset)
    return start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def poll() -> None:
    settings = load_json(SETTINGS_FILE)
    utc_offset = settings.get("utc_offset", 3)
    username = os.environ.get("GH_USERNAME", "")

    if not username:
        print("GH_USERNAME not set")
        return

    today = get_today(utc_offset)
    since = get_since_datetime(utc_offset)

    print(f"polling all repos for {username} since {since}")

    # fetch all repos
    repos = fetch_all_repos(username)
    print(f"found {len(repos)} repos to check")

    log = load_json(LOG_FILE)
    log = ensure_day_entry(log, today)

    existing_shas = {c["sha"] for c in log[today]["commits"]}
    total_added = 0

    for owner, repo in repos:
        raw_commits = fetch_commits_since(owner, repo, since)
        for raw in raw_commits:
            sha = raw.get("sha", "")[:7]
            if sha in existing_shas:
                continue
            # Fetch full detail to get files and stats (list endpoint omits these)
            full_sha = raw.get("sha", "")
            detail = fetch_commit_detail(owner, repo, full_sha)
            if detail:
                raw = detail
            commit = parse_commit(repo, raw)
            log[today]["commits"].append(commit)
            existing_shas.add(sha)
            total_added += 1
            print(f"  [{owner}/{repo}] {sha} {commit['message'][:60]}")

    save_json(LOG_FILE, log)
    print(f"done — {total_added} new commit(s) logged for {today}")


if __name__ == "__main__":
    poll()
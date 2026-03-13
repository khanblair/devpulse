"""
devpulse — Department 2: Analyst
graveyard.py

No AI call. GitHub API only.
Detects repos with no commits in 14+ days.
Checks for open PRs older than 7 days across tracked repos.
Updates data/graveyard.json.
"""

import json
import os
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAVEYARD_FILE = ROOT / "data" / "graveyard.json"
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


def get_gh_headers() -> dict:
    token = os.environ.get("GH_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def days_since(date_str: str) -> int:
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 0


def update_graveyard(log: dict, settings: dict) -> None:
    threshold = settings.get("graveyard_threshold_days", 14)
    username = os.environ.get("GH_USERNAME", "")
    headers = get_gh_headers()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # find repos tracked in log
    all_repos: dict[str, str] = {}  # repo_name -> last_commit_date
    for date_str, entry in log.items():
        for commit in entry.get("commits", []):
            repo = commit["repo"]
            if repo not in all_repos or date_str > all_repos[repo]:
                all_repos[repo] = date_str

    abandoned_repos = []
    open_prs = []

    for repo_name, last_date in all_repos.items():
        try:
            last_dt = datetime.strptime(last_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_quiet = (datetime.now(timezone.utc) - last_dt).days
        except Exception:
            continue

        if days_quiet >= threshold:
            abandoned_repos.append({
                "name": repo_name,
                "last_commit_date": last_date,
                "days_quiet": days_quiet,
            })

        # check for open PRs on this repo
        if not username:
            continue

        try:
            pr_resp = httpx.get(
                f"{GH_API}/repos/{username}/{repo_name}/pulls",
                headers=headers,
                params={"state": "open", "per_page": 10},
                timeout=10,
            )
            if pr_resp.status_code == 200:
                for pr in pr_resp.json():
                    created = pr.get("created_at", "")
                    age_days = days_since(created)
                    if age_days >= 7:
                        open_prs.append({
                            "repo": repo_name,
                            "number": pr.get("number"),
                            "title": pr.get("title", "")[:80],
                            "days_open": age_days,
                            "url": pr.get("html_url", ""),
                        })
        except Exception as e:
            print(f"PR check failed for {repo_name}: {e}")

    graveyard = {
        "last_checked": today,
        "repos": sorted(abandoned_repos, key=lambda x: x["days_quiet"], reverse=True),
        "open_prs": sorted(open_prs, key=lambda x: x["days_open"], reverse=True),
    }

    save_json(GRAVEYARD_FILE, graveyard)
    print(
        f"graveyard updated: {len(abandoned_repos)} abandoned repo(s), "
        f"{len(open_prs)} open PR(s)"
    )

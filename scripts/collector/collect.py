"""
devpulse — Department 1: Collector
collect.py

Receives push webhook payload via repository_dispatch.
Parses commit data, appends to data/log.json.
No AI calls. No external services. Fast and silent.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT / "data" / "log.json"


def get_today(utc_offset: int = 3) -> str:
    now = datetime.now(timezone.utc)
    hour = (now.hour + utc_offset) % 24
    if now.hour + utc_offset >= 24:
        from datetime import timedelta
        now = now + timedelta(days=1)
    return now.strftime("%Y-%m-%d")


def load_log() -> dict:
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 0:
        with open(LOG_FILE) as f:
            return json.load(f)
    return {}


def save_log(log: dict) -> None:
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def parse_payload(payload: dict) -> list[dict]:
    commits = []
    repo = payload.get("repository", {}).get("name", "unknown")
    branch = payload.get("ref", "").replace("refs/heads/", "")

    for commit in payload.get("commits", []):
        added_files = commit.get("added", [])
        modified_files = commit.get("modified", [])
        removed_files = commit.get("removed", [])
        all_files = added_files + modified_files + removed_files

        # extract file extensions for language drift tracking
        extensions = []
        for f in all_files:
            ext = Path(f).suffix.lstrip(".")
            if ext:
                extensions.append(ext)

        commits.append({
            "repo": repo,
            "branch": branch,
            "sha": commit.get("id", "")[:7],
            "message": commit.get("message", "").split("\n")[0][:120],
            "author": commit.get("author", {}).get("name", "unknown"),
            "timestamp": commit.get("timestamp", ""),
            "files_changed": len(all_files),
            "added": len(added_files),
            "modified": len(modified_files),
            "removed": len(removed_files),
            "extensions": extensions,
            "url": commit.get("url", ""),
        })

    return commits


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


def record_commits(payload: dict) -> None:
    today = get_today()
    log = load_log()
    log = ensure_day_entry(log, today)

    new_commits = parse_payload(payload)
    if not new_commits:
        print("no commits found in payload")
        return

    existing_shas = {c["sha"] for c in log[today]["commits"]}
    added = 0
    for commit in new_commits:
        if commit["sha"] not in existing_shas:
            log[today]["commits"].append(commit)
            added += 1

    save_log(log)
    print(f"logged {added} commit(s) for {today}")


def main() -> None:
    raw = os.environ.get("PAYLOAD", "")
    if not raw:
        print("no PAYLOAD env var found")
        sys.exit(0)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"failed to parse payload: {e}")
        sys.exit(1)

    record_commits(payload)


if __name__ == "__main__":
    main()

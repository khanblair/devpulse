"""
devpulse — Department 2: Analyst
yoyo.py

No AI call.
Fetches today's latest commit from yologdev/yoyo-evolve
via the GitHub public API.
Also reads DAY_COUNT file to get the current day number.
"""

import os
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path

YOYO_REPO = "yologdev/yoyo-evolve"
GH_API = "https://api.github.com"


def get_today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_yoyo() -> dict:
    token = os.environ.get("GH_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    today = get_today_utc()
    result = {
        "day": None,
        "message": None,
        "sha": None,
        "summary": None,
        "date": today,
    }

    try:
        # fetch latest commits
        resp = httpx.get(
            f"{GH_API}/repos/{YOYO_REPO}/commits",
            headers=headers,
            params={"per_page": 5},
            timeout=15,
        )
        resp.raise_for_status()
        commits = resp.json()

        # find today's commit
        today_commit = None
        for commit in commits:
            commit_date = commit.get("commit", {}).get("author", {}).get("date", "")
            if commit_date.startswith(today):
                today_commit = commit
                break

        # fallback to most recent if none today
        if not today_commit and commits:
            today_commit = commits[0]

        if today_commit:
            result["sha"] = today_commit.get("sha", "")[:7]
            message = today_commit.get("commit", {}).get("message", "")
            result["message"] = message.split("\n")[0][:120]

        # fetch DAY_COUNT file
        day_resp = httpx.get(
            f"{GH_API}/repos/{YOYO_REPO}/contents/DAY_COUNT",
            headers=headers,
            timeout=10,
        )
        if day_resp.status_code == 200:
            import base64
            content = day_resp.json().get("content", "")
            day_count = base64.b64decode(content).decode("utf-8").strip()
            result["day"] = int(day_count) if day_count.isdigit() else None

        # fetch latest JOURNAL.md entry for summary
        journal_resp = httpx.get(
            f"{GH_API}/repos/{YOYO_REPO}/contents/JOURNAL.md",
            headers=headers,
            timeout=10,
        )
        if journal_resp.status_code == 200:
            import base64
            content = journal_resp.json().get("content", "")
            journal = base64.b64decode(content).decode("utf-8")
            # extract first entry — lines after first "###" heading
            lines = journal.split("\n")
            summary_lines = []
            in_entry = False
            for line in lines:
                if line.startswith("###") and not in_entry:
                    in_entry = True
                    continue
                if in_entry:
                    if line.startswith("###") or line.startswith("## "):
                        break
                    if line.strip():
                        summary_lines.append(line.strip())
                    if len(summary_lines) >= 2:
                        break
            if summary_lines:
                result["summary"] = " ".join(summary_lines)[:200]

    except Exception as e:
        print(f"yoyo fetch failed: {e}")

    return result

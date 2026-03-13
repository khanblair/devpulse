"""
devpulse — Department 2: Analyst
weekly_report.py

Groq call #4 — Sunday only.
Generates a deep written analysis of the week.
Factors in targets, mood patterns, yoyo comparison,
graveyard, and language drift.
Returns 3-4 paragraphs of plain prose.
"""

import os
import json
import httpx
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAVEYARD_FILE = ROOT / "data" / "graveyard.json"
FINGERPRINT_FILE = ROOT / "data" / "fingerprint.json"
TARGETS_HISTORY_FILE = ROOT / "data" / "targets_history.json"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def load_json(path: Path) -> dict:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def get_week_dates(today: str) -> list[str]:
    base = datetime.strptime(today, "%Y-%m-%d")
    monday = base - timedelta(days=base.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def generate_weekly_report(
    log: dict,
    today: str,
    target_report: dict | None,
    settings: dict,
) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "Weekly report unavailable — no API key."

    model = settings.get("groq_model", "groq/compound")
    name = settings.get("name", "Dev")
    week_dates = get_week_dates(today)

    # gather week data
    all_commits = []
    moods = []
    yoyo_entries = []
    repos: dict[str, int] = {}

    for d in week_dates:
        entry = log.get(d, {})
        commits = entry.get("commits", [])
        all_commits.extend(commits)
        if entry.get("mood"):
            moods.append(entry["mood"])
        if entry.get("yoyo"):
            yoyo_entries.append(entry["yoyo"])
        for c in commits:
            repos[c["repo"]] = repos.get(c["repo"], 0) + 1

    if not all_commits:
        return "No commits this week."

    feat = sum(1 for c in all_commits if c["message"].startswith("feat"))
    fix = sum(1 for c in all_commits if c["message"].startswith("fix"))
    chore = sum(1 for c in all_commits if c["message"].startswith("chore"))
    days_active = sum(1 for d in week_dates if log.get(d, {}).get("commits"))
    top_repo = max(repos, key=repos.get) if repos else "none"
    quiet_repos = [r for r, c in repos.items() if c <= 1]

    # graveyard
    graveyard = load_json(GRAVEYARD_FILE)
    graveyard_repos = [r["name"] for r in graveyard.get("repos", [])]

    # fingerprint context
    fp = load_json(FINGERPRINT_FILE)

    # targets history — check if patterns exist
    history = load_json(TARGETS_HISTORY_FILE)
    past_weeks = history.get("weeks", [])[-4:]
    repeat_misses = []
    if target_report and past_weeks:
        current_misses = {
            k for k, v in target_report.get("scores", {}).items()
            if v.get("pct", 100) < 80
        }
        for week in past_weeks:
            week_misses = {
                k for k, v in week.get("scores", {}).items()
                if v.get("pct", 100) < 80
            }
            repeat_misses.extend(current_misses & week_misses)

    # yoyo summary
    yoyo_summary = ""
    if yoyo_entries:
        yoyo_days = len(yoyo_entries)
        yoyo_messages = [y.get("message", "") for y in yoyo_entries if y.get("message")]
        yoyo_summary = f"yoyo-evolve shipped {yoyo_days} commit(s) this week: {'; '.join(yoyo_messages[:3])}"

    # targets summary
    target_summary = ""
    if target_report:
        scores = target_report.get("scores", {})
        hit = sum(1 for v in scores.values() if v.get("pct", 0) >= 100)
        total_targets = len(scores)
        target_summary = f"Hit {hit}/{total_targets} targets."
        if repeat_misses:
            target_summary += f" Repeated misses: {', '.join(set(repeat_misses))}."

    prompt = (
        f"Write a weekly developer report for {name}.\n\n"
        f"Week ending {today}:\n"
        f"- {len(all_commits)} commits across {len(repos)} repos over {days_active} active days\n"
        f"- feat: {feat}, fix: {fix}, chore: {chore}\n"
        f"- Most active repo: {top_repo}\n"
        f"- Quiet repos: {', '.join(quiet_repos) if quiet_repos else 'none'}\n"
        f"- Moods: {', '.join(moods) if moods else 'not recorded'}\n"
        f"- Graveyard: {', '.join(graveyard_repos) if graveyard_repos else 'none'}\n"
        f"- {target_summary}\n"
        f"- {yoyo_summary}\n\n"
        f"Write 3-4 short paragraphs. Rules:\n"
        f"- Plain honest prose, first person\n"
        f"- Paragraph 1: what the week actually looked like\n"
        f"- Paragraph 2: patterns worth noticing (targets, moods, repo activity)\n"
        f"- Paragraph 3: one concrete recommendation for next week\n"
        f"- Paragraph 4 (optional): yoyo comparison — what the AI shipped vs what you shipped\n"
        f"- Not motivational. Not corporate. Honest.\n"
        f"- Max 150 words total.\n\n"
        f"Write the report now:"
    )

    try:
        resp = httpx.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.6,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"weekly report generation failed: {e}")
        return (
            f"Week of {today}: {len(all_commits)} commits across "
            f"{len(repos)} repos over {days_active} days. "
            f"Most active in {top_repo}."
        )

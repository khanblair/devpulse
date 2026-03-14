"""
devpulse — Department 3: Publisher
build_site.py

Reads all data files and generates docs/index.html.
Uses Jinja2 for templating.
Embeds SVG graphs inline.
Dark, clean aesthetic. Zero JS dependencies on the output page.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT / "data" / "log.json"
FINGERPRINT_FILE = ROOT / "data" / "fingerprint.json"
GRAVEYARD_FILE = ROOT / "data" / "graveyard.json"
DRIFT_FILE = ROOT / "data" / "drift.json"
TARGETS_HISTORY_FILE = ROOT / "data" / "targets_history.json"
SETTINGS_FILE = ROOT / "config" / "settings.json"
TEMPLATES_DIR = ROOT / "templates"
DOCS_DIR = ROOT / "docs"
ASSETS_DIR = DOCS_DIR / "assets"

DOCS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def load_svg(name: str) -> str:
    path = ASSETS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f'<div class="no-data">Graph not yet generated</div>'


def get_today(utc_offset: int = 3) -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    return now.strftime("%Y-%m-%d")


def streak_count(log: dict, today: str) -> int:
    count = 0
    check = datetime.strptime(today, "%Y-%m-%d")
    while True:
        d = check.strftime("%Y-%m-%d")
        if log.get(d, {}).get("commits"):
            count += 1
            check -= timedelta(days=1)
        else:
            break
    return count


def day_number(log: dict) -> int:
    return sum(1 for entry in log.values() if entry.get("commits"))


def get_last_n_days(n: int) -> list[str]:
    today = datetime.now(timezone.utc)
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(n))]


def get_week_dates(today: str) -> list[str]:
    base = datetime.strptime(today, "%Y-%m-%d")
    monday = base - timedelta(days=base.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def build_context(log: dict, settings: dict) -> dict:
    utc_offset = settings.get("utc_offset", 3)
    today = get_today(utc_offset)
    entry = log.get(today, {})
    commits = entry.get("commits", [])
    week_dates = get_week_dates(today)

    # today stats
    repos_today: dict[str, list] = {}
    for c in commits:
        repos_today.setdefault(c["repo"], []).append(c)

    # week stats
    week_commits = []
    for d in week_dates:
        week_commits.extend(log.get(d, {}).get("commits", []))

    # all time
    all_commits = []
    for e in log.values():
        all_commits.extend(e.get("commits", []))

    # mood last 30 days for timeline
    mood_timeline = []
    for d in get_last_n_days(30):
        e = log.get(d, {})
        mood_timeline.append({
            "date": d,
            "mood": e.get("mood"),
            "count": len(e.get("commits", [])),
            "devlog": e.get("devlog", ""),
        })

    # recent daily entries for journal section
    recent_days = []
    for d in sorted(log.keys(), reverse=True)[:14]:
        e = log[d]
        if e.get("commits") or e.get("devlog"):
            recent_days.append({
                "date": d,
                "commits": e.get("commits", []),
                "mood": e.get("mood"),
                "devlog": e.get("devlog"),
                "yoyo": e.get("yoyo"),
            })

    fingerprint = load_json(FINGERPRINT_FILE)
    graveyard = load_json(GRAVEYARD_FILE)
    drift = load_json(DRIFT_FILE)
    targets_history = load_json(TARGETS_HISTORY_FILE)

    # weekly targets from today's target report
    target_report = entry.get("target_report") or {}
    # fallback to most recent sunday
    if not target_report:
        for d in sorted(log.keys(), reverse=True):
            if log[d].get("target_report"):
                target_report = log[d]["target_report"]
                break

    # last weekly question
    last_question = entry.get("question")
    if not last_question:
        for d in sorted(log.keys(), reverse=True):
            if log[d].get("question"):
                last_question = log[d]["question"]
                break

    # last weekly report
    last_weekly = entry.get("weekly_report")
    if not last_weekly:
        for d in sorted(log.keys(), reverse=True):
            if log[d].get("weekly_report"):
                last_weekly = log[d]["weekly_report"]
                break

    return {
        "settings": settings,
        "today": today,
        "day_number": day_number(log),
        "streak": streak_count(log, today),
        "total_commits": len(all_commits),
        "total_days": len([d for d in log if log[d].get("commits")]),
        "entry": entry,
        "commits_today": commits,
        "repos_today": repos_today,
        "week_commits": week_commits,
        "mood_timeline": mood_timeline,
        "recent_days": recent_days,
        "fingerprint": fingerprint,
        "graveyard": graveyard,
        "drift": drift,
        "targets_history": targets_history,
        "target_report": target_report,
        "last_question": last_question,
        "last_weekly": last_weekly,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "svg": {
            "mood_timeline": load_svg("mood-timeline.svg"),
            "commit_heatmap": load_svg("commit-heatmap.svg"),
            "language_drift": load_svg("language-drift.svg"),
            "hourly_pattern": load_svg("hourly-pattern.svg"),
            "repo_activity": load_svg("repo-activity.svg"),
            "streak_chart": load_svg("streak-chart.svg"),
            "targets_scorecard": load_svg("targets-scorecard.svg"),
        },
    }


def render_site(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("site.html")
    return template.render(**context)


def main() -> None:
    settings = load_json(SETTINGS_FILE)
    log = load_json(LOG_FILE)

    print("building context...")
    context = build_context(log, settings)

    print("rendering site...")
    html = render_site(context)

    output = DOCS_DIR / "index.html"
    output.write_text(html, encoding="utf-8")
    print(f"site written to {output}")


if __name__ == "__main__":
    main()

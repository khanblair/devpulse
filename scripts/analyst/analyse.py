"""
devpulse — Department 2: Analyst
analyse.py

Orchestrator. Runs every evening at 9pm Kampala time.
Calls each analyst module in order.
Makes all Groq API calls for the day (max 4 on weekdays, 4 on Sundays).
Commits enriched data and generated graphs back to repo.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.analyst.mood import infer_mood
from scripts.analyst.devlog import generate_devlog
from scripts.analyst.yoyo import fetch_yoyo
from scripts.analyst.fingerprint import update_fingerprint
from scripts.analyst.drift import update_drift
from scripts.analyst.graveyard import update_graveyard
from scripts.analyst.targets import score_targets
from scripts.analyst.graphs import generate_all_graphs

LOG_FILE = ROOT / "data" / "log.json"
SETTINGS_FILE = ROOT / "config" / "settings.json"


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


def is_sunday(utc_offset: int = 3) -> bool:
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    return now.weekday() == 6


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


def main() -> None:
    settings = load_json(SETTINGS_FILE)
    utc_offset = settings.get("utc_offset", 3)
    today = get_today(utc_offset)
    sunday = is_sunday(utc_offset)

    print(f"analyst running for {today} (sunday={sunday})")

    log = load_json(LOG_FILE)
    log = ensure_day_entry(log, today)
    entry = log[today]
    commits = entry.get("commits", [])

    # ── Step 1: fetch yoyo-evolve (no AI) ─────────────────────────────────────
    print("fetching yoyo-evolve...")
    yoyo_data = fetch_yoyo()
    entry["yoyo"] = yoyo_data
    print(f"yoyo: day {yoyo_data.get('day')} — {yoyo_data.get('message', 'no commit today')}")

    # ── Step 2: infer mood (Groq call #1) ─────────────────────────────────────
    if commits:
        print("inferring mood...")
        mood = infer_mood(commits, settings)
        entry["mood"] = mood
        print(f"mood: {mood}")
    else:
        print("no commits today — skipping mood inference")
        entry["mood"] = "no commits"

    # ── Step 3: generate dev log (Groq call #2) ───────────────────────────────
    if commits:
        print("generating dev log...")
        devlog = generate_devlog(commits, today, settings)
        entry["devlog"] = devlog
        print(f"devlog: {devlog[:60]}...")
    else:
        entry["devlog"] = "No commits today."

    # ── Step 4: update fingerprint (no AI) ────────────────────────────────────
    print("updating fingerprint...")
    update_fingerprint(log)

    # ── Step 5: update language drift (no AI) ─────────────────────────────────
    print("updating language drift...")
    update_drift(log)

    # ── Step 6: update graveyard (GitHub API, no AI) ──────────────────────────
    print("checking graveyard...")
    update_graveyard(log, settings)

    # ── Step 7: score targets (no AI) ─────────────────────────────────────────
    print("scoring targets...")
    target_report = score_targets(log, today)
    entry["target_report"] = target_report

    # ── Step 8: Sunday-only deep analysis ─────────────────────────────────────
    if sunday:
        from scripts.analyst.question import generate_question
        from scripts.analyst.weekly_report import generate_weekly_report

        print("sunday — generating honest question (Groq call #3)...")
        question = generate_question(log, today, target_report, settings)
        entry["question"] = question
        print(f"question: {question[:80]}...")

        print("sunday — generating weekly report (Groq call #4)...")
        weekly = generate_weekly_report(log, today, target_report, settings)
        entry["weekly_report"] = weekly
        print(f"weekly report: {weekly[:60]}...")

    # ── Save enriched log ──────────────────────────────────────────────────────
    log[today] = entry
    save_json(LOG_FILE, log)
    print("log saved")

    # ── Step 9: generate graphs (no AI) ───────────────────────────────────────
    print("generating graphs...")
    generate_all_graphs(log)
    print("graphs saved to docs/assets/")

    print("analyst complete")


if __name__ == "__main__":
    main()

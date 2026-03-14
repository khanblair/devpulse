"""
devpulse — Department 3: Publisher
telegram.py

Sends the daily digest or Sunday weekly report to Telegram.
Reads from enriched log.json. No AI calls.
Weekdays: compact daily format.
Sundays: deep weekly format with targets scorecard.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT / "data" / "log.json"
FINGERPRINT_FILE = ROOT / "data" / "fingerprint.json"
GRAVEYARD_FILE = ROOT / "data" / "graveyard.json"
TARGETS_HISTORY_FILE = ROOT / "data" / "targets_history.json"
SETTINGS_FILE = ROOT / "config" / "settings.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def load_json(path: Path) -> dict:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def get_today(utc_offset: int = 3) -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    return now.strftime("%Y-%m-%d")


def is_sunday(utc_offset: int = 3) -> bool:
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    return now.weekday() == 6


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


def progress_bar(value: int, target: int, width: int = 8) -> str:
    if target == 0:
        return "░" * width
    filled = min(int((value / target) * width), width)
    return "█" * filled + "░" * (width - filled)


def esc(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_message(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return False

    try:
        resp = httpx.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        resp.raise_for_status()
        print("telegram message sent")
        return True
    except Exception as e:
        print(f"telegram send failed: {e}")
        return False


def format_daily(log: dict, today: str, settings: dict) -> str:
    entry = log.get(today, {})
    commits = entry.get("commits", [])
    mood = entry.get("mood", "")
    devlog = entry.get("devlog", "")
    yoyo = entry.get("yoyo", {}) or {}
    target_report = entry.get("target_report", {}) or {}
    streak = streak_count(log, today)
    day_n = day_number(log)
    site_url = settings.get("site_url", "")

    dt = datetime.strptime(today, "%Y-%m-%d")
    day_name = dt.strftime("%A %b %d")

    lines = []
    lines.append(f"📅 <b>{esc(day_name)}</b> — Day {day_n}  🔥 {streak}-day streak\n")

    if not commits:
        lines.append("<i>No commits today.</i>")
    else:
        # group by repo
        repos: dict[str, list] = {}
        for c in commits:
            repos.setdefault(c["repo"], []).append(c)

        for repo, repo_commits in repos.items():
            lines.append(f"<code>{esc(repo)}</code> · {len(repo_commits)} commit(s)")
            for c in repo_commits[:5]:
                lines.append(f"  {c['sha']} {esc(c['message'][:60])}")
            if len(repo_commits) > 5:
                lines.append(f"  <i>...and {len(repo_commits) - 5} more</i>")

        total_files = sum(c.get("files_changed", 0) for c in commits)
        total_added = sum(c.get("added", 0) for c in commits)
        total_removed = sum(c.get("removed", 0) for c in commits)
        lines.append(
            f"\n{len(commits)} commits · {total_files} files · "
            f"+{total_added} / -{total_removed} lines"
        )
        if mood:
            lines.append(f"mood: <i>{esc(mood)}</i>")

    if devlog and devlog != "No commits today.":
        lines.append(f"\n<i>{esc(devlog)}</i>")

    if yoyo.get("message"):
        day_label = f"Day {yoyo['day']}" if yoyo.get("day") else ""
        lines.append(f"\n🤖 <b>yoyo-evolve</b> {esc(day_label)}")
        lines.append(f"<code>{esc(yoyo['message'][:80])}</code>")

    # daily target check
    if target_report and target_report.get("scores"):
        scores = target_report["scores"]
        missed = [k for k, v in scores.items() if v.get("status") == "missed"]
        if missed:
            lines.append(f"\n⚠️ Behind on: {esc(', '.join(missed))}")

    if site_url:
        lines.append(f"\n📋 <a href=\"{esc(site_url)}\">Full report</a>")

    return "\n".join(lines)


def format_weekly(log: dict, today: str, settings: dict) -> str:
    entry = log.get(today, {})
    weekly_report = entry.get("weekly_report", "")
    question = entry.get("question", "")
    target_report = entry.get("target_report", {}) or {}
    yoyo = entry.get("yoyo", {}) or {}
    site_url = settings.get("site_url", "")

    dt = datetime.strptime(today, "%Y-%m-%d")
    week_num = dt.isocalendar()[1]

    # gather week stats
    week_dates = [
        (dt - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(7)
    ]
    all_commits = []
    for d in week_dates:
        all_commits.extend(log.get(d, {}).get("commits", []))

    repos = set(c["repo"] for c in all_commits)
    days_active = sum(1 for d in week_dates if log.get(d, {}).get("commits"))

    lines = []
    lines.append(f"📊 <b>Week {week_num} — deep report</b>\n")
    lines.append(
        f"{len(all_commits)} commits · {len(repos)} repos · "
        f"{days_active} active days\n"
    )

    if weekly_report:
        lines.append(esc(weekly_report))
        lines.append("")

    # targets scorecard
    if target_report and target_report.get("scores"):
        scores = target_report["scores"]
        repo_scores = target_report.get("repo_scores", {})
        summary = target_report.get("summary", {})

        lines.append(f"🎯 <b>Targets — {summary.get('hit', 0)}/{summary.get('total', 0)} hit</b>\n")

        for key, score in scores.items():
            bar = progress_bar(score["actual"], score["target"])
            pct = score["pct"]
            icon = "✅" if score["status"] == "hit" else "🔶" if score["status"] == "close" else "❌"
            label = key.replace("_", " ")
            lines.append(
                f"<code>{esc(label):<16}</code> {score['actual']:>3}/{score['target']:<3} "
                f"{bar} {pct}% {icon}"
            )

        if repo_scores:
            lines.append("")
            for repo, score in repo_scores.items():
                bar = progress_bar(score["actual"], score["target"])
                icon = "✅" if score["status"] == "hit" else "🔶" if score["status"] == "close" else "❌"
                lines.append(
                    f"<code>{esc(repo[:16]):<16}</code> {score['actual']:>3}/{score['target']:<3} "
                    f"{bar} {score['pct']}% {icon}"
                )

    if question:
        lines.append(f"\n❓ <i>{esc(question)}</i>")

    if yoyo.get("message"):
        day_label = f"Day {yoyo['day']}" if yoyo.get("day") else ""
        lines.append(f"\n🤖 <b>yoyo this week</b> {esc(day_label)}")
        lines.append(f"<code>{esc(yoyo['message'][:80])}</code>")
        if yoyo.get("summary"):
            lines.append(f"<i>{esc(yoyo['summary'][:120])}</i>")

    if site_url:
        lines.append(f"\n📋 <a href=\"{esc(site_url)}\">Full report + graphs</a>")

    return "\n".join(lines)


def main() -> None:
    settings = load_json(SETTINGS_FILE)
    utc_offset = settings.get("utc_offset", 3)
    today = get_today(utc_offset)
    log = load_json(LOG_FILE)
    sunday = is_sunday(utc_offset)

    if sunday:
        print(f"sending sunday weekly report for {today}")
        message = format_weekly(log, today, settings)
    else:
        print(f"sending daily digest for {today}")
        message = format_daily(log, today, settings)

    ok = send_message(message)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

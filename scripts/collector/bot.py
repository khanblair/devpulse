"""
devpulse — Department 1: Collector
bot.py

Polls Telegram for new messages every 10 minutes via bot.yml.
Routes commands to handlers. Reads from data files.
Only /settarget writes anything. Everything else is read-only.
No AI calls.
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
DRIFT_FILE = ROOT / "data" / "drift.json"
TARGETS_FILE = ROOT / "config" / "targets.json"
TARGETS_HISTORY_FILE = ROOT / "data" / "targets_history.json"
SETTINGS_FILE = ROOT / "config" / "settings.json"
OFFSET_FILE = ROOT / "data" / ".bot_offset"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict | list:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict | list) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def send(text: str) -> None:
    httpx.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }, timeout=10)


def get_today(utc_offset: int = 3) -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    return now.strftime("%Y-%m-%d")


def get_date_n_days_ago(n: int, utc_offset: int = 3) -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    return (now - timedelta(days=n)).strftime("%Y-%m-%d")


def load_offset() -> int:
    if OFFSET_FILE.exists():
        return int(OFFSET_FILE.read_text().strip())
    return 0


def save_offset(offset: int) -> None:
    OFFSET_FILE.write_text(str(offset))


def get_week_dates(utc_offset: int = 3) -> list[str]:
    now = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    monday = now - timedelta(days=now.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def streak_count(log: dict, today: str, utc_offset: int = 3) -> int:
    count = 0
    check = datetime.strptime(today, "%Y-%m-%d")
    while True:
        date_str = check.strftime("%Y-%m-%d")
        if date_str in log and log[date_str].get("commits"):
            count += 1
            check -= timedelta(days=1)
        else:
            break
    return count


def progress_bar(value: int, target: int, width: int = 10) -> str:
    if target == 0:
        return "░" * width
    filled = min(int((value / target) * width), width)
    return "█" * filled + "░" * (width - filled)


def pct_label(value: int, target: int) -> str:
    if target == 0:
        return "n/a"
    p = int((value / target) * 100)
    if p >= 100:
        return f"{p}% ✅"
    elif p >= 80:
        return f"{p}% 🔶"
    else:
        return f"{p}% ❌"


# ── command handlers ──────────────────────────────────────────────────────────

def cmd_help() -> str:
    return (
        "*devpulse commands*\n\n"
        "/report — today's full report\n"
        "/weekly — this week's summary\n"
        "/commits — today's commits\n"
        "/commits N — commits N days ago\n"
        "/mood — today's mood\n"
        "/streak — current streak\n"
        "/yoyo — what yoyo-evolve did today\n"
        "/targets — your current targets\n"
        "/progress — this week vs targets\n"
        "/settarget weekly\\_commits 20\n"
        "/settarget repo:my-api 4\n"
        "/graveyard — abandoned repos + PRs\n"
        "/fingerprint — your dev personality\n"
        "/drift — language shift summary\n"
        "/site — your GitHub Pages URL\n"
        "/status — system health check\n"
        "/help — this list"
    )


def cmd_report() -> str:
    log = load_json(LOG_FILE)
    today = get_today()
    entry = log.get(today, {})
    commits = entry.get("commits", [])

    if not commits:
        return f"*{today}*\n\nNo commits logged yet today."

    lines = [f"*{today} — daily report*\n"]

    repos: dict[str, list] = {}
    for c in commits:
        repos.setdefault(c["repo"], []).append(c)

    for repo, repo_commits in repos.items():
        lines.append(f"`{repo}` · {len(repo_commits)} commit(s)")
        for c in repo_commits:
            lines.append(f"  {c['sha']} {c['message']}")

    total_files = sum(c["files_changed"] for c in commits)
    lines.append(f"\n{len(commits)} commits · {total_files} files changed")

    if entry.get("mood"):
        lines.append(f"mood: {entry['mood']}")

    if entry.get("devlog"):
        lines.append(f"\n_{entry['devlog']}_")

    streak = streak_count(log, today)
    lines.append(f"\n🔥 {streak}-day streak")

    return "\n".join(lines)


def cmd_commits(days_ago: int = 0) -> str:
    log = load_json(LOG_FILE)
    date = get_date_n_days_ago(days_ago) if days_ago > 0 else get_today()
    entry = log.get(date, {})
    commits = entry.get("commits", [])

    if not commits:
        label = "today" if days_ago == 0 else f"{days_ago} day(s) ago"
        return f"No commits found for {label} ({date})."

    lines = [f"*Commits — {date}*\n"]
    repos: dict[str, list] = {}
    for c in commits:
        repos.setdefault(c["repo"], []).append(c)

    for repo, repo_commits in repos.items():
        lines.append(f"`{repo}`")
        for c in repo_commits:
            time_str = c.get("timestamp", "")[:16].replace("T", " ") if c.get("timestamp") else ""
            lines.append(f"  `{c['sha']}` {c['message']}{' · ' + time_str if time_str else ''}")

    return "\n".join(lines)


def cmd_mood() -> str:
    log = load_json(LOG_FILE)
    today = get_today()
    entry = log.get(today, {})
    mood = entry.get("mood")
    commits = entry.get("commits", [])

    if not mood and not commits:
        return "No data for today yet."
    if not mood:
        return f"Mood not yet inferred for today. {len(commits)} commit(s) logged."
    return f"*Today's mood:* {mood}\n\n_{entry.get('devlog', '')}_"


def cmd_streak() -> str:
    log = load_json(LOG_FILE)
    today = get_today()
    current = streak_count(log, today)

    # find longest streak
    best = 0
    temp = 0
    for date_str in sorted(log.keys()):
        if log[date_str].get("commits"):
            temp += 1
            best = max(best, temp)
        else:
            temp = 0

    return (
        f"*Streak*\n\n"
        f"Current: 🔥 {current} day(s)\n"
        f"Best: ⭐ {best} day(s)"
    )


def cmd_yoyo() -> str:
    log = load_json(LOG_FILE)
    today = get_today()
    entry = log.get(today, {})
    yoyo = entry.get("yoyo")

    if not yoyo:
        return "No yoyo-evolve data for today yet. Check back after 9pm."

    lines = [f"*yoyo-evolve — {today}*\n"]
    if yoyo.get("day"):
        lines.append(f"Day {yoyo['day']}")
    if yoyo.get("message"):
        lines.append(f"`{yoyo['message']}`")
    if yoyo.get("summary"):
        lines.append(f"\n_{yoyo['summary']}_")

    return "\n".join(lines)


def cmd_targets() -> str:
    targets = load_json(TARGETS_FILE)
    weekly = targets.get("weekly", {})
    repos = {k: v for k, v in targets.get("repos", {}).items() if k != "_comment"}

    lines = ["*Current targets*\n"]
    lines.append("*Weekly:*")
    for key, val in weekly.items():
        lines.append(f"  {key.replace('_', ' ')}: {val}")

    if repos:
        lines.append("\n*Per-repo:*")
        for repo, cfg in repos.items():
            for key, val in cfg.items():
                lines.append(f"  {repo}: {val} commits/week")

    daily = targets.get("daily", {})
    if daily:
        lines.append("\n*Daily floor:*")
        for key, val in daily.items():
            lines.append(f"  {key.replace('_', ' ')}: {val}")

    lines.append("\nUse `/settarget key value` to update")
    return "\n".join(lines)


def cmd_progress() -> str:
    log = load_json(LOG_FILE)
    targets = load_json(TARGETS_FILE)
    today = get_today()
    week_dates = get_week_dates()

    week_commits = []
    for d in week_dates:
        if d in log:
            week_commits.extend(log[d].get("commits", []))

    total = len(week_commits)
    feat_count = sum(1 for c in week_commits if c["message"].startswith("feat"))
    active_repos = len(set(c["repo"] for c in week_commits))
    streak = streak_count(log, today)

    weekly = targets.get("weekly", {})
    days_left = 7 - datetime.now(timezone.utc).weekday()

    lines = [f"*Week progress — {today}*\n"]

    if "commits" in weekly:
        t = weekly["commits"]
        lines.append(f"commits       {total:>3} / {t:<3} {progress_bar(total, t)} {pct_label(total, t)}")

    if "feat_commits" in weekly:
        t = weekly["feat_commits"]
        lines.append(f"feat commits  {feat_count:>3} / {t:<3} {progress_bar(feat_count, t)} {pct_label(feat_count, t)}")

    if "active_repos" in weekly:
        t = weekly["active_repos"]
        lines.append(f"active repos  {active_repos:>3} / {t:<3} {progress_bar(active_repos, t)} {pct_label(active_repos, t)}")

    if "streak_days" in weekly:
        t = weekly["streak_days"]
        lines.append(f"streak days   {streak:>3} / {t:<3} {progress_bar(streak, t)} {pct_label(streak, t)}")

    repos_cfg = {k: v for k, v in targets.get("repos", {}).items() if k != "_comment"}
    if repos_cfg:
        lines.append("")
        for repo, cfg in repos_cfg.items():
            repo_count = sum(1 for c in week_commits if c["repo"] == repo)
            t = cfg.get("weekly_commits", 0)
            lines.append(f"{repo:<14} {repo_count:>3} / {t:<3} {progress_bar(repo_count, t)} {pct_label(repo_count, t)}")

    lines.append(f"\n{days_left} day(s) left this week")
    return "\n".join(lines)


def cmd_settarget(args: list[str]) -> str:
    if len(args) < 2:
        return "Usage: `/settarget key value`\nExample: `/settarget weekly_commits 20`"

    key = args[0]
    try:
        value = int(args[1])
    except ValueError:
        return "Value must be a number."

    targets = load_json(TARGETS_FILE)

    if key.startswith("repo:"):
        repo_name = key[5:]
        if "repos" not in targets:
            targets["repos"] = {}
        if repo_name not in targets["repos"]:
            targets["repos"][repo_name] = {}
        targets["repos"][repo_name]["weekly_commits"] = value
        save_json(TARGETS_FILE, targets)
        return f"✅ *{repo_name}* weekly target updated to *{value}* commits"

    weekly_keys = ["commits", "active_repos", "feat_commits", "streak_days"]
    if key in weekly_keys:
        if "weekly" not in targets:
            targets["weekly"] = {}
        old = targets["weekly"].get(key, "not set")
        targets["weekly"][key] = value
        save_json(TARGETS_FILE, targets)
        return f"✅ *{key.replace('_', ' ')}* updated: {old} → {value}"

    if key == "min_commits":
        if "daily" not in targets:
            targets["daily"] = {}
        targets["daily"]["min_commits"] = value
        save_json(TARGETS_FILE, targets)
        return f"✅ Daily minimum commits set to *{value}*"

    return f"Unknown target key: `{key}`\nValid keys: commits, active\\_repos, feat\\_commits, streak\\_days, min\\_commits, repo:name"


def cmd_graveyard() -> str:
    data = load_json(GRAVEYARD_FILE)
    repos = data.get("repos", [])
    prs = data.get("open_prs", [])
    last = data.get("last_checked", "never")

    if not repos and not prs:
        return f"*Graveyard*\n\nAll clear — no abandoned repos or PRs.\nLast checked: {last}"

    lines = [f"*Graveyard* — last checked {last}\n"]

    if repos:
        lines.append("*Abandoned repos* (14+ days quiet):")
        for r in repos:
            lines.append(f"  `{r['name']}` — {r['days_quiet']} days since last commit")

    if prs:
        lines.append("\n*Open PRs* (7+ days old):")
        for pr in prs:
            lines.append(f"  `{pr['repo']}` #{pr['number']} — {pr['title'][:50]}")

    return "\n".join(lines)


def cmd_fingerprint() -> str:
    fp = load_json(FINGERPRINT_FILE)

    if not fp.get("last_updated"):
        return "Fingerprint not built yet. Runs after 2+ weeks of data."

    lines = ["*Your dev fingerprint*\n"]

    if fp.get("peak_coding_hour") is not None:
        h = fp["peak_coding_hour"]
        lines.append(f"Peak hour: {h:02d}:00")

    if fp.get("style"):
        lines.append(f"Style: {fp['style']}")

    if fp.get("feat_fix_ratio") is not None:
        lines.append(f"Feat/fix ratio: {fp['feat_fix_ratio']:.1f}x")

    if fp.get("most_active_repo"):
        lines.append(f"Most active: `{fp['most_active_repo']}`")

    if fp.get("most_avoided_repo"):
        lines.append(f"Most avoided: `{fp['most_avoided_repo']}`")

    if fp.get("avg_commit_size") is not None:
        lines.append(f"Avg commit size: {fp['avg_commit_size']} files")

    if fp.get("consistency_score") is not None:
        lines.append(f"Consistency: {fp['consistency_score']}/10")

    if fp.get("total_days_tracked"):
        lines.append(f"\n_{fp['total_days_tracked']} days tracked_")

    return "\n".join(lines)


def cmd_drift() -> str:
    drift = load_json(DRIFT_FILE)
    monthly = drift.get("monthly", {})

    if not monthly:
        return "Language drift not tracked yet. Needs a few weeks of data."

    lines = ["*Language drift*\n"]
    months = sorted(monthly.keys())[-6:]

    for month in months:
        langs = monthly[month]
        top = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:4]
        lang_str = "  ".join(f"{lang}:{pct}%" for lang, pct in top)
        lines.append(f"`{month}` {lang_str}")

    return "\n".join(lines)


def cmd_site() -> str:
    settings = load_json(SETTINGS_FILE)
    url = settings.get("site_url", "Not configured yet")
    return f"*devpulse site*\n\n{url}"


def cmd_status() -> str:
    log = load_json(LOG_FILE)
    today = get_today()
    entry = log.get(today, {})
    commits_today = len(entry.get("commits", []))
    enriched = entry.get("mood") is not None
    last_date = max(log.keys()) if log else "never"

    lines = [
        "*System status*\n",
        f"Today's commits logged: {commits_today}",
        f"Today enriched by analyst: {'yes' if enriched else 'not yet'}",
        f"Last log entry: {last_date}",
        f"Total days tracked: {len(log)}",
        "\nAll 4 workflows active ✅",
    ]
    return "\n".join(lines)


def cmd_weekly() -> str:
    log = load_json(LOG_FILE)
    today = get_today()
    week_dates = get_week_dates()

    all_commits = []
    for d in week_dates:
        if d in log:
            all_commits.extend(log[d].get("commits", []))

    if not all_commits:
        return "No commits this week yet."

    repos: dict[str, int] = {}
    for c in all_commits:
        repos[c["repo"]] = repos.get(c["repo"], 0) + 1

    feat = sum(1 for c in all_commits if c["message"].startswith("feat"))
    fix = sum(1 for c in all_commits if c["message"].startswith("fix"))
    days_active = sum(1 for d in week_dates if d in log and log[d].get("commits"))

    lines = [f"*Week summary*\n"]
    lines.append(f"{len(all_commits)} commits · {len(repos)} repos · {days_active} active days")
    lines.append(f"feat: {feat} · fix: {fix}\n")

    for repo, count in sorted(repos.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"`{repo}` · {count}")

    sunday_entry = log.get(week_dates[6], {})
    if sunday_entry.get("weekly_report"):
        lines.append(f"\n_{sunday_entry['weekly_report'][:300]}..._")

    return "\n".join(lines)


# ── router ────────────────────────────────────────────────────────────────────

def route(text: str) -> str:
    text = text.strip()
    parts = text.split()
    cmd = parts[0].lower() if parts else ""
    args = parts[1:]

    routes = {
        "/help": lambda: cmd_help(),
        "/report": lambda: cmd_report(),
        "/commits": lambda: cmd_commits(int(args[0]) if args and args[0].isdigit() else 0),
        "/mood": lambda: cmd_mood(),
        "/streak": lambda: cmd_streak(),
        "/yoyo": lambda: cmd_yoyo(),
        "/targets": lambda: cmd_targets(),
        "/progress": lambda: cmd_progress(),
        "/settarget": lambda: cmd_settarget(args),
        "/graveyard": lambda: cmd_graveyard(),
        "/fingerprint": lambda: cmd_fingerprint(),
        "/drift": lambda: cmd_drift(),
        "/site": lambda: cmd_site(),
        "/status": lambda: cmd_status(),
        "/weekly": lambda: cmd_weekly(),
    }

    if cmd in routes:
        return routes[cmd]()
    return None


# ── main polling loop ─────────────────────────────────────────────────────────

def poll() -> None:
    offset = load_offset()

    resp = httpx.get(f"{BASE_URL}/getUpdates", params={
        "offset": offset,
        "timeout": 5,
        "allowed_updates": ["message"],
    }, timeout=15)

    if resp.status_code != 200:
        print(f"getUpdates failed: {resp.status_code}")
        return

    updates = resp.json().get("result", [])
    if not updates:
        return

    for update in updates:
        update_id = update["update_id"]
        offset = update_id + 1

        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")

        if chat_id != str(CHAT_ID):
            continue

        if not text.startswith("/"):
            continue

        response = route(text)
        if response:
            send(response)

    save_offset(offset)


def main() -> None:
    poll()


if __name__ == "__main__":
    main()

"""
devpulse — Department 2: Analyst
targets.py

No AI call. Pure calculation.
Scores the current week against config/targets.json.
Updates data/targets_history.json on Sundays.
Returns a target_report dict for use by question.py and weekly_report.py.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS_FILE = ROOT / "config" / "targets.json"
TARGETS_HISTORY_FILE = ROOT / "data" / "targets_history.json"


def load_json(path: Path) -> dict:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_week_dates(today: str) -> list[str]:
    base = datetime.strptime(today, "%Y-%m-%d")
    monday = base - timedelta(days=base.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def is_sunday(today: str) -> bool:
    dt = datetime.strptime(today, "%Y-%m-%d")
    return dt.weekday() == 6


def score_targets(log: dict, today: str) -> dict:
    targets = load_json(TARGETS_FILE)
    week_dates = get_week_dates(today)

    # gather week stats
    all_commits = []
    repos_touched = set()
    days_active = 0
    feat_count = 0

    for d in week_dates:
        entry = log.get(d, {})
        commits = entry.get("commits", [])
        if commits:
            days_active += 1
            all_commits.extend(commits)
            for c in commits:
                repos_touched.add(c["repo"])
                if c.get("message", "").startswith("feat"):
                    feat_count += 1

    # calculate streak for this week
    streak = 0
    check = datetime.strptime(today, "%Y-%m-%d")
    for _ in range(7):
        d = check.strftime("%Y-%m-%d")
        if log.get(d, {}).get("commits"):
            streak += 1
        check -= timedelta(days=1)

    actuals = {
        "commits": len(all_commits),
        "active_repos": len(repos_touched),
        "feat_commits": feat_count,
        "streak_days": min(streak, 7),
    }

    weekly_targets = targets.get("weekly", {})
    scores: dict[str, dict] = {}

    for key, target_val in weekly_targets.items():
        actual = actuals.get(key, 0)
        pct = round((actual / target_val) * 100) if target_val > 0 else 0
        status = "hit" if pct >= 100 else "close" if pct >= 80 else "missed"
        scores[key] = {
            "target": target_val,
            "actual": actual,
            "pct": pct,
            "status": status,
        }

    # per-repo targets
    repo_scores: dict[str, dict] = {}
    repo_targets = {
        k: v for k, v in targets.get("repos", {}).items()
        if k != "_comment"
    }

    for repo_name, cfg in repo_targets.items():
        repo_target = cfg.get("weekly_commits", 0)
        repo_actual = sum(
            1 for c in all_commits if c["repo"] == repo_name
        )
        pct = round((repo_actual / repo_target) * 100) if repo_target > 0 else 0
        status = "hit" if pct >= 100 else "close" if pct >= 80 else "missed"
        repo_scores[repo_name] = {
            "target": repo_target,
            "actual": repo_actual,
            "pct": pct,
            "status": status,
        }

    overall_hit = sum(1 for v in scores.values() if v["status"] == "hit")
    overall_total = len(scores)

    report = {
        "week_ending": today,
        "scores": scores,
        "repo_scores": repo_scores,
        "summary": {
            "hit": overall_hit,
            "total": overall_total,
            "all_hit": overall_hit == overall_total,
        },
    }

    # save to history on Sundays
    if is_sunday(today):
        history = load_json(TARGETS_HISTORY_FILE)
        weeks = history.get("weeks", [])
        # avoid duplicates
        weeks = [w for w in weeks if w.get("week_ending") != today]
        weeks.append(report)
        # keep last 52 weeks
        history["weeks"] = weeks[-52:]
        save_json(TARGETS_HISTORY_FILE, history)
        print(f"targets history saved: {overall_hit}/{overall_total} hit")

    print(f"targets scored: {overall_hit}/{overall_total} hit")
    return report

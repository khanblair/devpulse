"""
devpulse — Department 2: Analyst
fingerprint.py

No AI call. Pure calculation.
Builds developer personality profile from last 30 days of log data.
Updates data/fingerprint.json weekly.
Needs at least 7 days of data to produce meaningful results.
"""

import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINGERPRINT_FILE = ROOT / "data" / "fingerprint.json"


def load_json(path: Path) -> dict:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_last_n_days(n: int = 30) -> list[str]:
    today = datetime.now(timezone.utc)
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def classify_style(
    total_commits: int,
    active_days: int,
    burst_days: int,
) -> str:
    if active_days == 0:
        return "inactive"
    avg = total_commits / max(active_days, 1)
    burst_ratio = burst_days / max(active_days, 1)

    if burst_ratio > 0.5:
        return "burst shipper"
    elif avg >= 4:
        return "high volume"
    elif avg >= 2:
        return "steady"
    else:
        return "sparse"


def update_fingerprint(log: dict) -> None:
    last_30 = get_last_n_days(30)
    all_commits = []
    active_days = 0
    burst_days = 0
    hour_counts: Counter = Counter()
    repo_counts: Counter = Counter()
    feat_count = 0
    fix_count = 0
    total_files = 0

    for date_str in last_30:
        entry = log.get(date_str, {})
        commits = entry.get("commits", [])
        if commits:
            active_days += 1
            if len(commits) >= 5:
                burst_days += 1
            all_commits.extend(commits)

            for c in commits:
                repo_counts[c["repo"]] += 1
                total_files += c.get("files_changed", 0)
                msg = c.get("message", "")
                if msg.startswith("feat"):
                    feat_count += 1
                elif msg.startswith("fix"):
                    fix_count += 1

                # extract hour from timestamp
                ts = c.get("timestamp", "")
                if "T" in ts:
                    try:
                        hour = int(ts.split("T")[1][:2])
                        hour_counts[hour] += 1
                    except (ValueError, IndexError):
                        pass

    total_days_tracked = sum(1 for d in log if log[d].get("commits"))

    if len(all_commits) < 5:
        # not enough data yet
        fp = load_json(FINGERPRINT_FILE)
        fp["total_days_tracked"] = total_days_tracked
        save_json(FINGERPRINT_FILE, fp)
        return

    peak_hour = hour_counts.most_common(1)[0][0] if hour_counts else None
    most_active = repo_counts.most_common(1)[0][0] if repo_counts else None
    most_avoided = repo_counts.most_common()[-1][0] if len(repo_counts) > 1 else None
    avg_commit_size = round(total_files / len(all_commits), 1) if all_commits else 0
    feat_fix_ratio = round(feat_count / max(fix_count, 1), 2)
    style = classify_style(len(all_commits), active_days, burst_days)

    # consistency score 0-10
    consistency = round((active_days / 30) * 10, 1)

    fp = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "peak_coding_hour": peak_hour,
        "style": style,
        "feat_fix_ratio": feat_fix_ratio,
        "most_active_repo": most_active,
        "most_avoided_repo": most_avoided,
        "avg_commit_size": avg_commit_size,
        "consistency_score": consistency,
        "total_days_tracked": total_days_tracked,
        "active_days_last_30": active_days,
        "burst_days_last_30": burst_days,
    }

    save_json(FINGERPRINT_FILE, fp)
    print(f"fingerprint updated: {style}, consistency {consistency}/10")

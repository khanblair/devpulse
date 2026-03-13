"""
devpulse — Department 2: Analyst
drift.py

No AI call. Pure calculation.
Reads file extensions from all commits grouped by month.
Builds a timeline of language usage percentages.
Updates data/drift.json.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIFT_FILE = ROOT / "data" / "drift.json"

# map extensions to friendly language names
EXT_MAP = {
    "py": "Python",
    "js": "JavaScript",
    "ts": "TypeScript",
    "tsx": "TypeScript",
    "jsx": "JavaScript",
    "rs": "Rust",
    "go": "Go",
    "java": "Java",
    "kt": "Kotlin",
    "swift": "Swift",
    "rb": "Ruby",
    "php": "PHP",
    "cs": "C#",
    "cpp": "C++",
    "c": "C",
    "html": "HTML",
    "css": "CSS",
    "scss": "CSS",
    "sass": "CSS",
    "json": "JSON",
    "yaml": "YAML",
    "yml": "YAML",
    "md": "Markdown",
    "sh": "Shell",
    "bash": "Shell",
    "sql": "SQL",
    "dart": "Dart",
    "vue": "Vue",
    "svelte": "Svelte",
}

IGNORE_EXTS = {"lock", "sum", "mod", "toml", "cfg", "ini", "txt", "gitignore"}


def load_json(path: Path) -> dict:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def update_drift(log: dict) -> None:
    # group all commits by month
    monthly: dict[str, Counter] = {}

    for date_str, entry in log.items():
        try:
            month = date_str[:7]  # "2026-03"
        except Exception:
            continue

        if month not in monthly:
            monthly[month] = Counter()

        for commit in entry.get("commits", []):
            for ext in commit.get("extensions", []):
                ext = ext.lower()
                if ext in IGNORE_EXTS:
                    continue
                lang = EXT_MAP.get(ext, ext.upper() if len(ext) <= 4 else None)
                if lang:
                    monthly[month][lang] += 1

    # convert counts to percentages
    monthly_pct: dict[str, dict] = {}
    for month, counter in sorted(monthly.items()):
        total = sum(counter.values())
        if total == 0:
            continue
        top = counter.most_common(6)
        monthly_pct[month] = {
            lang: round((count / total) * 100)
            for lang, count in top
        }

    drift = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "monthly": monthly_pct,
    }

    save_json(DRIFT_FILE, drift)
    print(f"drift updated: {len(monthly_pct)} months tracked")

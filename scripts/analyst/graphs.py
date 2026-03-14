"""
devpulse — Department 2: Analyst
graphs.py

No AI call. Pure SVG generation in Python.
Generates 7 SVG files to docs/assets/.
Dark themed. No external charting libraries.
Each graph is self-contained valid SVG.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT / "docs" / "assets"
FINGERPRINT_FILE = ROOT / "data" / "fingerprint.json"
DRIFT_FILE = ROOT / "data" / "drift.json"
GRAVEYARD_FILE = ROOT / "data" / "graveyard.json"
TARGETS_FILE = ROOT / "config" / "targets.json"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# colour palette — light theme
BG = "#ffffff"
BG2 = "#f8f9fc"
BG3 = "#f3f4f6"
BORDER = "#e4e8f0"
TEXT = "#1a1d2e"
MUTED = "#6b7280"
DIM = "#d1d5db"
ACCENT = "#6c63ff"
ACCENT2 = "#f59e0b"
ACCENT3 = "#3b82f6"
RED = "#ef4444"
GREEN = "#22c55e"

MOOD_COLORS = {
    "focused": "#6c63ff",
    "grinding": "#f59e0b",
    "scattered": "#3b82f6",
    "frustrated": "#ef4444",
    "exploratory": "#8b5cf6",
    "cleanup": "#10b981",
    "relieved": "#22c55e",
    "no commits": "#e5e7eb",
    "unknown": "#d1d5db",
    None: "#e5e7eb",
}


def load_json(path: Path) -> dict:
    if path.exists() and path.stat().st_size > 0:
        with open(path) as f:
            return json.load(f)
    return {}


def svg_wrap(content: str, width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="{BG}" rx="8"/>'
        f'{content}'
        f'</svg>'
    )


def get_last_n_days(n: int) -> list[str]:
    today = datetime.now(timezone.utc)
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(n))]


# ── Graph 1: mood timeline ─────────────────────────────────────────────────────

def graph_mood_timeline(log: dict) -> None:
    days = get_last_n_days(30)
    dot_r = 7
    gap = 16
    pad_x = 20
    pad_y = 30
    width = pad_x * 2 + len(days) * gap
    height = 80

    parts = []
    parts.append(
        f'<text x="{pad_x}" y="16" '
        f'font-family="monospace" font-size="10" fill="{MUTED}" '
        f'letter-spacing="2">MOOD — LAST 30 DAYS</text>'
    )

    for i, date_str in enumerate(days):
        entry = log.get(date_str, {})
        mood = entry.get("mood")
        has_commits = bool(entry.get("commits"))
        color = MOOD_COLORS.get(mood, DIM)
        cx = pad_x + i * gap + dot_r
        cy = pad_y + 20

        tooltip = f"{date_str}: {mood or 'no data'}"
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{dot_r}" '
            f'fill="{color}" opacity="{"0.9" if has_commits else "0.2"}">'
            f'<title>{tooltip}</title></circle>'
        )

    # legend
    legend_y = height - 12
    legend_items = [
        ("focused", "#c8f060"),
        ("grinding", "#f0a040"),
        ("exploratory", "#a060f0"),
        ("cleanup", "#60d0a0"),
    ]
    lx = pad_x
    for label, color in legend_items:
        parts.append(
            f'<circle cx="{lx + 5}" cy="{legend_y}" r="4" fill="{color}"/>'
            f'<text x="{lx + 13}" y="{legend_y + 4}" '
            f'font-family="monospace" font-size="9" fill="{MUTED}">{label}</text>'
        )
        lx += 80

    svg = svg_wrap("".join(parts), width, height)
    (ASSETS_DIR / "mood-timeline.svg").write_text(svg, encoding="utf-8")
    print("mood-timeline.svg saved")


# ── Graph 2: commit heatmap ────────────────────────────────────────────────────

def graph_commit_heatmap(log: dict) -> None:
    weeks = 12
    days_per_week = 7
    cell = 14
    gap = 3
    pad_x = 36
    pad_y = 28
    width = pad_x + weeks * (cell + gap) + 20
    height = pad_y + days_per_week * (cell + gap) + 20

    today = datetime.now(timezone.utc)
    # align to Sunday start
    start = today - timedelta(days=today.weekday() + 1 + (weeks - 1) * 7)

    # count commits per day
    max_commits = 1
    day_counts: dict[str, int] = {}
    for entry_date, entry in log.items():
        count = len(entry.get("commits", []))
        day_counts[entry_date] = count
        if count > max_commits:
            max_commits = count

    parts = []
    parts.append(
        f'<text x="{pad_x}" y="16" '
        f'font-family="monospace" font-size="10" fill="{MUTED}" '
        f'letter-spacing="2">COMMIT ACTIVITY — 12 WEEKS</text>'
    )

    day_labels = ["M", "T", "W", "T", "F", "S", "S"]
    for i, label in enumerate(day_labels):
        y = pad_y + i * (cell + gap) + cell // 2 + 4
        parts.append(
            f'<text x="14" y="{y}" font-family="monospace" '
            f'font-size="9" fill="{MUTED}" text-anchor="middle">{label}</text>'
        )

    for week in range(weeks):
        for day in range(days_per_week):
            dt = start + timedelta(weeks=week, days=day)
            date_str = dt.strftime("%Y-%m-%d")
            count = day_counts.get(date_str, 0)

            if count == 0:
                color = BG3
                opacity = "1"
            else:
                intensity = min(count / max_commits, 1.0)
                if intensity < 0.33:
                    color = "#c7d2fe"
                elif intensity < 0.66:
                    color = "#818cf8"
                else:
                    color = ACCENT
                opacity = "0.95"

            x = pad_x + week * (cell + gap)
            y = pad_y + day * (cell + gap)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'rx="2" fill="{color}" opacity="{opacity}">'
                f'<title>{date_str}: {count} commit(s)</title></rect>'
            )

    svg = svg_wrap("".join(parts), width, height)
    (ASSETS_DIR / "commit-heatmap.svg").write_text(svg, encoding="utf-8")
    print("commit-heatmap.svg saved")


# ── Graph 3: language drift ────────────────────────────────────────────────────

def graph_language_drift() -> None:
    drift = load_json(DRIFT_FILE)
    monthly = drift.get("monthly", {})

    if not monthly:
        empty = svg_wrap(
            f'<text x="20" y="30" font-family="monospace" font-size="11" '
            f'fill="{MUTED}">No language data yet</text>',
            400, 50
        )
        (ASSETS_DIR / "language-drift.svg").write_text(empty, encoding="utf-8")
        return

    months = sorted(monthly.keys())[-8:]
    all_langs = set()
    for m in months:
        all_langs.update(monthly[m].keys())
    top_langs = sorted(all_langs, key=lambda l: sum(
        monthly[m].get(l, 0) for m in months
    ), reverse=True)[:6]

    lang_colors = [ACCENT, ACCENT2, ACCENT3, "#a060f0", "#60d0a0", "#f06060"]
    bar_w = 32
    gap = 6
    pad_x = 20
    pad_y = 30
    chart_h = 120
    label_h = 30
    width = pad_x * 2 + len(months) * (bar_w + gap)
    height = pad_y + chart_h + label_h + 30

    parts = []
    parts.append(
        f'<text x="{pad_x}" y="18" font-family="monospace" font-size="10" '
        f'fill="{MUTED}" letter-spacing="2">LANGUAGE DRIFT</text>'
    )

    for mi, month in enumerate(months):
        x = pad_x + mi * (bar_w + gap)
        month_data = monthly[month]
        total = sum(month_data.values()) or 1
        y_offset = pad_y

        for li, lang in enumerate(top_langs):
            pct = month_data.get(lang, 0)
            bar_h = int((pct / 100) * chart_h)
            if bar_h < 2:
                continue
            color = lang_colors[li % len(lang_colors)]
            parts.append(
                f'<rect x="{x}" y="{pad_y + chart_h - y_offset - bar_h + pad_y}" '
                f'width="{bar_w}" height="{bar_h}" fill="{color}" opacity="0.85" rx="1">'
                f'<title>{month} {lang}: {pct}%</title></rect>'
            )
            y_offset += bar_h

        # month label
        parts.append(
            f'<text x="{x + bar_w // 2}" y="{pad_y + chart_h + 16}" '
            f'font-family="monospace" font-size="8" fill="{MUTED}" '
            f'text-anchor="middle">{month[5:]}</text>'
        )

    # legend
    lx = pad_x
    ly = height - 12
    for li, lang in enumerate(top_langs):
        color = lang_colors[li % len(lang_colors)]
        parts.append(
            f'<rect x="{lx}" y="{ly - 8}" width="8" height="8" fill="{color}" rx="1"/>'
            f'<text x="{lx + 11}" y="{ly}" font-family="monospace" '
            f'font-size="9" fill="{MUTED}">{lang}</text>'
        )
        lx += len(lang) * 7 + 20

    svg = svg_wrap("".join(parts), width, height)
    (ASSETS_DIR / "language-drift.svg").write_text(svg, encoding="utf-8")
    print("language-drift.svg saved")


# ── Graph 4: hourly pattern ────────────────────────────────────────────────────

def graph_hourly_pattern(log: dict) -> None:
    hour_counts: Counter = Counter()
    for entry in log.values():
        for commit in entry.get("commits", []):
            ts = commit.get("timestamp", "")
            if "T" in ts:
                try:
                    hour = int(ts.split("T")[1][:2])
                    hour_counts[hour] += 1
                except (ValueError, IndexError):
                    pass

    max_count = max(hour_counts.values(), default=1)
    bar_w = 18
    gap = 2
    pad_x = 20
    pad_y = 28
    chart_h = 80
    width = pad_x * 2 + 24 * (bar_w + gap)
    height = pad_y + chart_h + 24

    parts = []
    parts.append(
        f'<text x="{pad_x}" y="16" font-family="monospace" font-size="10" '
        f'fill="{MUTED}" letter-spacing="2">CODING HOURS</text>'
    )

    for hour in range(24):
        count = hour_counts.get(hour, 0)
        bar_h = int((count / max_count) * chart_h) if max_count > 0 else 0
        x = pad_x + hour * (bar_w + gap)
        y = pad_y + chart_h - bar_h

        # color by time of day
        if 6 <= hour < 12:
            color = ACCENT3
        elif 12 <= hour < 18:
            color = ACCENT
        elif 18 <= hour < 22:
            color = ACCENT2
        else:
            color = "#8b5cf6"

        parts.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{max(bar_h, 2)}" '
            f'fill="{color if count > 0 else BG3}" opacity="{"0.85" if count > 0 else "1"}" rx="2">'
            f'<title>{hour:02d}:00 — {count} commit(s)</title></rect>'
        )

        if hour % 6 == 0:
            parts.append(
                f'<text x="{x + bar_w // 2}" y="{pad_y + chart_h + 14}" '
                f'font-family="monospace" font-size="9" fill="{MUTED}" '
                f'text-anchor="middle">{hour:02d}h</text>'
            )

    svg = svg_wrap("".join(parts), width, height)
    (ASSETS_DIR / "hourly-pattern.svg").write_text(svg, encoding="utf-8")
    print("hourly-pattern.svg saved")


# ── Graph 5: repo activity ─────────────────────────────────────────────────────

def graph_repo_activity(log: dict) -> None:
    days_30 = set(get_last_n_days(30))
    graveyard = load_json(GRAVEYARD_FILE)
    graveyard_repos = {r["name"] for r in graveyard.get("repos", [])}

    repo_counts: Counter = Counter()
    for date_str, entry in log.items():
        if date_str in days_30:
            for commit in entry.get("commits", []):
                repo_counts[commit["repo"]] += 1

    if not repo_counts:
        empty = svg_wrap(
            f'<text x="20" y="30" font-family="monospace" font-size="11" '
            f'fill="{MUTED}">No repo activity yet</text>',
            300, 50
        )
        (ASSETS_DIR / "repo-activity.svg").write_text(empty, encoding="utf-8")
        return

    repos = repo_counts.most_common(10)
    max_count = repos[0][1] if repos else 1
    bar_h = 20
    gap = 6
    pad_x = 20
    label_w = 120
    chart_w = 240
    pad_y = 30
    width = pad_x + label_w + chart_w + 60
    height = pad_y + len(repos) * (bar_h + gap) + 20

    parts = []
    parts.append(
        f'<text x="{pad_x}" y="18" font-family="monospace" font-size="10" '
        f'fill="{MUTED}" letter-spacing="2">REPO ACTIVITY — 30 DAYS</text>'
    )

    for i, (repo, count) in enumerate(repos):
        y = pad_y + i * (bar_h + gap)
        is_graveyard = repo in graveyard_repos
        bar_color = "#d1d5db" if is_graveyard else ACCENT
        bar_width = int((count / max_count) * chart_w)
        opacity = "1" if is_graveyard else "0.85"

        # repo name
        parts.append(
            f'<text x="{pad_x + label_w - 4}" y="{y + bar_h // 2 + 4}" '
            f'font-family="monospace" font-size="10" fill="{MUTED if is_graveyard else TEXT}" '
            f'text-anchor="end">{repo[:16]}</text>'
        )

        # bar
        parts.append(
            f'<rect x="{pad_x + label_w}" y="{y}" '
            f'width="{max(bar_width, 3)}" height="{bar_h}" '
            f'fill="{bar_color}" opacity="{opacity}" rx="2">'
            f'<title>{repo}: {count} commits</title></rect>'
        )

        # count label
        parts.append(
            f'<text x="{pad_x + label_w + bar_width + 6}" y="{y + bar_h // 2 + 4}" '
            f'font-family="monospace" font-size="9" fill="{MUTED}">{count}</text>'
        )

    svg = svg_wrap("".join(parts), width, height)
    (ASSETS_DIR / "repo-activity.svg").write_text(svg, encoding="utf-8")
    print("repo-activity.svg saved")


# ── Graph 6: streak chart ──────────────────────────────────────────────────────

def graph_streak_chart(log: dict) -> None:
    days = get_last_n_days(60)
    streak_vals = []
    current = 0

    for date_str in days:
        if log.get(date_str, {}).get("commits"):
            current += 1
        else:
            current = 0
        streak_vals.append(current)

    max_streak = max(streak_vals, default=1)
    pad_x = 20
    pad_y = 28
    chart_h = 80
    chart_w = 500
    width = pad_x * 2 + chart_w
    height = pad_y + chart_h + 20
    step = chart_w / max(len(streak_vals) - 1, 1)

    points = []
    for i, val in enumerate(streak_vals):
        x = pad_x + i * step
        y = pad_y + chart_h - (val / max(max_streak, 1)) * chart_h
        points.append((x, y))

    path_d = " ".join(
        f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}"
        for i, (x, y) in enumerate(points)
    )

    # fill area under line
    fill_d = (
        path_d
        + f" L{points[-1][0]:.1f} {pad_y + chart_h}"
        + f" L{points[0][0]:.1f} {pad_y + chart_h} Z"
    )

    parts = []
    parts.append(
        f'<text x="{pad_x}" y="16" font-family="monospace" font-size="10" '
        f'fill="{MUTED}" letter-spacing="2">STREAK HISTORY — 60 DAYS</text>'
    )
    parts.append(
        f'<path d="{fill_d}" fill="{ACCENT}" opacity="0.1"/>'
    )
    parts.append(
        f'<path d="{path_d}" fill="none" stroke="{ACCENT}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
    )

    # current streak label
    if streak_vals:
        current_streak = streak_vals[-1]
        lx, ly = points[-1]
        parts.append(
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{ACCENT}"/>'
            f'<text x="{lx - 4}" y="{ly - 10}" font-family="monospace" '
            f'font-size="10" fill="{ACCENT}" text-anchor="end">'
            f'🔥 {current_streak}</text>'
        )

    # baseline
    parts.append(
        f'<line x1="{pad_x}" y1="{pad_y + chart_h}" '
        f'x2="{pad_x + chart_w}" y2="{pad_y + chart_h}" '
        f'stroke="{DIM}" stroke-width="0.5"/>'
    )

    svg = svg_wrap("".join(parts), width, height)
    (ASSETS_DIR / "streak-chart.svg").write_text(svg, encoding="utf-8")
    print("streak-chart.svg saved")


# ── Graph 7: targets scorecard ─────────────────────────────────────────────────

def graph_targets_scorecard(log: dict) -> None:
    from scripts.analyst.targets import score_targets
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        report = score_targets(log, today)
    except Exception:
        empty = svg_wrap(
            f'<text x="20" y="30" font-family="monospace" font-size="11" '
            f'fill="{MUTED}">No targets configured</text>',
            300, 50
        )
        (ASSETS_DIR / "targets-scorecard.svg").write_text(empty, encoding="utf-8")
        return

    scores = report.get("scores", {})
    repo_scores = report.get("repo_scores", {})
    all_scores = {**scores, **repo_scores}

    if not all_scores:
        empty = svg_wrap(
            f'<text x="20" y="30" font-family="monospace" font-size="11" '
            f'fill="{MUTED}">No targets set</text>',
            300, 50
        )
        (ASSETS_DIR / "targets-scorecard.svg").write_text(empty, encoding="utf-8")
        return

    bar_h = 22
    gap = 8
    pad_x = 20
    label_w = 130
    bar_max_w = 220
    count_w = 60
    pad_y = 30
    width = pad_x + label_w + bar_max_w + count_w + 20
    height = pad_y + len(all_scores) * (bar_h + gap) + 20

    parts = []
    parts.append(
        f'<text x="{pad_x}" y="18" font-family="monospace" font-size="10" '
        f'fill="{MUTED}" letter-spacing="2">TARGETS — THIS WEEK</text>'
    )

    for i, (key, score) in enumerate(all_scores.items()):
        y = pad_y + i * (bar_h + gap)
        pct = score.get("pct", 0)
        actual = score.get("actual", 0)
        target = score.get("target", 0)
        status = score.get("status", "missed")

        bar_w = min(int((pct / 100) * bar_max_w), bar_max_w)
        if status == "hit":
            color = ACCENT
        elif status == "close":
            color = ACCENT2
        else:
            color = RED

        label = key.replace("_", " ")

        parts.append(
            f'<text x="{pad_x + label_w - 6}" y="{y + bar_h // 2 + 4}" '
            f'font-family="monospace" font-size="10" fill="{TEXT}" '
            f'text-anchor="end">{label[:16]}</text>'
        )

        # background track
        parts.append(
            f'<rect x="{pad_x + label_w}" y="{y}" '
            f'width="{bar_max_w}" height="{bar_h}" '
            f'fill="{BG3}" opacity="1" rx="3"/>'
        )

        # fill bar
        if bar_w > 0:
            parts.append(
                f'<rect x="{pad_x + label_w}" y="{y}" '
                f'width="{bar_w}" height="{bar_h}" '
                f'fill="{color}" opacity="0.85" rx="3">'
                f'<title>{actual}/{target} ({pct}%)</title></rect>'
            )

        # count label
        status_icon = "✓" if status == "hit" else "~" if status == "close" else "✗"
        parts.append(
            f'<text x="{pad_x + label_w + bar_max_w + 8}" y="{y + bar_h // 2 + 4}" '
            f'font-family="monospace" font-size="9" fill="{color}">'
            f'{actual}/{target} {status_icon}</text>'
        )

    svg = svg_wrap("".join(parts), width, height)
    (ASSETS_DIR / "targets-scorecard.svg").write_text(svg, encoding="utf-8")
    print("targets-scorecard.svg saved")


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_all_graphs(log: dict) -> None:
    graph_mood_timeline(log)
    graph_commit_heatmap(log)
    graph_language_drift()
    graph_hourly_pattern(log)
    graph_repo_activity(log)
    graph_streak_chart(log)
    graph_targets_scorecard(log)

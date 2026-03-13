"""
devpulse — Department 2: Analyst
question.py

Groq call #3 — Sunday only.
Reads the full week's data including target scores.
Generates one honest, specific question worth sitting with.
Not a tip. Not a recommendation. A question.
"""

import os
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def get_week_dates(today: str) -> list[str]:
    base = datetime.strptime(today, "%Y-%m-%d")
    monday = base - timedelta(days=base.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def generate_question(
    log: dict,
    today: str,
    target_report: dict | None,
    settings: dict,
) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "What would make next week meaningfully different from this one?"

    model = settings.get("groq_model", "groq/compound")
    name = settings.get("name", "Dev")
    week_dates = get_week_dates(today)

    # build week summary
    all_commits = []
    moods = []
    repos_touched = set()

    for d in week_dates:
        entry = log.get(d, {})
        commits = entry.get("commits", [])
        all_commits.extend(commits)
        if entry.get("mood"):
            moods.append(entry["mood"])
        for c in commits:
            repos_touched.add(c["repo"])

    if not all_commits:
        return "You pushed nothing this week — what got in the way?"

    feat_count = sum(1 for c in all_commits if c["message"].startswith("feat"))
    fix_count = sum(1 for c in all_commits if c["message"].startswith("fix"))
    chore_count = sum(1 for c in all_commits if c["message"].startswith("chore"))
    days_active = sum(
        1 for d in week_dates
        if log.get(d, {}).get("commits")
    )

    # build target context
    target_context = ""
    if target_report:
        missed = [
            f"{k}: {v['actual']}/{v['target']}"
            for k, v in target_report.get("scores", {}).items()
            if v.get("pct", 100) < 80
        ]
        exceeded = [
            f"{k}: {v['actual']}/{v['target']}"
            for k, v in target_report.get("scores", {}).items()
            if v.get("pct", 0) >= 130
        ]
        if missed:
            target_context += f"Missed targets: {', '.join(missed)}. "
        if exceeded:
            target_context += f"Exceeded: {', '.join(exceeded)}. "

    prompt = (
        f"You are generating one honest, specific question for a developer to reflect on.\n\n"
        f"Developer: {name}\n"
        f"Week ending: {today}\n\n"
        f"Week data:\n"
        f"- Total commits: {len(all_commits)}\n"
        f"- Active days: {days_active}/7\n"
        f"- Repos touched: {', '.join(repos_touched)}\n"
        f"- feat: {feat_count}, fix: {fix_count}, chore: {chore_count}\n"
        f"- Moods this week: {', '.join(moods) if moods else 'not recorded'}\n"
        f"- {target_context}\n\n"
        f"Generate ONE question. Rules:\n"
        f"- Specific to this week's data, not generic\n"
        f"- A question worth sitting with, not a productivity tip\n"
        f"- Honest, not motivational\n"
        f"- Under 30 words\n"
        f"- No preamble. Just the question.\n\n"
        f"Examples of the right tone:\n"
        f"'You touched auth every day this week — is that focus or avoidance?'\n"
        f"'You hit your commit target but 12 of 15 were chores — what does that say about the week?'\n"
        f"'Three active days, four quiet ones — what happened on the quiet days?'\n\n"
        f"Write the question now:"
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
                "max_tokens": 60,
                "temperature": 0.8,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        question = result["choices"][0]["message"]["content"].strip().strip('"').strip("'")
        if not question.endswith("?"):
            question += "?"
        return question

    except Exception as e:
        print(f"question generation failed: {e}")
        return "What would you do differently if you ran this week again?"

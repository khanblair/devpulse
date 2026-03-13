"""
devpulse — Department 2: Analyst
devlog.py

Groq call #2 — daily.
Reads today's commits, generates 2-3 sentences of plain prose
written in first person as if the developer kept a diary.
Honest, not cheerful. Reflects what actually happened.
"""

import os
import httpx
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def generate_devlog(commits: list[dict], date: str, settings: dict) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "No API key configured."

    model = settings.get("groq_model", "groq/compound")
    name = settings.get("name", "Dev")

    # group commits by repo
    repos: dict[str, list] = {}
    for c in commits:
        repos.setdefault(c["repo"], []).append(c["message"])

    repo_lines = []
    for repo, messages in repos.items():
        repo_lines.append(f"  {repo}: {', '.join(messages[:5])}")

    commits_summary = "\n".join(repo_lines)
    total_files = sum(c.get("files_changed", 0) for c in commits)

    prompt = (
        f"You are ghost-writing a developer's daily log entry.\n\n"
        f"Developer: {name}\n"
        f"Date: {date}\n"
        f"Commits today:\n{commits_summary}\n"
        f"Total files changed: {total_files}\n\n"
        f"Write 2-3 sentences in first person, past tense, as if {name} wrote this themselves.\n\n"
        f"Rules:\n"
        f"- Plain, honest prose. Not enthusiastic. Not corporate.\n"
        f"- Mention what was actually done, not how great it was.\n"
        f"- If commits are boring maintenance, say so plainly.\n"
        f"- No bullet points. No headers. Just sentences.\n"
        f"- Max 60 words.\n"
        f"- Start with what was done, not with 'Today I...'\n\n"
        f"Example tone: 'Spent most of the day on auth cleanup — "
        f"three small fixes that should have been one. "
        f"Touched the mobile app briefly but nothing shipped.'\n\n"
        f"Write the entry now:"
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
                "max_tokens": 120,
                "temperature": 0.7,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        text = result["choices"][0]["message"]["content"].strip()
        # strip surrounding quotes if present
        text = text.strip('"').strip("'")
        return text

    except Exception as e:
        print(f"devlog generation failed: {e}")
        # fallback — build a simple summary without AI
        repo_names = list(repos.keys())
        return (
            f"Pushed {len(commits)} commit(s) across "
            f"{', '.join(repo_names)}."
        )

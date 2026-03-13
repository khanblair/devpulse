"""
devpulse — Department 2: Analyst
mood.py

Groq call #1 — daily.
Reads today's commit messages, infers developer mood.
Returns one word from a fixed vocabulary.
"""

import os
import json
import httpx
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = ROOT / "config" / "settings.json"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

MOOD_VOCAB = [
    "focused",
    "grinding",
    "scattered",
    "frustrated",
    "exploratory",
    "cleanup",
    "relieved",
]


def infer_mood(commits: list[dict], settings: dict) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "unknown"

    model = settings.get("groq_model", "groq/compound")
    vocab_str = ", ".join(MOOD_VOCAB)

    messages_text = "\n".join(
        f"- [{c['repo']}] {c['message']}" for c in commits
    )

    prompt = (
        f"You are analysing a developer's commit messages to infer their mood for the day.\n\n"
        f"Commit messages:\n{messages_text}\n\n"
        f"Based only on these commit messages, respond with exactly ONE word from this list:\n"
        f"{vocab_str}\n\n"
        f"Rules:\n"
        f"- focused: clear purposeful work, single area\n"
        f"- grinding: many small commits, repetitive fixes\n"
        f"- scattered: commits across many unrelated areas\n"
        f"- frustrated: words like 'fix', 'again', 'broken', 'revert'\n"
        f"- exploratory: new features, experiments, trying things\n"
        f"- cleanup: refactor, chore, remove, tidy, organise\n"
        f"- relieved: 'finally', 'done', 'working', 'resolved'\n\n"
        f"Respond with exactly one word only. No punctuation. No explanation."
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
                "max_tokens": 10,
                "temperature": 0.1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        mood = result["choices"][0]["message"]["content"].strip().lower()

        # validate against vocab
        if mood in MOOD_VOCAB:
            return mood

        # fallback — find closest match
        for word in MOOD_VOCAB:
            if word in mood:
                return word

        return "focused"

    except Exception as e:
        print(f"mood inference failed: {e}")
        return "unknown"

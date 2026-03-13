"""
devpulse — Setup
register_commands.py

Run once after creating your Telegram bot.
Registers all 15 commands with Telegram's setMyCommands API
so they appear in the bot menu automatically.

Usage:
    python scripts/setup/register_commands.py

Requires TELEGRAM_BOT_TOKEN in environment or .env file.
"""

import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)

# load .env if present
env_file = Path(__file__).resolve().parents[2] / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key and val and val not in (
                "your_telegram_bot_token_here",
                "your_telegram_chat_id_here",
                "your_groq_api_key_here",
                "your_github_token_here",
                "your_github_username_here",
            ):
                os.environ.setdefault(key, val)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here":
    print("❌  TELEGRAM_BOT_TOKEN not set.")
    print("    Add it to your .env file or export it in your shell.")
    sys.exit(1)

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

COMMANDS = [
    ("report",      "Today's full report"),
    ("weekly",      "This week's summary"),
    ("commits",     "Today's commits (or: /commits 3)"),
    ("mood",        "Today's inferred mood"),
    ("streak",      "Current streak and history"),
    ("yoyo",        "What yoyo-evolve did today"),
    ("targets",     "Show all current targets"),
    ("progress",    "This week vs targets"),
    ("settarget",   "Update a target (e.g. /settarget weekly_commits 20)"),
    ("graveyard",   "Abandoned repos and open PRs"),
    ("fingerprint", "Your dev personality profile"),
    ("drift",       "Language shift summary"),
    ("site",        "Your GitHub Pages URL"),
    ("status",      "System health check"),
    ("help",        "List all commands"),
]


def register() -> None:
    print(f"registering {len(COMMANDS)} commands with Telegram...\n")

    payload = {
        "commands": [
            {"command": cmd, "description": desc}
            for cmd, desc in COMMANDS
        ]
    }

    try:
        resp = httpx.post(
            f"{BASE_URL}/setMyCommands",
            json=payload,
            timeout=15,
        )
        data = resp.json()

        if data.get("ok"):
            print("✅  Commands registered successfully!\n")
            print("Commands now active in your bot:")
            for cmd, desc in COMMANDS:
                print(f"  /{cmd:<14} {desc}")
            print("\nOpen Telegram, find your bot, and type '/' to see them.")
        else:
            print(f"❌  Telegram returned an error:")
            print(f"    {data}")

    except httpx.RequestError as e:
        print(f"❌  Network error: {e}")
        sys.exit(1)


def verify_bot() -> None:
    """Check the bot token is valid before attempting registration."""
    try:
        resp = httpx.get(f"{BASE_URL}/getMe", timeout=10)
        data = resp.json()
        if data.get("ok"):
            bot = data["result"]
            print(f"✅  Bot verified: @{bot['username']} ({bot['first_name']})\n")
        else:
            print(f"❌  Bot token invalid: {data.get('description', 'unknown error')}")
            sys.exit(1)
    except httpx.RequestError as e:
        print(f"❌  Could not reach Telegram: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("devpulse — register bot commands\n")
    print("─" * 40)
    verify_bot()
    register()

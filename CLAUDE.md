# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

devpulse is a serverless dev analytics system running on GitHub Actions. It automatically tracks commits, sends daily/weekly Telegram digests, and publishes a GitHub Pages dashboard — all without external servers.

## Architecture

```
Department 1 — Collector (poll.yml)
  - Runs every 30 minutes
  - poll.py: Polls GitHub API for recent commits across all repos
  - Stores in data/log.json
  - bot.yml: Polls Telegram every 10min for commands

Department 2 — Analyst (analyse.yml)
  - Runs daily at 6pm UTC (9pm Kampala)
  - analyse.py: Orchestrates all analyst modules
  - Modules: mood, devlog, yoyo, fingerprint, drift, graveyard, targets, graphs, weekly_report
  - Makes Groq API calls for AI analysis

Department 3 — Publisher (publish.yml)
  - Triggered after analyse.yml completes
  - build_site.py: Generates dashboard to docs/
  - telegram.py: Sends daily digest to Telegram
```

## Key Files

- `config/settings.json` — User config (name, timezone, site_url, groq_model, etc.)
- `config/targets.json` — Weekly targets for commits, PRs, repos
- `data/log.json` — Main data store (commits, mood, devlog per day)
- `data/targets_history.json` — Historical target progress
- `docs/` — GitHub Pages site output

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Test collector
python scripts/collector/poll.py --test

# Test analyst
python scripts/analyst/analyse.py --dry-run

# Test publisher
python scripts/publisher/build_site.py
python scripts/publisher/telegram.py --dry-run
```

## GitHub Actions Workflows

- `poll.yml` — Collector, every 30 min
- `analyse.yml` — Daily at 6pm UTC
- `publish.yml` — After analyse completes
- `bot.yml` — Telegram command polling

## Known Issues

- Race condition between poll.yml and analyse.yml can cause non-fast-forward push failures. Fix: use `git stash --include-untracked` before pull-rebase, then `git stash pop || true`.

## Secrets Required

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GROQ_API_KEY`, `GH_TOKEN`, `GH_USERNAME` — stored in GitHub Secrets and `.env` locally.

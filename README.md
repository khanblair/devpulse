# devpulse

Your dev life, tracked automatically. Daily Telegram digests, weekly AI reports, GitHub Pages site — all running on GitHub Actions with zero external servers.

---

## What it does

- Silently logs every commit you push across all your repos
- Every evening at 9pm sends a Telegram digest of your day
- Every Sunday sends a deep weekly report with AI analysis
- Tracks your mood, streak, language drift, and dev personality
- Compares your progress against weekly targets you set
- Watches yoyo-evolve and includes its daily progress alongside yours
- Publishes everything to a GitHub Pages site updated daily
- Responds to bot commands so you can query your data anytime

---

## Setup

### 1. Create your Telegram bot
- Open Telegram → search `@BotFather` → send `/newbot`
- Follow prompts → copy the bot token
- Message your new bot once
- Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
- Copy the `"id"` value from `"chat"` — that is your chat ID

### 2. Get your Groq API key
- Go to [console.groq.com](https://console.groq.com)
- API Keys → Create new key → copy it

### 3. Add GitHub Secrets
Go to this repo → Settings → Secrets and variables → Actions → New repository secret

| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your personal chat ID |
| `GROQ_API_KEY` | Your Groq API key |
| `GH_TOKEN` | Your GitHub personal access token (repo scope) |

### 4. Update config
Edit `config/settings.json`:
- Set `name` to your name
- Set `site_url` to `https://YOUR_USERNAME.github.io/devpulse`

Edit `config/targets.json`:
- Set your weekly targets (or use `/settarget` in the bot later)
- Add your repos under `"repos"` for per-repo targets

### 5. Enable GitHub Pages
This repo → Settings → Pages → Source: Deploy from branch → Branch: `main` → Folder: `/docs`

### 6. Register bot commands
```bash
pip install httpx
python scripts/setup/register_commands.py
```

### 7. Add webhooks to your repos
For each repo you want tracked:
- Repo → Settings → Webhooks → Add webhook
- Payload URL: `https://api.github.com/repos/YOUR_USERNAME/devpulse/dispatches`
- Content type: `application/json`
- Secret: your `GH_TOKEN`
- Events: Just the push event

### 8. Test
Push any commit to one of your tracked repos and watch `collect.yml` fire in the Actions tab.

---

## Bot commands

| Command | What it does |
|---|---|
| `/report` | Today's full report on demand |
| `/weekly` | This week's report so far |
| `/commits` | Today's commits |
| `/commits 3` | Commits from 3 days ago |
| `/mood` | Today's inferred mood |
| `/streak` | Current streak and history |
| `/yoyo` | What yoyo-evolve did today |
| `/targets` | Show all current targets |
| `/progress` | This week vs targets right now |
| `/settarget weekly_commits 20` | Update a global target |
| `/settarget repo:my-api 4` | Update a per-repo target |
| `/graveyard` | Abandoned repos and open PRs |
| `/fingerprint` | Your dev personality profile |
| `/drift` | Language shift summary |
| `/site` | Your GitHub Pages URL |
| `/status` | Confirm bot and workflows running |
| `/help` | List all commands |

---

## Architecture

```
Department 1 — Collector
  collect.yml    fires on every push → collect.py logs to data/log.json
  bot.yml        polls Telegram every 10min → bot.py handles commands

Department 2 — Analyst
  analyse.yml    runs 9pm daily → all analyst modules → enriches log.json
                 Groq calls: mood, devlog, question (Sun), weekly_report (Sun)

Department 3 — Publisher
  publish.yml    triggered by analyse.yml → build_site.py + telegram.py
```

---

## Secrets reference

```
TELEGRAM_BOT_TOKEN   — Telegram bot token from @BotFather
TELEGRAM_CHAT_ID     — Your personal Telegram chat ID
GROQ_API_KEY         — Groq API key from console.groq.com
GH_TOKEN             — GitHub personal access token with repo scope
```

---

## Local development

```bash
cp .env.example .env
# fill in your values in .env

pip install -r requirements.txt

# test collector
python scripts/collector/collect.py --test

# test analyst
python scripts/analyst/analyse.py --dry-run

# test publisher
python scripts/publisher/build_site.py
python scripts/publisher/telegram.py --dry-run
```

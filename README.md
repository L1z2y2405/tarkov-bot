# tarkov-discord-notifier

Polls the official Escape from Tarkov X account and forwards any new post to a Discord channel via webhook.

## Features

- Prefers the official X page first.
- Falls back to public mirror sources if X is blocked or changes markup.
- Persists the last processed post ID.
- Uses Playwright with Chromium headless.
- Sends Discord embeds.
- Fully modular and testable.

## Requirements

- Python 3.12+
- `uv`
- Node.js 18+ (only needed to deploy the Cloudflare cron Worker)

## Installation

```bash
uv sync
playwright install
cp .env.example .env
```

Set `DISCORD_WEBHOOK_URL` in `.env` before running.

## Run

```bash
python app.py
```

## Automation

GitHub's own `schedule` cron is not used. A Cloudflare Worker in `cloudflare-cron/` fires every 15 minutes and calls `workflow_dispatch` on `.github/workflows/tarkov-discord-notifier.yml`.

That avoids GitHub Actions scheduler delay (runs can otherwise sit in queue for hours). The workflow still does the crawl, Discord notify, and `data/last_post.json` commit.

```text
Cloudflare Cron (*/15 * * * *)
        │
        ▼
  workflow_dispatch
        │
        ▼
GitHub Actions (uv + Playwright)
        │
        ▼
   Discord webhook
```

### GitHub Actions

Workflow: `.github/workflows/tarkov-discord-notifier.yml`

- Trigger: `workflow_dispatch` only (from Cloudflare, or Run workflow in the Actions tab)
- Checks out the default branch
- Runs the notifier once and exits
- Uses `DISCORD_WEBHOOK_URL` from GitHub Secrets
- Persists `data/last_post.json` back to the repository after a successful notification

Enable the workflow:

1. Push this repository to GitHub.
2. `Settings` → `Secrets and variables` → `Actions` → add `DISCORD_WEBHOOK_URL`.
3. Enable Actions for the repository.
4. Keep the repository public if you want standard GitHub-hosted runner usage to stay free under GitHub's public-repo policy.
5. The workflow needs `contents: write` so it can push the updated post state.

### Cloudflare Worker

Source: `cloudflare-cron/`

Needs Node.js 18+ (`npx wrangler`). One-time setup:

1. Create a fine-grained GitHub PAT for this repo with **Actions: Read and write**.
2. From `cloudflare-cron/`:

```bash
npx wrangler login
npx wrangler secret put GITHUB_DISPATCH_TOKEN
npx wrangler deploy
```

`secret put` asks for a value: paste the PAT there. The argument is the secret **name** (`GITHUB_DISPATCH_TOKEN`), not the token itself.

3. Confirm deploy output includes `schedule: */15 * * * *`.
4. Check the Actions tab within 15 minutes for a `Tarkov Discord Notifier` run triggered by `workflow_dispatch`.

Worker env (in `wrangler.toml`):

- `GITHUB_OWNER`: `L1z2y2405`
- `GITHUB_REPO`: `tarkov-bot`
- `GITHUB_WORKFLOW`: `tarkov-discord-notifier.yml`
- `GITHUB_REF`: `main`

Secret (Cloudflare only, never commit it):

- `GITHUB_DISPATCH_TOKEN`: GitHub PAT used to call the workflow dispatch API

Rotate the PAT: revoke the old token on GitHub, create a new one, then run `npx wrangler secret put GITHUB_DISPATCH_TOKEN` again. Redeploy is not required after updating a secret.

If a cron tick fails, check Worker logs. GitHub should return HTTP `204`. `401` / `403` usually means the PAT is wrong or expired; `404` usually means the owner, repo, or workflow filename is wrong.

## Configuration

- `DISCORD_WEBHOOK_URL`: Discord webhook target
- `CHECK_INTERVAL_SECONDS`: Polling interval in seconds, default `300`
- `TWITTER_USERNAME`: X username to monitor, default `tarkov`
- `HEADLESS`: `true` or `false`
- `RETRY_ATTEMPTS`: retry count for transient failures, default `3`
- `RUN_ONCE`: when `true`, run a single check and exit

## Folder Structure

- `app.py`: application entrypoint and dependency wiring
- `config.py`: environment parsing and settings
- `models.py`: data models
- `storage.py`: JSON persistence for the last post ID
- `twitter.py`: X scraping logic and fallback retrieval
- `discord_webhook.py`: Discord webhook client
- `scheduler.py`: polling loop and delivery orchestration
- `utils.py`: shared retry helper
- `data/last_post.json`: persisted processing state
- `cloudflare-cron/`: Cloudflare Worker that dispatches the GitHub Actions workflow
- `.github/workflows/tarkov-discord-notifier.yml`: one-shot notifier job

## Architecture

```text
Cloudflare Cron
       │
       v
GitHub Actions workflow
       │
       v
┌──────────────┐
│   app.py     │
└──────┬───────┘
       │
       v
┌────────────────────┐
│ NotifierScheduler  │
└───┬─────────┬──────┘
    │         │
    v         v
┌────────┐   ┌───────────────┐
│Storage │   │TwitterClient   │
└────────┘   └──────┬────────┘
                    │
        ┌───────────┴───────────┐
        v                       v
┌──────────────────┐   ┌────────────────────┐
│ Official X page  │   │ Public fallback     │
│ Playwright scrape│   │ mirror scrape       │
└──────────────────┘   └────────────────────┘
                    │
                    v
           ┌────────────────┐
           │ DiscordClient   │
           └────────────────┘
```

## Storage Format

`data/last_post.json`

```json
{
  "last_post_id": "1234567890"
}
```

## Notes

- On GitHub Actions, the client prefers the public X mirror first, then falls back to Playwright.
- Locally, the official X page is attempted first.
- If scraping fails, the client falls back to public mirrors while preserving the same output format.
- Duplicate notifications are prevented by comparing the latest post ID with the stored ID.

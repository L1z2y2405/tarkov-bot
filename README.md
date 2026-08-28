# tarkov-discord-notifier

Polls the official Escape from Tarkov X account and forwards any new post to a Discord channel via webhook.

## Features

- Prefers the official X page first
- Falls back to public mirror sources if X is blocked or changes markup
- Persists the last processed post ID
- Uses Playwright with Chromium headless
- Sends Discord embeds
- Fully modular and testable

## Requirements

- Python 3.12+
- `uv`

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

## GitHub Actions Automation

This repository includes a scheduled workflow at `.github/workflows/tarkov-discord-notifier.yml`.

- Runs every 15 minutes
- Prefers the latest commit on the default branch
- Runs the notifier once and exits
- Uses `DISCORD_WEBHOOK_URL` from GitHub Secrets
- Persists `data/last_post.json` back to the repository after a successful notification

To enable it:

1. Push the workflow file to GitHub.
2. In your repository, go to `Settings` -> `Secrets and variables` -> `Actions`.
3. Add a secret named `DISCORD_WEBHOOK_URL`.
4. Make sure Actions are enabled for the repository.
5. Keep the repository public if you want standard GitHub-hosted runner usage to remain free under GitHub's public-repo policy.
6. Ensure the workflow has `contents: write` permission so it can push the updated post state back to the repo.

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

## Architecture

```text
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

- The official X page is always attempted first.
- If scraping fails, the client falls back to public mirrors while preserving the same output format.
- Duplicate notifications are prevented by comparing the latest post ID with the stored ID.

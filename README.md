# Crypto Meme Hype Bot

A standalone Telegram monitor for Solana meme-token hype. It discovers candidate
channels, ingests messages from explicitly enabled channels, detects cashtags and
Solana contract addresses, scores sentiment, aggregates mentions in SQLite, and
sends alerts through a separate Telegram bot.

The project has no link, dependency, shared data, or runtime coupling to
`crypto-bot` or `crypto-trading-bot`. It does not place trades. Sentiment analysis
uses the local, free VADER library only; no paid AI service, Claude, or other
hosted model is used.

## Requirements

- Python 3.10 or newer
- A Telegram user account
- A Telegram API ID and API hash from [my.telegram.org](https://my.telegram.org)
- A separate Telegram alert bot created with
  [BotFather](https://t.me/BotFather)

## Install

From this repository:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`: create an application at
  `my.telegram.org`, then copy its API credentials.
- `ALERT_BOT_TOKEN`: create an alert bot with BotFather and copy its token.
- `ALERT_CHAT_ID`: send the alert bot a message, then obtain your chat ID from
  `https://api.telegram.org/bot<TOKEN>/getUpdates`.

Keep `.env`, bot tokens, API credentials, and Telethon session files private.
The remaining settings in `.env` control paths, aggregation thresholds,
discovery frequency, and verbose alerts.

## First login

Telethon operates as your Telegram user account. On the first run, start the
listener to create its local session:

```bash
.venv/bin/python -m src.listener
```

Telethon prompts for your phone number, login code, and two-step verification
password if enabled. The listener can then be stopped while channels are
discovered and reviewed.

## Discover and approve channels

Run discovery:

```bash
.venv/bin/python -m src.discover
```

Discovery repeats at `DISCOVER_INTERVAL_HOURS` and writes candidates to
`channels.yaml` with `status: suggested`; it never enables a channel
automatically. Stop the process after a discovery pass if you want to review
immediately.

Review every suggestion. For each trusted channel:

1. Join the channel or chat with the same Telegram user account used by
   Telethon.
2. Edit its entry in `channels.yaml` from `status: suggested` to
   `status: enabled`.

Set untrusted entries to `status: ignored`. Only enabled entries are monitored.
After changing a channel to `status: enabled`, restart the listener process so
it reloads the monitored chats list from `channels.yaml`.

## Run

Run discovery and listening as two separate processes:

```bash
.venv/bin/python -m src.discover
```

```bash
.venv/bin/python -m src.listener
```

The listener stores qualifying mentions in `data/meme.db`, aggregates hype
within the configured time window, and delivers eligible alerts through the
alert bot. Set `VERBOSE=true` in `.env` to also send raw-hit alerts.

## Stop alerts safely

Create the STOP file:

```bash
touch data/STOP
```

While the file exists, message ingestion and SQLite storage continue, but alert
delivery is skipped. Resume alerts by removing it:

```bash
rm data/STOP
```

## Dashboard

Read-only overview (channels, mentions, alerts). FastAPI on localhost; put nginx
with HTTPS + HTTP Basic Auth in front on the VPS.

```bash
.venv/bin/uvicorn dashboard.app:app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001/ — UI loads live data from `GET /api/overview`.

Mock-only preview (no API):

```bash
.venv/bin/python -m http.server 8765 --directory dashboard
```

### VPS (nginx + basic auth sketch)

1. Copy `dashboard/crypto-meme-dashboard.service` to `/etc/systemd/system/`, adjust paths, `systemctl enable --now crypto-meme-dashboard`.
2. Create htpasswd: `sudo htpasswd -c /etc/nginx/.htpasswd-meme youruser`
3. nginx server block (example):

```nginx
server {
    listen 443 ssl;
    server_name meme.example.com;
    # ssl_certificate ...;

    auth_basic "Meme dashboard";
    auth_basic_user_file /etc/nginx/.htpasswd-meme;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
    }
}
```

## Tests

```bash
.venv/bin/pytest -v
```

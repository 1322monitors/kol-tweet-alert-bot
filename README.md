# kol-tweet-alert-bot

[![License: MIT](https://img.shields.io/github/license/1322monitors/kol-tweet-alert-bot?style=flat-square&color=blue)](LICENSE) [![Last commit](https://img.shields.io/github/last-commit/1322monitors/kol-tweet-alert-bot?style=flat-square)](https://github.com/1322monitors/kol-tweet-alert-bot/commits) [![CI](https://github.com/1322monitors/kol-tweet-alert-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/1322monitors/kol-tweet-alert-bot/actions/workflows/ci.yml) [![Built for 1322.io](https://img.shields.io/badge/built%20for-1322.io-3b82f6?style=flat-square)](https://1322.io) [![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](https://github.com/1322monitors/kol-tweet-alert-bot/pulls)

A real-time crypto KOL tweet alert bot in about 120 lines of Python: it watches the X (Twitter) accounts on your 1322 list over the X WebSocket, finds Solana and EVM contract addresses in each new tweet and sends a Telegram alert. It is a crypto Twitter monitoring tool for memecoin entries and KOL-driven trades. X typically arrives 150-250ms after posting. It can also watch the Binance Square creators on your list: Binance Square has its own WebSocket feed and key, so the bot opens a second socket for it. Maintained by the 1322 team; the consumer pattern is generic.

The bot holds a persistent WebSocket per source and reacts the moment a tracked
KOL posts, which is the whole point for memecoin entries and KOL-driven trades.
You do not need an X developer account.

- Crypto KOL tracking: https://1322.io/use-cases/crypto-kol-tracking
- Full walkthrough: https://1322.io/blog/kol-tweet-alert-bot-python
- X quick start: https://1322.io/docs/x
- Binance Square quick start: https://1322.io/docs/binance
- Full event reference: https://1322.io/docs

## What you need

- Python 3.10+ and `pip install -r requirements.txt` (websockets 13+, aiohttp)
- A 1322 X API key from the API access page in your dashboard. X Starter is $250/month for 100 accounts, WebSocket included.
- Optional, for Binance Square: your Binance Square `ws_path` and WS key, from the same API access page (or `GET https://binance.1322.io/v1/dashboard`). Binance Square Lite is $300/month for 5 accounts; its WebSocket is a +$100/month add-on.
- A Telegram bot token from @BotFather and your chat id. Without them the bot prints alerts to the console.

A one-day evaluation is available on request, reviewed by the team, no card: https://1322.io/trial. All plans: https://1322.io/pricing

## Run

```bash
pip install -r requirements.txt
API_KEY=your-x-api-key WS_URL=wss://ws.normal.1322.io/ws/normal \
TELEGRAM_TOKEN=your-bot-token TELEGRAM_CHAT=your-chat-id \
python main.py
```

`WS_URL` defaults to the normal X stream. X Ultimate's selected accounts use `wss://ws.ultimate.1322.io/ws/ultimate` with your ultimate key.

To watch Binance Square as well, add its path and WS key. The bot then connects to `wss://binance.1322.io/{ws_path}?key={ws_key}`:

```bash
BINANCE_WS_PATH=your-binance-ws-path BINANCE_WS_KEY=your-binance-ws-key \
API_KEY=your-x-api-key TELEGRAM_TOKEN=your-bot-token TELEGRAM_CHAT=your-chat-id \
python main.py
```

## How it works

1. Opens the X WebSocket (`wss://ws.normal.1322.io/ws/normal`) with your key in the `X-API-Key` header. The stream carries the accounts on your tracked list.
2. Branches on `type`. A tweet arrives in stages that share one `tweet.id`: `tweet.mini.update` first, then `tweet.update`, `tweet.update.expanded` and `tweet.full` when the tweet has more to add. The bot reads `tweet.author.handle` and `tweet.body.text` on every stage, because a later stage can carry untruncated text, and alerts once per `tweet.id`.
3. Matches a regex for Solana and EVM contract addresses. On a hit, it sends the author, the address and the text to Telegram.
4. If `BINANCE_WS_PATH` and `BINANCE_WS_KEY` are set, it opens a second WebSocket to Binance Square and runs both side by side with `asyncio.gather`. Every Binance Square frame is `{ type, data }`; the bot reads `binance.post` frames (`data.username`, `data.text`, `data.coin_pairs`), alerts once per `data.id`, and skips `binance.pin.update`.
5. Each socket reconnects on its own with a capped backoff (1s, 2s, 4s ... up to 30s). Events are not queued while you are disconnected.

Each 1322 source has its own WebSocket feed and key, managed in one dashboard. 1322 covers eight sources: X (Twitter), Truth Social, Instagram, YouTube, TikTok, Binance Square, FOMO and News.

## Frames it reads

`tweet.mini.update` on the X stream (trimmed, from the [X quick start](https://1322.io/docs/x)):

```json
{
  "id": "6f1d2c3b-1322-4a5e-9b7c-0d1e2f3a4b5c",
  "type": "tweet.mini.update",
  "source": "1322",
  "tweet": {
    "id": "1978456123456789012",
    "type": "TWEET",
    "created_at": 1792073001000,
    "author": {
      "id": "1500000000000000001",
      "handle": "exampledesk",
      "name": "Example Desk",
      "verified": false,
      "metrics": {
        "following": 210,
        "followers": 48210
      }
    },
    "subtweet": null,
    "reply": null,
    "quoted": null,
    "body": {
      "text": "Q3 numbers are live on the blog.",
      "urls": [],
      "mentions": []
    },
    "media": {
      "images": [],
      "videos": [],
      "thumbnails": []
    }
  }
}
```

`binance.post` on the Binance Square stream (trimmed, from the [Binance Square quick start](https://1322.io/docs/binance)):

```json
{
  "type": "binance.post",
  "data": {
    "id": "356349125025001",
    "username": "examplecrypto",
    "display_name": "Example Crypto",
    "content_type": "post",
    "is_reply": false,
    "text": "Watching #bitcoin hold the weekly level.",
    "tendency": "bullish",
    "coin_pairs": [
      "BTCUSDT"
    ],
    "hashtags": [
      "bitcoin"
    ],
    "like_count": 12,
    "view_count": 940,
    "published_at": "2026-10-15T14:03:20Z",
    "detected_at": "2026-10-15T14:03:21Z"
  }
}
```

## Related

- Social alerts for trading bots: https://github.com/1322monitors/social-trading-signals
- Async Python client for the 1322 API: https://github.com/1322monitors/1322-python
- Twitter/X client: https://github.com/1322monitors/twitter-websocket-client
- Minimal consumers, one per source: https://github.com/1322monitors/social-monitor-examples
- Best crypto Twitter monitoring tools (roundup): https://1322.io/blog/best-crypto-twitter-monitoring-tools

MIT licensed.

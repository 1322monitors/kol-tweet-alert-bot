"""Real-time crypto KOL alert bot.

Watches the X (Twitter) accounts on your 1322 list, finds contract addresses
in each new tweet and sends a Telegram alert. Optionally it also watches the
Binance Square creators on your list. Each 1322 source has its own WebSocket
feed and key, so the bot opens one socket per source and runs them side by
side. Set the env vars below (see README). Docs: https://1322.io/docs/x and
https://1322.io/docs/binance
"""
import asyncio
import json
import os
import re
from urllib.parse import quote

import aiohttp
from websockets.asyncio.client import connect

# X: your 1322 X API key, sent as the X-API-Key header.
API_KEY = os.environ.get("API_KEY")
WS_URL = os.environ.get("WS_URL") or "wss://ws.normal.1322.io/ws/normal"
# Optional Binance Square feed: ws_path and WS key from the API access page.
BINANCE_WS_PATH = os.environ.get("BINANCE_WS_PATH", "").strip("/")
BINANCE_WS_KEY = os.environ.get("BINANCE_WS_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT")

# Solana base58 (32-44 chars) or EVM 0x-address.
CONTRACT = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44}|0x[a-fA-F0-9]{40})\b")

# A tweet arrives in stages that share one tweet.id (tweet.mini.update first).
# Every stage is checked, because a later stage can carry untruncated text.
X_TWEET_STAGES = {"tweet.mini.update", "tweet.update", "tweet.update.expanded", "tweet.full"}

alerted = {}  # (source, post id) already alerted (insertion order, capped)


def parse_x(event):
    """X frame -> (tweet id, author, text), or None for other event types."""
    if event.get("type") not in X_TWEET_STAGES:
        return None
    tweet = event.get("tweet") or {}
    handle = (tweet.get("author") or {}).get("handle") or "?"
    return tweet.get("id"), f"@{handle} on X", (tweet.get("body") or {}).get("text") or ""


def parse_binance(frame):
    """Binance Square {type, data} frame -> (post id, author, text), or None."""
    if frame.get("type") != "binance.post":
        return None  # binance.pin.update
    data = frame.get("data") or {}
    pairs = ", ".join(data.get("coin_pairs") or [])
    text = (data.get("text") or "") + (f"\n\npairs: {pairs}" if pairs else "")
    return data.get("id"), f"{data.get('username') or '?'} on Binance Square", text


def check(source, parse, frame):
    """Return the alert text for a frame, or None. Alerts once per post."""
    hit = parse(frame)
    if not hit or not hit[0]:
        return None
    post_id, who, text = hit
    match = CONTRACT.search(text)
    if not match or (source, post_id) in alerted:
        return None
    alerted[(source, post_id)] = True
    if len(alerted) > 10_000:
        del alerted[next(iter(alerted))]
    return f"{who} dropped a contract:\n{match.group(0)}\n\n{text}"


async def alert(session, text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print("ALERT:", text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with session.post(url, json={"chat_id": TELEGRAM_CHAT, "text": text}) as resp:
            if resp.status != 200:
                print(f"telegram send failed (HTTP {resp.status})")
    except Exception as exc:  # noqa: BLE001
        print(f"telegram send failed ({exc})")


async def consume(session, source, url, headers, parse):
    """One WebSocket per source, reconnecting with a capped 1-30s backoff."""
    backoff = 1
    while True:
        try:
            async with connect(url, additional_headers=headers) as ws:
                print(f"{source}: connected")
                backoff = 1
                async for raw in ws:
                    try:
                        frame = json.loads(raw)
                    except ValueError:
                        continue
                    text = check(source, parse, frame) if isinstance(frame, dict) else None
                    if text:
                        print(f"{source}: " + " ".join(text.splitlines()[:2]))
                        await alert(session, text)
        except Exception as exc:  # noqa: BLE001
            print(f"{source}: disconnected ({exc})")
        # Events are not queued while disconnected, so reconnect promptly.
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30)


async def run():
    if not API_KEY:
        raise SystemExit("set API_KEY (see README)")
    async with aiohttp.ClientSession() as session:
        feeds = [consume(session, "x", WS_URL, {"X-API-Key": API_KEY}, parse_x)]
        if BINANCE_WS_PATH and BINANCE_WS_KEY:
            binance_url = f"wss://binance.1322.io/{BINANCE_WS_PATH}?key={quote(BINANCE_WS_KEY, safe='')}"
            feeds.append(consume(session, "binance", binance_url, None, parse_binance))
        elif BINANCE_WS_PATH or BINANCE_WS_KEY:
            print("binance: set both BINANCE_WS_PATH and BINANCE_WS_KEY to watch Binance Square")
        await asyncio.gather(*feeds)


if __name__ == "__main__":
    asyncio.run(run())

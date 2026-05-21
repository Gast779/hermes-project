"""
Crypto Fast Movers — Cron Job
Runs one tick to check for coins with significant price movement.
Uses CoinGecko built-in 1h change as proxy for fast-mover detection.
Sends alerts to Telegram topic: -1003792129186:26
Format: 🚀 ALERT: {symbol} +{change}% in {timeframe}
"""
import os, sys
sys.path.insert(0, '/tmp/hermes_project/hermes_project')
os.chdir('/tmp/hermes_project/hermes_project')

# Load envs: Hermes global env has Telegram token; project .env has other keys
from dotenv import load_dotenv
load_dotenv('/home/hermes/.hermes/.env')
load_dotenv('/tmp/hermes_project/hermes_project/.env')

from config import settings
from crypto_monitor.data_sources import CoinGeckoClient
from scripts.notify_telegram import send_telegram

cg = CoinGeckoClient(
    api_key=os.getenv("COINGECKO_API_KEY"),
    base_url=settings()["crypto_monitor"]["data_source"]["coingecko_base"]
)

# Fetch top 250 coins with 1h data
coins = cg.get_top_markets(per_page=250, page=1, price_change="1h,24h")

candidates = []
for c in coins:
    pct = c.pct_change_1h
    if pct is None:
        continue
    # Threshold: >=5% 1h change (proxy for fast movement)
    if pct >= 5:
        candidates.append(c)

alerts = []
if candidates:
    # Sort by biggest change first
    candidates.sort(key=lambda c: c.pct_change_1h, reverse=True)
    for c in candidates:
        text = f"🚀 ALERT: {c.symbol} +{c.pct_change_1h:.1f}% in 1h"
        ok = send_telegram(text, chat_id="-1003792129186", message_thread_id=26)
        alerts.append((c.symbol, c.pct_change_1h, ok))

cg.close()

# Report
print(f"Coins scanned: {len(coins)}")
print(f"Fast movers (≥5% 1h): {len(candidates)}")
if alerts:
    for sym, pct, ok in alerts:
        print(f"  → {sym}: +{pct:.1f}% 1h (telegram={'OK' if ok else 'FAIL'})")
else:
    print("No fast movers detected above 5% threshold.")

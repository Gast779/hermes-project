"""
Crypto Fast Movers — Cron Job with persisted price history.
Uses local price history for real 5m/1h % change, falls back to CoinGecko 1h proxy.
Sends alerts to Telegram topic: -1003792129186:26
"""
import os, sys, json, time
from pathlib import Path

sys.path.insert(0, '/tmp/hermes_project/hermes_project')
os.chdir('/tmp/hermes_project/hermes_project')

from dotenv import load_dotenv
load_dotenv('/home/hermes/.hermes/.env')
load_dotenv('/tmp/hermes_project/hermes_project/.env')

from config import settings
from crypto_monitor.data_sources import CoinGeckoClient
from scripts.notify_telegram import send_telegram

cg = CoinGeckoClient(
    api_key=os.getenv('COINGECKO_API_KEY'),
    base_url=settings()['crypto_monitor']['data_source']['coingecko_base']
)

coins = cg.get_top_markets(per_page=200, page=1, price_change='1h,24h')

# Load persisted price history if exists
history_path = Path('/tmp/hermes_project/hermes_project/crypto_price_history.json')
history = {}
if history_path.exists():
    with open(history_path, 'r') as f:
        history = json.load(f)

now = time.time()

# Update history
for c in coins:
    if c.id not in history:
        history[c.id] = []
    history[c.id].append({'ts': now, 'price': c.price_usd})
    # Keep last 500 entries (~42h at 5min intervals)
    history[c.id] = history[c.id][-500:]

# Compute real 5m and 1h changes from history
alerts = []
for c in coins:
    hist = history.get(c.id, [])
    if len(hist) < 2:
        continue
    # 5m change
    target_5m = now - 5*60
    old_5m = None
    for entry in hist:
        if entry['ts'] >= target_5m - 90:
            old_5m = entry['price']
            break
    pct_5m = None
    if old_5m is not None and old_5m != 0:
        pct_5m = (c.price_usd - old_5m) / old_5m * 100.0

    # 1h change
    target_1h = now - 60*60
    old_1h = None
    for entry in hist:
        if entry['ts'] >= target_1h - 300:
            old_1h = entry['price']
            break
    pct_1h = None
    if old_1h is not None and old_1h != 0:
        pct_1h = (c.price_usd - old_1h) / old_1h * 100.0

    if pct_5m is not None and pct_5m >= 5:
        alerts.append((c.symbol, pct_5m, '5m', c.price_usd))
    if pct_1h is not None and pct_1h >= 20:
        alerts.append((c.symbol, pct_1h, '1h', c.price_usd))

# Fallback: if no local-history alerts, use CoinGecko 1h proxy
if not alerts:
    for c in coins:
        pct = c.pct_change_1h
        if pct is None:
            continue
        if pct >= 20:
            alerts.append((c.symbol, pct, '1h', c.price_usd))
        elif pct >= 5:
            alerts.append((c.symbol, pct, '1h', c.price_usd))

# Deduplicate by symbol+window
seen = set()
unique_alerts = []
for sym, pct, window, price in alerts:
    key = (sym, window)
    if key in seen:
        continue
    seen.add(key)
    unique_alerts.append((sym, pct, window, price))

# Send alerts
sent = []
for sym, pct, window, price in unique_alerts:
    text = f'🚀 ALERT: {sym} +{pct:.1f}% in {window}'
    ok = send_telegram(text, chat_id='-1003792129186', message_thread_id=26)
    sent.append((sym, pct, window, ok))
    print(f'{text} (telegram={"OK" if ok else "FAIL"})')

# Save history
with open(history_path, 'w') as f:
    json.dump(history, f)

print(f'Coins scanned: {len(coins)}')
print(f'Alerts: {len(sent)}')
if not sent:
    print('No fast movers detected above thresholds (>=5% / 5min, >=20% / 1h).')

cg.close()

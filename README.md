# Hermes Multi-Agent System

Python-проєкт з трьох автономних модулів:

1. **`english_bot/`** — персональний тренер англійської (Grok + Whisper).
2. **`crypto_monitor/`** — звіти CoinGecko 3×/день + real-time fast-movers.
3. **`polymarket_analyzer/`** — Polymarket: top-of-book і depth-aware арбітраж, моніторинг тем, cross-market vs Kalshi, news linker.

> ⚠️ **Polymarket з січня 2026 заблокований в Україні.** Для роботи потрібен 
> VPN/проксі. У `.env` є змінна `POLYMARKET_PROXY` (HTTP або SOCKS5).
> CoinGecko, Grok, Kalshi, RSS-фіди з України працюють нормально.

## Швидкий старт

```bash
# 1. Установка
git clone <repo> && cd hermes_project
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Конфіг
cp config/.env.example .env
# відредагуй .env: XAI_API_KEY, COINGECKO_API_KEY, TELEGRAM_*, POLYMARKET_PROXY

# 3. Перевірка що все працює
python scripts/smoke_test.py
```

## Команди

### Polymarket
```bash
python main.py polymarket scan                       # top-of-book арбітраж
python main.py polymarket depth-scan                 # із slippage-аналізом
python main.py polymarket monitor "trump"            # моніторинг теми
python main.py polymarket monitor "btc" --once       # один тік
python main.py polymarket cross --keyword election   # vs Kalshi
python main.py polymarket news                       # новини → ринки
python main.py polymarket realtime --tokens 123... 456...
```

### Crypto
```bash
python main.py crypto report --notify     # звіт + Telegram
python main.py crypto watch               # daemon fast-movers
```

### English
```bash
python main.py english chat                                   # REPL з тьютором
python main.py english lesson grammar                         # урок граматики
python main.py english voice recording.ogg --backend openai   # голос
```

### Історія / БД
```bash
python main.py db stats                   # скільки записано
python main.py db alerts --coin bitcoin   # останні алерти
python main.py db arb                     # арбітражі за історією
```

### Розклад
```bash
python main.py scheduler                  # запустити всі cron-задачі
python main.py skills                     # перелік для Hermes Dashboard
```

## Структура

```
hermes_project/
├── english_bot/                # уроки + Grok + Whisper
│   ├── grok_client.py
│   ├── lesson_planner.py
│   ├── handlers.py
│   ├── prompts.py
│   └── transcriber.py          # OpenAI Whisper / faster-whisper
├── crypto_monitor/             # CoinGecko + Binance + алерти
│   ├── data_sources.py
│   ├── reports.py
│   ├── alerts.py
│   └── scheduler.py
├── polymarket_analyzer/        # Gamma + CLOB + WebSocket
│   ├── client.py               # з підтримкою proxy
│   ├── arbitrage_internal.py
│   ├── depth_arbitrage.py      # повний orderbook + slippage
│   ├── cross_market.py
│   ├── topic_monitor.py
│   ├── realtime.py
│   ├── news_linker.py          # RSS → ринки
│   └── reporter.py
├── hermes_integration/
├── config/
├── docs/
│   ├── polymarket.md
│   ├── crypto.md
│   └── english.md
├── scripts/
│   ├── notify_telegram.py
│   └── smoke_test.py           # перевірка живих API
├── tests/                      # 22 unit-тести
├── storage.py                  # SQLite сховище
├── main.py
└── requirements.txt
```

## Що тестується

```
tests/test_arbitrage.py   - 6 тестів: buy/sell-arb, fees, volume filter, multi-outcome
tests/test_alerts.py      - 4 тести: 5m/1h windows, cooldown, volume filter
tests/test_extensions.py  - 12 тестів: depth math, keyword extraction, SQLite
                           ────────
                           22 passed in 0.25s
```

## Документація по сферах

- [`docs/polymarket.md`](docs/polymarket.md) — арбітражна математика, API-довідник
- [`docs/crypto.md`](docs/crypto.md) — формат звіту, пороги алертів
- [`docs/english.md`](docs/english.md) — методика, CEFR-syllabus, Whisper

## Безпека

- Усі секрети — лише в `.env`, ніколи в коді.
- Polymarket private key потрібен **тільки** для виконання угод; усі read-операції публічні.
- Telegram-бот пише лише собі (chat_id у конфігу).
- SQLite-БД зберігається в `~/.hermes/state.db` — не в репозиторії.

## Обмеження

- **Polymarket geoblock в UA.** Потрібен проксі/VPN.
- **CoinGecko Demo** = 30 req/min — тротлінг вбудовано.
- **xAI Grok моделі** оновлюються — звір `grok_model` у `settings.yaml` з [docs.x.ai/models](https://docs.x.ai/models).
- **Polymarket** не має sandbox: всі ордери — реальні USDC. Для тестування лише read-операції.
- **fees** для арбітражу зараз 0 (`fee_per_side=0`), але це може змінитися — підкручуй у конфігу.

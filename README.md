# Hermes Multi-Agent System

5 автономних агентів з cross-agent event bus, composite digest та Telegram delivery.

## Агенти

| # | Агент | Функціонал | Telegram тема |
|---|-------|-----------|---------------|
| 1 | 🇬🇧 **english_learning_bot** | AI-тренер англійської (Grok + Whisper) | #24 |
| 2 | 💰 **crypto_monitor** | CoinGecko звіти 3×/день + fast movers | #25, #26 |
| 3 | 🎯 **polymarket_analyzer** | Арбітраж, deep scan, cross-market, news linker, topic monitor | #27–#30 |
| 4 | 🏦 **strategy_engine** | Deribit basis, on-chain whales, LP yield | #32–#34 |
| 5 | 🧠 **coordinator** | Композитний digest: зважена оцінка з усіх сигналів | #31 |

## Telegram теми (11)

| # | Назва | Опис |
|---|-------|------|
| 24 | 🇬🇧 English Learning | Уроки, квізи, щоденний челендж |
| 25 | 💰 Crypto Daily Reports | Ранок / день / вечір |
| 26 | 🚀 Fast Movers | Різкі рухи >5% |
| 27 | 🎯 Polymarket Arbitrage | Top-of-book арбітраж |
| 28 | 🔍 Polymarket Deep | Depth-aware + slippage |
| 29 | 📰 Polymarket News | RSS → ринки |
| 30 | 👁️ Topic Monitor | Моніторинг теми |
| **31** | **📊 Coordinator Digest** | **Композитний score з усіх агентів** |
| **32** | **📈 Backtest Reports** | **Win rate, sharpe, drawdown** |
| **33** | **🎯 Strategy Signals** | **Deribit + On-chain + LP** |
| **34** | **🚨 General Alerts** | **Критичні cross-agent + health** |

## CLI координатора

```bash
# 🧠 Coordinator
python main.py coordinator generate              # згенерувати дайджест
python main.py coordinator status                # оцінки всіх сигналів
python main.py coordinator history --days 7        # історія

# 🏦 Strategy Engine
python main.py deribit scan [BTC|ETH]           # basis arbitrage
python main.py onchain whales [BTC|ETH|All]      # whale transactions
python main.py lp scan [ethereum|arbitrum]       # LP pools по APY
python main.py backtest                          # backtest 4 стратегій
```

## Бектест

```bash
python -m backtest.recorder          # записати сигнали
python main.py backtest              # запустити backtest
python main.py backtest --compare    # порівняти стратегії
```

Метрики: win rate, sharpe, max drawdown, profit factor, Kelly fraction.

## Структура

```
hermes_project/
├── english_bot/              # AI-тренер англійської
├── crypto_monitor/           # CoinGecko + алерти
├── polymarket_analyzer/      # Gamma + CLOB + cross-market
├── deribit/                  # Basis arbitrage + funding
├── onchain/                  # Whale transactions
├── lp_yield/                 # DeFiLlama LP scanner
├── coordination/
│   ├── event_bus.py          # Cross-agent pub/sub
│   ├── reaction_engine.py     # Дії на сигнали
│   ├── coordinator.py         # Композитний digest
│   └── deliver.py             # Telegram delivery
├── strategies/               # Реєстр стратегій + backtest
├── backtest/                 # Бектест-фреймворк
├── scripts/
│   ├── coordinator_digest.py   # Cron: кожні 4h → #31
│   ├── deribit_scan.py         # Cron: 09:00 → #33
│   ├── lp_scan.py              # Cron: Sun 10:00 → #33
│   ├── onchain_whales.py       # Cron: кожні 6h → #34
│   └── health_check.py         # Cron: щогодини → #34
├── tests/                    # 106 unit-тестів
└── config/
    ├── telegram_topics.yml    # 11 тем з thread_id
    └── skills_config.yml      # 5 крон-скілів
```

## Тести

```bash
pytest tests/ -v
# 106 passed
```
| Модуль | Тести |
|--------|-------|
| Safety | 33 |
| Event Bus | 17 |
| English | 11 |
| Crypto | 9 |
| Polymarket | 15 |
| Coordinator | 8 |
| Strategies / Backtest | 21 |

## Cron (5 jobs)

| Job | Розклад | Тема |
|-----|---------|------|
| `coordinator-digest` | `0 */4 * * *` | #31 |
| `deribit-scan` | `0 9 * * *` | #33 |
| `lp-scan` | `0 10 * * 0` | #33 |
| `onchain-whales` | `0 */6 * * *` | #34 |
| `system-health` | `0 * * * *` | #34 |

## Фази

| Фаза | Що | Коміт |
|------|-----|-------|
| 0 | Safety Foundation | — |
| 1 | Safety v2 | — |
| 2 | Event Bus + Reaction Engine | ae4529d |
| 3 | Backtest Framework | — |
| 4 | Deribit + On-chain + LP | 6c86b31 |
| 5 | Coordinator Agent | 0a110a7 |
| 6 | Telegram Digest + Topics 31-34 + Cron | 976341e |

## Безпека

- Всі секрети в `.env`, у `.gitignore`
- Private key Polymarket тільки для угод; read — публічний
- Telegram delivery тільки в теми з конфігу
- SQLite БД в `~/.hermes/state.db`

> ⚠️ Polymarket geoblock в UA — потрібен `POLYMARKET_PROXY` у `.env`.

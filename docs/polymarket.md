# Polymarket Analyzer

> ⚠️ **ВАЖЛИВО для користувачів з України.** Polymarket з січня 2026 офіційно
> заблокований в Україні (як один з 33 країн зі списку обмежень). Прямі
> HTTP-запити з українського IP до `gamma-api.polymarket.com` повертають
> **HTTP 403**. Для роботи з API потрібен:
>
> - VPN з виходом у дозволеній країні (більшість провайдерів — США поза NY),
>   **або**
> - HTTP/SOCKS5-проксі.  У клієнті є підтримка через параметр `proxy=` або
>   змінну `POLYMARKET_PROXY` / `HTTPS_PROXY` у `.env`.
>
> Окремо: торгівля з українського гаманця/IP може порушувати ToS Polymarket.
> Цей код для read-only аналітики й освітніх цілей.

## Які API використовуємо

| API | URL | Що дає | Auth |
|-----|-----|--------|------|
| **Gamma** | `https://gamma-api.polymarket.com` | Метадані ринків: question, slug, outcomes, volume, теги, дати | None |
| **CLOB** | `https://clob.polymarket.com` | Реальний orderbook (bid/ask) per token_id | None (read-only) / Auth для трейдингу |
| **CLOB WS** | `wss://ws-subscriptions-clob.polymarket.com/ws/market` | Стрім оновлень orderbook | None |

### Найважливіші endpoint-и

```
GET  /markets?active=true&limit=100&order=volume24hr   # Gamma
GET  /book?token_id=<asset_id>                          # CLOB
WSS  ws/market    (subscribe: {"type":"MARKET","assets_ids":["..."]})
```

> **Gamma vs CLOB:** Gamma може відставати на кілька секунд (last trade), 
> CLOB — це реальний live-orderbook. Для арбітражних розрахунків — 
> завжди CLOB.

## Математика внутрішнього арбітражу

Для ринку з `n` взаємовиключних outcome-ів справжня сума ймовірностей завжди дорівнює 1.  Ціни в Polymarket — це ймовірності в діапазоні `[0, 1]`, де 1 USDC за share = виплата 1 USDC за правильний result.

### Buy-all arbitrage

Якщо `∑ best_ask_i < 1 − fees`:

```
Купити всі outcomes одночасно за best_ask
→ Якщо результат настав → отримуєш 1 USDC рівно за один з outcomes
→ Прибуток на 1 контракт = 1 − ∑ ask − fees
```

### Sell-all arbitrage

Якщо `∑ best_bid_i > 1 + fees`:

```
Продати всі outcomes (надати liquidity на bid)
→ Отримуєш одразу ∑ bid
→ Виплатиш рівно 1 USDC за один правильний outcome
→ Прибуток = ∑ bid − 1 − fees
```

## Реальні ризики

1. **Slippage.** Best ask може мати малий розмір; для покупки на більшу суму середня ціна буде гірша. Реальна реалізація має враховувати весь стак orderbook.
2. **Fees.** Polymarket поки що 0% maker / 0% taker, але це може змінитися. У `arbitrage_internal.py` є параметр `fee_per_side`.
3. **Resolution risk.** Питання може бути сформульоване так, що його resolution неоднозначний. Завжди читай "Resolution criteria" перед торгом.
4. **Liquidity drain.** Зразу після того, як ти спостерігаєш можливість, інші боти можуть її забрати раніше.
5. **Gas.** Кожен ордер — transaction на Polygon. Для дуже малих edges газ зʼїсть прибуток.

## Команди CLI

```bash
# Сканувати топ-300 активних ринків
python main.py polymarket scan --max-markets 300 --min-edge 0.01

# Моніторити тему "trump" з тиком кожні 30 сек
python main.py polymarket monitor "trump" --interval 30

# Один тік без циклу
python main.py polymarket monitor "btc" --once

# Крос-маркет порівняння з Kalshi
python main.py polymarket cross --keyword "election"

# WebSocket для конкретних token_id
python main.py polymarket realtime --tokens 71321045... 71321046...
```

## Hermes-skill

`polymarket_arbitrage` запускається кожні 30 хв, шле сигнали в Telegram, якщо edge > 1%.

`polymarket_topic_monitor` (вимкнено за замовчуванням) — раз увімкнеш, дай keyword у `skills_config.yml`.

## Що додати далі

- [ ] Облік повного orderbook (sum size × price), а не лише top-of-book.
- [ ] Виконання ордерів через py-clob-client (потрібен private key + USDC на Polygon).
- [ ] Інтеграція ще одного external client (Manifold, Predictit).
- [ ] News linker: підключити RSS Polymarket News + correlator "новина → ринок".

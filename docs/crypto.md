# Crypto Monitor

## Що робить модуль

1. **Daily reports** — звіт по крипторинку 3 рази на день (09:00, 15:00, 21:00 Europe/Kyiv):
   - загальна капіталізація + 24h volume + BTC/ETH dominance,
   - топ-N монет з цінами і %-змінами,
   - топ-10 24h gainers і losers,
   - trending за CoinGecko search.
2. **Fast movers** — фоновий моніторинг різких рухів:
   - **5m** ≥ 5%,
   - **1h** ≥ 20%,
   - з фільтрами по обʼєму (`> $500k 24h`) і market cap (`> $1M`), щоб уникнути шит-коїнів і pump-and-dump-ів,
   - cooldown 30 хв per coin, щоб не спамити.

## Джерела даних

- **CoinGecko** (primary). Demo plan: 30 req/min, 10k req/month.
  Працює з України без обмежень.
  - `GET /global` — стан ринку.
  - `GET /coins/markets?vs_currency=usd&order=market_cap_desc` — топ-N зі змінами.
  - `GET /search/trending` — trending.
- **Binance** (опційно). Public REST, без ключа:
  - `GET /api/v3/ticker/24hr`
  - `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&limit=12`

> Якщо ти зробиш upgrade на CoinGecko Pro, заміни в `config/settings.yaml`:
> `coingecko_base: https://pro-api.coingecko.com/api/v3` — клієнт автоматично 
> підставить правильний заголовок (`x-cg-pro-api-key`).

## Як розраховуються fast-movers

`alerts.py` тримає кільцевий буфер (`deque maxlen=200`) останніх цін для кожного coin_id.  На кожному tick:

```python
old_price = найстаріший запис не старший за (now - window - 30% tolerance)
pct = (latest_price - old_price) / old_price * 100
```

Tolerance 30% потрібен, бо poll_interval = 60s, а вікно — 300s; точна точка "5 хв тому" не завжди є в буфері.

## Telegram-нотифікації

Формат повідомлення (з `config/settings.yaml`):

```
*BTC* `+5.4%` за 5m | $69234.50 | [chart](https://...)
```

Перед першим запуском:

1. Створи бота через `@BotFather` → отримай `TELEGRAM_BOT_TOKEN`.
2. Напиши боту /start.
3. Знайди свій chat_id: `https://api.telegram.org/bot<TOKEN>/getUpdates`.
4. Заповни `.env`.

## Команди

```bash
python main.py crypto report           # один звіт у консоль
python main.py crypto report --notify  # + у Telegram
python main.py crypto watch            # daemon fast-movers
python main.py scheduler               # повний розклад (reports за cron)
```

## Що можна покращити

- [ ] Додати OHLCV-аналіз Binance для перевірки CoinGecko (захист від спайків).
- [ ] Crypto news через CryptoPanic API або RSS CoinDesk/TheBlock.
- [ ] Виявлення pump-схем: одночасний пік volume + сильний move.
- [ ] Зберігати історію алертів у SQLite для аналізу false-positives.

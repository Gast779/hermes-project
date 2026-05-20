"""
Smoke-test реальних API: запусти після того, як заповнив .env

Перевіряє:
    1. Polymarket Gamma API доступний (отримання списку ринків).
    2. Polymarket CLOB API доступний (orderbook).
    3. CoinGecko API + ключ працює.
    4. Grok API + ключ працює.
    5. Telegram-бот шле повідомлення.

Жодних реальних угод не виконується.

Usage:
    python scripts/smoke_test.py            # запустити всі перевірки
    python scripts/smoke_test.py polymarket # лише одну
"""
from __future__ import annotations

import logging
import sys
from typing import Callable

# Шлях до проєкту в sys.path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import env, setup_logging

setup_logging()
log = logging.getLogger("smoke")


def check_polymarket_gamma() -> bool:
    from polymarket_analyzer import PolymarketClient
    with PolymarketClient() as c:
        markets = c.fetch_markets_raw(active=True, limit=3)
    print(f"  ✅ Gamma: got {len(markets)} markets")
    if markets:
        first = markets[0]
        print(f"     example question: {first.get('question', '')[:80]!r}")
    return len(markets) > 0


def check_polymarket_clob() -> bool:
    from polymarket_analyzer import PolymarketClient
    with PolymarketClient() as c:
        markets = c.fetch_markets(active=True, max_total=5)
        # Беремо перший токен з найликвіднішого ринку
        for m in markets:
            for o in m.outcomes:
                bid, ask = c.fetch_best_prices(o.token_id)
                if bid is not None or ask is not None:
                    print(f"  ✅ CLOB: {m.slug} → {o.name}: bid={bid} ask={ask}")
                    return True
    print("  ⚠️  CLOB: жодного non-empty orderbook серед перших 5 ринків")
    return False


def check_coingecko() -> bool:
    from crypto_monitor import CoinGeckoClient
    key = env("COINGECKO_API_KEY")
    cg = CoinGeckoClient(api_key=key)
    try:
        g = cg.get_global()
        cap = (g.get("total_market_cap") or {}).get("usd", 0)
        top = cg.get_top_markets(per_page=3, page=1)
    finally:
        cg.close()
    print(f"  ✅ CoinGecko: total cap ${cap/1e12:.2f}T, top: {[c.symbol for c in top]}")
    return cap > 0


def check_grok() -> bool:
    from english_bot import GrokClient
    key = env("XAI_API_KEY", required=False)
    if not key:
        print("  ❌ XAI_API_KEY not set, skipping")
        return False
    g = GrokClient(api_key=key)
    answer = g.chat_simple(
        "You answer with one short sentence in English.",
        "What is the capital of Ukraine?",
        max_tokens=30,
    )
    print(f"  ✅ Grok answered: {answer!r}")
    return "kyiv" in answer.lower() or "kiev" in answer.lower()


def check_telegram() -> bool:
    from scripts.notify_telegram import send_telegram
    ok = send_telegram("🤖 *Hermes smoke test* — якщо ти це бачиш, нотифікації працюють.")
    if ok:
        print("  ✅ Telegram: повідомлення відправлено")
    else:
        print("  ❌ Telegram: not configured або помилка (див. логи)")
    return ok


CHECKS: dict[str, Callable[[], bool]] = {
    "polymarket_gamma": check_polymarket_gamma,
    "polymarket_clob":  check_polymarket_clob,
    "coingecko":        check_coingecko,
    "grok":             check_grok,
    "telegram":         check_telegram,
}


def main() -> int:
    targets = sys.argv[1:] or list(CHECKS)
    failed = 0
    for name in targets:
        # дозволяємо часткові імена ("polymarket" → обидва)
        matched = [k for k in CHECKS if k.startswith(name) or name in k]
        if not matched:
            print(f"❌ Unknown check: {name}")
            failed += 1
            continue
        for k in matched:
            print(f"\n── {k} ──")
            try:
                if not CHECKS[k]():
                    failed += 1
            except Exception as e:        # noqa: BLE001
                print(f"  ❌ {k} raised: {e}")
                failed += 1
    print(f"\n{'='*40}\n{'✅ All checks passed' if not failed else f'❌ {failed} check(s) failed'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

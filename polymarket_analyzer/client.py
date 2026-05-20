"""
HTTP-клієнт до Polymarket.

Об'єднує два API:
    - Gamma   — публічні метадані ринків та подій (без авторизації).
    - CLOB    — публічний orderbook (без авторизації для read-only).

Документація:
    https://docs.polymarket.com/developers/gamma-markets-api/get-markets
    https://docs.polymarket.com/developers/CLOB/clients/methods-public

Rate limits (грудень 2025 — травень 2026):
    Gamma:  ≈ 60 req/min для unauthenticated.
    CLOB:   ≈ 100 req/min для unauthenticated.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

import httpx

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Моделі даних
# --------------------------------------------------------------------------- #
@dataclass
class Outcome:
    """Один вихід ринку (наприклад "Yes" / "No" або одна опція в multi-choice)."""
    token_id: str             # ERC-1155 token id у CTF — потрібен для orderbook-запитів
    name: str                 # "Yes", "No", або текст опції
    price: float | None       # last trade price з gamma (0..1, ймовірність)
    best_bid: float | None = None
    best_ask: float | None = None
    volume_24h: float | None = None


@dataclass
class Market:
    """Один ринок Polymarket з повним набором полів, що нам потрібен."""
    id: str
    condition_id: str         # унікальний condition_id у CTF
    question: str             # людська назва ("Will Trump win 2028?")
    slug: str
    outcomes: list[Outcome] = field(default_factory=list)
    end_date_iso: str | None = None
    volume_usd: float = 0.0
    liquidity_usd: float = 0.0
    active: bool = True
    closed: bool = False
    tags: list[str] = field(default_factory=list)

    @property
    def is_binary(self) -> bool:
        return len(self.outcomes) == 2

    @property
    def total_volume(self) -> float:
        return self.volume_usd


# --------------------------------------------------------------------------- #
# Клієнт
# --------------------------------------------------------------------------- #
class PolymarketClient:
    """
    Тонкий клієнт зі вбудованим backoff і простим in-memory rate-limit.

    Приклад:
        client = PolymarketClient()
        markets = client.fetch_markets(active=True, limit=200)
        ob = client.fetch_orderbook(markets[0].outcomes[0].token_id)
    """

    def __init__(
        self,
        gamma_base: str = "https://gamma-api.polymarket.com",
        clob_base: str = "https://clob.polymarket.com",
        timeout: float = 15.0,
        max_retries: int = 3,
        min_request_interval: float = 0.6,   # ~ 100 req/min з запасом
        proxy: str | None = None,            # http://user:pass@host:port — для обходу geoblock
    ):
        self.gamma_base = gamma_base.rstrip("/")
        self.clob_base = clob_base.rstrip("/")
        self.max_retries = max_retries
        self.min_request_interval = min_request_interval
        self._last_call = 0.0
        # Підтримка проксі: Polymarket заблокований у деяких країнах (UA з січня 2026).
        # Використай HTTP/SOCKS5-проксі через аргумент proxy=, або змінну середовища HTTPS_PROXY.
        import os
        proxy = proxy or os.getenv("POLYMARKET_PROXY") or os.getenv("HTTPS_PROXY")
        client_kwargs: dict = {
            "timeout": timeout,
            "headers": {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (hermes-polymarket/1.0)",
            },
            "follow_redirects": True,
        }
        if proxy:
            client_kwargs["proxy"] = proxy
        self._http = httpx.Client(**client_kwargs)

    # ---- low-level ------------------------------------------------------- #
    def _throttle(self) -> None:
        delta = time.monotonic() - self._last_call
        if delta < self.min_request_interval:
            time.sleep(self.min_request_interval - delta)
        self._last_call = time.monotonic()

    def _get(self, url: str, params: dict | None = None) -> Any:
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                r = self._http.get(url, params=params)
                if r.status_code == 429:
                    wait = 2 ** attempt
                    log.warning("429 rate-limited; sleeping %ss (attempt %s)", wait, attempt)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                log.warning("HTTP error %s on %s (attempt %s/%s)", e, url, attempt, self.max_retries)
                if attempt == self.max_retries:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    # ---- Gamma: markets metadata ----------------------------------------- #
    def fetch_markets_raw(
        self,
        *,
        active: bool = True,
        closed: bool = False,
        limit: int = 100,
        offset: int = 0,
        order: str = "volume24hr",
        ascending: bool = False,
    ) -> list[dict]:
        """Сирий JSON з Gamma /markets."""
        url = f"{self.gamma_base}/markets"
        params = {
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "limit": limit,
            "offset": offset,
            "order": order,
            "ascending": str(ascending).lower(),
        }
        return self._get(url, params=params)

    def fetch_markets(
        self,
        *,
        active: bool = True,
        closed: bool = False,
        limit: int = 100,
        max_total: int = 500,
        order: str = "volume24hr",
    ) -> list[Market]:
        """
        Постранична вигрузка ринків + парсинг у dataclass.
        max_total — стоп, щоб не висмоктати весь Gamma; за замовчуванням топ-500.
        """
        out: list[Market] = []
        offset = 0
        page = min(limit, 100)            # Gamma приймає до 500, але робимо менше — стабільніше
        while len(out) < max_total:
            batch = self.fetch_markets_raw(
                active=active, closed=closed, limit=page, offset=offset, order=order
            )
            if not batch:
                break
            out.extend(self._parse_market(m) for m in batch if m)
            if len(batch) < page:
                break
            offset += page
        return out[:max_total]

    @staticmethod
    def _parse_market(m: dict) -> Market | None:
        """
        Дістати найважливіші поля. Polymarket іноді віддає `outcomes` як JSON-рядок —
        обережно парсимо.
        """
        import json

        try:
            outcomes_raw = m.get("outcomes") or "[]"
            prices_raw = m.get("outcomePrices") or "[]"
            token_ids_raw = m.get("clobTokenIds") or "[]"

            outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
            prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
            token_ids = json.loads(token_ids_raw) if isinstance(token_ids_raw, str) else token_ids_raw

            outcome_objs = []
            for i, name in enumerate(outcomes):
                token_id = token_ids[i] if i < len(token_ids) else None
                price = float(prices[i]) if i < len(prices) and prices[i] not in (None, "") else None
                if token_id is None:
                    continue
                outcome_objs.append(Outcome(token_id=str(token_id), name=str(name), price=price))

            return Market(
                id=str(m.get("id", "")),
                condition_id=str(m.get("conditionId", "")),
                question=str(m.get("question", "")),
                slug=str(m.get("slug", "")),
                outcomes=outcome_objs,
                end_date_iso=m.get("endDate"),
                volume_usd=float(m.get("volume", 0) or 0),
                liquidity_usd=float(m.get("liquidity", 0) or 0),
                active=bool(m.get("active", False)),
                closed=bool(m.get("closed", False)),
                tags=[t.get("label", "") for t in (m.get("tags") or []) if isinstance(t, dict)],
            )
        except Exception as e:           # noqa: BLE001
            log.warning("Failed to parse market id=%s: %s", m.get("id"), e)
            return None

    def search_markets(self, keyword: str, *, limit: int = 200) -> list[Market]:
        """Локальний фільтр по слову — Gamma не має повноцінного full-text search."""
        kw = keyword.lower().strip()
        markets = self.fetch_markets(active=True, closed=False, max_total=limit)
        return [m for m in markets if kw in m.question.lower() or kw in m.slug.lower()]

    # ---- CLOB: orderbook -------------------------------------------------- #
    def fetch_orderbook(self, token_id: str) -> dict:
        """
        Найкращі bid/ask по конкретному outcome-токену.

        Повертає словник:
            {"asks": [{"price": "0.42", "size": "...."}, ...],
             "bids": [{"price": "0.41", "size": "...."}, ...],
             "market": "...", "asset_id": "...", ...}
        """
        url = f"{self.clob_base}/book"
        return self._get(url, params={"token_id": token_id})

    def fetch_best_prices(self, token_id: str) -> tuple[float | None, float | None]:
        """Зручний хелпер: повертає (best_bid, best_ask) як float, або (None, None)."""
        try:
            ob = self.fetch_orderbook(token_id)
        except httpx.HTTPError:
            return None, None

        def _top(side: str) -> float | None:
            arr = ob.get(side) or []
            if not arr:
                return None
            # CLOB сортує: для bids — спадання, для asks — зростання. Беремо перший.
            try:
                return float(arr[0]["price"])
            except (KeyError, ValueError, TypeError):
                return None

        return _top("bids"), _top("asks")

    def enrich_market_with_book(self, market: Market) -> Market:
        """Заповнити best_bid / best_ask по кожному outcome."""
        for o in market.outcomes:
            o.best_bid, o.best_ask = self.fetch_best_prices(o.token_id)
        return market

    # ---- lifecycle ------------------------------------------------------- #
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "PolymarketClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

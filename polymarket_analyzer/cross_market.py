"""
Крос-маркет аналіз: Polymarket vs інші prediction markets.

Архітектура:
    - ExternalMarket — стандартизована модель «ринок-десь-ще».
    - ExternalMarketClient — інтерфейс для будь-якого зовнішнього джерела.
    - KalshiClient — реалізація для Kalshi (можна додати інші: Manifold, PredictIt, ...).
    - CrossMarketAnalyzer — матчер ринків і шукач розбіжностей.

Чому Kalshi:
    Kalshi — найбільший конкурент Polymarket у США з публічним API
    (https://trading-api.readme.io/), що дає bid/ask по ринках.

УВАГА: у різних платформ різні правила розрахунку (resolution rules).
Перш ніж торгувати на основі сигналу — переконайся, що формулювання питання
збігається.  Цей модуль СИГНАЛІЗУЄ потенційну розбіжність, не виконує її.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Protocol

from .client import Market, PolymarketClient

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Зовнішня модель ринку
# --------------------------------------------------------------------------- #
@dataclass
class ExternalMarket:
    source: str               # "kalshi", "manifold", ...
    market_id: str
    question: str
    outcome_name: str         # "Yes" / "No" / опція
    probability: float | None  # 0..1
    best_bid: float | None = None
    best_ask: float | None = None
    end_date_iso: str | None = None


class ExternalMarketClient(Protocol):
    """Контракт для зовнішнього джерела."""
    source_name: str
    def fetch(self, keyword: str | None = None) -> list[ExternalMarket]: ...


# --------------------------------------------------------------------------- #
# Аналізатор
# --------------------------------------------------------------------------- #
@dataclass
class Discrepancy:
    topic_similarity: float
    polymarket_question: str
    external_question: str
    source: str
    outcome: str
    pm_prob: float
    ext_prob: float
    diff: float                # pm − ext (додатне → Polymarket переоцінює)
    pm_market_id: str
    ext_market_id: str


class CrossMarketAnalyzer:
    """
    Шукаємо розбіжності між Polymarket і одним або кількома зовнішніми ринками.

    Метод матчингу — fuzzy similarity по question (SequenceMatcher).
    Поріг similarity_threshold можна підкручувати: 0.55 — досить ліберально,
    0.75 — лише дуже схожі формулювання.
    """

    def __init__(
        self,
        pm_client: PolymarketClient,
        external_clients: Iterable[ExternalMarketClient],
        *,
        min_diff: float = 0.07,
        similarity_threshold: float = 0.60,
    ):
        self.pm_client = pm_client
        self.external_clients = list(external_clients)
        self.min_diff = min_diff
        self.similarity_threshold = similarity_threshold

    # ---------------------------------------------------------------- #
    @staticmethod
    def _sim(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _flatten_polymarket(self, markets: Iterable[Market]) -> list[tuple[Market, str, float | None]]:
        rows: list[tuple[Market, str, float | None]] = []
        for m in markets:
            for o in m.outcomes:
                rows.append((m, o.name, o.price))
        return rows

    def find_discrepancies(self, keyword: str | None = None, *, max_markets: int = 300) -> list[Discrepancy]:
        pm_markets = self.pm_client.fetch_markets(active=True, max_total=max_markets)
        if keyword:
            kw = keyword.lower()
            pm_markets = [m for m in pm_markets if kw in m.question.lower() or kw in m.slug.lower()]
        pm_rows = self._flatten_polymarket(pm_markets)

        result: list[Discrepancy] = []
        for client in self.external_clients:
            try:
                ext_rows = client.fetch(keyword)
            except Exception as e:        # noqa: BLE001
                log.warning("External source %s failed: %s", client.source_name, e)
                continue

            for ext in ext_rows:
                if ext.probability is None:
                    continue
                # Шукаємо найкращий матч на стороні Polymarket
                best: tuple[float, Market, str, float] | None = None
                for m, oname, pprice in pm_rows:
                    if pprice is None:
                        continue
                    if oname.lower() != ext.outcome_name.lower():
                        continue
                    s = self._sim(m.question, ext.question)
                    if best is None or s > best[0]:
                        best = (s, m, oname, pprice)
                if best is None or best[0] < self.similarity_threshold:
                    continue

                s, m, oname, pprice = best
                diff = pprice - ext.probability
                if abs(diff) >= self.min_diff:
                    result.append(
                        Discrepancy(
                            topic_similarity=s,
                            polymarket_question=m.question,
                            external_question=ext.question,
                            source=client.source_name,
                            outcome=oname,
                            pm_prob=pprice,
                            ext_prob=ext.probability,
                            diff=diff,
                            pm_market_id=m.id,
                            ext_market_id=ext.market_id,
                        )
                    )
        result.sort(key=lambda d: abs(d.diff), reverse=True)
        return result


# --------------------------------------------------------------------------- #
# Приклад зовнішнього клієнта — Kalshi (заглушка з реальними endpoint-ами)
# --------------------------------------------------------------------------- #
class KalshiClient:
    """
    Простий read-only клієнт до публічного Kalshi API.
    Для авторизованих операцій потрібен email + password (login → token).
    Тут — лише публічні endpoint-и /trade-api/v2/markets.

    Документація: https://trading-api.readme.io/reference/getmarkets
    """
    source_name = "kalshi"

    def __init__(self, base_url: str = "https://api.elections.kalshi.com/trade-api/v2"):
        import httpx
        self.base = base_url.rstrip("/")
        self._http = httpx.Client(timeout=15.0, headers={"Accept": "application/json"})

    def fetch(self, keyword: str | None = None) -> list[ExternalMarket]:
        """
        Тягне активні ринки Kalshi. Якщо передано keyword — фільтрує локально
        (Kalshi API не має full-text search у публічному ендпоїнті).
        """
        url = f"{self.base}/markets"
        out: list[ExternalMarket] = []
        cursor = None
        fetched = 0
        while fetched < 500:
            params = {"limit": 200, "status": "open"}
            if cursor:
                params["cursor"] = cursor
            try:
                r = self._http.get(url, params=params)
                r.raise_for_status()
                data = r.json()
            except Exception as e:        # noqa: BLE001
                log.warning("Kalshi fetch failed: %s", e)
                break

            for m in data.get("markets", []):
                title = m.get("title", "") or m.get("subtitle", "")
                if keyword and keyword.lower() not in title.lower():
                    continue
                # Kalshi використовує yes_bid / yes_ask у центах (0..100)
                yes_bid = m.get("yes_bid")
                yes_ask = m.get("yes_ask")
                if yes_bid is None or yes_ask is None:
                    continue
                mid_yes = (yes_bid + yes_ask) / 2.0 / 100.0

                out.append(ExternalMarket(
                    source=self.source_name,
                    market_id=str(m.get("ticker", "")),
                    question=title,
                    outcome_name="Yes",
                    probability=mid_yes,
                    best_bid=yes_bid / 100.0,
                    best_ask=yes_ask / 100.0,
                    end_date_iso=m.get("close_time"),
                ))
                out.append(ExternalMarket(
                    source=self.source_name,
                    market_id=str(m.get("ticker", "")),
                    question=title,
                    outcome_name="No",
                    probability=1.0 - mid_yes,
                    best_bid=(100 - yes_ask) / 100.0,
                    best_ask=(100 - yes_bid) / 100.0,
                    end_date_iso=m.get("close_time"),
                ))
                fetched += 1

            cursor = data.get("cursor")
            if not cursor:
                break
        return out

    def close(self) -> None:
        self._http.close()

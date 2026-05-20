"""
Пошук арбітражу ВСЕРЕДИНІ Polymarket.

Теорія:
    Для будь-якого ринку з повним набором взаємовиключних outcomes
    сума ймовірностей істинного йде = 1.  Тому:

    *  Якщо ∑ best_ask < 1  → купивши усі outcomes за best_ask дохід на 1 USDC
       за кожний контракт гарантовано, прибуток = 1 − ∑ ask (мінус fees).
    *  Якщо ∑ best_bid > 1  → продавши усі outcomes за best_bid (тобто
       видавши синтетичне «1 на щось», що сумарно завжди = 1) отримуємо
       prepaid 1 USDC < ∑ bids → прибуток = ∑ bid − 1.

Особливості Polymarket:
    - Це CLOB на CTF (ERC-1155); ціни в діапазоні 0..1 (USDC per share).
    - Біржа стягує fee при tape-фіксації; зараз для розрахунків
      допускаємо `fee_per_side` (за замовчуванням 0 — Polymarket поки що
      має нульові маркет-комісії, але це може змінитися).
    - Для НЕ-binary ринків (multi-choice) теж працює: важлива лише
      ⩽-залежність ∑ probability = 1 між взаємовиключними outcomes.

Цей модуль не торгує — лише знаходить потенційні нерівноваги.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Iterable

from .client import Market, Outcome, PolymarketClient

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Структура можливості
# --------------------------------------------------------------------------- #
@dataclass
class ArbitrageOpportunity:
    market_id: str
    question: str
    slug: str
    kind: str                  # "buy_all"  або "sell_all"
    edge: float                # абсолютна перевага, у USDC на 1 контракт
    sum_asks: float | None
    sum_bids: float | None
    outcomes: list[dict]       # для відображення
    volume_usd: float
    end_date_iso: str | None

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Finder
# --------------------------------------------------------------------------- #
class InternalArbitrageFinder:
    """
    Знаходить ринки, де сума цін по всіх outcomes створює арбітражну можливість.
    """

    def __init__(
        self,
        client: PolymarketClient,
        *,
        min_edge: float = 0.01,
        min_volume_usd: float = 1_000.0,
        fee_per_side: float = 0.0,
    ):
        self.client = client
        self.min_edge = min_edge
        self.min_volume_usd = min_volume_usd
        self.fee_per_side = fee_per_side

    # ---- analysis -------------------------------------------------------- #
    def analyze_market(self, market: Market) -> ArbitrageOpportunity | None:
        """
        Заповнює orderbook для всіх outcomes і шукає арбітраж.
        Повертає Opportunity або None.
        """
        if market.volume_usd < self.min_volume_usd:
            return None

        # Підтягуємо орди
        self.client.enrich_market_with_book(market)

        asks = [o.best_ask for o in market.outcomes]
        bids = [o.best_bid for o in market.outcomes]

        # Якщо хоч одна сторона не зчиталась — арбітраж невиконуваний
        sum_asks = sum(asks) if all(a is not None for a in asks) else None
        sum_bids = sum(bids) if all(b is not None for b in bids) else None

        # Враховуємо fees (комісія на кожен з n outcomes)
        n = len(market.outcomes)
        fee_total = self.fee_per_side * n

        buy_edge  = (1.0 - sum_asks - fee_total) if sum_asks is not None else None
        sell_edge = (sum_bids - 1.0 - fee_total) if sum_bids is not None else None

        # Вибираємо найкращий бік
        kind: str | None = None
        edge: float | None = None
        if buy_edge is not None and buy_edge > self.min_edge:
            kind, edge = "buy_all", buy_edge
        if sell_edge is not None and sell_edge > self.min_edge:
            if edge is None or sell_edge > edge:
                kind, edge = "sell_all", sell_edge

        if kind is None or edge is None:
            return None

        return ArbitrageOpportunity(
            market_id=market.id,
            question=market.question,
            slug=market.slug,
            kind=kind,
            edge=edge,
            sum_asks=sum_asks,
            sum_bids=sum_bids,
            outcomes=[
                {
                    "name": o.name,
                    "best_bid": o.best_bid,
                    "best_ask": o.best_ask,
                    "token_id": o.token_id,
                }
                for o in market.outcomes
            ],
            volume_usd=market.volume_usd,
            end_date_iso=market.end_date_iso,
        )

    def find(
        self,
        markets: Iterable[Market] | None = None,
        *,
        max_markets: int = 300,
    ) -> list[ArbitrageOpportunity]:
        """
        Запустити пошук по списку ринків.  Якщо markets=None — підтягне
        активні ринки з найбільшим обʼємом.
        """
        if markets is None:
            markets = self.client.fetch_markets(active=True, closed=False, max_total=max_markets)

        opps: list[ArbitrageOpportunity] = []
        for i, m in enumerate(markets, 1):
            try:
                opp = self.analyze_market(m)
                if opp is not None:
                    opps.append(opp)
                    log.info("[%s/%s] FOUND arb in %s (edge %.3f)", i, "?", m.slug, opp.edge)
                else:
                    log.debug("[%s] no arb in %s", i, m.slug)
            except Exception as e:        # noqa: BLE001
                log.warning("analyze_market failed for %s: %s", m.id, e)
        # сортуємо за edge: найжирніший зверху
        opps.sort(key=lambda o: o.edge, reverse=True)
        return opps

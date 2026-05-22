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

Safety-інтеграція (Фаза 1):
    - Перед публікацією сигналу → перевірка circuit breakers
    - Оцінка resolution risk → скипаємо небезпечні ринки
    - Fee-aware edge (з урахуванням fee_per_side)
    - Kelly sizing → recommend_usd для звіту
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict, field
from typing import Iterable, Any

from .client import Market, Outcome, PolymarketClient

log = logging.getLogger(__name__)


# --- lazy imports safety modules (циркулярні) ---
def _import_safety():
    """Lazy import — уникає циркулярних залежностей на старті."""
    from risk.position_sizing import recommend_size, SizingParams, StrategyType
    from risk.circuit_breakers import trading_allowed
    from polymarket_analyzer.resolution_risk import score_resolution_risk
    return recommend_size, SizingParams, StrategyType, trading_allowed, score_resolution_risk


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

    safe_to_trade: bool = True
    resolution_risk: float = 0.0
    recommended_usd: float | None = None
    sizing_reasoning: list[str] = field(default_factory=list)

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

    # ---- safety wrapper (Фаза 1) ------------------------------------- #
    def analyze_market_safely(
        self,
        market: Market,
        *,
        bankroll_usd: float = 10_000,  # для Kelly sizing
        correlated_exposure_usd: float = 0,
    ) -> ArbitrageOpportunity | None:
        """
        analyze_market з усіма safety checks:
        1. Circuit breaker (трейдинг дозволено?)
        2. Resolution risk (ринок не ambiguous?)
        3. Kelly sizing (рекомендований розмір)
        """
        recommend_size, SizingParams, StrategyType, trading_allowed, score_resolution_risk = (
            _import_safety()
        )

        # --- 1. Circuit breaker ---
        allowed, tripped = trading_allowed()
        if not allowed:
            log.warning("Trade blocked: breakers tripped: %s", tripped)
            return None

        # --- 2. Resolution risk ---
        market_dict = {
            "question": market.question,
            "description": "",  # client не містить description
            "resolution_source": "",
        }
        risk = score_resolution_risk(market_dict)
        if not risk.safe_to_trade:
            log.info("Skip risky market: %s - %s", market.slug, risk.red_flags)
            return None

        # --- 3. Find arbitrage ---
        opp = self.analyze_market(market)
        if opp is None:
            return None

        # --- 4. Fee-aware: edge already computed with fee_per_side ---
        # nothing extra needed

        # --- 5. Kelly sizing ---
        sizing = recommend_size(SizingParams(
            bankroll_usd=bankroll_usd,
            edge=opp.edge,  # decimal
            win_probability=0.95,  # arb = near-certain для sizing
            payout_ratio=opp.edge,  # rough estimate
            confidence=0.7 if risk.overall_risk < 0.2 else 0.5,
            strategy_type=StrategyType.POLYMARKET_ARB,
            correlated_exposure_usd=correlated_exposure_usd,
        ))

        # Tag the opportunity
        opp.safe_to_trade = risk.safe_to_trade
        opp.resolution_risk = risk.overall_risk
        opp.recommended_usd = sizing.recommended_usd
        opp.sizing_reasoning = sizing.reasoning

        return opp

    def find_safe(
        self,
        markets: Iterable[Market] | None = None,
        *,
        max_markets: int = 300,
        bankroll_usd: float = 10_000,
    ) -> list[ArbitrageOpportunity]:
        """find() з safety checks та Kelly sizing для кожного arбітражу."""
        if markets is None:
            markets = self.client.fetch_markets(active=True, closed=False, max_total=max_markets)

        opps: list[ArbitrageOpportunity] = []
        for i, m in enumerate(markets, 1):
            try:
                opp = self.analyze_market_safely(m, bankroll_usd=bankroll_usd)
                if opp is not None:
                    opps.append(opp)
                    log.info(
                        "[%s/%s] SAFE arb in %s edge=%.3f rec=$%s risk=%.2f",
                        i, "?", m.slug, opp.edge, opp.recommended_usd, opp.resolution_risk
                    )
                else:
                    log.debug("[%s] no safe arb in %s", i, m.slug)
            except Exception as e:
                log.warning("analyze_market_safely failed for %s: %s", m.id, e)
        opps.sort(key=lambda o: o.edge, reverse=True)
        return opps

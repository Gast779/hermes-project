"""
Аналіз глибини orderbook для реалістичного оцінювання арбітражу.

Базовий `arbitrage_internal.py` дивиться лише на top-of-book.
Цей модуль рахує:

    - яка максимальна *сума* (USDC), яку можна реально проторгувати
      зі збереженням позитивного edge,
    - середньозважену ціну при заданому обʼємі,
    - очікуваний slippage.

Це критично, бо часто на best ask стоїть лише $50, а тобі треба зайти
на $1000 — реальна середня ціна буде гірша.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from .client import Market, PolymarketClient

log = logging.getLogger(__name__)


@dataclass
class DepthLevel:
    price: float
    size: float                    # к-сть shares
    cumulative_size: float = 0.0
    cumulative_cost: float = 0.0   # USDC, накопичено

    @property
    def avg_price(self) -> float:
        return self.cumulative_cost / self.cumulative_size if self.cumulative_size else 0.0


@dataclass
class ExecutionEstimate:
    side: str                      # "buy" | "sell"
    target_size: float             # скільки shares хочемо
    achievable_size: float         # скільки реально доступно
    avg_price: float
    worst_price: float
    slippage_bps: float            # vs best price, basis points


# --------------------------------------------------------------------------- #
def _parse_levels(side: list, *, reverse_sort: bool) -> list[DepthLevel]:
    """
    side = orderbook["bids"] або ["asks"].  Polymarket віддає рядки.
    reverse_sort=True для bids (від найвищої до найнижчої).
    """
    out: list[DepthLevel] = []
    for lvl in side or []:
        try:
            price = float(lvl["price"])
            size = float(lvl["size"])
        except (KeyError, ValueError, TypeError):
            continue
        if size <= 0:
            continue
        out.append(DepthLevel(price=price, size=size))
    out.sort(key=lambda x: x.price, reverse=reverse_sort)

    cum_size = 0.0
    cum_cost = 0.0
    for lvl in out:
        cum_size += lvl.size
        cum_cost += lvl.size * lvl.price
        lvl.cumulative_size = cum_size
        lvl.cumulative_cost = cum_cost
    return out


def estimate_execution(
    levels: Sequence[DepthLevel],
    target_shares: float,
) -> ExecutionEstimate | None:
    """
    Скільки коштуватиме купити/продати `target_shares` за існуючим стаком.
    levels мають бути ВЖЕ відсортовані: для ask — від мін. ціни, для bid — від макс.
    """
    if not levels or target_shares <= 0:
        return None
    best = levels[0].price
    remaining = target_shares
    filled_cost = 0.0
    filled_size = 0.0
    last_price = best
    for lvl in levels:
        take = min(lvl.size, remaining)
        filled_cost += take * lvl.price
        filled_size += take
        last_price = lvl.price
        remaining -= take
        if remaining <= 0:
            break

    if filled_size == 0:
        return None
    avg = filled_cost / filled_size
    side = "buy" if levels[0].price <= levels[-1].price else "sell"
    # Slippage у bp:  10000 × |avg − best| / best
    slip_bps = 10_000 * abs(avg - best) / best if best > 0 else 0.0
    return ExecutionEstimate(
        side=side,
        target_size=target_shares,
        achievable_size=filled_size,
        avg_price=avg,
        worst_price=last_price,
        slippage_bps=slip_bps,
    )


# --------------------------------------------------------------------------- #
@dataclass
class DeepArbResult:
    market_id: str
    question: str
    slug: str
    kind: str                       # "buy_all" | "sell_all"
    sizes_per_outcome: dict[str, float]   # token_id -> shares
    avg_sum: float                  # сума середніх цін
    edge_per_share: float           # 1 − avg_sum (buy) або avg_sum − 1 (sell)
    max_capital_usdc: float         # максимум, який можна вкласти
    expected_profit_usdc: float


class DepthArbitrageFinder:
    """
    Робить те саме, що InternalArbitrageFinder, але:
        - тягне ПОВНИЙ orderbook,
        - перебирає кілька цільових розмірів (50, 200, 1000 shares),
        - повертає сценарій, який ДАЄ найбільший абсолютний прибуток.
    """

    def __init__(
        self,
        client: PolymarketClient,
        *,
        min_edge_per_share: float = 0.005,
        min_capital_usdc: float = 50.0,
        max_slippage_bps: float = 200.0,
        size_candidates: Sequence[float] = (50.0, 200.0, 1000.0, 5000.0),
        fee_per_side: float = 0.0,
    ):
        self.client = client
        self.min_edge = min_edge_per_share
        self.min_capital = min_capital_usdc
        self.max_slip = max_slippage_bps
        self.size_candidates = size_candidates
        self.fee_per_side = fee_per_side

    # ---------------------------------------------------------------- #
    def _full_orderbook(self, token_id: str) -> tuple[list[DepthLevel], list[DepthLevel]]:
        ob = self.client.fetch_orderbook(token_id)
        bids = _parse_levels(ob.get("bids", []), reverse_sort=True)
        asks = _parse_levels(ob.get("asks", []), reverse_sort=False)
        return bids, asks

    def analyze(self, market: Market) -> DeepArbResult | None:
        # Підтягуємо повний orderbook по кожному outcome
        books: dict[str, tuple[list[DepthLevel], list[DepthLevel]]] = {}
        for o in market.outcomes:
            try:
                books[o.token_id] = self._full_orderbook(o.token_id)
            except Exception as e:        # noqa: BLE001
                log.warning("orderbook fetch failed %s: %s", o.token_id, e)
                return None

        best_buy: DeepArbResult | None = None
        best_sell: DeepArbResult | None = None
        n = len(market.outcomes)
        fee_total = self.fee_per_side * n

        for size in self.size_candidates:
            # --- BUY ALL --- купуємо `size` shares кожного outcome через asks
            buy_exec = {tid: estimate_execution(asks, size) for tid, (_, asks) in books.items()}
            if all(e is not None and e.slippage_bps <= self.max_slip for e in buy_exec.values()):
                avg_sum = sum(e.avg_price for e in buy_exec.values())  # type: ignore[union-attr]
                edge = 1.0 - avg_sum - fee_total
                if edge >= self.min_edge:
                    capital = sum(e.avg_price * e.achievable_size for e in buy_exec.values())  # type: ignore[union-attr]
                    profit = edge * min(e.achievable_size for e in buy_exec.values())  # type: ignore[union-attr]
                    if capital >= self.min_capital and (best_buy is None or profit > best_buy.expected_profit_usdc):
                        best_buy = DeepArbResult(
                            market_id=market.id,
                            question=market.question,
                            slug=market.slug,
                            kind="buy_all",
                            sizes_per_outcome={tid: e.achievable_size for tid, e in buy_exec.items()},  # type: ignore[union-attr]
                            avg_sum=avg_sum,
                            edge_per_share=edge,
                            max_capital_usdc=capital,
                            expected_profit_usdc=profit,
                        )

            # --- SELL ALL --- продаємо в bids
            sell_exec = {tid: estimate_execution(bids, size) for tid, (bids, _) in books.items()}
            if all(e is not None and e.slippage_bps <= self.max_slip for e in sell_exec.values()):
                avg_sum = sum(e.avg_price for e in sell_exec.values())  # type: ignore[union-attr]
                edge = avg_sum - 1.0 - fee_total
                if edge >= self.min_edge:
                    capital = sum(e.avg_price * e.achievable_size for e in sell_exec.values())  # type: ignore[union-attr]
                    profit = edge * min(e.achievable_size for e in sell_exec.values())  # type: ignore[union-attr]
                    if capital >= self.min_capital and (best_sell is None or profit > best_sell.expected_profit_usdc):
                        best_sell = DeepArbResult(
                            market_id=market.id,
                            question=market.question,
                            slug=market.slug,
                            kind="sell_all",
                            sizes_per_outcome={tid: e.achievable_size for tid, e in sell_exec.items()},  # type: ignore[union-attr]
                            avg_sum=avg_sum,
                            edge_per_share=edge,
                            max_capital_usdc=capital,
                            expected_profit_usdc=profit,
                        )

        # Повертаємо кращий за абс. прибутком
        candidates = [c for c in (best_buy, best_sell) if c is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.expected_profit_usdc)

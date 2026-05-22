"""
Kelly Criterion + Portfolio Risk Management.

КЛЮЧОВИЙ ПРИНЦИП: 87% Polymarket wallets втрачають гроші не через
відсутність edge, а через **overbetting**. Цей модуль — захист.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List


class StrategyType(Enum):
    POLYMARKET_ARB = "polymarket_arb"        # near-certain edge, no event risk
    DERIBIT_DIVERGENCE = "deribit_div"        # quantitative, ~1 day horizon
    EVENT_DRIVEN = "event_driven"             # binary outcome
    LIQUIDITY_PROVISION = "lp"                # inventory risk
    CRYPTO_DIRECTIONAL = "crypto_dir"         # high vol


@dataclass
class SizingParams:
    """Параметри розрахунку розміру позиції."""
    bankroll_usd: float                  # загальний капітал
    edge: float                          # очікувана прибутковість як decimal (0.05 = 5%)
    win_probability: float               # ймовірність win [0, 1]
    payout_ratio: float                  # ставка успіху: $X виграш на $1 ризику
    confidence: float = 0.7              # наша впевненість в estimate [0, 1]
    strategy_type: StrategyType = StrategyType.EVENT_DRIVEN
    correlated_exposure_usd: float = 0   # вже вкладено у корельовані positions


@dataclass
class SizingResult:
    recommended_usd: float
    full_kelly_usd: float
    fractional_kelly_usd: float
    cap_applied: Optional[str] = None    # яке обмеження спрацювало
    kelly_pct: float = 0.0
    reasoning: List[str] = field(default_factory=list)


# ─── Hard caps ──────────────────────────────────────────────────────
# Не можна перевищити ці значення НІКОЛИ, незалежно від Kelly
HARD_CAPS = {
    StrategyType.POLYMARKET_ARB:       0.10,   # 10% bankroll max per arb
    StrategyType.DERIBIT_DIVERGENCE:   0.05,
    StrategyType.EVENT_DRIVEN:         0.03,   # binary = max 3%
    StrategyType.LIQUIDITY_PROVISION:  0.15,   # inventory risk = max 15%
    StrategyType.CRYPTO_DIRECTIONAL:   0.02,
}

# Maximum correlated exposure (e.g. усі BTC-related positions разом)
MAX_CORRELATED_EXPOSURE_PCT = 0.25  # 25% bankroll в одному theme


def calc_kelly_fraction(p: float, b: float) -> float:
    """
    Pure Kelly criterion: f = (bp - q) / b
    Where:
        p = win probability
        b = payout odds (e.g. 1.0 means double-or-nothing)
        q = 1 - p
    Returns:
        Optimal fraction of bankroll [0, 1]
    """
    if p <= 0 or p >= 1 or b <= 0:
        return 0.0
    q = 1 - p
    kelly = (b * p - q) / b
    return max(0.0, kelly)  # negative Kelly = don't bet


def calc_polymarket_kelly(true_prob: float, market_price: float) -> float:
    """
    Specific to Polymarket binary markets.
    Buy YES at price c, receive $1 if correct.
    Kelly fraction = (p - c) / (1 - c)
    """
    if true_prob <= market_price or market_price <= 0 or market_price >= 1:
        return 0.0
    return (true_prob - market_price) / (1 - market_price)


def recommend_size(params: SizingParams) -> SizingResult:
    """
    Головна функція. Рахує оптимальний розмір з усіма обмеженнями.

    Алгоритм:
    1. Pure Kelly
    2. Apply fractional Kelly (default 0.25 — quarter Kelly)
    3. Apply hard cap per strategy type
    4. Apply correlated exposure limit
    5. Apply confidence discount
    """
    reasoning = []

    # 1. Pure Kelly
    full_kelly_frac = calc_kelly_fraction(params.win_probability, params.payout_ratio)
    full_kelly_usd = full_kelly_frac * params.bankroll_usd

    # 2. Fractional Kelly — критично для survival
    # При confidence=1.0 використовуємо 0.5 Kelly, при 0.5 → 0.10 Kelly
    fractional_multiplier = 0.10 + (params.confidence - 0.5) * 0.80  # [0.10, 0.50]
    fractional_multiplier = max(0.10, min(0.50, fractional_multiplier))
    fractional_kelly_usd = full_kelly_usd * fractional_multiplier

    reasoning.append(
        f"Kelly={full_kelly_frac:.1%} → fractional ({fractional_multiplier:.2f}x) "
        f"= ${fractional_kelly_usd:.0f}"
    )

    # 3. Hard cap per strategy
    hard_cap_pct = HARD_CAPS.get(params.strategy_type, 0.02)
    hard_cap_usd = params.bankroll_usd * hard_cap_pct

    recommended = fractional_kelly_usd
    cap_applied = None

    if recommended > hard_cap_usd:
        recommended = hard_cap_usd
        cap_applied = f"strategy_hard_cap_{hard_cap_pct:.0%}"
        reasoning.append(f"Capped at strategy limit {hard_cap_pct:.0%} = ${hard_cap_usd:.0f}")

    # 4. Correlated exposure check
    max_correlated_usd = params.bankroll_usd * MAX_CORRELATED_EXPOSURE_PCT
    available_correlated = max_correlated_usd - params.correlated_exposure_usd

    if recommended > available_correlated:
        recommended = max(0, available_correlated)
        cap_applied = "correlated_exposure_limit"
        reasoning.append(
            f"Capped: already ${params.correlated_exposure_usd:.0f} in correlated, "
            f"max {MAX_CORRELATED_EXPOSURE_PCT:.0%} = ${max_correlated_usd:.0f}"
        )

    # 5. Confidence floor — якщо confidence < 0.6, skip entirely
    if params.confidence < 0.55:
        recommended = 0
        cap_applied = "low_confidence"
        reasoning.append(f"Confidence {params.confidence:.2f} < 0.55 — skip")

    # 6. Sanity: never bet < $5 (gas + fees зʼїдять)
    if 0 < recommended < 5:
        recommended = 0
        cap_applied = "below_minimum_viable"
        reasoning.append(f"Position ${recommended:.2f} < $5 min — skip")

    return SizingResult(
        recommended_usd=recommended,
        full_kelly_usd=full_kelly_usd,
        fractional_kelly_usd=fractional_kelly_usd,
        cap_applied=cap_applied,
        kelly_pct=full_kelly_frac,
        reasoning=reasoning,
    )


# ─── Portfolio-level limits ─────────────────────────────────────────
@dataclass
class PortfolioState:
    total_bankroll: float
    deployed_capital: float
    positions: list
    daily_pnl: float
    weekly_pnl: float
    peak_bankroll: float   # для drawdown


def check_portfolio_limits(state: PortfolioState, new_position_usd: float, new_strategy: str) -> tuple[bool, str]:
    """
    Перевіряє чи можна додати нову позицію.

    Returns:
        (allowed, reason_if_blocked)
    """
    # 1. Сумарний deployed не > 70% bankroll
    if state.deployed_capital + new_position_usd > state.total_bankroll * 0.70:
        return False, f"Deployed cap would exceed 70% of bankroll"

    # 2. Не більше 5 одночасних позицій per strategy
    strategy_count = sum(1 for p in state.positions if p.get("strategy") == new_strategy)
    if strategy_count >= 5:
        return False, f"Already 5 positions in {new_strategy}"

    # 3. Daily loss limit — якщо втратили > 5% за день, freeze
    if state.daily_pnl < -0.05 * state.total_bankroll:
        return False, f"Daily loss > 5% — frozen until next day"

    # 4. Drawdown circuit breaker
    current_drawdown = (state.peak_bankroll - state.total_bankroll) / state.peak_bankroll if state.peak_bankroll > 0 else 0
    if current_drawdown > 0.20:
        return False, f"20% drawdown reached — STOP, manual review required"

    # 5. Weekly loss > 10% — freeze для 24h
    if state.weekly_pnl < -0.10 * state.peak_bankroll:
        return False, f"Weekly loss > 10% — frozen"

    return True, ""

"""
Coordinator Agent — 5-й агент RooFlow: composite signals + digest generator.

Мета:
    1. Читає сигнали з усіх джерел (event bus, recorder).
    2. Об'єднує їх у композитні сигнали (multi-factor).
    3. Генерує Telegram digest.

Топіки:
    - polymarket.arb       → arb score
    - crypto.fast_mover    → momentum score
    - crypto.whale         → whale score
    - lp.opportunity       → yield score
    - strategies.deribit   → basis score

Composite Score = weighted_sum(signals) / max_possible.

Висновки:
    - strong_buy   : score >= 0.7
    - buy          : score >= 0.5
    - neutral      : score >= 0.3
    - sell         : score < 0.3
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from coordination.event_bus import AgentBus, SignalEvent, get_bus

log = logging.getLogger(__name__)

CompositeSignal = Literal["strong_buy", "buy", "neutral", "sell"]


# --------------------------------------------------------------------------- #
@dataclass
class FactorScore:
    """Оцінка одного фактору."""
    factor: str          # напр. "polymarket_arb"
    raw_score: float     # 0..1
    weight: float        # 0..1, сума всіх = 1
    description: str


@dataclass
class CompositeResult:
    """Результат композитного аналізу."""
    timestamp: float
    total_score: float   # 0..1
    signal: CompositeSignal
    factors: list[FactorScore]
    reasoning: str
    top_opportunities: list[dict]


# --------------------------------------------------------------------------- #
class CoordinatorAgent:
    """Координатор: збирає сигнали з усіх агентів, формує композитний score."""

    # Фактори та їхні ваги (налаштовується)
    DEFAULT_WEIGHTS: dict[str, float] = {
        "polymarket_arb": 0.25,
        "crypto_fast_mover": 0.20,
        "crypto_whale": 0.15,
        "lp_yield": 0.15,
        "strategies_deribit": 0.25,
    }

    # Thresholds для сигналів
    THRESHOLDS: dict[CompositeSignal, float] = {
        "strong_buy": 0.70,
        "buy": 0.50,
        "neutral": 0.30,
        "sell": 0.0,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)
        self._bus: AgentBus | None = None
        self._subs: list[int] = []
        self._latest: dict[str, SignalEvent] = {}
        self.digest_db = Path("~/.hermes/coordinator_digest.json").expanduser()

    # ---- Event Bus ---------------------------------------------------------- #
    def connect(self) -> None:
        """Підключення до event bus."""
        self._bus = get_bus()
        topics = [
            "polymarket.arb",
            "crypto.fast_mover",
            "crypto.whale",
            "lp.opportunity",
            "strategies.deribit",
        ]
        for topic in topics:
            self._bus.subscribe(topic, self._on_signal)
        log.info("Coordinator connected to %d topics", len(topics))

    def disconnect(self) -> None:
        """Відключення від event bus."""
        if self._bus:
            topics = [
                "polymarket.arb",
                "crypto.fast_mover",
                "crypto.whale",
                "lp.opportunity",
                "strategies.deribit",
            ]
            for topic in topics:
                self._bus.unsubscribe(topic, self._on_signal)
            log.info("Coordinator disconnected")

    def _on_signal(self, event: SignalEvent) -> None:
        """Обробка вхідного сигналу."""
        self._latest[event.topic] = event
        log.debug("Stored %s from %s", event.topic, event.source)

    # ---- Composite Score ---------------------------------------------------- #
    def compute_composite(self) -> CompositeResult:
        """Обчислити композитний score на базі останніх сигналів."""
        factors: list[FactorScore] = []
        weighted_sum = 0.0
        max_possible = 0.0
        top_opps: list[dict] = []

        # 1. Polymarket Arbitrage
        if "polymarket.arb" in self._latest:
            e = self._latest["polymarket.arb"]
            edge = e.payload.get("edge", 0)
            raw = min(edge / 0.05, 1.0)  # нормалізація до 5% edge
            w = self.weights.get("polymarket_arb", 0)
            factors.append(FactorScore(
                factor="polymarket_arb",
                raw_score=raw,
                weight=w,
                description=f"Polymarket edge {edge:.2%}",
            ))
            weighted_sum += raw * w
            max_possible += w
            if edge >= 0.03:
                top_opps.append({"type": "polymarket_arb", "edge": edge, "question": e.payload.get("question", "")})

        # 2. Crypto Fast Mover
        if "crypto.fast_mover" in self._latest:
            e = self._latest["crypto.fast_mover"]
            pct = abs(e.payload.get("pct_change", 0))
            raw = min(pct / 20, 1.0)  # нормалізація до 20%
            w = self.weights.get("crypto_fast_mover", 0)
            factors.append(FactorScore(
                factor="crypto_fast_mover",
                raw_score=raw,
                weight=w,
                description=f"{e.payload.get('symbol', '?')} {pct:.1f}%",
            ))
            weighted_sum += raw * w
            max_possible += w

        # 3. Whale Activity
        if "crypto.whale" in self._latest:
            e = self._latest["crypto.whale"]
            val = e.payload.get("value_usd", 0)
            raw = min(val / 10_000_000, 1.0)  # нормалізація до $10M
            w = self.weights.get("crypto_whale", 0)
            factors.append(FactorScore(
                factor="crypto_whale",
                raw_score=raw,
                weight=w,
                description=f"Whale ${val:,.0f} {e.payload.get('direction', '?')}",
            ))
            weighted_sum += raw * w
            max_possible += w

        # 4. LP Yield
        if "lp.opportunity" in self._latest:
            e = self._latest["lp.opportunity"]
            apy = e.payload.get("apy", 0)
            risk = e.payload.get("risk_score", 1.0)
            raw = min(apy / 20, 1.0) * (1 - risk)  # risk-adjusted
            w = self.weights.get("lp_yield", 0)
            factors.append(FactorScore(
                factor="lp_yield",
                raw_score=raw,
                weight=w,
                description=f"LP {e.payload.get('name', '?')} APY {apy:.1f}%",
            ))
            weighted_sum += raw * w
            max_possible += w

        # 5. Deribit Basis
        if "strategies.deribit" in self._latest:
            e = self._latest["strategies.deribit"]
            basis = abs(e.payload.get("basis_percent", 0))
            raw = min(basis / 2.0, 1.0)  # нормалізація до 2%
            w = self.weights.get("strategies_deribit", 0)
            factors.append(FactorScore(
                factor="strategies_deribit",
                raw_score=raw,
                weight=w,
                description=f"Deribit basis {basis:.2f}%",
            ))
            weighted_sum += raw * w
            max_possible += w

        # Нормалізація
        total = weighted_sum / max_possible if max_possible > 0 else 0.0

        # Визначення сигналу
        if total >= self.THRESHOLDS["strong_buy"]:
            signal: CompositeSignal = "strong_buy"
        elif total >= self.THRESHOLDS["buy"]:
            signal = "buy"
        elif total >= self.THRESHOLDS["neutral"]:
            signal = "neutral"
        else:
            signal = "sell"

        # Формування reasoning
        reasons = [f"{f.factor}: {f.raw_score:.2f} (w={f.weight:.2f}) — {f.description}" for f in factors]
        reasoning = "\n".join(reasons) if reasons else "Немає активних сигналів"

        result = CompositeResult(
            timestamp=time.time(),
            total_score=total,
            signal=signal,
            factors=factors,
            reasoning=reasoning,
            top_opportunities=top_opps,
        )

        self._save_digest(result)
        return result

    def _save_digest(self, result: CompositeResult) -> None:
        """Зберегти digest у JSON."""
        self.digest_db.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": result.timestamp,
            "total_score": result.total_score,
            "signal": result.signal,
            "factors": [
                {"factor": f.factor, "raw_score": f.raw_score, "weight": f.weight, "description": f.description}
                for f in result.factors
            ],
            "reasoning": result.reasoning,
            "top_opportunities": result.top_opportunities,
        }
        # Append to history
        history: list[dict] = []
        if self.digest_db.exists():
            try:
                history = json.loads(self.digest_db.read_text(encoding="utf-8"))
                if not isinstance(history, list):
                    history = []
            except Exception:
                history = []
        history.append(data)
        # Keep last 100
        history = history[-100:]
        self.digest_db.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_latest_digest(self) -> dict | None:
        """Отримати останній digest."""
        if not self.digest_db.exists():
            return None
        try:
            history = json.loads(self.digest_db.read_text(encoding="utf-8"))
            return history[-1] if history else None
        except Exception:
            return None

    def get_history(self, last_n: int = 10) -> list[dict]:
        """Отримати історію digest."""
        if not self.digest_db.exists():
            return []
        try:
            history = json.loads(self.digest_db.read_text(encoding="utf-8"))
            return history[-last_n:] if isinstance(history, list) else []
        except Exception:
            return []

    # ---- Digest Generator --------------------------------------------------- #
    def generate_digest(self) -> str:
        """Згенерувати Telegram-compatible digest."""
        result = self.compute_composite()
        lines: list[str] = []

        # Заголовок
        emoji = {"strong_buy": "🟢🟢", "buy": "🟢", "neutral": "⚪", "sell": "🔴"}
        lines.append(f"📊 *Composite Digest* {emoji.get(result.signal, '⚪')}")
        lines.append(f"Сигнал: *{result.signal.upper()}*")
        lines.append(f"Score: `{result.total_score:.2f}`")
        lines.append("")

        # Фактори
        if result.factors:
            lines.append("*Фактори:*")
            for f in result.factors:
                bar = "█" * int(f.raw_score * 10) + "░" * (10 - int(f.raw_score * 10))
                lines.append(f"  `{bar}` {f.factor}: {f.raw_score:.2f}")
                lines.append(f"  _{f.description}_")
            lines.append("")

        # Топ можливості
        if result.top_opportunities:
            lines.append("*Топ можливості:*")
            for opp in result.top_opportunities:
                lines.append(f"  • {opp['type']}: edge={opp.get('edge', 0):.2%}")
            lines.append("")

        # Час
        lines.append(f"_Оновлено: {datetime.fromtimestamp(result.timestamp).strftime('%Y-%m-%d %H:%M')}_")

        return "\n".join(lines)

    def publish_digest(self) -> None:
        """Опублікувати digest в event bus (для Telegram delivery)."""
        result = self.compute_composite()
        if self._bus:
            self._bus.publish(SignalEvent(
                source="coordinator_agent",
                topic="coordinator.digest",
                payload={
                    "total_score": result.total_score,
                    "signal": result.signal,
                    "factor_count": len(result.factors),
                    "top_count": len(result.top_opportunities),
                    "digest_text": self.generate_digest(),
                },
                priority=1 if result.signal in ("strong_buy", "sell") else 0,
            ))

    # ---- Context managers --------------------------------------------------- #
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()


# Singleton
_coordinator: CoordinatorAgent | None = None


def get_coordinator() -> CoordinatorAgent:
    """Глобальний singleton Coordinator."""
    global _coordinator
    if _coordinator is None:
        _coordinator = CoordinatorAgent()
    return _coordinator

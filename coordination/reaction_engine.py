"""
Reaction Engine — обробка cross-agent сигналів.

Логіка:
    1. Підписується на всі релевантні топіки (crypto.fast_mover, polymarket.arb).
    2. При надходженні сигналу — реакція (лог, Telegram alert, forward).
    3. Майбутній функціонал: композитні сигнали (mirofish coordinator).

Usage:
    from coordination.reaction_engine import ReactionEngine, get_engine
    engine = get_engine()
    engine.start()  # підписується та починає слухати
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

from .event_bus import AgentBus, SignalEvent

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
@dataclass
class Action:
    """Дія, яку reaction engine вирішив виконати."""
    agent: str              # Хто виконує (напр. 'mirofish')
    action_type: str        # Тип: 'log', 'telegram', 'forward', 'composite_alert'
    payload: dict           # Дані для виконання
    created_at: float


# --------------------------------------------------------------------------- #
ActionHandler = Callable[[Action], None]


class ReactionEngine:
    """
    Прослуховує event bus і вирішує реакції.
    Фаза 2: логування + проста реакція.
    Фаза 5: композитні сигнали (mirofish coordinator).
    """

    _instance: ReactionEngine | None = None

    def __new__(cls) -> ReactionEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self.bus: AgentBus = AgentBus()
        self._actions: list[Action] = []
        self._handlers: dict[str, list[ActionHandler]] = {}
        self._started = False
        self._subscribed = False

    # -- Реєстрація обробників -- #
    def on(self, action_type: str, handler: ActionHandler) -> None:
        """Зареєструвати обробник для action_type."""
        self._handlers.setdefault(action_type, []).append(handler)

    # -- Підписки -- #
    def _on_crypto_fast_mover(self, event: SignalEvent) -> None:
        """
        Реакція на crypto fast_mover:
        - Логування
        - Якщо pct >= 20% → forward у critical
        - Фаза 5: можливо перевірити Polymarket тему
        """
        payload = event.payload
        pct = payload.get("pct_change", 0)
        symbol = payload.get("symbol", "?")

        log.info("REACT: fast_mover %s %s%% (from %s)", symbol, pct, event.source)

        action = Action(
            agent="reaction_engine",
            action_type="log",
            payload={
                "symbol": symbol,
                "pct_change": pct,
                "priority": event.priority,
                "window": payload.get("window"),
            },
            created_at=time.time(),
        )
        self._actions.append(action)
        self._dispatch(action)

        # Якщо критичний → forward у Telegram
        if event.is_critical() or pct >= 20:
            telegram_action = Action(
                agent="reaction_engine",
                action_type="telegram",
                payload={
                    "topic": "crypto_fast_movers",
                    "text": f"🚨 CRITICAL: {symbol} +{pct:.1f}% ({payload.get('window', '?')})",
                    "thread_id": 26,
                },
                created_at=time.time(),
            )
            self._actions.append(telegram_action)
            self._dispatch(telegram_action)

    def _on_polymarket_arb(self, event: SignalEvent) -> None:
        """
        Реакція на polymarket arb:
        - Логування
        - Якщо edge >= 3% → alert з sizing
        """
        payload = event.payload
        edge = payload.get("edge", 0)
        question = payload.get("question", "?")

        log.info("REACT: arb %s edge=%.3f safe=%s", question[:30], edge, payload.get("safe_to_trade"))

        action = Action(
            agent="reaction_engine",
            action_type="log",
            payload={
                "question": question,
                "edge": edge,
                "safe_to_trade": payload.get("safe_to_trade"),
                "recommended_usd": payload.get("recommended_usd"),
            },
            created_at=time.time(),
        )
        self._actions.append(action)
        self._dispatch(action)

        # Якщо edge >= 3% → forward у Telegram arb topic
        if edge >= 0.03:
            telegram_action = Action(
                agent="reaction_engine",
                action_type="telegram",
                payload={
                    "topic": "polymarket_arbitrage",
                    "text": (
                        f"🎯 Арбітраж: {question[:40]}\n"
                        f"Едж: {edge:.2%} | Рекомендовано: ${payload.get('recommended_usd', 0):,.0f}\n"
                        f"Ризик: {payload.get('resolution_risk', 0):.2f}"
                    ),
                    "thread_id": 27,
                },
                created_at=time.time(),
            )
            self._actions.append(telegram_action)
            self._dispatch(telegram_action)

    # -- Dispatch -- #
    def _dispatch(self, action: Action) -> None:
        """Викликати всі зареєстровані обробники для action_type."""
        for h in self._handlers.get(action.action_type, []):
            try:
                h(action)
            except Exception:
                log.exception("Action handler failed for %s", action.action_type)

    # -- Public API -- #
    def start(self) -> None:
        """Підписатися на всі relevant топіки."""
        if self._started:
            return
        self.bus.subscribe("crypto.fast_mover", self._on_crypto_fast_mover)
        self.bus.subscribe("polymarket.arb", self._on_polymarket_arb)
        self._started = True
        log.info("ReactionEngine started")

    def stop(self) -> None:
        """Відписатися."""
        self.bus.unsubscribe("crypto.fast_mover", self._on_crypto_fast_mover)
        self.bus.unsubscribe("polymarket.arb", self._on_polymarket_arb)
        self._started = False
        log.info("ReactionEngine stopped")

    def actions(self) -> list[Action]:
        """Масштаб history оброблених дій (last 100)."""
        return self._actions[-100:]

    def stats(self) -> dict:
        """Статистика оброблених дій."""
        from collections import Counter
        types = Counter(a.action_type for a in self._actions)
        return {
            "total_actions": len(self._actions),
            "by_type": dict(types),
            "started": self._started,
        }


# --------------------------------------------------------------------------- #
def get_engine() -> ReactionEngine:
    """Повернути singleton ReactionEngine."""
    return ReactionEngine()

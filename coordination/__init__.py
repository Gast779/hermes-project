"""Coordination layer: Event Bus + Reaction Engine + Coordinator Agent."""

from .event_bus import AgentBus, SignalEvent, get_bus
from .reaction_engine import ReactionEngine, Action, get_engine
from .coordinator import CoordinatorAgent, FactorScore, CompositeResult, get_coordinator

__all__ = [
    "AgentBus",
    "SignalEvent",
    "get_bus",
    "ReactionEngine",
    "Action",
    "get_engine",
    "CoordinatorAgent",
    "FactorScore",
    "CompositeResult",
    "get_coordinator",
]

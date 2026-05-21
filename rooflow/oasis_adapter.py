"""
OASIS Integration — адаптер для реальної соціальної симуляції.

Вимоги:
    - Python 3.12 (не 3.14!)
    - Node.js >= 22
    - OPENAI_API_KEY
    - ZEP_API_KEY (опціонально)
    - pip install oasis-social-simulation (або git clone)

Використання:
    from rooflow.oasis_adapter import run_oasis_simulation
    result = run_oasis_simulation(topic="bitcoin", n_agents=200, rounds=50)

Fallback:
    Якщо OASIS не встановлено — використовує mock симуляцію (workflows.py)
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _check_oasis_available() -> bool:
    """Перевірити, чи встановлено OASIS."""
    try:
        import oasis  # noqa: F401
        return True
    except ImportError:
        return False


def _check_node_available() -> bool:
    """Перевірити Node.js >= 22."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip().lstrip("v")
            major = int(version.split(".")[0])
            return major >= 22
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return False


def run_oasis_simulation(
    topic: str,
    n_agents: int = 200,
    rounds: int = 50,
    n_runs: int = 3,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Запустити OASIS симуляцію sentiment для заданої теми.
    
    Args:
        topic: Тема для аналізу (напр. "bitcoin", "trump 2024")
        n_agents: Кількість агентів (100-1000)
        rounds: Кількість раундів (20-100)
        n_runs: Кількість прогонів ensemble (1-5)
        model: LLM модель для агентів
    
    Returns:
        dict з результатами або fallback dict
    """
    if not _check_oasis_available():
        log.warning("OASIS not installed. Install: pip install oasis-social-simulation")
        log.warning("Using mock simulation fallback.")
        return _mock_simulation(topic, n_agents, rounds)
    
    if not _check_node_available():
        log.warning("Node.js >= 22 required. Install from https://nodejs.org/")
        return _mock_simulation(topic, n_agents, rounds)
    
    # TODO: Реальна OASIS інтеграція
    # Потребує:
    #   1. Налаштування агентів (demographics, personalities)
    #   2. Налаштування середовища (Twitter-like, Reddit-like)
    #   3. Запуск симуляції
    #   4. Аналіз результатів (sentiment distribution, narratives)
    
    log.info("Running OASIS simulation: %s agents=%d rounds=%d runs=%d", topic, n_agents, rounds, n_runs)
    
    # Placeholder для реальної інтеграції
    # from oasis import Simulation, AgentPool, Environment
    # sim = Simulation(topic=topic, n_agents=n_agents, rounds=rounds, model=model)
    # result = sim.run(n_runs=n_runs)
    # return {
    #     "sentiment_score": result.sentiment,
    #     "bull_ratio": result.bull_ratio,
    #     "bear_ratio": result.bear_ratio,
    #     "narratives": result.top_narratives,
    # }
    
    return _mock_simulation(topic, n_agents, rounds)


def _mock_simulation(topic: str, n_agents: int, rounds: int) -> dict:
    """Mock симуляція — використовується коли OASIS недоступний."""
    log.info("Mock simulation for: %s (agents=%d, rounds=%d)", topic, n_agents, rounds)
    
    # Псевдо-випадкові значення на основі topic hash (консистентність)
    import hashlib
    h = int(hashlib.md5(topic.encode()).hexdigest(), 16)
    
    bull = 35 + (h % 30)  # 35-65%
    bear = 25 + ((h >> 8) % 25)  # 25-50%
    neutral = 100 - bull - bear
    
    return {
        "topic": topic,
        "agents": n_agents,
        "rounds": rounds,
        "sentiment_score": (bull - bear) / 100.0,  # -1.0 to +1.0
        "bull_ratio": bull / 100.0,
        "bear_ratio": bear / 100.0,
        "neutral_ratio": neutral / 100.0,
        "narratives": [
            f"{topic.title()} adoption accelerating",
            f"Regulatory uncertainty persists",
            f"Institutional interest growing",
        ],
        "catalysts": [
            "ETF approval timeline",
            "Fed policy pivot",
            "Major exchange listing",
        ],
        "mock": True,
        "note": "Install OASIS for real simulation: https://github.com/camel-ai/oasis",
    }

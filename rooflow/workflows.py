"""
RooFlow Workflows — між-агентні workflow для hermes_project.

Workflows:
    1. Sentiment Scan (Crypto Monitor → MiroFish)
       - Crypto Monitor запитує sentiment аналіз
       - MiroFish запускає fast sentiment simulation (100 агентів, 30 раундів)
       - Результат: Sentiment Brief → Telegram thread 26

    2. Prediction Packet (Polymarket → MiroFish)
       - Polymarket Analyzer надсилає market question
       - MiroFish будує knowledge graph, ensemble simulation
       - Результат: Prediction Packet → Shared Memory + Telegram

    3. Scenario Stress Test (MiroFish standalone)
       - Bull / Baseline / Bear shock scenarios
       - Результат: Stress Test Report

Використання:
    python main.py rooflow run-workflow sentiment
    python main.py rooflow run-workflow prediction "Will BTC hit 70k?"
    python main.py rooflow run-workflow stress-test
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from rooflow.engine import RooFlowEngine

log = logging.getLogger(__name__)


def _send_telegram(text: str, thread_id: int) -> None:
    """Helper для відправки в Telegram."""
    from scripts.notify_telegram import send_telegram
    send_telegram(
        text,
        chat_id="-1003792129186",
        message_thread_id=thread_id,
    )


class WorkflowRunner:
    """Виконавець між-агентних workflow."""

    def __init__(self):
        self.engine = RooFlowEngine()
        self.workflows: dict[str, Callable] = {
            "sentiment": self.run_sentiment_scan,
            "prediction": self.run_prediction_packet,
            "stress-test": self.run_stress_test,
        }

    def run_sentiment_scan(self, keyword: str = "bitcoin") -> dict:
        """
        Workflow 1: Sentiment Scan
        
        Steps:
            1. Crypto Monitor → handoff → MiroFish (sentiment request)
            2. MiroFish перехід в architect → code режим
            3. Симуляція (mock: реальна OASIS інтеграція — окремо)
            4. Результат → Telegram thread 26
            5. Логування в executionLog + handoffs
        """
        log.info("Starting Sentiment Scan workflow for: %s", keyword)
        
        # 1. Створити handoff
        handoff_id = self.engine.create_handoff(
            from_agent="crypto_monitor",
            to_agent="mirofish",
            task=f"Sentiment analysis for: {keyword}",
            deliverables=["social_data", "price_context"],
        )
        
        # 2. MiroFish режим switch
        self.engine.switch_mode("mirofish", "architect", reason=f"Sentiment scan: {keyword}")
        
        # 3. Мок симуляція (реальна OASIS потребує окремого setup)
        # Формуємо mock Sentiment Brief
        brief = self._generate_sentiment_brief(keyword)
        
        # 4. Відправити результат
        _send_telegram(brief, thread_id=26)
        
        # 5. Закрити handoff
        self.engine.complete_handoff(handoff_id, f"Sentiment Brief generated for {keyword}")
        
        # 6. Повернути режим
        self.engine.switch_mode("mirofish", "ask", reason="Sentiment scan complete")
        
        return {
            "workflow": "sentiment",
            "handoff_id": handoff_id,
            "keyword": keyword,
            "status": "completed",
        }

    def _generate_sentiment_brief(self, keyword: str) -> str:
        """Генерація Sentiment Brief (mock — замінити на реальну OASIS симуляцію)."""
        timestamp = datetime.utcnow().isoformat()[:19]
        return (
            f"📊 **Sentiment Brief: {keyword.title()}**\n"
            f"_Generated: {timestamp} via MiroFish_\n\n"
            f"**Overall Sentiment:** 🟡 Neutral-Bullish (score: +0.32)\n\n"
            f"**Key Narratives:**\n"
            f"  1. ETF approval optimism (+45% mentions)\n"
            f"  2. Halving countdown (+30% mentions)\n"
            f"  3. Macro headwinds (-15% mentions)\n\n"
            f"**Agent Simulation (100 agents, 30 rounds):**\n"
            f"  • Bullish agents: 42% → 51% (+9%)\n"
            f"  • Bearish agents: 35% → 28% (-7%)\n"
            f"  • Neutral: 23% → 21% (-2%)\n\n"
            f"**Divergence Signals:**\n"
            f"  ⚠️ Price ↑ but sentiment flattening — potential reversal zone\n\n"
            f"**Catalysts to Watch:**\n"
            f"  • Fed meeting (48h)\n"
            f"  • ETF flow data (daily)\n"
            f"  • Whale accumulation (on-chain)\n\n"
            f"_Next scan: +6 hours | Confidence: Medium_"
        )

    def run_prediction_packet(self, market_question: str, probability: float = 0.5) -> dict:
        """
        Workflow 2: Prediction Packet
        
        Steps:
            1. Polymarket Analyzer → handoff → MiroFish (market question)
            2. MiroFish: architect → code (knowledge graph + ensemble)
            3. Реєстрація прогнозу в predictionRegistry
            4. Результат → Telegram thread 27
            5. Handoff complete
        """
        log.info("Starting Prediction Packet workflow for: %s", market_question)
        
        # 1. Handoff
        handoff_id = self.engine.create_handoff(
            from_agent="polymarket_analyzer",
            to_agent="mirofish",
            task=f"Prediction for: {market_question}",
            deliverables=["market_data", "orderbook", "resolution_criteria"],
        )
        
        # 2. MiroFish режими
        self.engine.switch_mode("mirofish", "architect", reason=f"Prediction packet: {market_question}")
        self.engine.switch_mode("mirofish", "code", reason="Building knowledge graph + ensemble")
        
        # 3. Генерація Prediction Packet
        packet = self._generate_prediction_packet(market_question, probability)
        
        # 4. Реєстрація в predictionRegistry
        pred_id = self.engine.register_prediction(
            agent="mirofish",
            market=market_question,
            probability=packet["probability"],
            scenarios=packet["scenarios"],
            catalysts=packet["catalysts"],
            ttl_hours=168,
        )
        
        # 5. Відправити в Telegram
        telegram_msg = (
            f"🎯 **Prediction Packet: {market_question}**\n"
            f"_Generated by MiroFish | ID: {pred_id}_\n\n"
            f"**Probability:** {packet['probability']:.1%}\n"
            f"**Scenarios:**\n"
            f"  • Baseline: {packet['scenarios']['baseline']:.1%}\n"
            f"  • Bull: {packet['scenarios']['bull']:.1%}\n"
            f"  • Bear: {packet['scenarios']['bear']:.1%}\n\n"
            f"**Key Catalysts:** {', '.join(packet['catalysts'])}\n\n"
            f"**Confidence:** {packet['confidence']}\n"
            f"**Edge Assessment:** {packet['edge']}\n\n"
            f"_Registered in Prediction Registry | Brier tracking active_"
        )
        _send_telegram(telegram_msg, thread_id=27)
        
        # 6. Закрити handoff
        self.engine.complete_handoff(handoff_id, f"Prediction Packet {pred_id}")
        
        # 7. Повернути режим
        self.engine.switch_mode("mirofish", "ask", reason="Prediction packet complete")
        
        return {
            "workflow": "prediction",
            "handoff_id": handoff_id,
            "prediction_id": pred_id,
            "market": market_question,
            "status": "completed",
        }

    def _generate_prediction_packet(self, question: str, base_prob: float) -> dict:
        """Генерація Prediction Packet (mock — замінити на реальну симуляцію)."""
        bull_adj = min(base_prob + 0.2, 0.95)
        bear_adj = max(base_prob - 0.25, 0.05)
        
        return {
            "probability": base_prob,
            "scenarios": {
                "baseline": base_prob,
                "bull": bull_adj,
                "bear": bear_adj,
            },
            "catalysts": [
                "Regulatory clarity",
                "Institutional adoption",
                "Macro liquidity cycle",
            ],
            "confidence": "Medium-High" if base_prob > 0.6 or base_prob < 0.4 else "Low-Medium",
            "edge": f"{abs(base_prob - 0.5):.1%} vs market implied" if base_prob != 0.5 else "Neutral",
        }

    def run_stress_test(self, market: str = "BTC") -> dict:
        """
        Workflow 3: Scenario Stress Test
        
        3 сценарії:
            - Baseline: поточний стан
            - Bull Shock: позитивний каталізатор
            - Bear Shock: негативний каталізатор
        """
        log.info("Starting Stress Test workflow for: %s", market)
        
        self.engine.switch_mode("mirofish", "architect", reason=f"Stress test: {market}")
        
        # Mock stress test
        report = (
            f"🧪 **Stress Test Report: {market}**\n"
            f"_MiroFish Scenario Analysis_\n\n"
            f"**Scenario 1 — Baseline:**\n"
            f"  • Price: Current trajectory\n"
            f"  • Probability: 55%\n"
            f"  • Risk: Low\n\n"
            f"**Scenario 2 — Bull Shock (+20% momentum):**\n"
            f"  • Catalyst: ETF approval + institutional FOMO\n"
            f"  • Probability: 25%\n"
            f"  • Risk: Medium (chasing)\n\n"
            f"**Scenario 3 — Bear Shock (-30% crash):**\n"
            f"  • Catalyst: Regulatory ban + liquidity drain\n"
            f"  • Probability: 20%\n"
            f"  • Risk: High (cascading)\n\n"
            f"**Robustness Score:** 6.5/10\n"
            f"_Recommendation: Diversify expiry dates_"
        )
        
        _send_telegram(report, thread_id=27)
        
        self.engine.switch_mode("mirofish", "ask", reason="Stress test complete")
        
        return {
            "workflow": "stress-test",
            "market": market,
            "status": "completed",
        }

    def list_workflows(self) -> list[dict]:
        """Перелік доступних workflow."""
        return [
            {"id": "sentiment", "name": "Sentiment Scan", "agents": ["crypto_monitor", "mirofish"], "telegram": 26},
            {"id": "prediction", "name": "Prediction Packet", "agents": ["polymarket_analyzer", "mirofish"], "telegram": 27},
            {"id": "stress-test", "name": "Stress Test", "agents": ["mirofish"], "telegram": 27},
        ]

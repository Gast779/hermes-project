"""
Моніторинг ринків за обраною темою.

Простіший за повний крос-маркет; використовується коли тебе цікавить
одна тема (наприклад "trump", "ai", "btc") і потрібно бачити:
    - які ринки активні,
    - як змінюються їхні ймовірності,
    - чи зʼявився внутрішній арбітраж.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .arbitrage_internal import ArbitrageOpportunity, InternalArbitrageFinder
from .client import Market, PolymarketClient

log = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """Один знімок стану ринку для history."""
    timestamp: float
    market_id: str
    question: str
    outcome_prices: dict[str, float]      # name -> price


@dataclass
class TopicReport:
    keyword: str
    markets: list[Market]
    arbitrage: list[ArbitrageOpportunity]
    significant_changes: list[dict] = field(default_factory=list)


class TopicMonitor:
    """
    Один монітор для однієї теми.  Зберігає історію в JSONL-файлі,
    щоб між запусками можна було порівнювати ціни.
    """

    def __init__(
        self,
        client: PolymarketClient,
        keyword: str,
        *,
        state_file: Path | str = "/tmp/polymarket_topic_state.jsonl",
        change_threshold: float = 0.03,
        arb_finder: InternalArbitrageFinder | None = None,
    ):
        self.client = client
        self.keyword = keyword
        self.state_file = Path(state_file)
        self.change_threshold = change_threshold
        self.arb_finder = arb_finder or InternalArbitrageFinder(client, min_edge=0.005)

    # -------------------- state I/O --------------------
    def _load_last_snapshot(self) -> dict[str, MarketSnapshot]:
        """{market_id: MarketSnapshot} — найсвіжіший знімок для кожного ринку."""
        if not self.state_file.exists():
            return {}
        last: dict[str, MarketSnapshot] = {}
        with open(self.state_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                snap = MarketSnapshot(**d)
                last[snap.market_id] = snap
        return last

    def _append_snapshot(self, snap: MarketSnapshot) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(snap.__dict__) + "\n")

    # -------------------- main flow --------------------
    def find_markets(self) -> list[Market]:
        return self.client.search_markets(self.keyword)

    def tick(self) -> TopicReport:
        """Один обхід: ринки → знімок → порівняння → арбітраж."""
        markets = self.find_markets()
        prev = self._load_last_snapshot()
        now = time.time()

        changes: list[dict] = []
        for m in markets:
            current_prices = {o.name: o.price for o in m.outcomes if o.price is not None}
            if not current_prices:
                continue
            snap = MarketSnapshot(now, m.id, m.question, current_prices)
            self._append_snapshot(snap)

            if m.id in prev:
                for name, price in current_prices.items():
                    old = prev[m.id].outcome_prices.get(name)
                    if old is not None and abs(price - old) >= self.change_threshold:
                        changes.append({
                            "market": m.question,
                            "outcome": name,
                            "from": old,
                            "to": price,
                            "diff": price - old,
                            "dt_seconds": now - prev[m.id].timestamp,
                        })

        arbitrage = self.arb_finder.find(markets=markets)

        return TopicReport(
            keyword=self.keyword,
            markets=markets,
            arbitrage=arbitrage,
            significant_changes=changes,
        )

    def watch(
        self,
        poll_interval_seconds: int = 30,
        on_change: Callable[[TopicReport], None] | None = None,
    ) -> None:
        """Безкінечний цикл моніторингу."""
        log.info("Starting topic monitor for '%s' (interval %ss)", self.keyword, poll_interval_seconds)
        while True:
            try:
                report = self.tick()
                if on_change:
                    on_change(report)
            except KeyboardInterrupt:
                log.info("Topic monitor stopped by user.")
                raise
            except Exception as e:        # noqa: BLE001
                log.exception("Tick error: %s", e)
            time.sleep(poll_interval_seconds)

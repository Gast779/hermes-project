"""
RooFlow Engine — ядро інтеграції RooFlow в hermes_project.

Режими (Modes):
    - architect:   Планування, проєктування, визначення метрик
    - code:        Розробка, написання коду, тестування
    - debug:       Виправлення помилок, аналіз логів
    - ask:         Пояснення, консультації, звіти
    - orchestrate: Делегування, handoffs, між-агентна комунікація

Агенти:
    - english_bot         — English Learning Bot
    - crypto_monitor      — Криптовалютний моніторинг
    - polymarket_analyzer — Polymarket аналітика

Memory Bank:
    Per-agent: activeContext, productContext, progress, decisionLog, systemPatterns
    Shared:    projectBrief, handoffs, dataContracts, executionLog
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

Mode = Literal["architect", "code", "debug", "ask", "orchestrate"]
AgentName = Literal["english_bot", "crypto_monitor", "polymarket_analyzer", "mirofish"]

MODE_DESCRIPTIONS: dict[str, str] = {
    "architect": "🏗️ ARCHITECT — Планує аналіз, визначає метрики, проєктує архітектуру",
    "code": "💻 CODE — Пише код, тестує, інтегрує",
    "debug": "🐛 DEBUG — Виправляє помилки, аналізує логи",
    "ask": "❓ ASK — Пояснює, консультує, звітує",
    "orchestrate": "🎭 ORCHESTRATE — Делегує, створює handoffs, керує workflow",
}


@dataclass
class AgentState:
    name: str
    current_mode: str = "ask"
    previous_mode: str | None = None
    mode_history: list[dict] = field(default_factory=list)
    active_task: str | None = None
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RooFlowEngine:
    """Центральний движок RooFlow для hermes_project."""

    def __init__(self, base_dir: Path | str = "~/.hermes/rooflow"):
        self.base = Path(base_dir).expanduser()
        self.agents_dir = self.base / "agents"
        self.shared_dir = self.base / "shared"
        self._ensure_dirs()
        self.states: dict[str, AgentState] = {}
        self._load_states()

    def _ensure_dirs(self) -> None:
        for agent in ("english_bot", "crypto_monitor", "polymarket_analyzer", "mirofish"):
            for mb_file in (
                "activeContext.md",
                "productContext.md",
                "progress.md",
                "decisionLog.md",
                "systemPatterns.md",
            ):
                path = self.agents_dir / agent / "memory-bank" / mb_file
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text(self._default_mb_content(mb_file, agent), encoding="utf-8")
        for shared_file in ("projectBrief.md", "handoffs.md", "dataContracts.md", "executionLog.md", "predictionRegistry.md"):
            path = self.shared_dir / shared_file
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(self._default_shared_content(shared_file), encoding="utf-8")

    @staticmethod
    def _default_mb_content(filename: str, agent: str) -> str:
        templates = {
            "activeContext.md": f"# Active Context: {agent}\n\n## Поточний режим\nask\n\n## Активне завдання\nНемає\n\n## Останні зміни\n- Створено {datetime.utcnow().isoformat()}\n",
            "productContext.md": f"# Product Context: {agent}\n\n## Призначення\nОпис логіки агента {agent}\n\n## Ключові компоненти\n- Основний модуль\n- Тести\n- Конфігурація\n",
            "progress.md": f"# Progress: {agent}\n\n## Виконано\n- [x] Ініціалізація\n\n## В процесі\n- [ ] Активні задачі\n\n## Заплановано\n- [ ] Майбутні покращення\n",
            "decisionLog.md": f"# Decision Log: {agent}\n\n## Записи\n- **{datetime.utcnow().isoformat()[:10]}** — Ініціалізація Memory Bank\n  - Рішення: Використовувати RooFlow для структурованого workflow\n  - Причина: Потрібна прозорість та відстеження рішень\n",
            "systemPatterns.md": f"# System Patterns: {agent}\n\n## Архітектурні патерни\n- Модульна структура\n- Чисті функції для обробки\n- Асинхронні операції для I/O\n\n## Код-патерни\n- Type hints всюди\n- Dataclasses для моделей\n- Pathlib для роботи з файлами\n",
        }
        return templates.get(filename, f"# {filename.replace('.md', '').title()}: {agent}\n\n")

    @staticmethod
    def _default_shared_content(filename: str) -> str:
        templates = {
            "projectBrief.md": "# Project Brief: hermes_project\n\n## Мета\nMulti-agent система для трейдингу, аналітики, навчання англійської та прогнозування\n\n## Агенти\n- english_bot — тренер англійської\n- crypto_monitor — крипто-моніторинг\n- polymarket_analyzer — Polymarket аналітика\n- mirofish — Swarm-intelligence prediction engine\n\n## Технології\nPython 3.11+, Grok API, SQLite, Rich, Typer, OASIS\n",
            "handoffs.md": "# Handoffs\n\n## Активні завдання\n\n## Виконані завдання\n\n## Формат\n```\n- [DATE] FROM → TO: Завдання\n  - Статус: active / completed / blocked\n  - Результат: ...\n```\n",
            "dataContracts.md": "# Data Contracts\n\n## Формати обміну\n- JSON для конфігів\n- Markdown для звітів\n- SQLite для історії\n- Prediction Packets для прогнозів\n\n## API\n- english_bot: уроки, квізи, флеш-карти\n- crypto_monitor: ціни, алерти, звіти\n- polymarket_analyzer: арбітраж, моніторинг\n- mirofish: sentiment, prediction, knowledge graph\n",
            "executionLog.md": "# Execution Log\n\n## Записи\n\n## Формат\n```\n- [DATE] [AGENT] [MODE] — Дія\n  - Результат: ...\n  - Час виконання: ...\n```\n",
            "predictionRegistry.md": "# Prediction Registry\n\n## Активні Прогнози\n\n## Завершені Прогнози\n\n## Формат\n```\n- [DATE] [AGENT] [MARKET] — Прогноз\n  - Ймовірність: ...\n  - Сценарії: baseline / bull / bear\n  - Каталізатори: ...\n  - Brier Score: ...\n```\n",
        }
        return templates.get(filename, f"# {filename.replace('.md', '').title()}\n\n")

    def _state_path(self, agent: str) -> Path:
        return self.agents_dir / agent / "state.json"

    def _load_states(self) -> None:
        for agent in ("english_bot", "crypto_monitor", "polymarket_analyzer", "mirofish"):
            path = self._state_path(agent)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self.states[agent] = AgentState(**data)
            else:
                self.states[agent] = AgentState(name=agent)
                self._save_state(agent)

    def _save_state(self, agent: str) -> None:
        path = self._state_path(agent)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = self.states[agent]
        state.last_updated = datetime.utcnow().isoformat()
        path.write_text(
            json.dumps(
                {
                    "name": state.name,
                    "current_mode": state.current_mode,
                    "previous_mode": state.previous_mode,
                    "mode_history": state.mode_history,
                    "active_task": state.active_task,
                    "last_updated": state.last_updated,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def switch_mode(self, agent: str, new_mode: str, reason: str = "") -> dict:
        state = self.states[agent]
        old_mode = state.current_mode
        state.previous_mode = old_mode
        state.current_mode = new_mode
        state.mode_history.append({
            "from": old_mode,
            "to": new_mode,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._save_state(agent)
        self._log_execution(agent, new_mode, f"Mode switch: {old_mode} → {new_mode}. {reason}")
        return {"agent": agent, "previous": old_mode, "current": new_mode, "reason": reason}

    def get_mode(self, agent: str) -> str:
        return self.states[agent].current_mode

    def read_memory_bank(self, agent: str, file: str) -> str:
        path = self.agents_dir / agent / "memory-bank" / file
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_memory_bank(self, agent: str, file: str, content: str) -> None:
        path = self.agents_dir / agent / "memory-bank" / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        log.info("Updated %s/%s (%d bytes)", agent, file, len(content))

    def append_memory_bank(self, agent: str, file: str, content: str) -> None:
        existing = self.read_memory_bank(agent, file)
        self.write_memory_bank(agent, file, existing + "\n" + content)

    def read_shared(self, file: str) -> str:
        path = self.shared_dir / file
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_shared(self, file: str, content: str) -> None:
        path = self.shared_dir / file
        path.write_text(content, encoding="utf-8")

    def create_handoff(self, from_agent: str, to_agent: str, task: str, deliverables: list[str]) -> str:
        handoff_id = f"HO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        entry = (
            f"\n### {handoff_id}\n"
            f"- **From:** {from_agent}\n"
            f"- **To:** {to_agent}\n"
            f"- **Task:** {task}\n"
            f"- **Deliverables:** {', '.join(deliverables)}\n"
            f"- **Status:** 🔴 active\n"
            f"- **Created:** {datetime.utcnow().isoformat()}\n"
        )
        self.append_shared("handoffs.md", entry)
        self._log_execution(from_agent, "orchestrate", f"Created handoff {handoff_id} → {to_agent}: {task}")
        return handoff_id
    def complete_handoff(self, handoff_id: str, result: str) -> None:
        """Позначити handoff як виконаний."""
        content = self.read_shared("handoffs.md")
        # Знаходимо блок з цим handoff_id
        header = f"### {handoff_id}"
        start = content.find(header)
        if start == -1:
            log.warning("Handoff %s not found", handoff_id)
            return

        # Знаходимо кінець блоку (наступний ### або кінець файлу)
        next_header = content.find("\n### HO-", start + len(header))
        if next_header == -1:
            end = len(content)
        else:
            end = next_header

        block = content[start:end]
        if "🔴 active" in block:
            new_block = block.replace("🔴 active", "🟢 completed", 1)
            new_block += f"\n- **Completed:** {datetime.utcnow().isoformat()}\n"
            new_block += f"- **Result:** {result}\n"
            new_content = content[:start] + new_block + content[end:]
            self.write_shared("handoffs.md", new_content)
            log.info("Handoff %s marked completed", handoff_id)
        else:
            log.warning("Handoff %s already completed", handoff_id)

    def append_shared(self, file: str, content: str) -> None:
        existing = self.read_shared(file)
        self.write_shared(file, existing + "\n" + content)

    def _log_execution(self, agent: str, mode: str, action: str) -> None:
        entry = f"- **{datetime.utcnow().isoformat()}** [{agent}] [{mode}] — {action}\n"
        self.append_shared("executionLog.md", entry)

    def dashboard(self) -> dict:
        return {
            "agents": {
                agent: {
                    "mode": state.current_mode,
                    "previous": state.previous_mode,
                    "task": state.active_task,
                    "history_count": len(state.mode_history),
                    "last_updated": state.last_updated,
                }
                for agent, state in self.states.items()
            },
            "shared_files": {
                f.name: len(f.read_text(encoding="utf-8"))
                for f in self.shared_dir.glob("*.md")
                if f.is_file()
            },
        }

    def set_task(self, agent: str, task: str) -> None:
        self.states[agent].active_task = task
        self._save_state(agent)

    def clear_task(self, agent: str) -> None:
        self.states[agent].active_task = None
        self._save_state(agent)

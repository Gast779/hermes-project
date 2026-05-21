"""
Skills-to-RooFlow Sync — синхронізація Hermes skills з RooFlow Memory Bank.

Як це працює:
    1. Читає skills з hermes_integration/hermes_adapter.py
    2. Записує кожен skill в активний Memory Bank агента
    3. Оновлює projectBrief та systemPatterns
    4. Логує зміни в executionLog

Використання:
    python -c "from rooflow.skills_sync import sync_skills; sync_skills()"
    
    Або через CLI:
    python main.py rooflow sync-skills
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from hermes_integration.hermes_adapter import load_skills
from rooflow.engine import RooFlowEngine

log = logging.getLogger(__name__)

# Мапінг skill → агент (за префіксом або категорією)
SKILL_TO_AGENT: dict[str, str] = {
    "english": "english_bot",
    "crypto": "crypto_monitor",
    "polymarket": "polymarket_analyzer",
}


def _detect_agent(skill_id: str) -> str | None:
    """Визначити агента за ID skill."""
    for prefix, agent in SKILL_TO_AGENT.items():
        if prefix in skill_id.lower():
            return agent
    return None


def sync_skills() -> dict:
    """
    Синхронізувати всі skills з RooFlow Memory Bank.
    
    Returns:
        dict з результатами: {agent: [skill_ids]}
    """
    engine = RooFlowEngine()
    skills = load_skills()
    results: dict[str, list[str]] = {}
    
    for skill in skills:
        agent = _detect_agent(skill.id)
        if not agent:
            log.warning("Cannot map skill %s to agent — skipping", skill.id)
            continue
        
        # Записати skill в systemPatterns агента
        pattern_entry = (
            f"\n## Skill: {skill.id}\n"
            f"- **Назва:** {skill.name}\n"
            f"- **Опис:** {skill.description}\n"
            f"- **Entrypoint:** `{skill.entrypoint}`\n"
            f"- **Статус:** {'✅ enabled' if skill.enabled else '❌ disabled'}\n"
            f"- **Розклад:** {skill.schedule}\n"
            f"- **Синхронізовано:** {datetime.utcnow().isoformat()[:19]}\n"
        )
        engine.append_memory_bank(agent, "systemPatterns.md", pattern_entry)
        
        # Записати в progress
        progress_entry = (
            f"\n- [x] **{datetime.utcnow().isoformat()[:19]}** — Skill registered: {skill.id}\n"
            f"  - Режим: {skill.schedule}\n"
            f"  - Статус: {'✅ active' if skill.enabled else '⏸️ paused'}\n"
        )
        engine.append_memory_bank(agent, "progress.md", progress_entry)
        
        # Логувати
        engine._log_execution(agent, "orchestrate", f"Skill synced: {skill.id} → {agent}")
        
        results.setdefault(agent, []).append(skill.id)
        log.info("Synced skill %s → %s", skill.id, agent)
    
    # Оновити projectBrief зі списком всіх skills
    all_skills_summary = "\n## Skills Inventory\n\n"
    for agent, skill_ids in results.items():
        all_skills_summary += f"- **{agent}:** {', '.join(skill_ids)}\n"
    
    existing = engine.read_shared("projectBrief.md")
    if "## Skills Inventory" not in existing:
        engine.append_shared("projectBrief.md", all_skills_summary)
    else:
        # Оновити існуючий блок
        lines = existing.split("\n")
        new_lines = []
        in_inventory = False
        for line in lines:
            if line.startswith("## Skills Inventory"):
                in_inventory = True
                new_lines.append(all_skills_summary.strip())
                continue
            if in_inventory and line.startswith("## "):
                in_inventory = False
            if not in_inventory:
                new_lines.append(line)
        engine.write_shared("projectBrief.md", "\n".join(new_lines))
    
    engine._log_execution("orchestrate", "orchestrate", f"Skills sync complete: {sum(len(v) for v in results.values())} skills")
    
    return results


def sync_single_skill(skill_id: str) -> bool:
    """
    Синхронізувати один skill з RooFlow Memory Bank.
    
    Args:
        skill_id: ID skill для синхронізації
    
    Returns:
        True якщо успішно, False якщо skill не знайдено
    """
    engine = RooFlowEngine()
    skills = load_skills()
    
    skill = next((s for s in skills if s.id == skill_id), None)
    if not skill:
        log.warning("Skill %s not found", skill_id)
        return False
    
    agent = _detect_agent(skill.id)
    if not agent:
        log.warning("Cannot map skill %s to agent", skill_id)
        return False
    
    # Записати в activeContext — що зараз активно
    entry = (
        f"\n- **{datetime.utcnow().isoformat()[:19]}** — Skill: {skill.id}\n"
        f"  - Статус: {'✅ enabled' if skill.enabled else '❌ disabled'}\n"
        f"  - Розклад: {skill.schedule}\n"
    )
    engine.append_memory_bank(agent, "activeContext.md", entry)
    
    engine._log_execution(agent, "orchestrate", f"Single skill sync: {skill.id}")
    return True

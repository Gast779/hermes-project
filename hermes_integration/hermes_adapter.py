"""
Адаптер між нашими модулями і Hermes Dashboard.

Якщо ти знаєш точний формат skills для свого Hermes Dashboard — заміни
імпорти/декларацію тут.  Поки що це універсальний loader, який:
    - читає skills_config.yml,
    - повертає список skill-описів,
    - дає executor.execute(skill_id, args) — викликає правильний CLI-handler.
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

log = logging.getLogger(__name__)


@dataclass
class SkillDef:
    id: str
    name: str
    description: str
    entrypoint: str               # "module:function"
    enabled: bool
    schedule: Any
    config: dict[str, Any] | None = None

    def resolve(self) -> Callable[..., Any]:
        module_name, func_name = self.entrypoint.split(":")
        module = importlib.import_module(module_name)
        return getattr(module, func_name)


def load_skills(config_path: Path | str | None = None) -> list[SkillDef]:
    path = Path(config_path) if config_path else Path(__file__).parent / "skills_config.yml"
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return [SkillDef(**s) for s in data.get("skills", [])]


class HermesExecutor:
    def __init__(self, config_path: Path | str | None = None):
        self.skills = {s.id: s for s in load_skills(config_path)}

    def execute(self, skill_id: str, *args, **kwargs) -> Any:
        if skill_id not in self.skills:
            raise KeyError(f"Unknown skill: {skill_id}")
        skill = self.skills[skill_id]
        if not skill.enabled:
            log.warning("Skill %s is disabled in config", skill_id)
        fn = skill.resolve()
        log.info("Executing skill %s (%s)", skill.id, skill.entrypoint)
        return fn(*args, **kwargs)

    def list_skills(self) -> list[dict]:
        return [
            {"id": s.id, "name": s.name, "enabled": s.enabled, "description": s.description}
            for s in self.skills.values()
        ]

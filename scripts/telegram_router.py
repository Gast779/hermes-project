#!/usr/bin/env python3
"""
Telegram Topic Router для Hermes Multi-Agent System.

Маршрутизує звіти та повідомлення від skills у відповідні теми групи Hermes_team.
"""
from __future__ import annotations

import os
import yaml
import logging
from pathlib import Path
from typing import Optional

# Try importing send_message, fallback to requests
try:
    from hermes_tools import send_message
    HERMES_AVAILABLE = True
except ImportError:
    HERMES_AVAILABLE = False

log = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent.parent / "config" / "telegram_topics.yml"

class TopicRouter:
    """Routes messages to correct Telegram topics based on skill name."""

    def __init__(self):
        self.config = self._load_config()
        self.group_id = self.config["group_id"]
        self.topics = self.config["topics"]
        self.default = self.config.get("default_topic", "english_learning_bot")
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    def _load_config(self) -> dict:
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)

    def get_topic_id(self, skill_name: str) -> Optional[int]:
        """Find thread_id for a given skill name."""
        for topic_key, topic_data in self.topics.items():
            if skill_name in topic_data.get("skills", []):
                return topic_data["thread_id"]
        # Fallback to default
        default_data = self.topics.get(self.default, {})
        return default_data.get("thread_id")

    def get_topic_name(self, skill_name: str) -> str:
        """Get human-readable topic name."""
        for topic_key, topic_data in self.topics.items():
            if skill_name in topic_data.get("skills", []):
                return topic_data["name"]
        default_data = self.topics.get(self.default, {})
        return default_data.get("name", "General")

    def send_to_topic(self, skill_name: str, message: str, *, use_hermes: bool = True) -> bool:
        """Send message to the correct topic."""
        thread_id = self.get_topic_id(skill_name)
        topic_name = self.get_topic_name(skill_name)

        if not thread_id:
            log.error(f"No thread_id found for skill: {skill_name}")
            return False

        target = f"telegram:{self.group_id}:{thread_id}"
        log.info(f"Routing {skill_name} -> {topic_name} (thread {thread_id})")

        if use_hermes and HERMES_AVAILABLE:
            try:
                send_message(message=message, target=target)
                return True
            except Exception as e:
                log.warning(f"Hermes send failed: {e}, falling back to direct API")

        # Fallback: direct Telegram API
        return self._send_via_api(message, thread_id)

    def _send_via_api(self, message: str, thread_id: int) -> bool:
        """Send via direct HTTP API call."""
        import requests

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.group_id,
            "message_thread_id": thread_id,
            "text": message,
            "parse_mode": "Markdown",
        }

        try:
            resp = requests.post(url, json=payload, timeout=30)
            return resp.status_code == 200
        except Exception as e:
            log.error(f"API send failed: {e}")
            return False

    def list_topics(self) -> dict:
        """Return all topics for display."""
        return {
            key: {
                "name": data["name"],
                "thread_id": data["thread_id"],
                "skills": data["skills"],
            }
            for key, data in self.topics.items()
        }


# Convenience function
def route_message(skill_name: str, message: str) -> bool:
    """Quick send to correct topic."""
    router = TopicRouter()
    return router.send_to_topic(skill_name, message)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 3:
        print("Usage: telegram_router.py <skill_name> <message>")
        print("\nAvailable skills:")
        router = TopicRouter()
        for key, data in router.list_topics().items():
            print(f"  {key}: {data['name']} (thread {data['thread_id']})")
        sys.exit(1)

    skill = sys.argv[1]
    message = sys.argv[2]
    success = route_message(skill, message)
    print("✅ Sent" if success else "❌ Failed")

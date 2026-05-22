"""
Local secrets storage.

Замість .env у git — використовуй keyring (cross-platform).

Якщо є $5/month — лучше HashiCorp Vault або AWS Secrets Manager.
Цей файл — мінімум.
"""
import os
from pathlib import Path
import json
from datetime import datetime
from typing import Optional


def get_secret(key: str, fallback_env: bool = True) -> Optional[str]:
    """
    Тягне secret з keyring; fallback до env var.

    Install: pip install keyring
    Setup:
        python -c "import keyring; keyring.set_password('hermes', 'XAI_API_KEY', 'sk-...')"
    """
    try:
        import keyring
        val = keyring.get_password("hermes", key)
        if val:
            return val
    except Exception:
        pass

    if fallback_env:
        return os.getenv(key)
    return None


def rotate_check(key: str, max_age_days: int = 90) -> bool:
    """
    Перевіряє чи key старший за max_age_days.
    Метадата rotation tracked у local file.
    """
    metadata_file = Path.home() / ".hermes" / "secrets_metadata.json"
    if not metadata_file.exists():
        return False  # unknown — treat as fresh

    with open(metadata_file) as f:
        meta = json.load(f)

    last_rotated = meta.get(key, {}).get("rotated_at")
    if not last_rotated:
        return False

    age_days = (datetime.utcnow() - datetime.fromisoformat(last_rotated)).days
    return age_days > max_age_days

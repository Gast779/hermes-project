#!/usr/bin/env python3
"""One-off send of fast movers scan result to Telegram topic."""
import os
import sys

# Load main hermes .env where TELEGRAM_BOT_TOKEN lives
from pathlib import Path
from dotenv import load_dotenv

env_path = Path.home() / '.hermes' / '.env'
load_dotenv(env_path, override=True)

# Also load project local env if present (for overrides)
project_env = Path('/tmp/hermes_project/hermes_project/.env')
if project_env.exists():
    load_dotenv(project_env, override=True)

# Dedupe TELEGRAM_BOT_TOKEN if duplicated in file
raw = env_path.read_text()
# prefer the non-empty one near line 472
tokens = [l.split('=', 1)[1].strip() for l in raw.splitlines() if l.strip().startswith('TELEGRAM_BOT_TOKEN=')]
for t in tokens:
    if t and not t.startswith('***'):
        os.environ['TELEGRAM_BOT_TOKEN'] = t
        break

sys.path.insert(0, '/tmp/hermes_project/hermes_project')
from scripts.notify_telegram import send_telegram

text = '🟢 Fast Movers: різких рухів не виявлено.'
ok = send_telegram(text, chat_id='-1003792129186', message_thread_id=26)
print('Sent:', ok)

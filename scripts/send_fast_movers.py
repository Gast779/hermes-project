#!/usr/bin/env python3
"""One-off send of fast movers scan result to Telegram topic."""
import os
import sys

# Load main hermes .env where TELEGRAM_BOT_TOKEN lives
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path.home() / '.hermes' / '.env')

sys.path.insert(0, '/tmp/hermes_project/hermes_project')
from scripts.notify_telegram import send_telegram

text = '🟢 Fast Movers: різких рухів не виявлено.'
ok = send_telegram(text, chat_id='-1003792129186', message_thread_id=26)
print('Sent:', ok)

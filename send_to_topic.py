#!/usr/bin/env python3
"""Send a message to a Telegram topic."""
import os, sys
sys.path.insert(0, '/tmp/hermes_project/hermes_project')

from scripts.notify_telegram import send_telegram

CHAT_ID = "-1003792129186"
THREAD_ID = 27
MESSAGE = "🔍 Сканування завершено. Арбітраж не знайдено."

ok = send_telegram(MESSAGE, chat_id=CHAT_ID, message_thread_id=THREAD_ID)
print("sent" if ok else "failed")

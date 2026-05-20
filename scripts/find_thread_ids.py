#!/usr/bin/env python3
"""
Скрипт для визначення справжніх message_thread_id тем Telegram.

Відправляє тестове повідомлення з різними thread_id та показує, куди воно потрапило.
"""
import os
import sys
import time
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = "-1003792129186"

if not TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not set")
    sys.exit(1)

def send_test(thread_id: int) -> bool:
    """Send test message to specific thread_id."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": thread_id,
        "text": f"🔍 Тест thread_id={thread_id}",
    }
    resp = requests.post(url, json=payload, timeout=30)
    data = resp.json()
    if data.get("ok"):
        print(f"✅ thread_id={thread_id}: Надіслано успішно")
        return True
    else:
        err = data.get("description", "Unknown error")
        print(f"❌ thread_id={thread_id}: {err}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1, help="Start thread_id")
    parser.add_argument("--end", type=int, default=50, help="End thread_id")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between sends (sec)")
    args = parser.parse_args()

    print(f"🔍 Пошук тем у групі {CHAT_ID}")
    print(f"Діапазон: {args.start} - {args.end}")
    print("-" * 40)

    found = []
    for tid in range(args.start, args.end + 1):
        if send_test(tid):
            found.append(tid)
        time.sleep(args.delay)

    print("-" * 40)
    print(f"Знайдено {len(found)} тем: {found}")
    print("\n⚠️ Видаліть тестові повідомлення з групи!")

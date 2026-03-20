import os
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(message):

    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM credentials in .env")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"   # optional but recommended
    }

    try:
        response = requests.post(url, data=payload)

        if response.status_code != 200:
            print("❌ Telegram Error:", response.text)

    except Exception as e:
        print("❌ Telegram Exception:", e)
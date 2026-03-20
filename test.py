from alerts.telegram_bot import send_telegram_message
from alerts.telegram_bot import BOT_TOKEN
from alerts.telegram_bot import CHAT_ID

print("BOT:", BOT_TOKEN)
print("CHAT:", CHAT_ID)
send_telegram_message("Bot working via .env") 
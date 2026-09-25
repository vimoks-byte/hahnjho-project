import os
import sys
import asyncio
import requests
from dotenv import load_dotenv
from telegram import Bot

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

NH_APP_KEY = os.getenv("NH_APP_KEY")
NH_APP_SECRET = os.getenv("NH_APP_SECRET")
NH_BASE_URL = os.getenv("NH_BASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID")

async def test_telegram():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    me = await bot.get_me()
    print(f"Telegram Bot Connected: @{me.username} ({me.first_name})")
    await bot.send_message(chat_id=ALLOWED_CHAT_ID, text="🤖 NH투자증권 나무 PLUG 자동매매 연동 테스트 성공")
    print("Telegram test message sent successfully.")

def test_nh_api():
    url = f"{NH_BASE_URL}/oauth2/token"
    payload = {
        "grant_type": "client_credentials",
        "appkey": NH_APP_KEY,
        "appsecretkey": NH_APP_SECRET,
        "scope": "oob"
    }
    headers = {"content-type": "application/x-www-form-urlencoded"}
    
    import urllib3
    urllib3.disable_warnings()
    response = requests.post(url, data=payload, headers=headers, verify=False)
    print("NH API Token Response Status:", response.status_code)
    try:
        data = response.json()
        if "access_token" in data:
            print("NH API Token successfully retrieved:", data["access_token"][:15] + "...")
        else:
            print("NH API Response JSON:", data)
    except Exception as e:
        print("Failed to parse NH API response:", e, response.text)

if __name__ == "__main__":
    print("Starting connection tests...")
    try:
        test_nh_api()
        print("✅ NH API test executed.\n")
    except Exception as e:
        print("❌ NH API test failed:", e, "\n")
        
    try:
        asyncio.run(test_telegram())
        print("✅ Telegram test succeeded!")
    except Exception as e:
        print("❌ Telegram test failed:", e)

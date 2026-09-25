import os
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

class TelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("ALLOWED_CHAT_ID")
        self.bot = Bot(token=self.token)

    async def send_message(self, text):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text)
        except Exception as e:
            print(f"텔레그램 메시지 전송 실패: {e}")

    async def send_buy_approval(self, symbol, price, qty, reason):
        keyboard = [
            [
                InlineKeyboardButton("매수 승인", callback_data=f"buy_{symbol}_{price}_{qty}"),
                InlineKeyboardButton("취소", callback_data="cancel_buy")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"🔥 매수 조건 포착 ({reason})\n종목: {symbol}\n가격: {price}원\n수량: {qty}주\n승인하시겠습니까?"
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)
        except Exception as e:
            print(f"텔레그램 매수 승인 메시지 전송 실패: {e}")

    async def send_sell_approval(self, symbol, price, qty, reason):
        keyboard = [
            [
                InlineKeyboardButton("매도 승인", callback_data=f"sell_{symbol}_{price}_{qty}"),
                InlineKeyboardButton("취소", callback_data="cancel_sell")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"🚨 매도 조건 발생 ({reason})\n종목: {symbol}\n현재가: {price}원\n수량: {qty}주\n승인하시겠습니까?"
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)
        except Exception as e:
            print(f"텔레그램 매도 승인 메시지 전송 실패: {e}")

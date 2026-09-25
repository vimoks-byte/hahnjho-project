import os
import sys
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from nh_api import NhApi
from position_mgr import PositionManager
from telegram_bot import TelegramBot

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

load_dotenv()

nh = NhApi()
pos_mgr = PositionManager()
tg_bot = TelegramBot()

ORDER_AMOUNT_KRW = int(os.getenv("ORDER_AMOUNT_KRW", "1000000"))
SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "30")) # API 호출 스로틀 및 모니터링 주기

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    acc = nh.get_account_no()
    msg = (
        f"🤖 NH투자증권 나무 PLUG 자동매매 봇이 시작되었습니다.\n\n"
        f"📌 연동 계좌: {acc}\n"
        f"💰 1회 매수 설정금액: {ORDER_AMOUNT_KRW:,}원\n"
        f"⏱️ 스캔 주기: {SCAN_INTERVAL_SEC}초\n\n"
        f"사용 가능 명령어:\n"
        f"/status - 보유 포지션 및 계좌 잔고 현황 확인"
    )
    await update.message.reply_text(msg)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = pos_mgr.get_status_text(nh_api=nh)
    await update.message.reply_text(text)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "cancel_buy" or data == "cancel_sell":
        await query.edit_message_text(text="🚫 주문이 취소되었습니다.")
        return
        
    parts = data.split('_')
    if len(parts) < 4:
        return
        
    action = parts[0]
    symbol = parts[1]
    price = int(parts[2])
    qty = int(parts[3])
    
    if action == "buy":
        try:
            res = nh.place_order(symbol, price, qty, is_buy=True)
            if res.get('rt_cd') == '0':
                pos_mgr.add_position(symbol, price, qty)
                await query.edit_message_text(text=f"✅ 매수 주문 접수 완료: {symbol} {qty}주 @ {price:,}원\n응답: {res.get('msg1')}")
            else:
                await query.edit_message_text(text=f"❌ 매수 주문 실패: {res.get('msg1')}")
        except Exception as e:
            await query.edit_message_text(text=f"❌ 매수 주문 에러: {e}")
            
    elif action == "sell":
        try:
            res = nh.place_order(symbol, price, qty, is_buy=False)
            if res.get('rt_cd') == '0':
                pos_mgr.remove_position(symbol)
                await query.edit_message_text(text=f"✅ 매도 주문 접수 완료: {symbol} {qty}주 @ {price:,}원\n응답: {res.get('msg1')}")
            else:
                await query.edit_message_text(text=f"❌ 매도 주문 실패: {res.get('msg1')}")
        except Exception as e:
            await query.edit_message_text(text=f"❌ 매도 주문 에러: {e}")

async def monitor_loop():
    print("감시 루프 시작...", flush=True)
    await tg_bot.send_message("📈 실전투자기반 모니터링 루프가 가동되었습니다.")
    
    pending_approvals = set()

    while True:
        try:
            # 1. 대상 종목 스캔
            symbols = nh.get_top_trading_value()
            for sym in symbols:
                if sym in pos_mgr.positions or sym in pending_approvals:
                    continue
                
                # 5일 이동평균선 기반 조건 탐색 (비동기 스레드 풀에서 실행)
                candles = await asyncio.to_thread(nh.get_daily_candles, sym)
                if len(candles) < 5:
                    continue
                    
                current_price = candles[0]
                ma5 = sum(candles[:5]) / 5
                
                # 매수 조건: 현재가가 5일선 대비 1% 이상일 때 (상향 돌파)
                if current_price > ma5 * 1.01:
                    qty = ORDER_AMOUNT_KRW // current_price
                    if qty > 0:
                        reason = f"현재가({current_price:,}원) > 5일선({int(ma5):,}원) 1% 상향 돌파"
                        await tg_bot.send_buy_approval(sym, current_price, qty, reason)
                        pending_approvals.add(sym)
            
            # 2. 보유 포지션 매도 감시
            for sym, pos in list(pos_mgr.positions.items()):
                current_price = await asyncio.to_thread(nh.get_current_price, sym)
                if current_price == 0:
                    continue
                    
                reason = pos_mgr.check_exit_condition(sym, current_price)
                if reason:
                    await tg_bot.send_sell_approval(sym, current_price, pos['qty'], reason)

        except asyncio.CancelledError:
            print("모니터링 루프 정상 종료.", flush=True)
            break
        except Exception as e:
            print(f"모니터링 에러: {e}", flush=True)
            
        await asyncio.sleep(SCAN_INTERVAL_SEC)

monitor_task = None

async def post_init(application: Application) -> None:
    global monitor_task
    tg_bot.bot = application.bot
    monitor_task = asyncio.create_task(monitor_loop())

async def post_shutdown(application: Application) -> None:
    global monitor_task
    if monitor_task and not monitor_task.done():
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

def main():
    print("NH투자증권 자동매매 봇 구동 준비 중...", flush=True)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("텔레그램 봇 폴링 시작...", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()

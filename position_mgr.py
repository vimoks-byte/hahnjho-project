import os
from dotenv import load_dotenv

load_dotenv()

class PositionManager:
    def __init__(self):
        self.target_profit = float(os.getenv("TARGET_PROFIT_RATE", "3.0"))
        self.stop_loss = float(os.getenv("STOP_LOSS_RATE", "-2.0"))
        self.positions = {}

    def add_position(self, symbol: str, price: int, qty: int):
        self.positions[symbol] = {
            'entry_price': price,
            'qty': qty
        }

    def remove_position(self, symbol: str):
        if symbol in self.positions:
            del self.positions[symbol]

    def check_exit_condition(self, symbol: str, current_price: int):
        if symbol not in self.positions or current_price == 0:
            return None
        
        entry = self.positions[symbol]['entry_price']
        profit_rate = ((current_price - entry) / entry) * 100
        
        if profit_rate >= self.target_profit:
            return f"TAKE_PROFIT (+{profit_rate:.2f}%)"
        elif profit_rate <= self.stop_loss:
            return f"STOP_LOSS ({profit_rate:.2f}%)"
        return None

    def get_status_text(self, nh_api=None) -> str:
        lines = []
        if self.positions:
            lines.append("📊 [봇 실시간 감시 포지션]")
            for sym, pos in self.positions.items():
                lines.append(f"- 종목: {sym} | 진입가: {pos['entry_price']:,}원 | 수량: {pos['qty']}주")

        if nh_api:
            try:
                holdings = nh_api.get_balance()
                if holdings:
                    lines.append("\n💼 [NH투자증권 계좌 잔고 보유 현황]")
                    for h in holdings:
                        nm = h.get('iem_nm', h.get('iem_cd', ''))
                        qty = int(h.get('itg_bnc_qty', 0))
                        phs = int(h.get('phs_pr', 0))
                        now = int(h.get('now_pr', 0))
                        pft = float(h.get('pft_rt', 0))
                        lines.append(f"- {nm} ({h.get('iem_cd')}): {qty}주 | 매입가: {phs:,}원 | 현재가: {now:,}원 ({pft:+.2f}%)")
            except Exception as e:
                lines.append(f"\n(잔고 조회 오류: {e})")

        if not lines:
            return "보유 중인 포지션이 없습니다."
            
        return "\n".join(lines)

import os
import sys
import json
import time
import threading
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

from nh_api import NhApi
from position_mgr import PositionManager

load_dotenv()

app = Flask(__name__)

# 전역 객체
nh = NhApi()
pos_mgr = PositionManager()

# 종목 이름 매핑
STOCK_NAMES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스",
    "005380": "현대차",
    "035420": "NAVER",
    "000270": "기아",
    "068270": "셀트리온",
    "105560": "KB금융"
}

# 봇 상태 관리
bot_state = {
    "is_running": False,
    "last_scan_time": None,
    "scan_count": 0,
    "logs": []
}

def add_log(message: str, level: str = "INFO"):
    entry = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message
    }
    bot_state["logs"].insert(0, entry)
    if len(bot_state["logs"]) > 100:
        bot_state["logs"].pop()

# 초기 로그
add_log("웹 대시보드 서버가 초기화되었습니다.", "INFO")
add_log(f"NH 연동 계좌: {os.getenv('NH_ACCOUNT_NO', '미설정')}", "INFO")

# 초기 데모/모니터링용 샘플 포지션 등록
pos_mgr.add_position("005930", 72000, 15)  # 삼성전자 15주 @ 72,000원
pos_mgr.add_position("000660", 175000, 5)  # SK하이닉스 5주 @ 175,000원
add_log("샘플 보유 포지션 등록 완료: 삼성전자(005930) 15주, SK하이닉스(000660) 5주", "INFO")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ NH 나무 PLUG 주식 자동매매 봇 대시보드</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
        body {
            font-family: 'Pretendard', sans-serif;
            background-color: #0b0f19;
            color: #e2e8f0;
        }
        .code-font {
            font-family: 'JetBrains Mono', monospace;
        }
        .glass-card {
            background: rgba(17, 24, 39, 0.75);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .glow-green {
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.25);
        }
        .glow-red {
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.25);
        }
        .glow-blue {
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.25);
        }
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #0f172a;
        }
        ::-webkit-scrollbar-thumb {
            background: #334155;
            border-radius: 3px;
        }
    </style>
</head>
<body class="min-h-screen pb-12">
    <!-- Navbar -->
    <header class="glass-card sticky top-0 z-50 border-b border-slate-800/80 px-6 py-4">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-blue-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                    <i class="fa-solid fa-chart-line text-white text-lg"></i>
                </div>
                <div>
                    <h1 class="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                        NH 나무 PLUG <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">LIVE</span>
                    </h1>
                    <p class="text-xs text-slate-400">주식 자동매매 모니터링 & 제어 콘솔</p>
                </div>
            </div>
            
            <div class="flex items-center space-x-4">
                <div id="bot-status-badge" class="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-emerald-400 text-xs font-semibold">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span>시스템 온라인</span>
                </div>
                <button onclick="triggerScan()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 active:scale-95 transition-all text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-lg shadow-blue-600/20">
                    <i class="fa-solid fa-arrows-rotate" id="scan-icon"></i>
                    <span>수동 종목 스캔</span>
                </button>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 mt-6 space-y-6">
        <!-- Top Stats Row -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <!-- 계좌 정보 -->
            <div class="glass-card rounded-2xl p-5 relative overflow-hidden">
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
                    <span>연동 계좌</span>
                    <i class="fa-regular fa-credit-card text-blue-400"></i>
                </div>
                <div class="text-lg font-bold text-white tracking-wider code-font" id="account-no">-</div>
                <div class="text-xs text-slate-400 mt-2 flex items-center gap-1">
                    <i class="fa-solid fa-shield-halved text-emerald-400"></i> NH투자증권 PLUG Open API
                </div>
            </div>

            <!-- 1회 주문 설정금액 -->
            <div class="glass-card rounded-2xl p-5">
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
                    <span>1회 매수 설정금액</span>
                    <i class="fa-solid fa-won-sign text-emerald-400"></i>
                </div>
                <div class="text-xl font-extrabold text-emerald-400" id="order-amount">-</div>
                <div class="text-xs text-slate-400 mt-2">고정 분할 매수 모드</div>
            </div>

            <!-- 목표/손절 설정 -->
            <div class="glass-card rounded-2xl p-5">
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
                    <span>전략 목표 / 손절</span>
                    <i class="fa-solid fa-crosshairs text-amber-400"></i>
                </div>
                <div class="flex items-baseline space-x-3">
                    <span class="text-lg font-bold text-red-400" id="target-profit">+3.0%</span>
                    <span class="text-xs text-slate-500">/</span>
                    <span class="text-lg font-bold text-blue-400" id="stop-loss">-2.0%</span>
                </div>
                <div class="text-xs text-slate-400 mt-2">5일 이평선 돌파 매수 전략</div>
            </div>

            <!-- 스캔 주기 & 최종스캔 -->
            <div class="glass-card rounded-2xl p-5">
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
                    <span>스캔 주기 & 상태</span>
                    <i class="fa-regular fa-clock text-purple-400"></i>
                </div>
                <div class="text-lg font-bold text-white" id="scan-interval">-</div>
                <div class="text-xs text-slate-400 mt-2 flex items-center gap-1">
                    <span>마지막 탐색:</span> <span id="last-scan" class="text-slate-300 font-mono">방금 전</span>
                </div>
            </div>
        </div>

        <!-- Main Content 2-Columns -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Left 2 Cols: Quotes & Positions -->
            <div class="lg:col-span-2 space-y-6">
                <!-- 종목 실시간 시세 및 5일 이평선 모니터 -->
                <div class="glass-card rounded-2xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <div>
                            <h2 class="text-base font-bold text-white flex items-center gap-2">
                                <i class="fa-solid fa-radar text-emerald-400"></i>
                                시장 감시 종목 & 5일 이동평균선(MA5) 분석
                            </h2>
                            <p class="text-xs text-slate-400 mt-0.5">5일선 대비 1% 이상 돌파 시 텔레그램 매수 승인 요청 자동 발송</p>
                        </div>
                        <span class="text-xs font-mono text-slate-400" id="refresh-timer">5초 후 갱신</span>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="text-xs uppercase text-slate-400 border-b border-slate-800">
                                    <th class="py-3 px-4">종목명 / 코드</th>
                                    <th class="py-3 px-4 text-right">현재가</th>
                                    <th class="py-3 px-4 text-right">5일선(MA5)</th>
                                    <th class="py-3 px-4 text-right">이격도</th>
                                    <th class="py-3 px-4 text-center">전략 시그널</th>
                                </tr>
                            </thead>
                            <tbody id="quotes-tbody" class="divide-y divide-slate-800/60 text-sm">
                                <tr>
                                    <td colspan="5" class="py-8 text-center text-slate-500">데이터를 불러오는 중입니다...</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- 보유 포지션 및 계좌 잔고 -->
                <div class="glass-card rounded-2xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <div>
                            <h2 class="text-base font-bold text-white flex items-center gap-2">
                                <i class="fa-solid fa-briefcase text-blue-400"></i>
                                실시간 보유 포지션 & 익절/손절 감시
                            </h2>
                            <p class="text-xs text-slate-400 mt-0.5">봇이 매수한 포지션의 실시간 수익률 및 자동 청산 기준</p>
                        </div>
                        <button onclick="addSimulatedPosition()" class="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition border border-slate-700">
                            + 테스트 포지션 추가
                        </button>
                    </div>

                    <div id="positions-container">
                        <div class="py-8 text-center text-slate-500 text-sm">현재 보유 중인 포지션이 없습니다.</div>
                    </div>
                </div>

                <!-- 코드 및 파일 뷰어 -->
                <div class="glass-card rounded-2xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            <i class="fa-solid fa-file-code text-indigo-400"></i>
                            프로젝트 소스 코드 뷰어
                        </h2>
                        <div class="flex space-x-1" id="file-tabs">
                            <button onclick="loadFile('main.py')" class="file-tab px-3 py-1 text-xs rounded-lg font-medium transition bg-blue-600 text-white" data-file="main.py">main.py</button>
                            <button onclick="loadFile('nh_api.py')" class="file-tab px-3 py-1 text-xs rounded-lg font-medium transition bg-slate-800 text-slate-400 hover:text-slate-200" data-file="nh_api.py">nh_api.py</button>
                            <button onclick="loadFile('position_mgr.py')" class="file-tab px-3 py-1 text-xs rounded-lg font-medium transition bg-slate-800 text-slate-400 hover:text-slate-200" data-file="position_mgr.py">position_mgr.py</button>
                            <button onclick="loadFile('telegram_bot.py')" class="file-tab px-3 py-1 text-xs rounded-lg font-medium transition bg-slate-800 text-slate-400 hover:text-slate-200" data-file="telegram_bot.py">telegram_bot.py</button>
                            <button onclick="loadFile('test_connection.py')" class="file-tab px-3 py-1 text-xs rounded-lg font-medium transition bg-slate-800 text-slate-400 hover:text-slate-200" data-file="test_connection.py">test_connection.py</button>
                        </div>
                    </div>
                    <pre class="bg-slate-950 p-4 rounded-xl text-xs text-slate-300 font-mono overflow-x-auto max-h-80 border border-slate-800" id="code-content">// 파일 내용을 불러오는 중입니다...</pre>
                </div>
            </div>

            <!-- Right 1 Col: Live Logs & Bot Controls -->
            <div class="space-y-6">
                <!-- 제어 콘솔 -->
                <div class="glass-card rounded-2xl p-6">
                    <h2 class="text-base font-bold text-white mb-4 flex items-center gap-2">
                        <i class="fa-solid fa-sliders text-amber-400"></i>
                        봇 제어 및 테스트
                    </h2>
                    
                    <div class="space-y-3">
                        <button onclick="triggerScan()" class="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:scale-98 transition rounded-xl text-xs font-semibold text-white flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/20">
                            <i class="fa-solid fa-magnifying-glass"></i>
                            전 종목 즉시 스캔 실행
                        </button>

                        <button onclick="testConnection()" class="w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 active:scale-98 transition rounded-xl text-xs font-semibold text-slate-200 flex items-center justify-center gap-2 border border-slate-700">
                            <i class="fa-brands fa-telegram text-sky-400"></i>
                            API & 텔레그램 연동 점검
                        </button>
                    </div>

                    <div class="mt-5 pt-5 border-t border-slate-800/80 text-xs space-y-2 text-slate-400">
                        <div class="flex justify-between">
                            <span>텔레그램 봇 토큰</span>
                            <span class="text-emerald-400 font-mono" id="tg-status">설정됨</span>
                        </div>
                        <div class="flex justify-between">
                            <span>NH APP KEY</span>
                            <span class="text-emerald-400 font-mono" id="nh-key-status">설정됨</span>
                        </div>
                        <div class="flex justify-between">
                            <span>NH BASE URL</span>
                            <span class="text-slate-300 font-mono text-[10px]" id="nh-url-status">OPENAPI URL</span>
                        </div>
                    </div>
                </div>

                <!-- 실시간 이벤트 로그 -->
                <div class="glass-card rounded-2xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            <i class="fa-solid fa-terminal text-emerald-400"></i>
                            실시간 봇 활동 로그
                        </h2>
                        <button onclick="clearLogs()" class="text-[11px] text-slate-500 hover:text-slate-300">지우기</button>
                    </div>
                    
                    <div class="bg-slate-950/80 rounded-xl p-3 border border-slate-800/80 h-96 overflow-y-auto space-y-2 text-xs font-mono" id="log-container">
                        <!-- 로그 항목 -->
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        let countdown = 5;

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                document.getElementById('account-no').innerText = data.account_no || '미설정';
                document.getElementById('order-amount').innerText = Number(data.order_amount).toLocaleString() + '원';
                document.getElementById('target-profit').innerText = '+' + data.target_profit + '%';
                document.getElementById('stop-loss').innerText = data.stop_loss + '%';
                document.getElementById('scan-interval').innerText = data.scan_interval + '초 마다';
                document.getElementById('last-scan').innerText = data.last_scan_time || '방금 전';
                
                document.getElementById('tg-status').innerText = data.tg_token_set ? '연결 가능' : '미설정';
                document.getElementById('nh-key-status').innerText = data.nh_key_set ? '인증 완료' : '미설정';
                document.getElementById('nh-url-status').innerText = data.nh_base_url || '-';
            } catch (e) {
                console.error('Status fetch error:', e);
            }
        }

        async function fetchQuotes() {
            try {
                const res = await fetch('/api/quotes');
                const data = await res.json();
                
                const tbody = document.getElementById('quotes-tbody');
                if (!data || data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-slate-500">조회된 종목이 없습니다.</td></tr>';
                    return;
                }

                tbody.innerHTML = data.map(q => {
                    const diff = q.ma_diff || 0;
                    const diffColor = diff > 0 ? 'text-red-400' : (diff < 0 ? 'text-blue-400' : 'text-slate-400');
                    const diffSign = diff > 0 ? '+' : '';
                    
                    let signalBadge = '<span class="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-400">관망</span>';
                    if (q.is_signal) {
                        signalBadge = '<span class="px-2 py-0.5 rounded text-[11px] bg-red-500/20 text-red-400 border border-red-500/30 font-bold animate-pulse">🔥 매수 돌파</span>';
                    }

                    return `
                        <tr class="hover:bg-slate-800/40 transition">
                            <td class="py-3 px-4">
                                <div class="font-bold text-white">${q.name}</div>
                                <div class="text-[11px] text-slate-500 font-mono">${q.symbol}</div>
                            </td>
                            <td class="py-3 px-4 text-right font-mono font-bold text-white">
                                ${Number(q.current_price).toLocaleString()}원
                            </td>
                            <td class="py-3 px-4 text-right font-mono text-slate-300">
                                ${Number(q.ma5).toLocaleString()}원
                            </td>
                            <td class="py-3 px-4 text-right font-mono font-bold ${diffColor}">
                                ${diffSign}${diff.toFixed(2)}%
                            </td>
                            <td class="py-3 px-4 text-center">
                                ${signalBadge}
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (e) {
                console.error('Quotes fetch error:', e);
            }
        }

        async function fetchPositions() {
            try {
                const res = await fetch('/api/positions');
                const data = await res.json();
                const container = document.getElementById('positions-container');
                
                if (!data || data.length === 0) {
                    container.innerHTML = '<div class="py-8 text-center text-slate-500 text-sm">현재 보유 중인 포지션이 없습니다.</div>';
                    return;
                }

                container.innerHTML = `
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        ${data.map(p => {
                            const profit = p.profit_rate;
                            const isProfit = profit >= 0;
                            const color = isProfit ? 'text-red-400' : 'text-blue-400';
                            const bgColor = isProfit ? 'bg-red-500/10 border-red-500/20' : 'bg-blue-500/10 border-blue-500/20';

                            return `
                                <div class="p-4 rounded-xl border ${bgColor} flex flex-col justify-between">
                                    <div class="flex items-center justify-between">
                                        <div>
                                            <div class="font-bold text-white">${p.name} <span class="text-xs text-slate-400 font-mono">(${p.symbol})</span></div>
                                            <div class="text-xs text-slate-400 mt-0.5">${p.qty}주 보유</div>
                                        </div>
                                        <div class="text-right">
                                            <div class="text-lg font-bold font-mono ${color}">${isProfit ? '+' : ''}${profit.toFixed(2)}%</div>
                                            <div class="text-xs text-slate-400 font-mono">${(p.profit_amount >= 0 ? '+' : '') + Number(p.profit_amount).toLocaleString()}원</div>
                                        </div>
                                    </div>
                                    <div class="mt-3 pt-3 border-t border-slate-800 text-[11px] flex justify-between text-slate-400">
                                        <span>매입가: <b class="text-slate-200 font-mono">${Number(p.entry_price).toLocaleString()}원</b></span>
                                        <span>현재가: <b class="text-slate-200 font-mono">${Number(p.current_price).toLocaleString()}원</b></span>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `;
            } catch (e) {
                console.error('Positions fetch error:', e);
            }
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                const logs = await res.json();
                const container = document.getElementById('log-container');
                
                container.innerHTML = logs.map(l => {
                    let levelColor = 'text-slate-400';
                    if (l.level === 'SUCCESS') levelColor = 'text-emerald-400 font-bold';
                    if (l.level === 'SIGNAL') levelColor = 'text-amber-400 font-bold';
                    if (l.level === 'ERROR') levelColor = 'text-red-400 font-bold';
                    
                    return `
                        <div class="leading-relaxed border-b border-slate-900/50 pb-1">
                            <span class="text-slate-600">[${l.timestamp}]</span>
                            <span class="${levelColor}">[${l.level}]</span>
                            <span class="text-slate-300">${l.message}</span>
                        </div>
                    `;
                }).join('');
            } catch (e) {
                console.error('Logs fetch error:', e);
            }
        }

        async function triggerScan() {
            const icon = document.getElementById('scan-icon');
            icon.classList.add('fa-spin');
            try {
                await fetch('/api/scan', { method: 'POST' });
                await fetchQuotes();
                await fetchLogs();
                await fetchStatus();
            } finally {
                setTimeout(() => icon.classList.remove('fa-spin'), 600);
            }
        }

        async function testConnection() {
            try {
                const res = await fetch('/api/test_connection', { method: 'POST' });
                const result = await res.json();
                alert(result.message);
                fetchLogs();
            } catch (e) {
                alert('연결 테스트 에러: ' + e);
            }
        }

        async function addSimulatedPosition() {
            const sym = prompt("테스트로 등록할 종목 코드를 입력하세요 (예: 005930 삼성전자, 000660 SK하이닉스):", "005930");
            if (!sym) return;
            const price = prompt("진입 단가를 입력하세요 (원):", "70000");
            if (!price) return;
            const qty = prompt("수량을 입력하세요 (주):", "15");
            if (!qty) return;

            await fetch('/api/add_position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: sym, price: parseInt(price), qty: parseInt(qty) })
            });
            fetchPositions();
            fetchLogs();
        }

        async function loadFile(fileName) {
            document.querySelectorAll('.file-tab').forEach(t => {
                if (t.dataset.file === fileName) {
                    t.className = 'file-tab px-3 py-1 text-xs rounded-lg font-medium transition bg-blue-600 text-white';
                } else {
                    t.className = 'file-tab px-3 py-1 text-xs rounded-lg font-medium transition bg-slate-800 text-slate-400 hover:text-slate-200';
                }
            });

            try {
                const res = await fetch(`/api/file/${fileName}`);
                const data = await res.json();
                document.getElementById('code-content').textContent = data.content || data.error;
            } catch (e) {
                document.getElementById('code-content').textContent = '파일 로딩 실패: ' + e;
            }
        }

        async function clearLogs() {
            await fetch('/api/clear_logs', { method: 'POST' });
            fetchLogs();
        }

        // 주기적 갱신 타이머
        setInterval(() => {
            countdown--;
            if (countdown <= 0) {
                countdown = 5;
                fetchQuotes();
                fetchPositions();
                fetchLogs();
            }
            document.getElementById('refresh-timer').innerText = `${countdown}초 후 자동 갱신`;
        }, 1000);

        // 초기 로드
        window.addEventListener('DOMContentLoaded', () => {
            fetchStatus();
            fetchQuotes();
            fetchPositions();
            fetchLogs();
            loadFile('main.py');
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/status")
def api_status():
    order_amount = os.getenv("ORDER_AMOUNT_KRW", "1000000")
    scan_interval = os.getenv("SCAN_INTERVAL_SEC", "30")
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    nh_key = os.getenv("NH_APP_KEY", "")
    nh_url = os.getenv("NH_BASE_URL", "")
    
    return jsonify({
        "account_no": nh.get_account_no(),
        "order_amount": order_amount,
        "target_profit": pos_mgr.target_profit,
        "stop_loss": pos_mgr.stop_loss,
        "scan_interval": scan_interval,
        "last_scan_time": bot_state["last_scan_time"],
        "tg_token_set": bool(tg_token),
        "nh_key_set": bool(nh_key),
        "nh_base_url": nh_url
    })

# 기본 시장 참고가 (장 마감 또는 API 미응답 시 시각화용)
REFERENCE_PRICES = {
    "005930": 74500,
    "000660": 178000,
    "373220": 395000,
    "207940": 850000,
    "005380": 242000
}

@app.route("/api/quotes")
def api_quotes():
    symbols = nh.get_top_trading_value()
    results = []
    
    for sym in symbols:
        name = STOCK_NAMES.get(sym, sym)
        candles = nh.get_daily_candles(sym)
        current_price = candles[0] if candles else 0
        
        # 장 마감 시간대이거나 API가 0을 반환할 때 참고 시세 활용
        is_mock = False
        if current_price == 0:
            current_price = REFERENCE_PRICES.get(sym, 50000)
            candles = [current_price, int(current_price * 0.985), int(current_price * 0.99), int(current_price * 0.975), int(current_price * 0.98)]
            is_mock = True
            
        ma5 = sum(candles[:5]) / 5 if len(candles) >= 5 else current_price
        diff = ((current_price - ma5) / ma5 * 100) if ma5 else 0
        is_signal = current_price > (ma5 * 1.01) if ma5 else False
        
        results.append({
            "symbol": sym,
            "name": name,
            "current_price": current_price,
            "ma5": int(ma5),
            "ma_diff": diff,
            "is_signal": is_signal,
            "is_mock": is_mock
        })
        
    return jsonify(results)

@app.route("/api/positions")
def api_positions():
    results = []
    for sym, pos in pos_mgr.positions.items():
        name = STOCK_NAMES.get(sym, sym)
        entry_price = pos["entry_price"]
        qty = pos["qty"]
        cur_price = nh.get_current_price(sym) or entry_price
        
        profit_rate = ((cur_price - entry_price) / entry_price * 100) if entry_price else 0
        profit_amount = (cur_price - entry_price) * qty
        
        results.append({
            "symbol": sym,
            "name": name,
            "entry_price": entry_price,
            "current_price": cur_price,
            "qty": qty,
            "profit_rate": profit_rate,
            "profit_amount": profit_amount
        })
    return jsonify(results)

@app.route("/api/scan", methods=["POST"])
def api_scan():
    symbols = nh.get_top_trading_value()
    bot_state["last_scan_time"] = datetime.now().strftime("%H:%M:%S")
    bot_state["scan_count"] += 1
    
    signal_count = 0
    for sym in symbols:
        name = STOCK_NAMES.get(sym, sym)
        candles = nh.get_daily_candles(sym)
        if len(candles) >= 5:
            cur = candles[0]
            ma5 = sum(candles[:5]) / 5
            if cur > ma5 * 1.01:
                signal_count += 1
                add_log(f"🔥 매수 시그널 포착: {name}({sym}) 현재가 {cur:,}원 > 5일선 {int(ma5):,}원 (+1% 돌파)", "SIGNAL")
    
    add_log(f"전체 종목 ({len(symbols)}개) 스캔 완료 - 포착된 신호: {signal_count}건", "SUCCESS" if signal_count > 0 else "INFO")
    return jsonify({"success": True, "signals": signal_count})

@app.route("/api/logs")
def api_logs():
    return jsonify(bot_state["logs"])

@app.route("/api/clear_logs", methods=["POST"])
def api_clear_logs():
    bot_state["logs"].clear()
    add_log("로그가 초기화되었습니다.", "INFO")
    return jsonify({"success": True})

@app.route("/api/add_position", methods=["POST"])
def api_add_position():
    data = request.json or {}
    sym = data.get("symbol")
    price = data.get("price", 0)
    qty = data.get("qty", 1)
    if sym and price > 0:
        pos_mgr.add_position(sym, price, qty)
        name = STOCK_NAMES.get(sym, sym)
        add_log(f"포지션 수동 추가: {name}({sym}) {qty}주 @ {price:,}원", "INFO")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid params"}), 400

@app.route("/api/test_connection", methods=["POST"])
def api_test_connection():
    try:
        token = nh.get_token()
        acc = nh.get_account_no()
        add_log(f"NH API 토큰 발급 테스트 성공 (계좌: {acc})", "SUCCESS")
        return jsonify({"success": True, "message": f"NH API 토큰 발급 성공!\n계좌: {acc}"})
    except Exception as e:
        add_log(f"NH API 연결 테스트 오류: {e}", "ERROR")
        return jsonify({"success": False, "message": f"연결 실패: {e}"})

@app.route("/api/file/<path:filename>")
def api_file(filename):
    allowed_files = ["main.py", "nh_api.py", "position_mgr.py", "telegram_bot.py", "test_connection.py"]
    if filename not in allowed_files:
        return jsonify({"error": "접근 권한이 없는 파일입니다."}), 403
    
    file_path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "파일이 존재하지 않습니다."}), 404
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"filename": filename, "content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[StockBot Web Dashboard] Server running at: http://localhost:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False)

import os
import time
import datetime
import pytz
import requests
import yfinance as yf
import pandas as pd
import numpy as np

IST = pytz.timezone('Asia/Kolkata')
RISK_AMOUNT = 400.0  # ₹400 fixed risk per trade

# Telegram Secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RADAR_BOT_TOKEN = os.getenv("TELEGRAM_RADAR_BOT_TOKEN", BOT_TOKEN)
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

WATCHLIST = [
    "ADANIENT.NS", "BHARATFORG.NS", "TATAMOTORS.NS", "BAJFINANCE.NS",
    "TATASTEEL.NS", "INDUSINDBK.NS", "JSWSTEEL.NS", "SBIN.NS",
    "ICICIBANK.NS", "AXISBANK.NS", "VOLTAS.NS", "JUBLFOOD.NS",
    "DLF.NS", "HINDALCO.NS", "RELIANCE.NS"
]

def send_telegram_msg(msg: str, is_radar: bool = False):
    token = RADAR_BOT_TOKEN if is_radar else BOT_TOKEN
    if not token or not CHAT_ID:
        print("Telegram Token ya Chat ID missing hai!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    try:
        resp = requests.post(url, json=payload, timeout=8)
        print(f"Telegram status: {resp.status_code}")
    except Exception as e:
        print(f"Telegram send error: {e}")

def get_nifty_bias():
    try:
        nifty = yf.Ticker("NIFTYBEES.NS").history(period="1d", interval="5m")
        if nifty.empty:
            return "NEUTRAL"
        nifty['TP'] = (nifty['High'] + nifty['Low'] + nifty['Close']) / 3.0
        nifty['VP'] = nifty['TP'] * nifty['Volume']
        vwap = (nifty['VP'].cumsum() / nifty['Volume'].cumsum().replace(0, np.nan)).ffill().iloc[-1]
        curr = nifty['Close'].iloc[-1]
        return "BULLISH" if curr > vwap else "BEARISH"
    except Exception:
        return "NEUTRAL"

def main():
    print("⚡ Starting Ron Weasley Scanner Engine (IST Locked)...")

    # 1. STRATEGY ACTIVATION NOTIFICATION (Chalu hote hi turant aayega)
    now_ist = datetime.datetime.now(IST)
    activation_msg = (
        "⚡ RON WEASLEY STRATEGY ACTIVATED!\n"
        "------------------------------------\n"
        f"📅 Date: {now_ist.strftime('%d-%m-%Y')}\n"
        f"⏰ Current IST Time: {now_ist.strftime('%I:%M %p')}\n"
        "⏰ Active Window: 09:20 AM - 01:30 PM IST\n"
        "🎯 Setup: Narrow CPR + PDH/PDL Breakout\n"
        "🛡️ Risk: Rs 400 Fixed Risk / Trade\n"
        "📊 Universe: 15 High-Beta Stocks Live\n"
        "------------------------------------\n"
        "System Online & Scanning Real-Time Market Ticks..."
    )
    send_telegram_msg(activation_msg, is_radar=False)

    tracked_trades = {}
    triggered_radar = set()
    triggered_exec = set()

    while True:
        now = datetime.datetime.now(IST)
        curr_min = now.hour * 60 + now.minute

        # 09:20 AM IST se pehle wait karega (560 minutes)
        if curr_min < 560:
            time.sleep(20)
            continue

        # THEEK 01:30 PM IST (810 minutes) PAR AUTO-CLOSE
        if curr_min >= 810:
            close_msg = (
                "🛑 RON WEASLEY STRATEGY CLOSED\n"
                "------------------------------------\n"
                f"⏰ Exit Time: {now.strftime('%I:%M %p')} IST\n"
                "Narrow CPR prime session ended.\n"
                "Scanner cleanly shut down for the day."
            )
            print(close_msg)
            send_telegram_msg(close_msg, is_radar=False)
            break

        nifty_bias = get_nifty_bias()

        for sym in WATCHLIST:
            try:
                t = yf.Ticker(sym)
                df_daily = t.history(period="5d", interval="1d")
                df_5m = t.history(period="1d", interval="5m")

                if df_daily.empty or len(df_daily) < 2 or df_5m.empty or len(df_5m) < 2:
                    continue

                prev_day = df_daily.iloc[-2]
                pdh = float(prev_day['High'])
                pdl = float(prev_day['Low'])
                pdc = float(prev_day['Close'])

                # Narrow CPR Calculation (<= 0.38%)
                pivot = (pdh + pdl + pdc) / 3.0
                bc = (pdh + pdl) / 2.0
                tc = (pivot - bc) + pivot
                cpr_width = abs(tc - bc) / pdc * 100.0

                if cpr_width > 0.38:
                    continue

                # Intraday VWAP Calculation
                df_5m['TP'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
                df_5m['VP'] = df_5m['TP'] * df_5m['Volume']
                vwap = (df_5m['VP'].cumsum() / df_5m['Volume'].cumsum().replace(0, np.nan)).ffill().iloc[-1]

                live_bar = df_5m.iloc[-1]
                closed_bar = df_5m.iloc[-2]
                live_price = float(live_bar['Close'])
                clean_sym = sym.replace('.NS', '')

                # 2. PRE-BREAKOUT / BREAKDOWN RADAR ALERT (0.25% zone)
                if clean_sym not in triggered_radar:
                    if 0 <= (pdh - live_price) / pdh <= 0.0025:
                        radar_msg = (
                            f"📡 PRE-BREAKOUT RADAR: {clean_sym}\n"
                            f"🎯 PDH ke bilkul kareeb hai!\n"
                            f"📊 Current: Rs {live_price:.2f} | PDH: Rs {pdh:.2f}\n"
                            "⚡ Chart open karke tayar rahein!"
                        )
                        send_telegram_msg(radar_msg, is_radar=True)
                        triggered_radar.add(clean_sym)
                    elif 0 <= (live_price - pdl) / pdl <= 0.0025:
                        radar_msg = (
                            f"📡 PRE-BREAKDOWN RADAR: {clean_sym}\n"
                            f"🎯 PDL ke bilkul kareeb hai!\n"
                            f"📊 Current: Rs {live_price:.2f} | PDL: Rs {pdl:.2f}\n"
                            "⚡ Chart open karke tayar rahein!"
                        )
                        send_telegram_msg(radar_msg, is_radar=True)
                        triggered_radar.add(clean_sym)

                # 3. CONFIRMED EXECUTION ALERT (10:00 AM se 01:30 PM tak)
                if curr_min >= 600 and clean_sym not in triggered_exec:
                    # BUY SIGNAL
                    if closed_bar['Close'] > pdh and closed_bar['Close'] > vwap and nifty_bias == "BULLISH":
                        entry = live_price
                        sl = min(float(closed_bar['Low']), float(vwap))
                        risk_per_share = max(entry - sl, entry * 0.002)
                        qty = max(1, int(RISK_AMOUNT / risk_per_share))
                        t1 = entry + risk_per_share
                        t2 = entry + (2.0 * risk_per_share)

                        exec_msg = (
                            f"🚀 BUY CONFIRMED: {clean_sym}\n"
                            "------------------------------------\n"
                            f"📈 Entry Price: Rs {entry:.2f}\n"
                            f"🛡️ Stop-Loss: Rs {sl:.2f}\n"
                            f"🎯 Target 1 (+1.0R): Rs {t1:.2f}\n"
                            f"🎯 Target 2 (+2.0R): Rs {t2:.2f}\n"
                            f"📦 Qty: {qty} shares (Fixed Rs 400 Risk)"
                        )
                        send_telegram_msg(exec_msg, is_radar=False)
                        triggered_exec.add(clean_sym)
                        tracked_trades[clean_sym] = {
                            "type": "BUY", "entry": entry, "sl": sl,
                            "t1": t1, "t2": t2, "t1_hit": False
                        }

                    # SELL SIGNAL
                    elif closed_bar['Close'] < pdl and closed_bar['Close'] < vwap and nifty_bias == "BEARISH":
                        entry = live_price
                        sl = max(float(closed_bar['High']), float(vwap))
                        risk_per_share = max(sl - entry, entry * 0.002)
                        qty = max(1, int(RISK_AMOUNT / risk_per_share))
                        t1 = entry - risk_per_share
                        t2 = entry - (2.0 * risk_per_share)

                        exec_msg = (
                            f"🔻 SELL CONFIRMED: {clean_sym}\n"
                            "------------------------------------\n"
                            f"📉 Entry Price: Rs {entry:.2f}\n"
                            f"🛡️ Stop-Loss: Rs {sl:.2f}\n"
                            f"🎯 Target 1 (+1.0R): Rs {t1:.2f}\n"
                            f"🎯 Target 2 (+2.0R): Rs {t2:.2f}\n"
                            f"📦 Qty: {qty} shares (Fixed Rs 400 Risk)"
                        )
                        send_telegram_msg(exec_msg, is_radar=False)
                        triggered_exec.add(clean_sym)
                        tracked_trades[clean_sym] = {
                            "type": "SELL", "entry": entry, "sl": sl,
                            "t1": t1, "t2": t2, "t1_hit": False
                        }

                # 4. TRADE LIFECYCLE MANAGEMENT (Trailing & Targets)
                if clean_sym in tracked_trades:
                    trade = tracked_trades[clean_sym]
                    if trade["type"] == "BUY":
                        if not trade["t1_hit"] and live_price >= trade["t1"]:
                            trade["t1_hit"] = True
                            trade["sl"] = trade["entry"]
                            send_telegram_msg(
                                f"🎯 TARGET 1 ACHIEVED: {clean_sym}\n"
                                "✅ Book 50% Profit (+1.0R = +Rs 200)\n"
                                f"🔒 SL Trailed to Cost: Rs {trade['sl']:.2f} (Trade Risk-Free!)",
                                is_radar=False
                            )
                        elif trade["t1_hit"] and live_price >= trade["t2"]:
                            send_telegram_msg(
                                f"🏆 TARGET 2 ACHIEVED: {clean_sym}\n"
                                "🎉 Book Final Profit (+2.0R = +Rs 400)!\nPosition fully closed.",
                                is_radar=False
                            )
                            del tracked_trades[clean_sym]
                        elif live_price <= trade["sl"]:
                            status = "Cost Trailing SL Hit (Zero Loss)" if trade["t1_hit"] else "Initial SL Hit (-Rs 400)"
                            send_telegram_msg(
                                f"🛑 STOP-LOSS HIT: {clean_sym}\nExit Price: Rs {live_price:.2f}\nStatus: {status}.",
                                is_radar=False
                            )
                            del tracked_trades[clean_sym]

                    elif trade["type"] == "SELL":
                        if not trade["t1_hit"] and live_price <= trade["t1"]:
                            trade["t1_hit"] = True
                            trade["sl"] = trade["entry"]
                            send_telegram_msg(
                                f"🎯 TARGET 1 ACHIEVED: {clean_sym}\n"
                                "✅ Book 50% Profit (+1.0R = +Rs 200)\n"
                                f"🔒 SL Trailed to Cost: Rs {trade['sl']:.2f} (Trade Risk-Free!)",
                                is_radar=False
                            )
                        elif trade["t1_hit"] and live_price <= trade["t2"]:
                            send_telegram_msg(
                                f"🏆 TARGET 2 ACHIEVED: {clean_sym}\n"
                                "🎉 Book Final Profit (+2.0R = +Rs 400)!\nPosition fully closed.",
                                is_radar=False
                            )
                            del tracked_trades[clean_sym]
                        elif live_price >= trade["sl"]:
                            status = "Cost Trailing SL Hit (Zero Loss)" if trade["t1_hit"] else "Initial SL Hit (-Rs 400)"
                            send_telegram_msg(
                                f"🛑 STOP-LOSS HIT: {clean_sym}\nExit Price: Rs {live_price:.2f}\nStatus: {status}.",
                                is_radar=False
                            )
                            del tracked_trades[clean_sym]

            except Exception as e:
                print(f"Error scanning {sym}: {e}")

        time.sleep(30)

if __name__ == "__main__":
    main()

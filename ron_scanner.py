import os
import time
import datetime
import pytz
import requests
import yfinance as yf
import pandas as pd
import numpy as np

IST = pytz.timezone('Asia/Kolkata')
RISK_AMOUNT = 400.0

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
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_nifty_bias():
    try:
        nifty = yf.Ticker("NIFTYBEES.NS").history(period="1d", interval="5m")
        if nifty.empty:
            return "NEUTRAL"
        nifty['Typical_Price'] = (nifty['High'] + nifty['Low'] + nifty['Close']) / 3.0
        nifty['Vol_Price'] = nifty['Typical_Price'] * nifty['Volume']
        cum_vol_price = nifty['Vol_Price'].cumsum()
        cum_vol = nifty['Volume'].cumsum().replace(0, np.nan)
        vwap = (cum_vol_price / cum_vol).ffill().iloc[-1]
        curr_price = nifty['Close'].iloc[-1]
        return "BULLISH" if curr_price > vwap else "BEARISH"
    except Exception:
        return "NEUTRAL"

def main():
    print("⚡ Starting Ron Weasley Scanner Engine...")
    tracked_trades = {}
    triggered_radar = set()
    triggered_exec = set()

    while True:
        now = datetime.datetime.now(IST)
        curr_min = now.hour * 60 + now.minute

        if curr_min < 555:
            print("Market not open yet. Waiting...")
            time.sleep(60)
            continue
        if curr_min > 915:
            print("Market closed (03:15 PM IST). Exiting cleanly.")
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

                pivot = (pdh + pdl + pdc) / 3.0
                bc = (pdh + pdl) / 2.0
                tc = (pivot - bc) + pivot
                cpr_width = abs(tc - bc) / pdc * 100.0

                if cpr_width > 0.38:
                    continue

                df_5m['Typical_Price'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
                df_5m['Vol_Price'] = df_5m['Typical_Price'] * df_5m['Volume']
                vwap = (df_5m['Vol_Price'].cumsum() / df_5m['Volume'].cumsum().replace(0, np.nan)).ffill().iloc[-1]

                live_bar = df_5m.iloc[-1]
                closed_bar = df_5m.iloc[-2]
                live_price = float(live_bar['Close'])

                # 1. RADAR (0.25% zone)
                if sym not in triggered_radar:
                    if abs(live_price - pdh) / pdh <= 0.0025:
                        msg = f"📡 *PRE-BREAKOUT RADAR: {sym.replace('.NS', '')}*\n🎯 Near PDH: ₹{pdh:.2f} | Current: ₹{live_price:.2f}"
                        send_telegram_msg(msg, is_radar=True)
                        triggered_radar.add(sym)
                    elif abs(live_price - pdl) / pdl <= 0.0025:
                        msg = f"📡 *PRE-BREAKDOWN RADAR: {sym.replace('.NS', '')}*\n🎯 Near PDL: ₹{pdl:.2f} | Current: ₹{live_price:.2f}"
                        send_telegram_msg(msg, is_radar=True)
                        triggered_radar.add(sym)

                # 2. EXECUTION ALERT (10:00 AM onwards)
                if curr_min >= 600 and sym not in triggered_exec:
                    if closed_bar['Close'] > pdh and closed_bar['Close'] > vwap and nifty_bias == "BULLISH":
                        entry = live_price
                        sl = min(float(closed_bar['Low']), float(vwap))
                        risk_per_share = max(entry - sl, entry * 0.002)
                        qty = max(1, int(RISK_AMOUNT / risk_per_share))
                        t1 = entry + risk_per_share
                        t2 = entry + (2.0 * risk_per_share)

                        msg = (f"🚀 *BUY EXECUTION: {sym.replace('.NS', '')}*\n"
                               f"Entry: ₹{entry:.2f}\nStop-Loss: ₹{sl:.2f}\n"
                               f"Target 1: ₹{t1:.2f} | Target 2: ₹{t2:.2f}\nQty: {qty}")
                        send_telegram_msg(msg, is_radar=False)
                        triggered_exec.add(sym)
                        tracked_trades[sym] = {"type": "BUY", "entry": entry, "sl": sl, "t1": t1, "t2": t2, "t1_hit": False}

                    elif closed_bar['Close'] < pdl and closed_bar['Close'] < vwap and nifty_bias == "BEARISH":
                        entry = live_price
                        sl = max(float(closed_bar['High']), float(vwap))
                        risk_per_share = max(sl - entry, entry * 0.002)
                        qty = max(1, int(RISK_AMOUNT / risk_per_share))
                        t1 = entry - risk_per_share
                        t2 = entry - (2.0 * risk_per_share)

                        msg = (f"🔻 *SELL EXECUTION: {sym.replace('.NS', '')}*\n"
                               f"Entry: ₹{entry:.2f}\nStop-Loss: ₹{sl:.2f}\n"
                               f"Target 1: ₹{t1:.2f} | Target 2: ₹{t2:.2f}\nQty: {qty}")
                        send_telegram_msg(msg, is_radar=False)
                        triggered_exec.add(sym)
                        tracked_trades[sym] = {"type": "SELL", "entry": entry, "sl": sl, "t1": t1, "t2": t2, "t1_hit": False}

                # 3. TRADE LIFECYCLE MANAGEMENT
                if sym in tracked_trades:
                    trade = tracked_trades[sym]
                    if trade["type"] == "BUY":
                        if not trade["t1_hit"] and live_price >= trade["t1"]:
                            trade["t1_hit"] = True
                            trade["sl"] = trade["entry"]
                            send_telegram_msg(f"🎯 *TARGET 1 REACHED: {sym.replace('.NS', '')}*\nSL Trailed to ₹{trade['sl']:.2f}", is_radar=False)
                        elif trade["t1_hit"] and live_price >= trade["t2"]:
                            send_telegram_msg(f"🏆 *TARGET 2 REACHED: {sym.replace('.NS', '')}*\nBook Final (+2.0R)!", is_radar=False)
                            del tracked_trades[sym]
                        elif live_price <= trade["sl"]:
                            status = "Cost Trailing SL Hit (0 Loss)" if trade["t1_hit"] else "Initial SL Hit"
                            send_telegram_msg(f"🛑 *STOP-LOSS TRIGGERED: {sym.replace('.NS', '')}*\nStatus: {status}", is_radar=False)
                            del tracked_trades[sym]

                    elif trade["type"] == "SELL":
                        if not trade["t1_hit"] and live_price <= trade["t1"]:
                            trade["t1_hit"] = True
                            trade["sl"] = trade["entry"]
                            send_telegram_msg(f"🎯 *TARGET 1 REACHED: {sym.replace('.NS', '')}*\nSL Trailed to ₹{trade['sl']:.2f}", is_radar=False)
                        elif trade["t1_hit"] and live_price <= trade["t2"]:
                            send_telegram_msg(f"🏆 *TARGET 2 REACHED: {sym.replace('.NS', '')}*\nBook Final (+2.0R)!", is_radar=False)
                            del tracked_trades[sym]
                        elif live_price >= trade["sl"]:
                            status = "Cost Trailing SL Hit (0 Loss)" if trade["t1_hit"] else "Initial SL Hit"
                            send_telegram_msg(f"🛑 *STOP-LOSS TRIGGERED: {sym.replace('.NS', '')}*\nStatus: {status}", is_radar=False)
                            del tracked_trades[sym]

            except Exception as e:
                print(f"Error {sym}: {e}")

        time.sleep(60)

if __name__ == "__main__":
    main()

import os
import time
import datetime
import pytz
import requests
import yfinance as yf
import pandas as pd
import numpy as np

IST = pytz.timezone('Asia/Kolkata')
RISK_AMOUNT = 400.0  # Fixed ₹400 Risk per trade

# Telegram Credentials
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
        print("Telegram tokens/chat_id missing.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Send Error: {e}")

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

        # Market timing checks
        if curr_min < 555: # Before 09:15 AM
            print("Market not open yet. Waiting...")
            time.sleep(60)
            continue
        if curr_min > 915: # After 03:15 PM
            print("Market closed. Exiting.")
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

                # Narrow CPR Calculation
                pivot = (pdh + pdl + pdc) / 3.0
                bc = (pdh + pdl) / 2.0
                tc = (pivot - bc) + pivot
                cpr_width = abs(tc - bc) / pdc * 100.0

                if cpr_width > 0.38:
                    continue

                # Intraday VWAP
                df_5m['Typical_Price'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
                df_5m['Vol_Price'] = df_5m['Typical_Price'] * df_5m['Volume']
                vwap = (df_5m['Vol_Price'].cumsum() / df_5m['Volume'].cumsum().replace(0, np.nan)).ffill().iloc[-1]

                live_bar = df_5m.iloc[-1]
                closed_bar = df_5m.iloc[-2]
                live_price = float


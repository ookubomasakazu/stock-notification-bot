import yfinance as yf
import pandas as pd
import ta
import requests
import os
from datetime import datetime

TEST_MODE = True

# ==========================
# 設定
# ==========================

WATCHLIST = ["AAPL"]
""" WATCHLIST = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "TSLA"
]
"""

PERIOD = "2y"
INTERVAL = "1d"

# ==========================
# 株価取得
# ==========================

def get_price(symbol):
    df = yf.download(symbol, period=PERIOD, interval=INTERVAL, progress=False)

    # MultiIndexを潰す
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    assert not isinstance(df.columns, pd.MultiIndex)

    if df.empty:
        return None

    # CloseがDataFrameになっている場合対策
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()

    df["Close"] = close

    return df


# ==========================
# テクニカル指標追加
# ==========================

def add_indicators(df):

    # Closeを完全に1次元Seriesへ変換
    close = df["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close = pd.Series(close.values.flatten(), index=close.index)

    # RSI
    df["RSI"] = ta.momentum.RSIIndicator(close, window=14).rsi()

    # MACD
    macd = ta.trend.MACD(close)
    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()

    # SMA
    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()

    return df


# ==========================
# シグナル判定
# ==========================

def check_signals(df):

    print(df.columns)

    if len(df) < 200:
        return None, None

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # 明示的にfloatへ変換
    rsi_latest = float(latest["RSI"])
    rsi_prev = float(prev["RSI"])

    macd_latest = float(latest["MACD"])
    macd_prev = float(prev["MACD"])

    signal_latest = float(latest["MACD_SIGNAL"])
    signal_prev = float(prev["MACD_SIGNAL"])

    sma50_latest = float(latest["SMA50"])
    sma50_prev = float(prev["SMA50"])

    sma200_latest = float(latest["SMA200"])
    sma200_prev = float(prev["SMA200"])

    gc_reason = []
    dc_reason = []

    # RSI
    if rsi_latest < 30:
        gc_reason.append("RSI")

    if rsi_latest > 70:
        dc_reason.append("RSI")

    # MACDクロス
    if macd_prev < signal_prev and macd_latest > signal_latest:
        gc_reason.append("MACD")

    if macd_prev > signal_prev and macd_latest < signal_latest:
        dc_reason.append("MACD")

    # SMAクロス
    if sma50_prev < sma200_prev and sma50_latest > sma200_latest:
        gc_reason.append("SMA")

    if sma50_prev > sma200_prev and sma50_latest < sma200_latest:
        dc_reason.append("SMA")

    gc = " + ".join(gc_reason) if gc_reason else None
    dc = " + ".join(dc_reason) if dc_reason else None

    return gc, dc


# ==========================
# LINE本文生成
# ==========================

def format_line_body(gc_list, dc_list):

    today = datetime.now().strftime("%Y-%m-%d")

    body = f"📈 株式シグナル通知（{today}）\n\n"

    all_signals = gc_list + dc_list

    if all_signals:
        body += "本日の推奨シグナル発生銘柄：\n"
        body += ", ".join([s["symbol"] for s in all_signals])
    else:
        body += "本日の推奨シグナル発生銘柄：ありません"

    body += "\n\n【GC詳細】\n"
    if gc_list:
        for s in gc_list:
            body += f'{s["symbol"]}：{s["reason"]}\n'
    else:
        body += "ありません\n"

    body += "\n【DC詳細】\n"
    if dc_list:
        for s in dc_list:
            body += f'{s["symbol"]}：{s["reason"]}\n'
    else:
        body += "ありません\n"

    return body


# ==========================
# LINE送信（1対1 push）
# ==========================

def send_line_message(message):

    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")

    # ローカル実行でトークン未設定なら送信しない
    if not token or not user_id:
        print("LINEトークン未設定のため送信スキップ")
        print(message)
        return

    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    data = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    print("LINE status:", response.status_code)
    print("LINE response:", response.text)


# ==========================
# メイン処理
# ==========================

def main():

    gc_list = []
    dc_list = []

    if TEST_MODE:
        CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
        USER_ID = os.environ["USER_ID"]

        # import requests

        url = "https://api.line.me/v2/bot/message/push"

        headers = {
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        data = {
            "to": USER_ID,
            "messages": [
                {
                    "type": "text",
                    "text": "株通知テスト"
                }
            ]
        }

        requests.post(url, headers=headers, json=data)

    for symbol in WATCHLIST:

        print(f"Processing {symbol}")

        df = get_price(symbol)

        if df is None:
            continue

        df = add_indicators(df)
        
        df = df.dropna()
        print(df.tail(2)[["RSI","MACD","MACD_SIGNAL","SMA50","SMA200"]])

        gc, dc = check_signals(df)

        if TEST_MODE:
            print("🧪 TEST MODE: 強制シグナルON")
            gc = True
            dc = False

        if gc:
            gc_list.append({
                "symbol": symbol,
                "reason": gc
            })

        if dc:
            dc_list.append({
                "symbol": symbol,
                "reason": dc
            })

    message = format_line_body(gc_list, dc_list)

    # シグナル0でも必ず通知
    send_line_message(message)


if __name__ == "__main__":
    main()
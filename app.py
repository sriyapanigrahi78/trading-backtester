import streamlit as st
import pandas as pd
import pandas_ta as ta
import requests
import pyotp
import io
from datetime import datetime, time

st.set_page_config(layout="wide", page_title="Algorithmic Quantum Hub")

# ------------------------------------------------------------------
# 1. CORE STRATEGY ENGINE
# ------------------------------------------------------------------
def execute_5ema_short_strategy(df, asset_type="STOCK"):
    if df.empty:
        return pd.DataFrame()
        
    df['ema5'] = df.groupby('symbol')['close'].transform(lambda x: ta.ema(x, length=5))
    df['date_str'] = df['datetime'].dt.date
    df['time_str'] = df['datetime'].dt.time
    
    df['is_alert'] = (df['low'] > df['ema5']) & (df['close'] > df['ema5'])
    df['prev_is_alert'] = df.groupby('symbol')['is_alert'].shift(1)
    df['prev_high'] = df.groupby('symbol')['high'].shift(1)
    df['prev_low'] = df.groupby('symbol')['low'].shift(1)
    
    trade_logs = []
    grouped = df.sort_values(by=['date_str', 'time_str']).groupby('date_str')
    
    for date, day_data in grouped:
        active_assets = set()
        asset_trade_counts = {}
        open_positions = {}
        
        for idx, row in day_data.iterrows():
            sym = row['symbol']
            curr_time = row['time_str']
            
            if asset_type == "STOCK" and curr_time >= time(15, 0):
                if sym in open_positions:
                    p = open_positions[sym]
                    p['exit_time'] = curr_time
                    p['exit_price'] = row['close']
                    p['status'] = 'Squared Off @ 3PM'
                    p['pnl'] = p['quantity'] * (p['entry_price'] - row['close'])
                    trade_logs.append(p)
                    del open_positions[sym]
                continue
                
            if sym in open_positions:
                p = open_positions[sym]
                if row['high'] >= p['sl_price']:
                    p['exit_time'] = curr_time
                    p['exit_price'] = p['sl_price']
                    p['status'] = 'SL Hit'
                    p['pnl'] = -5000
                    trade_logs.append(p)
                    del open_positions[sym]
                elif row['low'] <= p['target_price']:
                    p['exit_time'] = curr_time
                    p['exit_price'] = p['target_price']
                    p['status'] = 'Target Achieved'
                    p['pnl'] = 15000
                    trade_logs.append(p)
                    del open_positions[sym]
                continue
                
            if row['prev_is_alert'] and row['low'] < row['prev_low']:
                cnt = asset_trade_counts.get(sym, 0)
                if cnt < 2 and (sym in active_assets or len(active_assets) < 5):
                    active_assets.add(sym)
                    asset_trade_counts[sym] = cnt + 1
                    sl_pts = row['prev_high'] - row['prev_low']
                    if sl_pts <= 0: continue
                    
                    qty = int(5000 / sl_pts)
                    open_positions[sym] = {
                        "DATE": str(date), "SYMBOL": sym, 
                        "entry_time": str(curr_time), "entry_price": row['prev_low'],
                        "sl_price": row['prev_high'], "target_price": row['prev_low'] - (3 * sl_pts),
                        "quantity": qty, "pnl": 0
                    }
                    
    return pd.DataFrame(trade_logs) if trade_logs else pd.DataFrame()

# ------------------------------------------------------------------
# 2. RAW NETWORK DATA FETCHERS (NO BROKEN SDKs)
# ------------------------------------------------------------------
def fetch_crypto_btc_data(start_date, end_date):
    start_unix = int(pd.to_datetime(start_date).timestamp()) * 1000
    end_unix = int(pd.to_datetime(end_date).timestamp()) * 1000
    
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime={start_unix}&endTime={end_unix}&limit=1000"
    try:
        res = requests.get(url).json()
        df = pd.DataFrame(res, columns=['time', 'open', 'high', 'low', 'close', 'v', 'c_time', 'q', 'n', 't', 'b', 'i'])
        df['datetime'] = pd.to_datetime(df['time'], unit='ms')
        df['symbol'] = "BTC-USD"
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        return df[['datetime', 'symbol', 'open', 'high', 'low', 'close']]
    except:
        return pd.DataFrame()

def fetch_fyers_native(symbol, start_d, end_d, access_token, app_id):
    url = "https://api-t1.fyers.in/data/history"
    headers = {"Authorization": f"{app_id}:{access_token}"}
    params = {
        "symbol": f"NSE:{symbol}-EQ", "resolution": "5", "date_format": "1",
        "range_from": str(start_d), "range_to": str(end_d), "cont_flag": "1"
    }
    try:
        res = requests.get(url, headers=headers, params=params).json()
        if res.get("s") == "ok":
            df = pd.DataFrame(res.get("candles", []), columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['datetime'], unit='s')
            df['symbol'] = symbol
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# ------------------------------------------------------------------
# 3. INTERFACE
# ------------------------------------------------------------------
st.title("⚡ Infinite Loop Quantitative Strategy Terminal")

market_mode = st.radio("Choose Target Asset Class", ["Indian Stocks (Fyers API)", "Bitcoin Crypto (Instant Free Sourcing)"])

st.sidebar.title("🔐 Authentication Management")
client_id = st.sidebar.text_input("Fyers App ID", type="password")
access_token = st.sidebar.text_input("Daily Access Token", type="password")

c1, c2 = st.columns(2)
start_date = c1.date_input("Backtest Timeline Start", value=pd.to_datetime("2026-01-01"))
end_date = c2.date_input("Backtest Timeline Close", value=pd.to_datetime("2026-07-01"))

if market_mode == "Indian Stocks (Fyers API)":
    stocks_input = st.text_input("Target Stock Tickers:", "SBIN,TATAMOTORS")
    target_list = [s.strip().upper() for s in stocks_input.split(",") if s.strip()]
else:
    st.markdown("🎯 **Target Asset:** Bitcoin (`BTC-USDT`) via free data stream pipelines.")
    target_list = ["BTC-USD"]

if st.button("🚀 Fire Algorithmic Backtest Loop"):
    master_dataset = pd.DataFrame()
    
    if market_mode == "Bitcoin Crypto (Instant Free Sourcing)":
        with st.spinner("Streaming Bitcoin market intervals down to engine..."):
            master_dataset = fetch_crypto_btc_data(start_date, end_date)
    else:
        if not (client_id and access_token):
            st.error("Please enter your App ID and Access Token in the sidebar!")
        else:
            with st.spinner("Fetching data from Fyers server..."):
                all_dfs = [fetch_fyers_native(sym, start_date, end_date, access_token, client_id) for sym in target_list]
                all_dfs = [d for d in all_dfs if not d.empty]
                if all_dfs:
                    master_dataset = pd.concat(all_dfs, ignore_index=True)

    if not master_dataset.empty:
        st.success(f"Successfully loaded {len(master_dataset)} raw data candles!")
        final_report = execute_5ema_short_strategy(master_dataset, asset_type="STOCK" if market_mode == "Indian Stocks (Fyers API)" else "CRYPTO")
        
        if not final_report.empty:
            st.subheader("📈 Backtest Results Log Sheet")
            st.dataframe(final_report.style.applymap(lambda v: 'background-color: #2ecc71; color: white;' if v > 0 else 'background-color: #e74c3c; color: white;', subset=['pnl']), use_container_width=True)
            
            csv_buf = io.BytesIO()
            final_report.to_csv(csv_buf, index=False)
            st.download_button("📥 Download Result CSV", data=csv_buf.getvalue(), file_name="Performance_Report.csv", mime="text/csv")
        else:
            st.warning("Data parsed successfully, but no setups hit your entry criteria.")
    else:
        st.error("Engine Stream Failure: No data could be downloaded for calculation.")

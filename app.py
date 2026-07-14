import streamlit as st
import pandas as pd
import requests
import io
import time as time_lib
from datetime import datetime, time, timedelta

st.set_page_config(layout="wide", page_title="Algorithmic Strategy Hub")

# ------------------------------------------------------------------
# 1. CORE STRATEGY VAULT (Modular Framework for Multiple Setups)
# ------------------------------------------------------------------

def execute_5ema_short_strategy(df, asset_type="STOCK"):
    """
    Setup 1: 5EMA Short Setup Engine
    Strictly follows Delta Exchange / Fyers asset-class nuances.
    """
    if df.empty:
        return pd.DataFrame()
        
    # Standardize incoming column layout formats safely
    df.columns = [c.lower().strip() for c in df.columns]
    
    # NATIVE PANDAS EMA Calculation (Bypasses external library errors)
    df['ema5'] = df.groupby('symbol')['close'].transform(lambda x: x.ewm(span=5, adjust=False).mean())
    
    # Isolate string layouts for tradebook generation matching target template
    df['date_str'] = df['datetime_ist'].dt.strftime('%Y-%m-%d')
    df['time_str'] = df['datetime_ist'].dt.strftime('%H:%M:%S')
    
    df['is_alert'] = (df['low'] > df['ema5']) & (df['close'] > df['ema5'])
    df['prev_is_alert'] = df.groupby('symbol')['is_alert'].shift(1)
    df['prev_high'] = df.groupby('symbol')['high'].shift(1)
    df['prev_low'] = df.groupby('symbol')['low'].shift(1)
    
    trade_logs = []
    grouped = df.sort_values(by='datetime_ist').groupby('date_str')
    
    for date, day_data in grouped:
        active_assets = set()
        asset_trade_counts = {}
        open_positions = {}
        
        for idx, row in day_data.iterrows():
            sym = row['symbol']
            curr_time_str = row['time_str']
            curr_time_parsed = datetime.strptime(curr_time_str, '%H:%M:%S').time()
            
            # Intraday Square-off at 3 PM (Only applied to standard Stock Markets)
            if asset_type == "STOCK" and curr_time_parsed >= time(15, 0):
                if sym in open_positions:
                    p = open_positions[sym]
                    p['exit_time'] = curr_time_str
                    p['exit_price'] = row['close']
                    p['status'] = 'OPEN_EOD'
                    p['points'] = p['entry_price'] - row['close']
                    trade_logs.append(p)
                    del open_positions[sym]
                continue
                
            # Manage active positions tracking
            if sym in open_positions:
                p = open_positions[sym]
                if row['high'] >= p['sl_price']:
                    p['exit_time'] = curr_time_str
                    p['exit_price'] = p['sl_price']
                    p['status'] = 'SL'
                    p['points'] = -abs(p['entry_price'] - p['sl_price'])
                    trade_logs.append(p)
                    del open_positions[sym]
                elif row['low'] <= p['target_price']:
                    p['exit_time'] = curr_time_str
                    p['exit_price'] = p['target_price']
                    p['status'] = 'TARGET'
                    p['points'] = abs(p['entry_price'] - p['target_price'])
                    trade_logs.append(p)
                    del open_positions[sym]
                continue
                
            # Strategy entry logic evaluation
            if row['prev_is_alert'] and row['low'] < row['prev_low']:
                cnt = asset_trade_counts.get(sym, 0)
                if cnt < 2 and (sym in active_assets or len(active_assets) < 5):
                    active_assets.add(sym)
                    asset_trade_counts[sym] = cnt + 1
                    sl_pts = row['prev_high'] - row['prev_low']
                    if sl_pts <= 0: continue
                    
                    open_positions[sym] = {
                        "DATE": date, 
                        "SYMBOL": sym, 
                        "ENTRY TIME (IST)": curr_time_str, 
                        "entry_price": row['prev_low'],
                        "sl_price": row['prev_high'], 
                        "target_price": row['prev_low'] - (3 * sl_pts),
                        "exit_time": "-",
                        "exit_price": 0.0,
                        "status": "OPEN_EOD",
                        "points": 0.0
                    }
                    
        # Flush remaining intraday nodes
        for sym, p in list(open_positions.items()):
            p['status'] = 'OPEN_EOD'
            p['points'] = 0.0
            trade_logs.append(p)
            
    if not trade_logs:
        return pd.DataFrame()
        
    res_df = pd.DataFrame(trade_logs)
    res_df['ENTRY PRICE'] = res_df['entry_price'].round(2)
    res_df['EXIT PRICE'] = res_df['exit_price'].round(2)
    res_df['RESULT'] = res_df['status']
    res_df['POINTS'] = res_df['points'].round(2)
    res_df['EXIT TIME (IST)'] = res_df['exit_time']
    
    # Matches your provided Excel sheet columns exactly
    order_cols = ["DATE", "SYMBOL", "ENTRY TIME (IST)", "EXIT TIME (IST)", "ENTRY PRICE", "EXIT PRICE", "RESULT", "POINTS"]
    return res_df[order_cols]


def execute_setup_two_strategy(df):
    """
    [💥 RESERVED FOR FUTURE STRATEGY SETUP 2]
    """
    st.info("Strategy Space 2 is currently empty. Ready for your custom logic parameters.")
    return pd.DataFrame()


def execute_setup_three_strategy(df):
    """
    [💥 RESERVED FOR FUTURE STRATEGY SETUP 3]
    """
    st.info("Strategy Space 3 is currently empty. Ready for your custom logic parameters.")
    return pd.DataFrame()


# ------------------------------------------------------------------
# 2. BULLETPROOF NETWORK DATA FETCHERS (NO GEO-BLOCKS)
# ------------------------------------------------------------------
def fetch_crypto_btc_data(start_date, end_date):
    """
    Slices requested windows into incremental 5-day batches to safely retrieve 
    historical intraday data from Yahoo Finance without triggering range rejections.
    """
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    combined_dfs = []
    current_chunk_start = start_dt
    
    while current_chunk_start < end_dt:
        current_chunk_end = min(current_chunk_start + timedelta(days=5), end_dt)
        p1 = int(current_chunk_start.timestamp())
        p2 = int(current_chunk_end.timestamp())
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?period1={p1}&period2={p2}&interval=5m"
        
        try:
            res = requests.get(url, headers=headers, timeout=15).json()
            if 'chart' in res and res['chart']['result'] is not None:
                result_node = res['chart']['result'][0]
                if 'timestamp' in result_node and result_node['timestamp'] is not None:
                    timestamps = result_node['timestamp']
                    ohlc = result_node['indicators']['quote'][0]
                    
                    chunk_df = pd.DataFrame({
                        'time': timestamps,
                        'open': ohlc.get('open'),
                        'high': ohlc.get('high'),
                        'low': ohlc.get('low'),
                        'close': ohlc.get('close')
                    })
                    combined_dfs.append(chunk_df)
        except Exception:
            pass
            
        current_chunk_start = current_chunk_end + timedelta(seconds=1)
        time_lib.sleep(0.2)

    if not combined_dfs:
        return pd.DataFrame()
        
    df = pd.concat(combined_dfs, ignore_index=True)
    df = df.dropna().copy()
    
    df['datetime_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['datetime_ist'] = df['datetime_utc'].dt.tz_convert('Asia/Kolkata')
    df['symbol'] = "BTCUSD"
    
    return df[['datetime_ist', 'symbol', 'open', 'high', 'low', 'close']].drop_duplicates(subset=['datetime_ist'])


def fetch_fyers_native(symbol, start_d, end_d, access_token, app_id):
    url = "https://api-t1.fyers.in/data/history"
    headers = {"Authorization": f"{app_id}:{access_token}"}
    params = {
        "symbol": f"NSE:{symbol}-EQ", "resolution": "5", "date_format": "1",
        "range_from": str(start_d), "range_to": str(end_d), "cont_flag": "1"
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get("s") == "ok":
            df = pd.DataFrame(res.get("candles", []), columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime_utc'] = pd.to_datetime(df['datetime'], unit='s', utc=True)
            df['datetime_ist'] = df['datetime_utc'].dt.tz_convert('Asia/Kolkata')
            df['symbol'] = symbol
            return df[['datetime_ist', 'symbol', 'open', 'high', 'low', 'close']]
        return pd.DataFrame()
    except:
        return pd.DataFrame()


# ------------------------------------------------------------------
# 3. INTERACTIVE DASHBOARD GRAPHICS
# ------------------------------------------------------------------
st.title("⚡ Multi-Setup Quantitative Strategy Hub")
st.markdown("Automated zero-friction backtesting engine for Equities and Cryptocurrencies.")

market_mode = st.radio("Choose Target Asset Class", ["Bitcoin Crypto (Instant Free Sourcing)", "Indian Stocks (Fyers API)"])

st.sidebar.title("🔐 API Credential Gateways")
if market_mode == "Indian Stocks (Fyers API)":
    client_id = st.sidebar.text_input("Fyers App ID", type="password")
    access_token = st.sidebar.text_input("Daily Access Token", type="password")
else:
    st.sidebar.info("🍀 Crypto mode active: Live endpoints bypassed. No keys required.")

strategy_choice = st.selectbox(
    "Select Strategy Code Block", 
    ["Setup 1: 5EMA Short Setup Engine", "Setup 2: [Empty Slot]", "Setup 3: [Empty Slot]"]
)

c1, c2 = st.columns(2)
start_date = c1.date_input("Backtest Timeline Start", value=pd.to_datetime("2025-11-01"))
end_date = c2.date_input("Backtest Timeline Close", value=pd.to_datetime("2025-11-07"))

if market_mode == "Indian Stocks (Fyers API)":
    stocks_input = st.text_input("Target Stock Tickers:", "SBIN,TATAMOTORS")
    target_list = [s.strip().upper() for s in stocks_input.split(",") if s.strip()]
else:
    st.markdown("🎯 **Target Asset:** Bitcoin (`BTCUSD`) tracked automatically.")
    target_list = ["BTC-USD"]

if st.button("🚀 Fire Algorithmic Backtest Loop"):
    master_dataset = pd.DataFrame()
    
    if market_mode == "Bitcoin Crypto (Instant Free Sourcing)":
        with st.spinner("Streaming Bitcoin market intervals down to engine..."):
            master_dataset = fetch_crypto_btc_data(start_date, end_date)
    else:
        if not (client_id and access_token):
            st.error("Please fill in your App ID and Access Token inside the sidebar!")
        else:
            with st.spinner("Fetching historical candles from Fyers..."):
                all_dfs = [fetch_fyers_native(sym, start_date, end_date, access_token, client_id) for sym in target_list]
                all_dfs = [d for d in all_dfs if not d.empty]
                if all_dfs:
                    master_dataset = pd.concat(all_dfs, ignore_index=True)

    if not master_dataset.empty:
        st.success(f"Successfully loaded {len(master_dataset)} chronological data candles!")
        
        if strategy_choice == "Setup 1: 5EMA Short Setup Engine":
            asset_env = "STOCK" if market_mode == "Indian Stocks (Fyers API)" else "CRYPTO"
            final_report = execute_5ema_short_strategy(master_dataset, asset_type=asset_env)
        elif strategy_choice == "Setup 2: [Empty Slot]":
            final_report = execute_setup_two_strategy(master_dataset)
        else:
            final_report = execute_setup_three_strategy(master_dataset)
            
        if not final_report.empty:
            st.subheader("📋 Formatted Strategy Trade Log Sheet")
            
            # Formats row backgrounds cleanly to match your visual design specification
            def style_rows(row):
                if row['RESULT'] == 'TARGET':
                    return ['background-color: #2ecc71; color: white; font-weight: bold;'] * len(row)
                elif row['RESULT'] == 'SL':
                    return ['background-color: #e74c3c; color: white; font-weight: bold;'] * len(row)
                return [''] * len(row)
                
            st.dataframe(final_report.style.apply(style_rows, axis=1), use_container_width=True)
            
            csv_buf = io.StringIO()
            final_report.to_csv(csv_buf, index=False)
            st.download_button(
                label="📥 Download Formatted Trade Log CSV", 
                data=csv_buf.getvalue(), 
                file_name="BTCUSD_strategy_trade_log.csv", 
                mime="text/csv"
            )
        else:
            st.warning("Data parsed successfully, but no candles triggered your strategy entry logic.")
    else:
        st.error("Engine Data Stream Failure: No historical intervals could be loaded. Verify targets.")

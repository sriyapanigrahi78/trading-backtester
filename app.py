import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime, time

st.set_page_config(layout="wide", page_title="Algorithmic Strategy Hub")

# ------------------------------------------------------------------
# 1. CORE STRATEGY VAULT (Modular Space for Multiple Setups)
# ------------------------------------------------------------------

def execute_5ema_short_strategy(df, asset_type="STOCK"):
    """
    Setup 1: 5EMA Short Setup Engine
    Capped at ₹5,000 risk per trade (or equivalent unit points for Crypto),
    max 2 trades per asset per day, max 5 assets.
    """
    if df.empty:
        return pd.DataFrame()
        
    # Native Pandas EMA Calculation (Zero conflicts with modern systems)
    df['ema5'] = df.groupby('symbol')['close'].transform(lambda x: x.ewm(span=5, adjust=False).mean())
    
    # Extract structural dates/times in Indian Standard Time (IST)
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
            
            # Parse row clock components safely for equity constraints
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
                    
        # Handle open positions remaining at the absolute end of the continuous tracking sequence
        for sym, p in list(open_positions.items()):
            p['status'] = 'OPEN_EOD'
            p['points'] = 0.0
            trade_logs.append(p)
            
    if not trade_logs:
        return pd.DataFrame()
        
    # Standardize data columns to match your exact sheet template
    res_df = pd.DataFrame(trade_logs)
    res_df['ENTRY PRICE'] = res_df['entry_price'].round(2)
    res_df['EXIT PRICE'] = res_df['exit_price'].round(2)
    res_df['RESULT'] = res_df['status']
    res_df['POINTS'] = res_df['points'].round(2)
    res_df['EXIT TIME (IST)'] = res_df['exit_time']
    
    order_cols = ["DATE", "SYMBOL", "ENTRY TIME (IST)", "EXIT TIME (IST)", "ENTRY PRICE", "EXIT PRICE", "RESULT", "POINTS"]
    return res_df[order_cols]


def execute_setup_two_strategy(df):
    """
    [💥 SPACE RESERVED FOR FUTURE STRATEGY SETUP 2]
    """
    st.info("Strategy Space 2 is currently empty. Ready for your future rules!")
    return pd.DataFrame()


def execute_setup_three_strategy(df):
    """
    [💥 SPACE RESERVED FOR FUTURE STRATEGY SETUP 3]
    """
    st.info("Strategy Space 3 is currently empty. Ready for your future rules!")
    return pd.DataFrame()


# ------------------------------------------------------------------
# 2. DATA SOURCE ROUTERS (Fyers Stock Engine vs Free BTC Crypto)
# ------------------------------------------------------------------

def fetch_crypto_btc_data(start_date, end_date):
    """
    Streams historical 5-minute data directly via Binance API, shifted perfectly to IST.
    """
    start_unix = int(pd.to_datetime(start_date).timestamp()) * 1000
    end_unix = int(pd.to_datetime(end_date).timestamp()) * 1000
    
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime={start_unix}&endTime={end_unix}&limit=1000"
    try:
        res = requests.get(url).json()
        df = pd.DataFrame(res, columns=['time', 'open', 'high', 'low', 'close', 'v', 'c_time', 'q', 'n', 't', 'b', 'i'])
        
        # Pull UTC timestamps from the exchange node and convert directly to IST
        df['datetime_utc'] = pd.to_datetime(df['time'], unit='ms', utc=True)
        df['datetime_ist'] = df['datetime_utc'].dt.tz_convert('Asia/Kolkata')
        
        df['symbol'] = "BTCUSD"
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        return df[['datetime_ist', 'symbol', 'open', 'high', 'low', 'close']]
    except:
        return pd.DataFrame()


def fetch_fyers_native(symbol, start_d, end_d, access_token, app_id):
    """
    Fetches stock history straight via Fyers Native API endpoints using clean Requests.
    """
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
            
            # Map Fyers data epoch values directly to matching IST layout
            df['datetime_utc'] = pd.to_datetime(df['datetime'], unit='s', utc=True)
            df['datetime_ist'] = df['datetime_utc'].dt.tz_convert('Asia/Kolkata')
            df['symbol'] = symbol
            return df[['datetime_ist', 'symbol', 'open', 'high', 'low', 'close']]
        return pd.DataFrame()
    except:
        return pd.DataFrame()


# ------------------------------------------------------------------
# 3. INTERACTIVE WEB DASHBOARD RENDERER
# ------------------------------------------------------------------
st.title("⚡ Multi-Setup Quantitative Strategy Hub")
st.markdown("Automated zero-friction backtesting engine for Equities and Cryptocurrencies.")

# Asset router selector
market_mode = st.radio("Choose Target Asset Class", ["Bitcoin Crypto (Instant Free Sourcing)", "Indian Stocks (Fyers API)"])

# Authentication panel for side menu parameters
st.sidebar.title("🔐 API Credential Gateways")
if market_mode == "Indian Stocks (Fyers API)":
    client_id = st.sidebar.text_input("Fyers App ID", type="password")
    access_token = st.sidebar.text_input("Daily Access Token", type="password")
else:
    st.sidebar.info("🍀 Crypto mode active: Live endpoints bypassed. No keys or registration tokens required.")

# Active Strategy Core Router selection
strategy_choice = st.selectbox(
    "Select Strategy Code Block", 
    ["Setup 1: 5EMA Short Setup Engine", "Setup 2: [Empty Configuration Slot]", "Setup 3: [Empty Configuration Slot]"]
)

# Shared universal parameters matrix
c1, c2 = st.columns(2)
start_date = c1.date_input("Backtest Timeline Start", value=pd.to_datetime("2025-11-01"))
end_date = c2.date_input("Backtest Timeline Close", value=pd.to_datetime("2025-11-07"))

if market_mode == "Indian Stocks (Fyers API)":
    stocks_input = st.text_input("Target Stock Tickers (separated by commas):", "SBIN,TATAMOTORS")
    target_list = [s.strip().upper() for s in stocks_input.split(",") if s.strip()]
else:
    st.markdown("🎯 **Target Asset Node:** Bitcoin (`BTCUSD`) tracked automatically.")
    target_list = ["BTC-USD"]

# Trigger Engine
if st.button("🚀 Fire Algorithmic Backtest Loop"):
    master_dataset = pd.DataFrame()
    
    if market_mode == "Bitcoin Crypto (Instant Free Sourcing)":
        with st.spinner("Streaming Bitcoin market intervals down to engine..."):
            master_dataset = fetch_crypto_btc_data(start_date, end_date)
    else:
        if not (client_id and access_token):
            st.error("Please fill in your App ID and Access Token inside the sidebar!")
        else:
            with st.spinner("Fetching historical candles from Fyers servers..."):
                all_dfs = [fetch_fyers_native(sym, start_date, end_date, access_token, client_id) for sym in target_list]
                all_dfs = [d for d in all_dfs if not d.empty]
                if all_dfs:
                    master_dataset = pd.concat(all_dfs, ignore_index=True)

    # Calculate and output formatted structures
    if not master_dataset.empty:
        st.success(f"Successfully loaded {len(master_dataset)} chronological market data rows!")
        
        # Strategy Choice routing matrix execution
        if strategy_choice == "Setup 1: 5EMA Short Setup Engine":
            asset_env = "STOCK" if market_mode == "Indian Stocks (Fyers API)" else "CRYPTO"
            final_report = execute_5ema_short_strategy(master_dataset, asset_type=asset_env)
        elif strategy_choice == "Setup 2: [Empty Configuration Slot]":
            final_report = execute_setup_two_strategy(master_dataset)
        else:
            final_report = execute_setup_three_strategy(master_dataset)
            
        # Display performance logs matrix
        if not final_report.empty:
            st.subheader("📋 Formatted Strategy Trade Log Sheet")
            
            # Dynamic color rendering matching your configuration design rules
            def style_rows(row):
                if row['RESULT'] == 'TARGET':
                    return ['background-color: #2ecc71; color: white; font-weight: bold;'] * len(row)
                elif row['RESULT'] == 'SL':
                    return ['background-color: #e74c3c; color: white; font-weight: bold;'] * len(row)
                return [''] * len(row)
                
            st.dataframe(final_report.style.apply(style_rows, axis=1), use_container_width=True)
            
            # Instant memory serialization buffer for exports
            csv_buf = io.StringIO()
            final_report.to_csv(csv_buf, index=False)
            st.download_button(
                label="📥 Download Formatted Trade Log CSV", 
                data=csv_buf.getvalue(), 
                file_name="BTCUSD_strategy_trade_log.csv", 
                mime="text/csv"
            )
        else:
            st.warning("Data parsed successfully, but no candles triggered your strategy parameters during this range.")
    else:
        st.error("Engine Data Stream Failure: No historical intervals could be loaded. Verify targets.")

import streamlit as st
import pandas as pd
import io
from datetime import datetime, time

st.set_page_config(layout="wide", page_title="Algorithmic Strategy Hub")

# ------------------------------------------------------------------
# 1. CORE STRATEGY ENGINE
# ------------------------------------------------------------------
def execute_5ema_short_strategy(df, asset_type="STOCK"):
    if df.empty:
        return pd.DataFrame()
        
    # Standardize incoming column layout formats safely
    df.columns = [c.lower().strip() for c in df.columns]
    
    # Detect time/date column headers dynamically
    time_col = [c for c in df.columns if 'time' in c or 'date' in c]
    if not time_col:
        st.error("Error: Could not find a Timestamp or Date column in the CSV file.")
        return pd.DataFrame()
    
    # Parse date strings into execution timelines
    df['parsed_datetime'] = pd.to_datetime(df[time_col[0]])
    df['date_str'] = df['parsed_datetime'].dt.strftime('%Y-%m-%d')
    df['time_str'] = df['parsed_datetime'].dt.strftime('%H:%M:%S')
    
    # Deduce target asset column name if present
    sym_col = [c for c in df.columns if 'sym' in c or 'ticker' in c]
    df['clean_symbol'] = df[sym_col[0]].astype(str).str.upper() if sym_col else "ASSET"

    # Calculate 5 EMA
    df['ema5'] = df.groupby('clean_symbol')['close'].transform(lambda x: x.ewm(span=5, adjust=False).mean())
    
    df['is_alert'] = (df['low'] > df['ema5']) & (df['close'] > df['ema5'])
    df['prev_is_alert'] = df.groupby('clean_symbol')['is_alert'].shift(1)
    df['prev_high'] = df.groupby('clean_symbol')['high'].shift(1)
    df['prev_low'] = df.groupby('clean_symbol')['low'].shift(1)
    
    trade_logs = []
    grouped = df.sort_values(by='parsed_datetime').groupby('date_str')
    
    for date, day_data in grouped:
        active_assets = set()
        asset_trade_counts = {}
        open_positions = {}
        
        for idx, row in day_data.iterrows():
            sym = row['clean_symbol']
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
    
    order_cols = ["DATE", "SYMBOL", "ENTRY TIME (IST)", "EXIT TIME (IST)", "ENTRY PRICE", "EXIT PRICE", "RESULT", "POINTS"]
    return res_df[order_cols]

def execute_setup_two_strategy(df):
    st.info("Strategy Space 2 is currently empty.")
    return pd.DataFrame()

def execute_setup_three_strategy(df):
    st.info("Strategy Space 3 is currently empty.")
    return pd.DataFrame()

# ------------------------------------------------------------------
# 2. APP USER INTERFACE
# ------------------------------------------------------------------
st.title("⚡ Multi-Setup Quantitative Strategy Hub")
st.markdown("Upload any historical CSV chart file to generate immediate trade books.")

# Mode select routers
market_mode = st.radio("Choose Strategy Asset Class", ["Cryptocurrency (Continuous 24/7 Engine)", "Indian Stocks (3 PM Square-off Engine)"])

strategy_choice = st.selectbox(
    "Select Strategy Code Block", 
    ["Setup 1: 5EMA Short Setup Engine", "Setup 2: [Empty Configuration Slot]", "Setup 3: [Empty Configuration Slot]"]
)

# File drag box
uploaded_file = st.file_uploader("Upload Historical Data Chart File (CSV Format)", type=["csv"])

if uploaded_file is not None:
    # Read the data instantly into pandas memory structures
    try:
        raw_df = pd.read_csv(uploaded_file)
        st.success(f"Successfully loaded CSV containing {len(raw_df)} candle rows!")
        
        # Verify columns are correct
        required_cols = ['open', 'high', 'low', 'close']
        found_cols = [c.lower().strip() for c in raw_df.columns]
        missing = [col for col in required_cols if col not in found_cols]
        
        if missing:
            st.error(f"Missing required price columns in CSV: {missing}. Ensure your file contains Open, High, Low, and Close.")
        else:
            if st.button("🚀 Fire Algorithmic Backtest Loop"):
                with st.spinner("Processing technical matrix setups..."):
                    
                    if strategy_choice == "Setup 1: 5EMA Short Setup Engine":
                        asset_env = "STOCK" if "Stock" in market_mode else "CRYPTO"
                        final_report = execute_5ema_short_strategy(raw_df, asset_type=asset_env)
                    elif strategy_choice == "Setup 2: [Empty Configuration Slot]":
                        final_report = execute_setup_two_strategy(raw_df)
                    else:
                        final_report = execute_setup_three_strategy(raw_df)

                if not final_report.empty:
                    st.subheader("📋 Formatted Strategy Trade Log Sheet")
                    
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
                        file_name="Strategy_Performance_Log.csv", 
                        mime="text/csv"
                    )
                else:
                    st.warning("Data read perfectly, but no candles triggered your strategy entry logic.")
    except Exception as e:
        st.error(f"Failed to read file: {str(e)}")

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
import io

st.set_page_config(
    page_title="Stock Analytics Suite",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== Custom CSS for Better Appearance =====
st.markdown("""
<style>
    .main > div { padding-top: 2rem; }
    h1 { color: #1f77b4; font-weight: 700; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; padding-left: 20px; padding-right: 20px;
        border-radius: 5px 5px 0 0;
    }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Stock Analytics Suite")
st.markdown("**Comprehensive Analysis Tools for Breakouts, Behaviors & Backtests**")
st.divider()

@st.cache_data(ttl=3600)
def is_breakout_last_13_days(hist):
    if len(hist) < 30:
        return False
    recent_close = hist['Close'].iloc[-1]
    past_high = hist['High'].iloc[-30:-13].max()
    return recent_close > past_high

@st.cache_data(ttl=3600)
def find_breakouts(tickers, suffix):
    all_results = []
    bullish_count = 0
    bearish_count = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, ticker in enumerate(tickers):
        full_ticker = ticker + suffix
        status_text.text(f"Analyzing {full_ticker}... ({idx + 1}/{len(tickers)})")
        try:
            stock = yf.Ticker(full_ticker)
            hist = stock.history(period="2mo", interval="1d")
            hist_1y = stock.history(period="1y", interval="1d")
            if hist.empty or hist_1y.empty or 'Close' not in hist or 'Volume' not in hist:
                all_results.append({
                    'Ticker': full_ticker,
                    'Status': 'No Data',
                    'Sector': '',
                    'Current Price': '',
                    '30-Day High': '',
                    'Breakout Date': '',
                    'MA Signal (LT)': '',
                    'Trend Days LT (+/-)': '',
                    'ST Signal': '',
                    'Trend Days ST (+/-)': '',
                    'EMA Filter': '',
                    'Volume Confirmed': '',
                    'Breakout': '',
                    'Volume': '',
                    'Avg Vol(30d)': ''
                })
                progress_bar.progress((idx + 1) / len(tickers))
                continue
            hist_1y['MA_50'] = hist_1y['Close'].rolling(window=50).mean()
            hist_1y['MA_200'] = hist_1y['Close'].rolling(window=200).mean()
            is_bullish = hist_1y['MA_50'].iloc[-1] > hist_1y['MA_200'].iloc[-1]
            ma_signal = "Bullish 🟢" if is_bullish else "Bearish 🔴"
            hist_1y['LT_Trend'] = hist_1y['MA_50'] > hist_1y['MA_200']
            trend_days = (hist_1y['LT_Trend'] == hist_1y['LT_Trend'].iloc[-1])[::-1].cumprod().sum()
            trend_days_signed = trend_days if is_bullish else -trend_days
            hist_1y['MA_20'] = hist_1y['Close'].rolling(window=20).mean()
            hist_1y['MA_50_ST'] = hist_1y['Close'].rolling(window=50).mean()
            st_bullish = hist_1y['MA_20'].iloc[-1] > hist_1y['MA_50_ST'].iloc[-1]
            st_signal = "Bullish" if st_bullish else "Bearish"
            hist_1y['ST_Trend'] = hist_1y['MA_20'] > hist_1y['MA_50_ST']
            st_days = (hist_1y['ST_Trend'] == hist_1y['ST_Trend'].iloc[-1])[::-1].cumprod().sum()
            st_days_signed = st_days if st_bullish else -st_days
            if is_bullish:
                bullish_count += 1
            else:
                bearish_count += 1
            hist['EMA_20'] = hist['Close'].ewm(span=20, adjust=False).mean()
            hist['EMA_50'] = hist['Close'].ewm(span=50, adjust=False).mean()
            ema_ok = hist['Close'].iloc[-1] > hist['EMA_20'].iloc[-1] > hist['EMA_50'].iloc[-1]
            recent_volume = hist['Volume'].iloc[-1]
            avg_volume = hist['Volume'].iloc[-30:].mean()
            volume_confirmed = recent_volume > 1.5 * avg_volume
            breakout = is_breakout_last_13_days(hist)
            info = stock.info
            sector = info.get('sector', 'Unknown')
            all_results.append({
                'Ticker': full_ticker,
                'Status': 'OK',
                'Sector': sector,
                'Current Price': round(hist['Close'].iloc[-1], 2),
                '30-Day High': round(hist['High'].iloc[-30:-1].max(), 2),
                'Breakout Date': hist.index[-1].strftime("%Y-%m-%d"),
                'MA Signal (LT)': ma_signal,
                'Trend Days LT (+/-)': trend_days_signed,
                'ST Signal': st_signal,
                'Trend Days ST (+/-)': st_days_signed,
                'EMA Filter': '✅' if ema_ok else '❌',
                'Volume Confirmed': '✅' if volume_confirmed else '❌',
                'Breakout': '✅' if breakout and ema_ok and volume_confirmed else '❌',
                'Volume': int(recent_volume),
                'Avg Vol(30d)': int(avg_volume)
            })
        except Exception as e:
            all_results.append({
                'Ticker': full_ticker,
                'Status': f"Error: {e}",
                'Sector': '',
                'Current Price': '',
                '30-Day High': '',
                'Breakout Date': '',
                'MA Signal (LT)': '',
                'Trend Days LT (+/-)': '',
                'ST Signal': '',
                'Trend Days ST (+/-)': '',
                'EMA Filter': '',
                'Volume Confirmed': '',
                'Breakout': '',
                'Volume': '',
                'Avg Vol(30d)': ''
            })
        progress_bar.progress((idx + 1) / len(tickers))
    progress_bar.empty()
    status_text.empty()
    df = pd.DataFrame(all_results)
    return df, bullish_count, bearish_count

# ===== Helper: Support/Resistance =====
@st.cache_data(ttl=3600)
def analyze_stock_behavior(ticker, country):
    suffix = {'india': '.NS', 'australia': '.AX', 'us': ''}.get(country.lower(), '')
    full_ticker = ticker.upper() + suffix
    stock = yf.Ticker(full_ticker)
    hist = stock.history(period="3mo", interval="1d")
    
    if hist.empty:
        return f"\n📌 **{full_ticker}**\n⚠️ No data found.\n" + "="*50 + "\n"
    
    hist['Volatility'] = hist['High'] - hist['Low']
    recent = hist.iloc[-1]
    current_price = round(recent['Close'], 2)
    support_zone = round(hist['Low'].tail(30).min(), 2)
    resistance_zone = round(hist['High'].tail(30).max(), 2)
    avg_volatility = hist['Volatility'].rolling(10).mean().iloc[-1]
    recent_volatility = recent['High'] - recent['Low']
    wild_swings = recent_volatility > 1.5 * avg_volatility
    
    hist['20DMA_Vol'] = hist['Volume'].rolling(20).mean()
    volume_surge = recent['Volume'] > 1.5 * hist['20DMA_Vol'].iloc[-1]
    
    breakout_trigger = round(resistance_zone * 1.01, 2)
    breakdown_trigger = round(support_zone * 0.99, 2)
    
    lines = [f"\n📌 **{full_ticker}** - Current Price: **₹{current_price}**\n\n"]
    
    if wild_swings:
        lines.append("🔥 The stock is showing **wild intraday swings**, suggesting large players accumulating or unloading.\n\n")
    
    lines.append(f"📍 **Support Zone**: ₹{support_zone} (recent test level)\n")
    lines.append(f"🔻 **Technically Weak Below**: ₹{breakdown_trigger} (downside risk)\n")
    lines.append(f"🔺 **Breakout Above**: ₹{breakout_trigger} (high target potential)\n\n")
    
    if volume_surge:
        lines.append("🔊 **Volume Spike Detected** - Supports potential breakout.\n")
    
    lines.append("="*50 + "\n")
    return "".join(lines)

# ====== Streamlit Tabs ======
tab1, tab2, tab3 = st.tabs(["🔥 Breakout Finder", "📉 Support/Resistance", "⚡ MA/RSI Backtest"])

# ==== Tab 1: Breakout Finder ====
with tab1:
    st.header("🔥 Breakout Finder")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        country = st.selectbox("Select Country", ["India", "Australia", "US"], key="tab1_country")
    with col2:
        tickers_str = st.text_input("Enter comma-separated tickers", "RELIANCE, TCS, INFY", key="tab1_tickers")
    
    run_btn = st.button("🔍 Find Breakouts", use_container_width=True)
    suffix = {'India': '.NS', 'Australia': '.AX', 'US': ''}[country]
    tickers = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]
    
    if run_btn and len(tickers) > 0:
        with st.spinner("🔎 Analyzing stocks..."):
            df, bullish, bearish = find_breakouts(tickers, suffix)
        
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 Total Stocks", len(df))
            col2.metric("🟢 Bullish (LT)", bullish)
            col3.metric("🔴 Bearish (LT)", bearish)
            
            st.dataframe(df, use_container_width=True, height=600)
            
        if not df.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button(
                label="📥 Download Excel",
                data=output.getvalue(),
                file_name="breakout_stocks.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.warning("⚠️ No stocks found matching the criteria.")

# ==== Tab 2: Support & Resistance ====
with tab2:
    st.header("📉 Support, Resistance & Behavioral Analysis")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        country2 = st.selectbox("Select Country", ["India", "Australia", "US"], key="tab2_country")
    with col2:
        tickers2_str = st.text_input("Enter comma-separated tickers", "RELIANCE, INFY", key="tab2_tickers")
    
    analyze_btn = st.button("📊 Analyze Behavior", use_container_width=True)
    tickers2 = [t.strip().upper() for t in tickers2_str.split(',') if t.strip()]
    
    if analyze_btn and len(tickers2) > 0:
        all_analyses = []
        for t in tickers2:
            msg = analyze_stock_behavior(t, country2)
            st.markdown(msg)
            all_analyses.append(msg)
        
        txt = "\n".join(all_analyses)
        st.download_button(
            "📥 Download Analysis",
            txt,
            file_name="behavioral_analysis.txt",
            mime="text/plain",
            use_container_width=True
        )


# ==== Tab 3: MA/RSI Backtest ====
with tab3:
    st.header("⚡ MA + RSI Strategy Backtest")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        stock_input = st.text_input("Stock Symbol", value="RELIANCE", key="tab3_symbol")
    with col2:
        inv_amount = st.number_input("Investment (₹)", min_value=1000, value=100000, step=10000, key="tab3_amt")
    with col3:
        yrs = st.slider("Years", 1, 12, value=3, key="tab3_years")
    
    run_bt = st.button("🚀 Run Backtest", use_container_width=True)
    
    if run_bt and stock_input:
        suffix = ".NS" if not stock_input.upper().endswith((".NS", ".AX")) else ""
        ticker = stock_input.upper() + suffix
        
        with st.spinner(f"⏳ Backtesting {ticker}..."):
            df = yf.download(ticker, period=f"{yrs}y", interval="1d", auto_adjust=True, progress=False)
        
        if not df.empty:
            close_series = df['Close']
            if isinstance(close_series, pd.DataFrame):
                close_series = close_series.iloc[:, 0]
            
            # Compute Indicators
            df['RSI'] = RSIIndicator(close_series, window=14).rsi()
            df['SMA_short'] = SMAIndicator(close_series, window=20).sma_indicator()
            df['SMA_long'] = SMAIndicator(close_series, window=50).sma_indicator()
            df['Signal'] = 0
            df.loc[(df['RSI'] > 30) & (df['SMA_short'] > df['SMA_long']), 'Signal'] = 1
            
            position, entry_price, trades = 0, 0.0, 0
            positions_list, trade_log = [], []
            
            for i in range(len(df)):
                date, price = df.index[i], close_series.iloc[i]
                if position == 0 and df['Signal'].iloc[i] == 1:
                    position, entry_price, trades = 1, price, trades + 1
                    trade_log.append([date.date(), 'Buy', price])
                elif position == 1 and (price <= entry_price * 0.99 or df['SMA_short'].iloc[i] < df['SMA_long'].iloc[i] or df['RSI'].iloc[i] < 70):
                    position, trades = 0, trades + 1
                    trade_log.append([date.date(), 'Sell', price])
                positions_list.append(position)
            
            df['Position'] = positions_list
            df['Market Return'] = close_series.pct_change()
            df['Strategy Return'] = df['Market Return'] * df['Position'].shift(1).fillna(0)
            df['Portfolio Value'] = inv_amount * (1 + df['Strategy Return']).cumprod()
            
            # Display Results
            col1, col2, col3 = st.columns(3)
            final_value = df['Portfolio Value'].iloc[-1]
            total_return = ((final_value / inv_amount) - 1) * 100
            
            col1.metric("Initial Investment", f"₹{inv_amount:,.0f}")
            col2.metric("Final Value", f"₹{final_value:,.2f}")
            col3.metric("Total Return", f"{total_return:.2f}%")
            
            st.line_chart(df['Portfolio Value'], use_container_width=True)
            st.info(f"📊 Total Trades Executed: **{trades}**")
            
            # Download Trade Log
            trade_log_df = pd.DataFrame(trade_log, columns=['Date', 'Action', 'Price'])
            if not trade_log_df.empty:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    trade_log_df.to_excel(writer, index=False)
                st.download_button(
                    "📥 Download Trade Log (Excel)",
                    output.getvalue(),
                    file_name="trade_log.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.error("❌ No data found for this ticker.")






st.divider()
st.caption("💡 Built with Streamlit • Data from Yahoo Finance")
st.caption("Gaurav Jain")

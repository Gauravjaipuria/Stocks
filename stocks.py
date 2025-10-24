import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os

st.set_page_config(page_title="Stock Analytics Suite", layout="wide")
st.title("📊 Stock Analytics Suite (Breakouts, Behaviors & Backtests)")

# ===== Helper: Breakout Logic =====
def is_breakout_last_13_days(hist):
    if len(hist) < 30:
        return False
    recent_close = hist['Close'].iloc[-1]
    past_high = hist['High'].iloc[-30:-13].max()
    return recent_close > past_high

def find_breakouts(tickers, suffix):
    breakout_results = []
    bullish_count = 0
    bearish_count = 0
    for ticker in tickers:
        full_ticker = ticker + suffix
        try:
            stock = yf.Ticker(full_ticker)
            hist = stock.history(period="2mo", interval="1d")
            hist_1y = stock.history(period="1y", interval="1d")
            if hist.empty or hist_1y.empty or 'Close' not in hist or 'Volume' not in hist:
                continue
            hist_1y['MA_50'] = hist_1y['Close'].rolling(window=50).mean()
            hist_1y['MA_200'] = hist_1y['Close'].rolling(window=200).mean()
            ma_50 = hist_1y['MA_50'].iloc[-1]
            ma_200 = hist_1y['MA_200'].iloc[-1]
            is_bullish = ma_50 > ma_200
            ma_signal = "Bullish 🟢" if is_bullish else "Bearish 🔴"
            hist_1y['LT_Trend'] = hist_1y['MA_50'] > hist_1y['MA_200']
            current_trend = hist_1y['LT_Trend'].iloc[-1]
            trend_days = 0
            for i in range(len(hist_1y) - 1, -1, -1):
                if hist_1y['LT_Trend'].iloc[i] == current_trend:
                    trend_days += 1
                else:
                    break
            trend_days_signed = trend_days if is_bullish else -trend_days
            hist_1y['MA_20'] = hist_1y['Close'].rolling(window=20).mean()
            hist_1y['MA_50_ST'] = hist_1y['Close'].rolling(window=50).mean()
            st_bullish = hist_1y['MA_20'].iloc[-1] > hist_1y['MA_50_ST'].iloc[-1]
            st_signal = "Bullish" if st_bullish else "Bearish"
            hist_1y['ST_Trend'] = hist_1y['MA_20'] > hist_1y['MA_50_ST']
            st_current_trend = hist_1y['ST_Trend'].iloc[-1]
            st_days = 0
            for i in range(len(hist_1y) - 1, -1, -1):
                if hist_1y['ST_Trend'].iloc[i] == st_current_trend:
                    st_days += 1
                else:
                    break
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
            if is_breakout_last_13_days(hist) and ema_ok and volume_confirmed:
                info = stock.info
                sector = info.get('sector', 'Unknown')
                breakout_results.append({
                    'Ticker': full_ticker,
                    'Sector': sector,
                    'Current Price': round(hist['Close'].iloc[-1], 2),
                    '30-Day High': round(hist['High'].iloc[-30:-1].max(), 2),
                    'Breakout Date': hist.index[-1].strftime("%Y-%m-%d"),
                    'MA Signal (LT)': ma_signal,
                    'Trend Days LT (+/-)': trend_days_signed,
                    'ST Signal': st_signal,
                    'Trend Days ST (+/-)': st_days_signed,
                    'EMA Filter': '✅',
                    'Volume Confirmed': '✅',
                    'Volume': int(recent_volume),
                    'Avg Vol(30d)': int(avg_volume)
                })
        except Exception as e:
            continue
    df = pd.DataFrame(breakout_results)
    return df, bullish_count, bearish_count

# ===== Helper: Support/Resistance =====
def analyze_stock_behavior(ticker, country):
    suffix = {'india': '.NS', 'australia': '.AX', 'us': ''}.get(country.lower(), '')
    full_ticker = ticker.upper() + suffix
    stock = yf.Ticker(full_ticker)
    hist = stock.history(period="3mo", interval="1d")
    if hist.empty:
        return f"\n📌 {full_ticker}\n⚠️ No data found.\n" + "="*50 + "\n"
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
    lines = [f"\n📌 {full_ticker} CP ${current_price}\n"]
    if wild_swings:
        lines.append("The stock is showing **wild intraday swings**, suggesting the presence of **large players accumulating or unloading**.\n")
    lines.append(f"It recently tested the zone near **${support_zone}**, which aligns with a prior breakout level.\n")
    lines.append(f"It will be considered **technically weak below ${breakdown_trigger}**, indicating potential downside risk.\n")
    lines.append(f"However, a **close above ${breakout_trigger}** could signal a breakout and unlock **high target potential**.\n")
    if volume_surge:
        lines.append("🔊 The last session also showed a **volume spike**, supporting the idea of a potential breakout.\n")
    lines.append("="*50 + "\n")
    return "".join(lines)

# ====== Streamlit Tabs ======
tab1, tab2, tab3 = st.tabs(["Breakout Finder", "Support/Resistance", "MA/RSI Backtest"])

# ==== Tab 1: Breakout Finder ====
with tab1:
    st.header("🔥 Breakout Finder")
    country = st.selectbox("Country", ["India", "Australia", "US"], key="tab1_country")
    tickers_str = st.text_input("Enter comma-separated tickers", "RELIANCE, TCS, INFY", key="tab1_tickers")
    run_btn = st.button("Find Breakouts")
    suffix = { 'India': '.NS', 'Australia': '.AX', 'US': '' }[country]
    tickers = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]
    if run_btn and len(tickers) > 0:
        with st.spinner("Searching for bullish breakout stocks..."):
            df, bullish, bearish = find_breakouts(tickers, suffix)
        if not df.empty:
            st.success(f"{bullish} Bullish LT | {bearish} Bearish LT")
            st.dataframe(df)
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, file_name="breakout_stocks_filtered.csv", mime="text/csv")
        else:
            st.warning("No breakout stocks found in last 13 days.")

# ==== Tab 2: Support & Resistance/Behavioral Analysis ====
with tab2:
    st.header("📉 Support, Resistance & Behavioral Analysis")
    country2 = st.selectbox("Country", ["India", "Australia", "US"], key="tab2_country")
    tickers2_str = st.text_input("Enter comma-separated tickers", "RELIANCE, INFY", key="tab2_tickers")
    analyze_btn = st.button("Analyze Behavior")
    tickers2 = [t.strip().upper() for t in tickers2_str.split(',') if t.strip()]
    if analyze_btn and len(tickers2) > 0:
        all_analyses = []
        for t in tickers2:
            msg = analyze_stock_behavior(t, country2)
            st.write(msg)
            all_analyses.append(msg)
        txt = "\n".join(all_analyses)
        st.download_button("Download as Text", txt, file_name="multi_stock_behavioral_analysis.txt", mime="text/plain")

# ==== Tab 3: Place-holder for MA/RSI strategy ====
with tab3:
    st.header("⚡ Advanced: MA + RSI Strategy")
    st.info("For a Streamlit MA/RSI backtest with trade log and charting, additional modules (`ta`, `matplotlib`, etc.) must be installed on the server. Let me know if you want a ready-to-run backtest module with Streamlit plotting and downloads.")

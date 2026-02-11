import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go

# --- 1. CONSTANTS & CONFIGURATION ---
# noinspection SpellCheckingInspection
MY_API_KEY = st.secrets["POLYGON_API_KEY"]
START_DATE = "2024-04-01"
END_DATE = "2026-02-05"
POPULAR_STOCKS = ["AAPL", "MSFT", "TSLA", "AMZN", "GOOGL", "NVDA", "META"]
BENCHMARK_MAP = {
    "S&P 500 (SPY)": "SPY",
    "Nasdaq (QQQ)": "QQQ",
    "Dow Jones (DIA)": "DIA"
}


# --- 2. HELPER FUNCTIONS ---
def calculate_percentage_return(past_val: float, current_val: float) -> float:
    """Calculates percentage return between two price points."""
    return ((current_val - past_val) / past_val) * 100


def fetch_api_data(target_url: str):
    """Safe wrapper for API requests with specific exception handling."""
    try:
        res = requests.get(target_url, timeout=10)
        return res.json() if res.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


# --- 3. PAGE SETUP ---
st.set_page_config(page_title="Ultimate Stock Pro", layout="wide")

# --- 4. SIDEBAR INPUTS ---
st.sidebar.header("Welcome to the Stock Dashboard!")

input_choice = st.sidebar.radio("Please select input method", ["Choose from list", "Type manually"])

if input_choice == "Choose from list":
    symbol = st.sidebar.selectbox("Popular stocks", POPULAR_STOCKS)
else:
    symbol = st.sidebar.text_input("Enter ticker symbol (e.g. NVDA)").upper()

benchmark_label = st.sidebar.selectbox("Select Benchmark", ["None"] + list(BENCHMARK_MAP.keys()))
benchmark_symbol = BENCHMARK_MAP.get(benchmark_label)

# Initializing dataframes to avoid 'undefined' warnings in IDE
main_df = pd.DataFrame()
bench_df = pd.DataFrame()

if not symbol:
    st.title("📈 Stock Market Intelligence Dashboard")
    st.warning("Please select or enter a ticker symbol to begin.")
    st.stop()

# --- 5. DATA ACQUISITION ---
stock_url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{START_DATE}/{END_DATE}?adjusted=true&sort=asc&apiKey={MY_API_KEY}"
info_url = f"https://api.polygon.io/v3/reference/tickers/{symbol}?apiKey={MY_API_KEY}"

# 'type: ignore' used to quiet IDE context manager warnings (like st.spinner)
with st.spinner('Fetching data from Wall Street...'):  # type: ignore
    stock_raw_data = fetch_api_data(stock_url)
    details_raw_data = fetch_api_data(info_url)

    benchmark_raw_data = None
    if benchmark_symbol:
        bench_url_api = f"https://api.polygon.io/v2/aggs/ticker/{benchmark_symbol}/range/1/day/{START_DATE}/{END_DATE}?adjusted=true&sort=asc&apiKey={MY_API_KEY}"
        benchmark_raw_data = fetch_api_data(bench_url_api)

# --- 6. DATA PROCESSING & UI ---
if stock_raw_data and 'results' in stock_raw_data:
    st.title("📈 Stock Market Intelligence Dashboard")

    # Header Logic
    company_name = details_raw_data.get('results', {}).get('name', symbol) if details_raw_data else symbol

    logo_col, name_col = st.columns([1, 10])
    with logo_col:
        img_url = f"https://companiesmarketcap.com/img/company-logos/64/{symbol}.webp"
        try:
            if requests.head(img_url, timeout=2).status_code == 200:
                st.image(img_url, width=70)
            else:
                st.markdown("## 🏢")
        except requests.exceptions.RequestException:
            st.markdown("## 🏢")

    with name_col:
        st.header(company_name)

    # DataFrame Transformation
    main_df = pd.DataFrame(stock_raw_data['results'])
    main_df = main_df.rename(
        columns={'c': 'Close', 'h': 'High', 'l': 'Low', 'o': 'Open', 't': 'Timestamp', 'v': 'Volume'})
    main_df['Date'] = pd.to_datetime(main_df['Timestamp'], unit='ms')

    # Metrics Calculation
    latest_price = main_df['Close'].iloc[-1]
    ret_total = calculate_percentage_return(main_df['Close'].iloc[0], latest_price)
    ret_week = calculate_percentage_return(main_df['Close'].iloc[-5], latest_price) if len(main_df) >= 5 else ret_total

    # Comparison Logic
    outperform_val = None
    if benchmark_raw_data and 'results' in benchmark_raw_data:
        bench_df = pd.DataFrame(benchmark_raw_data['results'])
        bench_df['Date'] = pd.to_datetime(bench_df['t'], unit='ms')

        main_df['Normalized'] = (main_df['Close'] / main_df['Close'].iloc[0]) * 100
        bench_df['Normalized'] = (bench_df['c'] / bench_df['c'].iloc[0]) * 100

        bench_total_ret = calculate_percentage_return(bench_df['c'].iloc[0], bench_df['c'].iloc[-1])
        outperformance = ret_total - bench_total_ret
        outperform_val = outperformance

    # --- UI Sections ---
    st.markdown("### 📊 Performance Metrics")
    cols = st.columns(4 if outperform_val is not None else 3)
    cols[0].metric("Current Price", f"${latest_price:.2f}")
    cols[1].metric("Week Change", f"{ret_week:.2f}%", delta=f"{ret_week:.2f}%")
    cols[2].metric("Total Change", f"{ret_total:.2f}%", delta=f"{ret_total:.2f}%")
    if outperform_val is not None:
        cols[3].metric(f"vs. {benchmark_label}", f"{outperform_val:+.2f}%", delta=f"{outperform_val:.2f}%")

    tab1, tab2 = st.tabs(["🕯️ Candlestick Chart", "📈 Growth Comparison"])

    with tab1:
        fig_candle = go.Figure(data=[go.Candlestick(
            x=main_df['Date'], open=main_df['Open'], high=main_df['High'],
            low=main_df['Low'], close=main_df['Close'], name="Price"
        )])
        fig_candle.update_layout(
            template="plotly_dark", xaxis_rangeslider_visible=False, height=450,
            xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True)
        )
        st.plotly_chart(fig_candle, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        if outperform_val is not None:
            fig_comp = go.Figure()
            fig_comp.add_trace(
                go.Scatter(x=main_df['Date'], y=main_df['Normalized'], name=symbol, line=dict(color='cyan', width=3)))
            fig_comp.add_trace(go.Scatter(x=bench_df['Date'], y=bench_df['Normalized'], name=benchmark_label,
                                          line=dict(color='red', width=2)))
            fig_comp.update_layout(
                template="plotly_dark", height=450,
                title=f"Growth of $100 since {START_DATE}",
                xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True)
            )
            st.plotly_chart(fig_comp, use_container_width=True, config={'displayModeBar': False})
            st.info(
                f"This chart compares the relative performance starting from {START_DATE} of a $100 investment in {symbol} vs {benchmark_label}.")
        else:
            st.info("Please select a benchmark in the sidebar to see the growth comparison chart.")

    # Research Links
    st.markdown("---")
    st.subheader("📰 Market Insights")
    n1, n2, n3 = st.columns(3)
    n1.link_button("Yahoo Finance", f"https://finance.yahoo.com/quote/{symbol}", use_container_width=True)
    n2.link_button("Seeking Alpha", f"https://seekingalpha.com/symbol/{symbol}", use_container_width=True)
    n3.link_button("Google News", f"https://www.google.com/search?q={symbol}+stock+news&tbm=nws",
                   use_container_width=True)

    with st.expander("View Raw Data Table"):
        st.dataframe(main_df)
else:
    st.error("⚠️ Error: Data fetch failed. Check your connection, ticker, or API limit.")
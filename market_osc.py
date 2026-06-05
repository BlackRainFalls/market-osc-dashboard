import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Market OSC Indicator", layout="wide")
st.title("📈 Market OSC Indicator")

# FIX: Robust Plotly modebar visibility adjustment for light/dark mode mixing
st.markdown(
    """
    <style>
    /* Force visibility on all Plotly modebar paths regardless of theme */
    div[data-testid="stPlotlyChart"] .modebar-btn svg path {
        fill: #555555 !important;
        opacity: 0.7 !important;
    }
    
    /* Give it your signature high-visibility pink on hover */
    div[data-testid="stPlotlyChart"] .modebar-btn:hover svg path {
        fill: #ff007f !important;
        opacity: 1.0 !important;
    }
    
    /* Optional: Give the background of the vertical modebar a slight background tint on hover */
    div[data-testid="stPlotlyChart"] .modebar-btn:hover {
        background-color: rgba(0, 0, 0, 0.05) !important;
        border-radius: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Sidebar for controls
st.sidebar.header("Settings")

# Expanded Index Selection
ticker_mapping = {
    "S&P 500 (^GSPC)": "^GSPC",
    "Nasdaq 100 (^NDX)": "^NDX",
    "Russell 2000 (^RUT)": "^RUT",
    "Dow Jones (^DJI)": "^DJI"
}
ticker_choice = st.sidebar.selectbox("Select Index", list(ticker_mapping.keys()))
ticker = ticker_mapping[ticker_choice]

# Timeframe Selector - Defaulting to "1 Year" (index=1)
timeframe_options = ["6 Month", "1 Year", "3 Year", "5 Year"]
timeframe_display = st.sidebar.selectbox("Timeframe", timeframe_options, index=1)

# Advanced Macro Routing Rules
if timeframe_display == "6 Month":
    interval = "1d"
    download_period = "1y"       
    keep_bars = 126              
    sma_period = 50              
    sma_label = "50 DMA"
    default_fast, default_slow, default_signal = 12, 26, 9
    default_ob, default_os = 1.5, -1.5
    desc = "Tactical trend tracking with 50 DMA."
    
elif timeframe_display == "1 Year":
    interval = "1d"
    download_period = "2y"       
    keep_bars = 252              
    sma_period = 200             
    sma_label = "200 DMA"
    default_fast, default_slow, default_signal = 19, 39, 9
    default_ob, default_os = 2.0, -2.0
    desc = "Institutional macro daily layout."
    
elif timeframe_display == "3 Year":
    interval = "1wk"
    download_period = "5y"
    keep_bars = 156              
    sma_period = 50              
    sma_label = "50 WMA"
    default_fast, default_slow, default_signal = 12, 26, 9
    default_ob, default_os = 3.5, -3.5
    desc = "Multi-year weekly cyclical view."
    
else:  # 5 Year
    interval = "1mo"
    download_period = "10y"
    keep_bars = 60               
    sma_period = 20              
    sma_label = "20 MMA"
    default_fast, default_slow, default_signal = 12, 26, 9
    default_ob, default_os = 5.0, -5.0
    desc = "Secular monthly macroeconomic view."

st.sidebar.info(f"📊 **Interval:** {interval} ({sma_label} Active)\n🎯 **Profile:** {desc}")

# FEATURE 2 & UPDATE: Relative Strength Toggles
st.sidebar.subheader("Overlay Tools")
show_rs_spy = st.sidebar.checkbox("Show Relative Strength vs S&P 500", value=False)
show_rs_ndx = st.sidebar.checkbox("Show Relative Strength vs Nasdaq 100", value=False)

# OSC Parameter Tuning
st.sidebar.subheader("OSC Settings")
fast_ema = st.sidebar.slider("Fast EMA", 5, 50, default_fast)
slow_ema = st.sidebar.slider("Slow EMA", 21, 100, default_slow)
signal_period = st.sidebar.slider("Signal Period", 5, 30, default_signal)

# Risk Zones
st.sidebar.subheader("Risk Zones")
ob_level = st.sidebar.slider("Overbought Level (%)", 0.0, 10.0, default_ob, 0.1)
os_level = st.sidebar.slider("Oversold Level (%)", -10.0, 0.0, default_os, 0.1)

refresh = st.sidebar.button("Manual Refresh")

@st.cache_data(ttl=60) 
def fetch_data(ticker, period, interval):
    data = yf.download(ticker, period=period, interval=interval)
    if data.empty:
        return data
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data.columns = [str(col).strip() for col in data.columns]
    return data

@st.cache_data(ttl=300)
def fetch_breadth_data(period, interval):
    rsp = yf.download("RSP", period=period, interval=interval)
    spy = yf.download("SPY", period=period, interval=interval)
    
    if not rsp.empty:
        if isinstance(rsp.columns, pd.MultiIndex):
            rsp.columns = rsp.columns.get_level_values(0)
        rsp.columns = [str(col).strip() for col in rsp.columns]
        
    if not spy.empty:
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)
        spy.columns = [str(col).strip() for col in spy.columns]
        
    return rsp, spy

def calculate_osc(df, fast, slow, signal):
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    ppo = ((ema_fast - ema_slow) / ema_slow) * 100
    ppo_signal = ppo.ewm(span=signal, adjust=False).mean()
    ppo_hist = ppo - ppo_signal
    return ppo, ppo_signal, ppo_hist

# --- EXECUTION ---
raw_df = fetch_data(ticker, download_period, interval)

if not raw_df.empty:
    # Drops unfinalized tracking intervals
    raw_df = raw_df.dropna(subset=['Close'])

    # Calculations
    raw_df['Trend_Filter'] = raw_df['Close'].rolling(window=sma_period).mean()
    ppo, signal_line, hist = calculate_osc(raw_df, fast_ema, slow_ema, signal_period)
    
    raw_df['OSC_Line'] = ppo
    raw_df['OSC_Signal'] = signal_line
    raw_df['OSC_Hist'] = hist

    # Background processing for Relative Strength vs S&P 500
    if show_rs_spy and ticker != "^GSPC":
        spy_df = fetch_data("^GSPC", download_period, interval)
        if not spy_df.empty:
            spy_df = spy_df.dropna(subset=['Close'])
            combined_spy = pd.DataFrame({'Target': raw_df['Close'], 'Benchmark': spy_df['Close']}).dropna()
            raw_df['RS_SPY_Ratio'] = combined_spy['Target'] / combined_spy['Benchmark']

    # Background processing for Relative Strength vs Nasdaq 100
    if show_rs_ndx and ticker != "^NDX":
        ndx_df = fetch_data("^NDX", download_period, interval)
        if not ndx_df.empty:
            ndx_df = ndx_df.dropna(subset=['Close'])
            combined_ndx = pd.DataFrame({'Target': raw_df['Close'], 'Benchmark': ndx_df['Close']}).dropna()
            raw_df['RS_NDX_Ratio'] = combined_ndx['Target'] / combined_ndx['Benchmark']

    df = raw_df.tail(keep_bars)
    
    # Determine if ANY relative strength line needs to be shown to switch layout to 3 panels
    has_active_rs_spy = show_rs_spy and 'RS_SPY_Ratio' in df.columns and ticker != "^GSPC"
    has_active_rs_ndx = show_rs_ndx and 'RS_NDX_Ratio' in df.columns and ticker != "^NDX"
    any_rs_active = has_active_rs_spy or has_active_rs_ndx

    # Grid Construction - Clean structural multi-panel division
    if any_rs_active:
        # 3 Panels: Price (50%), RS Window Panel (20%), OSC Panel (30%)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.04, row_heights=[0.50, 0.20, 0.30],
                            specs=[[{"secondary_y": True}], [{"secondary_y": False}], [{"secondary_y": False}]])
    else:
        # 2 Panels: Price (65%), OSC Panel (35%)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.04, row_heights=[0.65, 0.35],
                            specs=[[{"secondary_y": True}], [{"secondary_y": False}]])

    # PANEL 1: Candlesticks & Navy Blue Moving Average Line
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name="Price"), row=1, col=1, secondary_y=False)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['Trend_Filter'], 
                             line=dict(color='#000080', width=2), name=sma_label), row=1, col=1, secondary_y=False)

    # PANEL 1 (Secondary Y-Axis): Muted Background Volume Overlay
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", 
                         marker_color='rgba(140, 140, 140, 0.14)', 
                         marker_line=dict(color='rgba(140, 140, 140, 0.25)', width=1)), 
                  row=1, col=1, secondary_y=True)

    # PANEL 2 (Conditional): Dedicated Relative Strength View Pane
    osc_row = 2
    if any_rs_active:
        if has_active_rs_spy:
            fig.add_trace(go.Scatter(x=df.index, y=df['RS_SPY_Ratio'], 
                                     line=dict(color='purple', width=1.5), 
                                     name="RS vs S&P 500"), row=2, col=1)
        if has_active_rs_ndx:
            fig.add_trace(go.Scatter(x=df.index, y=df['RS_NDX_Ratio'], 
                                     line=dict(color='#00b0ff', width=1.5), 
                                     name="RS vs Nasdaq 100"), row=2, col=1)
        fig.update_yaxes(title_text="RS Ratio", row=2, col=1)
        osc_row = 3

    # PANEL 3 (or 2): Market OSC Pane
    osc_colors = ['#26a69a' if val > 0 else '#ef5350' for val in df['OSC_Hist']]
    fig.add_trace(go.Bar(x=df.index, y=df['OSC_Hist'], name="OSC Histogram", marker_color=osc_colors), row=osc_row, col=1)
    
    # UPDATED: Changed line color to high-visibility pink ('#ff007f') for light-mode readability
    fig.add_trace(go.Scatter(x=df.index, y=df['OSC_Line'], line=dict(color='#ff007f', width=1.5), name="OSC Line"), row=osc_row, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['OSC_Signal'], line=dict(color='orange', width=1, dash='dot'), name="Signal"), row=osc_row, col=1)

    # OSC Overbought/Oversold Threshold Guardrails
    fig.add_hline(y=ob_level, line_dash="dash", line_color="#ff5252", line_width=1.2, row=osc_row, col=1)
    fig.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.15)", line_width=1, row=osc_row, col=1)
    fig.add_hline(y=os_level, line_dash="dash", line_color="#00e676", line_width=1.2, row=osc_row, col=1)

    # Scaling constraints for volume limits to prevent overlapping price bars
    max_volume = float(df['Volume'].max())
    fig.update_yaxes(range=[0, max_volume * 6], showgrid=False, showticklabels=False, row=1, col=1, secondary_y=True)

    # Global Layout Configuration with Vertical Modebar Settings
    fig.update_layout(height=850, template="plotly_dark", 
                      xaxis_rangeslider_visible=False,
                      margin=dict(l=20, r=20, t=10, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      modebar=dict(orientation='v')) 
    
    fig.update_yaxes(title_text="Price", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="OSC (%)", row=osc_row, col=1)

    st.plotly_chart(fig, width='stretch')
    
    # --- METRICS & BREADTH GENERATION ---
    rsp_df, spy_df = fetch_breadth_data(download_period, interval)
    breadth_desc = "Neutral/Skewed"
    ratio_change = 0.0
    if not rsp_df.empty and not spy_df.empty:
        rsp_df, spy_df = rsp_df.dropna(subset=['Close']), spy_df.dropna(subset=['Close'])
        ratio = rsp_df['Close'] / spy_df['Close']
        current_ratio = ratio.iloc[-1]
        prior_ratio = ratio.iloc[-2]
        ratio_change = ((current_ratio - prior_ratio) / prior_ratio) * 100
        breadth_desc = "🟢 Expanding (Broad-Based)" if ratio_change > 0 else "🔴 Contracting (Narrow Cap-Driven)"
    
    col1, col2, col3, col4 = st.columns(4)
    current_price = df['Close'].iloc[-1]
    price_change = current_price - df['Close'].iloc[-2]
    current_sma = df['Trend_Filter'].iloc[-1]
    
    trend_status = "🟢 ABOVE" if current_price > current_sma else "🔴 BELOW"
    
    col1.metric("Current Price", f"{current_price:,.2f}", f"{price_change:,.2f}")
    col2.metric(f"Active {sma_label}", f"{current_sma:,.2f}", f"Price is {trend_status} Trend")
    col3.metric("OSC Momentum Value", f"{df['OSC_Line'].iloc[-1]:.4f}%")
    col4.metric("Market Breadth Health", breadth_desc, f"{ratio_change:+.2f}% vs Prior Bar")

    # --- ACTION FOOTER PANEL ---
    st.write("")
    action_col1, action_col2 = st.columns([1, 1])

    with action_col1:
        # FEATURE 4: Clean CSV Data Export Button
        csv_data = df.to_csv().encode('utf-8')
        st.download_button(
            label="📥 Export Current Chart Data Matrix to CSV",
            data=csv_data,
            file_name=f"{ticker.replace('^', '')}_{timeframe_display.replace(' ', '_')}_market_data.csv",
            mime="text/csv",
        )

    with action_col2:
        # EMBEDDED SHAREABILITY: Floating cleanly to the lower right hand margin
        st.markdown(
            """
            <div style="text-align: right; margin-top: 10px;">
                <span style="color: #888888; font-size: 14px;">📊 Find this macro view useful? </span>
                <a href="https://share.streamlit.io/" target="_blank" style="color: #26a69a; text-decoration: none; font-weight: bold; font-size: 14px;">
                    Share the Live Dashboard Link
                </a>
            </div>
            """, 
            unsafe_allow_html=True
        )

else:
    st.error("Could not fetch data. Check your internet connection or ticker symbols.")

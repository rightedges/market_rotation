import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_loader import fetch_data
from strategy import RotationStrategy

from portfolio_manager import load_portfolio, save_portfolio
from auth_manager import authenticate_user, register_user

st.set_page_config(page_title="Market Rotation Strategy", layout="wide")

# Session State Initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None

# --- Authentication Flow ---
if not st.session_state.authenticated:
    st.title("Market Rotation Strategy - Login")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if authenticate_user(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")
                
    with tab2:
        new_user = st.text_input("Username", key="reg_user")
        new_pass = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register"):
            if new_user and new_pass:
                success, msg = register_user(new_user, new_pass)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.error("Please fill in all fields")
    
    st.stop() # Stop execution here if not logged in

# --- Main Application (Authenticated) ---

st.sidebar.title(f"User: {st.session_state.username}")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.username = None
    st.rerun()

st.title("Market Rotation Strategy")

# Sidebar Parameters
st.sidebar.header("Strategy Parameters")

# Load Portfolio (User Specific)
if 'base_weights' not in st.session_state:
    st.session_state.base_weights = load_portfolio(st.session_state.username)

st.sidebar.subheader("Base Weights")

# Convert dictionary to DataFrame for editing
import pandas as pd
weights_df = pd.DataFrame(list(st.session_state.base_weights.items()), columns=['Ticker', 'Weight'])

# Editable Dataframe
edited_df = st.sidebar.data_editor(
    weights_df,
    num_rows="dynamic",
    use_container_width=True,
    key="weight_editor"
)

# Save Button
if st.sidebar.button("Save Portfolio"):
    # Convert back to dictionary
    new_weights = dict(zip(edited_df['Ticker'], edited_df['Weight']))
    
    if save_portfolio(st.session_state.username, new_weights):
        st.session_state.base_weights = new_weights
        st.sidebar.success("Saved!")
        st.rerun()
    else:
        st.sidebar.error("Failed to save.")

# Use the session state weights for calculation
base_weights = st.session_state.base_weights

st.sidebar.subheader("Adjustment Factors")
trend_adj = st.sidebar.slider("Trend Adjustment (50-day MA)", 0.0, 0.20, 0.10, 0.01)
rel_adj = st.sidebar.slider("Relative Performance Adjustment (vs VOO)", 0.0, 0.20, 0.05, 0.01)

lookback_years = st.sidebar.slider("Backtest Lookback (Years)", 1, 10, 5)

# Main Execution
tickers = list(base_weights.keys())
with st.spinner("Fetching Data..."):
    df_close = fetch_data(tickers, period=f"{lookback_years}y")

if df_close.empty:
    st.error("Failed to fetch data. Please check your internet connection or ticker symbols.")
else:
    # Initialize Strategy
    strategy = RotationStrategy(df_close, base_weights, trend_adj, rel_adj)
    strategy.calculate_indicators()
    
    # Create Tabs
    tab1, tab2 = st.tabs(["Dashboard", "Strategy Logic"])
    
    with tab1:
        # 1. Current Recommendation
        st.header("Current Recommendation")
        
        # Get latest available date
        latest_date = df_close.index[-1]
        st.subheader(f"Date: {latest_date.strftime('%Y-%m-%d')}")
        
        current_weights, prices, ma, ret_3m = strategy.get_signals(latest_date)
        
        # Create a nice dataframe for display
        rec_data = []
        for t in tickers:
            trend_signal = "Uptrend" if prices[t] > ma[t] else "Downtrend"
            
            # Relative Performance vs VOO
            voo_ret = ret_3m['VOO']
            rel_perf = ret_3m[t] - voo_ret
            rel_signal = "Outperform" if rel_perf > 0 else "Underperform"
            if t == 'VOO': rel_signal = "Benchmark"
            
            rec_data.append({
                "Ticker": t,
                "Price": f"${prices[t]:.2f}",
                "50-Day MA": f"${ma[t]:.2f}",
                "Trend": trend_signal,
                "3M Return": f"{ret_3m[t]:.1%}",
                "Rel vs VOO": f"{rel_perf:+.1%}",
                "Rel Signal": rel_signal,
                "Target Weight": f"{current_weights[t]:.1%}",
                "Base Weight": f"{base_weights[t]:.1%}"
            })
            
        rec_df = pd.DataFrame(rec_data)
        st.dataframe(rec_df, width='stretch')
        st.caption("Note: Target weights are rounded to the nearest 5% for easier execution.")
        
        # 2. Backtest Results
        st.header("Backtest Performance")
        
        portfolio_series, weights_history = strategy.run_backtest()
        
        # Calculate Benchmark (VOO) Performance for comparison
        voo_prices = df_close['VOO']
        # Align start dates
        start_date = portfolio_series.index[0]
        voo_normalized = voo_prices.loc[start_date:] / voo_prices.loc[start_date] * 10000
        
        # Plot Equity Curve
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=portfolio_series.index, y=portfolio_series, name="Strategy"))
        fig.add_trace(go.Scatter(x=voo_normalized.index, y=voo_normalized, name="VOO (Benchmark)", line=dict(dash='dash')))
        
        fig.update_layout(title="Portfolio Value ($10k Initial)", xaxis_title="Date", yaxis_title="Value ($)")
        st.plotly_chart(fig, width='stretch')
        
        # Metrics
        total_return = (portfolio_series.iloc[-1] / portfolio_series.iloc[0]) - 1
        # CAGR
        days = (portfolio_series.index[-1] - portfolio_series.index[0]).days
        cagr = (portfolio_series.iloc[-1] / portfolio_series.iloc[0]) ** (365.0/days) - 1
        
        # Max Drawdown
        rolling_max = portfolio_series.cummax()
        drawdown = (portfolio_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Return", f"{total_return:.1%}")
        col2.metric("CAGR", f"{cagr:.1%}")
        col3.metric("Max Drawdown", f"{max_drawdown:.1%}")
        
        # 3. Rotation History
        st.header("Monthly Rotation History")
        st.write("Weights at the end of each month:")
        
        # Format weights for display
        display_weights = weights_history.map(lambda x: f"{x:.1%}")
        st.dataframe(display_weights.sort_index(ascending=False), width='stretch')

    with tab2:
        st.header("Strategy Logic")
        st.markdown("""
        ### Core Philosophy
        This strategy avoids blindly chasing up-weeks by using **Trend** and **Relative Performance** filters to make data-driven rotation decisions.
        
        ### 1. Trend Filter (50-Day Moving Average)
        - **Indicator**: 50-day Simple Moving Average (SMA).
        - **Logic**:
            - If Price > 50-day SMA → **Uptrend** → Increase Weight (Overweight).
            - If Price < 50-day SMA → **Downtrend** → Decrease Weight (Underweight).
        - **Adjustment**: +/- {trend_adj:.0%} (Adjustable in sidebar).
        
        ### 2. Relative Performance (vs Benchmark)
        - **Indicator**: 3-Month Return vs VOO (S&P 500).
        - **Logic**:
            - If Asset Return > VOO Return → **Outperforming** → Increase Weight.
            - If Asset Return < VOO Return → **Underperforming** → Decrease Weight.
        - **Adjustment**: +/- {rel_adj:.0%} (Adjustable in sidebar).
        
        ### 3. Mixed Signals & Net Adjustment
        The adjustments are **additive**. If an asset has mixed signals, they partially offset each other.
        
        **Example:**
        - **Trend**: Uptrend (+{trend_adj:.0%})
        - **Relative Performance**: Underperform (-{rel_adj:.0%})
        - **Net Result**: Base Weight + {trend_adj:.0%} - {rel_adj:.0%} = **Base + {net_diff:.0%}**
        
        ### 5. Real-World Example Calculation
        Let's say we are evaluating **QQQM** (Base Weight: 15%).
        
        **Scenario:**
        1.  **Price Check**: QQQM Price ($180) > 50-day MA ($170).
            -   **Result**: Uptrend (+10% Adjustment).
        2.  **Relative Performance**: QQQM 3M Return (+2%) < VOO 3M Return (+5%).
            -   **Result**: Underperforming (-5% Adjustment).
            
        **Calculation:**
        -   **Base Weight**: 15% (0.15)
        -   **Trend Adj**: +0.10
        -   **Rel Perf Adj**: -0.05
        -   **Raw Weight**: 0.15 + 0.10 - 0.05 = **0.20 (20%)**
        
        *Note: After calculating raw weights for all assets, they are normalized to sum to 100% and then rounded to the nearest 5%.*
        
        ### Base Portfolio
        - **VOO**: 40%
        - **BRK-B**: 30%
        - **SPMO**: 15%
        - **QQQM**: 15%
        """.format(trend_adj=trend_adj, rel_adj=rel_adj, net_diff=trend_adj-rel_adj))



import pandas as pd
import numpy as np
from app.services.strategy import RotationStrategy
from app.services.market_data import get_historical_data
import os

def export_backtest():
    print("Starting backtest export...")
    
    # Define portfolio
    # Switched QQQM to QQQ for longer history
    portfolio = {
        'VOO': 0.40,
        'SPMO': 0.20,
        'QQQ': 0.20,
        'BRK-B': 0.20
    }
    tickers = list(portfolio.keys())
    print(f"Portfolio: {portfolio}")
    
    # Fetch data
    print("Fetching historical data (10y)...")
    df_close = get_historical_data(tuple(tickers), period='10y')
    
    if df_close is None or df_close.empty:
        print("Error: Failed to fetch historical data.")
        return

    print(f"Data fetched. Shape: {df_close.shape}")
    print(f"Date Range: {df_close.index[0]} to {df_close.index[-1]}")
    
    # Initialize Strategy
    strategy = RotationStrategy(
        data=df_close, 
        base_weights=portfolio, 
        benchmark_ticker='VOO', 
        relaxed_constraint=False
    )
    
    print("Running backtest...")
    portfolio_series, weights_df = strategy.run_backtest()
    
    if portfolio_series.empty:
        print("Error: Backtest returned empty results.")
        return

    # Calculate Metrics
    total_return = (portfolio_series.iloc[-1] / portfolio_series.iloc[0]) - 1
    days = (portfolio_series.index[-1] - portfolio_series.index[0]).days
    cagr = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
    
    # Max Drawdown
    rolling_max = portfolio_series.cummax()
    drawdown = (portfolio_series - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    metrics = {
        "Total Return": [total_return],
        "CAGR": [cagr],
        "Max Drawdown": [max_drawdown],
        "Start Date": [portfolio_series.index[0]],
        "End Date": [portfolio_series.index[-1]],
        "Initial Value": [portfolio_series.iloc[0]],
        "Final Value": [portfolio_series.iloc[-1]]
    }
    metrics_df = pd.DataFrame(metrics)
    
    # Prepare Excel Writer
    output_file = 'backtest_results.xlsx'
    print(f"Exporting to {output_file}...")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # 0. Metrics (Summary)
        metrics_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # 1. Portfolio Value (Monthly)
        portfolio_monthly = portfolio_series.resample('M').last()
        portfolio_monthly.name = 'Portfolio Value'
        portfolio_monthly.to_excel(writer, sheet_name='Portfolio Value')
        
        # 2. Weights History
        weights_df.to_excel(writer, sheet_name='Weights History')
        
        # 3. Raw Data (Daily Close)
        df_close.to_excel(writer, sheet_name='Raw Data')
        
    print("Export complete!")
    print(f"File saved to: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    export_backtest()

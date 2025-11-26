from data_loader import fetch_data
from strategy import RotationStrategy
import pandas as pd

def verify():
    print("Fetching data...")
    base_weights = {
        'VOO': 0.40,
        'BRK-B': 0.30,
        'SPMO': 0.15,
        'QQQM': 0.15
    }
    tickers = list(base_weights.keys())
    df = fetch_data(tickers, period="2y")
    
    if df.empty:
        print("Error: No data fetched.")
        return

    print("Data fetched successfully.")
    print(df.tail())
    
    print("\nInitializing Strategy...")
    strategy = RotationStrategy(df, base_weights)
    
    print("\nCalculating Indicators...")
    ma, ret = strategy.calculate_indicators()
    print("50-day MA (tail):")
    print(ma.tail())
    print("3-month Returns (tail):")
    print(ret.tail())
    
    print("\nGetting Signals for latest date...")
    latest_date = df.index[-1]
    weights, prices, current_ma, current_ret = strategy.get_signals(latest_date)
    
    print(f"Date: {latest_date.date()}")
    print("Weights:", weights)
    print("Prices:", prices)
    print("MA:", current_ma)
    print("Returns:", current_ret)
    
    # Check logic manually for one case
    # Example: QQQM
    t = 'QQQM'
    print(f"\nVerifying {t}:")
    print(f"Price: {prices[t]}, MA: {current_ma[t]}")
    trend_adj = 0.10
    if prices[t] > current_ma[t]:
        print(f"Trend: UP (+{trend_adj})")
    else:
        print(f"Trend: DOWN (-{trend_adj})")
        
    print("\nRunning Backtest...")
    portfolio, weights_hist = strategy.run_backtest()
    print("Backtest completed.")
    print("Final Portfolio Value:", portfolio.iloc[-1])
    print("Weights History (tail):")
    print(weights_hist.tail())

if __name__ == "__main__":
    verify()

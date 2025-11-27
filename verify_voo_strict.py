from strategy import RotationStrategy
from data_loader import fetch_data
import pandas as pd

def test_voo_strict():
    print("Testing VOO Strict Constraint...")
    
    # 1. Setup Data
    tickers = ["VOO", "BRK-B", "SPMO", "QQQM"]
    base_weights = {"VOO": 0.4, "BRK-B": 0.2, "SPMO": 0.2, "QQQM": 0.2}
    
    # Mock Data Generation
    print("Generating mock data...")
    dates = pd.date_range(start="2022-01-01", end="2024-01-01", freq="B")
    data = pd.DataFrame(index=dates)
    import numpy as np
    np.random.seed(42)
    
    for ticker in tickers:
        # Random walk
        prices = [100]
        for _ in range(len(dates)-1):
            prices.append(prices[-1] * (1 + np.random.normal(0, 0.01)))
        data[ticker] = prices
        
    if data.empty:
        print("Error: No data generated")
        return

    # 2. Run Strategy
    strategy = RotationStrategy(data, base_weights)
    _, weights_history = strategy.run_backtest()
    
    # 3. Verify VOO Weight
    print(f"\nChecking {len(weights_history)} rotation events...")
    
    failures = 0
    for date, row in weights_history.iterrows():
        voo_weight = row.get('VOO', 0.0)
        # Allow tiny floating point error, but it should be exactly 0.4 after rounding
        if abs(voo_weight - 0.4) > 0.001:
            print(f"FAILURE at {date.date()}: VOO = {voo_weight} (Expected 0.4)")
            failures += 1
            
    if failures == 0:
        print("\nSUCCESS: VOO weight remained at 0.4 for all rotations.")
    else:
        print(f"\nFAILURE: VOO weight deviated in {failures} rotations.")
        exit(1)

if __name__ == "__main__":
    test_voo_strict()

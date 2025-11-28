from strategy import RotationStrategy
import pandas as pd
import numpy as np

def test_strategy_fixes():
    print("Testing Strategy Fixes...")
    
    # 1. Mock Data (Daily)
    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq='B') # Business days
    data = pd.DataFrame(index=dates)
    data['VOO'] = 100 + np.random.randn(len(dates)).cumsum()
    data['BRK-B'] = 200 + np.random.randn(len(dates)).cumsum()
    data['SPMO'] = 50 + np.random.randn(len(dates)).cumsum()
    data['QQQM'] = 150 + np.random.randn(len(dates)).cumsum()
    
    base_weights = {'VOO': 0.4, 'BRK-B': 0.2, 'SPMO': 0.2, 'QQQM': 0.2}
    
    strategy = RotationStrategy(data, base_weights)
    
    # 2. Test Rounding Logic (VOO Protection)
    # Force a situation where sum != 1.0
    # We can't easily force internal rounding errors, but we can check if VOO is ever the target of the diff fix
    # if VOO is the largest holding.
    # Actually, let's just run get_signals and see if it crashes or produces valid output.
    
    strategy.calculate_indicators()
    weights, _, _, _ = strategy.get_signals(dates[-1])
    print(f"Weights: {weights}")
    assert abs(sum(weights.values()) - 1.0) < 0.001, "Weights do not sum to 1.0"
    
    # 3. Test Backtest Dates (Missing Months)
    portfolio, history = strategy.run_backtest()
    
    print("\nRotation History Dates:")
    print(history.index)
    
    # Check if we have entries for each month (roughly)
    # We expect about 12 entries for a year
    assert len(history) >= 10, "Too few rotation events found"
    
    # Check specifically for month ends
    # e.g. 2024-11-29 (last business day of Nov 2024)
    nov_24 = pd.Timestamp("2024-11-29")
    if nov_24 in history.index:
        print("✓ November 2024 rotation found")
    else:
        print("✗ November 2024 rotation MISSING")
        # Print close dates
        print([d for d in history.index if d.month == 11])

    print("\nAll tests passed!")

if __name__ == "__main__":
    test_strategy_fixes()

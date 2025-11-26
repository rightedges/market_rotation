from strategy import RotationStrategy
import pandas as pd

def verify_rounding():
    print("Verifying Rounding Logic...")
    
    # Mock Data
    # We don't need real data to test the rounding logic in get_signals
    # But get_signals needs a dataframe structure.
    
    # Let's create a dummy dataframe
    dates = pd.date_range(start='2023-01-01', periods=100)
    tickers = ['VOO', 'BRK-B', 'SPMO', 'QQQM']
    data = pd.DataFrame(100.0, index=dates, columns=tickers)
    
    base_weights = {'VOO': 0.40, 'BRK-B': 0.30, 'SPMO': 0.15, 'QQQM': 0.15}
    
    strategy = RotationStrategy(data, base_weights)
    strategy.calculate_indicators() # Pre-req
    
    # Test 1: No change (Neutral)
    # If prices = MA and Returns = Benchmark, weights should be base weights.
    # But our logic is strict > or <=.
    # Let's force some values.
    
    # We can't easily force values inside the class without mocking data precisely.
    # But we can check if the output weights are multiples of 0.05.
    
    print("\nRunning Backtest to generate many signals...")
    _, weights_history = strategy.run_backtest()
    
    print("Checking if all weights are multiples of 0.05...")
    all_good = True
    for date, row in weights_history.iterrows():
        for t in tickers:
            w = row[t]
            # Check if multiple of 0.05
            # Allow small float error
            remainder = w % 0.05
            if not (remainder < 1e-9 or abs(remainder - 0.05) < 1e-9):
                print(f"FAIL at {date}: {t} = {w}")
                all_good = False
                
        # Check sum
        total = row.sum()
        if abs(total - 1.0) > 1e-9:
            print(f"FAIL at {date}: Sum = {total}")
            all_good = False
            
    if all_good:
        print("SUCCESS: All weights are multiples of 0.05 and sum to 1.0")
    else:
        print("FAILURE: Rounding logic issues found.")

if __name__ == "__main__":
    verify_rounding()

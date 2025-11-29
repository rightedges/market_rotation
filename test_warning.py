import pandas as pd
from datetime import datetime, timedelta

def check_warning(df_close, period):
    print(f"Testing period: {period}")
    df_clean = df_close.dropna()
    if not df_clean.empty:
        actual_start = df_clean.index[0]
        
        today = datetime.now()
        expected_years = int(period[:-1])
        expected_start = today - timedelta(days=expected_years*365)
        
        print(f"Actual Start: {actual_start}")
        print(f"Expected Start: {expected_start}")
        
        if actual_start > expected_start + timedelta(days=90):
            if isinstance(df_close, pd.Series):
                df_check = df_close.to_frame()
            else:
                df_check = df_close
                
            first_valid_indices = df_check.apply(lambda col: col.first_valid_index())
            latest_start_ticker = first_valid_indices.idxmax()
            latest_date = first_valid_indices.max()
            
            print(f"WARNING: Data shorter than {period}. Start: {latest_date}, Culprit: {latest_start_ticker}")
        else:
            print("No warning.")
    print("-" * 20)

# Mock Data
dates_10y = pd.date_range(end=datetime.now(), periods=252*10, freq='B')
dates_3y = pd.date_range(end=datetime.now(), periods=252*3, freq='B')

# Case 1: Full data
df_full = pd.DataFrame({'A': 1, 'B': 1}, index=dates_10y)
check_warning(df_full, '10y')

# Case 2: Short data (one ticker)
df_short = pd.DataFrame({'A': 1}, index=dates_10y)
df_short['B'] = pd.Series(1, index=dates_3y) # B is short
check_warning(df_short, '10y')

# Case 3: Short data (all tickers)
df_all_short = pd.DataFrame({'A': 1, 'B': 1}, index=dates_3y)
check_warning(df_all_short, '10y')

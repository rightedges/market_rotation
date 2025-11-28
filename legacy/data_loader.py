import yfinance as yf
import pandas as pd

def fetch_data(tickers, period="5y"):
    """
    Fetches historical data for the given tickers.
    """
    data = yf.download(tickers, period=period, group_by='ticker', auto_adjust=True)
    
    # If only one ticker, yfinance returns a DataFrame with columns like 'Open', 'Close'
    # If multiple, it returns a MultiIndex columns. We want to standardize.
    
    # Flatten the MultiIndex if necessary or restructure to have a clean Close dataframe
    # We primarily need 'Close' for this strategy.
    
    # Let's extract just the Close prices for simplicity in one DataFrame
    # But we might need OHLC for other things? The strategy only mentions Price (Close).
    
    df_close = pd.DataFrame()
    
    if len(tickers) == 1:
        ticker = tickers[0]
        df_close[ticker] = data['Close']
    else:
        for ticker in tickers:
            try:
                # yfinance structure can be tricky. 
                # If group_by='ticker', data[ticker] is a DataFrame.
                df_close[ticker] = data[ticker]['Close']
            except KeyError:
                # Fallback if structure is different (sometimes yf changes)
                # If auto_adjust=True, 'Close' is the adjusted close.
                pass
                
    return df_close

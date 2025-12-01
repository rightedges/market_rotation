import yfinance as yf
from flask_login import current_user
from datetime import datetime
import pandas as pd
from functools import lru_cache

def check_symbol(symbol):
    """
    Verifies if a stock symbol is available on Yahoo Finance.
    Returns True if valid, False otherwise.
    """
    try:
        ticker = yf.Ticker(symbol)
        # Try fetching 1 day of history to verify existence
        hist = ticker.history(period="1d")
        if not hist.empty:
            return True
        # If history is empty, it likely doesn't exist
        return False
    except Exception as e:
        print(f"Yahoo Finance check failed: {e}")
        # If we hit a rate limit or other error, we can't verify.
        # Better to allow it than block valid symbols due to API limits.
        # The user will just see 0 price if it's truly invalid.
        return True

def get_yahoo_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        # Get latest data
        # history(period='1d') returns a DataFrame
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            # Timestamp from the index (Date)
            timestamp = hist.index[-1].strftime('%Y-%m-%d %H:%M:%S')
            return {'price': price, 'timestamp': timestamp}
    except Exception as e:
        print(f"Error fetching Yahoo price for {symbol}: {e}")
    return None

def get_prices(symbols):
    """
    Fetches prices for multiple symbols using Yahoo Finance.
    """
    results = {}
    
    for sym in symbols:
        res = get_yahoo_price(sym)
        if res:
            results[sym] = res
            
    return results

@lru_cache(maxsize=32)
def get_historical_data(symbols, period='2y'):
    """
    Fetches historical close prices for a list of symbols.
    Uses yfinance.
    Cached to improve performance.
    """
    if not symbols:
        return None
        
    # Convert tuple back to list if needed (lru_cache requires hashable args)
    if isinstance(symbols, tuple):
        symbols = list(symbols)
        
    try:
        # Use yfinance for historical data as it's more reliable for bulk history on free tier
        # Ensure VOO is included for benchmark if not present
        fetch_symbols = list(set(symbols))
        
        # Handle custom periods that yfinance doesn't support directly (15y, 20y)
        kwargs = {'progress': False, 'auto_adjust': True}
        if period in ['15y', '20y']:
            years = int(period[:-1])
            start_date = (datetime.now() - pd.DateOffset(years=years)).strftime('%Y-%m-%d')
            kwargs['start'] = start_date
        else:
            kwargs['period'] = period
        
        # yf.download returns a MultiIndex DataFrame if multiple tickers
        # We just want the 'Close' column
        df = yf.download(fetch_symbols, **kwargs)
        
        if df.empty:
            return None
            
        # If multiple tickers, 'Close' is a DataFrame. If single, it's a Series.
        if 'Close' in df:
            df_close = df['Close']
        else:
            # Fallback for single ticker or different structure
            df_close = df
            if isinstance(df_close, pd.DataFrame) and len(df_close.columns) == 1:
                df_close.columns = fetch_symbols

        return df_close
    except Exception as e:
        print(f"Error fetching historical data: {e}")
        return None

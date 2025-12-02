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
def _fetch_historical_data(symbols, period='2y', start_date=None, end_date=None):
    """
    Internal cached function to fetch historical data.
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
        
        if start_date:
            kwargs['start'] = start_date
            if end_date:
                kwargs['end'] = end_date
        elif period in ['15y', '20y']:
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

def get_historical_data(symbols, period='2y', start_date=None, end_date=None):
    """
    Public function to get historical data.
    Calls cached fetcher and then ensures data is up to date.
    """
    # Call cached internal function
    df_close = _fetch_historical_data(symbols, period, start_date, end_date)
    
    if df_close is None or df_close.empty:
        return df_close
        
    # Patch: Check if we need to append latest data (if cached data is stale)
    # This logic must run every time, so it's outside the cache
    last_date = df_close.index[-1]
    today = datetime.now().date()
    
    # If last data is older than today, try to fetch latest price
    if last_date.date() < today:
        # We need a copy to avoid modifying the cached object
        df_close = df_close.copy()
        
        latest_prices = {}
        latest_timestamp = None
        
        # Determine symbols to check
        if isinstance(df_close, pd.Series):
            check_symbols = [symbols[0]] if isinstance(symbols, tuple) else symbols
        else:
            check_symbols = df_close.columns.tolist()
        
        for sym in check_symbols:
            # Use existing single-symbol fetcher which uses ticker.history(period='1d')
            price_data = get_yahoo_price(sym)
            if price_data:
                try:
                    ts = datetime.strptime(price_data['timestamp'], '%Y-%m-%d %H:%M:%S')
                    if ts.date() > last_date.date():
                        latest_prices[sym] = price_data['price']
                        if latest_timestamp is None or ts > latest_timestamp:
                            latest_timestamp = ts
                except (ValueError, TypeError):
                    continue
        
        if latest_prices and latest_timestamp:
            new_date = pd.Timestamp(latest_timestamp).normalize()
            
            if new_date > last_date:
                if isinstance(df_close, pd.Series):
                    # Handle Series
                    sym = check_symbols[0]
                    if sym in latest_prices:
                        val = latest_prices[sym]
                        new_row = pd.Series([val], index=[new_date])
                        new_row.name = df_close.name
                        df_close = pd.concat([df_close, new_row])
                else:
                    # Handle DataFrame
                    new_row = pd.Series(index=df_close.columns, dtype='float64')
                    for sym, price in latest_prices.items():
                        if sym in new_row.index:
                            new_row[sym] = price
                    
                    # Append to DataFrame
                    df_close.loc[new_date] = new_row

    return df_close

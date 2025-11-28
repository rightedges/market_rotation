import yfinance as yf

def test_symbol(symbol):
    print(f"Testing {symbol}...")
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        print(f"History empty? {hist.empty}")
        print(hist)
    except Exception as e:
        print(f"Error: {e}")

test_symbol("AAPL")
test_symbol("QQQM")

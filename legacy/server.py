from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from auth_manager import authenticate_user, register_user
from portfolio_manager import load_user_data, save_user_data, save_portfolio
from strategy import RotationStrategy
from data_loader import fetch_data
import pandas as pd
import json
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Routes ---

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    username = session.get('username')
    portfolio, config = load_user_data(username)
    
    # Calculate data for dashboard
    tickers = list(portfolio.keys())
    
    # Get relaxed constraint option
    relaxed_param = request.args.get('relaxed', 'false').lower()
    relaxed = relaxed_param == 'true'
    
    # Get backtest period from config
    backtest_period = config.get('backtest_period', '5y')
    
    # Fetch data (cached)
    # Ensure VOO is included for benchmark comparison
    fetch_tickers = list(set(tickers + ['VOO']))
    
    try:
        df_close = fetch_data(fetch_tickers, period=backtest_period)
        if df_close.empty:
            raise ValueError("No data")
            
        strategy = RotationStrategy(df_close, portfolio, relaxed_constraint=relaxed)
        strategy.calculate_indicators()
        
        latest_date = df_close.index[-1]
        current_weights, prices, ma, ret_3m = strategy.get_signals(latest_date)
        
        # Prepare data for template
        holdings = []
        for t in tickers:
            trend = "Uptrend" if prices.get(t, 0) > ma.get(t, 0) else "Downtrend"
            rel_perf = ret_3m.get(t, 0) - ret_3m.get('VOO', 0)
            rel_signal = "Outperform" if rel_perf > 0 else "Underperform"
            if t == 'VOO': rel_signal = "Benchmark"
            
            holdings.append({
                "ticker": t,
                "price": f"{prices.get(t, 0):.2f}",
                "ma": f"{ma.get(t, 0):.2f}",
                "trend": trend,
                "ret_3m": f"{ret_3m.get(t, 0):.1%}",
                "rel_perf": f"{rel_perf:+.1%}",
                "rel_signal": rel_signal,
                "target_weight": f"{current_weights.get(t, 0):.1%}",
                "base_weight": portfolio.get(t, 0) # Raw float for editing
            })
            
        # Backtest for chart
        portfolio_series, weights_history = strategy.run_backtest()
        
        # Benchmark (VOO) Series
        if 'VOO' in df_close.columns:
            voo_prices = df_close['VOO'].loc[portfolio_series.index]
            # Normalize to start at 10000
            voo_series = (voo_prices / voo_prices.iloc[0]) * 10000
            # Fill NaNs
            voo_series = voo_series.fillna(method='ffill').fillna(0)
            benchmark_values = voo_series.values.tolist()
        else:
            benchmark_values = []

        # Sanitize portfolio series
        portfolio_series = portfolio_series.fillna(method='ffill').fillna(0)

        chart_data = {
            "labels": portfolio_series.index.strftime('%Y-%m-%d').tolist(),
            "values": portfolio_series.values.tolist(),
            "benchmark_values": benchmark_values
        }
        
        # Calculate Metrics
        total_return = (portfolio_series.iloc[-1] / portfolio_series.iloc[0]) - 1
        days = (portfolio_series.index[-1] - portfolio_series.index[0]).days
        cagr = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
        
        # Max Drawdown
        rolling_max = portfolio_series.cummax()
        drawdown = (portfolio_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        metrics = {
            "total_return": f"{total_return:.1%}",
            "cagr": f"{cagr:.1%}",
            "max_drawdown": f"{max_drawdown:.1%}"
        }
        
        # Process Rotation History
        # weights_history is a DataFrame with dates as index and tickers as columns
        rotation_history = []
        # Sort descending by date
        weights_history = weights_history.sort_index(ascending=False)
        
        for date, row in weights_history.iterrows():
            entry = {"date": date.strftime('%Y-%m-%d')}
            # Format weights
            for t in tickers:
                entry[t] = f"{row.get(t, 0):.1%}"
            rotation_history.append(entry)
        
        return render_template('index.html', 
                             username=username, 
                             holdings=holdings, 
                             chart_data=json.dumps(chart_data, allow_nan=False),
                             latest_date=latest_date.strftime('%Y-%m-%d'),
                             metrics=metrics,
                             rotation_history=rotation_history,
                             tickers=tickers,
                             relaxed=relaxed,
                             backtest_period=backtest_period)
                             
    except Exception as e:
        return render_template('index.html', username=username, error=str(e))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        action = request.form['action']
        
        if action == 'login':
            if authenticate_user(username, password):
                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error="Invalid credentials")
        elif action == 'register':
            success, msg = register_user(username, password)
            if success:
                return render_template('login.html', success=msg)
            else:
                return render_template('login.html', error=msg)
                
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/save_portfolio', methods=['POST'])
def save_portfolio_route():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
        
    data = request.json
    username = session.get('username')
    
    # Validate weights sum to 1.0? Or just save.
    # Data comes as {ticker: weight, ...}
    # Convert weights to float
    try:
        new_weights = {k: float(v) for k, v in data.items()}
        if save_portfolio(username, new_weights):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Save failed"})
    except ValueError:
        return jsonify({"success": False, "message": "Invalid number format"})

@app.route('/api/update_settings', methods=['POST'])
def update_settings():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
        
    data = request.json
    username = session.get('username')
    
    # Load current data
    holdings, config = load_user_data(username)
    
    # Update config
    if 'backtest_period' in data:
        config['backtest_period'] = data['backtest_period']
        
    if save_user_data(username, holdings, config):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Save failed"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8501, debug=True)

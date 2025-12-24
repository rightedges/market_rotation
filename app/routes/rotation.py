from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Portfolio, Holding
from app.services.market_data import get_historical_data
from app.services.strategy import RotationStrategy
import pandas as pd
from datetime import datetime, timedelta

bp = Blueprint('rotation', __name__, url_prefix='/portfolio')

@bp.route('/<int:id>/rotation')
@login_required
def analysis(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
        
    holdings = portfolio.holdings.all()
    if not holdings:
        flash('Add stocks to your portfolio before running analysis.')
        return redirect(url_for('portfolio.view', id=id))
        
    # Prepare data for strategy
    tickers = [h.symbol for h in holdings]
    
    # Get benchmark from query params or DB
    benchmark_input = request.args.get('benchmark')
    if benchmark_input:
        portfolio.analysis_benchmark_ticker = benchmark_input
        db.session.commit()
        benchmark_ticker = benchmark_input
    elif portfolio.analysis_benchmark_ticker:
        benchmark_ticker = portfolio.analysis_benchmark_ticker
    else:
        benchmark_ticker = None

    # Validate benchmark is in holdings, else default to VOO if present, else first holding
    if not benchmark_ticker or benchmark_ticker not in tickers:
        if 'VOO' in tickers:
            benchmark_ticker = 'VOO'
        elif tickers:
            benchmark_ticker = tickers[0]
        else:
            benchmark_ticker = 'VOO' # Fallback if no holdings (though we check earlier)

    # Ensure benchmark is in the list for fetching data
    fetch_tickers = list(set(tickers + [benchmark_ticker]))
    
    # Get backtest period from query params, default to 5y
    period = request.args.get('period', '5y')
    if period not in ['5y', '10y', '15y', '20y']:
        period = '5y'
    
    # Calculate fixed start date to ensure consistency with optimization script
    # Default to 5y if not specified or invalid
    years = 5
    if period.endswith('y'):
        try:
            years = int(period[:-1])
        except ValueError:
            pass
            
    # Use a fixed end date (today) and start date (today - years)
    # This avoids "yfinance" relative period discrepancies
    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=years*365)
    
    start_date_str = start_date_dt.strftime('%Y-%m-%d')
    # We don't pass end_date to allow fetching up to the absolute latest available
    
    # Fetch historical data
    # Convert list to tuple for lru_cache
    # Pass start_date explicitly
    df_close = get_historical_data(tuple(fetch_tickers), period=period, start_date=start_date_str)
    
    if df_close is None or df_close.empty:
        flash('Failed to fetch historical data. Please try again later.')
        return redirect(url_for('portfolio.view', id=id))
        
    # Check data sufficiency
    # Drop rows where any ticker is NaN to find the effective start date for a full portfolio backtest
    df_close = df_close.dropna()
    
    if not df_close.empty:
        actual_start = df_close.index[0]
        
        # Calculate expected start
        today = datetime.now()
        expected_years = int(period[:-1]) # '5y' -> 5
        expected_start = today - timedelta(days=expected_years*365)
        
        # Allow buffer (e.g. 90 days) for holidays/weekend differences/delayed IPOs
        if actual_start > expected_start + timedelta(days=90):
            # Find the culprit
            # df_close might be a Series if only 1 ticker, convert to DF to be safe
            if isinstance(df_close, pd.Series):
                df_check = df_close.to_frame()
            else:
                df_check = df_close
                
            first_valid_indices = df_check.apply(lambda col: col.first_valid_index())
            latest_start_ticker = first_valid_indices.idxmax()
            latest_date = first_valid_indices.max()
            
            flash(f"Warning: Historical data is shorter than {period}. Backtest starts from {latest_date.strftime('%Y-%m-%d')} due to limited history for {latest_start_ticker}.", "warning")
        
    # Current weights (from DB target_percentage or equal weight?)
    # Strategy needs base_weights to know what to adjust.
    # If we want to suggest new weights based on "current" state, we should use current target_percentage.
    # If target_percentage is 0, maybe default to equal weight?
    
    # Always use Equal Weights for analysis to be independent of portfolio's current allocation
    # This ensures consistent results for the same set of stocks.
    base_weights = {}
    if holdings:
        equal_weight = 1.0 / len(holdings)
        for h in holdings:
            base_weights[h.symbol] = equal_weight
            
    # Check for reset request
    if request.args.get('reset_benchmark_weight'):
        portfolio.analysis_benchmark_weight = None
        db.session.commit()
        return redirect(url_for('rotation.analysis', 
                              id=id, 
                              period=period, 
                              benchmark=benchmark_ticker,
                              relaxed='true' if request.args.get('relaxed') == 'true' else 'false',
                              trend_weight=request.args.get('trend_weight'),
                              rel_weight=request.args.get('rel_weight')
                              ))

    # Check for benchmark weight override
    benchmark_weight_input = request.args.get('benchmark_weight')
    
    if benchmark_weight_input:
        try:
            override_weight = float(benchmark_weight_input) / 100.0
            if 0 <= override_weight <= 1.0:
                # Save to DB
                portfolio.analysis_benchmark_weight = override_weight
                db.session.commit()
                
                # Override benchmark weight
                base_weights[benchmark_ticker] = override_weight
        except ValueError:
            pass
    elif portfolio.analysis_benchmark_weight is not None:
        # Load from DB if not provided in args
        override_weight = portfolio.analysis_benchmark_weight
        base_weights[benchmark_ticker] = override_weight
        
    # If we have an override (either from args or DB), redistribute remaining
    if benchmark_weight_input or portfolio.analysis_benchmark_weight is not None:
        override_weight = base_weights[benchmark_ticker]
        remaining_target = 1.0 - override_weight
        
        # Calculate sum of other weights
        other_tickers = [t for t in base_weights if t != benchmark_ticker]
        current_other_sum = sum(base_weights[t] for t in other_tickers)
        
        if current_other_sum > 0:
            for t in other_tickers:
                base_weights[t] = (base_weights[t] / current_other_sum) * remaining_target
        elif other_tickers:
             # If others sum to 0, distribute equally
             equal_weight = remaining_target / len(other_tickers)
             for t in other_tickers:
                 base_weights[t] = equal_weight
            
    # Initialize Strategy
    # Check for relaxed mode input or load from DB
    relaxed_input = request.args.get('relaxed')
    if relaxed_input is not None:
        relaxed = relaxed_input.lower() == 'true'
        portfolio.analysis_relaxed_mode = relaxed
        db.session.commit()
    elif portfolio.analysis_relaxed_mode is not None:
        relaxed = portfolio.analysis_relaxed_mode
    else:
        relaxed = False

    # Check for trend weight input or load from DB
    trend_weight_input = request.args.get('trend_weight')
    if trend_weight_input:
        try:
            trend_weight = float(trend_weight_input) / 100.0
            portfolio.analysis_trend_weight = trend_weight
            db.session.commit()
        except ValueError:
            trend_weight = portfolio.analysis_trend_weight or 0.10
    else:
        trend_weight = portfolio.analysis_trend_weight or 0.10

    # Check for relative strength weight input or load from DB
    rel_weight_input = request.args.get('rel_weight')
    if rel_weight_input:
        try:
            rel_weight = float(rel_weight_input) / 100.0
            portfolio.analysis_relative_strength_weight = rel_weight
            db.session.commit()
        except ValueError:
            rel_weight = portfolio.analysis_relative_strength_weight or 0.05
    else:
        rel_weight = portfolio.analysis_relative_strength_weight or 0.05
    
    strategy = RotationStrategy(df_close, base_weights, trend_adj=trend_weight, rel_adj=rel_weight, benchmark_ticker=benchmark_ticker, relaxed_constraint=relaxed)
    strategy.calculate_indicators()
    
    latest_date = df_close.index[-1]
    suggested_weights, prices, ma, ret_3m = strategy.get_signals(latest_date)
    
    # Prepare display data
    analysis_data = []
    for h in holdings:
        t = h.symbol
        trend = "Uptrend" if prices.get(t, 0) > ma.get(t, 0) else "Downtrend"
        rel_perf = ret_3m.get(t, 0) - ret_3m.get(benchmark_ticker, 0)
        rel_signal = "Outperform" if rel_perf > 0 else "Underperform"
        if t == benchmark_ticker: rel_signal = "Benchmark"
        
        analysis_data.append({
            "symbol": t,
            "current_price": prices.get(t, 0),
            "current_target": f"{base_weights.get(t, 0):.1%}",
            "current_raw": base_weights.get(t, 0), # Raw float for comparison
            "suggested_weight": f"{suggested_weights.get(t, 0):.1%}",
            "suggested_raw": suggested_weights.get(t, 0), # For form submission
            "trend": trend,
            "rel_signal": rel_signal,
            "ret_3m": f"{ret_3m.get(t, 0):.1%}"
        })
        
    # Run Backtest
    portfolio_series_daily, weights_history = strategy.run_backtest()
    
    # Resample to Monthly (End of Month) to reduce noise for Chart
    portfolio_series = portfolio_series_daily.resample('M').last()
    
    # Benchmark Series for Chart
    benchmark_values = []
    if benchmark_ticker in df_close.columns:
        bench_prices = df_close[benchmark_ticker].resample('M').last()
        # Align with portfolio series index
        bench_prices = bench_prices.reindex(portfolio_series.index, method='ffill')
        
        # Normalize to start at 10000
        if not bench_prices.empty and bench_prices.iloc[0] > 0:
            bench_series = (bench_prices / bench_prices.iloc[0]) * 10000
            bench_series = bench_series.ffill().fillna(0)
            benchmark_values = bench_series.values.tolist()
        
    portfolio_series = portfolio_series.ffill().fillna(0)
    
    chart_data = {
        "labels": portfolio_series.index.strftime('%Y-%m-%d').tolist(),
        "values": portfolio_series.values.tolist(),
        "benchmark_values": benchmark_values,
        "benchmark_ticker": benchmark_ticker
    }
    
    # Calculate Metrics using Daily Data via shared strategy method
    metrics_data = RotationStrategy.calculate_metrics(portfolio_series_daily)
    
    metrics = {
        "total_return": f"{metrics_data['total_return']:.2%}",
        "cagr": f"{metrics_data['cagr']:.2%}",
        "max_drawdown": f"{metrics_data['max_drawdown']:.2%}",
        "winning_streak": f"{metrics_data['winning_streak']} mo",
        "losing_streak": f"{metrics_data['losing_streak']} mo"
    }
    
    # Debug Logging
    print("\n--- DEBUG ROTATION ANALYSIS ---")
    print(f"Tickers: {tickers}")
    print(f"Benchmark: {benchmark_ticker}")
    print(f"Base Weights: {base_weights}")
    print(f"Data Shape: {df_close.shape}")
    print(f"Data Start: {df_close.index[0]}")
    print(f"Data End: {df_close.index[-1]}")
    print(f"Backtest Start (idx 63): {portfolio_series_daily.index[0]}")
    print(f"Backtest End: {portfolio_series_daily.index[-1]}")
    print(f"Metrics: {metrics}")
    print("-------------------------------\n")

    # Calculate Historical Rotations
    rotation_data = []
    rotation_tickers = []
    
    if not weights_history.empty:
        # Use weights_history directly (it already contains month-end trading dates)
        monthly_weights = weights_history
        rotation_tickers = sorted(monthly_weights.columns.tolist())
        
        # Sort by date descending
        monthly_weights = monthly_weights.sort_index(ascending=False)
        
        for date, weights in monthly_weights.iterrows():
            row = {'date': date.strftime('%Y-%m-%d')}
            # Get portfolio value for this date
            if date in portfolio_series_daily.index:
                row['value'] = portfolio_series_daily.loc[date]
            else:
                row['value'] = 0.0
                
            for ticker in rotation_tickers:
                row[ticker] = weights.get(ticker, 0)
            rotation_data.append(row)
            
        # Calculate gain/loss between rebalancing
        for i in range(len(rotation_data) - 1):
            current_val = rotation_data[i]['value']
            prev_val = rotation_data[i+1]['value']
            if prev_val > 0:
                rotation_data[i]['gain_loss'] = (current_val / prev_val) - 1
            else:
                rotation_data[i]['gain_loss'] = 0
        if rotation_data:
            rotation_data[-1]['gain_loss'] = 0 # No previous rebalance for first entry
    
    # Calculate current benchmark weight for display
    current_bench_weight = int(base_weights.get(benchmark_ticker, 0) * 100)
    
    # Available benchmarks for dropdown
    # Only include portfolio holdings as requested
    available_benchmarks = sorted(tickers)
    
    import json
    return render_template('rotation/analysis.html', 
                         portfolio=portfolio, 
                         analysis_data=analysis_data, 
                         latest_date=latest_date.strftime('%Y-%m-%d'),
                         start_date=portfolio_series_daily.index[0].strftime('%Y-%m-%d'),
                         end_date=portfolio_series_daily.index[-1].strftime('%Y-%m-%d'),
                         relaxed=relaxed,
                         period=period,
                         benchmark_ticker=benchmark_ticker,
                         chart_data=json.dumps(chart_data),
                         metrics=metrics,
                         rotation_data=rotation_data,
                         rotation_tickers=rotation_tickers,
                         benchmark_weight_input=benchmark_weight_input,
                         current_bench_weight=current_bench_weight,
                         available_benchmarks=available_benchmarks,
                         trend_weight=int(trend_weight * 100),
                         rel_weight=int(rel_weight * 100))

@bp.route('/<int:id>/apply_rotation', methods=['POST'])
@login_required
def apply(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
        
    # Update target percentages
    holdings = portfolio.holdings.all()
    
    for h in holdings:
        # Form field name: weight_{symbol}
        weight_str = request.form.get(f'weight_{h.symbol}')
        if weight_str:
            try:
                weight = float(weight_str)
                # Convert 0.45 to 45.0
                h.target_percentage = weight * 100.0
            except ValueError:
                pass
                
    db.session.commit()
    flash('Target allocation updated based on rotation analysis.')
    return redirect(url_for('portfolio.rebalance', id=id))

@bp.route('/<int:id>/fixed_analysis', methods=['GET', 'POST'])
@login_required
def fixed_analysis(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
        
    holdings = portfolio.holdings.all()
    if not holdings:
        flash('Add stocks to your portfolio before running analysis.')
        return redirect(url_for('portfolio.view', id=id))
        
    if request.method == 'POST':
        # Update target percentages
        for h in holdings:
            weight_str = request.form.get(f'weight_{h.symbol}')
            if weight_str:
                try:
                    weight = float(weight_str)
                    h.target_percentage = weight
                except ValueError:
                    pass
        db.session.commit()
        action = request.form.get('action', 'analyze')

        if action == 'apply':
             flash('Target allocation updated based on fixed analysis.')
             return redirect(url_for('portfolio.rebalance', id=id))
        else:
             flash('Portfolio allocations updated.')
             # Redirect to GET to refresh analysis with new weights
             return redirect(url_for('rotation.fixed_analysis', id=id, 
                                   benchmark=request.args.get('benchmark'), 
                                   frequency=request.args.get('frequency'),
                                   period=request.args.get('period')))
        
    tickers = [h.symbol for h in holdings]
    
    # Get benchmark
    benchmark_input = request.args.get('benchmark')
    if benchmark_input:
        portfolio.analysis_benchmark_ticker = benchmark_input
        db.session.commit()
        benchmark_ticker = benchmark_input
    elif portfolio.analysis_benchmark_ticker:
        benchmark_ticker = portfolio.analysis_benchmark_ticker
    else:
        benchmark_ticker = 'VOO' if 'VOO' in tickers else (tickers[0] if tickers else None)

    # Get frequency
    frequency_input = request.args.get('frequency')
    if frequency_input and frequency_input in ['monthly', 'quarterly', 'semiannual', 'annual']:
        portfolio.fixed_analysis_frequency = frequency_input
        db.session.commit()
        frequency = frequency_input
    else:
        frequency = portfolio.fixed_analysis_frequency or 'quarterly'
        
    # Get period
    period = request.args.get('period', '5y')
    if period not in ['5y', '10y', '15y', '20y']:
        period = '5y'
        
    # Fetch data
    fetch_tickers = list(set(tickers + [benchmark_ticker])) if benchmark_ticker else tickers
    df_close = get_historical_data(tuple(fetch_tickers), period=period)
    
    if df_close is None or df_close.empty:
        flash('Failed to fetch historical data.')
        return redirect(url_for('portfolio.view', id=id))
        
    # Base weights from current targets
    base_weights = {}
    total_target = sum(h.target_percentage for h in holdings)
    for h in holdings:
        if total_target > 0:
            base_weights[h.symbol] = h.target_percentage / 100.0
        else:
            base_weights[h.symbol] = 1.0 / len(holdings)
            
    # Run Strategy
    from app.services.strategy import FixedRebalanceStrategy, RotationStrategy
    strategy = FixedRebalanceStrategy(df_close, base_weights, frequency=frequency)
    portfolio_series, weights_history = strategy.run_backtest()
    
    # Calculate Metrics
    metrics = RotationStrategy.calculate_metrics(portfolio_series)
    
    # Format metrics
    metrics['total_return'] = f"{metrics['total_return']:.1%}"
    metrics['cagr'] = f"{metrics['cagr']:.1%}"
    metrics['max_drawdown'] = f"{metrics['max_drawdown']:.1%}"
    metrics['winning_streak'] = f"{metrics['winning_streak']} mo"
    metrics['losing_streak'] = f"{metrics['losing_streak']} mo"
    
    # Prepare Chart Data
    portfolio_series_monthly = portfolio_series.resample('M').last().ffill().fillna(0)
    
    benchmark_values = []
    if benchmark_ticker and benchmark_ticker in df_close.columns:
        bench_prices = df_close[benchmark_ticker].resample('M').last()
        bench_prices = bench_prices.reindex(portfolio_series_monthly.index, method='ffill')
        if not bench_prices.empty and bench_prices.iloc[0] > 0:
            bench_series = (bench_prices / bench_prices.iloc[0]) * 10000
            bench_series = bench_series.ffill().fillna(0)
            benchmark_values = bench_series.values.tolist()
            
    chart_data = {
        "labels": portfolio_series_monthly.index.strftime('%Y-%m-%d').tolist(),
        "values": portfolio_series_monthly.values.tolist(),
        "benchmark_values": benchmark_values,
        "benchmark_ticker": benchmark_ticker
    }
    
    # Prepare Historical Rotations Data
    rotation_data = []
    rotation_tickers = []
    
    if not weights_history.empty:
        rotation_tickers = sorted(weights_history.columns.tolist())
        # Sort by date descending
        weights_history = weights_history.sort_index(ascending=False)
        
        for date, weights in weights_history.iterrows():
            row = {'date': date.strftime('%Y-%m-%d')}
            # Get portfolio value for this date
            if date in portfolio_series.index:
                row['value'] = portfolio_series.loc[date]
            else:
                row['value'] = 0.0
                
            for ticker in rotation_tickers:
                row[ticker] = weights.get(ticker, 0)
            rotation_data.append(row)

        # Calculate gain/loss between rebalancing
        for i in range(len(rotation_data) - 1):
            current_val = rotation_data[i]['value']
            prev_val = rotation_data[i+1]['value']
            if prev_val > 0:
                rotation_data[i]['gain_loss'] = (current_val / prev_val) - 1
            else:
                rotation_data[i]['gain_loss'] = 0
        if rotation_data:
            rotation_data[-1]['gain_loss'] = 0
    
    import json
    return render_template('rotation/fixed_analysis.html',
                         portfolio=portfolio,
                         holdings=holdings,
                         metrics=metrics,
                         chart_data=json.dumps(chart_data),
                         period=period,
                         frequency=frequency,
                         benchmark_ticker=benchmark_ticker,
                         available_benchmarks=sorted(tickers),
                         rotation_data=rotation_data,
                         rotation_tickers=rotation_tickers,
                         start_date=portfolio_series.index[0].strftime('%Y-%m-%d') if not portfolio_series.empty else '',
                         end_date=portfolio_series.index[-1].strftime('%Y-%m-%d') if not portfolio_series.empty else '')


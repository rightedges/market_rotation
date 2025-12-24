import pandas as pd
import itertools
from app.services.market_data import get_historical_data
from app.services.strategy import RotationStrategy

from datetime import datetime, timedelta

def optimize():
    tickers = ['VOO', 'QQQ', 'SPMO', 'BRK-B']
    benchmark_ticker = 'VOO'
    period = '10y'
    
    # Calculate fixed start date (same as web app)
    years = 10
    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=years*365)
    start_date_str = start_date_dt.strftime('%Y-%m-%d')
    
    print(f"Fetching {period} historical data for {tickers} (Start: {start_date_str})...")
    df_close = get_historical_data(tuple(tickers), period=period, start_date=start_date_str)
    
    if df_close is None or df_close.empty:
        print("Failed to fetch data.")
        return

    # Align with web app logic: Drop rows with NaNs to ensure consistent start date
    df_close = df_close.dropna()

    # Benchmark Allocation: 0% (Equal Weight) up to 40%
    # Including 0% allows testing the "Equal Footing" scenario recommended for Relaxed Mode.
    benchmark_allocs = [0.0] + [x / 100.0 for x in range(10, 45, 5)]
    
    # Trend Weight: 5% to 15% (0.05 to 0.15), step 0.05
    trend_weights = [x / 100.0 for x in range(5, 20, 5)]
    
    # Rel Strength Weight: 5% to 15% (0.05 to 0.15), step 0.05
    rel_weights = [x / 100.0 for x in range(5, 20, 5)]
    
    # Modes
    modes = [False, True] # False = Strict, True = Relaxed
    
    results = []
    
    total_combinations = len(benchmark_allocs) * len(trend_weights) * len(rel_weights) * len(modes)
    print(f"Testing {total_combinations} combinations...")
    
    count = 0
    best_return = -float('inf')
    best_params = None
    
    for bench_w, trend_w, rel_w, relaxed in itertools.product(benchmark_allocs, trend_weights, rel_weights, modes):
        count += 1
        if count % 10 == 0:
            print(f"Processed {count}/{total_combinations}...")
            
        # Construct Base Weights
        base_weights = {}
        if bench_w == 0:
            # Equal Weight for all assets (The "Clear" logic)
            eq_w = 1.0 / len(tickers)
            for t in tickers:
                base_weights[t] = eq_w
        else:
            # Specified Benchmark Weight
            base_weights[benchmark_ticker] = bench_w
            remaining = 1.0 - bench_w
            other_tickers = [t for t in tickers if t != benchmark_ticker]
            other_w = remaining / len(other_tickers)
            for t in other_tickers:
                base_weights[t] = other_w
            
        # Initialize Strategy
        strategy = RotationStrategy(
            df_close, 
            base_weights, 
            trend_adj=trend_w, 
            rel_adj=rel_w, 
            benchmark_ticker=benchmark_ticker, 
            relaxed_constraint=relaxed
        )
        
        try:
            portfolio_series, _ = strategy.run_backtest()
            
            if not portfolio_series.empty:
                # Calculate Metrics using shared method
                metrics = RotationStrategy.calculate_metrics(portfolio_series)
                
                total_return = metrics['total_return']
                cagr = metrics['cagr']
                max_drawdown = metrics['max_drawdown']
                
                results.append({
                    'benchmark_ticker': benchmark_ticker,
                    'benchmark_alloc': bench_w,
                    'trend_w': trend_w,
                    'rel_w': rel_w,
                    'relaxed': relaxed,
                    'return': total_return,
                    'cagr': cagr,
                    'max_drawdown': max_drawdown,
                    'mdd_start': metrics['mdd_start'],
                    'mdd_end': metrics['mdd_end']
                })
                
                if total_return > best_return:
                    best_return = total_return
                    best_params = results[-1]
                    print(f"New Best: {best_return:.2%} (CAGR: {cagr:.2%}, DD: {max_drawdown:.2%}, MDD Period: {metrics['mdd_start'].strftime('%Y-%m') if metrics['mdd_start'] else 'N/A'} to {metrics['mdd_end'].strftime('%Y-%m') if metrics['mdd_end'] else 'N/A'}) | Params: {best_params}")
        except Exception as e:
            print(f"Error in run: {e}")
            continue

    print("\n" + "="*30)
    print("OPTIMIZATION COMPLETE")
    print("="*30)
    
    if best_params:
        print(f"Highest Return: {best_params['return']:.2%}")
        print(f"CAGR: {best_params['cagr']:.2%}")
        print(f"Max Drawdown: {best_params['max_drawdown']:.2%}")
        print(f"Max Drawdown Period: {best_params['mdd_start'].strftime('%Y-%m') if best_params['mdd_start'] else 'N/A'} to {best_params['mdd_end'].strftime('%Y-%m') if best_params['mdd_end'] else 'N/A'}")
        print("Optimal Parameters:")
        print(f"  Benchmark: {best_params['benchmark_ticker']}")
        print(f"  Benchmark Allocation: {f'{best_params['benchmark_alloc']:.0%}' if best_params['benchmark_alloc'] > 0 else 'Equal Weight'}")
        print(f"  Trend Weight: {best_params['trend_w']:.0%}")
        print(f"  Relative Strength Weight: {best_params['rel_w']:.0%}")
        print(f"  Mode: {'Relaxed' if best_params['relaxed'] else 'Strict'}")
        
        # Top 5
        print("\nTop 5 Configurations:")
        sorted_results = sorted(results, key=lambda x: x['return'], reverse=True)[:5]
        for i, res in enumerate(sorted_results):
            mode_str = 'Relaxed' if res['relaxed'] else 'Strict'
            bench_alloc_str = f"{res['benchmark_alloc']:.0%}" if res['benchmark_alloc'] > 0 else "Equal"
            print(f"{i+1}. Return: {res['return']:.2%} | CAGR: {res['cagr']:.2%} | DD: {res['max_drawdown']:.2%} | MDD: {res['mdd_start'].strftime('%Y-%m') if res['mdd_start'] else 'N/A'} to {res['mdd_end'].strftime('%Y-%m') if res['mdd_end'] else 'N/A'} | Bench ({res['benchmark_ticker']}): {bench_alloc_str}, Trend: {res['trend_w']:.0%}, Rel: {res['rel_w']:.0%}, Mode: {mode_str}")
    else:
        print("No results found.")

if __name__ == "__main__":
    optimize()

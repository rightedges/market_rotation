import pandas as pd
import itertools
import numpy as np
from app.services.market_data import get_historical_data
from app.services.strategy import FixedRebalanceStrategy, RotationStrategy
from datetime import datetime, timedelta

def generate_weights(n_assets, step=0.05):
    """
    Generates weight combinations for n_assets that sum to 1.0.
    step: increment (e.g. 0.05 for 5%)
    """
    steps = int(1.0 / step)
    # Generate all combinations of integers that sum to 'steps'
    # This is equivalent to distributing 'steps' items into 'n_assets' bins
    
    for c in itertools.combinations_with_replacement(range(n_assets), steps):
        # c is a tuple of indices where we increment the count
        # e.g. for 3 assets, 2 steps: (0, 0) -> asset 0 gets 2
        # (0, 1) -> asset 0 gets 1, asset 1 gets 1
        counts = [0] * n_assets
        for index in c:
            counts[index] += 1
        
        weights = [round(x * step, 2) for x in counts]
        yield weights

def optimize():
    tickers = ['VOO', 'QQQ', 'SPMO', 'BRK-B']
    period = '10y'
    frequency = 'quarterly'
    
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
    
    print(f"Data range: {df_close.index[0].date()} to {df_close.index[-1].date()}")
    
    results = []
    
    # Generate weights
    step_size = 0.05
    weight_combinations = list(generate_weights(len(tickers), step=step_size))
    total_combinations = len(weight_combinations)
    
    print(f"Testing {total_combinations} weight combinations (Step: {step_size:.0%})...")
    
    count = 0
    best_return = -float('inf')
    best_config = None
    
    for weights_list in weight_combinations:
        count += 1
        if count % 100 == 0:
            print(f"Processed {count}/{total_combinations}...")
            
        # Map weights to tickers
        target_weights = {tickers[i]: weights_list[i] for i in range(len(tickers))}
        
        # Initialize Strategy
        strategy = FixedRebalanceStrategy(
            df_close, 
            target_weights, 
            frequency=frequency
        )
        
        try:
            portfolio_series, _ = strategy.run_backtest()
            
            if not portfolio_series.empty:
                # Calculate Metrics
                metrics = RotationStrategy.calculate_metrics(portfolio_series)
                
                total_return = metrics['total_return']
                cagr = metrics['cagr']
                max_drawdown = metrics['max_drawdown']
                
                # Calculate Sharpe Ratio (approximate, assuming risk-free rate = 0)
                daily_returns = portfolio_series.pct_change().dropna()
                if daily_returns.std() > 0:
                    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
                else:
                    sharpe = 0.0
                
                results.append({
                    'weights': target_weights,
                    'return': total_return,
                    'cagr': cagr,
                    'max_drawdown': max_drawdown,
                    'win_streak': metrics['winning_streak'],
                    'lose_streak': metrics['losing_streak'],
                    'sharpe': sharpe
                })
                
                if total_return > best_return:
                    best_return = total_return
                    best_config = results[-1]
                    # Format weights for print
                    w_str = ", ".join([f"{k}: {v:.0%}" for k, v in target_weights.items()])
                    print(f"New Best: {best_return:.2%} (CAGR: {cagr:.2%}, DD: {max_drawdown:.2%}, Win/Lose: {metrics['winning_streak']}/{metrics['losing_streak']} mo) | Weights: {w_str}")
                    
        except Exception as e:
            print(f"Error in run: {e}")
            continue

    print("\n" + "="*30)
    print("OPTIMIZATION COMPLETE")
    print("="*30)
    
    if best_config:
        print(f"Highest Return: {best_config['return']:.2%}")
        print(f"CAGR: {best_config['cagr']:.2%}")
        print(f"Max Drawdown: {best_config['max_drawdown']:.2%}")
        print(f"Longest Win/Lose Streak: {best_config['win_streak']}/{best_config['lose_streak']} mo")
        print(f"Sharpe Ratio: {best_config['sharpe']:.2f}")
        print("Optimal Weights:")
        for t, w in best_config['weights'].items():
            print(f"  {t}: {w:.0%}")
        
        # Top 5 by Return
        print("\nTop 5 Configurations (by Return):")
        sorted_by_return = sorted(results, key=lambda x: x['return'], reverse=True)[:5]
        for i, res in enumerate(sorted_by_return):
            w_str = ", ".join([f"{k}: {v:.0%}" for k, v in res['weights'].items()])
            print(f"{i+1}. Return: {res['return']:.2%} | CAGR: {res['cagr']:.2%} | DD: {res['max_drawdown']:.2%} | Streak W/L: {res['win_streak']}/{res['lose_streak']} mo | Weights: {w_str}")

        # Top 5 by Sharpe
        print("\nTop 5 Configurations (by Sharpe Ratio):")
        sorted_by_sharpe = sorted(results, key=lambda x: x['sharpe'], reverse=True)[:5]
        for i, res in enumerate(sorted_by_sharpe):
            w_str = ", ".join([f"{k}: {v:.0%}" for k, v in res['weights'].items()])
            print(f"{i+1}. Sharpe: {res['sharpe']:.2f} | Return: {res['return']:.2%} | DD: {res['max_drawdown']:.2%} | Streak W/L: {res['win_streak']}/{res['lose_streak']} mo | Weights: {w_str}")

    else:
        print("No results found.")

if __name__ == "__main__":
    optimize()

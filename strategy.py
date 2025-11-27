import pandas as pd
import numpy as np

class RotationStrategy:
    def __init__(self, data, base_weights, trend_adj=0.10, rel_adj=0.05, benchmark_ticker='VOO'):
        """
        data: DataFrame of Close prices
        base_weights: dict {ticker: weight}
        trend_adj: float (e.g., 0.10 for 10%)
        rel_adj: float (e.g., 0.05 for 5%)
        benchmark_ticker: str
        """
        self.data = data
        self.base_weights = base_weights
        self.trend_adj = trend_adj
        self.rel_adj = rel_adj
        self.benchmark_ticker = benchmark_ticker
        self.tickers = list(base_weights.keys())
        
    def calculate_indicators(self):
        """
        Calculates 50-day MA and 3-month returns.
        """
        df = self.data.copy()
        
        # 50-day Moving Average
        self.ma_50 = df.rolling(window=50).mean()
        
        # 3-month Return (approx 63 trading days)
        self.returns_3m = df.pct_change(periods=63)
        
        return self.ma_50, self.returns_3m

    def get_signals(self, date):
        """
        Returns target weights for a specific date.
        """
        if date not in self.data.index:
            # Find closest previous date
            idx = self.data.index.get_indexer([date], method='pad')[0]
            if idx == -1:
                return self.base_weights # Default if no data
            date = self.data.index[idx]
            
        current_prices = self.data.loc[date]
        current_ma = self.ma_50.loc[date]
        current_3m = self.returns_3m.loc[date]
        
        benchmark_3m = current_3m.get(self.benchmark_ticker, 0.0)
        
        # 1. Separate Benchmark and Others
        benchmark_weight = self.base_weights.get(self.benchmark_ticker, 0.0)
        other_weights = {}
        
        for ticker, base_weight in self.base_weights.items():
            if ticker == self.benchmark_ticker:
                continue
                
            weight = base_weight
            
            # Trend Filter
            # If price > 50MA -> Overweight
            if current_prices[ticker] > current_ma[ticker]:
                weight += self.trend_adj
            else:
                weight -= self.trend_adj
                
            # Relative Performance
            if current_3m[ticker] > benchmark_3m:
                weight += self.rel_adj
            else:
                weight -= self.rel_adj
            
            other_weights[ticker] = max(0.0, weight)
            
        # 3. Normalize others to sum to (1.0 - benchmark_weight)
        target_other_sum = 1.0 - benchmark_weight
        current_other_sum = sum(other_weights.values())
        
        if current_other_sum > 0:
            for t in other_weights:
                other_weights[t] = (other_weights[t] / current_other_sum) * target_other_sum
        else:
            # Fallback: distribute evenly or proportionally to base?
            # Let's revert to base weights for others
            base_other_sum = sum(self.base_weights[t] for t in other_weights)
            if base_other_sum > 0:
                for t in other_weights:
                    other_weights[t] = (self.base_weights[t] / base_other_sum) * target_other_sum
            
        # 4. Combine and Round
        final_weights = {self.benchmark_ticker: benchmark_weight}
        
        # Round others to nearest 5%
        # Note: This might make the sum drift from 1.0. We need to fix it within the "others" group.
        
        rounded_others = {}
        for t, w in other_weights.items():
            rounded_others[t] = round(w / 0.05) * 0.05
            
        # Let's put them all together first
        final_weights.update(rounded_others)
        
        # Fix floating point
        for t in final_weights:
            final_weights[t] = round(final_weights[t], 2)
            
        # Check total sum
        total_sum = sum(final_weights.values())
        diff = round(1.0 - total_sum, 2)
        
        if diff != 0:
            # Adjust one of the OTHER assets (not benchmark)
            candidates = list(other_weights.keys())
            if candidates:
                # Add to the largest holding among others
                max_ticker = max(candidates, key=lambda t: final_weights[t])
                final_weights[max_ticker] += diff
                final_weights[max_ticker] = round(final_weights[max_ticker], 2)
            else:
                # If only benchmark exists (edge case), adjust benchmark
                final_weights[self.benchmark_ticker] += diff
                
        return final_weights, current_prices, current_ma, current_3m

    def run_backtest(self):
        """
        Runs the monthly rotation backtest.
        """
        self.calculate_indicators()
        
        # Resample to monthly (end of month) - Get actual last trading day
        # Group by Year-Month and take the last index
        monthly_dates = self.data.groupby([self.data.index.year, self.data.index.month]).apply(lambda x: x.index[-1])
        # The above returns a multi-index series, we just want the values (dates)
        rebalance_dates = set(monthly_dates)
        
        portfolio_values = []
        weights_history = []
        
        # Start with initial capital
        capital = 10000.0
        current_holdings = {t: 0.0 for t in self.tickers} # Units held
        
        # We need to iterate through time.
        # Efficient way: Calculate weights at each month end, 
        # then apply returns for the next month.
        
        # Let's create a daily series for portfolio value
        daily_dates = self.data.index
        portfolio_series = pd.Series(index=daily_dates, dtype=float)
        portfolio_series.iloc[0] = capital # Initial value
        
        # Initial weights (Base)
        current_weights = self.base_weights.copy()
        
        # We start from the point where we have enough data (50 days + 63 days)
        start_idx = 63 
        
        # To make it simple and vector-ish but accurate:
        # We can just iterate monthly dates.
        
        # Create a DataFrame to store weights over time
        weights_df = pd.DataFrame(index=daily_dates, columns=self.tickers)
        
        # Forward fill weights between rebalance dates?
        # Actually, we need to calculate the daily value based on holdings.
        
        # Let's simulate step-by-step for accuracy
        
        cash = capital
        units = {t: 0.0 for t in self.tickers}
        
        # Initial buy
        start_date = daily_dates[start_idx]
        
        # We need to handle the period before start_date
        # Let's just start the backtest from start_date
        
        # Get initial weights based on signals at start_date
        initial_weights, _, _, _ = self.get_signals(start_date)
        
        # Buy
        prices = self.data.loc[start_date]
        for t in self.tickers:
            alloc = cash * initial_weights[t]
            units[t] = alloc / prices[t]
        cash = 0 # Fully invested
        
        portfolio_history = {}
        
        for i in range(start_idx, len(daily_dates)):
            date = daily_dates[i]
            price = self.data.loc[date]
            
            # Calculate current portfolio value
            val = sum(units[t] * price[t] for t in self.tickers) + cash
            portfolio_history[date] = val
            
            # Check if rebalance needed (Month End)
            if date in rebalance_dates:
                # Calculate new target weights
                target_weights, _, _, _ = self.get_signals(date)
                
                # Rebalance
                # Sell everything (conceptually) and rebuy to match weights
                # In practice: just adjust.
                
                # New allocations
                for t in self.tickers:
                    alloc = val * target_weights[t]
                    units[t] = alloc / price[t]
                    
                # Store weights for visualization
                weights_df.loc[date] = target_weights
        
        # Forward fill weights for visualization (optional, or just show dots)
        weights_df = weights_df.dropna()
        
        portfolio_series = pd.Series(portfolio_history)
        return portfolio_series, weights_df


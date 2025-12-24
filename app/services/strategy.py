import pandas as pd
import numpy as np

class RotationStrategy:
    def __init__(self, data, base_weights, trend_adj=0.10, rel_adj=0.05, benchmark_ticker='VOO', relaxed_constraint=False):
        """
        data: DataFrame of Close prices
        base_weights: dict {ticker: weight}
        trend_adj: float (e.g., 0.10 for 10%)
        rel_adj: float (e.g., 0.05 for 5%)
        benchmark_ticker: str
        relaxed_constraint: bool (If True, benchmark weight is not fixed)
        """
        self.data = data
        self.base_weights = base_weights
        self.trend_adj = trend_adj
        self.rel_adj = rel_adj
        self.benchmark_ticker = benchmark_ticker
        self.relaxed_constraint = relaxed_constraint
        self.tickers = sorted(list(base_weights.keys()))
        
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
                return self.base_weights, {}, {}, {} # Default if no data
            date = self.data.index[idx]
            
        current_prices = self.data.loc[date]
        current_ma = self.ma_50.loc[date]
        current_3m = self.returns_3m.loc[date]
        
        benchmark_3m = current_3m.get(self.benchmark_ticker, 0.0)
        
        target_weights = {}
        
        if self.relaxed_constraint:
            # Relaxed Mode: Treat all tickers (including benchmark) equally for adjustments
            raw_weights = {}
            
            # Iterate over sorted tickers for deterministic behavior
            for ticker in self.tickers:
                base_weight = self.base_weights[ticker]
                weight = base_weight
                
                # Trend Filter
                trend_val = current_prices.get(ticker, 0)
                ma_val = current_ma.get(ticker, 0)
                if trend_val > ma_val:
                    weight += self.trend_adj
                else:
                    weight -= self.trend_adj
                    
                # Relative Performance (Benchmark vs Benchmark is 0 diff, so no adj)
                if ticker != self.benchmark_ticker:
                    ret_val = current_3m.get(ticker, 0)
                    if ret_val > benchmark_3m:
                        weight += self.rel_adj
                    else:
                        weight -= self.rel_adj
                
                raw_weights[ticker] = max(0.0, weight)
                
            # Normalize ALL weights to sum to 1.0
            total_raw = sum(raw_weights.values())
            if total_raw > 0:
                for t in raw_weights:
                    target_weights[t] = raw_weights[t] / total_raw
            else:
                target_weights = self.base_weights.copy()
                
        else:
            # Strict Mode: Fix Benchmark, Adjust Others
            benchmark_weight = self.base_weights.get(self.benchmark_ticker, 0.0)
            other_weights = {}
            
            # Iterate over sorted tickers for deterministic behavior
            for ticker in self.tickers:
                if ticker == self.benchmark_ticker:
                    continue
                    
                base_weight = self.base_weights[ticker]
                weight = base_weight
                
                # Trend Filter
                if current_prices.get(ticker, 0) > current_ma.get(ticker, 0):
                    weight += self.trend_adj
                else:
                    weight -= self.trend_adj
                    
                # Relative Performance
                if current_3m.get(ticker, 0) > benchmark_3m:
                    weight += self.rel_adj
                else:
                    weight -= self.rel_adj
                
                other_weights[ticker] = max(0.0, weight)
                
            # Normalize others to sum to (1.0 - benchmark_weight)
            target_other_sum = 1.0 - benchmark_weight
            current_other_sum = sum(other_weights.values())
            
            if current_other_sum > 0:
                for t in other_weights:
                    other_weights[t] = (other_weights[t] / current_other_sum) * target_other_sum
            else:
                # Fallback
                base_other_sum = sum(self.base_weights[t] for t in other_weights)
                if base_other_sum > 0:
                    for t in other_weights:
                        other_weights[t] = (self.base_weights[t] / base_other_sum) * target_other_sum
            
            target_weights = {self.benchmark_ticker: benchmark_weight}
            target_weights.update(other_weights)
            
        # Rounding Logic (Common)
        final_weights = {}
        for t, w in target_weights.items():
            final_weights[t] = round(w / 0.05) * 0.05
            
        # Fix floating point
        for t in final_weights:
            final_weights[t] = round(final_weights[t], 2)
            
        # Check total sum
        total_sum = sum(final_weights.values())
        diff = round(1.0 - total_sum, 2)
        
        if diff != 0:
            # Adjust largest holding
            candidates = list(final_weights.keys())
            if not self.relaxed_constraint and self.benchmark_ticker in candidates and len(candidates) > 1:
                 # In strict mode, try not to touch benchmark if possible
                 candidates = [c for c in candidates if c != self.benchmark_ticker]
            
            if candidates:
                # Use (weight, ticker) tuple for deterministic tie-breaking
                # This ensures that if weights are equal, the result depends on ticker string (alphabetical)
                # rather than dictionary iteration order.
                max_ticker = max(candidates, key=lambda t: (final_weights[t], t))
                final_weights[max_ticker] += diff
                final_weights[max_ticker] = round(final_weights[max_ticker], 2)
            elif self.benchmark_ticker in final_weights:
                 final_weights[self.benchmark_ticker] += diff
                 
        return final_weights, current_prices, current_ma, current_3m

    def run_backtest(self):
        """
        Runs the monthly rotation backtest.
        """
        self.calculate_indicators()
        
        # Resample to monthly (end of month) - Get actual last trading day
        monthly_dates = self.data.groupby([self.data.index.year, self.data.index.month]).apply(lambda x: x.index[-1])
        rebalance_dates = set(monthly_dates)
        
        portfolio_values = []
        weights_history = []
        
        capital = 10000.0
        current_holdings = {t: 0.0 for t in self.tickers} # Units held
        
        daily_dates = self.data.index
        portfolio_series = pd.Series(index=daily_dates, dtype=float)
        portfolio_series.iloc[0] = capital
        
        start_idx = 63 
        weights_df = pd.DataFrame(index=daily_dates, columns=self.tickers)
        
        cash = capital
        units = {t: 0.0 for t in self.tickers}
        
        start_date = daily_dates[start_idx]
        initial_weights, _, _, _ = self.get_signals(start_date)
        
        # Record initial weights
        weights_df.loc[start_date] = initial_weights
        
        prices = self.data.loc[start_date]
        for t in self.tickers:
            alloc = cash * initial_weights[t]
            units[t] = alloc / prices[t]
        cash = 0 
        
        portfolio_history = {}
        
        for i in range(start_idx, len(daily_dates)):
            date = daily_dates[i]
            price = self.data.loc[date]
            
            val = sum(units[t] * price[t] for t in self.tickers) + cash
            portfolio_history[date] = val
            
            if date in rebalance_dates:
                target_weights, _, _, _ = self.get_signals(date)
                
                for t in self.tickers:
                    alloc = val * target_weights[t]
                    units[t] = alloc / price[t]
                    
                weights_df.loc[date] = target_weights
        
        weights_df = weights_df.dropna()
        portfolio_series = pd.Series(portfolio_history)
        return portfolio_series, weights_df

    @staticmethod
    def calculate_metrics(portfolio_series):
        """
        Calculates performance metrics for a portfolio series.
        Returns a dictionary with 'total_return', 'cagr', 'max_drawdown',
        'winning_streak', and 'losing_streak'.
        """
        if portfolio_series.empty:
            return {
                'total_return': 0.0,
                'cagr': 0.0,
                'max_drawdown': 0.0,
                'winning_streak': 0,
                'losing_streak': 0
            }
            
        # Total Return
        total_return = (portfolio_series.iloc[-1] / portfolio_series.iloc[0]) - 1
        
        # CAGR
        days = (portfolio_series.index[-1] - portfolio_series.index[0]).days
        cagr = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
        
        # Max Drawdown
        rolling_max = portfolio_series.cummax()
        drawdown = (portfolio_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Monthly Streaks
        monthly_series = portfolio_series.resample('M').last()
        monthly_returns = monthly_series.pct_change().dropna()
        
        win_streak = 0
        max_win_streak = 0
        lose_streak = 0
        max_lose_streak = 0
        
        for ret in monthly_returns:
            if ret > 0:
                win_streak += 1
                lose_streak = 0
                max_win_streak = max(max_win_streak, win_streak)
            elif ret < 0:
                lose_streak += 1
                win_streak = 0
                max_lose_streak = max(max_lose_streak, lose_streak)
        
        return {
            'total_return': total_return,
            'cagr': cagr,
            'max_drawdown': max_drawdown,
            'winning_streak': max_win_streak,
            'losing_streak': max_lose_streak
        }

class FixedRebalanceStrategy:
    def __init__(self, data, target_weights, frequency='quarterly'):
        """
        data: DataFrame of Close prices
        target_weights: dict {ticker: weight} (Should sum to 1.0)
        frequency: str ('monthly', 'quarterly', 'semiannual', 'annual')
        """
        self.data = data
        self.target_weights = target_weights
        self.frequency = frequency.lower()
        self.tickers = sorted(list(target_weights.keys()))
        
    def run_backtest(self):
        """
        Runs the fixed weight rebalancing backtest.
        """
        # Determine rebalancing dates
        if self.frequency == 'monthly':
            rebalance_dates = self.data.groupby([self.data.index.year, self.data.index.month]).apply(lambda x: x.index[-1])
        elif self.frequency == 'quarterly':
            rebalance_dates = self.data.groupby([self.data.index.year, self.data.index.quarter]).apply(lambda x: x.index[-1])
        elif self.frequency == 'semiannual':
            # Custom grouping for semi-annual (approx every 6 months)
            # We can use month // 7 to group 1-6 and 7-12
            rebalance_dates = self.data.groupby([self.data.index.year, (self.data.index.month - 1) // 6]).apply(lambda x: x.index[-1])
        elif self.frequency == 'annual':
            rebalance_dates = self.data.groupby([self.data.index.year]).apply(lambda x: x.index[-1])
        else:
            # Default to quarterly
            rebalance_dates = self.data.groupby([self.data.index.year, self.data.index.quarter]).apply(lambda x: x.index[-1])
            
        rebalance_dates = set(rebalance_dates)
        
        daily_dates = self.data.index
        if len(daily_dates) == 0:
            return pd.Series(), pd.DataFrame()
            
        capital = 10000.0
        portfolio_history = {}
        weights_history = {} # Use dict for sparse storage then convert to DF
        
        # Start from the first available date
        start_date = daily_dates[0]
        
        # Initial Allocation
        units = {t: 0.0 for t in self.tickers}
        prices = self.data.loc[start_date]
        
        # Record initial weights
        weights_history[start_date] = self.target_weights.copy()
        
        for t in self.tickers:
            alloc = capital * self.target_weights.get(t, 0)
            if prices[t] > 0:
                units[t] = alloc / prices[t]
            else:
                units[t] = 0
                
        portfolio_history[start_date] = capital
        
        for i in range(1, len(daily_dates)):
            date = daily_dates[i]
            price = self.data.loc[date]
            
            # Calculate current value
            val = sum(units[t] * price[t] for t in self.tickers)
            portfolio_history[date] = val
            
            # Rebalance if needed
            if date in rebalance_dates:
                # Record rebalancing
                weights_history[date] = self.target_weights.copy()
                
                for t in self.tickers:
                    alloc = val * self.target_weights.get(t, 0)
                    if price[t] > 0:
                        units[t] = alloc / price[t]
                    else:
                        units[t] = 0
                        
        portfolio_series = pd.Series(portfolio_history)
        weights_df = pd.DataFrame.from_dict(weights_history, orient='index')
        return portfolio_series, weights_df


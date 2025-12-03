import os
from app import create_app, db
from app.models import Portfolio, Holding, User
from app.services.strategy import FixedRebalanceStrategy
import pandas as pd
import numpy as np

app = create_app()
app.app_context().push()

# Ensure a test user and portfolio exist
user = User.query.filter_by(username='testuser').first()
if not user:
    user = User(username='testuser')
    user.set_password('test')
    db.session.add(user)
    db.session.commit()

portfolio = Portfolio.query.filter_by(name='Fixed Test Portfolio', owner=user).first()
symbols = ['VOO', 'QQQ', 'BRK-B', 'SPMO']
if not portfolio:
    portfolio = Portfolio(name='Fixed Test Portfolio', type='Test', owner=user)
    db.session.add(portfolio)
    db.session.commit()
    # Add holdings
    for sym in symbols:
        holding = Holding(symbol=sym, units=10, target_percentage=25.0, portfolio=portfolio)
        db.session.add(holding)
    db.session.commit()

# Mock Data
dates = pd.date_range(start='2020-01-01', end='2023-01-01', freq='B')
data = pd.DataFrame(index=dates)
for sym in ['VOO', 'QQQ', 'BRK-B', 'SPMO']:
    # Random walk
    data[sym] = 100 * (1 + np.random.randn(len(dates)) * 0.01).cumprod()

# Test Strategy Logic
target_weights = {'VOO': 0.25, 'QQQ': 0.25, 'BRK-B': 0.25, 'SPMO': 0.25}
strategy = FixedRebalanceStrategy(data, target_weights, frequency='quarterly')
portfolio_series, _ = strategy.run_backtest()

print(f"Backtest run. Start Value: {portfolio_series.iloc[0]:.2f}, End Value: {portfolio_series.iloc[-1]:.2f}")
print(f"Total Return: {(portfolio_series.iloc[-1]/portfolio_series.iloc[0] - 1):.2%}")

# Test Route
client = app.test_client()
# Login
with client.session_transaction() as sess:
    sess['_user_id'] = user.id

resp = client.get(f'/portfolio/{portfolio.id}/fixed_analysis')
if resp.status_code == 200:
    print("Fixed Analysis Route: OK")
else:
    print(f"Fixed Analysis Route: Failed ({resp.status_code})")

# Test Frequency Change
resp = client.get(f'/portfolio/{portfolio.id}/fixed_analysis?frequency=monthly')
if resp.status_code == 200:
    portfolio = Portfolio.query.get(portfolio.id)
    if portfolio.fixed_analysis_frequency == 'monthly':
        print("Frequency Persistence: OK")
    else:
        print(f"Frequency Persistence: Failed (Expected monthly, got {portfolio.fixed_analysis_frequency})")
else:
    print(f"Frequency Change Route: Failed ({resp.status_code})")

# Test Allocation Update
new_weights = {
    f'weight_{symbols[0]}': 30.0,
    f'weight_{symbols[1]}': 20.0,
    f'weight_{symbols[2]}': 25.0,
    f'weight_{symbols[3]}': 25.0
}
resp = client.post(f'/portfolio/{portfolio.id}/fixed_analysis', data=new_weights, follow_redirects=True)
if resp.status_code == 200:
    # Verify DB update
    h = Holding.query.filter_by(portfolio_id=portfolio.id, symbol=symbols[0]).first()
    if h.target_percentage == 30.0:
        print("Allocation Update: OK")
    else:
        print(f"Allocation Update: Failed (Expected 30.0, got {h.target_percentage})")
else:
    print(f"Allocation Update Route: Failed ({resp.status_code})")


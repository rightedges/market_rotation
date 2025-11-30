from app import create_app, db
from app.models import User, Portfolio

app = create_app()

with app.app_context():
    # Create a dummy user and portfolio if not exists
    user = User.query.filter_by(username='test_persistence').first()
    if not user:
        user = User(username='test_persistence')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
    portfolio = Portfolio.query.filter_by(name='Test Portfolio', owner=user).first()
    if not portfolio:
        portfolio = Portfolio(name='Test Portfolio', owner=user)
        db.session.add(portfolio)
        db.session.commit()
        
    print(f"Initial Benchmark Ticker: {portfolio.analysis_benchmark_ticker}")
    print(f"Initial Relaxed Mode: {portfolio.analysis_relaxed_mode}")
    
    # Update settings
    portfolio.analysis_benchmark_ticker = 'SPY'
    portfolio.analysis_relaxed_mode = True
    db.session.commit()
    
    # Reload
    db.session.refresh(portfolio)
    print(f"Updated Benchmark Ticker: {portfolio.analysis_benchmark_ticker}")
    print(f"Updated Relaxed Mode: {portfolio.analysis_relaxed_mode}")
    
    assert portfolio.analysis_benchmark_ticker == 'SPY'
    assert portfolio.analysis_relaxed_mode == True
    
    print("Persistence verification successful!")

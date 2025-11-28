import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from app import create_app, db
from app.models import User, Portfolio, Holding
from config import Config
from app.services.strategy import RotationStrategy

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False

class RotationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()
        
        # Create user and portfolio
        self.user = User(username='testuser')
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.commit()
        
        self.portfolio = Portfolio(name='Test Portfolio', type='TFSA', owner=self.user)
        db.session.add(self.portfolio)
        db.session.commit()
        
        # Add holdings
        h1 = Holding(symbol='VOO', units=10, portfolio=self.portfolio, target_percentage=40.0)
        h2 = Holding(symbol='QQQ', units=10, portfolio=self.portfolio, target_percentage=30.0)
        h3 = Holding(symbol='SPY', units=10, portfolio=self.portfolio, target_percentage=30.0)
        db.session.add_all([h1, h2, h3])
        db.session.commit()
        
        self.client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'password'
        })

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('app.routes.rotation.get_historical_data')
    def test_rotation_route(self, mock_get_data):
        # Mock data: 100 days of data
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        data = {
            'VOO': np.linspace(100, 110, 100),
            'QQQ': np.linspace(300, 330, 100), # Stronger uptrend
            'SPY': np.linspace(400, 410, 100)
        }
        df = pd.DataFrame(data, index=dates)
        mock_get_data.return_value = df
        
        response = self.client.get(f'/portfolio/{self.portfolio.id}/rotation')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Market Rotation Analysis', response.data)
        self.assertIn(b'QQQ', response.data)
        # Check for historical rotation table headers
        self.assertIn(b'Historical Rotations', response.data)
        self.assertIn(b'<th>VOO</th>', response.data)

    @patch('app.routes.rotation.get_historical_data')
    def test_rotation_period_selection(self, mock_get_data):
        # Mock data
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        data = {
            'VOO': np.linspace(100, 110, 100),
            'QQQ': np.linspace(100, 110, 100),
            'SPY': np.linspace(100, 110, 100)
        }
        df = pd.DataFrame(data, index=dates)
        mock_get_data.return_value = df
        
        # Test 10y period
        response = self.client.get(f'/portfolio/{self.portfolio.id}/rotation?period=10y')
        self.assertEqual(response.status_code, 200)
        mock_get_data.assert_called_with(unittest.mock.ANY, period='10y')

    def test_strategy_logic(self):
        # Create mock data
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        data = {
            'VOO': np.linspace(100, 105, 100), # +5%
            'QQQ': np.linspace(100, 120, 100), # +20% (Outperform)
            'SPY': np.linspace(100, 102, 100)  # +2% (Underperform)
        }
        df = pd.DataFrame(data, index=dates)
        
        base_weights = {'VOO': 0.4, 'QQQ': 0.3, 'SPY': 0.3}
        
        strategy = RotationStrategy(df, base_weights, relaxed_constraint=False)
        strategy.calculate_indicators()
        weights, _, _, _ = strategy.get_signals(dates[-1])
        
        # Verify Backtest runs
        portfolio_series, weights_history = strategy.run_backtest()
        self.assertFalse(portfolio_series.empty)
        self.assertFalse(weights_history.empty)
        
        # QQQ should increase (Trend Up + Outperform VOO)
        # SPY should decrease (Trend Up but Underperform VOO)
        
        self.assertGreater(weights['QQQ'], 0.3)
        self.assertLess(weights['SPY'], 0.3)
        self.assertEqual(weights['VOO'], 0.4) # Strict mode fixes benchmark

    def test_apply_rotation(self):
        # Test applying new weights
        response = self.client.post(f'/portfolio/{self.portfolio.id}/apply_rotation', data={
            'weight_VOO': '0.40',
            'weight_QQQ': '0.45',
            'weight_SPY': '0.15'
        }, follow_redirects=True)
        
        self.assertIn(b'Target allocation updated', response.data)
        
        # Verify DB update
        h_qqq = Holding.query.filter_by(symbol='QQQ', portfolio_id=self.portfolio.id).first()
        self.assertEqual(h_qqq.target_percentage, 45.0)

    def test_caching(self):
        from app.services.market_data import get_historical_data
        
        # Clear cache first
        get_historical_data.cache_clear()
        
        with patch('yfinance.download') as mock_download:
            # Mock return value
            dates = pd.date_range(end=pd.Timestamp.now(), periods=10)
            data = {'VOO': np.linspace(100, 110, 10)}
            df = pd.DataFrame(data, index=dates)
            mock_download.return_value = df
            
            # First call
            get_historical_data(('VOO',), period='2y')
            self.assertEqual(mock_download.call_count, 1)
            
            # Second call (should be cached)
            get_historical_data(('VOO',), period='2y')
            self.assertEqual(mock_download.call_count, 1)
            
            # Different args (should call again)
            get_historical_data(('QQQ',), period='2y')
            self.assertEqual(mock_download.call_count, 2)

if __name__ == '__main__':
    unittest.main()

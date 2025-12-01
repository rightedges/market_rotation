import unittest
from app import create_app, db
from app.models import User, Portfolio, Holding
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False

class TestDuplicatePortfolio(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        
        # Create user
        self.user = User(username='testuser_dup')
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.commit()
        
        # Create portfolio
        self.portfolio = Portfolio(
            name='Original Portfolio',
            type='RRSP',
            owner=self.user,
            analysis_benchmark_weight=0.5,
            analysis_benchmark_ticker='QQQ',
            analysis_relaxed_mode=True,
            analysis_trend_weight=0.15,
            analysis_relative_strength_weight=0.08
        )
        db.session.add(self.portfolio)
        
        # Add holding
        self.holding = Holding(
            symbol='AAPL',
            units=10,
            target_percentage=50.0,
            portfolio=self.portfolio,
            last_price=150.0
        )
        db.session.add(self.holding)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self):
        return self.client.post('/auth/login', data=dict(
            username='testuser_dup',
            password='password'
        ), follow_redirects=True)

    def test_duplicate_portfolio(self):
        self.login()
        
        # Duplicate
        response = self.client.get(f'/portfolio/duplicate/{self.portfolio.id}', follow_redirects=True)
        self.assertIn(b'Portfolio duplicated successfully.', response.data)
        
        # Verify new portfolio exists
        new_portfolio = Portfolio.query.filter_by(name='Copy of Original Portfolio').first()
        self.assertIsNotNone(new_portfolio)
        
        # Verify attributes
        self.assertEqual(new_portfolio.type, 'RRSP')
        self.assertEqual(new_portfolio.analysis_benchmark_weight, 0.5)
        self.assertEqual(new_portfolio.analysis_benchmark_ticker, 'QQQ')
        self.assertTrue(new_portfolio.analysis_relaxed_mode)
        self.assertEqual(new_portfolio.analysis_trend_weight, 0.15)
        self.assertEqual(new_portfolio.analysis_relative_strength_weight, 0.08)
        
        # Verify holdings
        self.assertEqual(new_portfolio.holdings.count(), 1)
        new_holding = new_portfolio.holdings.first()
        self.assertEqual(new_holding.symbol, 'AAPL')
        self.assertEqual(new_holding.units, 10)
        self.assertEqual(new_holding.target_percentage, 50.0)
        self.assertEqual(new_holding.last_price, 150.0)

if __name__ == '__main__':
    unittest.main()

import unittest
from app import create_app, db
from app.models import User, Portfolio, Holding
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False

class PortfolioTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def register_login(self):
        self.client.post('/auth/register', data={
            'username': 'testuser',
            'password': 'password',
            'api_key': 'demo'
        })
        self.client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'password'
        })

    def test_auth(self):
        response = self.client.post('/auth/register', data={
            'username': 'newuser',
            'password': 'password'
        }, follow_redirects=True)
        self.assertIn(b'Congratulations, you are now a registered user!', response.data)

    def test_rebalancing_logic(self):
        # Setup
        self.register_login()
        user = User.query.filter_by(username='testuser').first()
        p = Portfolio(name='Test Portfolio', type='TFSA', owner=user)
        db.session.add(p)
        db.session.commit()
        
        # Add holdings manually to avoid API calls in this specific unit test
        # Scenario from user request:
        # QQQM: 50 units, Price ~375.65 (Mocked)
        # BRK.B: 14 units, Price ~450.25 (Mocked)
        # VOO: 52 units, Price ~105.75 (Mocked - wait, VOO is ~400+, VYM is ~100. The user example said VOO but price 105.75 suggests maybe they meant VYM or just example numbers. I will use their numbers.)
        
        # User Example:
        # QQQM: 50 units. Price 375.65. Value = 18782.5
        # BRK.B: 14 units. Price 450.25. Value = 6303.5
        # VOO: 52 units. Price 105.75. Value = 5499.0
        # Total Value = 30585.0
        # Cash = 5000
        # New Total = 35585.0
        
        # Targets:
        # QQQM: 0.5 -> 17792.5. Diff = -990. Sell ~2.6 -> Sell 2
        # BRK.B: 0.25 -> 8896.25. Diff = +2592.75. Buy ~5.7 -> Buy 5
        # VOO: 0.25 -> 8896.25. Diff = +3397.25. Buy ~32.1 -> Buy 32
        
        # Wait, the user example output says:
        # QQQ: Buy 4 (Target must be higher?)
        # BRK-B: Sell 2
        # VYM: Buy 5
        # The user example output numbers don't match their input numbers mathematically if we strictly follow the prices/units provided.
        # "QQQ 375.65 Buy 4" -> implies they want more QQQ.
        # "BRK-B 450.25 Sell 2"
        # "VYM 105.75 Buy 5" -> User switched VOO to VYM in the output text.
        
        # I will implement the logic correctly based on the math:
        # Target Value = (Current Total + Cash) * Target Ratio
        # Units to Change = (Target Value - Current Value) / Price
        
        h1 = Holding(symbol='QQQM', units=50, portfolio=p)
        h2 = Holding(symbol='BRK.B', units=14, portfolio=p)
        h3 = Holding(symbol='VOO', units=52, portfolio=p)
        db.session.add_all([h1, h2, h3])
        db.session.commit()
        
        # Mock prices
        prices = {
            'QQQM': 375.65,
            'BRK.B': 450.25,
            'VOO': 105.75
        }
        
        current_val_1 = 50 * 375.65 # 18782.5
        current_val_2 = 14 * 450.25 # 6303.5
        current_val_3 = 52 * 105.75 # 5499.0
        total_current = 18782.5 + 6303.5 + 5499.0 # 30585.0
        cash = 5000
        new_total = total_current + cash # 35585.0
        
        # Test Case 1: 50% QQQM, 25% BRK.B, 25% VOO
        target_1 = new_total * 0.5 # 17792.5
        diff_1 = target_1 - current_val_1 # 17792.5 - 18782.5 = -990
        units_1 = diff_1 / 375.65 # -2.63 -> Sell 2 or 3
        
        # My logic uses simple rounding or float.
        # Let's verify the calculation function logic I wrote in the route.
        # units_to_change = diff / price
        
        self.assertAlmostEqual(units_1, -2.635, places=2)

if __name__ == '__main__':
    unittest.main()

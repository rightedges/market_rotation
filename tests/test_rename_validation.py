import unittest
from app import create_app, db
from app.models import User, Portfolio
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False

class TestRenameValidation(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        
        # Create user
        self.user = User(username='testuser_ren')
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.commit()
        
        # Create initial portfolio
        self.p1 = Portfolio(name='Portfolio A', type='RRSP', owner=self.user)
        db.session.add(self.p1)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self):
        return self.client.post('/auth/login', data=dict(
            username='testuser_ren',
            password='password'
        ), follow_redirects=True)

    def test_create_duplicate_fail(self):
        self.login()
        # Try to create another 'Portfolio A' (RRSP)
        response = self.client.post('/portfolio/create', data=dict(
            name='Portfolio A',
            type='RRSP'
        ), follow_redirects=True)
        self.assertIn(b'already exists', response.data)
        self.assertEqual(Portfolio.query.count(), 1)

    def test_rename_success(self):
        self.login()
        response = self.client.post(f'/portfolio/rename/{self.p1.id}', data=dict(
            name='Portfolio B',
            type='TFSA'
        ), follow_redirects=True)
        self.assertIn(b'Portfolio renamed successfully', response.data)
        
        p = Portfolio.query.get(self.p1.id)
        self.assertEqual(p.name, 'Portfolio B')
        self.assertEqual(p.type, 'TFSA')

    def test_rename_duplicate_fail(self):
        self.login()
        # Create a second portfolio
        p2 = Portfolio(name='Portfolio B', type='RRSP', owner=self.user)
        db.session.add(p2)
        db.session.commit()
        
        # Try to rename p1 to 'Portfolio B' (RRSP)
        response = self.client.post(f'/portfolio/rename/{self.p1.id}', data=dict(
            name='Portfolio B',
            type='RRSP'
        ), follow_redirects=True)
        self.assertIn(b'already exists', response.data)
        
        # Verify name didn't change
        p = Portfolio.query.get(self.p1.id)
        self.assertEqual(p.name, 'Portfolio A')

    def test_duplicate_fail_if_exists(self):
        self.login()
        # Create 'Copy of Portfolio A' manually first
        p_copy = Portfolio(name='Copy of Portfolio A', type='RRSP', owner=self.user)
        db.session.add(p_copy)
        db.session.commit()
        
        # Try to duplicate p1, which would try to create 'Copy of Portfolio A' again
        response = self.client.get(f'/portfolio/duplicate/{self.p1.id}', follow_redirects=True)
        self.assertIn(b'Cannot duplicate', response.data)

if __name__ == '__main__':
    unittest.main()

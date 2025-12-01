import unittest
from app import create_app, db
from app.models import User
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False # Disable CSRF for testing

class TestChangePassword(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        
        # Create user
        self.user = User(username='testuser_pwd')
        self.user.set_password('old_password')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, username, password):
        return self.client.post('/auth/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def test_change_password_success(self):
        self.login('testuser_pwd', 'old_password')
        response = self.client.post('/auth/change_password', data=dict(
            current_password='old_password',
            new_password='new_password',
            confirm_password='new_password'
        ), follow_redirects=True)
        
        self.assertIn(b'Your password has been updated.', response.data)
        
        # Verify new password works
        self.client.get('/auth/logout', follow_redirects=True)
        response = self.login('testuser_pwd', 'new_password')
        self.assertIn(b'Logout', response.data) # Should be logged in

    def test_change_password_wrong_current(self):
        self.login('testuser_pwd', 'old_password')
        response = self.client.post('/auth/change_password', data=dict(
            current_password='wrong_password',
            new_password='new_password',
            confirm_password='new_password'
        ), follow_redirects=True)
        
        self.assertIn(b'Incorrect current password', response.data)

    def test_change_password_mismatch(self):
        self.login('testuser_pwd', 'old_password')
        response = self.client.post('/auth/change_password', data=dict(
            current_password='old_password',
            new_password='new_password',
            confirm_password='mismatch_password'
        ), follow_redirects=True)
        
        self.assertIn(b'New passwords do not match', response.data)

if __name__ == '__main__':
    unittest.main()

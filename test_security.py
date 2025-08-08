import unittest
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app import app, db
from production_config import config

class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.from_object(config['testing'])
        config['testing'].init_app(self.app)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_malicious_request_blocked(self):
        """Test that a malicious request is blocked by the SecurityManager"""
        response = self.client.get('/?test=<script>alert("XSS")</script>')
        self.assertEqual(response.status_code, 403)

        response = self.client.get('/?test=;cat /etc/passwd')
        self.assertEqual(response.status_code, 403)

    def test_input_sanitization(self):
        """Test that user input is sanitized by the InputValidator"""
        from app import InputValidator
        data = {'test': '<script>alert("XSS")</script><p>Allowed paragraph.</p><a href="javascript:alert(1)">Allowed link.</a>'}
        validator = InputValidator(data)
        validator.sanitize_html('test')
        self.assertEqual(validator.get_sanitized_data()['test'], 'alert("XSS")\nAllowed paragraph.<a>Allowed link.</a>')

    def test_rate_limiter(self):
        """Test that the rate limiter is working correctly"""
        for i in range(5):
            response = self.client.post('/auth/login', data=dict(
                email='demo@maritime.test',
                password='demo123'
            ), follow_redirects=True)

        response = self.client.post('/auth/login', data=dict(
            email='demo@maritime.test',
            password='demo123'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()

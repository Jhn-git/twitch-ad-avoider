"""
Tests for AuthManager OAuth authentication.

Critical security tests for:
- OAuth flow and state validation
- Token encryption/decryption
- Secure token storage
- Authentication state management
"""
import unittest
import json
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open

from src.auth_manager import AuthManager, TOKEN_FILE
from src.exceptions import ValidationError


class TestAuthManager(unittest.TestCase):
    """Test AuthManager security and functionality"""

    def setUp(self):
        """Set up test with mock credentials"""
        self.client_id = "test_client_id_12345"
        self.client_secret = "test_client_secret_67890"

        # Patch TOKEN_FILE to use temp location
        self.temp_token_file = Path("test_auth_token.enc")
        self.token_file_patcher = patch('src.auth_manager.TOKEN_FILE', self.temp_token_file)
        self.token_file_patcher.start()

        # Create auth manager
        with patch.object(AuthManager, 'load_token', return_value=False):
            self.auth = AuthManager(self.client_id, self.client_secret)

    def tearDown(self):
        """Clean up test files"""
        self.token_file_patcher.stop()
        if self.temp_token_file.exists():
            self.temp_token_file.unlink()

    def test_initialization(self):
        """Test AuthManager initializes correctly"""
        self.assertEqual(self.auth.client_id, self.client_id)
        self.assertEqual(self.auth.client_secret, self.client_secret)
        self.assertIsNone(self.auth.access_token)
        self.assertIsNone(self.auth.refresh_token)
        self.assertIsNone(self.auth.username)

    def test_is_authenticated_no_token(self):
        """Test is_authenticated returns False when no token"""
        self.assertFalse(self.auth.is_authenticated())

    def test_is_authenticated_with_valid_token(self):
        """Test is_authenticated returns True with valid token"""
        self.auth.access_token = "test_token"
        self.auth.token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertTrue(self.auth.is_authenticated())

    def test_is_authenticated_with_expired_token(self):
        """Test is_authenticated returns False when token expired"""
        self.auth.access_token = "test_token"
        self.auth.token_expires = datetime.now(timezone.utc) - timedelta(hours=1)
        self.assertFalse(self.auth.is_authenticated())

    def test_get_username_authenticated(self):
        """Test get_username returns username when authenticated"""
        self.auth.access_token = "test_token"
        self.auth.username = "test_user"
        self.auth.token_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        self.assertEqual(self.auth.get_username(), "test_user")

    def test_get_username_not_authenticated(self):
        """Test get_username returns None when not authenticated"""
        self.assertIsNone(self.auth.get_username())

    def test_get_access_token_authenticated(self):
        """Test get_access_token returns token when authenticated"""
        self.auth.access_token = "test_token_123"
        self.auth.token_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        self.assertEqual(self.auth.get_access_token(), "test_token_123")

    def test_get_access_token_not_authenticated(self):
        """Test get_access_token returns None when not authenticated"""
        self.assertIsNone(self.auth.get_access_token())

    def test_oauth_state_generation(self):
        """Test OAuth state is generated securely (security-critical)"""
        with patch('webbrowser.open'), \
             patch.object(AuthManager, '_start_callback_server', return_value=True):

            # Generate state multiple times
            states = []
            for _ in range(5):
                auth = AuthManager(self.client_id, self.client_secret)
                auth.start_oauth_flow()
                states.append(auth.oauth_state)

            # All states should be unique
            self.assertEqual(len(states), len(set(states)))

            # All states should be reasonable length (at least 32 chars)
            for state in states:
                self.assertIsNotNone(state)
                self.assertGreater(len(state), 32)

    def test_encryption_decryption_roundtrip(self):
        """Test token encryption and decryption roundtrip (security-critical)"""
        test_data = "test_token_data_12345"

        # Encrypt
        encrypted = self.auth._encrypt_token_data(test_data)
        self.assertIsInstance(encrypted, bytes)
        self.assertNotEqual(encrypted, test_data.encode())

        # Decrypt
        decrypted = self.auth._decrypt_token_data(encrypted)
        self.assertEqual(decrypted, test_data)

    def test_encryption_key_consistency(self):
        """Test encryption key is consistent across calls"""
        key1 = self.auth._get_encryption_key()
        key2 = self.auth._get_encryption_key()

        self.assertEqual(key1, key2)
        self.assertIsInstance(key1, bytes)
        self.assertGreater(len(key1), 16)  # Should be at least 128-bit

    def test_save_token_no_access_token(self):
        """Test save_token returns False when no access token"""
        result = self.auth.save_token()
        self.assertFalse(result)
        self.assertFalse(self.temp_token_file.exists())

    def test_save_token_success(self):
        """Test save_token saves encrypted data"""
        # Set token data
        self.auth.access_token = "test_access_token"
        self.auth.refresh_token = "test_refresh_token"
        self.auth.username = "test_user"
        self.auth.token_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        # Save
        result = self.auth.save_token()
        self.assertTrue(result)
        self.assertTrue(self.temp_token_file.exists())

        # Verify data is encrypted (not plaintext JSON)
        encrypted_data = self.temp_token_file.read_bytes()
        self.assertNotIn(b"test_access_token", encrypted_data)
        self.assertNotIn(b"test_refresh_token", encrypted_data)
        self.assertNotIn(b"test_user", encrypted_data)

    def test_load_token_no_file(self):
        """Test load_token returns False when no token file"""
        result = self.auth.load_token()
        self.assertFalse(result)

    @patch('src.auth_manager.AuthManager.validate_token')
    def test_load_token_success(self, mock_validate):
        """Test load_token loads and decrypts token"""
        mock_validate.return_value = True

        # Save a token first
        self.auth.access_token = "test_access_token"
        self.auth.refresh_token = "test_refresh_token"
        self.auth.username = "test_user"
        self.auth.token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        self.auth.save_token()

        # Create new auth manager and load
        with patch.object(AuthManager, 'load_token', return_value=True):
            auth2 = AuthManager(self.client_id, self.client_secret)

        # Now manually load
        auth2.load_token()

        # Verify data loaded
        self.assertEqual(auth2.access_token, "test_access_token")
        self.assertEqual(auth2.refresh_token, "test_refresh_token")
        self.assertEqual(auth2.username, "test_user")
        self.assertIsNotNone(auth2.token_expires)

    @patch('src.auth_manager.AuthManager.validate_token')
    def test_load_token_invalid_token(self, mock_validate):
        """Test load_token clears invalid token"""
        mock_validate.return_value = False

        # Save a token
        self.auth.access_token = "test_access_token"
        self.auth.refresh_token = "test_refresh_token"
        self.auth.username = "test_user"
        self.auth.token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        self.auth.save_token()

        # Load with validation failing
        with patch.object(AuthManager, 'logout') as mock_logout:
            result = self.auth.load_token()
            self.assertFalse(result)
            mock_logout.assert_called_once()

    def test_load_token_corrupted_file(self):
        """Test load_token handles corrupted token file"""
        # Write corrupted data
        self.temp_token_file.write_bytes(b"corrupted_data_not_valid_token")

        result = self.auth.load_token()
        self.assertFalse(result)

        # Corrupted file should be removed
        self.assertFalse(self.temp_token_file.exists())

    def test_logout_clears_all_data(self):
        """Test logout clears all authentication data"""
        # Set token data
        self.auth.access_token = "test_access_token"
        self.auth.refresh_token = "test_refresh_token"
        self.auth.username = "test_user"
        self.auth.token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        self.auth.oauth_state = "test_state"
        self.auth.save_token()

        # Logout
        self.auth.logout()

        # Verify all cleared
        self.assertIsNone(self.auth.access_token)
        self.assertIsNone(self.auth.refresh_token)
        self.assertIsNone(self.auth.username)
        self.assertIsNone(self.auth.token_expires)
        self.assertIsNone(self.auth.oauth_state)
        self.assertFalse(self.temp_token_file.exists())

    def test_set_callbacks(self):
        """Test callback functions can be set"""
        success_callback = Mock()
        failure_callback = Mock()

        self.auth.set_callbacks(
            on_success=success_callback,
            on_failure=failure_callback
        )

        self.assertEqual(self.auth.on_auth_success, success_callback)
        self.assertEqual(self.auth.on_auth_failure, failure_callback)

    @patch('src.auth_manager.requests')
    def test_validate_token_success(self, mock_requests):
        """Test validate_token with valid token"""
        # Setup
        self.auth.access_token = "test_token"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'client_id': self.client_id,
            'login': 'test_user',
            'scopes': ['chat:read', 'chat:edit'],
            'user_id': '12345',
            'expires_in': 3600
        }
        mock_requests.get.return_value = mock_response

        # Test
        result = self.auth.validate_token()
        self.assertTrue(result)

        # Verify API call
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        self.assertIn('Authorization', call_args[1]['headers'])
        self.assertEqual(
            call_args[1]['headers']['Authorization'],
            'OAuth test_token'
        )

    @patch('src.auth_manager.requests')
    def test_validate_token_invalid(self, mock_requests):
        """Test validate_token with invalid token"""
        self.auth.access_token = "invalid_token"
        mock_response = Mock()
        mock_response.status_code = 401
        mock_requests.get.return_value = mock_response

        result = self.auth.validate_token()
        self.assertFalse(result)

    def test_validate_token_no_token(self):
        """Test validate_token returns False when no token"""
        result = self.auth.validate_token()
        self.assertFalse(result)

    @patch('webbrowser.open')
    @patch('src.auth_manager.AuthManager._start_callback_server')
    def test_start_oauth_flow_success(self, mock_server, mock_browser):
        """Test OAuth flow starts successfully"""
        mock_server.return_value = True

        result = self.auth.start_oauth_flow()

        self.assertTrue(result)
        mock_server.assert_called_once()
        mock_browser.assert_called_once()

        # Verify OAuth state was generated
        self.assertIsNotNone(self.auth.oauth_state)

        # Verify browser opened with correct URL
        url = mock_browser.call_args[0][0]
        self.assertIn('client_id=' + self.client_id, url)
        self.assertIn('state=' + self.auth.oauth_state, url)
        self.assertIn('scope=chat%3Aread+chat%3Aedit', url)

    @patch('src.auth_manager.requests', None)
    def test_start_oauth_flow_no_requests_library(self):
        """Test OAuth flow fails gracefully without requests library"""
        result = self.auth.start_oauth_flow()
        self.assertFalse(result)

    def test_build_auth_url(self):
        """Test OAuth URL building"""
        self.auth.oauth_state = "test_state_12345"
        url = self.auth._build_auth_url()

        self.assertIn('https://id.twitch.tv/oauth2/authorize', url)
        self.assertIn('client_id=' + self.client_id, url)
        self.assertIn('state=test_state_12345', url)
        self.assertIn('response_type=code', url)
        self.assertIn('redirect_uri=http%3A%2F%2Flocalhost%3A8080', url)

    @patch('src.auth_manager.requests')
    def test_exchange_code_for_token_state_mismatch(self, mock_requests):
        """Test code exchange fails with state mismatch (security-critical)"""
        self.auth.oauth_state = "correct_state"

        # Setup callback
        failure_callback = Mock()
        self.auth.set_callbacks(on_failure=failure_callback)

        # Try to exchange with wrong state
        self.auth._exchange_code_for_token("auth_code", "wrong_state")

        # Should fail and call failure callback
        failure_callback.assert_called_once()
        self.assertIn("state mismatch", failure_callback.call_args[0][0].lower())

        # Should not make API call
        mock_requests.post.assert_not_called()

    @patch('src.auth_manager.requests')
    def test_exchange_code_for_token_success(self, mock_requests):
        """Test successful code exchange"""
        self.auth.oauth_state = "test_state"

        # Mock successful token response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600,
            'scope': ['chat:read', 'chat:edit'],
            'token_type': 'bearer'
        }
        mock_requests.post.return_value = mock_response

        # Mock validation response
        mock_validate_response = Mock()
        mock_validate_response.status_code = 200
        mock_validate_response.json.return_value = {
            'client_id': self.client_id,
            'login': 'test_user',
            'scopes': ['chat:read', 'chat:edit'],
            'user_id': '12345',
            'expires_in': 3600
        }
        mock_requests.get.return_value = mock_validate_response

        # Setup success callback
        success_callback = Mock()
        self.auth.set_callbacks(on_success=success_callback)

        # Exchange code
        self.auth._exchange_code_for_token("auth_code", "test_state")

        # Verify token was set
        self.assertEqual(self.auth.access_token, 'new_access_token')
        self.assertEqual(self.auth.refresh_token, 'new_refresh_token')
        self.assertIsNotNone(self.auth.token_expires)

        # Verify success callback was called
        success_callback.assert_called_once_with('test_user')


if __name__ == '__main__':
    unittest.main()

"""
OAuth authentication manager for Twitch API integration.

This module provides secure OAuth authentication flow for Twitch chat messaging,
following security best practices for token storage and management.

The :class:`AuthManager` handles:
    - OAuth flow initiation and redirect handling
    - Secure token storage with encryption
    - Token refresh and validation
    - User authentication state management

Key Features:
    - Browser-based OAuth flow using Twitch's official authentication
    - Local HTTP server for OAuth redirect capture
    - Encrypted token storage for security
    - Automatic token refresh when needed
"""

import json
import secrets
import threading
import webbrowser
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Callable, Any
from urllib.parse import urlparse, parse_qs, urlencode

try:
    import requests
except ImportError:
    requests = None

# Use lazy imports for cryptography to avoid PyInstaller issues with pycparser

from .logging_config import get_logger

logger = get_logger(__name__)

# Twitch OAuth constants
TWITCH_OAUTH_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
REDIRECT_URI = "http://localhost:8080/auth/callback"
REQUIRED_SCOPES = ["chat:read", "chat:edit"]

# Token storage
TOKEN_FILE = Path("config/auth_token.enc")


class OAuthHTTPServer(HTTPServer):
    """Custom HTTPServer with OAuth callback attributes."""

    auth_code: Optional[str] = None
    auth_state: Optional[str] = None
    auth_error: Optional[str] = None


class AuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""

    server: OAuthHTTPServer  # Type annotation for mypy

    def do_GET(self) -> None:
        """Handle GET request for OAuth callback"""
        if self.path.startswith("/auth/callback") or (
            "code=" in self.path or "error=" in self.path
        ):
            # Parse the callback URL
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            # Store the authorization code or error
            if "code" in query_params:
                self.server.auth_code = query_params["code"][0]
                self.server.auth_state = query_params.get("state", [None])[0]
                response = """
                <html><body>
                <h2>Authentication Successful!</h2>
                <p>You can now close this window and return to TwitchAdAvoider.</p>
                <script>window.close();</script>
                </body></html>
                """
            else:
                error = query_params.get("error", ["unknown_error"])[0]
                self.server.auth_error = error
                response = f"""
                <html><body>
                <h2>Authentication Failed</h2>
                <p>Error: {error}</p>
                <p>Please close this window and try again.</p>
                </body></html>
                """

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP server logging"""
        pass


class AuthManager:
    """
    Manages Twitch OAuth authentication for chat messaging.

    This manager handles the complete OAuth flow, secure token storage,
    and authentication state management.
    """

    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize the authentication manager.

        Args:
            client_id: Twitch application client ID
            client_secret: Twitch application client secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.username: Optional[str] = None

        # OAuth state for security
        self.oauth_state: Optional[str] = None

        # Callbacks
        self.on_auth_success: Optional[Callable[[str], None]] = None
        self.on_auth_failure: Optional[Callable[[str], None]] = None

        # HTTP server for callback
        self.callback_server: Optional[OAuthHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None

        # Create config directory if needed
        TOKEN_FILE.parent.mkdir(exist_ok=True)

        # Load existing token if available
        self.load_token()

    def set_callbacks(
        self,
        on_success: Optional[Callable[[str], None]] = None,
        on_failure: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Set authentication callback functions.

        Args:
            on_success: Called with username when authentication succeeds
            on_failure: Called with error message when authentication fails
        """
        self.on_auth_success = on_success
        self.on_auth_failure = on_failure

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated.

        Returns:
            True if authenticated with valid token, False otherwise
        """
        if not self.access_token:
            return False

        # Check if token is expired
        if self.token_expires and datetime.now(timezone.utc) >= self.token_expires:
            logger.debug("Access token has expired")
            return False

        return True

    def get_username(self) -> Optional[str]:
        """
        Get the authenticated username.

        Returns:
            Username if authenticated, None otherwise
        """
        return self.username if self.is_authenticated() else None

    def get_access_token(self) -> Optional[str]:
        """
        Get the current access token.

        Returns:
            Access token if authenticated, None otherwise
        """
        return self.access_token if self.is_authenticated() else None

    def start_oauth_flow(self) -> bool:
        """
        Start the OAuth authentication flow.

        Returns:
            True if flow started successfully, False otherwise
        """
        if not requests:
            logger.error("requests library not available for OAuth flow")
            if self.on_auth_failure:
                self.on_auth_failure("Missing required dependency: requests")
            return False

        try:
            # Generate secure state parameter
            self.oauth_state = secrets.token_urlsafe(32)

            # Start callback server
            if not self._start_callback_server():
                return False

            # Build OAuth URL
            auth_url = self._build_auth_url()

            # Open browser
            logger.info("Opening browser for Twitch authentication...")
            webbrowser.open(auth_url)

            return True

        except Exception as e:
            logger.error(f"Failed to start OAuth flow: {e}")
            if self.on_auth_failure:
                self.on_auth_failure(f"Failed to start authentication: {str(e)}")
            return False

    def logout(self) -> None:
        """Logout and clear all authentication data"""
        self.access_token = None
        self.refresh_token = None
        self.token_expires = None
        self.username = None
        self.oauth_state = None

        # Remove token file
        if TOKEN_FILE.exists():
            try:
                TOKEN_FILE.unlink()
                logger.info("Authentication token cleared")
            except Exception as e:
                logger.warning(f"Failed to remove token file: {e}")

        # Stop callback server if running
        self._stop_callback_server()

    def validate_token(self) -> bool:
        """
        Validate the current token with Twitch API.

        Returns:
            True if token is valid, False otherwise
        """
        if not self.access_token or not requests:
            return False

        try:
            headers = {"Authorization": f"OAuth {self.access_token}"}
            response = requests.get(TWITCH_VALIDATE_URL, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                self.username = data.get("login")

                # Update expiry if provided
                expires_in = data.get("expires_in")
                if expires_in:
                    self.token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

                logger.info(f"Token validated for user: {self.username}")
                return True
            else:
                logger.warning(f"Token validation failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False

    def load_token(self) -> bool:
        """
        Load stored authentication token.

        Returns:
            True if token loaded successfully, False otherwise
        """
        if not TOKEN_FILE.exists():
            return False

        try:
            # Read encrypted token data
            encrypted_data = TOKEN_FILE.read_bytes()

            # Decrypt
            decrypted_data = self._decrypt_token_data(encrypted_data)
            if not decrypted_data:
                return False

            # Parse token data
            token_data = json.loads(decrypted_data)
            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")
            self.username = token_data.get("username")

            # Parse expiry time
            expires_str = token_data.get("expires")
            if expires_str:
                self.token_expires = datetime.fromisoformat(expires_str)

            logger.info(f"Authentication token loaded for user: {self.username}")

            # Validate the loaded token
            if self.validate_token():
                return True
            else:
                # Token is invalid, clear it
                self.logout()
                return False

        except Exception as e:
            logger.warning(f"Failed to load authentication token: {e}")
            # Remove corrupted token file
            if TOKEN_FILE.exists():
                TOKEN_FILE.unlink()
            return False

    def save_token(self) -> bool:
        """
        Save authentication token securely.

        Returns:
            True if token saved successfully, False otherwise
        """
        if not self.access_token:
            return False

        try:
            # Prepare token data
            token_data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "username": self.username,
                "expires": self.token_expires.isoformat() if self.token_expires else None,
            }

            # Encrypt and save
            json_data = json.dumps(token_data)
            encrypted_data = self._encrypt_token_data(json_data)

            TOKEN_FILE.write_bytes(encrypted_data)
            logger.info("Authentication token saved securely")
            return True

        except Exception as e:
            logger.error(f"Failed to save authentication token: {e}")
            return False

    def _start_callback_server(self) -> bool:
        """Start HTTP server for OAuth callback"""
        try:
            self.callback_server = OAuthHTTPServer(("localhost", 8080), AuthCallbackHandler)
            self.callback_server.auth_code = None
            self.callback_server.auth_error = None
            self.callback_server.auth_state = None

            self.server_thread = threading.Thread(target=self._run_callback_server, daemon=True)
            self.server_thread.start()

            logger.debug("OAuth callback server started on localhost:8080")
            return True

        except Exception as e:
            logger.error(f"Failed to start callback server: {e}")
            return False

    def _stop_callback_server(self) -> None:
        """Stop the OAuth callback server"""
        if self.callback_server:
            self.callback_server.shutdown()
            self.callback_server = None

        if self.server_thread:
            self.server_thread.join(timeout=5)
            self.server_thread = None

    def _run_callback_server(self) -> None:
        """Run the callback server and handle OAuth response"""
        try:
            # Wait for OAuth callback (with timeout)
            if not self.callback_server:
                return
            self.callback_server.timeout = 60  # 60 second timeout
            while self.callback_server:
                self.callback_server.handle_request()

                # Check if we received a response
                if hasattr(self.callback_server, "auth_code") and self.callback_server.auth_code:
                    # Success - exchange code for token
                    auth_state = self.callback_server.auth_state or ""
                    self._exchange_code_for_token(self.callback_server.auth_code, auth_state)
                    break
                elif (
                    hasattr(self.callback_server, "auth_error") and self.callback_server.auth_error
                ):
                    # Error occurred
                    error_msg = f"OAuth error: {self.callback_server.auth_error}"
                    logger.error(error_msg)
                    if self.on_auth_failure:
                        self.on_auth_failure(error_msg)
                    break

        except Exception as e:
            logger.error(f"Callback server error: {e}")
            if self.on_auth_failure:
                self.on_auth_failure(f"Authentication server error: {str(e)}")
        finally:
            self._stop_callback_server()

    def _build_auth_url(self) -> str:
        """Build the OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(REQUIRED_SCOPES),
            "state": self.oauth_state,
        }

        param_string = urlencode(params)
        return f"{TWITCH_OAUTH_URL}?{param_string}"

    def _exchange_code_for_token(self, auth_code: str, state: str) -> None:
        """Exchange authorization code for access token"""
        try:
            # Verify state parameter
            if state != self.oauth_state:
                error_msg = "OAuth state mismatch - possible security issue"
                logger.error(error_msg)
                if self.on_auth_failure:
                    self.on_auth_failure(error_msg)
                return

            # Exchange code for token
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            response = requests.post(TWITCH_TOKEN_URL, data=token_data, headers=headers, timeout=30)

            if response.status_code == 200:
                token_info = response.json()

                self.access_token = token_info.get("access_token")
                self.refresh_token = token_info.get("refresh_token")

                # Calculate expiry time
                expires_in = token_info.get("expires_in", 3600)
                self.token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

                # Validate token and get user info
                if self.validate_token():
                    # Save token
                    self.save_token()

                    logger.info(f"Authentication successful for user: {self.username}")
                    if self.on_auth_success and self.username:
                        self.on_auth_success(self.username)
                else:
                    error_msg = "Token validation failed after OAuth"
                    logger.error(error_msg)
                    if self.on_auth_failure:
                        self.on_auth_failure(error_msg)
            else:
                # Get detailed error information
                try:
                    error_details = response.json()
                    error_msg = (
                        f"Token exchange failed: {response.status_code} - "
                        f"{error_details.get('message', 'Unknown error')}"
                    )
                    logger.error(f"Token exchange failed: {response.status_code}")
                    logger.error(f"Response body: {error_details}")
                except Exception:
                    error_msg = (
                        f"Token exchange failed: {response.status_code} - " f"{response.text}"
                    )
                    logger.error(f"Token exchange failed: {response.status_code}")
                    logger.error(f"Response body: {response.text}")

                if self.on_auth_failure:
                    self.on_auth_failure(error_msg)

        except Exception as e:
            error_msg = f"Token exchange error: {str(e)}"
            logger.error(error_msg)
            if self.on_auth_failure:
                self.on_auth_failure(error_msg)

    def _get_encryption_key(self) -> bytes:
        """Generate encryption key from system-specific data"""
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
        except ImportError:
            raise ImportError("cryptography library required for token encryption")

        # Use a combination of system-specific data as password
        # This is basic security - in production, consider using system keyring
        import platform
        import getpass

        password = f"{platform.node()}{getpass.getuser()}TwitchAdAvoider".encode()

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"TwitchAdAvoider2024",  # Static salt for consistency
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key

    def _encrypt_token_data(self, data: str) -> bytes:
        """Encrypt token data"""
        try:
            from cryptography.fernet import Fernet
            import base64

            key = self._get_encryption_key()
            f = Fernet(key)
            return f.encrypt(data.encode())
        except ImportError:
            # Fallback to base64 encoding if cryptography not available
            logger.warning("Cryptography not available, using basic encoding")
            import base64

            return base64.b64encode(data.encode())

    def _decrypt_token_data(self, encrypted_data: bytes) -> Optional[str]:
        """Decrypt token data"""
        try:
            # Try cryptography first
            try:
                from cryptography.fernet import Fernet

                key = self._get_encryption_key()
                f = Fernet(key)
                return f.decrypt(encrypted_data).decode()
            except ImportError:
                # Fallback to base64 decoding
                import base64

                return base64.b64decode(encrypted_data).decode()

        except Exception as e:
            logger.warning(f"Failed to decrypt token data: {e}")
            return None

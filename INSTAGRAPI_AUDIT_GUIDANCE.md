# instagrapi Testing & Configuration Audit Remediation Guide

**Source**: Authoritative patterns from instagrapi official docs, repository tests, and implementation experience.

---

## 1. AUTHENTICATION & TESTING PATTERNS

### Official Pattern: Environment-Based Configuration
([Source: instagrapi/tests.py](https://github.com/subzeroid/instagrapi/blob/master/tests.py#L40-L45))

```python
# Environment variables for test authentication
ACCOUNT_USERNAME = os.getenv("IG_USERNAME", "username")
ACCOUNT_PASSWORD = os.getenv("IG_PASSWORD", "password*")
ACCOUNT_SESSIONID = os.getenv("IG_SESSIONID", "")
TEST_ACCOUNTS_URL = os.getenv("TEST_ACCOUNTS_URL")
```

**Key Principles**:
- Never hardcode credentials in test code
- Use environment variables with secure defaults
- Provide fallback values for CI/CD environments
- Support both fresh credentials and session-based auth

### Session-Based Testing Pattern
([Source: instagrapi/tests.py](https://github.com/subzeroid/instagrapi/blob/master/tests.py#L102-L130))

```python
class ClientPrivateTestCase(BaseClientMixin, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        filename = f"/tmp/instagrapi_tests_client_settings_{ACCOUNT_USERNAME}.json"
        self.cl = Client()
        settings = {}
        try:
            st = os.stat(filename)
            # Use only fresh session (1 hour max)
            if datetime.fromtimestamp(st.st_mtime) > (
                datetime.now() - timedelta(seconds=3600)
            ):
                settings = self.cl.load_settings(filename)
        except FileNotFoundError:
            pass
        
        self.cl.set_settings(settings)
        self.cl.request_timeout = 1  # 1 second default
        self.set_proxy_if_exists()
        
        if ACCOUNT_SESSIONID:
            self.cl.login_by_sessionid(ACCOUNT_SESSIONID)
        else:
            self.cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD, relogin=True)
        
        self.cl.dump_settings(filename)
```

**Critical Insight**: 
- Sessions are cached for 1 hour max (prevents stale session reuse)
- Settings are persisted to JSON between test runs
- Fresh logins (relogin=True) ensure device consistency
- request_timeout is set at client level (1 second default)

---

## 2. TIMEOUT CONFIGURATION

### Request Timeout (HTTP-level)
([Source: instagrapi/mixins/private.py#L82](https://github.com/subzeroid/instagrapi/blob/master/instagrapi/mixins/private.py#L82))

```python
class PrivateRequestMixin:
    request_timeout = 1  # Default: 1 second for HTTP requests
    
    def __init__(self, *args, **kwargs):
        self.request_timeout = kwargs.pop("request_timeout", self.request_timeout)
```

**Usage**:
```python
# At client initialization
cl = Client(request_timeout=5)  # 5 seconds

# Or modify after creation
cl.request_timeout = 10  # 10 seconds
```

### Upload Configuration Timeout (Media-specific)
([Source: instagrapi/mixins/photo.py, album.py](https://github.com/subzeroid/instagrapi/blob/master/instagrapi/mixins/album.py#L120))

```python
def photo_upload_to_album(
    self,
    filepath: str,
    caption: str = "",
    upload_id: str = None,
    configure_timeout: int = 3,  # Media-specific timeout
    **kwargs
) -> Media:
    """
    configure_timeout: Sleep duration while Instagram processes upload
    """
    time.sleep(configure_timeout)
```

**Where Used**:
- `photo_upload_to_album()`: configure_timeout=3 (default)
- `video_upload_to_album()`: configure_timeout=3 (default)
- `video_upload_to_igtv()`: configure_timeout=10 (default, longer for IGTV)
- `video_upload_to_clip()`: configure_timeout=10 (default)

**Explanation**: These are NOT HTTP timeouts—they're deliberate delays (`time.sleep()`) to allow Instagram's backend to process the uploaded media before the client queries status.

### Environment-Based Timeout Configuration

```python
import os

def create_client_with_env_config():
    """Environment-driven client configuration pattern"""
    cl = Client(
        request_timeout=int(os.getenv("IG_REQUEST_TIMEOUT", "1")),
        delay_range=[
            float(os.getenv("IG_DELAY_MIN", "1")),
            float(os.getenv("IG_DELAY_MAX", "3"))
        ],
        proxy=os.getenv("IG_PROXY", None)
    )
    return cl
```

---

## 3. DELAY CONFIGURATION

### Rate-Limiting & Human-Like Behavior
([Source: instagrapi Best Practices](https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html))

```python
cl = Client()
cl.delay_range = [1, 3]  # Random delay 1-3 seconds between requests

# Internally (instagrapi/utils.py):
def random_delay(delay_range: list):
    return time.sleep(random.uniform(delay_range[0], delay_range[1]))
```

**Recommendation from Docs**: 
- "Add delays to mimic real user behavior"
- "Use random delays, not fixed intervals"
- Official safe limits: 10 accounts per IP, 4-16 posts per account

---

## 4. MOCKING PATTERNS FOR TESTS

### Approach 1: Abstraction Wrapper (Recommended)

Instead of mocking `instagrapi.Client` directly, wrap it:

```python
# instagram_adapter.py
from instagrapi import Client
from instagrapi.exceptions import ClientError, LoginRequired

class InstagramAdapter:
    """Adapter wrapping instagrapi client for testability"""
    
    def __init__(self, client: Client = None):
        self.client = client or Client()
    
    def authenticate(self, username: str, password: str) -> bool:
        """Environment-aware authentication"""
        try:
            self.client.login(username, password)
            return True
        except LoginRequired as e:
            # Handle session validation
            raise
    
    def get_user_info(self, user_id: int) -> dict:
        """Wrapped call for easier mocking"""
        try:
            return self.client.user_info(user_id).dict()
        except ClientError as e:
            raise ValueError(f"Failed to fetch user {user_id}: {e}")

# tests/test_adapter.py
from unittest.mock import Mock, patch, MagicMock
import pytest

@pytest.fixture
def mock_client():
    """Fixture providing a mock instagrapi Client"""
    client = Mock(spec=Client)
    client.user_info.return_value = Mock(
        pk=123,
        username="test_user",
        full_name="Test User",
        biography="Test bio"
    )
    return client

def test_get_user_info_success(mock_client):
    """Test successful user info retrieval with mock"""
    adapter = InstagramAdapter(mock_client)
    
    result = adapter.get_user_info(123)
    
    assert result['username'] == "test_user"
    mock_client.user_info.assert_called_once_with(123)

def test_get_user_info_handles_error(mock_client):
    """Test error handling in adapter"""
    mock_client.user_info.side_effect = Exception("API Error")
    adapter = InstagramAdapter(mock_client)
    
    with pytest.raises(ValueError):
        adapter.get_user_info(999)
```

**Why This Pattern**:
- ✅ Decouples your code from instagrapi internals
- ✅ Easy to mock in tests
- ✅ Can add retry logic, timeouts, custom error handling
- ✅ Facilitates environment-driven configuration
- ✅ Reduces fragility from instagrapi API changes

### Approach 2: Environment-Based Toggle (Alternative)

```python
# config.py
import os
from instagrapi import Client

USE_MOCK_INSTAGRAM = os.getenv("USE_MOCK_INSTAGRAM", "false").lower() == "true"

def get_instagram_client():
    """Factory function for dependency injection"""
    if USE_MOCK_INSTAGRAM:
        return MockInstagramClient()
    
    return Client(
        request_timeout=int(os.getenv("IG_REQUEST_TIMEOUT", "1")),
        proxy=os.getenv("IG_PROXY")
    )

class MockInstagramClient:
    """Mock client for testing"""
    def __init__(self):
        self.user_id = 12345
    
    def user_info(self, user_id):
        return Mock(pk=user_id, username=f"user_{user_id}")
```

---

## 5. TIMEOUT TESTING PATTERNS

### Test Configuration Timeout Scenarios

```python
# tests/test_timeouts.py
import pytest
from unittest.mock import patch, MagicMock
import time

def test_request_timeout_honored(mock_client):
    """Verify request_timeout is passed to HTTP layer"""
    from instagrapi import Client
    
    # Arrange
    with patc

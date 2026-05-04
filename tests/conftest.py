import os
import sys
from unittest.mock import MagicMock

# Stub Python 3.9+ packages that can't be installed on 3.8.
# Must happen before any backend module is imported.
for _mod in [
    'langgraph',
    'langgraph.checkpoint',
    'langgraph.checkpoint.postgres',
    'langgraph.graph',
    'langgraph.graph.message',
    'langgraph.prebuilt',
    'langchain_core',
    'langchain_core.messages',
    'langchain_core.tools',
    'langchain_openai',
]:
    sys.modules.setdefault(_mod, MagicMock())

# Must be set before any app code is imported
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-do-not-use-in-prod')
os.environ.setdefault('OPENROUTER_API_KEY', 'test-openrouter-key')
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/testdb')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/1')
os.environ.setdefault('FLASK_ENV', 'testing')

import jwt
import pytest
import fakeredis
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import backend.extensions as ext


@pytest.fixture(scope='session')
def app():
    with patch('backend.app.init_pool'), \
         patch('backend.app.run_migrations'), \
         patch('backend.app.setup_langgraph_checkpointer'), \
         patch('backend.app.init_redis', return_value=fakeredis.FakeRedis(decode_responses=True)):
        from backend.app import create_app
        test_app = create_app('testing')

    ext.redis_client = fakeredis.FakeRedis(decode_responses=True)
    yield test_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def fresh_redis(app):
    """Reset fakeredis state between every test."""
    r = fakeredis.FakeRedis(decode_responses=True)
    ext.redis_client = r
    yield r
    r.flushall()


@pytest.fixture(autouse=True)
def reset_rate_limits(app):
    """Clear in-memory rate limit counters between every test."""
    yield
    try:
        from backend.extensions import limiter
        limiter._storage.reset()
    except Exception:
        pass


@pytest.fixture()
def valid_user_payload() -> dict:
    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'SecurePass1',
        'full_name': 'Test User',
        'phone': '+1234567890',
    }


@pytest.fixture()
def access_token_for(app) -> callable:
    """Factory: returns a valid JWT access token for any user_id string."""
    def _make(user_id: str = 'user-uuid-1234') -> str:
        return jwt.encode(
            {
                'sub': user_id,
                'exp': datetime.now(timezone.utc) + timedelta(minutes=15),
                'iat': datetime.now(timezone.utc),
            },
            app.config['SECRET_KEY'],
            algorithm='HS256',
        )
    return _make


@pytest.fixture()
def auth_headers(access_token_for) -> dict:
    """Authorization headers for a generic test user."""
    return {'Authorization': f'Bearer {access_token_for()}'}

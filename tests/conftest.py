import os
import sys
from unittest.mock import MagicMock

# Stub heavy packages before any backend module is imported.
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

os.environ.setdefault('SESSION_SECRET_KEY', 'test-secret-key-do-not-use-in-prod')
os.environ.setdefault('OPENROUTER_API_KEY', 'test-openrouter-key')
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/testdb')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/1')
os.environ.setdefault('FLASK_ENV', 'testing')

import pytest
import fakeredis
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
        'first_name': 'Test',
        'last_name': 'User',
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'SecurePass1',
        'confirm_password': 'SecurePass1',
        'phone': '+1234567890',
    }


@pytest.fixture()
def authed_client(client):
    """Client fixture with a pre-set session for user-uuid-1234."""
    with client.session_transaction() as sess:
        sess['user_id'] = 'user-uuid-1234'
    return client

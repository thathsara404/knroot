import pytest
import fakeredis

from backend.app import create_app
from backend.core.db import init_pool
import backend.extensions as ext


@pytest.fixture(scope="session")
def app(postgresql):
    """Flask test app wired to a real test Postgres + fake Redis."""
    db_url = (
        f"postgresql://{postgresql.info.user}:@"
        f"{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )
    test_app = create_app("testing")
    test_app.config["DATABASE_URL"] = db_url
    # Override pool with test DB
    init_pool(db_url)
    # Override Redis with fakeredis
    ext.redis_client = fakeredis.FakeRedis(decode_responses=True)
    return test_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)

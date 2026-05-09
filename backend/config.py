import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv('SESSION_SECRET_KEY', '')
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/postgres')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    RATELIMIT_STORAGE_URI = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'deepseek/deepseek-chat')
    DB_POOL_MAX_SIZE = int(os.getenv('DB_POOL_MAX_SIZE', '20'))
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False
    RATELIMIT_ENABLED = os.getenv('RATELIMIT_ENABLED', 'true').lower() == 'true'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    DATABASE_URL = os.getenv(
        'TEST_DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/testdb'
    )
    REDIS_URL = os.getenv('TEST_REDIS_URL', 'redis://localhost:6379/1')
    RATELIMIT_STORAGE_URI = 'memory://'
    # Flask-Session is skipped in tests; Flask's default cookie session is used instead


config_map = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
}

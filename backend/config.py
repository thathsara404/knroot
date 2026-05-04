import os


class Config:
    SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/postgres")
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    JWT_ACCESS_EXPIRES_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRES_MINUTES", "15"))
    JWT_REFRESH_EXPIRES_DAYS = int(os.getenv("JWT_REFRESH_EXPIRES_DAYS", "7"))
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")
    APP_URL = os.getenv("APP_URL", "http://localhost:5000")
    DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "20"))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/testdb")
    REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")


config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
}

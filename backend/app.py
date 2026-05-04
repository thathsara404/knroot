import logging
import os

from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from flask_cors import CORS

from backend.config import config_map
from backend.core.db import init_pool, run_migrations, setup_langgraph_checkpointer
from backend.core.errors import register_error_handlers
from backend.extensions import init_redis, limiter


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    cfg = config_map.get(config_name, config_map["development"])
    app.config.from_object(cfg)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Extensions
    CORS(app, origins=app.config["CORS_ORIGINS"])
    limiter.init_app(app)

    # Database
    init_pool(app.config["DATABASE_URL"], app.config["DB_POOL_MAX_SIZE"])
    run_migrations()
    setup_langgraph_checkpointer()

    # Redis
    redis = init_redis(app.config["REDIS_URL"])

    # Scheduler (only in non-testing env to avoid background threads in tests)
    if not app.config.get("TESTING"):
        from backend.core.scheduler import init_scheduler
        init_scheduler(redis)

    # Blueprints
    from backend.api.health.routes import bp as health_bp
    from backend.api.news.routes import bp as news_bp
    from backend.api.chat.routes import bp as chat_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(chat_bp)

    register_error_handlers(app)

    return app

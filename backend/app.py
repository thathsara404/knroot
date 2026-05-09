from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
load_dotenv()

from flask import Flask  # noqa: E402

from backend.config import config_map  # noqa: E402
from backend.core.db import init_pool, run_migrations, setup_langgraph_checkpointer  # noqa: E402
from backend.core.errors import register_error_handlers  # noqa: E402
from backend.extensions import init_redis, init_session, limiter  # noqa: E402


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    cfg = config_map.get(config_name, config_map['development'])
    app.config.from_object(cfg)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    limiter.init_app(app)

    # Database
    init_pool(app.config['DATABASE_URL'], app.config['DB_POOL_MAX_SIZE'])
    run_migrations()
    setup_langgraph_checkpointer()

    # Redis + server-side sessions (skipped in testing — Flask cookie session used instead)
    redis = init_redis(app.config['REDIS_URL'])
    if not app.config.get('TESTING'):
        init_session(app, app.config['REDIS_URL'])

    # Scheduler (only in non-testing env to avoid background threads in tests)
    if not app.config.get('TESTING'):
        from backend.core.scheduler import init_scheduler
        init_scheduler(redis)

    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('SESSION_SECRET_KEY environment variable is not set')

    # Blueprints
    from backend.api.health.routes import bp as health_bp
    from backend.api.auth.routes import bp as auth_bp
    from backend.api.news.routes import bp as news_bp
    from backend.api.chat.routes import bp as chat_bp
    from backend.api.pages.routes import bp as pages_bp
    from backend.api.sessions.routes import bp as sessions_bp
    from backend.api.discuss.routes import bp as discuss_bp
    from backend.api.quiz.routes import bp as quiz_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(discuss_bp)
    app.register_blueprint(quiz_bp)

    register_error_handlers(app)

    from backend.core.template_filters import pub_date
    app.jinja_env.filters["pub_date"] = pub_date

    return app

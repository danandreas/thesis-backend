from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
import logging
import os

from config.settings import get_config

# Extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def create_app():
    app = Flask(__name__)

    # Load config
    config = get_config()
    app.config.from_object(config)

    # Setup logging
    _setup_logging(app)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # CORS setup
    _setup_cors(app, config)

    # Register blueprints (routes)
    _register_routes(app)

    # JWT error handlers
    _register_jwt_handlers(app)

    return app


def _setup_logging(app):
    level = getattr(logging, app.config.get('LOG_LEVEL', 'DEBUG'), logging.DEBUG)
    handlers = [logging.StreamHandler()]

    # File logging hanya aktif jika bisa membuat direktori (tidak berlaku di Vercel)
    log_file = app.config.get('LOG_FILE', 'storage/logs/app.log')
    log_dir = os.path.dirname(log_file)
    try:
        os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    except OSError:
        pass  # Filesystem read-only (e.g. Vercel), skip file logging

    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=handlers
    )


def _setup_cors(app, config):
    if app.config.get('DEBUG'):
        # Development: allow all origins
        CORS(app, resources={r"/api/*": {"origins": "*"}})
        app.logger.info("CORS: Allowing all origins (DEBUG mode)")
    else:
        origins = config.CORS_ORIGINS_LIST
        if origins:
            CORS(app, resources={r"/api/*": {"origins": origins}})
            app.logger.info(f"CORS: Restricted to {origins}")
        else:
            app.logger.warning("CORS: No origins configured for production!")


def _register_routes(app):
    from routes.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')


def _register_jwt_handlers(app):
    from app.helpers.response import api_response
    from app.models.token_blacklist import TokenBlacklist

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_data):
        """
        Dipanggil otomatis setiap ada request dengan JWT.
        Return True = token di-blacklist → Flask-JWT tolak dengan 401 revoked.
        """
        jti = jwt_data.get('jti')
        return TokenBlacklist.is_revoked(jti)

    @jwt.unauthorized_loader
    def unauthorized_callback(error):
        return api_response(
            success=False,
            message="Token tidak ditemukan atau tidak valid.",
            code=401
        )

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return api_response(
            success=False,
            message="Token tidak valid.",
            code=401
        )

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        return api_response(
            success=False,
            message="Token sudah kadaluarsa. Silakan login kembali atau gunakan refresh token.",
            code=401
        )

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_data):
        return api_response(
            success=False,
            message="Token telah dicabut. Silakan login kembali.",
            code=401
        )

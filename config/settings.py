import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # App
    APP_NAME = os.getenv('APP_NAME', 'DanFlask')
    DEBUG = os.getenv('APP_DEBUG', 'true').lower() == 'true'
    SECRET_KEY = os.getenv('APP_SECRET_KEY', 'fallback-secret-key')
    PORT = int(os.getenv('APP_PORT', 5000))

    # Database - SQLAlchemy style (Eloquent-like via SQLAlchemy)
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_DATABASE = os.getenv('DB_DATABASE', 'dan_flask')
    DB_USERNAME = os.getenv('DB_USERNAME', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"
        f"?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = DEBUG  # Log SQL queries in debug mode

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'fallback-jwt-secret')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 86400)))
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    # CORS
    CORS_ORIGINS_LIST = [
        o.strip()
        for o in os.getenv('CORS_ORIGINS', '').split(',')
        if o.strip()
    ]

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
    LOG_FILE = os.getenv('LOG_FILE', 'storage/logs/app.log')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False


def get_config():
    env = os.getenv('APP_ENV', 'development').lower()
    configs = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
    }
    return configs.get(env, DevelopmentConfig)

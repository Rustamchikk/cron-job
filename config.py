"""
Ilova sozlamalari fayli
"""

import os
from dotenv import load_dotenv

# .env faylidan o'qish
load_dotenv()

class Config:
    """Asosiy sozlamalar"""
    # SECRET_KEY - Flask uchun maxfiy kalit
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-please-change-in-production'
    
    # Database konfiguratsiyasi
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20,
    }
    
    # Tozalash sozlamalari
    CLEANUP_SCHEDULE = '0 0 * * 1'  # Har dushanba 00:00 (CRON format)
    CLEANUP_ENABLED = True
    
    # Ilova sozlamalari
    DEBUG = os.environ.get('FLASK_DEBUG')
    HOST = '0.0.0.0'
    PORT = 5000
    
    # Pagination
    USERS_PER_PAGE = 50
    LOGS_PER_PAGE = 20
    
    # Session sozlamalari
    PERMANENT_SESSION_LIFETIME = 3600  # 1 soat

class DevelopmentConfig(Config):
    """Rivojlanish muhiti"""
    DEBUG = True
    SQLALCHEMY_ECHO = True  # SQL so'rovlarni terminalda ko'rsatadi

class ProductionConfig(Config):
    """Ishlab chiqarish muhiti"""
    DEBUG = False
    # Production uchun alohida database
    SQLALCHEMY_DATABASE_URI = os.environ.get('PRODUCTION_DATABASE_URL') or Config.SQLALCHEMY_DATABASE_URI

class TestingConfig(Config):
    """Test muhiti"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Konfiguratsiya obyekti
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
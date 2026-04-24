"""
TaskFlow 任务管理系统 - 应用配置
配置文件管理应用的各项配置参数
"""
import os
from datetime import timedelta


class Config:
    """基础配置类"""
    
    # 密钥配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///taskflow.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # 生产环境应设为 False
    
    # JWT 配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)  # Token 有效期 24 小时
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)  # 刷新 Token 有效期 30 天
    
    # 应用配置
    ITEMS_PER_PAGE = 20  # 分页每页数量
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 最大上传文件 16MB
    
    # 任务提醒配置
    REMINDER_CHECK_INTERVAL = 60  # 提醒检查间隔（秒）
    DEFAULT_REMINDER_BEFORE = 60  # 默认提前提醒时间（分钟）


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    SQLALCHEMY_ECHO = False


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """获取配置
    
    Args:
        env: 环境名称，默认为环境变量 FLASK_ENV 或 'development'
    
    Returns:
        Config: 配置类
    """
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])

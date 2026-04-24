"""
TaskFlow 任务管理系统 - 应用工厂
使用工厂模式创建 Flask 应用实例
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import get_config

# 初始化扩展
db = SQLAlchemy()
jwt = JWTManager()


def create_app(config_name='development'):
    """应用工厂函数
    
    Args:
        config_name: 配置名称
    
    Returns:
        Flask: Flask 应用实例
    """
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    
    # 加载配置
    app.config.from_object(get_config(config_name))
    
    # 初始化扩展
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册蓝图
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.tasks import tasks_bp
    from app.routes.categories import categories_bp
    from app.routes.teams import teams_bp
    from app.routes.notifications import notifications_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(categories_bp, url_prefix='/api/categories')
    app.register_blueprint(teams_bp, url_prefix='/api/teams')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
    
    # 注册错误处理器
    from app.utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # 初始化任务调度器
    from app.utils.scheduler import init_scheduler
    init_scheduler(app)
    
    # 创建数据库表
    with app.app_context():
        db.create_all()
    
    return app

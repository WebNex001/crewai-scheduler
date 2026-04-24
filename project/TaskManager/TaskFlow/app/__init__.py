# TaskFlow 应用工厂模块
# 负责创建和初始化Flask应用实例

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name='development'):
    """
    应用工厂函数：创建并配置Flask应用实例
    
    Args:
        config_name: 配置环境名称
    
    Returns:
        Flask 应用实例
    """
    # 创建应用
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static'
    )
    
    # 加载配置
    from app.config import get_config
    app.config.from_object(get_config(config_name))
    
    # 初始化扩展
    _init_extensions(app)
    
    # 注册蓝图
    _register_blueprints(app)
    
    # 注册模板上下文
    _register_context_processors(app)
    
    # 创建数据库表
    _init_database(app)
    
    return app


def _init_extensions(app):
    """初始化Flask扩展"""
    # 数据库
    db.init_app(app)
    
    # 用户认证
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录以访问此页面'
    login_manager.login_message_category = 'info'
    
    # CSRF 保护
    csrf.init_app(app)
    
    # 用户加载器
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))


def _register_blueprints(app):
    """注册应用蓝图"""
    from app.routes.auth import auth_bp
    from app.routes.tasks import tasks_bp
    from app.routes.categories import categories_bp
    from app.routes.teams import teams_bp
    from app.routes.main import main_bp
    
    # 注册蓝图并设置URL前缀
    app.register_blueprint(main_bp)  # 主页/仪表盘
    app.register_blueprint(auth_bp, url_prefix='/auth')  # 认证
    app.register_blueprint(tasks_bp, url_prefix='/tasks')  # 任务管理
    app.register_blueprint(categories_bp, url_prefix='/categories')  # 分类管理
    app.register_blueprint(teams_bp, url_prefix='/teams')  # 团队管理


def _register_context_processors(app):
    """注册模板上下文处理器"""
    from flask_login import current_user
    from app.utils.helpers import get_notification_count
    
    @app.context_processor
    def inject_user_context():
        """注入用户相关上下文"""
        return dict(
            current_user=current_user,
            notification_count=get_notification_count() if current_user.is_authenticated else 0
        )


def _init_database(app):
    """初始化数据库"""
    with app.app_context():
        # 导入所有模型以确保它们被注册
        from app.models import user, task, category, team
        
        # 创建所有表
        db.create_all()
        
        # 如果是开发环境，可以创建测试数据
        if app.config.get('DEBUG') and app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('sqlite'):
            _create_development_data(app)


def _create_development_data(app):
    """创建开发测试数据"""
    from app.models.user import User
    from app.models.category import Category
    
    # 检查是否已有数据
    if User.query.first() is not None:
        return
    
    # 创建默认分类
    default_categories = [
        {'name': '工作', 'color': '#3498db', 'icon': 'briefcase'},
        {'name': '个人', 'color': '#2ecc71', 'icon': 'user'},
        {'name': '学习', 'color': '#9b59b6', 'icon': 'book'},
        {'name': '购物', 'color': '#e74c3c', 'icon': 'shopping-cart'},
        {'name': '其他', 'color': '#95a5a6', 'icon': 'folder'}
    ]
    
    for cat_data in default_categories:
        category = Category(**cat_data)
        db.session.add(category)
    
    db.session.commit()
    print("\n✓ 开发测试数据已创建")

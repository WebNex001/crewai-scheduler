# TaskFlow 路由包
# 导出所有蓝图

from app.routes.auth import auth_bp
from app.routes.tasks import tasks_bp
from app.routes.categories import categories_bp
from app.routes.teams import teams_bp
from app.routes.main import main_bp

__all__ = [
    'auth_bp',
    'tasks_bp',
    'categories_bp',
    'teams_bp',
    'main_bp'
]

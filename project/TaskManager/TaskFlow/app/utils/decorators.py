# TaskFlow 装饰器模块
# 提供各种功能装饰器

from functools import wraps
from flask import request, jsonify, flash, redirect, url_for, abort
from flask_login import current_user


def login_required(func):
    """
    登录Required装饰器
    确保用户已登录才能访问视图
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # 判断是否为AJAX请求
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '请先登录', 'code': 'UNAUTHORIZED'}), 401
            flash('请先登录以访问此页面', 'warning')
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return decorated_function


def admin_required(func):
    """
    管理员Required装饰器
    确保用户是管理员才能访问视图
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': '请先登录', 'code': 'UNAUTHORIZED'}), 401
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin:
            if request.is_json:
                return jsonify({'error': '权限不足', 'code': 'FORBIDDEN'}), 403
            abort(403)
        
        return func(*args, **kwargs)
    return decorated_function


def ajax_login_required(func):
    """
    AJAX请求登录Required装饰器
    用于API端点的登录验证
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': '请先登录',
                'code': 'UNAUTHORIZED'
            }), 401
        return func(*args, **kwargs)
    return decorated_function


def validate_json(required_fields=None):
    """
    JSON数据验证装饰器
    
    Args:
        required_fields: 必需字段列表
    
    Returns:
        装饰器函数
    """
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    'success': False,
                    'error': '请求Content-Type必须是application/json',
                    'code': 'INVALID_CONTENT_TYPE'
                }), 400
            
            if required_fields:
                data = request.get_json()
                missing_fields = [f for f in required_fields if f not in data]
                if missing_fields:
                    return jsonify({
                        'success': False,
                        'error': f'缺少必需字段: {", ".join(missing_fields)}',
                        'code': 'MISSING_FIELDS'
                    }), 400
            
            return func(*args, **kwargs)
        return decorated_function
    return decorator


def rate_limit(max_requests=100, window=3600):
    """
    速率限制装饰器（简化实现）
    
    Args:
        max_requests: 最大请求数
        window: 时间窗口（秒）
    
    Note:
        生产环境建议使用 Flask-Limiter
    """
    # 简化实现，实际生产中应使用 Redis 或数据库存储
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            # 这里可以添加实际的速率限制逻辑
            return func(*args, **kwargs)
        return decorated_function
    return decorator


def team_member_required(team_id_param='team_id'):
    """
    团队成员Required装饰器
    
    Args:
        team_id_param: 团队ID参数名称
    """
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': '请先登录', 'code': 'UNAUTHORIZED'}), 401
                flash('请先登录', 'warning')
                return redirect(url_for('auth.login'))
            
            team_id = kwargs.get(team_id_param) or request.view_args.get(team_id_param)
            if not team_id:
                return jsonify({'error': '缺少团队ID', 'code': 'MISSING_TEAM_ID'}), 400
            
            from app.models.team import Team
            team = Team.query.get(team_id)
            if not team:
                return jsonify({'error': '团队不存在', 'code': 'TEAM_NOT_FOUND'}), 404
            
            if not team.is_member(current_user.id) and not team.is_owner(current_user.id):
                return jsonify({'error': '您不是该团队成员', 'code': 'NOT_TEAM_MEMBER'}), 403
            
            # 将team对象添加到kwargs中
            kwargs['team'] = team
            return func(*args, **kwargs)
        return decorated_function
    return decorator

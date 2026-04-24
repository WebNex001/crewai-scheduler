"""
TaskFlow 任务管理系统 - 装饰器
定义通用的装饰器函数
"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.models import User, Task, Team, TeamMember


def jwt_required_custom(fn):
    """自定义 JWT 验证装饰器
    
    扩展 Flask-JWT-Extended 的 jwt_required，添加额外的验证逻辑
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # 验证 JWT
        verify_jwt_in_request()
        
        # 获取当前用户
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': '用户不存在'}), 401
        
        # 将用户添加到请求上下文
        from flask import g
        g.current_user = user
        
        return fn(*args, **kwargs)
    
    return wrapper


def owner_required(model, id_param='id'):
    """验证资源所有权的装饰器工厂
    
    Args:
        model: 数据模型类
        id_param: URL 参数名称
    
    Returns:
        装饰器函数
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            resource_id = kwargs.get(id_param)
            
            if not resource_id:
                return jsonify({'error': '缺少必要参数'}), 400
            
            resource = model.query.get(resource_id)
            
            if not resource:
                return jsonify({'error': '资源不存在'}), 404
            
            # 检查所有权
            if hasattr(resource, 'user_id') and resource.user_id != user_id:
                return jsonify({'error': '无权限访问此资源'}), 403
            
            if hasattr(resource, 'owner_id') and resource.owner_id != user_id:
                return jsonify({'error': '无权限访问此资源'}), 403
            
            from flask import g
            g.resource = resource
            
            return fn(*args, **kwargs)
        
        return wrapper
    
    return decorator


def team_member_required(fn):
    """验证团队成员身份的装饰器
    
    用于需要团队成员身份才能访问的接口
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        team_id = kwargs.get('team_id')
        
        if not team_id:
            return jsonify({'error': '缺少团队ID'}), 400
        
        # 检查团队是否存在
        team = Team.query.get(team_id)
        if not team:
            return jsonify({'error': '团队不存在'}), 404
        
        # 检查用户是否是团队成员
        membership = TeamMember.query.filter_by(
            team_id=team_id, 
            user_id=user_id
        ).first()
        
        if not membership:
            return jsonify({'error': '您不是该团队成员'}), 403
        
        from flask import g
        g.team = team
        g.membership = membership
        
        return fn(*args, **kwargs)
    
    return wrapper


def paginate(query, page=1, per_page=20):
    """分页辅助函数
    
    Args:
        query: SQLAlchemy 查询对象
        page: 页码
        per_page: 每页数量
    
    Returns:
        dict: 包含分页信息的字典
    """
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        'items': [item.to_dict() for item in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    }

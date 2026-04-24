"""
TaskFlow 任务管理系统 - 认证路由
处理用户注册、登录、登出等认证相关功能
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required, 
    get_jwt_identity
)
from app import db
from app.models import User

# 创建认证蓝图
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册
    
    请求体:
        username: 用户名（必填，3-80字符）
        email: 邮箱（必填，有效邮箱格式）
        password: 密码（必填，至少6位）
        full_name: 真实姓名（可选）
    
    成功响应 (201):
        message: 注册成功消息
        user: 用户信息
        access_token: 访问令牌
        refresh_token: 刷新令牌
    
    错误响应:
        400: 参数验证失败
        409: 用户名或邮箱已存在
    """
    # 获取请求数据
    data = request.get_json()
    
    # 参数验证
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    
    # 验证必填字段
    errors = []
    if not username:
        errors.append('用户名不能为空')
    elif len(username) < 3 or len(username) > 80:
        errors.append('用户名长度需在3-80个字符之间')
    
    if not email:
        errors.append('邮箱不能为空')
    elif '@' not in email:
        errors.append('邮箱格式无效')
    
    if not password:
        errors.append('密码不能为空')
    elif len(password) < 6:
        errors.append('密码长度至少6位')
    
    if errors:
        return jsonify({'error': '参数验证失败', 'details': errors}), 400
    
    # 检查用户名是否已存在
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 409
    
    # 检查邮箱是否已存在
    if User.query.filter_by(email=email).first():
        return jsonify({'error': '邮箱已被注册'}), 409
    
    # 创建新用户
    user = User(
        username=username,
        email=email,
        full_name=full_name if full_name else None
    )
    user.set_password(password)
    
    # 保存到数据库
    db.session.add(user)
    db.session.commit()
    
    # 生成 Token
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'message': '注册成功',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录
    
    请求体:
        username: 用户名或邮箱（必填）
        password: 密码（必填）
    
    成功响应 (200):
        message: 登录成功消息
        user: 用户信息
        access_token: 访问令牌
        refresh_token: 刷新令牌
    
    错误响应:
        400: 参数缺失
        401: 用户名或密码错误
    """
    # 获取请求数据
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    # 查找用户（支持用户名或邮箱登录）
    user = User.query.filter(
        (User.username == username) | (User.email == username.lower())
    ).first()
    
    # 验证密码
    if not user or not user.check_password(password):
        return jsonify({'error': '用户名或密码错误'}), 401
    
    # 生成 Token
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'message': '登录成功',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """刷新访问令牌
    
    使用刷新令牌获取新的访问令牌
    
    请求头:
        Authorization: Bearer <refresh_token>
    
    成功响应 (200):
        access_token: 新的访问令牌
    """
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)
    
    return jsonify({
        'access_token': access_token
    }), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """获取当前用户信息
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        user: 用户信息
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    return jsonify({
        'user': user.to_dict()
    }), 200


@auth_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_current_user():
    """更新当前用户信息
    
    请求头:
        Authorization: Bearer <access_token>
    
    请求体:
        full_name: 真实姓名（可选）
        email: 邮箱（可选）
        password: 新密码（可选）
    
    成功响应 (200):
        message: 更新成功消息
        user: 更新后的用户信息
    
    错误响应:
        400: 参数验证失败
        409: 邮箱已被使用
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    # 更新字段
    if 'full_name' in data:
        user.full_name = data['full_name'].strip() if data['full_name'] else None
    
    if 'email' in data:
        new_email = data['email'].strip().lower()
        # 检查邮箱是否已被其他用户使用
        if new_email != user.email:
            existing = User.query.filter_by(email=new_email).first()
            if existing:
                return jsonify({'error': '邮箱已被其他用户使用'}), 409
            user.email = new_email
    
    if 'password' in data:
        if len(data['password']) < 6:
            return jsonify({'error': '密码长度至少6位'}), 400
        user.set_password(data['password'])
    
    # 保存更新
    db.session.commit()
    
    return jsonify({
        'message': '更新成功',
        'user': user.to_dict()
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """用户登出
    
    注意：由于使用 JWT，令牌登出需要在客户端移除令牌
    此接口主要用于记录日志或处理其他清理逻辑
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 登出成功消息
    """
    return jsonify({
        'message': '登出成功'
    }), 200

"""
TaskFlow 任务管理系统 - 分类路由
处理任务分类的 CRUD 操作
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Category

# 创建分类蓝图
categories_bp = Blueprint('categories', __name__)


@categories_bp.route('', methods=['GET'])
@jwt_required()
def get_categories():
    """获取当前用户的所有分类
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        categories: 分类列表
    """
    current_user_id = get_jwt_identity()
    
    categories = Category.query.filter_by(user_id=current_user_id)\
        .order_by(Category.created_at.desc()).all()
    
    return jsonify({
        'categories': [c.to_dict() for c in categories]
    }), 200


@categories_bp.route('/<int:category_id>', methods=['GET'])
@jwt_required()
def get_category(category_id):
    """获取单个分类详情
    
    路径参数:
        category_id: 分类ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        category: 分类详情
    
    错误响应:
        404: 分类不存在
        403: 无权限访问
    """
    current_user_id = get_jwt_identity()
    
    category = Category.query.get(category_id)
    
    if not category:
        return jsonify({'error': '分类不存在'}), 404
    
    # 检查权限
    if category.user_id != current_user_id:
        return jsonify({'error': '无权限访问此分类'}), 403
    
    return jsonify({
        'category': category.to_dict()
    }), 200


@categories_bp.route('', methods=['POST'])
@jwt_required()
def create_category():
    """创建新分类
    
    请求体:
        name: 分类名称（必填）
        color: 分类颜色（可选，默认#3498db）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (201):
        message: 创建成功消息
        category: 新建的分类
    
    错误响应:
        400: 参数验证失败
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '分类名称不能为空'}), 400
    
    if len(name) > 50:
        return jsonify({'error': '分类名称不能超过50个字符'}), 400
    
    # 验证颜色格式
    color = data.get('color', '#3498db').strip()
    if not color.startswith('#') or len(color) != 7:
        # 使用默认颜色
        color = '#3498db'
    
    # 检查是否已存在同名分类
    existing = Category.query.filter_by(
        user_id=current_user_id,
        name=name
    ).first()
    
    if existing:
        return jsonify({'error': '分类名称已存在'}), 409
    
    # 创建分类
    category = Category(
        name=name,
        color=color,
        user_id=current_user_id
    )
    
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        'message': '分类创建成功',
        'category': category.to_dict()
    }), 201


@categories_bp.route('/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_category(category_id):
    """更新分类
    
    路径参数:
        category_id: 分类ID
    
    请求体:
        name: 分类名称（可选）
        color: 分类颜色（可选）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 更新成功消息
        category: 更新后的分类
    
    错误响应:
        400: 参数验证失败
        403: 无权限修改
        404: 分类不存在
        409: 分类名称已存在
    """
    current_user_id = get_jwt_identity()
    
    category = Category.query.get(category_id)
    
    if not category:
        return jsonify({'error': '分类不存在'}), 404
    
    # 检查权限
    if category.user_id != current_user_id:
        return jsonify({'error': '无权限修改此分类'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    # 更新名称
    if 'name' in data:
        name = data['name'].strip()
        if not name:
            return jsonify({'error': '分类名称不能为空'}), 400
        
        if len(name) > 50:
            return jsonify({'error': '分类名称不能超过50个字符'}), 400
        
        # 检查是否与其他分类重名
        existing = Category.query.filter(
            Category.user_id == current_user_id,
            Category.name == name,
            Category.id != category_id
        ).first()
        
        if existing:
            return jsonify({'error': '分类名称已存在'}), 409
        
        category.name = name
    
    # 更新颜色
    if 'color' in data:
        color = data['color'].strip()
        if color.startswith('#') and len(color) == 7:
            category.color = color
    
    db.session.commit()
    
    return jsonify({
        'message': '分类更新成功',
        'category': category.to_dict()
    }), 200


@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    """删除分类
    
    注意：删除分类不会删除该分类下的任务，
    任务将变为无分类状态
    
    路径参数:
        category_id: 分类ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 删除成功消息
    
    错误响应:
        403: 无权限删除
        404: 分类不存在
    """
    current_user_id = get_jwt_identity()
    
    category = Category.query.get(category_id)
    
    if not category:
        return jsonify({'error': '分类不存在'}), 404
    
    # 检查权限
    if category.user_id != current_user_id:
        return jsonify({'error': '无权限删除此分类'}), 403
    
    # 将该分类的任务设为无分类
    from app.models import Task
    Task.query.filter_by(category_id=category_id).update({'category_id': None})
    
    db.session.delete(category)
    db.session.commit()
    
    return jsonify({
        'message': '分类删除成功'
    }), 200

"""
TaskFlow 任务管理系统 - 通知路由
处理通知相关功能
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Notification
from app.utils.decorators import paginate

# 创建通知蓝图
notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('', methods=['GET'])
@jwt_required()
def get_notifications():
    """获取当前用户的通知列表
    
    查询参数:
        page: 页码（默认1）
        per_page: 每页数量（默认20）
        is_read: 已读状态筛选（true/false）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        notifications: 通知列表
        pagination: 分页信息
    """
    current_user_id = get_jwt_identity()
    
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    is_read = request.args.get('is_read')
    
    # 构建查询
    query = Notification.query.filter_by(user_id=current_user_id)
    
    if is_read is not None:
        query = query.filter(Notification.is_read == (is_read.lower() == 'true'))
    
    # 按创建时间倒序
    query = query.order_by(Notification.created_at.desc())
    
    # 分页
    result = paginate(query, page, per_page)
    
    return jsonify(result), 200


@notifications_bp.route('/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
def mark_as_read(notification_id):
    """标记通知为已读
    
    路径参数:
        notification_id: 通知ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 操作成功消息
    """
    current_user_id = get_jwt_identity()
    
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user_id
    ).first()
    
    if not notification:
        return jsonify({'error': '通知不存在'}), 404
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({
        'message': '标记已读成功'
    }), 200


@notifications_bp.route('/read-all', methods=['PUT'])
@jwt_required()
def mark_all_as_read():
    """标记所有通知为已读
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 操作成功消息
    """
    current_user_id = get_jwt_identity()
    
    Notification.query.filter_by(
        user_id=current_user_id,
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    return jsonify({
        'message': '全部标记已读成功'
    }), 200


@notifications_bp.route('/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    """获取未读通知数量
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        count: 未读数量
    """
    current_user_id = get_jwt_identity()
    
    count = Notification.query.filter_by(
        user_id=current_user_id,
        is_read=False
    ).count()
    
    return jsonify({
        'count': count
    }), 200

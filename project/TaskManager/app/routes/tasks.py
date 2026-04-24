"""
TaskFlow 任务管理系统 - 任务路由
处理任务的 CRUD 操作
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from app import db
from app.models import Task, Category, TaskComment
from app.utils.decorators import paginate

# 创建任务蓝图
tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    """获取任务列表
    
    查询参数:
        page: 页码（默认1）
        per_page: 每页数量（默认20）
        status: 任务状态筛选（pending/in_progress/completed/cancelled）
        priority: 优先级筛选（low/medium/high/urgent）
        category_id: 分类ID筛选
        team_id: 团队ID筛选
        due_date_from: 到期日开始筛选
        due_date_to: 到期日结束筛选
        search: 搜索关键词（标题和描述）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        tasks: 任务列表
        pagination: 分页信息
    """
    current_user_id = get_jwt_identity()
    
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    priority = request.args.get('priority')
    category_id = request.args.get('category_id', type=int)
    team_id = request.args.get('team_id', type=int)
    due_date_from = request.args.get('due_date_from')
    due_date_to = request.args.get('due_date_to')
    search = request.args.get('search', '').strip()
    
    # 构建基础查询（自己的任务 + 被分配的任务）
    query = Task.query.filter(
        (Task.user_id == current_user_id) | 
        (Task.assigned_to == current_user_id)
    )
    
    # 应用筛选条件
    if status:
        query = query.filter(Task.status == status)
    
    if priority:
        query = query.filter(Task.priority == priority)
    
    if category_id:
        query = query.filter(Task.category_id == category_id)
    
    if team_id:
        query = query.filter(Task.team_id == team_id)
    
    if due_date_from:
        try:
            date_from = datetime.fromisoformat(due_date_from.replace('Z', '+00:00'))
            query = query.filter(Task.due_date >= date_from)
        except ValueError:
            pass
    
    if due_date_to:
        try:
            date_to = datetime.fromisoformat(due_date_to.replace('Z', '+00:00'))
            query = query.filter(Task.due_date <= date_to)
        except ValueError:
            pass
    
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern)
            )
        )
    
    # 按创建时间倒序
    query = query.order_by(Task.created_at.desc())
    
    # 分页
    result = paginate(query, page, per_page)
    
    return jsonify(result), 200


@tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    """获取单个任务详情
    
    路径参数:
        task_id: 任务ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        task: 任务详情
    
    错误响应:
        404: 任务不存在
        403: 无权限访问
    """
    current_user_id = get_jwt_identity()
    
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 检查权限（所有者或被分配者）
    if task.user_id != current_user_id and task.assigned_to != current_user_id:
        return jsonify({'error': '无权限访问此任务'}), 403
    
    return jsonify({
        'task': task.to_dict(include_owner=True)
    }), 200


@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    """创建新任务
    
    请求体:
        title: 任务标题（必填）
        description: 任务描述（可选）
        priority: 优先级（low/medium/high/urgent，默认medium）
        due_date: 到期日（可选，ISO格式）
        category_id: 分类ID（可选）
        team_id: 团队ID（可选）
        assigned_to: 分配给用户ID（可选）
        reminder_time: 提醒时间（可选，ISO格式）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (201):
        message: 创建成功消息
        task: 新建的任务
    
    错误响应:
        400: 参数验证失败
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    # 验证必填字段
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': '任务标题不能为空'}), 400
    
    # 验证分类权限
    category_id = data.get('category_id')
    if category_id:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({'error': '分类不存在'}), 404
        if category.user_id != current_user_id:
            return jsonify({'error': '无权限使用此分类'}), 403
    
    # 解析日期
    due_date = None
    if data.get('due_date'):
        try:
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': '到期日格式无效'}), 400
    
    reminder_time = None
    reminder_set = False
    if data.get('reminder_time'):
        try:
            reminder_time = datetime.fromisoformat(data['reminder_time'].replace('Z', '+00:00'))
            reminder_set = True
        except ValueError:
            return jsonify({'error': '提醒时间格式无效'}), 400
    
    # 创建任务
    task = Task(
        title=title,
        description=data.get('description', '').strip() or None,
        priority=data.get('priority', 'medium'),
        due_date=due_date,
        category_id=category_id,
        team_id=data.get('team_id'),
        assigned_to=data.get('assigned_to'),
        user_id=current_user_id,
        reminder_time=reminder_time,
        is_reminder_set=reminder_set
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify({
        'message': '任务创建成功',
        'task': task.to_dict()
    }), 201


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    """更新任务
    
    路径参数:
        task_id: 任务ID
    
    请求体:
        title: 任务标题（可选）
        description: 任务描述（可选）
        status: 任务状态（可选）
        priority: 优先级（可选）
        due_date: 到期日（可选）
        category_id: 分类ID（可选）
        team_id: 团队ID（可选）
        assigned_to: 分配给用户ID（可选）
        reminder_time: 提醒时间（可选）
        is_reminder_set: 是否设置提醒（可选）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 更新成功消息
        task: 更新后的任务
    
    错误响应:
        400: 参数验证失败
        403: 无权限修改
        404: 任务不存在
    """
    current_user_id = get_jwt_identity()
    
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 检查权限
    if task.user_id != current_user_id:
        return jsonify({'error': '无权限修改此任务'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    # 更新字段
    if 'title' in data:
        title = data['title'].strip()
        if not title:
            return jsonify({'error': '任务标题不能为空'}), 400
        task.title = title
    
    if 'description' in data:
        task.description = data['description'].strip() if data['description'] else None
    
    if 'status' in data:
        status = data['status']
        valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
        if status not in valid_statuses:
            return jsonify({'error': f'无效的状态，可选值: {valid_statuses}'}), 400
        
        # 如果完成任务，设置完成时间
        if status == 'completed' and task.status != 'completed':
            task.completed_at = datetime.utcnow()
        task.status = status
    
    if 'priority' in data:
        priority = data['priority']
        valid_priorities = ['low', 'medium', 'high', 'urgent']
        if priority not in valid_priorities:
            return jsonify({'error': f'无效的优先级，可选值: {valid_priorities}'}), 400
        task.priority = priority
    
    if 'due_date' in data:
        if data['due_date']:
            try:
                task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': '到期日格式无效'}), 400
        else:
            task.due_date = None
    
    if 'category_id' in data:
        if data['category_id']:
            category = Category.query.get(data['category_id'])
            if not category:
                return jsonify({'error': '分类不存在'}), 404
            if category.user_id != current_user_id:
                return jsonify({'error': '无权限使用此分类'}), 403
        task.category_id = data['category_id']
    
    if 'team_id' in data:
        task.team_id = data['team_id']
    
    if 'assigned_to' in data:
        task.assigned_to = data['assigned_to']
    
    if 'reminder_time' in data:
        if data['reminder_time']:
            try:
                task.reminder_time = datetime.fromisoformat(data['reminder_time'].replace('Z', '+00:00'))
                task.is_reminder_set = True
            except ValueError:
                return jsonify({'error': '提醒时间格式无效'}), 400
        else:
            task.reminder_time = None
            task.is_reminder_set = False
    
    if 'is_reminder_set' in data:
        task.is_reminder_set = data['is_reminder_set']
        if not data['is_reminder_set']:
            task.reminder_time = None
    
    db.session.commit()
    
    return jsonify({
        'message': '任务更新成功',
        'task': task.to_dict()
    }), 200


@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """删除任务
    
    路径参数:
        task_id: 任务ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 删除成功消息
    
    错误响应:
        403: 无权限删除
        404: 任务不存在
    """
    current_user_id = get_jwt_identity()
    
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 检查权限
    if task.user_id != current_user_id:
        return jsonify({'error': '无权限删除此任务'}), 403
    
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({
        'message': '任务删除成功'
    }), 200


@tasks_bp.route('/<int:task_id>/comments', methods=['GET'])
@jwt_required()
def get_task_comments(task_id):
    """获取任务的评论列表
    
    路径参数:
        task_id: 任务ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        comments: 评论列表
    """
    current_user_id = get_jwt_identity()
    
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 检查权限
    if task.user_id != current_user_id and task.assigned_to != current_user_id:
        return jsonify({'error': '无权限访问此任务'}), 403
    
    comments = TaskComment.query.filter_by(task_id=task_id)\
        .order_by(TaskComment.created_at.asc()).all()
    
    return jsonify({
        'comments': [c.to_dict() for c in comments]
    }), 200


@tasks_bp.route('/<int:task_id>/comments', methods=['POST'])
@jwt_required()
def create_task_comment(task_id):
    """添加任务评论
    
    路径参数:
        task_id: 任务ID
    
    请求体:
        content: 评论内容（必填）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (201):
        message: 创建成功消息
        comment: 新建的评论
    """
    current_user_id = get_jwt_identity()
    
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 检查权限
    if task.user_id != current_user_id and task.assigned_to != current_user_id:
        return jsonify({'error': '无权限评论此任务'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': '评论内容不能为空'}), 400
    
    comment = TaskComment(
        task_id=task_id,
        user_id=current_user_id,
        content=content
    )
    
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({
        'message': '评论添加成功',
        'comment': comment.to_dict()
    }), 201


@tasks_bp.route('/<int:task_id>/comments/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_task_comment(task_id, comment_id):
    """删除任务评论
    
    路径参数:
        task_id: 任务ID
        comment_id: 评论ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 删除成功消息
    """
    current_user_id = get_jwt_identity()
    
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    comment = TaskComment.query.get(comment_id)
    if not comment:
        return jsonify({'error': '评论不存在'}), 404
    
    # 检查权限（评论者或任务所有者可以删除）
    if comment.user_id != current_user_id and task.user_id != current_user_id:
        return jsonify({'error': '无权限删除此评论'}), 403
    
    db.session.delete(comment)
    db.session.commit()
    
    return jsonify({
        'message': '评论删除成功'
    }), 200

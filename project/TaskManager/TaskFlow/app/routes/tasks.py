# TaskFlow 任务路由
# 处理任务的CRUD操作和相关功能

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.task import Task, TaskComment, TaskPriority, TaskStatus
from app.models.category import Category
from app.models.team import Team
from app.models.notification import Notification
from app.utils.decorators import ajax_login_required
from app.utils.validators import validate_task_data
from app.utils.helpers import success_response, error_response, paginate_query, calculate_task_stats
from app.services.task_service import TaskService

tasks_bp = Blueprint('tasks', __name__)
task_service = TaskService()


@tasks_bp.route('/')
@login_required
def list():
    """
    任务列表页面
    支持筛选、排序、分页
    """
    # 获取查询参数
    status = request.args.get('status')
    priority = request.args.get('priority', type=int)
    category_id = request.args.get('category_id', type=int)
    team_id = request.args.get('team_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sort_by = request.args.get('sort_by', 'created_at')
    order = request.args.get('order', 'desc')
    
    # 构建查询
    query = Task.query.filter_by(user_id=current_user.id)
    
    # 应用筛选
    if status:
        query = query.filter_by(status=status)
    
    if priority:
        query = query.filter_by(priority=priority)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if team_id:
        query = query.filter_by(team_id=team_id)
    
    # 排序
    if sort_by == 'due_date':
        if order == 'asc':
            query = query.order_by(Task.due_date.asc().nullslast())
        else:
            query = query.order_by(Task.due_date.desc().nullsfirst())
    elif sort_by == 'priority':
        if order == 'asc':
            query = query.order_by(Task.priority.asc())
        else:
            query = query.order_by(Task.priority.desc())
    elif sort_by == 'created_at':
        if order == 'asc':
            query = query.order_by(Task.created_at.asc())
        else:
            query = query.order_by(Task.created_at.desc())
    else:
        query = query.order_by(Task.created_at.desc())
    
    # 分页
    pagination = paginate_query(query, page, per_page)
    
    # 获取用户的分类
    categories = Category.query.filter_by(user_id=current_user.id).all()
    
    # 获取用户加入的团队
    teams = [m.team for m in current_user.team_memberships]
    owned_teams = Team.query.filter_by(owner_id=current_user.id).all()
    all_teams = list(set(teams + owned_teams))
    
    return render_template(
        'tasks/list.html',
        tasks=pagination['items'],
        pagination=pagination,
        categories=categories,
        teams=all_teams,
        filters={
            'status': status,
            'priority': priority,
            'category_id': category_id,
            'team_id': team_id,
            'sort_by': sort_by,
            'order': order
        },
        TaskStatus=TaskStatus,
        TaskPriority=TaskPriority
    )


@tasks_bp.route('/<int:task_id>')
@login_required
def detail(task_id):
    """
    任务详情页面
    """
    task = Task.query.get_or_404(task_id)
    
    # 检查权限
    if task.user_id != current_user.id:
        if not task.team or not task.team.is_member(current_user.id):
            abort(403)
    
    # 获取评论
    comments = task.comments.order_by(TaskComment.created_at.desc()).all()
    
    return render_template(
        'tasks/detail.html',
        task=task,
        comments=comments,
        TaskStatus=TaskStatus,
        TaskPriority=TaskPriority
    )


@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    创建任务页面/处理
    """
    if request.method == 'POST':
        # 获取表单数据
        data = {
            'title': request.form.get('title', '').strip(),
            'description': request.form.get('description', '').strip(),
            'priority': request.form.get('priority', TaskPriority.MEDIUM.value, type=int),
            'status': request.form.get('status', TaskStatus.PENDING.value),
            'due_date': request.form.get('due_date', '').strip(),
            'start_date': request.form.get('start_date', '').strip(),
            'estimated_hours': request.form.get('estimated_hours', type=float),
            'category_id': request.form.get('category_id', type=int),
            'team_id': request.form.get('team_id', type=int),
            'tags': request.form.get('tags', '').strip()
        }
        
        # 验证数据
        is_valid, error, errors = validate_task_data(data)
        if not is_valid:
            for field, message in errors.items():
                flash(message, 'danger')
            return redirect(url_for('tasks.create'))
        
        # 处理日期
        if data['due_date']:
            try:
                data['due_date'] = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except ValueError:
                flash('到期日期格式无效', 'danger')
                return redirect(url_for('tasks.create'))
        
        if data['start_date']:
            try:
                data['start_date'] = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
            except ValueError:
                flash('开始日期格式无效', 'danger')
                return redirect(url_for('tasks.create'))
        
        # 处理标签
        if data['tags']:
            tag_list = [t.strip() for t in data['tags'].split(',') if t.strip()]
            import json
            data['tags'] = json.dumps(tag_list, ensure_ascii=False)
        
        # 创建任务
        task = Task(
            title=data['title'],
            description=data['description'],
            priority=data['priority'],
            status=data['status'],
            due_date=data.get('due_date'),
            start_date=data.get('start_date'),
            estimated_hours=data.get('estimated_hours'),
            category_id=data.get('category_id'),
            team_id=data.get('team_id'),
            tags=data.get('tags'),
            user_id=current_user.id
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash('任务创建成功', 'success')
        return redirect(url_for('tasks.detail', task_id=task.id))
    
    # GET 请求
    categories = Category.query.filter_by(user_id=current_user.id).all()
    teams = [m.team for m in current_user.team_memberships]
    owned_teams = Team.query.filter_by(owner_id=current_user.id).all()
    all_teams = list(set(teams + owned_teams))
    
    return render_template(
        'tasks/form.html',
        task=None,
        categories=categories,
        teams=all_teams,
        TaskPriority=TaskPriority,
        TaskStatus=TaskStatus
    )


@tasks_bp.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    """
    编辑任务页面/处理
    """
    task = Task.query.get_or_404(task_id)
    
    # 检查权限
    if task.user_id != current_user.id:
        if not task.team or not task.team.is_member(current_user.id):
            abort(403)
    
    if request.method == 'POST':
        # 获取表单数据
        data = {
            'title': request.form.get('title', '').strip(),
            'description': request.form.get('description', '').strip(),
            'priority': request.form.get('priority', type=int),
            'status': request.form.get('status'),
            'due_date': request.form.get('due_date', '').strip(),
            'start_date': request.form.get('start_date', '').strip(),
            'estimated_hours': request.form.get('estimated_hours', type=float),
            'category_id': request.form.get('category_id', type=int),
            'team_id': request.form.get('team_id', type=int),
            'tags': request.form.get('tags', '').strip(),
            'reminder_enabled': request.form.get('reminder_enabled') == 'on'
        }
        
        # 验证数据
        is_valid, error, errors = validate_task_data(data, is_update=True)
        if not is_valid:
            for field, message in errors.items():
                flash(message, 'danger')
            return redirect(url_for('tasks.edit', task_id=task_id))
        
        # 处理日期
        if data['due_date']:
            try:
                data['due_date'] = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except ValueError:
                flash('到期日期格式无效', 'danger')
                return redirect(url_for('tasks.edit', task_id=task_id))
        else:
            data['due_date'] = None
        
        if data['start_date']:
            try:
                data['start_date'] = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
            except ValueError:
                flash('开始日期格式无效', 'danger')
                return redirect(url_for('tasks.edit', task_id=task_id))
        else:
            data['start_date'] = None
        
        # 处理标签
        if data['tags']:
            tag_list = [t.strip() for t in data['tags'].split(',') if t.strip()]
            import json
            data['tags'] = json.dumps(tag_list, ensure_ascii=False)
        else:
            data['tags'] = None
        
        # 更新任务
        for key, value in data.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        # 如果状态变为完成，记录完成时间
        if data['status'] == TaskStatus.COMPLETED.value and task.status != TaskStatus.COMPLETED.value:
            task.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('任务更新成功', 'success')
        return redirect(url_for('tasks.detail', task_id=task.id))
    
    # GET 请求
    categories = Category.query.filter_by(user_id=current_user.id).all()
    teams = [m.team for m in current_user.team_memberships]
    owned_teams = Team.query.filter_by(owner_id=current_user.id).all()
    all_teams = list(set(teams + owned_teams))
    
    return render_template(
        'tasks/form.html',
        task=task,
        categories=categories,
        teams=all_teams,
        TaskPriority=TaskPriority,
        TaskStatus=TaskStatus
    )


@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
def delete(task_id):
    """
    删除任务
    """
    task = Task.query.get_or_404(task_id)
    
    # 检查权限
    if task.user_id != current_user.id:
        if not task.team or not task.team.is_owner(current_user.id):
            abort(403)
    
    db.session.delete(task)
    db.session.commit()
    
    flash('任务已删除', 'success')
    return redirect(url_for('tasks.list'))


@tasks_bp.route('/<int:task_id>/complete', methods=['POST'])
@login_required
def complete(task_id):
    """
    完成任务
    """
    task = Task.query.get_or_404(task_id)
    
    # 检查权限
    if task.user_id != current_user.id:
        if not task.team or not task.team.is_member(current_user.id):
            abort(403)
    
    task.mark_completed()
    db.session.commit()
    
    flash('任务已完成', 'success')
    return redirect(url_for('tasks.detail', task_id=task.id))


@tasks_bp.route('/<int:task_id>/comment', methods=['POST'])
@login_required
def add_comment(task_id):
    """
    添加任务评论
    """
    task = Task.query.get_or_404(task_id)
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('评论内容不能为空', 'danger')
        return redirect(url_for('tasks.detail', task_id=task_id))
    
    # 检查权限
    if task.user_id != current_user.id:
        if not task.team or not task.team.is_member(current_user.id):
            abort(403)
    
    # 创建评论
    comment = TaskComment(
        content=content,
        task_id=task.id,
        user_id=current_user.id
    )
    
    db.session.add(comment)
    db.session.commit()
    
    flash('评论已添加', 'success')
    return redirect(url_for('tasks.detail', task_id=task_id))


# API 端点

@tasks_bp.route('/api/tasks', methods=['GET'])
@ajax_login_required
def api_list():
    """
    获取任务列表（API）
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Task.query.filter_by(user_id=current_user.id)
    
    # 可选的筛选参数
    status = request.args.get('status')
    priority = request.args.get('priority', type=int)
    category_id = request.args.get('category_id', type=int)
    
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    pagination = paginate_query(query, page, per_page)
    
    return jsonify({
        'success': True,
        'tasks': [t.to_dict() for t in pagination['items']],
        'pagination': {
            'page': pagination['page'],
            'per_page': pagination['per_page'],
            'total': pagination['total'],
            'pages': pagination['pages']
        }
    })


@tasks_bp.route('/api/tasks', methods=['POST'])
@ajax_login_required
def api_create():
    """
    创建任务（API）
    """
    data = request.get_json()
    
    is_valid, error, errors = validate_task_data(data)
    if not is_valid:
        return error_response(error, 'VALIDATION_ERROR', 400, errors=errors)
    
    # 处理日期
    due_date = None
    if data.get('due_date'):
        try:
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return error_response('到期日期格式无效', 'INVALID_DATE')
    
    # 处理标签
    tags = None
    if data.get('tags'):
        import json
        tags = json.dumps(data['tags'], ensure_ascii=False)
    
    task = Task(
        title=data['title'],
        description=data.get('description'),
        priority=data.get('priority', TaskPriority.MEDIUM.value),
        status=data.get('status', TaskStatus.PENDING.value),
        due_date=due_date,
        category_id=data.get('category_id'),
        team_id=data.get('team_id'),
        tags=tags,
        user_id=current_user.id
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '任务创建成功',
        'task': task.to_dict()
    }), 201


@tasks_bp.route('/api/tasks/<int:task_id>', methods=['GET'])
@ajax_login_required
def api_detail(task_id):
    """
    获取任务详情（API）
    """
    task = Task.query.get_or_404(task_id)
    
    # 检查权限
    if task.user_id != current_user.id:
        if not task.team or not task.team.is_member(current_user.id):
            return error_response('权限不足', 'FORBIDDEN', 403)
    
    return jsonify({
        'success': True,
        'task': task.to_dict()
    })


@tasks_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
@ajax_login_required
def api_update(task_id):
    """
    更新任务（API）
    """
    task = Task.query.get_or_404(task_id)
    
    # 检查权限
    if task.user_id != current_user.id:
        if not task.team or not task.team.is_member(current_user.id):
            return error_response('权限不足', 'FORBIDDEN', 403)
    
    data = request.get_json()
    
    is_valid, error, errors = validate_task_data(data, is_update=True)
    if not is_valid:
        return error_response(error, 'VALIDATION_ERROR', 400, errors=errors)
    
    # 更新字段
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'priority' in data:
        task.priority = data['priority']
    if 'status' in data:
        task.status = data['status']
        if data['status'] == TaskStatus.COMPLETED.value:
            task.completed_at = datetime.utcnow()
    if 'category_id' in data:
        task.category_id = data['category_id']
    if 'team_id' in data:
        task.team_id = data['team_id']
    
    if 'due_date' in data:
        if data['due_date']:
            try:
                task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except ValueError:
                return error_response('到期日期格式无效', 'INVALID_DATE')
        else:
            task.due_date = None
    
    if 'tags' in data:
        import json
        task.tags = json.dumps(data['tags'], ensure_ascii=False) if data['tags'] else None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '任务更新成功',
        'task': task.to_dict()
    })


@tasks_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@ajax_login_required
def api_delete(task_id):
    """
    删除任务（API）
    """
    task = Task.query.get_or_404(task_id)
    
    # 检查权限
    if task.user_id != current_user.id:
        if not task.team or not task.team.is_owner(current_user.id):
            return error_response('权限不足', 'FORBIDDEN', 403)
    
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '任务已删除'
    })


@tasks_bp.route('/api/stats')
@ajax_login_required
def api_stats():
    """
    获取任务统计（API）
    """
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    stats = calculate_task_stats(tasks)
    
    # 按状态统计
    status_counts = {}
    for status in TaskStatus:
        count = Task.query.filter_by(
            user_id=current_user.id,
            status=status.value
        ).count()
        status_counts[status.value] = count
    
    # 按优先级统计
    priority_counts = {}
    for priority in TaskPriority:
        count = Task.query.filter_by(
            user_id=current_user.id,
            priority=priority.value
        ).count()
        priority_counts[priority.value] = count
    
    return jsonify({
        'success': True,
        'stats': stats,
        'status_counts': status_counts,
        'priority_counts': priority_counts
    })

# TaskFlow 主路由
# 处理主页、仪表盘、通知等核心功能

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app import db
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.category import Category
from app.models.team import Team
from app.models.notification import Notification
from app.utils.helpers import calculate_task_stats

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """
    首页
    未登录用户显示欢迎页，已登录用户跳转到仪表盘
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """
    仪表盘页面
    显示任务概览、统计数据、快速操作
    """
    # 获取统计信息
    total_tasks = Task.query.filter_by(user_id=current_user.id).count()
    pending_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status.in_(['pending', 'in_progress'])
    ).count()
    completed_tasks = Task.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).count()
    overdue_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.due_date < datetime.utcnow(),
        Task.status.in_(['pending', 'in_progress'])
    ).count()
    
    # 获取今日到期任务
    today = datetime.utcnow().replace(hour=23, minute=59, second=59)
    today_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.due_date <= today,
        Task.status.in_(['pending', 'in_progress'])
    ).order_by(Task.due_date.asc()).limit(5).all()
    
    # 获取最近创建的任务
    recent_tasks = Task.query.filter_by(
        user_id=current_user.id
    ).order_by(Task.created_at.desc()).limit(5).all()
    
    # 获取分类统计
    categories = Category.query.filter_by(user_id=current_user.id).all()
    category_stats = []
    for cat in categories:
        pending = cat.tasks.filter(
            Task.status.in_(['pending', 'in_progress'])
        ).count()
        category_stats.append({
            'category': cat,
            'pending_count': pending,
            'total_count': cat.tasks.count()
        })
    
    # 获取团队任务
    team_tasks = []
    for membership in current_user.team_memberships:
        tasks = Task.query.filter_by(team_id=membership.team_id).limit(3).all()
        for task in tasks:
            team_tasks.append({
                'task': task,
                'team': membership.team
            })
    
    # 限制显示数量
    team_tasks = team_tasks[:5]
    
    # 获取未读通知
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template(
        'dashboard.html',
        stats={
            'total': total_tasks,
            'pending': pending_tasks,
            'completed': completed_tasks,
            'overdue': overdue_tasks,
            'completion_rate': round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0
        },
        today_tasks=today_tasks,
        recent_tasks=recent_tasks,
        category_stats=category_stats,
        team_tasks=team_tasks,
        unread_notifications=unread_notifications,
        TaskPriority=TaskPriority,
        TaskStatus=TaskStatus
    )


@main_bp.route('/notifications')
@login_required
def notifications():
    """
    通知列表页面
    """
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 获取通知
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template(
        'notifications.html',
        notifications=notifications.items,
        pagination=notifications,
        page=page
    )


@main_bp.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """
    标记通知为已读
    """
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': '权限不足'}), 403
    
    notification.mark_as_read()
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    return redirect(url_for('main.notifications'))


@main_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """
    标记所有通知为已读
    """
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    return redirect(url_for('main.notifications'))


@main_bp.route('/api/notifications/unread-count')
@login_required
def api_unread_count():
    """
    获取未读通知数量（API）
    """
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({
        'success': True,
        'count': count
    })


@main_bp.route('/api/notifications')
@login_required
def api_notifications():
    """
    获取通知列表（API）
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'notifications': [n.to_dict() for n in notifications.items],
        'pagination': {
            'page': notifications.page,
            'per_page': notifications.per_page,
            'total': notifications.total,
            'pages': notifications.pages
        }
    })


@main_bp.route('/search')
@login_required
def search():
    """
    搜索页面
    """
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')
    
    if not query:
        return render_template('search.html', results=None, query='')
    
    results = {
        'tasks': [],
        'categories': [],
        'teams': []
    }
    
    if search_type in ['all', 'tasks']:
        # 搜索任务
        tasks = Task.query.filter(
            Task.user_id == current_user.id,
            Task.title.ilike(f'%{query}%')
        ).limit(20).all()
        results['tasks'] = [t.to_dict() for t in tasks]
    
    if search_type in ['all', 'categories']:
        # 搜索分类
        categories = Category.query.filter(
            Category.user_id == current_user.id,
            Category.name.ilike(f'%{query}%')
        ).limit(10).all()
        results['categories'] = [c.to_dict() for c in categories]
    
    if search_type in ['all', 'teams']:
        # 搜索团队
        teams = Team.query.filter(
            (Team.owner_id == current_user.id) | (Team.is_public == True),
            Team.name.ilike(f'%{query}%')
        ).limit(10).all()
        results['teams'] = [t.to_dict() for t in teams]
    
    return render_template(
        'search.html',
        results=results,
        query=query,
        search_type=search_type
    )


@main_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """
    设置页面
    """
    if request.method == 'POST':
        # 更新设置
        # 这里可以添加更多设置项
        flash('设置已保存', 'success')
        return redirect(url_for('main.settings'))
    
    return render_template('settings.html')


@main_bp.route('/about')
def about():
    """
    关于页面
    """
    return render_template('about.html')

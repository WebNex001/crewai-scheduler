# TaskFlow 辅助函数模块
# 提供各种工具函数

import hashlib
from datetime import datetime, timedelta
from flask import current_app, flash, session
from flask_login import current_user


def generate_avatar_url(email, size=200):
    """
    生成头像URL（使用Gravatar）
    
    Args:
        email: 邮箱地址
        size: 头像大小
    
    Returns:
        str: 头像URL
    """
    if not email:
        # 返回默认头像
        return f'https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&s={size}'
    
    # 生成MD5哈希
    email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    
    # 构建Gravatar URL
    # 使用默认图像
    return f'https://www.gravatar.com/avatar/{email_hash}?d=identicon&s={size}'


def get_notification_count():
    """
    获取当前用户未读通知数量
    
    Returns:
        int: 未读通知数量
    """
    if not current_user.is_authenticated:
        return 0
    
    from app.models.notification import Notification
    return Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()


def format_datetime(dt, format_str=None):
    """
    格式化日期时间
    
    Args:
        dt: datetime对象
        format_str: 格式字符串
    
    Returns:
        str: 格式化后的日期时间字符串
    """
    if not dt:
        return ''
    
    if format_str:
        return dt.strftime(format_str)
    
    # 默认格式
    return dt.strftime('%Y-%m-%d %H:%M')


def format_date(dt):
    """
    格式化日期
    
    Args:
        dt: datetime对象
    
    Returns:
        str: 格式化后的日期字符串
    """
    if not dt:
        return ''
    return dt.strftime('%Y-%m-%d')


def format_time(dt):
    """
    格式化时间
    
    Args:
        dt: datetime对象
    
    Returns:
        str: 格式化后的时间字符串
    """
    if not dt:
        return ''
    return dt.strftime('%H:%M')


def time_ago(dt):
    """
    获取相对时间字符串
    
    Args:
        dt: datetime对象
    
    Returns:
        str: 相对时间字符串
    """
    if not dt:
        return ''
    
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return '刚刚'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes}分钟前'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours}小时前'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days}天前'
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f'{weeks}周前'
    elif seconds < 31536000:
        months = int(seconds / 2592000)
        return f'{months}个月前'
    else:
        years = int(seconds / 31536000)
        return f'{years}年前'


def format_duration(hours):
    """
    格式化时长
    
    Args:
        hours: 小时数
    
    Returns:
        str: 格式化后的时长字符串
    """
    if not hours:
        return '0小时'
    
    if hours < 1:
        minutes = int(hours * 60)
        return f'{minutes}分钟'
    
    if hours < 24:
        return f'{hours}小时'
    
    days = int(hours / 24)
    remaining_hours = int(hours % 24)
    
    if remaining_hours > 0:
        return f'{days}天{remaining_hours}小时'
    return f'{days}天'


def flash_errors(form):
    """
    表单验证错误提示
    
    Args:
        form: WTForms表单对象
    """
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{getattr(form, field).label.text}: {error}', 'danger')


def success_response(message=None, data=None, **kwargs):
    """
    构建成功响应
    
    Args:
        message: 成功消息
        data: 数据
        **kwargs: 其他字段
    
    Returns:
        dict: 响应字典
    """
    response = {
        'success': True
    }
    
    if message:
        response['message'] = message
    
    if data is not None:
        response['data'] = data
    
    response.update(kwargs)
    
    return response


def error_response(message, code='ERROR', status_code=400, **kwargs):
    """
    构建错误响应
    
    Args:
        message: 错误消息
        code: 错误代码
        status_code: HTTP状态码
        **kwargs: 其他字段
    
    Returns:
        tuple: (response_dict, status_code)
    """
    response = {
        'success': False,
        'error': message,
        'code': code
    }
    
    response.update(kwargs)
    
    return response, status_code


def paginate_query(query, page=1, per_page=20, max_per_page=100):
    """
    分页查询
    
    Args:
        query: SQLAlchemy查询对象
        page: 页码
        per_page: 每页数量
        max_per_page: 每页最大数量
    
    Returns:
        dict: 包含分页信息的字典
    """
    # 限制每页数量
    per_page = min(per_page, max_per_page)
    
    # 执行分页
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return {
        'items': pagination.items,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
        'has_prev': pagination.has_prev,
        'has_next': pagination.has_next,
        'prev_num': pagination.prev_num,
        'next_num': pagination.next_num
    }


def get_client_ip():
    """
    获取客户端IP地址
    
    Returns:
        str: IP地址
    """
    from flask import request
    
    # 检查代理转发
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def calculate_task_stats(tasks):
    """
    计算任务统计信息
    
    Args:
        tasks: 任务查询结果
    
    Returns:
        dict: 统计信息
    """
    total = 0
    completed = 0
    pending = 0
    overdue = 0
    
    now = datetime.utcnow()
    
    for task in tasks:
        total += 1
        if task.status == 'completed':
            completed += 1
        elif task.due_date and task.due_date < now:
            overdue += 1
        else:
            pending += 1
    
    return {
        'total': total,
        'completed': completed,
        'pending': pending,
        'overdue': overdue,
        'completion_rate': round(completed / total * 100, 1) if total > 0 else 0
    }

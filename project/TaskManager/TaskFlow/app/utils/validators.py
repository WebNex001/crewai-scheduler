# TaskFlow 验证器模块
# 提供各种数据验证函数

import re
from datetime import datetime


def validate_email(email):
    """
    验证邮箱格式
    
    Args:
        email: 邮箱地址
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not email:
        return False, '邮箱地址不能为空'
    
    # 邮箱格式正则
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, '邮箱格式不正确'
    
    if len(email) > 120:
        return False, '邮箱地址过长'
    
    return True, None


def validate_username(username):
    """
    验证用户名格式
    
    Args:
        username: 用户名
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not username:
        return False, '用户名不能为空'
    
    if len(username) < 3:
        return False, '用户名至少需要3个字符'
    
    if len(username) > 80:
        return False, '用户名过长'
    
    # 用户名只能包含字母、数字和下划线
    pattern = r'^[a-zA-Z0-9_]+$'
    if not re.match(pattern, username):
        return False, '用户名只能包含字母、数字和下划线'
    
    return True, None


def validate_password(password, min_length=None):
    """
    验证密码强度
    
    Args:
        password: 密码
        min_length: 最小长度
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not password:
        return False, '密码不能为空'
    
    if min_length is None:
        from flask import current_app
        min_length = current_app.config.get('PASSWORD_MIN_LENGTH', 6)
    
    if len(password) < min_length:
        return False, f'密码至少需要{min_length}个字符'
    
    return True, None


def validate_task_data(data, is_update=False):
    """
    验证任务数据
    
    Args:
        data: 任务数据字典
        is_update: 是否为更新操作
    
    Returns:
        tuple: (is_valid, error_message, errors_dict)
    """
    errors = {}
    
    # 标题验证
    if 'title' in data:
        if not data['title'] or not data['title'].strip():
            errors['title'] = '任务标题不能为空'
        elif len(data['title']) > 200:
            errors['title'] = '任务标题过长'
    elif not is_update:
        errors['title'] = '任务标题不能为空'
    
    # 描述验证
    if 'description' in data and data['description']:
        if len(data['description']) > 5000:
            errors['description'] = '任务描述过长'
    
    # 优先级验证
    if 'priority' in data:
        try:
            priority = int(data['priority'])
            if priority < 1 or priority > 4:
                errors['priority'] = '优先级值无效'
        except (ValueError, TypeError):
            errors['priority'] = '优先级值无效'
    
    # 状态验证
    if 'status' in data:
        valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
        if data['status'] not in valid_statuses:
            errors['status'] = '任务状态无效'
    
    # 到期日验证
    if 'due_date' in data and data['due_date']:
        try:
            if isinstance(data['due_date'], str):
                datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            errors['due_date'] = '到期日期格式无效'
    
    # 预估工时验证
    if 'estimated_hours' in data and data['estimated_hours']:
        try:
            hours = float(data['estimated_hours'])
            if hours < 0:
                errors['estimated_hours'] = '预估工时不能为负数'
        except (ValueError, TypeError):
            errors['estimated_hours'] = '预估工时格式无效'
    
    is_valid = len(errors) == 0
    error_message = '; '.join(errors.values()) if errors else None
    
    return is_valid, error_message, errors


def validate_category_data(data, is_update=False):
    """
    验证分类数据
    
    Args:
        data: 分类数据字典
        is_update: 是否为更新操作
    
    Returns:
        tuple: (is_valid, error_message, errors_dict)
    """
    errors = {}
    
    # 名称验证
    if 'name' in data:
        if not data['name'] or not data['name'].strip():
            errors['name'] = '分类名称不能为空'
        elif len(data['name']) > 50:
            errors['name'] = '分类名称过长'
    elif not is_update:
        errors['name'] = '分类名称不能为空'
    
    # 描述验证
    if 'description' in data and data['description']:
        if len(data['description']) > 200:
            errors['description'] = '分类描述过长'
    
    # 颜色验证
    if 'color' in data and data['color']:
        if not re.match(r'^#[0-9A-Fa-f]{6}$', data['color']):
            errors['color'] = '颜色格式无效（应为十六进制颜色值）'
    
    # 图标验证
    if 'icon' in data and data['icon']:
        if len(data['icon']) > 50:
            errors['icon'] = '图标名称过长'
    
    is_valid = len(errors) == 0
    error_message = '; '.join(errors.values()) if errors else None
    
    return is_valid, error_message, errors


def validate_team_data(data, is_update=False):
    """
    验证团队数据
    
    Args:
        data: 团队数据字典
        is_update: 是否为更新操作
    
    Returns:
        tuple: (is_valid, error_message, errors_dict)
    """
    errors = {}
    
    # 名称验证
    if 'name' in data:
        if not data['name'] or not data['name'].strip():
            errors['name'] = '团队名称不能为空'
        elif len(data['name']) > 100:
            errors['name'] = '团队名称过长'
    elif not is_update:
        errors['name'] = '团队名称不能为空'
    
    # 描述验证
    if 'description' in data and data['description']:
        if len(data['description']) > 2000:
            errors['description'] = '团队描述过长'
    
    is_valid = len(errors) == 0
    error_message = '; '.join(errors.values()) if errors else None
    
    return is_valid, error_message, errors


def validate_pagination(page, per_page, max_per_page=100):
    """
    验证分页参数
    
    Args:
        page: 页码
        per_page: 每页数量
        max_per_page: 每页最大数量
    
    Returns:
        tuple: (page, per_page, error)
    """
    try:
        page = int(page) if page else 1
    except (ValueError, TypeError):
        page = 1
    
    try:
        per_page = int(per_page) if per_page else 20
    except (ValueError, TypeError):
        per_page = 20
    
    # 限制范围
    page = max(1, page)
    per_page = max(1, min(per_page, max_per_page))
    
    return page, per_page, None

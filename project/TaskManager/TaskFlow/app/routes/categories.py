# TaskFlow 分类路由
# 处理分类的CRUD操作

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models.category import Category
from app.models.task import Task
from app.utils.decorators import ajax_login_required
from app.utils.validators import validate_category_data
from app.utils.helpers import success_response, error_response

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('/')
@login_required
def list():
    """
    分类列表页面
    """
    categories = Category.query.filter_by(
        user_id=current_user.id
    ).order_by(Category.sort_order.asc(), Category.name.asc()).all()
    
    # 统计每个分类的任务数量
    category_data = []
    for cat in categories:
        data = cat.to_dict()
        data['pending_count'] = cat.tasks.filter(
            Task.status.in_(['pending', 'in_progress'])
        ).count()
        data['completed_count'] = cat.tasks.filter_by(
            status='completed'
        ).count()
        category_data.append(data)
    
    return render_template(
        'categories/list.html',
        categories=category_data
    )


@categories_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    创建分类页面/处理
    """
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'description': request.form.get('description', '').strip(),
            'color': request.form.get('color', '#3498db').strip(),
            'icon': request.form.get('icon', 'folder').strip()
        }
        
        is_valid, error, errors = validate_category_data(data)
        if not is_valid:
            for field, message in errors.items():
                flash(message, 'danger')
            return redirect(url_for('categories.create'))
        
        # 检查名称是否重复
        existing = Category.query.filter_by(
            user_id=current_user.id,
            name=data['name']
        ).first()
        
        if existing:
            flash('分类名称已存在', 'danger')
            return redirect(url_for('categories.create'))
        
        # 获取最大排序值
        max_order = db.session.query(db.func.max(Category.sort_order)).filter_by(
            user_id=current_user.id
        ).scalar() or 0
        
        # 创建分类
        category = Category(
            name=data['name'],
            description=data['description'],
            color=data['color'],
            icon=data['icon'],
            sort_order=max_order + 1,
            user_id=current_user.id
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash('分类创建成功', 'success')
        return redirect(url_for('categories.list'))
    
    return render_template('categories/form.html', category=None)


@categories_bp.route('/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(category_id):
    """
    编辑分类页面/处理
    """
    category = Category.query.get_or_404(category_id)
    
    # 检查权限
    if category.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'description': request.form.get('description', '').strip(),
            'color': request.form.get('color', '#3498db').strip(),
            'icon': request.form.get('icon', 'folder').strip()
        }
        
        is_valid, error, errors = validate_category_data(data, is_update=True)
        if not is_valid:
            for field, message in errors.items():
                flash(message, 'danger')
            return redirect(url_for('categories.edit', category_id=category_id))
        
        # 检查名称是否重复（排除自己）
        existing = Category.query.filter(
            Category.user_id == current_user.id,
            Category.name == data['name'],
            Category.id != category_id
        ).first()
        
        if existing:
            flash('分类名称已存在', 'danger')
            return redirect(url_for('categories.edit', category_id=category_id))
        
        # 更新分类
        category.name = data['name']
        category.description = data['description']
        category.color = data['color']
        category.icon = data['icon']
        
        db.session.commit()
        
        flash('分类更新成功', 'success')
        return redirect(url_for('categories.list'))
    
    return render_template('categories/form.html', category=category)


@categories_bp.route('/<int:category_id>/delete', methods=['POST'])
@login_required
def delete(category_id):
    """
    删除分类
    """
    category = Category.query.get_or_404(category_id)
    
    # 检查权限
    if category.user_id != current_user.id:
        abort(403)
    
    # 检查是否有任务关联
    if category.tasks.count() > 0:
        flash('该分类下还有任务，无法删除', 'danger')
        return redirect(url_for('categories.list'))
    
    db.session.delete(category)
    db.session.commit()
    
    flash('分类已删除', 'success')
    return redirect(url_for('categories.list'))


# API 端点

@categories_bp.route('/api/categories', methods=['GET'])
@ajax_login_required
def api_list():
    """
    获取分类列表（API）
    """
    categories = Category.query.filter_by(
        user_id=current_user.id
    ).order_by(Category.sort_order.asc(), Category.name.asc()).all()
    
    return jsonify({
        'success': True,
        'categories': [c.to_dict() for c in categories]
    })


@categories_bp.route('/api/categories', methods=['POST'])
@ajax_login_required
def api_create():
    """
    创建分类（API）
    """
    data = request.get_json()
    
    is_valid, error, errors = validate_category_data(data)
    if not is_valid:
        return error_response(error, 'VALIDATION_ERROR', 400, errors=errors)
    
    # 检查名称是否重复
    existing = Category.query.filter_by(
        user_id=current_user.id,
        name=data['name']
    ).first()
    
    if existing:
        return error_response('分类名称已存在', 'DUPLICATE_NAME', 400)
    
    # 获取最大排序值
    max_order = db.session.query(db.func.max(Category.sort_order)).filter_by(
        user_id=current_user.id
    ).scalar() or 0
    
    category = Category(
        name=data['name'],
        description=data.get('description'),
        color=data.get('color', '#3498db'),
        icon=data.get('icon', 'folder'),
        sort_order=max_order + 1,
        user_id=current_user.id
    )
    
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '分类创建成功',
        'category': category.to_dict()
    }), 201


@categories_bp.route('/api/categories/<int:category_id>', methods=['PUT'])
@ajax_login_required
def api_update(category_id):
    """
    更新分类（API）
    """
    category = Category.query.get_or_404(category_id)
    
    if category.user_id != current_user.id:
        return error_response('权限不足', 'FORBIDDEN', 403)
    
    data = request.get_json()
    
    is_valid, error, errors = validate_category_data(data, is_update=True)
    if not is_valid:
        return error_response(error, 'VALIDATION_ERROR', 400, errors=errors)
    
    # 检查名称是否重复
    existing = Category.query.filter(
        Category.user_id == current_user.id,
        Category.name == data['name'],
        Category.id != category_id
    ).first()
    
    if existing:
        return error_response('分类名称已存在', 'DUPLICATE_NAME', 400)
    
    category.name = data['name']
    if 'description' in data:
        category.description = data['description']
    if 'color' in data:
        category.color = data['color']
    if 'icon' in data:
        category.icon = data['icon']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '分类更新成功',
        'category': category.to_dict()
    })


@categories_bp.route('/api/categories/<int:category_id>', methods=['DELETE'])
@ajax_login_required
def api_delete(category_id):
    """
    删除分类（API）
    """
    category = Category.query.get_or_404(category_id)
    
    if category.user_id != current_user.id:
        return error_response('权限不足', 'FORBIDDEN', 403)
    
    # 检查是否有任务关联
    if category.tasks.count() > 0:
        return error_response('该分类下还有任务，无法删除', 'HAS_TASKS', 400)
    
    db.session.delete(category)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '分类已删除'
    })


@categories_bp.route('/api/categories/reorder', methods=['POST'])
@ajax_login_required
def api_reorder():
    """
    分类排序（API）
    """
    data = request.get_json()
    category_ids = data.get('category_ids', [])
    
    for index, cat_id in enumerate(category_ids):
        category = Category.query.get(cat_id)
        if category and category.user_id == current_user.id:
            category.sort_order = index
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '排序已更新'
    })

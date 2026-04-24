# TaskFlow 认证路由
# 处理用户注册、登录、登出等认证功能

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.models.notification import Notification
from app.utils.validators import validate_email, validate_username, validate_password
from app.utils.helpers import flash_errors

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    用户登录页面/处理
    GET: 显示登录表单
    POST: 处理登录请求
    """
    # 如果已登录，跳转到首页
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        # 处理表单提交
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False) == 'on'
        
        if not username or not password:
            flash('用户名和密码不能为空', 'danger')
            return render_template('auth/login.html')
        
        # 查找用户
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('账户已被禁用，请联系管理员', 'danger')
                return render_template('auth/login.html')
            
            # 登录用户
            login_user(user, remember=remember)
            user.update_last_login()
            
            # 跳转目标
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.dashboard')
            
            flash(f'欢迎回来，{user.get_display_name()}！', 'success')
            return redirect(next_page)
        else:
            flash('用户名或密码错误', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    用户注册页面/处理
    GET: 显示注册表单
    POST: 处理注册请求
    """
    # 如果已登录，跳转到首页
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # 验证字段
        is_valid, error = validate_username(username)
        if not is_valid:
            flash(error, 'danger')
            return render_template('auth/register.html')
        
        is_valid, error = validate_email(email)
        if not is_valid:
            flash(error, 'danger')
            return render_template('auth/register.html')
        
        is_valid, error = validate_password(password)
        if not is_valid:
            flash(error, 'danger')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return render_template('auth/register.html')
        
        # 检查用户名和邮箱是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'danger')
            return render_template('auth/register.html')
        
        # 创建用户
        user = User(
            username=username,
            email=email,
            display_name=username
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功！请登录', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    用户登出
    """
    logout_user()
    flash('您已成功退出登录', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    用户资料页面/编辑
    """
    if request.method == 'POST':
        # 更新资料
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        
        if display_name:
            current_user.display_name = display_name
        current_user.bio = bio
        
        # 如果提交了新密码
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if new_password:
            current_password = request.form.get('current_password', '')
            
            if not current_user.check_password(current_password):
                flash('当前密码错误', 'danger')
                return render_template('auth/profile.html')
            
            if new_password != confirm_password:
                flash('两次输入的密码不一致', 'danger')
                return render_template('auth/profile.html')
            
            is_valid, error = validate_password(new_password)
            if not is_valid:
                flash(error, 'danger')
                return render_template('auth/profile.html')
            
            current_user.set_password(new_password)
        
        db.session.commit()
        flash('资料更新成功', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html')


# API 端点

@auth_bp.route('/api/check-username')
def check_username():
    """
    检查用户名是否可用（AJAX）
    """
    username = request.args.get('username', '').strip()
    
    if not username:
        return jsonify({'available': False, 'message': '请输入用户名'})
    
    is_valid, error = validate_username(username)
    if not is_valid:
        return jsonify({'available': False, 'message': error})
    
    exists = User.query.filter_by(username=username).first() is not None
    
    return jsonify({
        'available': not exists,
        'message': '用户名已存在' if exists else '用户名可用'
    })


@auth_bp.route('/api/check-email')
def check_email():
    """
    检查邮箱是否可用（AJAX）
    """
    email = request.args.get('email', '').strip()
    
    if not email:
        return jsonify({'available': False, 'message': '请输入邮箱地址'})
    
    is_valid, error = validate_email(email)
    if not is_valid:
        return jsonify({'available': False, 'message': error})
    
    exists = User.query.filter_by(email=email).first() is not None
    
    return jsonify({
        'available': not exists,
        'message': '邮箱已被注册' if exists else '邮箱可用'
    })

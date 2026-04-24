"""
TaskFlow 任务管理系统 - 主视图路由
处理前端页面的渲染
"""
from flask import Blueprint, render_template, redirect, url_for, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User

# 创建主视图蓝图
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@jwt_required()
def index():
    """首页 - 任务列表"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return render_template('index.html', current_user=user)


@main_bp.route('/login')
def login():
    """登录页面"""
    return render_template('login.html')


@main_bp.route('/register')
def register():
    """注册页面"""
    return render_template('register.html')


@main_bp.route('/logout')
def logout():
    """退出登录"""
    from TaskFlow.Auth import Auth
    # 注意：由于JWT是无状态的，logout主要是在前端清除token
    # 这里重定向到登录页
    return redirect(url_for('main.login'))


@main_bp.route('/teams')
@jwt_required()
def teams():
    """团队页面"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return render_template('teams.html', current_user=user)


@main_bp.route('/categories')
@jwt_required()
def categories():
    """分类管理页面"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return render_template('categories.html', current_user=user)


@main_bp.route('/notifications')
@jwt_required()
def notifications():
    """通知中心页面"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return render_template('notifications.html', current_user=user)

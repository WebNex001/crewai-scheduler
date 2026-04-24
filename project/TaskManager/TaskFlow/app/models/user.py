# TaskFlow 用户模型
# 定义用户数据结构和认证相关功能

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.utils.helpers import generate_avatar_url


class User(UserMixin, db.Model):
    """
    用户模型
    存储用户账户信息和认证凭据
    """
    __tablename__ = 'users'
    
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    
    # 账户信息
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # 用户信息
    display_name = db.Column(db.String(100))
    avatar_url = db.Column(db.String(255))
    bio = db.Column(db.Text)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # 状态
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    
    # 关联关系
    tasks = db.relationship('Task', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    categories = db.relationship('Category', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    team_memberships = db.relationship('TeamMember', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """
        设置密码（哈希存储）
        
        Args:
            password: 明文密码
        """
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """
        验证密码
        
        Args:
            password: 明文密码
        
        Returns:
            bool: 密码是否正确
        """
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """更新最后登录时间"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def get_display_name(self):
        """
        获取显示名称
        
        Returns:
            str: 显示名称（优先使用 display_name，否则使用 username）
        """
        return self.display_name or self.username
    
    def get_avatar_url(self):
        """
        获取头像URL
        
        Returns:
            str: 头像URL
        """
        if self.avatar_url:
            return self.avatar_url
        return generate_avatar_url(self.email)
    
    def to_dict(self):
        """
        转换为字典格式
        
        Returns:
            dict: 用户信息字典
        """
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.get_display_name(),
            'avatar_url': self.get_avatar_url(),
            'bio': self.bio,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'is_admin': self.is_admin
        }
    
    @property
    def is_authenticated(self):
        """检查用户是否已认证"""
        return True
    
    @property
    def is_anonymous(self):
        """检查用户是否匿名"""
        return False
    
    def get_id(self):
        """获取用户ID（Flask-Loginrequired）"""
        return str(self.id)

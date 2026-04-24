# TaskFlow 任务模型
# 定义任务数据结构和关联关系

from datetime import datetime, timedelta
from enum import Enum
from app import db


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    
    @classmethod
    def choices(cls):
        """返回choices格式的选项列表"""
        return [(member.value, member.name) for member in cls]
    
    @classmethod
    def get_name(cls, value):
        """根据值获取名称"""
        for member in cls:
            if member.value == value:
                return member.name
        return 'UNKNOWN'
    
    @classmethod
    def get_display_name(cls, value):
        """获取显示名称"""
        names = {
            1: '低',
            2: '中',
            3: '高',
            4: '紧急'
        }
        return names.get(value, '未知')


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    
    @classmethod
    def choices(cls):
        """返回choices格式的选项列表"""
        return [(member.value, member.name.replace('_', ' ').title()) for member in cls]
    
    @classmethod
    def get_display_name(cls, value):
        """获取显示名称"""
        names = {
            'pending': '待处理',
            'in_progress': '进行中',
            'completed': '已完成',
            'cancelled': '已取消'
        }
        return names.get(value, '未知')


class Task(db.Model):
    """
    任务模型
    存储任务的所有信息
    """
    __tablename__ = 'tasks'
    
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    
    # 任务基本信息
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # 任务属性
    priority = db.Column(db.Integer, default=TaskPriority.MEDIUM.value)
    status = db.Column(db.String(20), default=TaskStatus.PENDING.value, index=True)
    
    # 时间相关
    due_date = db.Column(db.DateTime, index=True)
    start_date = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    estimated_hours = db.Column(db.Float)  # 预估工时
    
    # 提醒设置
    reminder_enabled = db.Column(db.Boolean, default=True)
    reminder_sent = db.Column(db.Boolean, default=False)
    
    # 标签（JSON格式存储）
    tags = db.Column(db.Text)  # JSON string
    
    # 排序权重
    sort_order = db.Column(db.Integer, default=0)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 外键关联
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    
    # 关联关系
    category = db.relationship('Category', backref='tasks')
    team = db.relationship('Team', backref='tasks')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_tasks')
    comments = db.relationship('TaskComment', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Task {self.id}: {self.title[:30]}>'
    
    def to_dict(self, include_owner=True):
        """
        转换为字典格式
        
        Args:
            include_owner: 是否包含所有者信息
        
        Returns:
            dict: 任务信息字典
        """
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'priority_display': TaskPriority.get_display_name(self.priority),
            'status': self.status,
            'status_display': TaskStatus.get_display_name(self.status),
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_hours': self.estimated_hours,
            'reminder_enabled': self.reminder_enabled,
            'tags': self.get_tags(),
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'category': self.category.to_dict() if self.category else None,
            'team': {'id': self.team_id, 'name': self.team.name} if self.team else None,
            'assignee': self.assignee.to_dict() if self.assignee else None,
            'comment_count': self.comments.count()
        }
        
        if include_owner:
            data['owner'] = {
                'id': self.user_id,
                'username': self.owner.username,
                'display_name': self.owner.get_display_name()
            }
        
        return data
    
    def get_tags(self):
        """
        获取任务标签列表
        
        Returns:
            list: 标签列表
        """
        if not self.tags:
            return []
        try:
            import json
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_tags(self, tags):
        """
        设置任务标签
        
        Args:
            tags: 标签列表
        """
        import json
        self.tags = json.dumps(tags, ensure_ascii=False) if tags else None
    
    def is_overdue(self):
        """
        检查任务是否已过期
        
        Returns:
            bool: 是否已过期
        """
        if self.status == TaskStatus.COMPLETED.value:
            return False
        if not self.due_date:
            return False
        return datetime.utcnow() > self.due_date
    
    def is_due_soon(self, hours=24):
        """
        检查任务是否即将到期
        
        Args:
            hours: 未来多少小时内
        
        Returns:
            bool: 是否即将到期
        """
        if not self.due_date or self.status == TaskStatus.COMPLETED.value:
            return False
        now = datetime.utcnow()
        return now <= self.due_date <= now + timedelta(hours=hours)
    
    def mark_completed(self):
        """标记任务为完成"""
        self.status = TaskStatus.COMPLETED.value
        self.completed_at = datetime.utcnow()
    
    def mark_pending(self):
        """标记任务为待处理"""
        self.status = TaskStatus.PENDING.value
        self.completed_at = None
    
    @property
    def is_completed(self):
        """检查任务是否已完成"""
        return self.status == TaskStatus.COMPLETED.value


class TaskComment(db.Model):
    """
    任务评论模型
    存储任务的评论和备注
    """
    __tablename__ = 'task_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联
    author = db.relationship('User', backref='task_comments')
    
    def __repr__(self):
        return f'<TaskComment {self.id} on Task {self.task_id}>'
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'content': self.content,
            'task_id': self.task_id,
            'author': {
                'id': self.user_id,
                'username': self.author.username,
                'display_name': self.author.get_display_name(),
                'avatar_url': self.author.get_avatar_url()
            },
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

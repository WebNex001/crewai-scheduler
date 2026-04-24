# TaskFlow 分类模型
# 定义任务分类数据结构和关联关系

from datetime import datetime
from app import db


class Category(db.Model):
    """
    分类模型
    用于对任务进行分类管理
    """
    __tablename__ = 'categories'
    
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    
    # 分类信息
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    color = db.Column(db.String(7), default='#3498db')  # 十六进制颜色值
    icon = db.Column(db.String(50), default='folder')  # 图标名称
    
    # 排序
    sort_order = db.Column(db.Integer, default=0)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 外键
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # 关联关系（在 User 模型中已定义）
    
    def __repr__(self):
        return f'<Category {self.name}>'
    
    def to_dict(self):
        """
        转换为字典格式
        
        Returns:
            dict: 分类信息字典
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'icon': self.icon,
            'sort_order': self.sort_order,
            'task_count': self.tasks.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def task_count(self):
        """获取该分类下的任务数量"""
        return self.tasks.count()
    
    def get_completed_count(self):
        """获取已完成的任务数量"""
        from app.models.task import TaskStatus
        return self.tasks.filter_by(status=TaskStatus.COMPLETED.value).count()
    
    def get_pending_count(self):
        """获取待处理的任务数量"""
        from app.models.task import TaskStatus
        return self.tasks.filter(
            TaskStatus.COMPLETED.value.notin_([TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value])
        ).count()

# TaskFlow 通知模型
# 定义系统通知和提醒数据结构

from datetime import datetime
from enum import Enum
from app import db


class NotificationType(Enum):
    """通知类型枚举"""
    TASK_REMINDER = 'task_reminder'      # 任务提醒
    TASK_ASSIGNED = 'task_assigned'      # 任务分配
    TASK_COMPLETED = 'task_completed'    # 任务完成
    TASK_UPDATED = 'task_updated'         # 任务更新
    TEAM_INVITE = 'team_invite'          # 团队邀请
    TEAM_MEMBER_ADDED = 'team_member_added'  # 新成员加入
    SYSTEM = 'system'                    # 系统通知
    
    @classmethod
    def get_display_name(cls, value):
        names = {
            'task_reminder': '任务提醒',
            'task_assigned': '任务分配',
            'task_completed': '任务完成',
            'task_updated': '任务更新',
            'team_invite': '团队邀请',
            'team_member_added': '新成员加入',
            'system': '系统通知'
        }
        return names.get(value, '通知')


class Notification(db.Model):
    """
    通知模型
    存储用户通知和提醒信息
    """
    __tablename__ = 'notifications'
    
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    
    # 通知内容
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    notification_type = db.Column(db.String(30), nullable=False, index=True)
    
    # 相关数据（JSON格式存储）
    data = db.Column(db.Text)  # JSON string
    
    # 状态
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # 外键
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # 关联关系（在 User 模型中已定义）
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title[:30]}>'
    
    def to_dict(self):
        """
        转换为字典格式
        
        Returns:
            dict: 通知信息字典
        """
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'type': self.notification_type,
            'type_display': NotificationType.get_display_name(self.notification_type),
            'data': self.get_data(),
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_data(self):
        """
        获取通知数据
        
        Returns:
            dict: 解析后的数据字典
        """
        if not self.data:
            return {}
        try:
            import json
            return json.loads(self.data)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_data(self, data):
        """
        设置通知数据
        
        Args:
            data: 数据字典
        """
        import json
        self.data = json.dumps(data, ensure_ascii=False) if data else None
    
    def mark_as_read(self):
        """标记为已读"""
        self.is_read = True
        self.read_at = datetime.utcnow()
    
    @property
    def type_display(self):
        """获取类型显示名称"""
        return NotificationType.get_display_name(self.notification_type)

# TaskFlow 通知服务
# 处理通知创建、发送和管理

from datetime import datetime
from app import db
from app.models.notification import Notification, NotificationType
from app.models.user import User


class NotificationService:
    """
    通知服务类
    封装通知相关的业务逻辑
    """
    
    def create_notification(self, user_id, notification_type, title, content=None, data=None):
        """
        创建通知
        
        Args:
            user_id: 接收用户ID
            notification_type: 通知类型
            title: 通知标题
            content: 通知内容
            data: 附加数据（字典）
        
        Returns:
            Notification: 创建的通知对象
        """
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type.value if isinstance(notification_type, NotificationType) else notification_type,
            title=title,
            content=content
        )
        
        if data:
            notification.set_data(data)
        
        db.session.add(notification)
        db.session.commit()
        
        return notification
    
    def notify_task_reminder(self, user_id, task):
        """
        发送任务提醒通知
        
        Args:
            user_id: 用户ID
            task: 任务对象
        
        Returns:
            Notification: 创建的通知
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.TASK_REMINDER,
            title=f'任务提醒：{task.title}',
            content=f'任务 "{task.title}" 即将到期',
            data={
                'task_id': task.id,
                'due_date': task.due_date.isoformat() if task.due_date else None
            }
        )
    
    def notify_task_assigned(self, user_id, task, assigned_by):
        """
        发送任务分配通知
        
        Args:
            user_id: 被分配的用户ID
            task: 任务对象
            assigned_by: 分配人
        
        Returns:
            Notification: 创建的通知
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.TASK_ASSIGNED,
            title=f'新任务分配：{task.title}',
            content=f'{assigned_by.get_display_name()} 将任务 "{task.title}" 分配给您',
            data={
                'task_id': task.id,
                'assigned_by': assigned_by.id
            }
        )
    
    def notify_task_completed(self, user_id, task, completed_by):
        """
        发送任务完成通知
        
        Args:
            user_id: 任务所有者ID
            task: 任务对象
            completed_by: 完成人
        
        Returns:
            Notification: 创建的通知
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.TASK_COMPLETED,
            title=f'任务已完成：{task.title}',
            content=f'{completed_by.get_display_name()} 完成了任务 "{task.title}"',
            data={
                'task_id': task.id,
                'completed_by': completed_by.id
            }
        )
    
    def notify_team_invite(self, user_id, team, invited_by):
        """
        发送团队邀请通知
        
        Args:
            user_id: 被邀请用户ID
            team: 团队对象
            invited_by: 邀请人
        
        Returns:
            Notification: 创建的通知
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.TEAM_INVITE,
            title=f'团队邀请：{team.name}',
            content=f'{invited_by.get_display_name()} 邀请您加入团队 "{team.name}"',
            data={
                'team_id': team.id,
                'invite_code': team.invite_code,
                'invited_by': invited_by.id
            }
        )
    
    def notify_team_member_added(self, user_id, team, new_member):
        """
        发送新成员加入通知
        
        Args:
            user_id: 团队所有者ID
            team: 团队对象
            new_member: 新成员
        
        Returns:
            Notification: 创建的通知
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.TEAM_MEMBER_ADDED,
            title=f'新成员加入：{team.name}',
            content=f'{new_member.get_display_name()} 加入了团队 "{team.name}"',
            data={
                'team_id': team.id,
                'new_member_id': new_member.id
            }
        )
    
    def get_user_notifications(self, user_id, unread_only=False, limit=50):
        """
        获取用户通知
        
        Args:
            user_id: 用户ID
            unread_only: 仅获取未读
            limit: 数量限制
        
        Returns:
            list: 通知列表
        """
        query = Notification.query.filter_by(user_id=user_id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        return query.order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
    
    def mark_as_read(self, notification_id):
        """
        标记通知为已读
        
        Args:
            notification_id: 通知ID
        
        Returns:
            bool: 是否成功
        """
        notification = Notification.query.get(notification_id)
        if not notification:
            return False
        
        notification.mark_as_read()
        db.session.commit()
        
        return True
    
    def mark_all_as_read(self, user_id):
        """
        标记所有通知为已读
        
        Args:
            user_id: 用户ID
        
        Returns:
            int: 更新的数量
        """
        count = Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        
        db.session.commit()
        
        return count
    
    def delete_notification(self, notification_id):
        """
        删除通知
        
        Args:
            notification_id: 通知ID
        
        Returns:
            bool: 是否成功
        """
        notification = Notification.query.get(notification_id)
        if not notification:
            return False
        
        db.session.delete(notification)
        db.session.commit()
        
        return True
    
    def clean_old_notifications(self, days=30):
        """
        清理旧通知
        
        Args:
            days: 保留天数
        
        Returns:
            int: 删除的数量
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        count = Notification.query.filter(
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        ).delete()
        
        db.session.commit()
        
        return count

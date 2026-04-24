# TaskFlow 任务服务
# 处理任务相关的核心业务逻辑

from datetime import datetime, timedelta
from app import db
from app.models.task import Task, TaskComment, TaskPriority, TaskStatus
from app.models.user import User
from app.models.category import Category
from app.models.team import Team


class TaskService:
    """
    任务服务类
    封装任务相关的业务逻辑
    """
    
    def create_task(self, user_id, data):
        """
        创建任务
        
        Args:
            user_id: 用户ID
            data: 任务数据字典
        
        Returns:
            Task: 创建的任务对象
        """
        task = Task(
            title=data['title'],
            description=data.get('description'),
            priority=data.get('priority', TaskPriority.MEDIUM.value),
            status=data.get('status', TaskStatus.PENDING.value),
            due_date=data.get('due_date'),
            start_date=data.get('start_date'),
            estimated_hours=data.get('estimated_hours'),
            category_id=data.get('category_id'),
            team_id=data.get('team_id'),
            tags=data.get('tags'),
            user_id=user_id
        )
        
        db.session.add(task)
        db.session.commit()
        
        return task
    
    def update_task(self, task_id, data):
        """
        更新任务
        
        Args:
            task_id: 任务ID
            data: 更新数据字典
        
        Returns:
            Task: 更新后的任务对象
        """
        task = Task.query.get(task_id)
        if not task:
            return None
        
        # 更新字段
        allowed_fields = [
            'title', 'description', 'priority', 'status',
            'due_date', 'start_date', 'estimated_hours',
            'category_id', 'team_id', 'tags', 'reminder_enabled'
        ]
        
        for field in allowed_fields:
            if field in data:
                setattr(task, field, data[field])
        
        # 处理完成时间
        if data.get('status') == TaskStatus.COMPLETED.value:
            if not task.completed_at:
                task.completed_at = datetime.utcnow()
        else:
            task.completed_at = None
        
        db.session.commit()
        
        return task
    
    def delete_task(self, task_id):
        """
        删除任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            bool: 是否删除成功
        """
        task = Task.query.get(task_id)
        if not task:
            return False
        
        db.session.delete(task)
        db.session.commit()
        
        return True
    
    def complete_task(self, task_id):
        """
        完成任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            Task: 更新后的任务对象
        """
        task = Task.query.get(task_id)
        if not task:
            return None
        
        task.mark_completed()
        db.session.commit()
        
        return task
    
    def assign_task(self, task_id, user_id):
        """
        分配任务
        
        Args:
            task_id: 任务ID
            user_id: 被分配的用户ID
        
        Returns:
            Task: 更新后的任务对象
        """
        task = Task.query.get(task_id)
        if not task:
            return None
        
        user = User.query.get(user_id)
        if not user:
            return None
        
        task.assigned_to = user_id
        db.session.commit()
        
        return task
    
    def get_user_tasks(self, user_id, filters=None):
        """
        获取用户任务列表
        
        Args:
            user_id: 用户ID
            filters: 筛选条件字典
        
        Returns:
            list: 任务列表
        """
        query = Task.query.filter_by(user_id=user_id)
        
        if filters:
            if 'status' in filters:
                query = query.filter_by(status=filters['status'])
            if 'priority' in filters:
                query = query.filter_by(priority=filters['priority'])
            if 'category_id' in filters:
                query = query.filter_by(category_id=filters['category_id'])
            if 'team_id' in filters:
                query = query.filter_by(team_id=filters['team_id'])
            if 'due_date_from' in filters:
                query = query.filter(Task.due_date >= filters['due_date_from'])
            if 'due_date_to' in filters:
                query = query.filter(Task.due_date <= filters['due_date_to'])
        
        return query.order_by(Task.due_date.asc().nullslast(), Task.priority.desc()).all()
    
    def get_overdue_tasks(self, user_id):
        """
        获取逾期任务
        
        Args:
            user_id: 用户ID
        
        Returns:
            list: 逾期任务列表
        """
        return Task.query.filter(
            Task.user_id == user_id,
            Task.due_date < datetime.utcnow(),
            Task.status.in_(['pending', 'in_progress'])
        ).all()
    
    def get_due_soon_tasks(self, user_id, hours=24):
        """
        获取即将到期任务
        
        Args:
            user_id: 用户ID
            hours: 未来多少小时内
        
        Returns:
            list: 即将到期任务列表
        """
        now = datetime.utcnow()
        future = now + timedelta(hours=hours)
        
        return Task.query.filter(
            Task.user_id == user_id,
            Task.due_date >= now,
            Task.due_date <= future,
            Task.status.in_(['pending', 'in_progress'])
        ).order_by(Task.due_date.asc()).all()
    
    def add_comment(self, task_id, user_id, content):
        """
        添加任务评论
        
        Args:
            task_id: 任务ID
            user_id: 用户ID
            content: 评论内容
        
        Returns:
            TaskComment: 创建的评论对象
        """
        task = Task.query.get(task_id)
        if not task:
            return None
        
        comment = TaskComment(
            task_id=task_id,
            user_id=user_id,
            content=content
        )
        
        db.session.add(comment)
        db.session.commit()
        
        return comment
    
    def get_task_comments(self, task_id):
        """
        获取任务评论
        
        Args:
            task_id: 任务ID
        
        Returns:
            list: 评论列表
        """
        return TaskComment.query.filter_by(
            task_id=task_id
        ).order_by(TaskComment.created_at.desc()).all()
    
    def bulk_update_status(self, task_ids, status):
        """
        批量更新任务状态
        
        Args:
            task_ids: 任务ID列表
            status: 新状态
        
        Returns:
            int: 更新的任务数量
        """
        if not task_ids:
            return 0
        
        now = datetime.utcnow()
        
        if status == TaskStatus.COMPLETED.value:
            count = Task.query.filter(
                Task.id.in_(task_ids),
                Task.user_id == db.session.query(Task.user_id).filter(Task.id == task_ids[0]).scalar()
            ).update({
                'status': status,
                'completed_at': now
            }, synchronize_session=False)
        else:
            count = Task.query.filter(
                Task.id.in_(task_ids)
            ).update({
                'status': status,
                'completed_at': None
            }, synchronize_session=False)
        
        db.session.commit()
        
        return count

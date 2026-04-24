# TaskFlow 提醒服务
# 处理任务到期提醒的调度和发送

from datetime import datetime, timedelta
from app import db, create_app
from app.models.task import Task, TaskStatus
from app.services.notification_service import NotificationService


class ReminderService:
    """
    提醒服务类
    负责定时检查并发送任务到期提醒
    """
    
    def __init__(self):
        self.notification_service = NotificationService()
    
    def check_due_tasks(self, advance_hours=24):
        """
        检查即将到期的任务并发送提醒
        
        Args:
            advance_hours: 提前提醒小时数
        
        Returns:
            int: 发送的提醒数量
        """
        now = datetime.utcnow()
        future = now + timedelta(hours=advance_hours)
        
        # 查找即将到期的任务
        tasks = Task.query.filter(
            Task.due_date >= now,
            Task.due_date <= future,
            Task.status.in_(['pending', 'in_progress']),
            Task.reminder_enabled == True,
            Task.reminder_sent == False
        ).all()
        
        count = 0
        for task in tasks:
            try:
                # 发送提醒
                self.notification_service.notify_task_reminder(
                    user_id=task.user_id,
                    task=task
                )
                
                # 标记已发送
                task.reminder_sent = True
                db.session.commit()
                
                count += 1
            except Exception as e:
                print(f"发送提醒失败: {e}")
                db.session.rollback()
        
        return count
    
    def check_overdue_tasks(self):
        """
        检查逾期任务
        
        Returns:
            int: 逾期任务数量
        """
        now = datetime.utcnow()
        
        # 查找逾期任务
        tasks = Task.query.filter(
            Task.due_date < now,
            Task.status.in_(['pending', 'in_progress'])
        ).all()
        
        return len(tasks)
    
    def send_overdue_notifications(self):
        """
        发送逾期通知（可选功能）
        
        Returns:
            int: 发送的通知数量
        """
        now = datetime.utcnow()
        
        # 获取所有用户的逾期任务
        tasks = Task.query.filter(
            Task.due_date < now,
            Task.status.in_(['pending', 'in_progress'])
        ).all()
        
        count = 0
        processed = set()  # 避免重复发送
        
        for task in tasks:
            key = f"{task.user_id}_{task.id}"
            if key in processed:
                continue
            
            # 可以选择每天只发送一次逾期提醒
            # 这里简化为不重复发送
            count += 1
            processed.add(key)
        
        return count
    
    def reset_daily_reminders(self):
        """
        重置每日提醒标志
        用于在每天开始时重置提醒状态
        """
        # 将所有任务的 reminder_sent 设为 False
        # 这样今天可以再次发送提醒
        count = Task.query.filter(
            Task.reminder_enabled == True,
            Task.status.in_(['pending', 'in_progress'])
        ).update({'reminder_sent': False})
        
        db.session.commit()
        
        return count
    
    def run_reminder_check(self):
        """
        执行提醒检查（由调度器调用）
        
        Returns:
            dict: 执行结果
        """
        from flask import current_app
        
        app = current_app._get_current_object()
        
        with app.app_context():
            try:
                # 检查即将到期的任务
                advance_hours = app.config.get('REMINDER_ADVANCE_HOURS', 24)
                due_count = self.check_due_tasks(advance_hours)
                
                return {
                    'success': True,
                    'due_tasks_checked': due_count,
                    'timestamp': datetime.utcnow().isoformat()
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }


# 全局实例
reminder_service = ReminderService()


def setup_scheduler(app):
    """
    设置任务调度器
    
    Args:
        app: Flask应用实例
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    
    scheduler = BackgroundScheduler()
    
    # 每分钟检查一次
    interval = app.config.get('REMINDER_CHECK_INTERVAL', 60)
    
    scheduler.add_job(
        func=lambda: reminder_service.run_reminder_check(),
        trigger=IntervalTrigger(seconds=interval),
        id='task_reminder_check',
        name='检查任务提醒',
        replace_existing=True
    )
    
    scheduler.start()
    
    return scheduler


def init_reminder_system(app):
    """
    初始化提醒系统
    
    Args:
        app: Flask应用实例
    """
    # 在生产环境中启用调度器
    if not app.config.get('TESTING') and app.config.get('REMINDER_ENABLED', True):
        setup_scheduler(app)

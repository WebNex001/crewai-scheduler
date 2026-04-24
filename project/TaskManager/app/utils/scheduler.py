"""
TaskFlow 任务管理系统 - 任务调度器
处理任务到期提醒的定时任务
"""
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app import db
from app.models import Task, Notification


def check_task_reminders(app):
    """检查任务提醒
    
    检查所有需要提醒的任务，发送通知
    此函数每分钟执行一次
    """
    with app.app_context():
        now = datetime.utcnow()
        
        # 查找需要提醒的任务
        # 条件：设置了提醒、未完成、提醒时间在当前时间之前
        tasks = Task.query.filter(
            Task.is_reminder_set == True,
            Task.status.in_(['pending', 'in_progress']),
            Task.reminder_time <= now,
            Task.reminder_time >= now - timedelta(minutes=1)  # 只处理最近1分钟内的提醒
        ).all()
        
        for task in tasks:
            # 创建通知
            notification = Notification(
                user_id=task.user_id,
                type='task_reminder',
                title=f'任务提醒：{task.title}',
                content=f'任务 "{task.title}" 已到期或即将到期',
                link=f'/tasks/{task.id}'
            )
            db.session.add(notification)
            
            # 重置提醒（可选：设置为不再提醒，或者设置为下一天）
            # 这里设置为1天后再次提醒
            task.reminder_time = now + timedelta(days=1)
        
        if tasks:
            db.session.commit()
            print(f"[{datetime.now()}] 发送了 {len(tasks)} 个任务提醒")


def check_overdue_tasks(app):
    """检查逾期任务
    
    每天执行一次，检查逾期任务并发送通知
    """
    with app.app_context():
        now = datetime.utcnow()
        
        # 查找逾期任务
        overdue_tasks = Task.query.filter(
            Task.status.in_(['pending', 'in_progress']),
            Task.due_date < now
        ).all()
        
        for task in overdue_tasks:
            # 检查是否已经发送过逾期通知（通过检查通知类型和创建时间）
            existing_notification = Notification.query.filter(
                Notification.user_id == task.user_id,
                Notification.type == 'task_overdue',
                Notification.link == f'/tasks/{task.id}',
                Notification.created_at >= now - timedelta(days=1)
            ).first()
            
            if not existing_notification:
                notification = Notification(
                    user_id=task.user_id,
                    type='task_overdue',
                    title=f'任务逾期：{task.title}',
                    content=f'任务 "{task.title}" 已逾期，请尽快处理',
                    link=f'/tasks/{task.id}'
                )
                db.session.add(notification)
        
        if overdue_tasks:
            db.session.commit()
            print(f"[{datetime.now()}] 处理了 {len(overdue_tasks)} 个逾期任务")


# 调度器实例
scheduler = None


def init_scheduler(app):
    """初始化任务调度器
    
    Args:
        app: Flask 应用实例
    """
    global scheduler
    
    # 创建后台调度器
    scheduler = BackgroundScheduler()
    
    # 添加任务：每分钟检查任务提醒
    scheduler.add_job(
        func=lambda: check_task_reminders(app),
        trigger=IntervalTrigger(seconds=60),
        id='task_reminder_check',
        name='检查任务提醒',
        replace_existing=True
    )
    
    # 添加任务：每天检查逾期任务
    scheduler.add_job(
        func=lambda: check_overdue_tasks(app),
        trigger=IntervalTrigger(hours=24),
        id='overdue_task_check',
        name='检查逾期任务',
        replace_existing=True
    )
    
    # 启动调度器
    scheduler.start()
    print("任务调度器已启动")


def shutdown_scheduler():
    """关闭任务调度器"""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        print("任务调度器已关闭")

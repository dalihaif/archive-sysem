from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """初始化定时任务调度器"""
    from scheduler.jobs import backup_database, check_retention_expiry, check_borrow_overdue

    scheduler.add_job(
        func=lambda: backup_database(app),
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_backup",
        name="每日数据库备份",
        replace_existing=True,
    )

    scheduler.add_job(
        func=lambda: check_retention_expiry(app),
        trigger=CronTrigger(hour=8, minute=0),
        id="retention_check",
        name="保管期限到期检查",
        replace_existing=True,
    )

    scheduler.add_job(
        func=lambda: check_borrow_overdue(app),
        trigger=CronTrigger(hour=9, minute=0),
        id="borrow_overdue_check",
        name="借阅逾期检查",
        replace_existing=True,
    )

    scheduler.start()

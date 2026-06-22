import os
import shutil
import datetime


def backup_database(app):
    """每日数据库备份"""
    try:
        db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
        backup_dir = app.config["BACKUP_FOLDER"]
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"archive_{date_str}.db")

        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)

            # 保留最近30天的备份
            backups = sorted(
                [f for f in os.listdir(backup_dir) if f.endswith(".db")],
                key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)),
                reverse=True,
            )
            for old in backups[30:]:
                os.remove(os.path.join(backup_dir, old))

        print(f"[备份] {date_str} 数据库备份完成 -> {backup_path}")
    except Exception as e:
        print(f"[备份] 失败: {e}")


def check_retention_expiry(app):
    """检查保管期限到期"""
    try:
        from app.models import Archive
        from app.extensions import db

        today = datetime.date.today()

        # 10年到期的（短期 = 10年）
        target_year_10 = today.year - 10
        short_archives = Archive.query.filter(
            Archive.retention_period.in_(["短期", "10年"]),
            Archive.archive_year <= target_year_10,
        ).count()

        # 30年到期的（长期 = "长期" or "30年"）
        target_year_30 = today.year - 30
        long_archives = Archive.query.filter(
            Archive.retention_period.in_(["长期", "30年"]),
            Archive.archive_year <= target_year_30,
        ).count()

        if short_archives or long_archives:
            print(f"[到期提醒] 短期到期: {short_archives} 件, 长期到期: {long_archives} 件")
    except Exception as e:
        print(f"[到期提醒] 失败: {e}")


def check_borrow_overdue(app):
    """检查借阅逾期"""
    try:
        from app.models import Borrow
        from app.extensions import db

        today = datetime.date.today()
        one_month_ago = today - datetime.timedelta(days=30)
        overdue = Borrow.query.filter(
            Borrow.status == "已通过",
            Borrow.approve_time <= one_month_ago,
        ).count()

        if overdue:
            print(f"[逾期提醒] 借阅逾期: {overdue} 件")
    except Exception as e:
        print(f"[逾期提醒] 失败: {e}")

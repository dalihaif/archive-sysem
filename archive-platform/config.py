import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dali-archives-2026-secret-key-change-in-prod"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'archive.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "data", "imports")
    ELECTRONIC_FOLDER = os.path.join(BASE_DIR, "data", "electronic")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

    # 备份
    BACKUP_FOLDER = os.path.join(BASE_DIR, "data", "backups")

    # 分页
    ARCHIVES_PER_PAGE = 50
    SEARCH_PER_PAGE = 20

    # APScheduler
    SCHEDULER_API_ENABLED = True

    # 借阅审批
    BORROW_APPROVE_EXPIRE_DAYS = 30  # 审批通过后30天内可查看电子版

    # 保管期限到期预警（年）
    RETENTION_WARN_10_YEARS = True
    RETENTION_WARN_30_YEARS = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

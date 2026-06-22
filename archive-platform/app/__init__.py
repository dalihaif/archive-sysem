import os
from flask import Flask
from config import config
from app.extensions import db, login_manager, migrate, bcrypt


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)

    # 确保必要目录存在
    for folder in [app.config["UPLOAD_FOLDER"], app.config["ELECTRONIC_FOLDER"], app.config["BACKUP_FOLDER"]]:
        os.makedirs(folder, exist_ok=True)

    # 注册蓝图
    from app.auth.routes import auth_bp
    from app.catalog.routes import catalog_bp
    from app.search.routes import search_bp
    from app.transfer.routes import transfer_bp
    from app.borrow.routes import borrow_bp
    from app.destroy.routes import destroy_bp
    from app.stats.routes import stats_bp
    from app.regulations.routes import reg_bp
    from app.import_data.routes import import_bp
    from app.admin.routes import admin_bp
    from app.mobile.routes import mobile_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(catalog_bp, url_prefix="/catalog")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(transfer_bp, url_prefix="/transfer")
    app.register_blueprint(borrow_bp, url_prefix="/borrow")
    app.register_blueprint(destroy_bp, url_prefix="/destroy")
    app.register_blueprint(stats_bp, url_prefix="/stats")
    app.register_blueprint(reg_bp, url_prefix="/regulations")
    app.register_blueprint(import_bp, url_prefix="/import")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(mobile_bp, url_prefix="/m")

    # 首页重定向
    from flask import redirect, url_for

    @app.route("/")
    def index():
        return redirect(url_for("stats.dashboard"))

    # 上下文处理器：注入用户信息
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        return dict(current_user=current_user)

    return app

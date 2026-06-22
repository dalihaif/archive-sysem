from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.models import User, OperationLog
from app.extensions import db
import datetime


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("stats.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username, active=True).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get("remember"))
            user.last_login = datetime.datetime.utcnow()
            db.session.commit()
            log_action(user.id, "login", "user", user.id, f"用户 {username} 登录")
            flash(f"欢迎回来，{user.real_name or user.username}！", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("stats.dashboard"))
        else:
            flash("用户名或密码错误", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    username = current_user.username
    log_action(current_user.id, "logout", "user", current_user.id, f"用户 {username} 登出")
    logout_user()
    flash("已安全退出", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")


def log_action(user_id, action, target_type, target_id, detail=""):
    try:
        log = OperationLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass

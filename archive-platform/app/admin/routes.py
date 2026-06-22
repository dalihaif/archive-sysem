import os
import shutil
import datetime
from flask import render_template, request, jsonify, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app.admin import admin_bp
from app.models import User, Archive, Borrow, Transfer, OperationLog
from app.extensions import db


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            return jsonify({"ok": False, "msg": "需要管理员权限"}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@login_required
def index():
    if not current_user.is_admin():
        flash("无权限访问系统管理", "danger")
        return redirect(url_for("stats.dashboard"))
    user_count = User.query.count()
    archive_count = Archive.query.count()
    log_count = OperationLog.query.count()
    borrow_pending = Borrow.query.filter_by(status="待审批").count()
    return render_template(
        "admin/index.html",
        user_count=user_count,
        archive_count=archive_count,
        log_count=log_count,
        borrow_pending=borrow_pending,
    )


# ─── 用户管理 API ───────────────────────────
@admin_bp.route("/api/users")
@login_required
@require_admin
def api_users():
    draw   = request.args.get("draw", 1, type=int)
    start  = request.args.get("start", 0, type=int)
    length = request.args.get("length", 20, type=int)
    search = request.args.get("search[value]", "").strip()

    q = User.query
    if search:
        q = q.filter(or_(
            User.username.contains(search),
            User.real_name.contains(search),
            User.department.contains(search),
        ))

    total = q.count()
    rows = q.order_by(User.id.asc()).offset(start).limit(length).all()

    role_badge = {
        "admin": '<span class="badge bg-danger">管理员</span>',
        "editor": '<span class="badge bg-primary">编辑者</span>',
        "viewer": '<span class="badge bg-secondary">浏览者</span>',
    }
    data = []
    for u in rows:
        data.append({
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name or "",
            "department": u.department or "",
            "phone": u.phone or "",
            "email": u.email or "",
            "role": role_badge.get(u.role, u.role),
            "role_raw": u.role,
            "active": u.active,
            "active_badge": '<span class="badge bg-success">启用</span>' if u.active else '<span class="badge bg-secondary">禁用</span>',
            "last_login": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "从未登录",
            "created_at": u.created_at.strftime("%Y-%m-%d") if u.created_at else "",
        })

    return jsonify({"draw": draw, "recordsTotal": total, "recordsFiltered": total, "data": data})


@admin_bp.route("/api/users/create", methods=["POST"])
@login_required
@require_admin
def api_create_user():
    data = request.json or {}
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"ok": False, "msg": "用户名不能为空"})
    if User.query.filter_by(username=username).first():
        return jsonify({"ok": False, "msg": "用户名已存在"})

    u = User(
        username=username,
        real_name=data.get("real_name", "").strip(),
        department=data.get("department", "").strip(),
        phone=data.get("phone", "").strip(),
        email=data.get("email", "").strip(),
        role=data.get("role", "viewer"),
        active=True,
    )
    u.set_password(data.get("password", "changeme123"))
    db.session.add(u)
    db.session.flush()
    db.session.add(OperationLog(
        user_id=current_user.id,
        action="create",
        target_type="user",
        target_id=u.id,
        detail=f"创建用户 {username}（{u.role}）",
        ip_address=request.remote_addr,
    ))
    db.session.commit()
    return jsonify({"ok": True, "id": u.id})


@admin_bp.route("/api/users/<int:uid>")
@login_required
@require_admin
def api_get_user(uid):
    u = User.query.get_or_404(uid)
    return jsonify({
        "id": u.id, "username": u.username, "real_name": u.real_name or "",
        "department": u.department or "", "phone": u.phone or "",
        "email": u.email or "", "role": u.role, "active": u.active,
    })


@admin_bp.route("/api/users/<int:uid>/update", methods=["POST"])
@login_required
@require_admin
def api_update_user(uid):
    u = User.query.get_or_404(uid)
    data = request.json or {}
    u.real_name = data.get("real_name", u.real_name or "")
    u.department = data.get("department", u.department or "")
    u.phone = data.get("phone", u.phone or "")
    u.email = data.get("email", u.email or "")
    u.role = data.get("role", u.role)
    u.active = data.get("active", u.active)
    if data.get("password"):
        u.set_password(data["password"])
    db.session.add(OperationLog(
        user_id=current_user.id, action="update", target_type="user",
        target_id=uid, detail=f"更新用户 {u.username}", ip_address=request.remote_addr,
    ))
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.route("/api/users/<int:uid>/delete", methods=["POST"])
@login_required
@require_admin
def api_delete_user(uid):
    if uid == current_user.id:
        return jsonify({"ok": False, "msg": "不能删除自己"})
    u = User.query.get_or_404(uid)
    db.session.add(OperationLog(
        user_id=current_user.id, action="delete", target_type="user",
        target_id=uid, detail=f"删除用户 {u.username}", ip_address=request.remote_addr,
    ))
    db.session.delete(u)
    db.session.commit()
    return jsonify({"ok": True})


# ─── 操作日志 API ───────────────────────────
@admin_bp.route("/api/logs")
@login_required
@require_admin
def api_logs():
    draw   = request.args.get("draw", 1, type=int)
    start  = request.args.get("start", 0, type=int)
    length = request.args.get("length", 30, type=int)
    search = request.args.get("search[value]", "").strip()

    q = OperationLog.query
    if search:
        q = q.filter(or_(
            OperationLog.action.contains(search),
            OperationLog.detail.contains(search),
        ))

    total = q.count()
    rows = q.order_by(OperationLog.timestamp.desc()).offset(start).limit(length).all()

    action_badge = {
        "create":   '<span class="badge bg-success">新建</span>',
        "update":   '<span class="badge bg-warning text-dark">更新</span>',
        "delete":   '<span class="badge bg-danger">删除</span>',
        "import":   '<span class="badge bg-info">导入</span>',
        "export":   '<span class="badge bg-info text-dark">导出</span>',
        "login":    '<span class="badge bg-secondary">登录</span>',
        "borrow":   '<span class="badge bg-primary">借阅</span>',
        "transfer": '<span class="badge bg-primary">移交</span>',
        "backup":   '<span class="badge bg-dark">备份</span>',
        "restore":  '<span class="badge bg-warning text-dark">恢复</span>',
    }
    data = []
    for log in rows:
        data.append({
            "id": log.id,
            "action": action_badge.get(log.action, f'<span class="badge bg-secondary">{log.action}</span>'),
            "target_type": log.target_type or "",
            "target_id": log.target_id or "",
            "user": log.user.username if log.user else "—",
            "detail": (log.detail or "")[:80],
            "ip_address": log.ip_address or "",
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "",
        })

    return jsonify({"draw": draw, "recordsTotal": total, "recordsFiltered": total, "data": data})


# ─── 数据备份 API ────────────────────────────────────────────────────────────

def _get_backup_dir():
    """获取备份目录，不存在则创建"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    backup_dir = os.path.join(base_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def _get_db_path():
    """获取当前数据库文件路径"""
    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    # sqlite:///path/to/db.sqlite3
    if db_uri.startswith("sqlite:///"):
        rel_path = db_uri[len("sqlite:///"):]
        if os.path.isabs(rel_path):
            return rel_path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, rel_path)
    return None


@admin_bp.route("/api/backup/list")
@login_required
@require_admin
def api_backup_list():
    """列出所有备份文件"""
    backup_dir = _get_backup_dir()
    backups = []
    try:
        for fname in sorted(os.listdir(backup_dir), reverse=True):
            if not fname.endswith(".sqlite3") and not fname.endswith(".db"):
                continue
            fpath = os.path.join(backup_dir, fname)
            stat = os.stat(fpath)
            backups.append({
                "filename": fname,
                "size": stat.st_size,
                "size_str": _human_size(stat.st_size),
                "created_at": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "ts": stat.st_mtime,
            })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

    return jsonify({"ok": True, "backups": backups})


@admin_bp.route("/api/backup/create", methods=["POST"])
@login_required
@require_admin
def api_backup_create():
    """创建数据库备份"""
    db_path = _get_db_path()
    if not db_path or not os.path.exists(db_path):
        return jsonify({"ok": False, "msg": "找不到数据库文件"})

    backup_dir = _get_backup_dir()
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    db_ext = os.path.splitext(db_path)[1] or ".sqlite3"
    backup_filename = f"archive_backup_{now_str}{db_ext}"
    backup_path = os.path.join(backup_dir, backup_filename)

    try:
        shutil.copy2(db_path, backup_path)
        size = os.path.getsize(backup_path)

        db.session.add(OperationLog(
            user_id=current_user.id,
            action="backup",
            target_type="database",
            target_id=0,
            detail=f"手动备份数据库：{backup_filename}（{_human_size(size)}）",
            ip_address=request.remote_addr,
        ))
        db.session.commit()

        return jsonify({
            "ok": True,
            "filename": backup_filename,
            "size_str": _human_size(size),
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@admin_bp.route("/api/backup/download/<filename>")
@login_required
@require_admin
def api_backup_download(filename):
    """下载备份文件"""
    # 安全检查：只允许字母数字下划线点连字符
    import re
    if not re.match(r'^[\w\-.]+$', filename):
        return jsonify({"error": "非法文件名"}), 400

    backup_dir = _get_backup_dir()
    file_path = os.path.join(backup_dir, filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "文件不存在"}), 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype="application/octet-stream",
    )


@admin_bp.route("/api/backup/delete/<filename>", methods=["POST"])
@login_required
@require_admin
def api_backup_delete(filename):
    """删除备份文件"""
    import re
    if not re.match(r'^[\w\-.]+$', filename):
        return jsonify({"ok": False, "msg": "非法文件名"}), 400

    backup_dir = _get_backup_dir()
    file_path = os.path.join(backup_dir, filename)

    if not os.path.exists(file_path):
        return jsonify({"ok": False, "msg": "文件不存在"})

    try:
        os.remove(file_path)
        db.session.add(OperationLog(
            user_id=current_user.id,
            action="delete",
            target_type="backup",
            target_id=0,
            detail=f"删除备份文件：{filename}",
            ip_address=request.remote_addr,
        ))
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@admin_bp.route("/api/backup/restore/<filename>", methods=["POST"])
@login_required
@require_admin
def api_backup_restore(filename):
    """从备份文件恢复数据库。
    执行步骤：
    1. 安全校验文件名
    2. 自动备份当前数据库（防止误操作）
    3. 关闭所有 SQLAlchemy 连接
    4. 复制备份文件覆盖当前数据库
    5. 重新连接数据库
    6. 写入操作日志（写到恢复后的DB）
    """
    import re
    if not re.match(r'^[\w\-.]+$', filename):
        return jsonify({"ok": False, "msg": "非法文件名"}), 400

    backup_dir = _get_backup_dir()
    restore_src = os.path.join(backup_dir, filename)

    if not os.path.exists(restore_src):
        return jsonify({"ok": False, "msg": "备份文件不存在"})

    db_path = _get_db_path()
    if not db_path:
        return jsonify({"ok": False, "msg": "无法定位当前数据库文件"})

    # 记录操作人信息，恢复后 Session 可能失效，提前取出
    operator_id = current_user.id
    operator_name = current_user.username
    remote_ip = request.remote_addr

    try:
        # 步骤1：自动备份当前数据库
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        db_ext = os.path.splitext(db_path)[1] or ".sqlite3"
        pre_backup_name = f"archive_pre_restore_{now_str}{db_ext}"
        pre_backup_path = os.path.join(backup_dir, pre_backup_name)

        if os.path.exists(db_path):
            shutil.copy2(db_path, pre_backup_path)

        # 步骤2：关闭所有数据库连接（释放文件锁）
        db.session.remove()
        db.engine.dispose()

        # 步骤3：复制备份文件覆盖当前数据库
        shutil.copy2(restore_src, db_path)

        # 步骤4：重新建立连接，写操作日志
        try:
            with current_app.app_context():
                db.session.add(OperationLog(
                    user_id=operator_id,
                    action="restore",
                    target_type="database",
                    target_id=0,
                    detail=(
                        f"从备份恢复数据库：{filename}；"
                        f"操作人：{operator_name}；"
                        f"恢复前自动备份：{pre_backup_name}"
                    ),
                    ip_address=remote_ip,
                ))
                db.session.commit()
        except Exception:
            # 日志写入失败不影响恢复成功的结果
            pass

        return jsonify({
            "ok": True,
            "msg": "数据库已成功恢复",
            "pre_backup": pre_backup_name,
        })

    except Exception as e:
        return jsonify({"ok": False, "msg": f"恢复失败：{str(e)}"})


@admin_bp.route("/api/backup/info")
@login_required
@require_admin
def api_backup_info():
    """获取数据库信息（大小、记录数等）"""
    db_path = _get_db_path()
    info = {
        "db_path": db_path or "未知",
        "db_exists": False,
        "db_size": 0,
        "db_size_str": "—",
        "archive_count": 0,
        "backup_count": 0,
        "backup_dir": _get_backup_dir(),
    }
    if db_path and os.path.exists(db_path):
        info["db_exists"] = True
        info["db_size"] = os.path.getsize(db_path)
        info["db_size_str"] = _human_size(info["db_size"])

    try:
        info["archive_count"] = Archive.query.count()
        backup_dir = _get_backup_dir()
        info["backup_count"] = len([
            f for f in os.listdir(backup_dir)
            if f.endswith(".sqlite3") or f.endswith(".db")
        ])
    except Exception:
        pass

    return jsonify(info)


def _human_size(size_bytes):
    """人性化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

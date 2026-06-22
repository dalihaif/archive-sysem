from flask import render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta
from app.stats import stats_bp
from app.models import Archive, Transfer, Borrow, Regulation, OperationLog
from app.extensions import db


@stats_bp.route("/")
@login_required
def dashboard():
    """工作台仪表盘"""
    return render_template("stats/dashboard.html")


@stats_bp.route("/api/dashboard")
@login_required
def api_dashboard():
    """仪表盘统计数据 API（供 dashboard.html 使用）"""
    # 总数统计
    total_archives = Archive.query.count()
    total_transfers = Transfer.query.count()
    active_borrows = Borrow.query.filter(Borrow.status == "已通过").count()
    total_regulations = Regulation.query.count()

    # 按类别分布
    by_category_raw = db.session.query(
        Archive.category, func.count(Archive.id)
    ).group_by(Archive.category).all()
    by_category = {cat: cnt for cat, cnt in by_category_raw}

    # 按保管期限分布
    by_retention_raw = db.session.query(
        Archive.retention_period, func.count(Archive.id)
    ).filter(Archive.retention_period.isnot(None), Archive.retention_period != ""
    ).group_by(Archive.retention_period).all()
    by_retention = {period: cnt for period, cnt in by_retention_raw}

    # 有电子版 / 已上链
    with_electronic = Archive.query.filter(Archive.electronic_path.isnot(None), Archive.electronic_path != "").count()
    with_blockchain = Archive.query.filter(Archive.bc_hash.isnot(None), Archive.bc_hash != "").count()

    # 最近操作记录
    recent_ops = OperationLog.query.order_by(OperationLog.timestamp.desc()).limit(10).all()
    ops_data = []
    op_icons = {
        "create": ("plus-circle", "success"),
        "update": ("pencil", "warning"),
        "delete": ("trash", "danger"),
        "import": ("upload", "info"),
        "login": ("box-arrow-in-right", "secondary"),
        "borrow": ("book", "primary"),
        "transfer": ("send", "info"),
        "default": ("circle", "secondary"),
    }
    for op in recent_ops:
        icon, color = op_icons.get(op.action, op_icons["default"])
        time_str = ""
        if op.timestamp:
            diff = datetime.now() - op.timestamp
            if diff.days > 0:
                time_str = f"{diff.days}天前"
            elif diff.seconds >= 3600:
                time_str = f"{diff.seconds // 3600}小时前"
            elif diff.seconds >= 60:
                time_str = f"{diff.seconds // 60}分钟前"
            else:
                time_str = "刚刚"
        ops_data.append({
            "detail": op.detail[:60] if op.detail else op.action,
            "time": time_str,
            "icon": icon,
            "color": color,
        })

    return jsonify({
        "total": total_archives,
        "transfers": total_transfers,
        "active_borrows": active_borrows,
        "regulations": total_regulations,
        "by_category": by_category,
        "by_retention": by_retention,
        "with_electronic": with_electronic,
        "with_blockchain": with_blockchain,
        "recent_ops": ops_data,
    })

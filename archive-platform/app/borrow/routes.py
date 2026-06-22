import secrets
import datetime
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.borrow import borrow_bp
from app.models import Borrow, Archive, OperationLog
from app.extensions import db


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def _log(action, target_id, detail):
    db.session.add(OperationLog(
        user_id=current_user.id,
        action=action,
        target_type="borrow",
        target_id=target_id,
        detail=detail,
        ip_address=request.remote_addr,
    ))


# ─────────────────────────────────────────────
# 借阅管理主页
# ─────────────────────────────────────────────
@borrow_bp.route("/")
@login_required
def list():
    pending_count = Borrow.query.filter_by(status="待审批").count()
    overdue_count = Borrow.query.filter(
        Borrow.status == "已通过",
        Borrow.return_date < datetime.date.today()
    ).count()
    return render_template(
        "borrow/list.html",
        pending_count=pending_count,
        overdue_count=overdue_count,
    )


# ─────────────────────────────────────────────
# API: 借阅列表（DataTables 服务端分页）
# ─────────────────────────────────────────────
@borrow_bp.route("/api/list")
@login_required
def api_list():
    draw   = request.args.get("draw", 1, type=int)
    start  = request.args.get("start", 0, type=int)
    length = request.args.get("length", 20, type=int)
    search = request.args.get("search[value]", "").strip()
    status = request.args.get("status", "")

    q = Borrow.query

    if status:
        q = q.filter(Borrow.status == status)
    if search:
        q = q.filter(or_(
            Borrow.borrower.contains(search),
            Borrow.borrower_department.contains(search),
            Borrow.archive_ref.contains(search),
        ))

    total = q.count()
    rows  = q.order_by(Borrow.created_at.desc()).offset(start).limit(length).all()

    data = []
    today = datetime.date.today()
    for b in rows:
        is_overdue = (b.status == "已通过" and b.return_date and b.return_date < today)
        status_badge = {
            "待审批": '<span class="badge bg-warning text-dark">待审批</span>',
            "已通过": '<span class="badge bg-success">已通过</span>' if not is_overdue else '<span class="badge bg-danger">已逾期</span>',
            "已拒绝": '<span class="badge bg-secondary">已拒绝</span>',
            "已归还": '<span class="badge bg-info">已归还</span>',
        }.get(b.status, b.status)

        data.append({
            "id": b.id,
            "borrower": b.borrower or "",
            "borrower_department": b.borrower_department or "",
            "archive_ref": (b.archive_ref or "")[:40],
            "purpose": (b.purpose or "")[:30],
            "borrow_date": b.borrow_date.strftime("%Y-%m-%d") if b.borrow_date else "",
            "return_date": b.return_date.strftime("%Y-%m-%d") if b.return_date else "",
            "status": status_badge,
            "status_raw": b.status,
            "created_at": b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "",
        })

    return jsonify({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": data,
    })


# ─────────────────────────────────────────────
# API: 借阅详情
# ─────────────────────────────────────────────
@borrow_bp.route("/api/<int:bid>")
@login_required
def api_detail(bid):
    b = Borrow.query.get_or_404(bid)
    archive = None
    if b.archive_id:
        a = Archive.query.get(b.archive_id)
        if a:
            archive = {"title": a.title, "archive_number": a.archive_number, "category": a.category}
    return jsonify({
        "id": b.id,
        "borrower": b.borrower,
        "borrower_department": b.borrower_department or "",
        "borrower_phone": b.borrower_phone or "",
        "archive_ref": b.archive_ref or "",
        "purpose": b.purpose or "",
        "borrow_date": b.borrow_date.strftime("%Y-%m-%d") if b.borrow_date else "",
        "return_date": b.return_date.strftime("%Y-%m-%d") if b.return_date else "",
        "status": b.status,
        "approve_comment": b.approve_comment or "",
        "approve_time": b.approve_time.strftime("%Y-%m-%d %H:%M") if b.approve_time else "",
        "approver": b.approver.real_name or b.approver.username if b.approver else "",
        "access_code": b.access_code or "",
        "archive": archive,
        "can_view_electronic": b.can_view_electronic(),
        "created_at": b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "",
    })


# ─────────────────────────────────────────────
# API: 审批（通过/拒绝）
# ─────────────────────────────────────────────
@borrow_bp.route("/api/<int:bid>/approve", methods=["POST"])
@login_required
def api_approve(bid):
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403

    b = Borrow.query.get_or_404(bid)
    if b.status != "待审批":
        return jsonify({"ok": False, "msg": "该申请已审批"})

    action = request.json.get("action")   # "approve" | "reject"
    comment = request.json.get("comment", "")

    if action == "approve":
        b.status = "已通过"
        b.access_code = secrets.token_hex(3).upper()   # 6 位验证码
        detail = f"审批通过借阅申请#{bid}（{b.borrower}）"
    elif action == "reject":
        b.status = "已拒绝"
        detail = f"拒绝借阅申请#{bid}（{b.borrower}）"
    else:
        return jsonify({"ok": False, "msg": "非法操作"})

    b.approve_comment = comment
    b.approver_id = current_user.id
    b.approve_time = datetime.datetime.utcnow()
    _log("borrow", bid, detail)
    db.session.commit()
    return jsonify({"ok": True, "access_code": b.access_code or ""})


# ─────────────────────────────────────────────
# API: 归还登记
# ─────────────────────────────────────────────
@borrow_bp.route("/api/<int:bid>/return", methods=["POST"])
@login_required
def api_return(bid):
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403

    b = Borrow.query.get_or_404(bid)
    if b.status not in ("已通过",):
        return jsonify({"ok": False, "msg": "当前状态不可归还"})

    b.status = "已归还"
    b.return_date = datetime.date.today()
    _log("borrow", bid, f"确认归还借阅#{bid}（{b.borrower}）")
    db.session.commit()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# API: 新建借阅申请（PC端管理员代录）
# ─────────────────────────────────────────────
@borrow_bp.route("/api/create", methods=["POST"])
@login_required
def api_create():
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403

    data = request.json or {}
    b = Borrow(
        borrower=data.get("borrower", "").strip(),
        borrower_department=data.get("borrower_department", "").strip(),
        borrower_phone=data.get("borrower_phone", "").strip(),
        archive_ref=data.get("archive_ref", "").strip(),
        purpose=data.get("purpose", "").strip(),
        borrow_date=datetime.date.today(),
        status="待审批",
    )
    if not b.borrower:
        return jsonify({"ok": False, "msg": "借阅人不能为空"})

    db.session.add(b)
    db.session.flush()
    _log("borrow", b.id, f"录入借阅申请（{b.borrower}）")
    db.session.commit()
    return jsonify({"ok": True, "id": b.id})


# ─────────────────────────────────────────────
# API: 删除
# ─────────────────────────────────────────────
@borrow_bp.route("/api/<int:bid>/delete", methods=["POST"])
@login_required
def api_delete(bid):
    if not current_user.is_admin():
        return jsonify({"ok": False, "msg": "需要管理员权限"}), 403
    b = Borrow.query.get_or_404(bid)
    _log("delete", bid, f"删除借阅记录#{bid}（{b.borrower}）")
    db.session.delete(b)
    db.session.commit()
    return jsonify({"ok": True})

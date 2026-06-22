import datetime
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.transfer import transfer_bp
from app.models import Transfer, Archive, OperationLog
from app.extensions import db

CATEGORIES = ["文书", "基建", "科研", "设备", "会计"]


def _log(action, target_id, detail):
    db.session.add(OperationLog(
        user_id=current_user.id,
        action=action,
        target_type="transfer",
        target_id=target_id,
        detail=detail,
        ip_address=request.remote_addr,
    ))


@transfer_bp.route("/")
@login_required
def list():
    total = Transfer.query.count()
    this_year = Transfer.query.filter(
        Transfer.transfer_date >= datetime.date(datetime.date.today().year, 1, 1)
    ).count()
    return render_template("transfer/list.html", total=total, this_year=this_year)


# ─── API: 列表 ───────────────────────────────
@transfer_bp.route("/api/list")
@login_required
def api_list():
    draw   = request.args.get("draw", 1, type=int)
    start  = request.args.get("start", 0, type=int)
    length = request.args.get("length", 20, type=int)
    search = request.args.get("search[value]", "").strip()
    category = request.args.get("category", "")
    year = request.args.get("year", "", type=str)

    q = Transfer.query
    if search:
        q = q.filter(or_(
            Transfer.from_department.contains(search),
            Transfer.from_person.contains(search),
            Transfer.to_person.contains(search),
            Transfer.transfer_type.contains(search),
        ))
    if category:
        q = q.filter(Transfer.transfer_type.contains(category))
    if year:
        try:
            y = int(year)
            q = q.filter(
                Transfer.transfer_date >= datetime.date(y, 1, 1),
                Transfer.transfer_date <= datetime.date(y, 12, 31),
            )
        except ValueError:
            pass

    total = q.count()
    rows = q.order_by(Transfer.transfer_date.desc(), Transfer.id.desc()).offset(start).limit(length).all()

    status_map = {
        "已完成": '<span class="badge bg-success">已完成</span>',
        "进行中": '<span class="badge bg-warning text-dark">进行中</span>',
        "待接收": '<span class="badge bg-info">待接收</span>',
    }
    data = []
    for t in rows:
        data.append({
            "id": t.id,
            "transfer_date": t.transfer_date.strftime("%Y-%m-%d") if t.transfer_date else "",
            "from_department": t.from_department or "",
            "from_person": t.from_person or "",
            "to_department": t.to_department or "",
            "to_person": t.to_person or "",
            "transfer_type": t.transfer_type or "",
            "quantity": t.quantity or 0,
            "start_number": t.start_number or "",
            "status": status_map.get(t.status, t.status or ""),
            "status_raw": t.status or "",
            "remarks": (t.remarks or "")[:30],
        })

    return jsonify({"draw": draw, "recordsTotal": total, "recordsFiltered": total, "data": data})


# ─── API: 详情 ───────────────────────────────
@transfer_bp.route("/api/<int:tid>")
@login_required
def api_detail(tid):
    t = Transfer.query.get_or_404(tid)
    return jsonify({
        "id": t.id,
        "transfer_date": t.transfer_date.strftime("%Y-%m-%d") if t.transfer_date else "",
        "from_department": t.from_department or "",
        "from_person": t.from_person or "",
        "to_department": t.to_department or "",
        "to_person": t.to_person or "",
        "transfer_type": t.transfer_type or "",
        "quantity": t.quantity or 0,
        "start_number": t.start_number or "",
        "status": t.status or "",
        "remarks": t.remarks or "",
        "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
    })


# ─── API: 新建 ───────────────────────────────
@transfer_bp.route("/api/create", methods=["POST"])
@login_required
def api_create():
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403

    data = request.json or {}
    date_str = data.get("transfer_date", "")
    try:
        tdate = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    except ValueError:
        tdate = datetime.date.today()

    t = Transfer(
        transfer_date=tdate,
        from_department=data.get("from_department", "").strip(),
        from_person=data.get("from_person", "").strip(),
        to_department=data.get("to_department", "").strip(),
        to_person=data.get("to_person", "").strip(),
        transfer_type=data.get("transfer_type", "").strip(),
        quantity=int(data.get("quantity", 0) or 0),
        start_number=data.get("start_number", "").strip(),
        status=data.get("status", "待接收"),
        remarks=data.get("remarks", "").strip(),
    )
    if not t.from_department:
        return jsonify({"ok": False, "msg": "移交部门不能为空"})

    db.session.add(t)
    db.session.flush()
    _log("transfer", t.id, f"新建移交记录#{t.id}（{t.from_department} → {t.to_department}）")
    db.session.commit()
    return jsonify({"ok": True, "id": t.id})


# ─── API: 更新状态 ───────────────────────────
@transfer_bp.route("/api/<int:tid>/status", methods=["POST"])
@login_required
def api_update_status(tid):
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403
    t = Transfer.query.get_or_404(tid)
    new_status = request.json.get("status", "")
    if new_status not in ("待接收", "进行中", "已完成"):
        return jsonify({"ok": False, "msg": "非法状态值"})
    t.status = new_status
    _log("update", tid, f"更新移交状态#{tid} → {new_status}")
    db.session.commit()
    return jsonify({"ok": True})


# ─── API: 删除 ───────────────────────────────
@transfer_bp.route("/api/<int:tid>/delete", methods=["POST"])
@login_required
def api_delete(tid):
    if not current_user.is_admin():
        return jsonify({"ok": False, "msg": "需要管理员权限"}), 403
    t = Transfer.query.get_or_404(tid)
    _log("delete", tid, f"删除移交记录#{tid}")
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})

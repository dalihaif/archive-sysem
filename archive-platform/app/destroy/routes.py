import datetime
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app.destroy import destroy_bp
from app.models import Destruction, Archive, OperationLog
from app.extensions import db

# 保管期限 → 年限对照
RETENTION_YEARS = {
    "永久": None,
    "30年": 30,
    "10年": 10,
}


def _log(action, target_id, detail):
    db.session.add(OperationLog(
        user_id=current_user.id,
        action=action,
        target_type="destruction",
        target_id=target_id,
        detail=detail,
        ip_address=request.remote_addr,
    ))


@destroy_bp.route("/")
@login_required
def list():
    """销毁鉴定主页"""
    today = datetime.date.today()
    # 计算各保管期限下到期档案数量
    overdue_10 = Archive.query.filter(
        Archive.retention_period == "10年",
        Archive.archive_year <= today.year - 10,
    ).count()
    overdue_30 = Archive.query.filter(
        Archive.retention_period == "30年",
        Archive.archive_year <= today.year - 30,
    ).count()
    total_dest = Destruction.query.count()
    pending_appraisal = Destruction.query.filter_by(opinion=None).count()
    return render_template(
        "destroy/list.html",
        overdue_10=overdue_10,
        overdue_30=overdue_30,
        total_dest=total_dest,
        pending_appraisal=pending_appraisal,
        current_year=today.year,
    )


# ─── API: 到期预警档案列表 ───────────────────
@destroy_bp.route("/api/overdue")
@login_required
def api_overdue():
    draw   = request.args.get("draw", 1, type=int)
    start  = request.args.get("start", 0, type=int)
    length = request.args.get("length", 20, type=int)
    search = request.args.get("search[value]", "").strip()
    period = request.args.get("period", "")   # "10年" / "30年"

    today = datetime.date.today()

    q = Archive.query.filter(Archive.retention_period != "永久")
    if period:
        years = RETENTION_YEARS.get(period)
        if years:
            q = q.filter(
                Archive.retention_period == period,
                Archive.archive_year <= today.year - years,
            )
    else:
        # 默认显示所有已到期
        q = q.filter(or_(
            (Archive.retention_period == "10年") & (Archive.archive_year <= today.year - 10),
            (Archive.retention_period == "30年") & (Archive.archive_year <= today.year - 30),
        ))
    if search:
        q = q.filter(or_(
            Archive.title.contains(search),
            Archive.archive_number.contains(search),
        ))

    total = q.count()
    rows = q.order_by(Archive.archive_year.asc()).offset(start).limit(length).all()

    data = []
    for a in rows:
        years = RETENTION_YEARS.get(a.retention_period, 0) or 0
        expire_year = (a.archive_year or 0) + years
        overdue_years = today.year - expire_year if a.archive_year else "—"
        data.append({
            "id": a.id,
            "archive_number": a.archive_number or "",
            "category": a.category or "",
            "title": (a.title or "")[:50],
            "archive_year": a.archive_year or "",
            "retention_period": a.retention_period or "",
            "expire_year": expire_year if a.archive_year else "—",
            "overdue_years": overdue_years,
            "pages": a.pages or "",
        })

    return jsonify({"draw": draw, "recordsTotal": total, "recordsFiltered": total, "data": data})


# ─── API: 鉴定记录列表 ───────────────────────
@destroy_bp.route("/api/records")
@login_required
def api_records():
    draw   = request.args.get("draw", 1, type=int)
    start  = request.args.get("start", 0, type=int)
    length = request.args.get("length", 20, type=int)
    search = request.args.get("search[value]", "").strip()

    q = Destruction.query
    if search:
        q = q.filter(or_(
            Destruction.archive_ref.contains(search),
            Destruction.title_ref.contains(search),
            Destruction.approver_name.contains(search),
        ))

    total = q.count()
    rows = q.order_by(Destruction.appraisal_date.desc()).offset(start).limit(length).all()

    opinion_badge = {
        "销毁": '<span class="badge bg-danger">销毁</span>',
        "保留": '<span class="badge bg-success">保留</span>',
        "延期复查": '<span class="badge bg-warning text-dark">延期复查</span>',
    }
    data = []
    for d in rows:
        data.append({
            "id": d.id,
            "appraisal_date": d.appraisal_date.strftime("%Y-%m-%d") if d.appraisal_date else "",
            "archive_ref": d.archive_ref or "",
            "title_ref": (d.title_ref or "")[:40],
            "retention_period": d.retention_period or "",
            "years_kept": d.years_kept or "",
            "opinion": opinion_badge.get(d.opinion, d.opinion or "未鉴定"),
            "approver_name": d.approver_name or "",
            "remarks": (d.remarks or "")[:30],
        })

    return jsonify({"draw": draw, "recordsTotal": total, "recordsFiltered": total, "data": data})


# ─── API: 新建鉴定记录 ───────────────────────
@destroy_bp.route("/api/create", methods=["POST"])
@login_required
def api_create():
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403

    data = request.json or {}
    date_str = data.get("appraisal_date", "")
    try:
        adate = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    except ValueError:
        adate = datetime.date.today()

    d = Destruction(
        appraisal_date=adate,
        archive_ref=data.get("archive_ref", "").strip(),
        title_ref=data.get("title_ref", "").strip(),
        retention_period=data.get("retention_period", "").strip(),
        years_kept=int(data.get("years_kept", 0) or 0),
        opinion=data.get("opinion", "").strip(),
        approver_name=data.get("approver_name", "").strip(),
        remarks=data.get("remarks", "").strip(),
    )
    db.session.add(d)
    db.session.flush()
    _log("create", d.id, f"新建鉴定记录#{d.id}（{d.archive_ref}）意见：{d.opinion}")
    db.session.commit()
    return jsonify({"ok": True, "id": d.id})


# ─── API: 批量鉴定（从到期预警列表中选） ───────
@destroy_bp.route("/api/batch_appraise", methods=["POST"])
@login_required
def api_batch_appraise():
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403

    data = request.json or {}
    archive_ids = data.get("archive_ids", [])
    opinion = data.get("opinion", "销毁")
    approver_name = data.get("approver_name", current_user.real_name or current_user.username)
    remarks = data.get("remarks", "")
    today = datetime.date.today()

    if not archive_ids:
        return jsonify({"ok": False, "msg": "未选择档案"})

    archives = Archive.query.filter(Archive.id.in_(archive_ids)).all()
    created = 0
    for a in archives:
        years = RETENTION_YEARS.get(a.retention_period, 0) or 0
        years_kept = today.year - (a.archive_year or today.year)
        rec = Destruction(
            archive_id=a.id,
            appraisal_date=today,
            archive_ref=a.archive_number,
            title_ref=a.title,
            retention_period=a.retention_period,
            years_kept=years_kept,
            opinion=opinion,
            approver_name=approver_name,
            remarks=remarks,
        )
        db.session.add(rec)
        created += 1

    _log("create", None, f"批量鉴定{created}条档案，意见：{opinion}")
    db.session.commit()
    return jsonify({"ok": True, "created": created})

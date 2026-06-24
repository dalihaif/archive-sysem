import os
import uuid
import datetime
from flask import render_template, request, jsonify, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from app.transfer import transfer_bp
from app.models import Transfer, TransferAttachment, Archive, OperationLog
from app.extensions import db

CATEGORIES = ["文书", "基建", "科研", "设备", "会计"]

# 允许上传的文件类型
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "gif", "bmp",
    "txt", "zip", "rar", "7z"
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _upload_dir():
    return os.path.join(current_app.root_path, "static", "uploads", "transfer")


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
        att_count = t.attachments.count()
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
            "att_count": att_count,
        })

    return jsonify({"draw": draw, "recordsTotal": total, "recordsFiltered": total, "data": data})


# ─── API: 详情 ───────────────────────────────
@transfer_bp.route("/api/<int:tid>")
@login_required
def api_detail(tid):
    t = Transfer.query.get_or_404(tid)
    attachments = []
    for a in t.attachments.order_by(TransferAttachment.uploaded_at.desc()).all():
        attachments.append({
            "id": a.id,
            "original_name": a.original_name,
            "file_size": a.size_human(),
            "mime_type": a.mime_type,
            "uploader": a.uploader.real_name or a.uploader.username if a.uploader else "未知",
            "uploaded_at": a.uploaded_at.strftime("%Y-%m-%d %H:%M") if a.uploaded_at else "",
        })
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
        "attachments": attachments,
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
    # 同步删除附件文件
    for a in t.attachments.all():
        fpath = os.path.join(_upload_dir(), a.stored_name)
        if os.path.exists(fpath):
            os.remove(fpath)
        db.session.delete(a)
    _log("delete", tid, f"删除移交记录#{tid}")
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})


# ─── API: 上传附件 ───────────────────────────
@transfer_bp.route("/api/<int:tid>/attachments/upload", methods=["POST"])
@login_required
def api_upload_attachment(tid):
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403
    t = Transfer.query.get_or_404(tid)

    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "未选择文件"})
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "msg": "文件名为空"})
    if not _allowed(f.filename):
        return jsonify({"ok": False, "msg": f"不支持的文件类型，允许：{', '.join(sorted(ALLOWED_EXTENSIONS))}"})

    # 检查大小（读入前先检查 content_length）
    f.seek(0, 2)
    size = f.tell()
    f.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({"ok": False, "msg": f"文件超过 20MB 限制（当前 {size/1024/1024:.1f} MB）"})

    ext = f.filename.rsplit(".", 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(_upload_dir(), stored_name)
    f.save(save_path)

    att = TransferAttachment(
        transfer_id=tid,
        original_name=f.filename,
        stored_name=stored_name,
        file_size=size,
        mime_type=f.content_type or "",
        uploader_id=current_user.id,
    )
    db.session.add(att)
    db.session.flush()
    _log("create", tid, f"移交#{tid}上传附件：{f.filename}")
    db.session.commit()
    return jsonify({
        "ok": True,
        "id": att.id,
        "original_name": att.original_name,
        "file_size": att.size_human(),
        "uploaded_at": att.uploaded_at.strftime("%Y-%m-%d %H:%M"),
    })


# ─── API: 附件列表 ───────────────────────────
@transfer_bp.route("/api/<int:tid>/attachments")
@login_required
def api_attachments(tid):
    Transfer.query.get_or_404(tid)
    rows = TransferAttachment.query.filter_by(transfer_id=tid)\
        .order_by(TransferAttachment.uploaded_at.desc()).all()
    data = [{
        "id": a.id,
        "original_name": a.original_name,
        "file_size": a.size_human(),
        "mime_type": a.mime_type,
        "uploader": a.uploader.real_name or a.uploader.username if a.uploader else "未知",
        "uploaded_at": a.uploaded_at.strftime("%Y-%m-%d %H:%M") if a.uploaded_at else "",
    } for a in rows]
    return jsonify({"ok": True, "data": data})


# ─── API: 下载附件 ───────────────────────────
@transfer_bp.route("/api/attachments/<int:aid>/download")
@login_required
def api_download_attachment(aid):
    a = TransferAttachment.query.get_or_404(aid)
    upload_dir = _upload_dir()
    return send_from_directory(
        upload_dir,
        a.stored_name,
        as_attachment=True,
        download_name=a.original_name,
    )


# ─── API: 删除附件 ───────────────────────────
@transfer_bp.route("/api/attachments/<int:aid>/delete", methods=["POST"])
@login_required
def api_delete_attachment(aid):
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403
    a = TransferAttachment.query.get_or_404(aid)
    tid = a.transfer_id
    fpath = os.path.join(_upload_dir(), a.stored_name)
    if os.path.exists(fpath):
        os.remove(fpath)
    _log("delete", tid, f"移交#{tid}删除附件：{a.original_name}")
    db.session.delete(a)
    db.session.commit()
    return jsonify({"ok": True})

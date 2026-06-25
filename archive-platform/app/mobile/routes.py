import datetime
from flask import render_template, request, jsonify
from app.mobile import mobile_bp
from app.models import Borrow, Archive
from app.extensions import db


@mobile_bp.route("/borrow")
def borrow_form():
    return render_template("mobile/borrow_form.html")


@mobile_bp.route("/my-borrows")
def my_borrows():
    return render_template("mobile/my_borrows.html")


# ─────────────────────────────────────────────
# 移动端 API: 根据手机号查询借阅记录（含验证码自动填入）
# ─────────────────────────────────────────────
@mobile_bp.route("/api/borrows/by-phone")
def api_borrows_by_phone():
    phone = request.args.get("phone", "").strip()
    if not phone or len(phone) < 7:
        return jsonify({"ok": False, "msg": "请输入正确的手机号"})

    rows = Borrow.query.filter(
        Borrow.borrower_phone == phone
    ).order_by(Borrow.created_at.desc()).all()

    if not rows:
        return jsonify({"ok": False, "msg": "未找到该手机号的借阅记录"})

    today = datetime.date.today()
    data = []
    access_code = ""

    for b in rows:
        is_overdue = (b.status == "已通过" and b.return_date and b.return_date < today)
        # 取第一个已通过的 access_code
        if b.status == "已通过" and b.access_code and not access_code:
            access_code = b.access_code

        item = {
            "id": b.id,
            "borrower": b.borrower or "",
            "borrower_department": b.borrower_department or "",
            "archive_ref": b.archive_ref or "",
            "purpose": b.purpose or "",
            "borrow_date": b.borrow_date.strftime("%Y-%m-%d") if b.borrow_date else "",
            "return_date": b.return_date.strftime("%Y-%m-%d") if b.return_date else "",
            "status": "已逾期" if is_overdue else b.status,
            "status_raw": b.status,
            "access_code": b.access_code if (b.status == "已通过" and b.access_code) else "",
            "can_view": b.can_view_electronic() if b.status == "已通过" else False,
            "archive_id": b.archive_id or 0,
        }

        # 如果关联了档案，带上电子版信息
        if b.archive_id:
            a = Archive.query.get(b.archive_id)
            if a:
                item["archive_title"] = a.title or ""
                item["archive_number"] = a.archive_number or ""
                item["has_electronic"] = bool(a.electronic_path)

        data.append(item)

    return jsonify({
        "ok": True,
        "count": len(data),
        "access_code": access_code,
        "borrows": data,
    })


# ─────────────────────────────────────────────
# 移动端 API: 验证码验证（可选，前端自动填入后直接验证）
# ─────────────────────────────────────────────
@mobile_bp.route("/api/borrows/verify")
def api_borrows_verify():
    phone = request.args.get("phone", "").strip()
    code = request.args.get("code", "").strip().upper()

    if not phone or not code:
        return jsonify({"ok": False, "msg": "手机号和验证码不能为空"})

    # 验证：该手机号下有匹配的已通过借阅且验证码正确
    b = Borrow.query.filter(
        Borrow.borrower_phone == phone,
        Borrow.status == "已通过",
        Borrow.access_code == code,
    ).first()

    if not b:
        return jsonify({"ok": False, "msg": "验证码不正确或该借阅已失效"})

    if not b.can_view_electronic():
        return jsonify({"ok": False, "msg": "查阅权限已过期（审批后30天内有效）"})

    return jsonify({"ok": True, "borrow_id": b.id})

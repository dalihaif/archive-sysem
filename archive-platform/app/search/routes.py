from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, text
from app.search import search_bp
from app.models import Archive, OperationLog
from app.extensions import db


@search_bp.route("/")
@login_required
def index():
    return render_template("search/index.html")


@search_bp.route("/api/search")
@login_required
def api_search():
    """档案全文检索 API"""
    q_str    = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    year     = request.args.get("year", "")
    period   = request.args.get("period", "")
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not q_str and not category and not year:
        return jsonify({"ok": True, "results": [], "total": 0, "page": page, "pages": 0})

    # SQLAlchemy 查询（多字段LIKE模糊检索）
    q = Archive.query
    if q_str:
        q = q.filter(or_(
            Archive.title.contains(q_str),
            Archive.archive_number.contains(q_str),
            Archive.responsible.contains(q_str),
            Archive.keywords.contains(q_str),
            Archive.doc_number.contains(q_str),
            Archive.remarks.contains(q_str),
        ))
    if category:
        q = q.filter(Archive.category == category)
    if year:
        try:
            q = q.filter(Archive.archive_year == int(year))
        except ValueError:
            pass
    if period:
        q = q.filter(Archive.retention_period == period)

    total = q.count()
    pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page
    rows = q.order_by(Archive.archive_year.desc(), Archive.id.desc()).offset(offset).limit(per_page).all()

    # 关键词高亮辅助函数
    def highlight(text_str, keyword):
        if not keyword or not text_str:
            return text_str or ""
        import re
        escaped = re.escape(keyword)
        return re.sub(f"({escaped})", r'<mark>\1</mark>', text_str, flags=re.IGNORECASE)

    results = []
    for a in rows:
        title_hl = highlight(a.title or "", q_str)
        results.append({
            "id": a.id,
            "archive_number": a.archive_number or "",
            "category": a.category or "",
            "title": title_hl,
            "title_raw": a.title or "",
            "responsible": a.responsible or "",
            "doc_number": a.doc_number or "",
            "archive_year": a.archive_year or "",
            "retention_period": a.retention_period or "",
            "pages": a.pages or "",
            "keywords": highlight(a.keywords or "", q_str),
            "has_electronic": bool(a.electronic_path),
            "has_blockchain": bool(a.bc_hash),
        })

    # 记录搜索操作
    if q_str:
        db.session.add(OperationLog(
            user_id=current_user.id,
            action="search",
            target_type="archive",
            detail=f"检索「{q_str}」共{total}条",
            ip_address=request.remote_addr,
        ))
        db.session.commit()

    return jsonify({
        "ok": True,
        "results": results,
        "total": total,
        "page": page,
        "pages": pages,
        "q": q_str,
    })

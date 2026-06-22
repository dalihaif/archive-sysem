import datetime
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.regulations import reg_bp
from app.models import Regulation, OperationLog
from app.extensions import db


# 内置医院档案法规数据（初始化用）
BUILTIN_REGULATIONS = [
    {
        "title": "中华人民共和国档案法",
        "doc_number": "主席令第58号",
        "publish_date": "2020-06-20",
        "category": "档案法规",
        "content": "档案是国家和社会的重要财富，本法适用于中华人民共和国境内档案的收集、整理、保护、提供利用等活动。医疗卫生机构应当加强档案管理，建立健全档案管理制度。",
        "source": "内置",
    },
    {
        "title": "医疗机构病历管理规定",
        "doc_number": "国卫医发〔2013〕31号",
        "publish_date": "2013-11-20",
        "category": "医疗档案",
        "content": "医疗机构应当建立门（急）诊病历和住院病历。住院病历保存时间自患者最后一次住院之日起不得少于30年。门诊病历由患者保管，或者由医疗机构保管，保管时间不少于15年。",
        "source": "内置",
    },
    {
        "title": "企业档案管理规定",
        "doc_number": "国档发〔2012〕4号",
        "publish_date": "2012-01-16",
        "category": "档案管理",
        "content": "企业应当依法建立健全档案管理制度，明确相关部门和人员的职责分工，确保档案工作顺利开展。档案工作的目标是实现档案管理标准化、规范化。",
        "source": "内置",
    },
    {
        "title": "科学技术档案工作条例",
        "doc_number": "国务院令第6号",
        "publish_date": "1987-05-21",
        "category": "科研档案",
        "content": "科学技术档案是国家的宝贵财富。科学技术档案包括科学研究档案、生产技术档案、基本建设档案、设备仪器档案。",
        "source": "内置",
    },
    {
        "title": "机关档案管理规定",
        "doc_number": "国家档案局令第13号",
        "publish_date": "2023-04-03",
        "category": "档案法规",
        "content": "机关档案是机关在履行职责过程中形成的具有保存价值的各种文字、图表、声像等不同形式和载体的历史记录。机关应当建立档案工作规章制度，明确档案工作人员岗位职责。",
        "source": "内置",
    },
    {
        "title": "会计档案管理办法",
        "doc_number": "财会〔2015〕27号",
        "publish_date": "2016-01-01",
        "category": "会计档案",
        "content": "会计档案是指单位在进行会计核算等过程中接收或形成的，记录和反映单位经济业务事项的，具有保存价值的文字、图表等各种形式和载体的文件材料。各类会计档案的保管期限最低为5年至永久不等。",
        "source": "内置",
    },
    {
        "title": "基本建设项目档案资料管理暂行规定",
        "doc_number": "国档发〔1988〕4号",
        "publish_date": "1988-03-22",
        "category": "基建档案",
        "content": "凡国家投资、计划和地方投资建设的工程项目，从立项开始到竣工验收，各建设、设计、施工单位都必须认真做好档案资料的收集、整理和移交工作。",
        "source": "内置",
    },
    {
        "title": "档案库房技术管理暂行规定",
        "doc_number": "国档发〔1987〕17号",
        "publish_date": "1987-07-01",
        "category": "档案管理",
        "content": "档案库房是保管档案实体的专门场所。档案库房应达到防盗、防火、防潮、防虫、防鼠、防光、防污染等安全要求，以确保档案安全。",
        "source": "内置",
    },
]


def _log(action, target_id, detail):
    db.session.add(OperationLog(
        user_id=current_user.id,
        action=action,
        target_type="regulation",
        target_id=target_id,
        detail=detail,
        ip_address=request.remote_addr,
    ))


@reg_bp.route("/")
@login_required
def list():
    """法规制度主页"""
    # 首次访问时，自动初始化内置法规
    if Regulation.query.count() == 0:
        for r in BUILTIN_REGULATIONS:
            date_str = r.get("publish_date", "")
            try:
                pub_date = datetime.date.fromisoformat(date_str) if date_str else None
            except ValueError:
                pub_date = None
            reg = Regulation(
                title=r["title"],
                doc_number=r.get("doc_number", ""),
                publish_date=pub_date,
                source=r.get("source", "内置"),
                category=r.get("category", ""),
                content=r.get("content", ""),
            )
            db.session.add(reg)
        db.session.commit()

    categories = db.session.query(Regulation.category).filter(
        Regulation.category.isnot(None), Regulation.category != ""
    ).distinct().all()
    cat_list = [c[0] for c in categories]
    return render_template("regulations/list.html", categories=cat_list)


# ─── API: 列表 ───────────────────────────────
@reg_bp.route("/api/list")
@login_required
def api_list():
    draw   = request.args.get("draw", 1, type=int)
    start  = request.args.get("start", 0, type=int)
    length = request.args.get("length", 20, type=int)
    search = request.args.get("search[value]", "").strip()
    category = request.args.get("category", "")

    q = Regulation.query
    if search:
        q = q.filter(or_(
            Regulation.title.contains(search),
            Regulation.doc_number.contains(search),
            Regulation.content.contains(search),
        ))
    if category:
        q = q.filter(Regulation.category == category)

    total = q.count()
    rows = q.order_by(Regulation.publish_date.desc()).offset(start).limit(length).all()

    source_badge = {
        "内置": '<span class="badge bg-secondary">内置</span>',
        "爬取": '<span class="badge bg-info">爬取</span>',
        "手动添加": '<span class="badge bg-success">手动添加</span>',
    }

    data = []
    for r in rows:
        data.append({
            "id": r.id,
            "title": r.title or "",
            "doc_number": r.doc_number or "",
            "publish_date": r.publish_date.strftime("%Y-%m-%d") if r.publish_date else "",
            "category": r.category or "",
            "source": source_badge.get(r.source, r.source or ""),
            "content_snippet": (r.content or "")[:60],
        })

    return jsonify({"draw": draw, "recordsTotal": total, "recordsFiltered": total, "data": data})


# ─── API: 详情 ───────────────────────────────
@reg_bp.route("/api/<int:rid>")
@login_required
def api_detail(rid):
    r = Regulation.query.get_or_404(rid)
    return jsonify({
        "id": r.id,
        "title": r.title,
        "doc_number": r.doc_number or "",
        "publish_date": r.publish_date.strftime("%Y-%m-%d") if r.publish_date else "",
        "category": r.category or "",
        "source": r.source or "",
        "source_url": r.source_url or "",
        "content": r.content or "",
        "created_at": r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
    })


# ─── API: 新建/编辑 ──────────────────────────
@reg_bp.route("/api/save", methods=["POST"])
@login_required
def api_save():
    if not current_user.can_edit():
        return jsonify({"ok": False, "msg": "权限不足"}), 403

    data = request.json or {}
    rid = data.get("id")
    if rid:
        r = Regulation.query.get_or_404(int(rid))
        action_log = "update"
    else:
        r = Regulation()
        db.session.add(r)
        action_log = "create"

    r.title = data.get("title", "").strip()
    r.doc_number = data.get("doc_number", "").strip()
    r.category = data.get("category", "").strip()
    r.content = data.get("content", "").strip()
    r.source = data.get("source", "手动添加")
    r.source_url = data.get("source_url", "").strip()

    date_str = data.get("publish_date", "")
    try:
        r.publish_date = datetime.date.fromisoformat(date_str) if date_str else None
    except ValueError:
        r.publish_date = None

    if not r.title:
        return jsonify({"ok": False, "msg": "标题不能为空"})

    db.session.flush()
    _log(action_log, r.id, f"{action_log} 法规#{r.id}：{r.title}")
    db.session.commit()
    return jsonify({"ok": True, "id": r.id})


# ─── API: 删除 ───────────────────────────────
@reg_bp.route("/api/<int:rid>/delete", methods=["POST"])
@login_required
def api_delete(rid):
    if not current_user.is_admin():
        return jsonify({"ok": False, "msg": "需要管理员权限"}), 403
    r = Regulation.query.get_or_404(rid)
    _log("delete", rid, f"删除法规#{rid}：{r.title}")
    db.session.delete(r)
    db.session.commit()
    return jsonify({"ok": True})

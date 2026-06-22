import datetime
import os

from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.import_data import import_bp
from app.import_data.parser import parse_excel, import_data_to_db
from app.models import OperationLog
from app.extensions import db
from flask import current_app as app


@import_bp.route("/")
@login_required
def index():
    return render_template("import_data/index.html")


@import_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    """上传并预览解析结果"""
    if not current_user.can_edit():
        return jsonify({"error": "无导入权限"}), 403

    if "file" not in request.files:
        return jsonify({"error": "未选择文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    if not file.filename.endswith((".xlsx", ".xls")):
        return jsonify({"error": "仅支持 .xlsx / .xls 格式"}), 400

    # 保存临时文件
    filename = secure_filename(file.filename)
    upload_folder = app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}")
    file.save(filepath)

    try:
        records = parse_excel(filepath)
        # 只返回前 100 条预览
        preview = records[:100]
        return jsonify({
            "success": True,
            "total": len(records),
            "preview": preview,
            "preview_count": len(preview),
            "filepath": filepath,
            "filename": filename,
        })
    except Exception as e:
        return jsonify({"error": f"解析失败: {str(e)}"}), 500


@import_bp.route("/confirm", methods=["POST"])
@login_required
def confirm():
    """确认导入"""
    if not current_user.can_edit():
        return jsonify({"error": "无导入权限"}), 403

    data = request.get_json()
    if not data or "filepath" not in data:
        return jsonify({"error": "未提供文件路径"}), 400

    filepath = data["filepath"]
    batch_name = data.get("batch", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))

    try:
        result = import_data_to_db(filepath, None, batch_name)

        # 操作日志
        log = OperationLog(
            user_id=current_user.id,
            action="import",
            target_type="archive",
            detail=f"导入档案: {result['message']}",
        )
        db.session.add(log)
        db.session.commit()

        # 清理临时文件
        try:
            os.remove(filepath)
        except OSError:
            pass

        return jsonify({"success": True, **result})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"导入失败: {str(e)}"}), 500


@import_bp.route("/direct-import", methods=["POST"])
@login_required
def direct_import():
    """一键导入workspace中的Excel文件（管理员专用）"""
    if not current_user.is_admin():
        return jsonify({"error": "仅管理员可执行批量导入"}), 403

    import glob

    workspace = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    excel_files = glob.glob(os.path.join(workspace, "*.xlsx"))

    results = []
    for fp in excel_files:
        fn = os.path.basename(fp)
        # 跳过非档案文件
        if "文书档案管理" not in fn and "基建档案" not in fn and "科研档案" not in fn and "设备档案" not in fn and "会计档案" not in fn:
            continue
        try:
            result = import_data_to_db(fp, None)
            results.append({"file": fn, **result})
        except Exception as e:
            results.append({"file": fn, "error": str(e)})

    # 操作日志
    total_imported = sum(r.get("imported", 0) for r in results)
    log = OperationLog(
        user_id=current_user.id,
        action="import",
        target_type="archive",
        detail=f"批量导入完成: 共{len(results)}个文件, 导入{total_imported}条",
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"success": True, "results": results, "total_imported": total_imported})

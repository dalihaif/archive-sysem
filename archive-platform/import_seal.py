"""
印章档案导入脚本
将 E:\工作文档\档案室\08_印章档案\印章档案目录.xlsx 导入到 archives 表
category="实物", object_type="印章"
"""
import datetime
import openpyxl
from app import create_app
from app.extensions import db
from app.models import Archive

EXCEL_PATH = r"E:\工作文档\档案室\08_印章档案\印章档案目录.xlsx"

# Excel 日期序列号 -> Python date（1900 年基准，Excel 有 1900-02-29 Bug 需修正）
def excel_date_to_date(value):
    if value is None:
        return None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.date() if isinstance(value, datetime.datetime) else value
    try:
        n = int(value)
        if n <= 0:
            return None
        # Excel 1900-02-29 Bug：序列号 > 60 要减 1
        if n > 60:
            n -= 1
        delta = datetime.timedelta(days=n - 1)
        return (datetime.date(1900, 1, 1) + delta)
    except Exception:
        return None

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    else:
        return f"{size_bytes/1024/1024:.1f} MB"

def main():
    app = create_app()
    with app.app_context():
        wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
        ws = wb["Sheet1"]
        rows = list(ws.iter_rows(values_only=True))

        # 跳过表头（第1行）
        data_rows = rows[1:]

        inserted = 0
        skipped = 0
        errors = 0

        for i, row in enumerate(data_rows, start=2):
            # 跳过全空行
            if not any(row):
                continue

            # 列：编号, 印章名称, 材质, 形状, 启用时间, 废止时间, 备注
            seq_num  = row[0]   # 编号
            name     = row[1]   # 印章名称
            material = row[2]   # 材质
            shape    = row[3]   # 形状
            start_dt = row[4]   # 启用时间（Excel序列号或日期）
            end_dt   = row[5]   # 废止时间
            remark   = row[6]   # 备注

            if not name:
                print(f"  行 {i}: 名称为空，跳过")
                skipped += 1
                continue

            # 格式化 archive_number: YZ-001
            try:
                num_str = f"YZ-{int(seq_num):03d}" if seq_num is not None else f"YZ-{i-1:03d}"
            except (ValueError, TypeError):
                num_str = f"YZ-{i-1:03d}"

            # 按 archive_number 去重
            exists = Archive.query.filter_by(
                archive_number=num_str, category="实物"
            ).first()
            if exists:
                skipped += 1
                continue

            # 关键词：材质 + 形状
            kw_parts = []
            if material:
                kw_parts.append(str(material).strip())
            if shape:
                kw_parts.append(str(shape).strip())
            keywords = " ".join(kw_parts)

            # 备注：合并废止时间 + 原备注
            remarks_parts = []
            end_date = excel_date_to_date(end_dt)
            if end_date:
                remarks_parts.append(f"废止：{end_date.strftime('%Y-%m-%d')}")
            if remark:
                remarks_parts.append(str(remark).strip())
            remarks = "；".join(remarks_parts)

            # 启用日期
            start_date = excel_date_to_date(start_dt)

            # 提取年份
            year = start_date.year if start_date else None

            try:
                archive = Archive(
                    category="实物",
                    object_type="印章",
                    archive_number=num_str,
                    title=str(name).strip(),
                    archive_year=year,
                    doc_date=start_date,
                    keywords=keywords,
                    remarks=remarks,
                    retention_period="永久",
                    responsible="档案室",
                    import_batch="seal_2026",
                )
                db.session.add(archive)
                inserted += 1

                if inserted % 50 == 0:
                    db.session.commit()
                    print(f"  已处理 {inserted} 条...")

            except Exception as e:
                print(f"  行 {i} 错误: {e}")
                errors += 1
                db.session.rollback()
                continue

        db.session.commit()
        print(f"\n===== 印章档案导入完成 =====")
        print(f"  成功导入: {inserted} 条")
        print(f"  跳过(重复/空): {skipped} 条")
        print(f"  错误: {errors} 条")

        # 验证
        count = Archive.query.filter_by(category="实物", object_type="印章").count()
        print(f"  数据库实物·印章总计: {count} 条")

if __name__ == "__main__":
    main()

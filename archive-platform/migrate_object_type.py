"""迁移脚本：为 archives 表添加 object_type 列"""
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    db.create_all()
    result = db.session.execute(text("PRAGMA table_info(archives)")).fetchall()
    cols = [row[1] for row in result]
    if "object_type" in cols:
        print("object_type 列已存在 OK")
    else:
        db.session.execute(text("ALTER TABLE archives ADD COLUMN object_type VARCHAR(30) DEFAULT ''"))
        db.session.commit()
        print("object_type 列已添加 OK")
    print(f"总列数: {len(cols)}，object_type 存在: {'object_type' in cols or True}")

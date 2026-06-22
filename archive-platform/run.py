#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
大理大学第一附属医院档案管理平台
运行入口
"""

import os
import sys

# 确保项目根目录在 Python Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import datetime

from app import create_app
from app.extensions import db
from app.models import User, Regulation

app = create_app(os.environ.get("FLASK_ENV", "development"))


def init_db():
    """初始化数据库：创建表 + 默认管理员 + 默认法规数据"""
    with app.app_context():
        db.create_all()

        # 创建默认管理员
        if not User.query.filter_by(username="admin").first():
            admin = User(
                username="admin",
                role="admin",
                real_name="系统管理员",
                department="档案室",
                active=True,
            )
            admin.set_password("admin123")
            db.session.add(admin)
            print("[初始化] 默认管理员已创建: admin / admin123")
        else:
            print("[初始化] 管理员账号已存在，跳过创建")

        # 创建默认编辑者
        if not User.query.filter_by(username="editor").first():
            editor = User(
                username="editor",
                role="editor",
                real_name="档案管理员",
                department="档案室",
                active=True,
            )
            editor.set_password("editor123")
            db.session.add(editor)
            print("[初始化] 默认编辑者已创建: editor / editor123")

        # 创建默认浏览者
        if not User.query.filter_by(username="viewer").first():
            viewer = User(
                username="viewer",
                role="viewer",
                real_name="普通用户",
                department="全院",
                active=True,
            )
            viewer.set_password("viewer123")
            db.session.add(viewer)
            print("[初始化] 默认浏览者已创建: viewer / viewer123")

        # 导入法规制度初始数据
        if Regulation.query.count() == 0:
            regulations = [
                ("《中华人民共和国档案法》", "主席令第47号（2020修订）", "2020-06-20",
                 "档案工作实行统一领导、分级管理原则；电子档案与传统载体档案具有同等效力；明确档案监督检查制度和法律责任。"),
                ("《中华人民共和国档案法实施条例》", "国务院令第772号", "2024-01-12",
                 "细化档案法操作规范，明确电子档案管理要求，规定档案开放审核程序和利用规则。"),
                ("《机关文件材料归档范围和文书档案保管期限规定》", "国家档案局令第8号", "2006-12-18",
                 "规定机关文件材料的归档范围和不归档范围，确定永久和定期（30年/10年）两档保管期限。"),
                ("《归档文件整理规则》", "DA/T 22-2015", "2015-10-25",
                 "以件为管理单位，规范归档文件整理：分类→排列→编号→编目→装订→装盒。"),
                ("《文书档案案卷格式》", "GB/T 9705-2008", "2008-11-01",
                 "规定文书档案案卷的卷皮、卷内文件目录、备考表等格式要求。"),
                ("《电子文件归档与电子档案管理规范》", "GB/T 18894-2016", "2016-08-29",
                 "电子文件归档范围、整理方法、元数据要求、长期保存策略。"),
                ("《纸质档案数字化技术规范》", "DA/T 31-2017", "2017-07-01",
                 "纸质档案扫描参数、图像处理、数据存储、质量控制等技术要求。"),
                ("《档案保管外包服务管理规范》", "DA/T 83-2019", "2019-12-30",
                 "规范档案保管外包服务的机构要求、合同管理、服务质量评价。"),
                ("《政务服务事项电子文件归档规范》", "GB/T 38390-2019", "2019-12-10",
                 "政务服务事项办理过程中形成的电子文件的归档范围、整理方法和保存格式。"),
                ("《重大活动和突发事件档案管理办法》", "国家档案局令第16号", "2020-12-31",
                 "重大活动、突发事件的档案收集范围、整理原则、移交时间和特殊管理要求。"),
            ]
            for title, doc_num, pub_date_str, content in regulations:
                y, m, d = pub_date_str.split("-")
                r = Regulation(
                    title=title,
                    doc_number=doc_num,
                    publish_date=datetime.date(int(y), int(m), int(d)),
                    content=content,
                    source="内置",
                    category="国家法规",
                )
                db.session.add(r)
            print(f"[初始化] {len(regulations)} 部法规制度已导入")
        else:
            print(f"[初始化] 法规数据已存在，跳过导入")

        db.session.commit()
        print("[初始化] 数据库初始化完成！")


if __name__ == "__main__":
    init_db()

    # 启动 APScheduler
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from scheduler import init_scheduler
        init_scheduler(app)
        print("[调度器] APScheduler 已启动")

    # 启动服务
    print("\n 档案管理平台启动中...")
    print(f" 访问地址: http://localhost:5100")
    print(f" 管理员: admin / admin123")
    print(f" 编辑者: editor / editor123")
    print(f" 浏览者: viewer / viewer123")
    print(f" 移动端借阅: http://localhost:5100/m/borrow\n")

    app.run(host="0.0.0.0", port=5100, debug=True)

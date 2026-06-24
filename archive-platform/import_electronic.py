"""
电子档案文件批量匹配导入脚本
将 E:\工作文档\档案室\03_红头文件存档 下的文件
与数据库档案目录标题匹配后：
  1. 复制文件到 app/static/uploads/electronic/
  2. 更新 Archive.electronic_path / electronic_size / electronic_location
  3. 将文件注册为 ArchiveAttachment（附件记录）
"""

import os
import re
import shutil
import uuid
import sys
import traceback
from datetime import datetime

# ── 路径配置 ─────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
SRC_ROOT     = r"E:\工作文档\档案室\03_红头文件存档"
DEST_DIR     = os.path.join(SCRIPT_DIR, "app", "static", "uploads", "electronic")
os.makedirs(DEST_DIR, exist_ok=True)

# 需要处理的子目录 → 对应档案分类提示（仅用于日志，匹配仍靠标题）
SUB_DIRS = ["行政发文", "党委发文", "会议纪要", "小红头", "收文归档"]

# 允许的文件类型
ALLOWED_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
               ".jpg", ".jpeg", ".png", ".gif", ".txt", ".zip", ".rar", ".7z"}

# ── Flask 应用上下文 ─────────────────────────────────────
sys.path.insert(0, SCRIPT_DIR)
from app import create_app
from app.extensions import db
from app.models import Archive

app = create_app()

# ── 工具函数 ─────────────────────────────────────────────

def extract_title_keywords(filename: str) -> list[str]:
    """
    从文件名提取多组关键词用于匹配。
    返回列表，从最精确到最宽泛，匹配时按序尝试。
    """
    name = os.path.splitext(filename)[0].strip()
    candidates = []

    # 模式1: "N号—内容" 或 "N号-内容"
    m = re.match(r'^\d+号\s*[—\-─]\s*(.+)$', name)
    if m:
        candidates.append(m.group(1).strip())

    # 模式2: 发文号格式 "大附院发〔2020〕10号 内容" 或 "大附院党发〔2020〕10号：内容"
    m = re.match(r'^.{0,40}[〔\[]\d{4}[〕\]]\d+号\s*[： :]\s*(.+)$', name)
    if m:
        candidates.append(m.group(1).strip())

    # 模式3: 发文号格式括号内容 "大院附党发[2004]12号（关于院级领导分管）"
    m = re.match(r'^.{0,40}[〔\[\(（]\d{4}[〕\]\)）]\d+号[（(](.+)[）)]$', name)
    if m:
        candidates.append(m.group(1).strip())

    # 模式4: 整个文件名（去扩展名）作为候选
    if name not in candidates:
        candidates.append(name)

    # 模式5: 去掉首部号码后的整体
    clean = re.sub(r'^[\d号年\-—─\s]+', '', name).strip()
    if clean and clean not in candidates:
        candidates.append(clean)

    return candidates


def extract_year_from_path(filepath: str) -> str | None:
    """从路径中提取年份（4位数字目录名）"""
    parts = filepath.replace("\\", "/").split("/")
    for p in parts:
        m = re.match(r'^(20\d{2}|19\d{2})$', p)
        if m:
            return m.group(1)
    return None


def size_human(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ── 主逻辑 ───────────────────────────────────────────────

def run():
    stats = {
        "scanned": 0,
        "matched": 0,
        "skipped_dup": 0,
        "skipped_ext": 0,
        "failed": 0,
        "no_match": 0,
    }

    matched_log = []    # (src_path, db_id, db_title, keywords)
    no_match_log = []   # (src_path, keywords)

    print(f"[{datetime.now():%H:%M:%S}] 开始扫描: {SRC_ROOT}")
    print(f"存储目录: {DEST_DIR}")
    print("=" * 70)

    with app.app_context():
        # 预加载所有文书档案到内存（title → list[Archive]）
        print("预加载档案目录...")
        all_archives = Archive.query.filter_by(category="文书").all()
        print(f"  文书档案共 {len(all_archives)} 条")

        # 建立索引：title (去空格/标点规范化) → archive id列表
        def normalize(s: str) -> str:
            if not s:
                return ""
            # 全角转半角，去掉多余空格，统一括号
            s = s.replace("（", "(").replace("）", ")").replace("【", "[").replace("】", "]")
            s = re.sub(r'\s+', '', s)
            return s.lower()

        title_index: dict[str, list[Archive]] = {}
        for arc in all_archives:
            key = normalize(arc.title or "")
            if key:
                title_index.setdefault(key, []).append(arc)

        print(f"  标题索引建立完成，唯一键 {len(title_index)} 个")

        def find_archive(keywords: list[str], year_hint: str | None) -> Archive | None:
            """按关键词和年份查找最佳匹配"""
            for kw in keywords:
                nkw = normalize(kw)
                if not nkw or len(nkw) < 4:
                    continue
                # 精确匹配
                if nkw in title_index:
                    candidates = title_index[nkw]
                    if year_hint:
                        yr_match = [a for a in candidates if a.archive_year == year_hint]
                        if yr_match:
                            return yr_match[0]
                    return candidates[0]
                # 包含匹配：找 title 中包含 kw 的
                hits = []
                for key, arcs in title_index.items():
                    if nkw in key or key in nkw:
                        hits.extend(arcs)
                if hits:
                    if year_hint:
                        yr_match = [a for a in hits if a.archive_year == year_hint]
                        if yr_match:
                            return yr_match[0]
                    return hits[0]
            return None

        # 扫描文件
        for subdir in SUB_DIRS:
            src_subdir = os.path.join(SRC_ROOT, subdir)
            if not os.path.isdir(src_subdir):
                continue

            for dirpath, _, filenames in os.walk(src_subdir):
                for fname in filenames:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in ALLOWED_EXT:
                        stats["skipped_ext"] += 1
                        continue
                    # 跳过目录文件（Excel目录）
                    if re.search(r'目录|汇编|模板|desktop', fname, re.IGNORECASE):
                        stats["skipped_ext"] += 1
                        continue

                    stats["scanned"] += 1
                    src_path = os.path.join(dirpath, fname)
                    year_hint = extract_year_from_path(src_path)
                    keywords = extract_title_keywords(fname)

                    # 找匹配
                    arc = find_archive(keywords, year_hint)
                    if not arc:
                        stats["no_match"] += 1
                        no_match_log.append((src_path, keywords))
                        continue

                    # 已有电子版则跳过（避免重复）
                    if arc.electronic_path:
                        stats["skipped_dup"] += 1
                        continue

                    # 复制文件
                    try:
                        new_name = f"{uuid.uuid4().hex}{ext}"
                        dest_path = os.path.join(DEST_DIR, new_name)
                        shutil.copy2(src_path, dest_path)
                        file_size = os.path.getsize(dest_path)

                        # 更新数据库
                        rel_path = f"uploads/electronic/{new_name}"
                        arc.electronic_path = rel_path
                        arc.electronic_size = file_size
                        arc.electronic_location = src_path  # 原始路径记录

                        stats["matched"] += 1
                        matched_log.append((src_path, arc.id, arc.title[:50], keywords[0] if keywords else ""))
                    except Exception as e:
                        stats["failed"] += 1
                        print(f"  [ERROR] {fname}: {e}")

                # 每200条提交一次
                if stats["matched"] > 0 and stats["matched"] % 200 == 0:
                    db.session.commit()
                    print(f"  已提交 {stats['matched']} 条...")

        # 最终提交
        db.session.commit()
        print()

    # ── 打印报告 ──────────────────────────────────────────
    print("=" * 70)
    print(f"扫描文件:   {stats['scanned']}")
    print(f"成功匹配:   {stats['matched']}")
    print(f"未能匹配:   {stats['no_match']}")
    print(f"已有跳过:   {stats['skipped_dup']}")
    print(f"类型跳过:   {stats['skipped_ext']}")
    print(f"失败:       {stats['failed']}")
    print()

    # 保存未匹配记录
    no_match_file = os.path.join(SCRIPT_DIR, "electronic_no_match.txt")
    with open(no_match_file, "w", encoding="utf-8") as f:
        f.write(f"未匹配文件列表（共 {len(no_match_log)} 条）\n")
        f.write("=" * 70 + "\n")
        for path, kws in no_match_log:
            f.write(f"{path}\n  关键词: {kws}\n")
    print(f"未匹配记录已保存: {no_match_file}")

    # 保存匹配成功记录
    match_file = os.path.join(SCRIPT_DIR, "electronic_matched.txt")
    with open(match_file, "w", encoding="utf-8") as f:
        f.write(f"匹配成功列表（共 {len(matched_log)} 条）\n")
        f.write("=" * 70 + "\n")
        for path, aid, title, kw in matched_log:
            f.write(f"[ID:{aid}] {title}\n  文件: {path}\n  关键词: {kw}\n")
    print(f"匹配成功记录已保存: {match_file}")


if __name__ == "__main__":
    run()

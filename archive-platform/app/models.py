import datetime
import hashlib
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


# ============================================================
# 用户模型
# ============================================================
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), default="")
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer")  # admin / editor / viewer
    real_name = db.Column(db.String(50))
    department = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "admin"

    def can_edit(self):
        return self.role in ("admin", "editor")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================================
# 档案总库
# ============================================================
class Archive(db.Model):
    __tablename__ = "archives"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 档案类别：文书/基建/科研/设备
    category = db.Column(db.String(20), nullable=False, default="文书", index=True)

    # 核心档案字段（Excel导入）
    archive_number = db.Column(db.String(100), default="", index=True)     # 档号
    fonds_number = db.Column(db.String(50), default="")                     # 全宗号
    archive_year = db.Column(db.Integer, index=True)                        # 归档年度
    retention_period = db.Column(db.String(20), default="", index=True)     # 保管期限
    class_number = db.Column(db.String(100), default="")                    # 分类号
    file_number = db.Column(db.Integer)                                     # 件号
    title = db.Column(db.Text, default="")                                  # 文件题名
    responsible = db.Column(db.String(200), default="")                     # 责任者
    doc_number = db.Column(db.String(100), default="")                      # 文件编号
    doc_date = db.Column(db.Date, index=True)                               # 形成日期
    pages = db.Column(db.String(50), default="")                            # 页数

    # 辅助字段
    keywords = db.Column(db.Text, default="")                               # 主题词
    remarks = db.Column(db.Text, default="")                                # 备注

    # 电子版管理
    electronic_path = db.Column(db.String(500), default="")                 # 电子文件存储路径
    electronic_size = db.Column(db.Integer, default=0)                      # 文件大小(bytes)
    electronic_location = db.Column(db.String(200), default="")             # 物理存放位置

    # 区块链可信
    bc_hash = db.Column(db.String(64), default="")                          # SHA-256
    bc_md5 = db.Column(db.String(32), default="")                           # MD5
    bc_tx_id = db.Column(db.String(128), default="")                        # FISCO BCOS交易ID
    bc_timestamp = db.Column(db.DateTime)                                   # 上链时间

    # 元数据
    import_batch = db.Column(db.String(50), default="", index=True)         # 导入批次
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 关联
    transfers = db.relationship("Transfer", backref="archive", lazy="dynamic")
    borrows = db.relationship("Borrow", backref="archive", lazy="dynamic")
    destructions = db.relationship("Destruction", backref="archive", lazy="dynamic")

    def compute_hashes(self, data: bytes):
        """计算并设置区块链哈希值"""
        self.bc_hash = hashlib.sha256(data).hexdigest()
        self.bc_md5 = hashlib.md5(data).hexdigest()

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "archive_number": self.archive_number,
            "fonds_number": self.fonds_number,
            "archive_year": self.archive_year,
            "retention_period": self.retention_period,
            "class_number": self.class_number,
            "file_number": self.file_number,
            "title": self.title,
            "responsible": self.responsible,
            "doc_number": self.doc_number,
            "doc_date": self.doc_date.isoformat() if self.doc_date else None,
            "pages": self.pages,
            "keywords": self.keywords,
            "remarks": self.remarks,
            "electronic_path": self.electronic_path,
            "electronic_location": self.electronic_location,
            "bc_hash": self.bc_hash,
            "bc_md5": self.bc_md5,
            "bc_tx_id": self.bc_tx_id,
        }

    def __repr__(self):
        return f"<Archive {self.id} {self.category} {self.title[:30] if self.title else ''}>"


# ============================================================
# 移交管理
# ============================================================
class Transfer(db.Model):
    __tablename__ = "transfers"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    archive_id = db.Column(db.Integer, db.ForeignKey("archives.id"), nullable=True)

    transfer_date = db.Column(db.Date, index=True)
    from_department = db.Column(db.String(100))       # 移交部门
    from_person = db.Column(db.String(50))             # 移交人
    to_department = db.Column(db.String(100))          # 接收部门
    to_person = db.Column(db.String(50))               # 接收人
    transfer_type = db.Column(db.String(100))          # 移交类别
    quantity = db.Column(db.Integer, default=0)
    start_number = db.Column(db.String(50))            # 起止件号
    status = db.Column(db.String(20), default="已完成") # 移交状态
    remarks = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Transfer {self.id} {self.status}>"


# ============================================================
# 移交附件
# ============================================================
class TransferAttachment(db.Model):
    __tablename__ = "transfer_attachments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("transfers.id"), nullable=False, index=True)
    transfer = db.relationship("Transfer", backref=db.backref("attachments", lazy="dynamic"))

    original_name = db.Column(db.String(255), nullable=False)   # 原始文件名
    stored_name = db.Column(db.String(255), nullable=False)      # 磁盘存储名（uuid+扩展名）
    file_size = db.Column(db.Integer, default=0)                 # 字节数
    mime_type = db.Column(db.String(100), default="")            # MIME类型
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    uploader = db.relationship("User", backref="transfer_attachments")
    uploaded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def size_human(self):
        """返回可读文件大小"""
        size = self.file_size or 0
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def __repr__(self):
        return f"<TransferAttachment {self.id} {self.original_name}>"


# ============================================================
# 借阅管理
# ============================================================
class Borrow(db.Model):
    __tablename__ = "borrows"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    archive_id = db.Column(db.Integer, db.ForeignKey("archives.id"), nullable=True)

    borrow_date = db.Column(db.Date, index=True)
    borrower = db.Column(db.String(50), nullable=False)            # 借阅人
    borrower_department = db.Column(db.String(100))                # 借阅部门
    borrower_phone = db.Column(db.String(20))                      # 手机号（通知）
    archive_ref = db.Column(db.String(200))                        # 档号/文件题名
    purpose = db.Column(db.Text)                                   # 借阅目的
    return_date = db.Column(db.Date)                               # 归还日期

    # 审批
    status = db.Column(db.String(20), default="待审批", index=True)  # 待审批/已通过/已拒绝/已归还
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approver = db.relationship("User", backref="approved_borrows")
    approve_time = db.Column(db.DateTime)
    approve_comment = db.Column(db.Text)

    # 移动端访问
    access_code = db.Column(db.String(6))                          # 6位验证码

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def can_view_electronic(self):
        """审批通过后30天内可查看电子版"""
        if self.status != "已通过":
            return False
        if self.approve_time is None:
            return False
        expire_date = self.approve_time + datetime.timedelta(days=30)
        return datetime.datetime.utcnow() < expire_date

    def __repr__(self):
        return f"<Borrow {self.id} {self.borrower} {self.status}>"


# ============================================================
# 销毁鉴定
# ============================================================
class Destruction(db.Model):
    __tablename__ = "destructions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    archive_id = db.Column(db.Integer, db.ForeignKey("archives.id"), nullable=True)

    appraisal_date = db.Column(db.Date)
    archive_ref = db.Column(db.String(200))           # 档号/分类
    title_ref = db.Column(db.Text)                    # 文件题名
    retention_period = db.Column(db.String(20))
    years_kept = db.Column(db.Integer)                # 已保管年限
    opinion = db.Column(db.String(50))                # 鉴定意见
    approver_name = db.Column(db.String(50))          # 批准人
    remarks = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Destruction {self.id} {self.opinion}>"


# ============================================================
# 法规制度
# ============================================================
class Regulation(db.Model):
    __tablename__ = "regulations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    doc_number = db.Column(db.String(100))            # 文号/标准号
    publish_date = db.Column(db.Date)
    source = db.Column(db.String(50), default="内置")  # 内置/爬取/手动添加
    source_url = db.Column(db.String(500))
    content = db.Column(db.Text)                      # 核心要点
    category = db.Column(db.String(50))               # 分类

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Regulation {self.title}>"


# ============================================================
# 归档范围对照表
# ============================================================
class FilingScope(db.Model):
    __tablename__ = "filing_scopes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    seq = db.Column(db.Integer)
    file_category = db.Column(db.String(200))         # 文件类别
    filing_scope = db.Column(db.Text)                 # 归档范围
    retention_period = db.Column(db.String(50))       # 保管期限
    description = db.Column(db.Text)                  # 说明

    def __repr__(self):
        return f"<FilingScope {self.seq}>"


# ============================================================
# 档号编制规则
# ============================================================
class ArchiveNumberRule(db.Model):
    __tablename__ = "archive_number_rules"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item = db.Column(db.String(100))                  # 项目
    description = db.Column(db.Text)                  # 说明
    example = db.Column(db.Text)                      # 示例

    def __repr__(self):
        return f"<ArchiveNumberRule {self.item}>"


# ============================================================
# 操作日志
# ============================================================
class OperationLog(db.Model):
    __tablename__ = "operation_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user = db.relationship("User", backref="logs")
    action = db.Column(db.String(50), nullable=False)   # create/update/delete/login/import/export
    target_type = db.Column(db.String(50))               # archive/user/transfer/borrow
    target_id = db.Column(db.Integer)
    detail = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)

    def __repr__(self):
        return f"<OperationLog {self.action} {self.target_type}>"


# ============================================================
# 外部搜索缓存
# ============================================================
class ExternalSearchCache(db.Model):
    __tablename__ = "external_search_cache"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    query = db.Column(db.String(500), index=True)
    source = db.Column(db.String(50))                 # baidu/bing/archive_org
    result_json = db.Column(db.Text)                  # JSON格式缓存结果
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<ExternalSearchCache {self.query[:30]}>"

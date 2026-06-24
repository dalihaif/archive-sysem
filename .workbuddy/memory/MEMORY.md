# 档案管理平台 - 项目记忆

## 基本信息
- **项目名称**: 大理大学第一附属医院档案管理平台
- **路径**: `E:\工作文档\档案室\02_归档文件目录与总库\档案总库\📁📁📁📂📁📁📁📂\archive-platform\`
- **技术栈**: Flask 3.1 + SQLAlchemy 2 + SQLite + Bootstrap 5 + jQuery + DataTables + Chart.js + APScheduler + Scrapling
- **Python**: C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe
- **端口**: 5100
- **启动**: `python run.py`

## 关键架构决策
1. auth_bp 使用 `/auth` url_prefix（登录页: `/auth/login`）
2. mobile_bp 使用 `/m` url_prefix（移动端免登录独立访问）
3. Archives 表含电子版字段(electronic_path/electronic_size/electronic_location)和区块链字段(bc_hash/bc_md5/bc_tx_id/bc_timestamp)
4. Borrows 表含审批工作流(approver_id FK/approve_time/approve_comment/access_code)
5. 数据导入策略：增量导入，按档号+类别联合去重，1000条批量commit
6. Excel解析：只解析"档案目录"sheet（兼容尾部空格），使用iter_rows(values_only=True)高效读取

## 默认账号
- admin / admin123 (管理员)
- editor / editor123 (编辑者)
- viewer / viewer123 (浏览者)

## 数据库状态 (2026-06-18)
- 文书档案: 18,133条
- 设备档案: 1,940条
- 科研档案: 101条
- 基建档案: 86条
- **合计: 20,260条**（全部已计算SHA-256+MD5哈希）

## 已完成功能
- [x] 项目骨架 + 数据库模型 + 蓝图路由
- [x] 用户认证（登录/登出/角色权限）
- [x] 档案总库列表（DataTables服务端分页+筛选）
- [x] 档案详情页（含电子版/区块链/关联记录）
- [x] 档案编辑页
- [x] Excel数据导入（解析+预览+去重）
- [x] 移动端借阅登记页（免登录）
- [x] 移动端我的借阅页
- [x] 借阅管理（完整审批流程：待审批/通过/拒绝/归还/逾期/访问码）
- [x] 移交管理（移交登记/列表/状态更新/详情/**附件上传下载**）
- [x] 销毁鉴定（到期预警/批量鉴定/鉴定记录）
- [x] 法规制度管理（8条内置法规/增删改查/分类筛选）
- [x] 系统管理（用户管理/权限/操作日志）
- [x] 全文检索（多字段LIKE+关键词高亮+分页）
- [ ] APScheduler定时任务（待实现）

## 关键接口规律（2026-06-22 完善各模块后）
- 所有模块均采用 `/模块/api/xxx` RESTful 路由
- 模板文件均通过 PowerShell WriteAllText 写入（避免 EBUSY 锁定问题）
- DataTables 服务端分页统一参数：draw/start/length/search[value]
- regulations/list.html 写入需用 PowerShell（文件系统锁定）
- catalog/routes.py 中禁止用中文引号（"..."），会导致 SyntaxError，应改用【】或英文引号

## 档案总库新增功能（2026-06-22）
- 批量修改：勾选框+浮动操作栏+批量修改Modal，`/catalog/api/batch-update` POST
- 导出数据：`/catalog/export`，按筛选条件导出20字段Excel（openpyxl美化）
- 导出模板：`/catalog/export-template`，含说明行+示例行+填写说明Sheet

## 系统管理备份功能（2026-06-22）
- 新增数据备份标签页：`/admin/api/backup/info|list|create|download|delete`
- 备份目录：项目根/backups/（自动创建）
- 使用 shutil.copy2 复制 SQLite，文件名含时间戳
- Toast 通知（非 alert）

## 移交管理附件功能（2026-06-24）
- 新模型 TransferAttachment（transfer_attachments 表）：原始名/存储名/大小/MIME/上传人/时间
- 文件存储：`app/static/uploads/transfer/`，UUID命名防冲突，20MB限制，白名单扩展名
- 接口：`/transfer/api/<tid>/attachments/upload|list`，`/transfer/api/attachments/<aid>/download|delete`
- 删除移交记录时自动级联删除磁盘文件
- 前端：新建Modal嵌入拖拽上传区（先保存→自动逐个上传）；列表附件数badge；独立附件管理Modal（拖拽上传+实时进度+下载+删除）

# 第一阶段架构

浏览器通过 Next.js App Router 页面访问独立 FastAPI 服务。FastAPI 使用 HttpOnly JWT Cookie
维护登录状态，对每个业务请求校验项目成员关系。SQLAlchemy 负责 SQLite 持久化，Alembic 管理结构迁移。

现场记录是证据主实体，原始描述、记录人、UTC 时间、项目、三级位置和 GPS 状态随记录保存。
照片文件保存在本地上传目录，媒体表保存格式、大小、系统文件名和相对路径。待办可通过
`source_record_id` 指向来源现场记录；删除记录时数据库将该引用设为空，避免伪造或丢失待办事实。


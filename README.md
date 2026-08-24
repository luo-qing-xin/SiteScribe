# 工地小秘 · 比赛 MVP 第一阶段

面向施工员和安全员的移动端优先现场工作助手。本阶段提供真实登录、项目、现场记录、GPS、照片和基础待办，不包含任何 AI、语音识别或自动事实生成能力。

## 目录结构

```text
SiteScribe/
├── frontend/        # Next.js App Router、TypeScript、Tailwind、shadcn 风格基础组件
├── backend/         # FastAPI、SQLAlchemy、Alembic、SQLite、本地上传
├── docs/            # 架构说明
├── AGENTS.md
├── Makefile
└── .env.example
```

## 环境要求

- Node.js 20+（包含 npm/npx）
- Python 3.12+
- uv

前端仍使用仓库锁定的 pnpm 11。若系统没有全局安装 pnpm，Makefile 会自动通过
`npx --yes pnpm@11.19.0` 启动固定版本，无需手工全局安装。当前项目使用 Node.js 24、
pnpm 11 和 uv 管理的 Python 3.12 环境。

## 从干净环境启动

```bash
cp .env.example .env
make install
make init
```

首次通过 npx 启动 pnpm 时需要访问 npm 包仓库。如果希望提前全局安装，也可运行：

```bash
npm install --global pnpm@11.19.0
```

然后打开两个终端：

```bash
make dev-backend
make dev-frontend
```

访问 <http://localhost:3000>。API 文档位于 <http://localhost:8000/docs>。SQLite 数据库默认位于 `backend/data/site_secretary.db`，上传文件位于 `backend/data/uploads/`。

后端命令由 Makefile 在 `backend/` 中执行，因此 `.env.example` 的数据库和上传目录使用相对于该目录的路径；不创建 `.env` 时内置开发默认值也可直接工作。

## 演示账号

所有账号密码均为 `demo123`：

| 用户名 | 姓名 | 身份 | 单位/部门 |
| --- | --- | --- | --- |
| `zhangwei` | 张伟 | 安全员 | XX建设集团 / 安全部 |
| `wangqiang` | 王强 | 施工员 | XX建设集团 / 工程部 |
| `lijianguo` | 李建国 | 班组长 | XX劳务公司 / 钢筋班组 |

数据库只保存 Argon2 密码哈希。种子命令可重复运行，不会重复写入项目、成员、位置或演示业务数据：

```bash
make seed
```

## 数据库迁移

```bash
cd backend
uv run alembic upgrade head
uv run alembic current
```

新增模型字段后使用 `uv run alembic revision --autogenerate -m "说明"` 创建迁移，并检查生成内容。

## 质量检查

```bash
make lint          # Ruff + ESLint
make typecheck     # TypeScript strict
make test-backend  # pytest API 测试
make build         # Next.js 生产构建
make check         # 上述静态检查、后端测试与构建
make test-e2e      # 安装 Chromium 并运行 Playwright 核心流程
```

Playwright 会启动（或复用）前后端，模拟 GPS 成功及权限拒绝，不依赖真实坐标。核心测试覆盖登录、新建 3号楼/6层/西侧记录、照片上传、详情、关联待办及待办中心可见性。

## API 与安全边界

- JWT 仅放在 HttpOnly、SameSite=Lax Cookie 中，生产环境应设置强 `JWT_SECRET` 并启用 `COOKIE_SECURE=true`。
- 所有业务 API 校验登录与项目成员身份；待办责任人只能选择项目成员。
- 后端读取文件实际内容并验证 JPEG、PNG、WebP，单张上限 10MB，每条记录最多 9 张；服务端使用 UUID 文件名。
- GPS 失败保存明确状态与空坐标，不伪造位置；楼栋、楼层、区域只来自用户三级选择。
- 删除记录会同步删除媒体文件；关联待办保留并将来源引用设为空。

## 已知限制

- 第一阶段采用单机 SQLite 与本地文件目录，不适合多实例横向扩容；部署前应规划持久卷、备份和 HTTPS。
- 无复杂 RBAC、通知、整改复核闭环、AI、ASR、规范查询或导出。
- 项目日期统计以服务端 UTC 自然日为界；正式面向多时区项目时应增加项目时区配置。

## 下一阶段 ASR 扩展建议

保留现有 `POST /api/records` 作为用户确认后的事实写入入口。可新增独立的音频上传与转写草稿资源（例如 `/api/transcription-jobs`），异步返回转写文本，由用户确认或编辑后再填入 `description`。音频与转写结果应保存来源、时间和操作者，不应直接覆盖原始现场描述，也不应自动创建施工事实或待办。

# 工地小秘 / SiteScribe

面向施工员与安全员的移动端优先现场工作助手，将照片、语音、人员、时间和位置沉淀为可追溯的现场事实，并贯通日志生成、问题确认、整改执行与复核闭环。

> 项目当前为可运行的 MVP。AI 仅生成结构化草稿和基于项目资料的辅助建议，不能替代专业判断；所有正式记录与整改结论均需人工确认。

## 项目简介

施工现场的信息通常分散在口头沟通、照片、纸质日志和聊天记录中。工地小秘围绕 **Evidence First（证据优先）** 原则，将原始证据、AI 草稿、人工修订和最终确认结果分层保存，让每条现场事实都能追溯到来源，让每个问题都能落实到责任人并完成复核。

项目采用前后端分离架构，提供移动端友好的 Web 界面、项目级权限隔离、结构化现场记录、施工与安全日志、项目知识库检索，以及带照片凭证的整改工作流。

## 核心功能

- **多模态现场记录**：支持手工填写、浏览器录音、现场照片、施工位置和人员信息采集。
- **语音与 Event 结构化**：保留原始音频、ASR 原始转写和用户修订文本，从已确认输入生成可编辑的结构化 Event 草稿。
- **证据引用与人工确认**：字段引用必须指向当前记录中的文本或图片；缺少证据的内容不会被补写为事实。
- **施工与安全日志**：从已确认 Event 生成每日日志草稿，保留来源快照、人工补录、确认版本和刷新记录。
- **项目知识库辅助**：支持 PDF、DOCX、TXT 和 Markdown 资料，检索结果保留页码、段落或行区间等原文定位。
- **整改闭环**：问题经人工确认后创建整改任务，责任人提交说明和照片，由创建人或项目安全员复核。
- **项目级访问控制**：业务 API 同时校验登录状态和项目成员身份，避免仅依赖前端权限判断。

## Evidence First 工作流

```text
现场照片 / 浏览器录音 / 人工描述
                ↓
      原始证据与元数据留存
                ↓
       ASR 转写与用户修订
                ↓
      AI Event 草稿与证据引用
                ↓
          专业人员人工确认
                ↓
  正式现场事实 → 日志复用 → 整改建单
                ↓
       整改照片提交 → 人工复核闭环
```

系统不会自动认定重大事故隐患、事故等级或停工结论。项目知识库无合格命中时会返回“依据不足”，不会生成无来源建议。

## 技术架构与目录

| 模块 | 技术与职责 |
| --- | --- |
| 前端 | Next.js App Router、React、TypeScript、Tailwind CSS、Playwright |
| 后端 | FastAPI、Pydantic、SQLAlchemy、Alembic、pytest |
| 数据 | SQLite；时间统一以 UTC 保存，前端按本地时区展示 |
| 文件 | 原始音频、派生音频和照片保存在 `backend/data/uploads/`，数据库仅保存相对路径与元数据 |
| AI | Faster Whisper、本地 Mock、OpenAI-compatible Provider，可按用途独立配置 |

```text
SiteScribe/
├── frontend/             # Next.js 前端与 Playwright E2E 测试
├── backend/
│   ├── app/              # FastAPI 路由、服务、模型与 Provider
│   ├── alembic/          # 数据库迁移
│   ├── tests/            # 后端测试
│   └── data/             # 本地数据库、上传文件与知识资料
├── data/                 # Event Schema 与合成评估样例
├── docs/                 # 架构与证据边界说明
├── .env.example          # 配置示例
└── Makefile              # 安装、启动、迁移与质量检查入口
```

更详细的数据流和约束见 [架构与证据边界](./docs/architecture.md)。

## 快速体验

推荐先使用确定性的 Mock 演示环境。该环境不调用外部模型，也不会覆盖日常开发数据库。

### 环境要求

- Node.js 20+
- pnpm 11（未全局安装时，Makefile 会使用仓库锁定版本）
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- FFmpeg 与 FFprobe

macOS 可通过 Homebrew 安装音频依赖：

```bash
brew install ffmpeg
```

### 初始化演示环境

```bash
cp .env.example .env
make install-test
make demo-reset
```

`make demo-reset` 仅重置隔离的演示数据库 `backend/data/site_secretary_demo.db` 和演示图片目录，然后重新生成标准模拟数据。

分别在两个终端启动服务：

```bash
make demo-backend
```

```bash
make demo-frontend
```

- Web 应用：<http://localhost:3000>
- API 文档：<http://localhost:8000/docs>
- 演示账号：`zhangwei`、`wangqiang`、`lijianguo`
- 演示密码：`demo123`

演示数据和 Mock 输出仅用于功能验证，不代表真实施工记录或模型准确率。

## 常规开发启动

安装完整依赖并初始化默认数据库：

```bash
cp .env.example .env
make install
make init
```

分别启动前后端开发服务器：

```bash
make dev-backend
```

```bash
make dev-frontend
```

数据库迁移可单独执行：

```bash
make migrate
```

默认后端地址为 `http://127.0.0.1:8000`。需要连接其他后端时，在 `frontend/.env.local` 中设置 `BACKEND_URL`。

## 配置说明

完整配置项及安全占位值见 [.env.example](./.env.example)。请勿提交真实 API Key 或生产密钥。

| 配置 | 用途 | 本地确定性选项 |
| --- | --- | --- |
| `ASR_PROVIDER` | 语音识别 | `mock` |
| `EVENT_EXTRACTION_PROVIDER` | 语音记录的结构化草稿 | `mock` |
| `AI_PROVIDER` | 已有记录的多模态 Event 提取 | `mock` |
| `RAG_PROVIDER` | 基于项目资料的辅助建议 | `mock` |

真实 ASR 默认使用 Faster Whisper。模型会在第一次处理录音时下载并占用本地缓存；外部 Event Extraction 与 RAG Provider 均配置超时，并在后端执行结构与证据校验。

## 测试与质量保障

```bash
make lint          # Ruff + ESLint
make typecheck     # TypeScript 类型检查
make test-backend  # pytest
make build         # Next.js 生产构建
make test-e2e      # Playwright 核心交互测试
make check         # lint + typecheck + backend tests + build
```

E2E 测试使用隔离端口和 Mock Provider，不依赖外网、真实麦克风或 GPS，并包含 375px 移动端视口覆盖。

## 安全与事实边界

- 原始证据、Provider 原始输出、用户修订和最终确认结果分开保存，避免 AI 草稿覆盖事实来源。
- 所有业务读写均由后端验证登录状态、项目成员身份和项目数据归属。
- 所有时间由后端以 UTC 保存，前端仅在展示时转换到本地时区。
- 上传内容不信任文件扩展名或浏览器 MIME；音频先经 FFprobe 验证，再由 FFmpeg 标准化。
- 照片只写入 `backend/data/uploads/`，数据库仅保存相对路径和元数据。
- 文本引用必须存在于人工确认文本中，图片引用必须属于当前记录；人工位置不会被图片推断覆盖。
- 责任人、截止时间、安全分类和整改结论必须由项目成员确认。

## 当前限制

- 后台任务基于 FastAPI `BackgroundTasks`，适合单进程 MVP，不具备持久队列、分布式锁或多实例调度能力。
- SQLite 和本地文件目录要求单机持久卷与备份，不适合直接横向扩容。
- 扫描版 PDF 暂不支持 OCR；当前知识库使用本地检索，不包含向量数据库。
- 当前不包含企业自定义日志模板、服务端 DOCX/PDF 导出、外部通知、自动建单、自训练视觉模型或自动停工判断。
- Mock Provider 只用于确定性演示和测试，不能用于评价真实模型质量。

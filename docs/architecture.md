# 第二至四阶段架构与证据边界

浏览器通过 Next.js App Router 访问 FastAPI。JWT 只保存在 HttpOnly Cookie；每个业务 API 都由后端再次检查项目成员关系。SQLAlchemy 负责 SQLite 持久化，Alembic 迁移保留历史数据，媒体文件只写入 `backend/data/uploads/`。

## 语音数据流

`MediaFile(audio_original)` 保存不可覆盖的原始音频。FFprobe 根据真实内容验证音轨、格式和时长，FFmpeg 生成独立的 `audio_normalized` 16kHz 单声道 WAV。`TranscriptionJob` 保存真实 QUEUED/PROCESSING/SUCCEEDED/FAILED 状态、原始转写和独立的用户修订；普通更新 API 没有写入 `raw_transcript` 的能力。

第二阶段语音草稿抽取读取 `edited_transcript`（存在时）或 `raw_transcript`。Provider 输出先通过 Pydantic Schema，再保存到 `EventDraft.raw_payload`；用户修订保存到 `user_corrected_payload`。责任人候选匹配和项目时区相对日期解析在服务层执行，歧义保持空候选并提示人工处理。

最终确认 service 在单个事务中校验任务、草稿、项目、位置、成员和 Schema，创建 `SiteRecord(source_type=VOICE_AI)`，关联原始音频、派生音频与照片，并仅为用户明确勾选且补齐字段的问题创建 `Task`。`confirmed_record_id` 与 `job.record_id` 提供幂等保护。历史手工记录保持 `MANUAL`，AI 字段可空。

## Provider 与后台任务

`ASRProvider` 提供 FasterWhisper 与 Mock 实现；faster-whisper 模型按 model/device/compute type 缓存复用。`EventExtractionProvider` 提供 OpenAI-compatible 与 Mock 实现，外部请求带超时，非法结构最多修复一次。路由不包含模型调用细节。

MVP 使用 FastAPI `BackgroundTasks`。应用启动会把遗留 PROCESSING 标记为 `PROCESS_INTERRUPTED` 失败，允许用户重试。它不是多实例可靠队列：进程退出会中断执行，也没有跨实例任务认领。

## 第三阶段记录级 Event Extraction

`EventExtractionJob` 针对已存在的 `SiteRecord` 保存不可变输入快照和 QUEUED/RUNNING/SUCCEEDED/FAILED 状态。快照包括人工确认文本及哈希、照片 ID、人工位置、记录人和 UTC 时间。`SiteEvent` 分别保存 Schema 校验后的 `ai_output`、当前 `draft_data` 和人工确认后的 `confirmed_data`；`EventRevision` 记录创建、编辑、确认、拒绝前后的数据与操作者。

`EventExtractor` 有 OpenAI 多模态与 Mock 两种实现。图片只从当前记录的受控上传目录读取，EXIF 修正与压缩发生在内存，不修改原图；失败图片产生 warning，仍有文本时降级运行。Structured Outputs 后仍经过 Pydantic 二次校验，超时、限流、鉴权、非法 JSON、Schema 错误使用不同安全错误码。

证据校验逐条确认文本 quote、source ID、media file ID 和项目/记录归属。无效引用被删除并产生 warning；非空字段缺少有效引用时进入 `needs_confirmation_fields`。人工位置继续由原记录提供，Event 不复制或覆盖位置真值。已确认 Event 阻止静默重新抽取，确认/拒绝不会创建 `Task` 或文档。

## 明确不推断

缺失字段不补全；人数、班组、进度和责任人不得从常识推断；照片不能覆盖人工位置；AI 不认定事故等级、不输出停工指令、不把分类写成正式安全结论。所有时间后端按 UTC 保存，前端只做本地展示转换。

## 第四阶段日志版本与刷新

`DailyLogDocument` 用项目、项目本地日期和日志类型标识一个日志序列，`DailyLogVersion` 保存草稿或不可修改的已确认版本。自动内容和人工补录分开保存；`DailyLogSource` 固化每版引用的 Event、现场记录、Event 快照和证据快照，`DailyLogAudit` 保存创建、编辑、刷新和确认操作。

日志日期通过项目时区转换成 UTC 边界后查询，只聚合 `SiteEvent.status=CONFIRMED` 的记录。生成过程是确定性字段映射，不调用 LLM，也不将多条人数或进度汇总成新的事实。来源摘要变化时返回 stale 状态；刷新草稿只重建自动部分并保留人工字段，刷新已确认版本会创建下一版草稿。已作为日志来源的现场记录通过业务 API 禁止删除，避免证据链断裂。

安全问题使用 `event_id + issue_index` 作为稳定键。系统默认归类为 `UNCLASSIFIED`，确认安全日志前必须由项目成员明确选择 `GENERAL`、`MAJOR` 或 `NOT_HAZARD`；其中重大事故隐患始终是人工结论，不来自 AI。

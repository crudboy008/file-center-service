# CONTRACT-HTTP-001 Java 文件 HTTP API 契约

- 文档版本：V0.1.0
- 状态：`DRAFT_FOR_USER_REVIEW / NOT_APPROVED_FOR_IMPLEMENTATION`
- 日期：2026-09-03
- 需求来源：[SRS-001](../srs/SRS-001-文件管理系统需求规格.md)
- 内部实现设计：[LLD-001](../lld/LLD-001-文件管理模块详细设计.md)、[LLD-002](../lld/LLD-002-数据库与MinIO一致性设计.md)
- 可执行 OpenAPI：`NOT_IMPLEMENTED / NOT_RUN`

## 1. 契约边界

本文冻结调用方可观察的 HTTP 方法、路径、媒体类型、并发版本、主要成功语义、下载头和错误语义。PostgreSQL 表结构、MinIO 调用、补偿任务和事务时序不属于 HTTP 契约，由 LLD 管理。

当前没有 Java 代码和版本化 OpenAPI。本文是设计阶段契约，不能证明接口已经实现或运行。实现后必须以版本化 OpenAPI 固化字段级事实，并通过 `AC-FILE-014` 静态核对。

## 2. 全局约定

| 项目 | V0.1.0 契约 |
|---|---|
| Base Path | `/api/v1/files` |
| JSON | 普通请求和响应使用 JSON；上传/替换使用 `multipart/form-data`；下载返回字节流 |
| 标识 | `fileId` 为 32 位小写十六进制逻辑文件 ID；替换内容后保持不变 |
| 并发 | 修改、整文件替换、启停、失败恢复和删除使用 `expectedVersion`；过期版本返回 `409 FILE_VERSION_CONFLICT` |
| 时间 | JSON 时间使用带时区的 RFC 3339 字符串；设计样例使用 UTC `Z` |
| 分页 | 页码从 1 开始；文件列表排序固定为 `created_at DESC, file_id DESC`；默认只返回 `ACTIVE + ENABLED` |
| 请求关联 | 调用方可传入或服务生成 `request_id`；错误响应和日志必须能按同一值关联 |
| 内部信息 | 外部响应不得包含数据库连接信息、MinIO Endpoint/Bucket/Object Key/凭据、内部路径或堆栈 |
| 认证授权 | V0.1.0 未实现；只能在本地或受控隔离网络验证，不形成公网安全声明 |

分页默认值、最大页大小、文件大小上限和补偿参数仍是 SRS 第 15 节待决项。实现前必须通过配置基线冻结，本文不编造数值。

## 3. 接口索引

| 操作 ID | 方法与路径 | 功能说明 | 请求 | 已冻结成功语义 | 主要需求 |
|---|---|---|---|---|---|
| `FILE-UPLOAD` | `POST /api/v1/files` | 创建一个新的逻辑文件和首个内容版本；一次请求只上传一个文件 | multipart：`file` 必填，`displayName` 可选 | `201 Created`；文件记录与对象完成后返回 `ACTIVE` 文件视图 | `FR-FILE-001`～`003`、`015` |
| `FILE-LIST` | `GET /api/v1/files` | 分页查找文件概要，供文件管理页面展示和筛选 | `page`、`pageSize`、`name`、`lifecycleStatus`、`availabilityStatus`、`mediaType`、`createdFrom`、`createdTo` | `200 OK`；稳定分页，默认只返回 `ACTIVE + ENABLED` | `FR-FILE-004`、`012`、`016` |
| `FILE-DETAIL` | `GET /api/v1/files/{fileId}` | 查询单个文件的元数据、生命周期、可用状态和当前已提交内容事实；不返回文件字节 | 路径参数 `fileId` | `200 OK`；返回两个状态；`REPLACING` 的内容字段仍指向旧的已提交事实，不暴露候选对象 | `FR-FILE-005`、`012`、`016` |
| `FILE-DOWNLOAD` | `GET /api/v1/files/{fileId}/content` | 流式下载当前已提交的文件字节 | 路径参数 `fileId` | `200 OK` 字节流；仅 `ENABLED` 且生命周期为 `ACTIVE/REPLACING` 时下载当前已提交对象 | `FR-FILE-006`、`010`、`012`、`016` |
| `FILE-METADATA-PATCH` | `PATCH /api/v1/files/{fileId}` | 修改展示名和备注，不修改文件正文 | JSON：`displayName`、`remark`、`expectedVersion` | 更新可编辑元数据并递增版本；精确成功响应体/状态码待 OpenAPI 冻结 | `FR-FILE-007` |
| `FILE-CONTENT-REPLACE` | `PUT /api/v1/files/{fileId}/content` | 上传一份完整新文件，替换同一逻辑文件的当前正文 | multipart：完整 `file`、`expectedVersion` | 保持 `fileId` 和可用状态，使用新内容引用原子切换；精确成功响应体/状态码待 OpenAPI 冻结 | `FR-FILE-008`、`011`、`019` |
| `FILE-AVAILABILITY-PATCH` | `PATCH /api/v1/files/{fileId}/availability` | 启用或停用文件，控制默认列表、下载及未来 RAG 使用资格 | JSON：`targetStatus`、`reason`、`expectedVersion` | `200 OK`；仅 `ACTIVE` 可执行，状态与历史同事务提交 | `FR-FILE-016` |
| `FILE-RECOVERY-RETRY` | `POST /api/v1/files/{fileId}/actions/retry-recovery` | 为失败文件重新排队已有恢复任务，供后台重新核对并收敛状态 | JSON：`reason`、`expectedVersion` | `202 Accepted`；只重新排队已有恢复事实，不直接改变 `FAILED` | `FR-FILE-018` |
| `FILE-STATUS-HISTORY` | `GET /api/v1/files/{fileId}/status-history` | 分页查询生命周期和人工可用状态的变化记录 | `page`、`pageSize` | `200 OK`；按 `changed_at DESC, history_id DESC` 稳定分页 | `FR-FILE-017` |
| `FILE-DELETE` | `DELETE /api/v1/files/{fileId}?expectedVersion={version}` | 发起幂等业务删除，使文件立即不可下载并由工作流清理对象 | 路径参数和查询参数 | `204 No Content`；重复删除语义稳定，清理失败进入可重试状态 | `FR-FILE-009`、`011` |

“待 OpenAPI 冻结”表示当前设计没有足够依据确定该细节。实现者必须先回填契约并评审，不能自行选择后又把选择描述成原始需求。

### 3.1 接口功能详解

以下说明面向 HTTP 调用方，用于回答每个接口“做什么、会改变什么、什么状态可调用、明确不做什么”。内部事务和补偿时序仍以 LLD-001、LLD-002 为准。

#### 3.1.1 `POST /api/v1/files`：上传并创建文件

- **业务用途：** 创建一个全新的逻辑文件及其首个内容版本。适用于用户从本机选择文件后首次录入文件中心。
- **主要副作用：** PostgreSQL 建立文件记录、状态历史和恢复事实，MinIO 写入新的私有对象；全部成功后返回 `ACTIVE + ENABLED` 文件视图。
- **输入限制：** 一个 multipart 请求只接受一个必填 `file`，可附带 `displayName`；空文件、超限文件和不支持的类型被拒绝。
- **明确不做：** 不提供批量上传；同名上传会创建不同 `fileId` 和对象，不按文件名覆盖已有文件；不把原始文件名直接用作 Object Key。

#### 3.1.2 `GET /api/v1/files`：分页查询文件列表

- **业务用途：** 为文件管理页面提供概要列表，并按名称、双状态、媒体类型和创建时间筛选。
- **读取范围：** 读取 PostgreSQL 中的文件概要，按 `created_at DESC, file_id DESC` 稳定分页；未显式传状态条件时只返回 `ACTIVE + ENABLED`。
- **主要副作用：** 无，只读接口。
- **明确不做：** 不返回文件字节、MinIO Object Key、Bucket、Endpoint 或凭据；也不把全部结果一次性无分页返回。

#### 3.1.3 `GET /api/v1/files/{fileId}`：查询文件详情

- **业务用途：** 查看单个逻辑文件的元数据、生命周期、人工可用状态、并发版本和当前已提交内容事实。
- **状态规则：** 已明确支持查询 `ACTIVE` 和 `REPLACING`；`DISABLED` 文件仍可通过该受控接口查看。`REPLACING` 时内容字段继续指向旧的已提交对象；不存在或已删除返回 `404`。
- **主要副作用：** 无，只读接口。
- **明确不做：** 不返回文件正文，不暴露正在上传的候选对象，也不返回内部存储定位或凭据。

#### 3.1.4 `GET /api/v1/files/{fileId}/content`：下载文件正文

- **业务用途：** 将当前已提交文件从 MinIO 经 Java 服务流式返回给调用方。
- **状态规则：** 只允许 `availabilityStatus=ENABLED` 且生命周期为 `ACTIVE` 或 `REPLACING`；`REPLACING` 时下载旧的已提交对象。`DISABLED` 或其他生命周期返回 `FILE_STATE_CONFLICT`。
- **主要副作用：** 无业务数据修改，只读取 PostgreSQL 当前内容事实并打开 MinIO 对象流。
- **明确不做：** 不读取未提交候选对象，不把任意大小文件整体装入 JVM `byte[]`，不向调用方返回 MinIO 凭据或长期公开 URL。

#### 3.1.5 `PATCH /api/v1/files/{fileId}`：修改文件元数据

- **业务用途：** 修改文件展示名和备注，适用于文件内容不变的说明性维护。
- **状态规则：** 仅生命周期为 `ACTIVE` 时允许，`ENABLED` 和 `DISABLED` 均可维护；请求必须带当前 `expectedVersion`。
- **主要副作用：** 在 PostgreSQL 更新 `display_name/remark` 并递增并发版本；过期版本返回 `FILE_VERSION_CONFLICT`。
- **明确不做：** 不改变原始文件名、媒体类型、文件字节、SHA-256、ETag、对象引用、生命周期或可用状态。

#### 3.1.6 `PUT /api/v1/files/{fileId}/content`：完整替换文件正文

- **业务用途：** 用户在本机完成编辑后，上传一份完整新文件替换现有正文，同时保留同一个逻辑 `fileId`。
- **状态规则：** 目标生命周期必须是 `ACTIVE`，`ENABLED` 和 `DISABLED` 均可替换；请求必须带当前 `expectedVersion`。替换期间文件进入 `REPLACING`。
- **主要副作用：** 为新内容生成新的 `reference_id/object_key`，流式写入 MinIO，计算新内容事实，再通过 PostgreSQL 乐观锁原子切换当前引用；成功后清理旧对象，清理失败进入持久重试。
- **明确不做：** 不支持页、段落、单元格、文本片段或字节范围的在线增量编辑；不原地覆盖旧 Object Key；不改变 `displayName/remark/availabilityStatus`，原文件为 `DISABLED` 时替换后仍为 `DISABLED`。

#### 3.1.7 `PATCH /api/v1/files/{fileId}/availability`：启用或停用文件

- **业务用途：** 在不删除文件的前提下，控制它是否出现在默认列表、能否下载，以及未来是否可被 RAG 当作有效知识使用。
- **状态规则：** 只允许生命周期为 `ACTIVE` 的文件；请求必须包含 `ENABLED/DISABLED` 目标值、非空原因和当前 `expectedVersion`。
- **主要副作用：** PostgreSQL 在同一事务更新可用状态、递增版本并写入状态历史。目标值与当前值相同且版本匹配时返回当前视图，不新增历史、不递增版本。
- **明确不做：** 不删除 PostgreSQL 记录或 MinIO 对象，不修改生命周期和文件正文，也不允许调用方借此把文件直接改成任意生命周期。

#### 3.1.8 `POST /api/v1/files/{fileId}/actions/retry-recovery`：请求重试失败恢复

- **业务用途：** 对需要人工介入的失败文件，重新排队系统已经持久化的恢复任务。
- **状态规则：** 仅接受 `FAILED` 且存在可重试持久任务的文件；请求必须包含原因和当前 `expectedVersion`，否则返回状态或版本冲突。
- **主要副作用：** 在同一 PostgreSQL 事务把恢复任务重置为 `PENDING`、递增文件版本并记录 `FAILED → FAILED` 的请求历史，返回 `202 Accepted`。
- **明确不做：** 接口本身不直接把文件改为 `ACTIVE`；最终状态只能由 `FileReconcileService` 核对 PostgreSQL 与 MinIO 事实后提交。

#### 3.1.9 `GET /api/v1/files/{fileId}/status-history`：查询状态历史

- **业务用途：** 审计文件生命周期和人工可用状态如何变化，并辅助定位失败及人工操作原因。
- **读取范围：** 从 PostgreSQL 分页返回前值、后值、状态维度、原因、操作者、请求 ID、提交后版本和变更时间，排序固定为 `changed_at DESC, history_id DESC`。
- **主要副作用：** 无，只读接口。
- **明确不做：** 不改变文件状态，不返回文件正文、Object Key、Bucket、凭据或异常堆栈。

#### 3.1.10 `DELETE /api/v1/files/{fileId}`：幂等删除文件

- **业务用途：** 发起文件业务删除，使文件立即失去下载资格，并通过可恢复工作流清理 MinIO 对象。
- **状态规则：** 允许删除 `ACTIVE + ENABLED/DISABLED` 文件并校验 `expectedVersion`；对已经处于 `DELETING/DELETED` 的同一文件重复调用仍可返回 `204`。
- **主要副作用：** 生命周期由 `ACTIVE → DELETING → DELETED`，进入 `DELETING` 后立即不可下载；对象清理失败时持久重试。
- **明确不做：** 不把一次 MinIO 删除失败伪装成已彻底清理，也不物理删除 PostgreSQL 墓碑记录。

## 4. 已冻结的公共文件视图

上传成功样例已经确认以下外部字段：

| 字段 | 类型/格式 | 语义 |
|---|---|---|
| `fileId` | string，32 位小写十六进制 | 逻辑文件身份 |
| `originalName` | string | 上传时经路径清理后的原始文件名 |
| `displayName` | string | 可修改的展示名 |
| `mediaType` | string | 七类允许 MIME 之一 |
| `sizeBytes` | integer，`> 0` | 实际文件字节数 |
| `contentSha256` | string，64 位小写十六进制 | 实际上传字节的 SHA-256，不是 MinIO ETag |
| `lifecycleStatus` | enum | 系统控制的 `UPLOADING/ACTIVE/REPLACING/DELETING/DELETED/FAILED` |
| `availabilityStatus` | enum | 人工控制的 `ENABLED/DISABLED`；只有 `ACTIVE + ENABLED` 才有效可用 |
| `version` | integer | 对应内部 `row_version` 的并发版本 |
| `createdAt` | RFC 3339 date-time | 创建时间 |

详情响应是否增加 `remark/updatedAt`，分页响应的容器字段名称，以及元数据 PATCH/内容 PUT 的精确成功响应体，当前设计尚未冻结。这些项目必须在实现 OpenAPI 前收口，并同步本文件和需求追踪矩阵。

启停成功和恢复请求接受后的最小状态视图冻结为：`fileId`、`lifecycleStatus`、`availabilityStatus`、`version`、`updatedAt`。状态历史项至少包含 `historyId`、`dimension`（`LIFECYCLE/AVAILABILITY`）、`fromStatus`、`toStatus`、`reason`、`actorId`、`requestId`、`fileVersion`、`changedAt`；创建时 `fromStatus` 可以省略，其他字段不得用存储凭据或对象定位填充。

## 5. 上传与替换规则

- 拒绝零字节文件，返回 `422 FILE_EMPTY`。
- 校验扩展名与规范 MIME 映射；允许集合以 LLD-001 §4.2 为准。
- 超过配置上限返回 `413 FILE_TOO_LARGE`，不得产生 `ACTIVE` 记录或不可识别对象。
- 原始文件名只作为业务元数据；不得直接成为 Object Key。
- 上传和替换使用有界流；不得把任意大小文件整体聚合进 JVM `byte[]`。
- 正文不提供在线页/段落/单元格/字节增量编辑；正文变化只能向 PUT 接口上传完整新文件。
- 替换生成新的 `reference_id/object_key`，保留逻辑 `fileId` 和替换前的 `availabilityStatus`；`REPLACING` 且 `ENABLED` 时查询和下载仍使用旧的已提交对象。

### 5.1 可用状态与恢复请求

启停请求固定为：

```json
{
  "targetStatus": "DISABLED",
  "reason": "文件内容需要重新审核",
  "expectedVersion": 3
}
```

`targetStatus` 只允许 `ENABLED/DISABLED`，`reason` 为去除首尾空白后 1..500 字符且不得含控制字符，`expectedVersion` 必须为当前非负版本。仅生命周期为 `ACTIVE` 的文件可启停；实际状态变化必须与历史同事务提交并递增版本。目标值已经等于当前值且版本仍匹配时可作为无变化成功返回，不新增历史、不递增版本。

恢复请求固定为：

```json
{
  "reason": "恢复条件已满足",
  "expectedVersion": 4
}
```

`reason` 使用与启停相同的 1..500 字符规则。该接口只对 `FAILED` 且存在可重试持久任务的文件返回 `202`，在同一事务重新排队任务、记录请求历史并递增版本。生命周期在响应时仍为 `FAILED`；后续只能由 `FileReconcileService` 核对数据库和 MinIO 事实后收敛。不存在通用 `PATCH /status`，也不存在调用方直接指定 `FAILED → ACTIVE` 的合同。

## 6. 下载响应

成功下载至少返回：

| Header | 规则 |
|---|---|
| `Content-Type` | 当前内容的规范 `media_type` |
| `Content-Length` | 存储响应能够确认时等于 `size_bytes` |
| `Content-Disposition` | `attachment; filename*=UTF-8''<percent-encoded-name>`，不得发生 CR/LF 或响应头注入 |
| `ETag` | 使用系统可控内容标识，例如由 `content_sha256` 构造；不得直接暴露 MinIO ETag |

V0.1.0 由 Java 转发对象流，不向浏览器返回 MinIO 凭据或长期公开 URL。

## 7. 统一错误合同

所有非成功响应至少包含：

```json
{
  "error_code": "FILE_NOT_FOUND",
  "message": "可向调用方公开的错误说明",
  "request_id": "用于日志关联的请求标识",
  "timestamp": "2026-09-03T00:00:00Z"
}
```

| HTTP | `error_code` | 触发语义 |
|---:|---|---|
| 400 | `INVALID_REQUEST` | 请求字段、文件名或分页参数非法 |
| 404 | `FILE_NOT_FOUND` | 文件不存在、已删除或按当前边界不可见 |
| 409 | `FILE_STATE_CONFLICT` | 生命周期/可用状态不允许操作，或失败记录不存在可重试恢复事实 |
| 409 | `FILE_VERSION_CONFLICT` | `expectedVersion` 已过期 |
| 413 | `FILE_TOO_LARGE` | 超过配置上限 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | 类型不在策略内或扩展名/MIME 不一致 |
| 422 | `FILE_EMPTY` | 实际文件字节数为 0 |
| 503 | `FILE_CONTENT_UNAVAILABLE` | 元数据存在但对象不可取得 |
| 503 | `OBJECT_STORAGE_UNAVAILABLE` | MinIO 暂时不可用 |
| 503 | `DATABASE_UNAVAILABLE` | PostgreSQL 暂时不可用 |
| 500 | `INTERNAL_ERROR` | 未分类服务异常 |

错误响应不得包含 Java 堆栈、SQL、数据库连接串、MinIO 凭据、内部 Bucket/Object Key、本机绝对路径或文件正文。

## 8. 版本与兼容性

1. Base Path 的 `/v1` 是 HTTP 主版本边界。
2. 新增真正可选且旧调用方可忽略的响应字段，可以作为兼容变更；删除、重命名、改变类型或语义属于不兼容变更。
3. 错误码、分页语义、并发字段和状态含义属于契约，不得在实现中静默变化。
4. 实现生成 OpenAPI 后，字段级差异必须回到本契约评审；不能让文档和 OpenAPI 长期并存冲突。

## 9. 验收入口

需求与契约的验收映射以 [RTM-V0.1.0](../governance/RTM-V0.1.0.md) 为唯一矩阵。当前所有 HTTP 运行项仍为 `NOT_IMPLEMENTED / NOT_RUN`；Schema 静态通过不能替代 `AC-FILE-001`～`019`。

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

| 操作 ID | 方法与路径 | 请求 | 已冻结成功语义 | 主要需求 |
|---|---|---|---|---|
| `FILE-UPLOAD` | `POST /api/v1/files` | multipart：`file` 必填，`displayName` 可选 | `201 Created`；文件记录与对象完成后返回 `ACTIVE` 文件视图 | `FR-FILE-001`～`003`、`015` |
| `FILE-LIST` | `GET /api/v1/files` | `page`、`pageSize`、`name`、`lifecycleStatus`、`availabilityStatus`、`mediaType`、`createdFrom`、`createdTo` | `200 OK`；稳定分页，默认只返回 `ACTIVE + ENABLED` | `FR-FILE-004`、`012`、`016` |
| `FILE-DETAIL` | `GET /api/v1/files/{fileId}` | 路径参数 `fileId` | `200 OK`；返回两个状态；`REPLACING` 的内容字段仍指向旧的已提交事实，不暴露候选对象 | `FR-FILE-005`、`012`、`016` |
| `FILE-DOWNLOAD` | `GET /api/v1/files/{fileId}/content` | 路径参数 `fileId` | `200 OK` 字节流；仅 `ENABLED` 且生命周期为 `ACTIVE/REPLACING` 时下载当前已提交对象 | `FR-FILE-006`、`010`、`012`、`016` |
| `FILE-METADATA-PATCH` | `PATCH /api/v1/files/{fileId}` | JSON：`displayName`、`remark`、`expectedVersion` | 更新可编辑元数据并递增版本；精确成功响应体/状态码待 OpenAPI 冻结 | `FR-FILE-007` |
| `FILE-CONTENT-REPLACE` | `PUT /api/v1/files/{fileId}/content` | multipart：完整 `file`、`expectedVersion` | 保持 `fileId` 和可用状态，使用新内容引用原子切换；精确成功响应体/状态码待 OpenAPI 冻结 | `FR-FILE-008`、`011`、`019` |
| `FILE-AVAILABILITY-PATCH` | `PATCH /api/v1/files/{fileId}/availability` | JSON：`targetStatus`、`reason`、`expectedVersion` | `200 OK`；仅 `ACTIVE` 可执行，状态与历史同事务提交 | `FR-FILE-016` |
| `FILE-RECOVERY-RETRY` | `POST /api/v1/files/{fileId}/actions/retry-recovery` | JSON：`reason`、`expectedVersion` | `202 Accepted`；只重新排队已有恢复事实，不直接改变 `FAILED` | `FR-FILE-018` |
| `FILE-STATUS-HISTORY` | `GET /api/v1/files/{fileId}/status-history` | `page`、`pageSize` | `200 OK`；按 `changed_at DESC, history_id DESC` 稳定分页 | `FR-FILE-017` |
| `FILE-DELETE` | `DELETE /api/v1/files/{fileId}?expectedVersion={version}` | 路径参数和查询参数 | `204 No Content`；重复删除语义稳定，清理失败进入可重试状态 | `FR-FILE-009`、`011` |

“待 OpenAPI 冻结”表示当前设计没有足够依据确定该细节。实现者必须先回填契约并评审，不能自行选择后又把选择描述成原始需求。

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

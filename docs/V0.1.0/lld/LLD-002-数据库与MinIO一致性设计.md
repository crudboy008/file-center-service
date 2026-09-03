# LLD-002 数据库与 MinIO 一致性设计

- 文档版本：V0.1.0
- 状态：`DRAFT_FOR_USER_REVIEW / NOT_APPROVED_FOR_IMPLEMENTATION`
- 日期：2026-09-03
- 适用对象：Java 文件中心 PostgreSQL 元数据与 MinIO 原始文件

## 1. 设计结论与证据边界

PostgreSQL 本地事务不能把 MinIO 写入或删除纳入同一个原子提交。V0.1.0 使用“文件状态机 + 不可变对象键 + PostgreSQL 乐观锁 + 持久恢复任务 + 孤儿扫描”收敛部分成功，不引入 Seata，不声称两个资源强一致。[设计决定，依据：ADR-004 第 1-3 节]

ADR-004 第 4 节允许 LLD 选择显式创建/替换状态并补全崩溃恢复。本 LLD 具体选择先用 PostgreSQL 登记 `UPLOADING/REPLACING` 与候选 `reference_id`，再调用 MinIO，使进程退出后仍有确定恢复入口；它是对 ADR-004 概要时序的细化。若本 LLD 未获批准，实现不得据此开工。

本设计保证：

- 只有 `availability_status=ENABLED` 且生命周期为 `ACTIVE` 的文件，以及同样为 `ENABLED` 的 `REPLACING` 文件旧当前对象可下载；
- 首次上传、内容替换和删除在进程崩溃后都有可识别的恢复事实；
- 任何新内容都写新 Object Key，不覆盖当前对象；
- 删除与清理把“对象已不存在”视为幂等成功；
- 重试次数、退避和扫描窗口由配置及真实测试冻结，本文不编造数值。

当前只完成设计。Java 工程、PostgreSQL 表、MinIO Bucket、补偿 Worker 和故障注入测试均未创建或执行。

## 2. 文件状态机

| 状态 | 含义 | 可查询详情 | 可下载 | 可修改/替换 | 可删除 |
|---|---|---:|---:|---:|---:|
| `UPLOADING` | 首次上传已登记，候选对象尚未确认 | 管理视图 | 否 | 否 | 否 |
| `ACTIVE` | 当前引用与对象已确认提交 | 是 | 仅 `ENABLED` | 元数据、完整替换和启停；`ENABLED/DISABLED` 均可维护 | 是 |
| `REPLACING` | 新候选对象准备中，旧当前对象仍有效 | 是 | 仅 `ENABLED`，读取旧当前对象 | 否 | 否 |
| `DELETING` | 已接受删除，当前对象清理中 | 管理视图 | 否 | 否 | 重复删除幂等 |
| `DELETED` | 删除完成，对象应不存在 | 管理视图 | 否 | 否 | 重复删除幂等 |
| `FAILED` | 创建、替换或删除清理已达到不能自动安全收口的失败条件 | 管理视图 | 否 | 否 | 仅受控清理 |

默认业务列表只返回 `ACTIVE + ENABLED`。`UPLOADING/REPLACING/DELETING/FAILED` 是真实恢复状态，不能在 API 或日志中伪装为完成。生命周期由系统工作流控制，不存在调用方任意赋值接口。

```mermaid
stateDiagram-v2
    [*] --> UPLOADING
    UPLOADING --> ACTIVE: 候选对象与内容事实确认
    UPLOADING --> FAILED: 首次上传确定失败
    ACTIVE --> REPLACING: 登记新候选对象
    REPLACING --> ACTIVE: 原子切换到新引用
    REPLACING --> ACTIVE: 替换失败并保留旧引用
    REPLACING --> FAILED: 旧引用也已不可用
    ACTIVE --> DELETING
    DELETING --> DELETING: 临时失败或结果不确定，等待重试
    DELETING --> DELETED: 对象已不存在
    DELETING --> FAILED: 重试耗尽或身份冲突，转人工处理
```

### 2.1 独立可用状态

`availability_status` 只取 `ENABLED/DISABLED`，新建成功默认 `ENABLED`。启停只在生命周期 `ACTIVE` 时允许，并以 `file_id + status=ACTIVE + row_version=expectedVersion` 做 CAS。`DISABLED` 只暂停普通读取与未来 RAG 可用性，不删除对象，不阻止元数据维护、完整内容替换、重新启用或删除；替换必须保留该值。

生命周期或可用状态每次实际变化，都必须与 `file_status_history` 在同一个 PostgreSQL 本地事务提交。历史包含维度、前后值、原因、操作者、`request_id`、`file_workflow_id`、提交后的 `row_version` 和数据库时间。任一步失败则整个本地事务回滚。

## 3. 一致性不变量

| 编号 | 不变量 |
|---|---|
| INV-01 | `file_id` 表示逻辑文件，创建后不变 |
| INV-02 | `reference_id` 表示一份不可变内容版本；`object_key=reference_id` |
| INV-03 | 同一 `reference_id` 只能属于一个文件的一次内容版本 |
| INV-04 | `ACTIVE/REPLACING/DELETING` 的当前引用必须具有正数 `size_bytes` 和 64 位小写 `content_sha256` |
| INV-05 | 新建或替换永远生成新 `reference_id`，禁止原地覆盖 |
| INV-06 | ETag 单独保存，不得冒充 SHA-256 |
| INV-07 | `REPLACING` 期间当前引用不变；仅 `availability_status=ENABLED` 时下载旧对象，`DISABLED` 时拒绝；绝不读取候选对象 |
| INV-08 | `DELETED` 对应的当前对象必须不可读取；数据库墓碑保留 |
| INV-09 | MinIO 用户元数据至少有 `file_name` 和 `media_type` |
| INV-10 | 所有存储任务提交结果时必须验证数据库状态、目标引用、乐观版本和 Worker 租约仍匹配 |
| INV-11 | 有效可用当且仅当 `status=ACTIVE and availability_status=ENABLED`；其他组合不能普通下载或供 RAG 作为可用知识 |
| INV-12 | 内容替换不得改变 `file_id` 或 `availability_status`；新旧 `reference_id` 必须不同 |
| INV-13 | 每次生命周期/可用状态实际变化与对应历史同一 PostgreSQL 事务提交，历史的 `file_version` 等于提交后的 `row_version` |
| INV-14 | 失败恢复接口只重排已有持久任务；只有恢复 Worker 核对对象与数据库事实后才能提交新生命周期 |

INV-09 适配当前 Python RAG MinIO Adapter。源码依据：`E:\mytest\szrcb_card_rag\card-rag-service\src\card_rag_service\adapters\files\minio.py` 第 65-83、92-139 行。

## 4. 存储身份与元数据

### 4.1 Bucket

Bucket 名由 `file.storage.bucket` 注入。未来联调时必须与 Python `CARD_RAG_MINIO_BUCKET` 指向同一 Bucket，因为当前 `file_ref` 不携带 Bucket。RAG 当前本地默认值为 `card-rag-doc-test`，该值只是本地快照，不是生产名称。[已确认，RAG `config.py` 第 35-40 行]

### 4.2 Object Key

```text
file_id      = 逻辑文件 ID，32 位小写十六进制
reference_id = 内容版本 ID，32 位小写十六进制
object_key   = reference_id
```

对象键不得使用原始文件名或 `files/{yyyy}/{MM}/...` 目录形式。当前 Python 本地 Adapter 将 `reference_id` 直接作为对象键，并拒绝 `/`、`\`、`.`、`..`。源码依据：RAG `adapters/files/minio.py` 第 9-11、44-55 行。

### 4.3 用户元数据

| 键 | 值 | 必要性 |
|---|---|---|
| `file_name` | 当前候选对象的原始文件名 | Python Adapter 必需 |
| `media_type` | 规范 MIME | Python Adapter 必需 |
| `file_id` | 逻辑文件 ID | Java 孤儿核对 |
| `reference_id` | 内容版本 ID | Java 孤儿核对 |
| `file_workflow_id` | 本次创建/替换的 Java 内部文件流程 ID | 故障关联 |
| `upload_started_at` | UTC RFC 3339 时间 | 安全窗口判断 |

同时设置对象 `Content-Type=media_type`。Python 当前代码只依赖前两项；后四项属于 Java 补偿设计，不能表述为 RAG 既有要求。

中文 `file_name` 经 Java SDK、MinIO Server、Python SDK 后能否原样读取尚未验证，必须纳入真实组合测试。

## 5. 持久恢复任务

### 5.1 `storage_reconcile_task`

| 字段 | 建议类型 | 说明 |
|---|---|---|
| `task_id` | `char(32)` | 主键 |
| `file_id` | `char(32)` | 逻辑文件 ID |
| `action` | `varchar(32)` | `VERIFY_UPLOAD`、`VERIFY_REPLACEMENT`、`DELETE_OBJECT` |
| `target_reference_id` | `char(32)` | 要验证或删除的对象引用 |
| `source_reference_id` | `char(32)` nullable | 替换前旧引用快照 |
| `expected_file_version` | `bigint` | 创建任务时的文件乐观版本 |
| `task_status` | `varchar(16)` | `PENDING`、`RUNNING`、`SUCCEEDED`、`MANUAL_REVIEW` |
| `attempt_count` | `integer` | 实际尝试次数，从 0 开始 |
| `next_attempt_at` | `timestamptz` | 下一次可领取时间 |
| `lease_owner` | `varchar(128)` nullable | Worker 身份 |
| `lease_expires_at` | `timestamptz` nullable | Worker 租约截止时间 |
| `last_error_code` | `varchar(64)` nullable | 稳定错误码 |
| `created_at/updated_at` | `timestamptz` | 审计时间 |

约束：

- 同一 `target_reference_id + action` 最多一条未终结任务；
- `RUNNING` 必须有 `lease_owner/lease_expires_at`，其他状态必须为空；
- Worker 在短事务内用 `FOR UPDATE SKIP LOCKED` 领取并提交租约，再到事务外访问 MinIO；
- 迟到 Worker 必须因租约、文件状态、引用或版本不匹配而拒绝提交。

### 5.2 孤儿扫描

有些故障发生在对象已经写入、但数据库无法登记恢复任务时，因此只靠任务表不够。孤儿扫描必须：

1. 只扫描本应用独占的私有 Bucket；
2. 只有 PostgreSQL 可读取时才做删除判断；
3. 读取对象的 `reference_id/upload_started_at`；
4. 同时检查 `file_record` 当前引用和所有未终结任务的目标/源引用；
5. 只把超过 `orphan-safe-age` 且无任何引用的对象列为候选；
6. 先写幂等清理事实，再删除对象；
7. 删除成功或 `NoSuchKey` 后终结清理事实。

扫描周期、安全窗口和批量大小无当前运行数据，必须配置化并在测试中记录，本文不写假数字。

## 6. 首次上传

```mermaid
sequenceDiagram
    participant C as Client
    participant J as Java File Service
    participant D as PostgreSQL
    participant M as MinIO
    C->>J: POST multipart
    J->>D: TX1 insert UPLOADING + VERIFY_UPLOAD task
    D-->>J: commit(file_id, candidate reference_id, version)
    J->>M: PutObject(candidate), stream + SHA-256
    M-->>J: success / failure / uncertain
    J->>D: TX2 write content facts, ACTIVE, task SUCCEEDED
    D-->>J: commit
    J-->>C: 201 Created
```

### 6.1 正常路径

1. 请求入口先拒绝已知空文件；若长度未知，则流式读取后的实际大小仍必须大于 0；
2. 生成 `file_id/reference_id/file_workflow_id`；
3. TX1 插入 `file_record(status=UPLOADING, availability_status=ENABLED, row_version=0)`、`VERIFY_UPLOAD` 任务和两条初始状态历史；
4. 使用有界缓冲流写 `object_key=reference_id`，同一读取过程计算字节数和 SHA-256；
5. 空流、非法类型或对象写入失败不得转为 `ACTIVE`；
6. TX2 条件检查 `UPLOADING + reference_id + row_version`，写入内容事实、转 `ACTIVE`、递增为 `row_version=1`，同时插入 `UPLOADING → ACTIVE` 生命周期历史；
7. 只有 TX2 提交成功才返回 `201`。

### 6.2 失败矩阵

| 失败点 | 数据库事实 | 对象事实 | 收敛动作 |
|---|---|---|---|
| TX1 失败 | 无文件记录 | 未调用 MinIO | 直接失败 |
| PutObject 明确失败且对象不存在 | `UPLOADING` | 不存在 | 转 `FAILED`，终结任务 |
| PutObject 返回超时 | `UPLOADING` | 未知 | 保持状态，由 `VERIFY_UPLOAD` HEAD/GET 核对 |
| 空流被写成空对象 | `UPLOADING` | 空对象可能存在 | 返回 `FILE_EMPTY`，删除候选并转 `FAILED` |
| PutObject 成功、TX2 失败 | `UPLOADING` | 候选存在 | Worker 从对象重新取得大小、元数据并流式复算 SHA-256，再完成 TX2 |
| 进程退出 | 最后一次已提交状态 | 未知 | 租约/宽限期后 Worker 接管 |
| 对象元数据非法 | `UPLOADING` | 不符合合同 | 删除候选并转 `FAILED`；删除不确定则继续任务 |

ETag 只用于对账辅助。恢复时需要内容哈希，必须对实际对象流重新计算 SHA-256。

## 7. 元数据修改

元数据修改仅更新 PostgreSQL 的 `display_name/remark`，不修改 MinIO `file_name`。`file_name` 是上传时原始文件名，`display_name` 是可变业务事实。

```sql
update file_record
   set display_name = :displayName,
       remark = :remark,
       row_version = row_version + 1
 where file_id = :fileId
   and status = 'ACTIVE'
   and row_version = :expectedVersion;
```

更新行数为 0 时重新查询，区分不存在、状态冲突和版本冲突；禁止静默覆盖。

### 7.1 可用状态变更

```sql
update file_record
   set availability_status = :targetStatus,
       updated_by = :actorId,
       updated_at = transaction_timestamp(),
       row_version = row_version + 1
 where file_id = :fileId
   and status = 'ACTIVE'
   and row_version = :expectedVersion
   and availability_status <> :targetStatus;
```

更新成功后必须在同一事务插入 `AVAILABILITY` 历史，其 `file_version` 使用更新后的版本。更新数为 0 时重新查询并严格区分不存在、生命周期冲突、版本冲突和“当前值已是目标值”。只有最后一种且版本匹配可以作为无变化成功；它不写历史、不递增版本。

## 8. 内容替换

```mermaid
sequenceDiagram
    participant C as Client
    participant J as Java File Service
    participant D as PostgreSQL
    participant M as MinIO
    C->>J: PUT content + expectedVersion
    J->>D: TX1 ACTIVE -> REPLACING<br/>保存 old ref + candidate ref + task
    D-->>J: commit(claimVersion)
    J->>M: PutObject(candidate), stream + SHA-256
    M-->>J: success / failure / uncertain
    J->>D: TX2 CAS current ref = candidate, ACTIVE<br/>创建 DELETE_OBJECT(old ref)
    D-->>J: commit
    J-->>C: 200 OK(new facts)
    J-->>M: async/best-effort delete old ref
```

规则：

1. TX1 必须匹配 `file_id + status=ACTIVE + expectedVersion`，保留 `availability_status`，转为 `REPLACING` 并递增 `row_version`，同时写 `ACTIVE → REPLACING` 生命周期历史；
2. TX1 同时保存旧引用快照、新候选 `reference_id` 和 `VERIFY_REPLACEMENT` 任务；
3. `REPLACING` 期间当前引用仍是旧引用；原可用状态为 `ENABLED` 时查询和下载继续读取旧对象，原状态为 `DISABLED` 时详情可查但下载仍拒绝；修改、再次替换和删除返回 `FILE_STATE_CONFLICT`；
4. 新内容写新 Object Key，空文件统一返回 `FILE_EMPTY`；
5. TX2 必须匹配 `REPLACING + candidate + claimVersion`；成功后原子切换 `reference_id/object_key/original_name/media_type/size/hash/etag`，保持原 `availability_status`，转回 `ACTIVE` 并写 `REPLACING → ACTIVE` 生命周期历史；
6. TX2 同一事务创建旧引用的 `DELETE_OBJECT` 任务，因此提交后即使进程退出也能清理旧对象；未来 MQ 进入范围时，同一 TX2 还必须插入包含新旧文档 ID 的不可变 `CONTENT_REPLACED` Outbox；V0.1.0 不建该表；
7. 候选失败时删除候选并恢复 `ACTIVE`，旧引用不变；
8. CAS 或数据库提交失败时不覆盖旧引用；候选对象立即尝试删除，失败则由任务或孤儿扫描清理；
9. 旧对象删除失败不回滚已经生效的新引用。

若在替换期间发现旧当前对象也已丢失或校验失败，不能无证据恢复 `ACTIVE`；转 `FAILED` 并进入人工处理。

## 9. 删除

```mermaid
sequenceDiagram
    participant C as Client
    participant J as Java File Service
    participant D as PostgreSQL
    participant M as MinIO
    C->>J: DELETE + expectedVersion
    J->>D: TX1 ACTIVE -> DELETING + history + DELETE_OBJECT task
    D-->>J: commit
    J->>M: RemoveObject(current reference)
    M-->>J: success / NoSuchKey / uncertain
    J->>D: TX2 DELETING -> DELETED + history, task SUCCEEDED
    D-->>J: commit
    J-->>C: 204 No Content
```

删除的 TX1/TX2 以及任何 `FAILED` 转换都必须把生命周期历史放在同一数据库事务。删除成功或 `NoSuchKey` 都可完成 TX2。超时或未知结果保持 `DELETING`，后台按同一引用重试。达到配置化重试阈值或出现任务/对象身份冲突时，文件以 CAS 转为 `FAILED`，对应任务转为 `MANUAL_REVIEW`；自动流程不得再宣称删除完成。`DELETING/DELETED` 上重复 DELETE 返回稳定 `204`，不创建第二条流程；`FAILED` 只能通过受控恢复接口重新排队，再由 Worker 依据事实收口。

Bucket 若启用版本控制，仅创建删除标记不代表历史字节物理清除。V0.1.0 部署必须记录版本控制状态；启用时需保存和清理精确 `version_id`，否则只能声称逻辑不可见，不能声称所有历史字节已物理删除。[设计边界]

## 10. Worker 的 ACK 式提交边界

Worker 每次执行：

1. 从数据库领取任务并提交租约；
2. 在事务外调用 MinIO；
3. 开启新事务，检查 `task_id/lease_owner/lease_expires_at`；
4. 同时检查文件状态、`target_reference_id/source_reference_id` 和 `expected_file_version`；
5. 更新文件与任务后提交；
6. 提交失败不报告动作完成，允许租约到期后重新执行。

临时故障回到 `PENDING` 并设置 `next_attempt_at`。达到配置化阈值或出现身份冲突时，任务进入 `MANUAL_REVIEW`；若该任务对应的文件工作流已不能自动安全收口，必须在同一提交边界按预期状态和版本把文件转为 `FAILED` 并写历史。保存稳定错误码、尝试次数和时间，不保存凭据、文件正文或未经脱敏的响应。

`POST /actions/retry-recovery` 只在一个短事务中锁定 `FAILED` 文件和对应 `MANUAL_REVIEW` 任务，检查 `expectedVersion`，把任务重置为 `PENDING`，递增文件版本并写带请求原因的 `FAILED → FAILED` 历史；它不调用 MinIO，也不直接改回 `ACTIVE`。之后 Worker 按上述 ACK 式边界核对事实并决定：旧/新内容可证明有效时恢复 `ACTIVE`，删除已完成时进入 `DELETED`，事实仍不足时保持或再次进入 `FAILED`。每次实际决定都与新历史同事务提交。

## 11. 与未来 RAG 生命周期和 MQ 原子边界的交界

V0.1.0 没有 RAG 运行依赖，因此替换后旧对象可按本设计清理。以后真实接入后，已经发送给 Python 的 `reference_id` 可能仍被在途任务读取；届时删除旧内容前必须检查对应 RAG ingestion delivery operation 是否已终结，或引入明确的引用租约/保留期。不能直接复用 V0.1.0 的即时旧对象清理规则并假设不会打断 RAG。[未来设计门禁]

`storage_reconcile_task` 只处理 Java 数据库与 MinIO，不是 MQ Outbox。V0.1.0 不创建 `rag_delivery_operation/event_outbox/result_inbox`，也不连接 RocketMQ。

`file_workflow_id` 是 Java 内部文件流程关联身份；涉及对象存储时可跨数据库 TX1、事务外 MinIO 操作和 TX2 复用。未来 `file_fact_changed.operation_id` 是单份不可变 MQ 事件身份；不同提交点产生不同 payload 时必须生成不同事件 ID。两者必须分别建模，不能直接共用唯一约束或幂等语义。

未来 MQ 进入范围时，必须在产生已提交文件事实的同一个 PostgreSQL 本地事务内同时写入 RAG delivery operation 和不可变 Outbox payload/hash：

| 文件提交点 | 同事务未来事件 |
|---|---|
| 首次上传 TX2：`UPLOADING → ACTIVE` | `CREATED` |
| 元数据更新事务 | `METADATA_UPDATED` |
| 可用状态事务 | `ENABLED` 或 `DISABLED` |
| 替换 TX2：原子切换新引用 | `CONTENT_REPLACED`，冻结新 `document_id` 与旧 `previous_document_id` |
| 删除 TX1：`ACTIVE → DELETING` | `DELETE_REQUESTED` |
| 删除 TX2：`DELETING → DELETED` | `DELETED` |
| 任一工作流提交 `FAILED` | `FAILED` |

Sender 只能在该事务提交后读取 Outbox 并发送。Outbox 必须保存完整 UTF-8 JSON、规范 payload hash、`operation_id/file_id/file_version/change_type`，重投时逐字复用已存负载；禁止重新读取后来版本的 `file_record` 拼装旧事件。PostgreSQL 与 MinIO 仍按 TX1/外部对象操作/TX2 补偿，不得把这条规则描述成跨 PostgreSQL、MinIO、RocketMQ 的单一 ACID 事务。

## 12. 验证清单

| 场景 | 期望 |
|---|---|
| 空文件创建/替换 | `FILE_EMPTY`；无可下载记录或候选对象最终清理 |
| 正常创建 | `UPLOADING -> ACTIVE`，字节、大小、SHA 一致 |
| 初始/后续状态历史 | 文件状态与历史同事务；历史版本等于提交后 `row_version` |
| PutObject 超时但实际成功 | API 不误报成功；任务核对后收敛 |
| PutObject 成功、TX2 失败 | Worker 重算对象 SHA 后完成或转人工处理 |
| 正常替换 | `ACTIVE -> REPLACING -> ACTIVE`，新引用生效，旧对象可清理 |
| 两个并发替换 | 只有一个通过 `expectedVersion`；失败者候选不残留 |
| 停用/启用 | 仅 `ACTIVE` 可操作；并发同版本最多一个成功；默认列表和下载行为随可用状态变化 |
| 停用文件替换 | 替换成功后仍为 `DISABLED`，逻辑 `file_id` 不变，新引用生效 |
| 候选上传失败 | `ENABLED` 时旧对象继续下载，状态恢复 `ACTIVE`；`DISABLED` 时仍不可下载 |
| 新引用已提交、旧删除失败 | 新内容可下载，旧对象由任务删除 |
| 正常/重复删除 | 最终 `DELETED`，对象不存在，重复调用稳定 |
| MinIO 删除超时 | 保持 `DELETING`，不可下载，恢复后收敛 |
| 两个 Worker 竞争 | 只有有效租约者能提交 |
| 受控失败恢复 | API 只重排持久任务；Worker 核对真实事实后才提交 `ACTIVE/DELETED/FAILED` |
| Future Outbox 静态边界 | 文档映射所有提交点；本版 Flyway/代码不存在 Outbox、MQ Producer/Consumer 或 Topic 初始化 |
| 孤儿扫描 | DB 不可用时不删除；安全窗口内不删除；有引用对象不删除 |
| 中文文件名 | Java 写入后可由 MinIO/Python SDK原样读取；未跑前标记 `NOT_RUN` |

以上均是实现验收门槛，不是本文已执行结果。

# RTM-V0.1.0 需求追踪与验收矩阵

- 文档版本：V0.1.0
- 状态：`DRAFT_FOR_USER_REVIEW / NOT_APPROVED_FOR_IMPLEMENTATION`
- 日期：2026-09-03
- 需求与验收权威来源：[SRS-001](../srs/SRS-001-文件管理系统需求规格.md)
- HTTP 契约：[CONTRACT-HTTP-001](../contracts/FILE-API-CONTRACT.md)
- RAG 契约：[LLD-003](../lld/LLD-003-RAG预留对接合同.md)及[机器可读 Schema](../lld/contracts/rag/RAG-CONTRACTS.md)

## 1. 验收规则

1. 本文件是 V0.1.0 唯一需求追踪矩阵和正式验收入口；SRS 不再复制矩阵表。
2. SRS 定义需求正文、`AC-*` 和证据等级；本矩阵只维护需求到设计、契约、验收检查和证据状态的关系。
3. `直接` 表示现有 `AC-*` 明确断言该需求；`直接+补充` 表示还必须执行第 2 节的 `VC-*`；`补充` 表示现有 SRS 没有单独 `AC-*`，必须由 `VC-*` 补足追踪。
4. 所有 `MUST` 行都达到要求后，才可以根据 SRS 第 14 节判断版本结果。`SHOULD` 未满足时必须记录，不自动伪装成通过。
5. 当前 Java 代码尚未实现，SRS 当前状态为 `NOT_RUN`；下面的“最低证据”是未来验收要求，不是已有结果。

### 1.1 状态词

| 状态 | 含义 |
|---|---|
| `DESIGN_MAPPED / NOT_RUN` | 已有设计和验收映射，尚无本版本运行证据 |
| `OPEN_BASELINE / NOT_RUN` | 仍依赖待冻结参数或字段合同 |
| `IMPLEMENTED / NOT_RUN` | 代码已存在，但没有当前对象执行证据 |
| `VERIFIED` | 当前冻结对象已取得规定等级的证据 |
| `BLOCKED` | 已执行或审查，但存在明确阻断条件 |
| `REMOVED` | 需求已移除，保留追溯和替代原因 |
| `STATIC_VERIFIED / RUNTIME_NOT_RUN` | 当前 Schema/样例或静态边界已核对；不表示 Java、MQ、Python 或跨服务运行通过 |

## 2. 补充核对项

`VC-*` 只补充验证方法，不新增产品需求，也不改变 SRS 的范围。

| 核对 ID | 核对内容 | 最低证据 |
|---|---|---|
| `VC-DB-001` | 检查 Flyway/真实 Schema 不含文件 BLOB；验证唯一约束、生命周期/可用状态约束、状态历史外键和对象引用约束生效 | E2 |
| `VC-CONFIG-001` | 检查数据库和 MinIO 运行值由 `card-service-app`/环境注入，凭据只来自环境；确认 `file-center-service` 没有独立整体 `application*.yml`，并对源码、配置样例、日志和响应做秘密扫描 | E1；启动行为需 E2 |
| `VC-CONFIG-002` | 读回文件/请求大小、分页上限、媒体类型、补偿周期、批量、重试和退避的实际配置 | E2 |
| `VC-PERF-001` | 同时检查上传和下载代码路径及运行测量，确认不存在任意大小整文件 `byte[]` 聚合 | E2 |
| `VC-PERF-002` | 超限上传必须在完成写入前返回 `413 FILE_TOO_LARGE`，且无 `ACTIVE` 记录或不可识别对象 | E2/E3 |
| `VC-SEC-001` | 读回 MinIO Bucket 非公开策略，确认 API 不返回长期公开 URL | E2 |
| `VC-SEC-002` | 记录服务监听边界和运行剖面，确认只在本地或受控隔离网络验证 | E1 |
| `VC-OBS-001` | 对成功、业务失败和基础设施失败请求，核对响应/日志的同一 `request_id` 及脱敏字段 | E2/E3 |
| `VC-OBS-002` | 分别探测 PostgreSQL 和 MinIO 健康状态，确认可区分且不回显凭据 | E2/E3 |
| `VC-OBS-003` | 核对补偿任务待处理、成功和失败指标；该项对应 SHOULD | E2 |
| `VC-ARCH-001` | 检查整体根是 Maven 聚合工程，只有 `card-service-app` 含 `main`、Spring Boot repackage、整体运行配置和全局 `ControllerAdvice`；`file-center-service` 是普通 JAR，只定义文件领域异常/错误码且不反向依赖启动宿主；再检查 Controller → Service → Mapper/DAO、MinIO SDK 隔离及 Job → `FileReconcileService` | E1 |
| `VC-BASE-001` | 核对 HLD 版本与整体根父 POM/BOM、Wrapper、整体 Compose、启动宿主配置、文件模块 Flyway 的实际锁定值和状态，确认没有在 `file-center-service` 重复建立整体基线 | E1/E2 |
| `VC-SCOPE-001` | 在不启动 Gateway、Nacos、RocketMQ、Python 和向量数据库时完成 Java 文件验收 | E2/E3 |

## 3. 功能需求

| 需求 ID | 级别 | 摘要 | 设计/契约 | 验收映射 | 覆盖 | 最低证据 | 当前状态 |
|---|---|---|---|---|---|---|---|
| `FR-FILE-001` | MUST | multipart 上传并创建记录与对象 | LLD-001 §5.1；HTTP §3 | `AC-FILE-001` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-002` | MUST | 稳定文件 ID，同名不覆盖 | LLD-001 §4、§5.1；LLD-002 §3 | `AC-FILE-002` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-003` | MUST | 上传流计算 SHA-256，ETag 分存 | LLD-001 §4、§5.1；HTTP §4 | `AC-FILE-001`、`006` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-004` | MUST | 条件分页与稳定排序 | LLD-001 §5.2；HTTP §3 | `AC-FILE-004` | 直接 | E2 | `OPEN_BASELINE / NOT_RUN` |
| `FR-FILE-005` | MUST | 文件详情查询 | LLD-001 §5.3；HTTP §3 | `AC-FILE-005` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-006` | MUST | 仅 ENABLED 的 ACTIVE/REPLACING 可流式下载 | LLD-001 §5.4；HTTP §6 | `AC-FILE-006`、`008` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-007` | MUST | 修改展示名/备注且不改内容 | LLD-001 §5.5；HTTP §3 | `AC-FILE-007` | 直接 | E2 | `OPEN_BASELINE / NOT_RUN` |
| `FR-FILE-008` | MUST | 新对象键替换与乐观切换 | LLD-001 §5.6；LLD-002 §8；HTTP §3 | `AC-FILE-008`、`009` | 直接 | E2/E3 | `OPEN_BASELINE / NOT_RUN` |
| `FR-FILE-009` | MUST | 幂等删除与失败重试 | LLD-001 §5.7；LLD-002 §9；HTTP §3 | `AC-FILE-010`、`011` | 直接 | E2/E3 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-010` | MUST | 文件名、路径和响应头防护 | LLD-001 §5.1、§5.4；HTTP §5、§6 | `AC-FILE-003`、`005` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-011` | MUST | PostgreSQL/MinIO 部分成功可恢复 | LLD-002 §5～§10 | `AC-FILE-008`、`011`、`012` | 直接 | E3 | `OPEN_BASELINE / NOT_RUN` |
| `FR-FILE-012` | MUST | 外部响应不暴露存储定位和凭据 | LLD-001 §5；HTTP §2、§7 | `AC-FILE-005`、`013` | 直接 | E2/E3 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-013` | MUST | 统一错误响应和稳定错误语义 | SRS §9；LLD-001 §8；HTTP §7 | `AC-FILE-005`、`009`、`013` | 直接 | E3 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-014` | MUST | OpenAPI 覆盖接口、字段和错误码 | HTTP §1、§3、§7 | `AC-FILE-014` | 直接 | E1 | `OPEN_BASELINE / NOT_RUN` |
| `FR-FILE-015` | MUST | 拒绝空文件且不留错误事实 | LLD-001 §5.1；HTTP §5、§7 | `AC-FILE-003` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-016` | MUST | 独立启停状态、原因和乐观锁 | LLD-001 §4.3、§5.8；LLD-002 §2.1、§7.1；HTTP §3、§5.1 | `AC-FILE-015`、`016` | 直接 | E2/E3 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-017` | MUST | 生命周期/可用状态历史分页 | LLD-001 §4.3、§5.10；HTTP §3、§4 | `AC-FILE-017` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-018` | MUST | 受控 FAILED 恢复且禁止任意状态赋值 | LLD-001 §5.9、§7；LLD-002 §10；HTTP §5.1 | `AC-FILE-018` | 直接 | E3 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-FILE-019` | MUST | 无在线正文编辑，只上传完整文件替换 | LLD-001 §5.6、§5.11；LLD-002 §8；HTTP §3、§5 | `AC-FILE-008`、`014`、`019` | 直接 | E2/E3 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-CFG-001` | MUST | DataSource 由启动宿主/环境注入，文件模块不维护独立运行配置 | HLD-002 §5；`VC-CONFIG-001` | `AC-FILE-013` + `VC-CONFIG-001` | 直接+补充 | E1/E3 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-CFG-002` | MUST | MinIO 运行值由启动宿主/环境注入且秘密不泄露 | HLD-002 §5；HTTP §2、§7 | `AC-FILE-013` + `VC-CONFIG-001` | 直接+补充 | E1/E3 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-CFG-003` | MUST | 文件专属上限和类型配置由模块定义、宿主供值 | LLD-001 §9；`VC-CONFIG-002` | `AC-FILE-003`、`004` + `VC-CONFIG-002`、`VC-PERF-002` | 直接+补充 | E2/E3 | `OPEN_BASELINE / NOT_RUN` |
| `FR-CFG-004` | MUST | 文件补偿配置由模块定义、宿主供值 | LLD-001 §9；LLD-002 §5、§10；SRS §15；`VC-CONFIG-002` | `AC-FILE-011`、`012` + `VC-CONFIG-002` | 直接+补充 | E3 | `OPEN_BASELINE / NOT_RUN` |

## 4. RAG 契约需求

| 需求 ID | 级别 | 摘要 | 设计/契约 | 验收映射 | 覆盖 | 最低证据 | 当前状态 |
|---|---|---|---|---|---|---|---|
| `FR-RAG-001` | MUST | Java → RAG 版本化请求 Schema | LLD-003 §4；intake Schema | `AC-RAG-001`、`004`、`005` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-002` | MUST | 文档/操作身份、file_ref、SHA 和访问字段 | LLD-003 §4、§8；intake Schema | `AC-RAG-001`、`004`、`005` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-003` | MUST | RAG → Java 接纳结果三分支 | LLD-003 §5；acceptance Schema | `AC-RAG-002`、`004`、`005` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-004` | MUST | 接纳分支字段存在/省略严格互斥 | LLD-003 §5；acceptance Schema | `AC-RAG-002`、`004`、`005` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-005` | MUST | RAG → Java 最终结果 Schema | LLD-003 §6；result Schema | `AC-RAG-003`、`004`、`005` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-006` | MUST | READY/FAILED 必填、省略和禁止字段 | LLD-003 §6；result Schema | `AC-RAG-003`、`004`、`005` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-007` | MUST | file_ref、MinIO 元数据和 SHA 规则 | LLD-003 §8；intake Schema | `AC-RAG-001`、`004`、`005` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-008` | MUST | 机器可校验正反样例 | RAG `examples/`、validator、manifest | `AC-RAG-001`～`004` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-009` | MUST | Topic/Tag/Key/Group/幂等/兼容规则且无运行依赖 | LLD-003 §3～§10、§12 | `AC-RAG-005`、`006` | 直接 | E0 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-RAG-010` | MUST | 本版仅静态校验，真实链路 NOT_RUN | SRS §10；LLD-003 §1、§13 | `AC-RAG-006` | 直接 | E0 | `DESIGN_MAPPED / NOT_RUN` |
| `FR-RAG-011` | MUST | 新增严格 file_fact_changed v1，不改 intake v2 | ADR-002 §2.1、§2.5；LLD-003 §12、§14；file fact Schema | `AC-RAG-007`、`008` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-012` | MUST | 按 file_id/file_version 排序、事件 ID/存储流程 ID 分离、规范 payload hash 与替换身份 | ADR-002 §2.5；LLD-003 §7、§14、§15 | `AC-RAG-007`、`009` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-013` | MUST | 严格分支、重复键和删除引用规则 | LLD-003 §11、§14；file fact Schema/反例 | `AC-RAG-007`、`008` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `FR-RAG-014` | MUST | 未来文件事实与不可变 Outbox 同事务，本版仅合同 | ADR-002 §2.6；ADR-004 §14；LLD-002 §11；LLD-003 §9、§16 | `AC-RAG-010` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |

## 5. 非功能需求

| 需求 ID | 级别 | 摘要 | 设计/契约 | 验收映射 | 覆盖 | 最低证据 | 当前状态 |
|---|---|---|---|---|---|---|---|
| `NFR-DATA-001` | MUST | PostgreSQL 不保存文件 BLOB | LLD-001 §4；LLD-002 §3 | `AC-FILE-001` + `VC-DB-001` | 直接+补充 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-DATA-002` | MUST | 对象引用唯一，同名对象隔离 | LLD-001 §4；LLD-002 §3 | `AC-FILE-002` + `VC-DB-001` | 直接+补充 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-DATA-003` | MUST | 实际字节 SHA，ETag 不冒充 | LLD-001 §4、§5.1 | `AC-FILE-001`、`006` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-DATA-004` | MUST | 创建/替换/删除有补偿和重试状态 | LLD-002 §5～§10 | `AC-FILE-008`、`011`、`012` | 直接 | E3 | `OPEN_BASELINE / NOT_RUN` |
| `NFR-DATA-005` | MUST | row_version 防止并发丢失更新 | LLD-001 §4、§5.5、§5.6 | `AC-FILE-007`、`009` | 直接 | E3 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-DATA-006` | MUST | 双状态变化与历史同 PostgreSQL 事务 | LLD-001 §4.3、§5.8、§7；LLD-002 §2.1、§7.1、§10 | `AC-FILE-015`、`017`、`018` + `VC-DB-001` | 直接+补充 | E2/E3 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-PERF-001` | MUST | 上传下载流式 I/O | LLD-001 §5.1、§5.4 | `AC-FILE-006` + `VC-PERF-001` | 直接+补充 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-PERF-002` | MUST | 分页且限制最大页大小 | LLD-001 §5.2 | `AC-FILE-004` + `VC-CONFIG-002` | 直接+补充 | E2 | `OPEN_BASELINE / NOT_RUN` |
| `NFR-PERF-003` | MUST | 写入完成前拒绝超限且不留残余 | HTTP §5、§7 | `AC-FILE-012` + `VC-PERF-002` | 直接+补充 | E3 | `OPEN_BASELINE / NOT_RUN` |
| `NFR-PERF-004` | SHOULD | 记录文件、堆、时延和峰值内存 | HLD-002 §8；`VC-PERF-001` | `AC-FILE-006` + `VC-PERF-001` | 直接+补充 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-SEC-001` | MUST | 私有 Bucket 且无长期公开 URL | HLD-002 §4、§7；HTTP §6 | `AC-FILE-005` + `VC-SEC-001` | 直接+补充 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-SEC-002` | MUST | 凭据外部注入且不泄露 | HLD-002 §5、§8；HTTP §7 | `AC-FILE-013` + `VC-CONFIG-001` | 直接+补充 | E1/E3 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-SEC-003` | MUST | Object Key 与文件名隔离并防注入 | LLD-001 §4、§5.1、§5.4 | `AC-FILE-002`、`003`、`005` | 直接 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-SEC-004` | MUST | 错误不泄露内部信息 | SRS §9；HTTP §7 | `AC-FILE-013` | 直接 | E3 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-SEC-005` | MUST | 无认证时仅限本地/隔离网络 | HLD-002 §4；HTTP §2 | `VC-SEC-002` | 补充 | E1 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-OBS-001` | MUST | request_id 关联响应和日志 | SRS §9；HTTP §2、§7 | `AC-FILE-013` + `VC-OBS-001` | 直接+补充 | E3 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-OBS-002` | MUST | 文件操作和补偿记录稳定诊断字段 | HLD-002 §8；LLD-002 §5、§10 | `AC-FILE-008`、`010`～`013` + `VC-OBS-001` | 直接+补充 | E3 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-OBS-003` | MUST | PostgreSQL/MinIO 健康状态可区分 | HLD-002 §6；`VC-OBS-002` | `AC-FILE-013` + `VC-OBS-002` | 直接+补充 | E3 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-OBS-004` | SHOULD | 补偿任务暴露可测量指标 | `VC-OBS-003` | `VC-OBS-003` | 补充 | E2 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-MAIN-001` | MUST | 多模块单 JVM、唯一启动宿主、全局异常映射及文件模块三层边界 | HLD-001 §4.1；ADR-001 §2；LLD-001 §3、§6 | `VC-ARCH-001` | 补充 | E1 | `DESIGN_MAPPED / NOT_RUN` |
| `NFR-MAIN-002` | MUST | 整体根统一版本/构建/编排，宿主统一运行配置 | HLD-001 §7、§8；HLD-002 §5 | `VC-BASE-001` | 补充 | E1/E2 | `OPEN_BASELINE / NOT_RUN` |
| `NFR-MAIN-003` | MUST | RAG Schema 显式版本并拒绝未知版本、重复键和额外字段 | LLD-003 §4～§6、§11、§12、§14；RAG Schema | `AC-RAG-001`～`004`、`007`、`008` | 直接 | E1 | `STATIC_VERIFIED / RUNTIME_NOT_RUN` |
| `NFR-MAIN-004` | MUST | Java 验收不依赖后续组件 | HLD-002 §4；`VC-SCOPE-001` | `AC-FILE-001`～`019` + `VC-SCOPE-001` | 直接+补充 | E2/E3 | `DESIGN_MAPPED / NOT_RUN` |

## 6. 当前汇总

- Java 文件功能：`NOT_IMPLEMENTED / NOT_RUN`。
- HTTP OpenAPI：`NOT_IMPLEMENTED / NOT_RUN`，且第 4 节列出的部分字段仍待冻结。
- RAG 静态合同：`STATIC_CONTRACT_VALIDATION=PASS`（4 份 Schema、14 个有效样例、22 个无效样例、SHA-256 清单）；Java/Python DTO 与运行链路仍为 `NOT_RUN`。
- Java/Python 真实联通：`OUT_OF_SCOPE / NOT_RUN`。
- V0.1.0 总体验收：`NOT_RUN`。

该汇总只复述当前证据状态，不得从文档完整性推导实现或运行 PASS。

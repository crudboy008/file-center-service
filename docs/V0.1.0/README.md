# Java 文件中心 V0.1.0 设计文档索引

- 文档版本：V0.1.0
- 状态：`DRAFT_FOR_USER_REVIEW / NOT_APPROVED_FOR_IMPLEMENTATION`
- 交付边界：本目录只包含设计与静态合同，不包含 Java 业务源码或运行证据
- 更新时间：2026-09-03

## 1. 本版范围

V0.1.0 的实现范围是 Java 文件管理：PostgreSQL 保存文件元数据、系统生命周期、人工可用状态、状态历史和补偿事实，MinIO 保存文件字节。内容包括上传、分页查询、详情、流式下载、元数据修改、上传完整文件到新 Object Key 后切换引用、启停、状态历史、受控失败恢复和幂等删除。正文不提供在线增量编辑。

Java 与 Python RAG 之间只冻结对接合同和固定样例，包括按逻辑 `file_id` 排序的 `file_fact_changed v1` 和未来 Transactional Outbox 原子规则。本版不创建或运行 RocketMQ Producer/Consumer、Outbox/Inbox、Java RAG 状态表、Topic/Group、Python RAG/Agent、Spring Cloud Gateway、Nacos 或 Sentinel，也不执行 Java 与 Python 的真实联通。

## 2. 推荐阅读顺序

1. 先读 SRS，确认要交付的行为、边界和验收条件。
2. 再读 HLD，确认系统边界、目标架构、部署剖面和技术版本基线。
3. 然后读 ADR，理解模块化单体、Controller/Service/Mapper 三层主链路、延迟接入 RAG、未来 Gateway 和 PostgreSQL/MinIO 一致性的决策理由。
4. 然后读 LLD，核对包依赖、状态机、存储时序和异常恢复。
5. 最后读契约与治理矩阵，核对外部行为、机器可读消息和逐需求验收入口。

## 3. 文档索引

### 3.1 SRS

- [SRS-001 文件管理系统需求规格](srs/SRS-001-文件管理系统需求规格.md)：功能范围、双状态、完整文件替换、非功能要求、RAG 静态合同和验收条件。

### 3.2 HLD

- [HLD-001 系统架构与技术版本基线](hld/HLD-001-系统架构与技术版本基线.md)：V0.1.0 运行边界、未来 Java/Python/Gateway 目标架构、组件职责和版本矩阵。
- [HLD-002 V0.1.0 部署与运行剖面](hld/HLD-002-V0.1.0部署与运行剖面.md)：`contract`、`file-integration` 和未来 `target-rag` 剖面分别能证明什么。

### 3.3 ADR

- [ADR-001 Java 文件中心采用模块化单体](adr/ADR-001-Java文件中心采用模块化单体.md)
- [ADR-002 V0.1.0 延迟接入 RAG 并冻结合同](adr/ADR-002-V0.1.0延迟接入RAG并冻结合同.md)
- [ADR-003 目标架构使用 Gateway 统一 Java 与 Python 入口](adr/ADR-003-目标架构使用Gateway统一Java与Python入口.md)
- [ADR-004 PostgreSQL 与 MinIO 一致性策略](adr/ADR-004-PostgreSQL与MinIO一致性策略.md)

### 3.4 LLD

- [LLD-001 文件管理模块详细设计](lld/LLD-001-文件管理模块详细设计.md)：Controller/Service/Mapper 包结构、双状态数据模型、状态 API、完整替换和错误映射。
- [LLD-002 数据库与 MinIO 一致性设计](lld/LLD-002-数据库与MinIO一致性设计.md)：上传、替换、状态历史、受控恢复、删除、补偿和对账时序。
- [LLD-003 RAG 预留对接合同](lld/LLD-003-RAG预留对接合同.md)：兼容入库请求、逻辑文件事实、接纳/最终结果、顺序幂等和未来 Outbox 原子边界。
- [RAG 机器可读合同说明](lld/contracts/rag/RAG-CONTRACTS.md)：JSON Schema、固定正反样例和静态校验入口。

### 3.5 Contracts

- [CONTRACT-HTTP-001 Java 文件 HTTP API 契约](contracts/FILE-API-CONTRACT.md)：文件接口、下载头、并发版本、错误语义和当前未冻结字段。

### 3.6 Governance

- [RTM-V0.1.0 需求追踪与验收矩阵](governance/RTM-V0.1.0.md)：本版唯一矩阵和正式验收入口，逐项覆盖功能与非功能需求。

## 4. 单一事实来源

| 事项 | 本目录的设计事实来源 | 实施后的可执行事实来源 |
|---|---|---|
| 本版范围与验收 | SRS-001 | 验收计划和同一运行对象的测试报告 |
| 系统边界与版本基线 | HLD-001、HLD-002 | 根 `pom.xml`、BOM 解析结果、锁定的容器 tag/digest 和运行配置 |
| 架构决策 | ADR-001～ADR-004 | 获批 ADR 及与其一致的实现 |
| 文件接口、状态机与一致性 | LLD-001、LLD-002 | Java 源码、Flyway 迁移和集成测试 |
| 文件 HTTP 外部契约 | `contracts/FILE-API-CONTRACT.md` | 版本化 OpenAPI 和接口契约测试 |
| RAG 消息字段与分支 | `lld/contracts/rag/*.schema.json` | 双方模型、不可变 Outbox、序列化测试、MQ 初始化和跨语言合同测试 |
| 需求到设计、契约和验收的映射 | `governance/RTM-V0.1.0.md` | 同一冻结对象上的测试命令、结果和证据路径 |

Markdown 版本表用于解释选择，不能约束 Maven 实际解析结果。进入实现后，Java 依赖版本必须由 POM/BOM 锁定，数据库结构必须由 Flyway 迁移锁定；后续 Python 依赖由 Python 项目的 `pyproject.toml` 和锁文件管理。

## 5. 当前冻结的关键设计

- Java 文件中心保持一个 Spring Boot 进程，代码主链路为 `Controller → Service → Mapper/DAO → PostgreSQL`；MinIO 通过 `ObjectStorageService` 接入，定时任务通过 `FileReconcileService` 执行补偿。
- 文件生命周期：`UPLOADING → ACTIVE`、`UPLOADING → FAILED`、`ACTIVE → REPLACING → ACTIVE`、`REPLACING → FAILED`、`ACTIVE → DELETING → DELETED`、`DELETING → FAILED`。
- 可用状态独立为 `ENABLED/DISABLED`；只有 `ACTIVE + ENABLED` 有效可用。启停仅允许生命周期为 `ACTIVE`，状态值与历史同 PostgreSQL 事务提交。
- 正文只允许上传完整文件替换，保持逻辑 `file_id` 和原可用状态，生成新 `reference_id/object_key`；不提供在线增量编辑。
- `REPLACING + ENABLED` 期间只允许查询详情和下载替换前已提交的旧当前对象；候选对象不得进入详情、下载或 RAG 引用。
- 上传和内容替换都拒绝零字节文件，返回 `422 FILE_EMPTY`。
- Java → RAG 入库合同：`document_submitted`，`schema_version=2.0`。
- Java → RAG 逻辑文件事实目标合同：`file_fact_changed`，`schema_version=1.0`，MessageGroup 为稳定 `file_id`，Property `payload_hash` 按规范 JSON 计算；每份不同 payload 使用独立事件 `operation_id`，与内部 `file_workflow_id` 分离；覆盖创建、完整替换、元数据修改、启停、删除和失败，当前为 `CONTRACT_ONLY / NOT_SENT / NOT_RUN`。
- RAG → Java 接纳合同：`document_ingestion_acceptance`，`schema_version=1.0`，分为 `ACCEPTED / REJECTED / CONFLICT`。这是目标合同，当前 Python 状态为 `NOT_IMPLEMENTED / NOT_RUN`。
- RAG → Java 最终结果合同：`document_ingestion_result`，`schema_version=1.0`，分为 `READY / FAILED`。
- 未来 MQ 接入时，已提交文件事实、RAG delivery operation 和不可变 Outbox payload/hash 同 PostgreSQL 本地事务写入，提交后发送，旧事件不得从新快照重建；V0.1.0 不建表、不发送。
- Gateway 是后续统一前端访问 Java 文件 API 与 Python RAG/Agent API 的独立入口，本版不启动。

## 6. 当前未决项

- 单文件大小上限、分页上限、墓碑保留期、补偿扫描间隔和重试参数需要在实现前根据部署环境冻结。
- MinIO Java SDK、MyBatis-Plus 和 Flyway 的候选组合仍需在目标 Temurin x64 JDK 8 工具链上完成构建与行为验证。
- 当前机器的 Java、Javac 和 Maven 绑定并非同一目标 JDK；实施前必须统一到 HLD-001 的 JDK 基线。
- Python 必须在后续版本实现 `file_fact_changed` 严格模型、按 `file_id/file_version` 幂等应用、替换退役旧文档，以及 acceptance 严格模型、同业务事务 Outbox 和固定向量测试，Java 才能进入真实接入。
- JSON Schema 中的 `x-utf8-max-bytes`、`x-max-fractional-second-digits` 和 `x-canonical-order` 是扩展约束，通用校验器可能忽略；后续 Java/Python 合同测试必须显式覆盖。

## 7. 证据边界

当前文档与 Schema 最多构成设计证据和静态合同证据。当前验证器对 4 份 Schema、14 个有效样例、22 个无效样例和 SHA-256 清单执行通过；这不能证明 Java 文件功能已实现，不能证明 PostgreSQL 或 MinIO 已启动，不能证明 Transactional Outbox、RocketMQ 收发、Python 状态应用、Gateway 或 Java/Python 端到端链路已运行。

在真实执行前，Java 源码、PostgreSQL、MinIO、RocketMQ、Python、Gateway 和端到端联通的状态均不得从这些文档推导为 `PASS`。本目录的正式状态保持 `DRAFT_FOR_USER_REVIEW / NOT_APPROVED_FOR_IMPLEMENTATION`。

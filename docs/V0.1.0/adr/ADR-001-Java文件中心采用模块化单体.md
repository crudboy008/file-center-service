# ADR-001 Java 文件中心采用模块化单体

- 日期：2026-09-03
- 状态：方向继承既有裁决；本文细节 `DRAFT_FOR_USER_REVIEW / NOT_APPROVED_FOR_IMPLEMENTATION`
- 适用版本：V0.1.0 起

## 1. 背景

V0.1.0 只交付 Java 文件管理。HTTP 接入、业务编排、PostgreSQL 数据访问和 MinIO 存储实现需要清晰分工，但当前不存在 Java 内部模块独立发布、独立扩容或网络隔离的已确认需求。

目标系统还会增加独立 Python RAG/Agent 服务。Python 是独立部署单元，不意味着 Java 内部的 Controller、Service、Mapper 和存储实现也必须拆成多个服务。

依据：

- 本期范围来自 2026-09-03 用户原文；
- 一个 JVM、一个启动类、模块间 Java 调用的既有裁决来自外部设计输入 `modular-monolith-decision.md` 第 1～3 节；
- 当前工程尚未实现，没有分布式 Java 服务的运行证据。

## 2. 决策

Java 文件中心采用模块化单体：

1. 只运行一个 JVM、一个 Spring Boot 启动类、一个可执行 JAR。
2. 在单 Maven 工程内采用常规三层主链路：`Controller → Service → Mapper/DAO → PostgreSQL`。
3. `Controller` 只负责 HTTP DTO、参数校验和响应/错误映射，只能调用 `Service`；禁止直接调用 Mapper 或 MinIO Client。
4. `Service` 负责业务规则、状态迁移、事务边界和跨资源编排，可以直接调用 MyBatis Mapper；本项目把 Mapper 作为 DAO 层，不再额外包装通用 Repository 端口。
5. 对象存储是数据库之外的外部资源，保留一个本项目定义的 `ObjectStorageService` 接口；`MinioObjectStorageService` 实现该接口，并把 MinIO SDK 类型限制在 `storage/minio` 包内。
6. 定时任务放在 `job` 包，只触发 `FileReconcileService`；补偿 Service 再调用 Mapper 和 `ObjectStorageService`，Job 不直接访问数据库或 MinIO Client。
7. Java 内部调用不使用 HTTP、OpenFeign、RocketMQ 或服务发现。RAG 契约可以作为独立稳定资源存在，但 V0.1.0 不装配 MQ 运行实现、RAG 状态表或虚假 RAG 实现。

精确包名和依赖方向由 LLD 冻结。不得出现第二个业务启动类或 Java 内部网络调用。

## 3. 原因

- 当前文件管理只有一个一致的发布和运行边界，拆成多个 Java 进程没有已确认的业务收益。
- 单个 PostgreSQL 本地事务足以管理文件元数据；MinIO 的跨资源问题仍需补偿，拆服务不会使它自动原子化。
- 三层结构与团队熟悉的 Spring MVC/MyBatis 开发方式一致，Controller、业务编排和数据库访问的责任容易从代码位置判断。
- MinIO 仍通过项目自定义接口隔离，因为它是外部 SDK 和独立资源；这保留了测试替身和存储实现替换点。
- 单进程降低本地运行资源和联调变量，便于把验证集中在文件生命周期与存储一致性上。

以上是架构推理，不是性能测量。当前没有压测数字证明模块化单体或微服务在吞吐上的优劣。

## 4. 后果

### 4.1 正向结果

- 文件用例可以在一个调用栈内编排，错误和事务边界清晰。
- 只需部署、监控和排查一个 Java 业务进程。
- Controller、Service、Mapper 的调用方向明确，主流程不需要穿过多组端口和适配器类型。
- MinIO SDK 只出现在 `storage/minio`，业务 Service 依赖稳定的 `ObjectStorageService`。
- 未来 Java 与 Python 的边界仍然是明确的网络/消息合同，不会因 Java 单体而消失。

### 4.2 代价与约束

- 模块共享进程，内存耗尽或 JVM 崩溃会影响整个 Java 文件中心。
- 构建必须检查包依赖方向，否则代码可能退化为 Controller、Mapper 和存储客户端任意互调。
- Service 直接依赖 Mapper 后，Service 容易持续膨胀；文件主流程和补偿流程必须分别由 `FileService`、`FileReconcileService` 承担。
- 共享数据库不能成为 Controller 或 Job 绕过 Service 的理由。
- 单体内不能声称拥有分布式服务治理、独立扩缩容或独立发布证据。

## 5. 被否决方案

### 5.1 V0.1.0 拆成多个 Java 微服务

否决原因：没有第二个独立 Java 业务发布边界，却会立即引入网络 DTO、超时、重试、鉴权、服务发现和多进程运维。当前需求和证据不支持这些成本。

### 5.2 所有代码放入一个无边界模块

否决原因：Controller、Mapper 和 MinIO SDK 容易直接耦合，文件状态机与补偿逻辑无法形成可测试边界，也不利于后续提取 RAG 集成模块。

### 5.3 V0.1.0 使用完整领域层与 Port/Adapter 体系

否决原因：当前是单进程、本地模拟交付，核心持久化只有 PostgreSQL，MyBatis Mapper 已能承担明确的 DAO 职责。再为每个数据库操作建立 Repository Port、领域接口和 Infrastructure Adapter 会增加类型、映射和调用层级，却没有对应的多实现、独立发布或复杂领域建模需求。对象存储因涉及独立资源和第三方 SDK，仍保留专用接口边界。

## 6. 重新评估条件

出现以下经过测量或组织确认的条件之一时，重新评估模块提取：

- 文件上传/下载需要独立扩容；
- 某模块需要独立发布节奏或故障隔离；
- 身份、审计等能力需要被多个系统复用；
- 安全或团队所有权要求独立部署；
- 单进程资源竞争已有可复现证据。

提取服务时必须新增网络合同、超时、重试、鉴权、可观测性和数据迁移设计，不能把 Java 接口直接视为远程接口。

## 7. 验证要求

- 构建产物中只有一个可执行 Spring Boot JAR；
- 只有一个 `main` 启动类；
- 依赖检查证明 Controller 只调用 Service，且不直接引用 Mapper 或 MinIO Client；
- Service 可以引用 Mapper 和 `ObjectStorageService`，但不能引用 MinIO SDK 类型；
- MyBatis-Plus 类型只出现在 Mapper/数据访问代码，MinIO SDK 类型只出现在 `storage/minio`；
- `job` 只调用 `FileReconcileService`，不直接调用 Mapper、`ObjectStorageService` 或 MinIO Client；
- 文件主流程在真实 PostgreSQL/MinIO 上验证。

静态依赖检查只能证明代码组织和构建形状；不能替代真实 PostgreSQL/MinIO 上的运行验证。

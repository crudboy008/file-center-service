# ADR-001 Java 整体工程采用多模块模块化单体

- 日期：2026-09-03
- 状态：方向继承既有裁决；本文细节 `DRAFT_FOR_USER_REVIEW / NOT_APPROVED_FOR_IMPLEMENTATION`
- 适用版本：V0.1.0 起

## 1. 背景

V0.1.0 只交付文件管理能力，但 `E:\project\java-card-service` 是整体 Java 工程，`E:\project\java-card-service\file-center-service` 只是其中一个业务模块。后续 Java 业务模块与文件模块同级，由同一个 Spring Boot 应用装配并共享同一个 JVM 进程，不按真实微服务拆成多个 Java 进程。

当前磁盘中，整体根目录只有 `file-center-service`；整体根 `pom.xml`、唯一启动宿主和其他业务模块尚未创建。现有 Git 根位于 `file-center-service`，不等于整体 Maven 工程根。实现时必须显式区分这两个根目录，不能因为当前仓库只包含文件模块，就把整体构建、启动和共享运行配置全部放进文件模块。

目标系统还会增加独立 Python RAG/Agent 服务。Python 是独立部署单元，不改变 Java 内部采用多模块、单进程直接调用的边界。

依据：

- 本期范围来自 2026-09-03 用户原文；
- 整体目录、当前模块、未来兄弟模块、共享 JVM 和公共配置边界来自 2026-09-03 用户最新原文：“`E:\project\java-card-service`，这是整体的 Java 项目，当前是这个项目里的一个模块……后续在整体项目里还要加入其他 service 的，跟当前项目享用同一个 JVM……别把公共配置全塞当前文件夹里了”；
- 单 JVM 和模块间 Java 调用的既有方向来自外部设计输入 `modular-monolith-decision.md` 第 1～3 节；
- 当前整体根和文件模块均尚未实现 Java 代码，没有多模块构建或运行证据。

## 2. 决策

整体 Java 工程采用 Maven 多模块的模块化单体：

1. `E:\project\java-card-service` 是 Maven 聚合根，负责父 `pom.xml`、`dependencyManagement`、`pluginManagement`、Maven Wrapper、模块清单和整体本地运行编排。
2. `card-service-app` 是唯一 Spring Boot 启动宿主，持有唯一 `main`、Spring Boot repackage、`application*.yml`、运行 Profile、全局 Web/Jackson/日志/请求关联/异常响应/OpenAPI 聚合及共享基础设施装配。整体 Java 应用只生成一个可执行 JAR、启动一个 JVM。
3. `file-center-service` 是当前非独立运行的业务 JAR 模块。它持有文件 Controller、Service、Mapper、实体、文件状态机、文件专属配置类型、MinIO 适配和 Flyway 文件表迁移；不得持有 `main`、独立 Spring Boot repackage、整体 `application*.yml`、根 Maven Wrapper 或整体 Compose。
4. 后续 Java 业务模块作为 `java-card-service` 下与 `file-center-service` 同级的 Maven 模块加入，由 `card-service-app` 统一依赖和装配，在同一个 JVM 内通过 Java 接口调用，不为每个模块启动独立端口或进程。
5. 端口、DataSource 连接、Jackson、日志、请求 ID、全局异常映射与统一错误格式、OpenAPI 聚合等跨模块运行配置放在 `card-service-app`；父 POM、依赖/插件版本、Wrapper 和整体 Compose 放在整体根。`file-center-service` 只定义文件领域异常和稳定错误码，不定义全局 `ControllerAdvice`。真正被两个及以上业务模块复用的编译期类型或技术代码再提取到同级公共模块，不得反向寄存在 `file-center-service`，也不得要求业务模块反向依赖启动宿主。
6. 文件大小、允许媒体类型、Bucket 逻辑名、补偿周期等文件领域专属配置键由文件模块定义类型和校验，但运行值仍由启动宿主的配置文件或环境变量注入。凭据只由环境注入。
7. 文件模块内部采用常规三层主链路：`Controller → Service → Mapper/DAO → PostgreSQL`。`Controller` 只能调用 `Service`；禁止直接调用 Mapper 或 MinIO Client。
8. `Service` 负责业务规则、状态迁移、事务边界和跨资源编排，可以直接调用 MyBatis Mapper；Mapper 是 DAO 层，不再额外包装通用 Repository 端口。
9. 对象存储保留文件模块定义的 `ObjectStorageService`；`MinioObjectStorageService` 实现该接口，并把 MinIO SDK 类型限制在文件模块的 `storage/minio` 包内。定时 Job 只触发 `FileReconcileService`。
10. Java 模块间调用不使用 HTTP、OpenFeign、RocketMQ 或服务发现。RAG 契约可以作为稳定资源存在，但 V0.1.0 不装配 MQ 运行实现、RAG 状态表或虚假 RAG 实现。

目标目录结构为：

```text
E:\project\java-card-service\
├─ pom.xml                         # Maven 父工程/聚合工程
├─ .mvn\ + mvnw + mvnw.cmd        # 整体构建入口
├─ docker-compose.yml              # 整体本地运行编排
├─ card-service-app\               # 唯一启动宿主和共享运行配置
├─ file-center-service\            # 当前文件业务模块
└─ <future-business-service>\      # 后续同 JVM 兄弟业务模块
```

精确包名和文件模块内部依赖方向由 LLD 冻结。当前 Git 仓库仍只覆盖 `file-center-service`；本 ADR 不授权移动 `.git`、初始化整体根仓库或决定未来仓库拆分策略。

## 3. 原因

- 多个 Java 业务模块只有一个发布和运行边界，拆成多个 Java 进程没有已确认的业务收益，还会超过当前模拟项目的资源预算。
- Maven 模块边界让文件能力和后续业务能力在源码、依赖和测试上分开，同时仍只消耗一个 JVM。
- 启动宿主集中装配共享运行配置，避免第一个业务模块变成事实上的公共基础模块。
- 单个 PostgreSQL 本地事务足以管理文件元数据；MinIO 的跨资源问题仍需补偿，拆服务不会使它自动原子化。
- 三层结构与团队熟悉的 Spring MVC/MyBatis 开发方式一致，Controller、业务编排和数据库访问的责任容易从代码位置判断。
- MinIO 仍通过项目自定义接口隔离，因为它是外部 SDK 和独立资源；这保留了测试替身和存储实现替换点。
- 单进程降低本地运行资源和联调变量，便于把验证集中在文件生命周期与存储一致性上。

以上是架构推理，不是性能测量。当前没有压测数字证明模块化单体或微服务在吞吐上的优劣。

## 4. 后果

### 4.1 正向结果

- 文件用例可以在一个调用栈内编排，错误和事务边界清晰。
- 只需启动和排查一个 Java 业务进程；当前模拟项目不为每个 Java 模块额外占用 JVM、端口和内存。
- 新业务模块以同级 Maven 模块加入，不需要迁入文件模块包目录。
- 共享运行配置有明确宿主，文件模块可以保持业务内聚。
- Controller、Service、Mapper 的调用方向明确，主流程不需要穿过多组端口和适配器类型。
- MinIO SDK 只出现在 `storage/minio`，业务 Service 依赖稳定的 `ObjectStorageService`。
- 未来 Java 与 Python 的边界仍然是明确的网络/消息合同，不会因 Java 单体而消失。

### 4.2 代价与约束

- 模块共享进程，内存耗尽或 JVM 崩溃会影响整个 Java 应用。
- 构建必须检查包依赖方向，否则代码可能退化为 Controller、Mapper 和存储客户端任意互调。
- `card-service-app` 会依赖业务模块，业务模块不得反向依赖启动宿主；否则形成 Maven 循环依赖。
- 当前 Git 根与整体 Maven 根不一致，整体父 POM 和启动宿主在创建后如何纳入版本控制仍需单独决定；不得为了绕过该问题把它们塞入文件模块。
- Service 直接依赖 Mapper 后，Service 容易持续膨胀；文件主流程和补偿流程必须分别由 `FileService`、`FileReconcileService` 承担。
- 共享数据库不能成为 Controller 或 Job 绕过 Service 的理由。
- 单体内不能声称拥有分布式服务治理、独立扩缩容或独立发布证据。

## 5. 被否决方案

### 5.1 V0.1.0 拆成多个 Java 微服务

否决原因：没有第二个独立 Java 业务发布边界，却会立即引入网络 DTO、超时、重试、鉴权、服务发现和多进程运维。当前需求和证据不支持这些成本。

### 5.2 把整体应用和公共配置放入 `file-center-service`

否决原因：会把当前第一个业务模块误当成整体工程根。后续业务模块要么反向依赖文件模块，要么复制启动与配置，最终破坏模块边界。

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

- `E:\project\java-card-service\pom.xml` 是聚合父 POM，并声明 `card-service-app`、`file-center-service` 及届时已存在的业务模块；
- 构建产物中只有 `card-service-app` 生成一个可执行 Spring Boot JAR，整体只有一个 `main` 启动类；
- `file-center-service` 只生成普通业务 JAR，不含 `main`、Spring Boot repackage、整体 `application*.yml`、Maven Wrapper 或整体 Compose；
- `card-service-app` 依赖并装配 `file-center-service`，文件模块不得反向依赖启动宿主；
- 共享运行配置位于启动宿主或整体根；文件模块只保留文件专属配置类型、校验和业务资源；
- 依赖检查证明 Controller 只调用 Service，且不直接引用 Mapper 或 MinIO Client；
- Service 可以引用 Mapper 和 `ObjectStorageService`，但不能引用 MinIO SDK 类型；
- MyBatis-Plus 类型只出现在 Mapper/数据访问代码，MinIO SDK 类型只出现在 `storage/minio`；
- `job` 只调用 `FileReconcileService`，不直接调用 Mapper、`ObjectStorageService` 或 MinIO Client；
- 文件主流程在真实 PostgreSQL/MinIO 上验证。

静态依赖检查只能证明代码组织和构建形状；不能替代真实 PostgreSQL/MinIO 上的运行验证。

# RAG 对接合同机器可读基线

- 文档状态：`DRAFT_FOR_USER_REVIEW / NOT_APPROVED_FOR_IMPLEMENTATION`
- 适用版本：`V0.1.0` 只做静态合同设计和校验
- 运行边界：不启动 RocketMQ、Python RAG 或 Java MQ Adapter

## 文件

| 文件 | 方向 | 当前性质 |
|---|---|---|
| `document-intake-v2.schema.json` | Java → Python | 对齐当前 Python `DocumentIntakeEvent`，并把 Java 必须发送 SHA-256 收紧为必填 |
| `document-ingestion-acceptance-v1.schema.json` | Python → Java | 为补齐接纳可见性而新增的目标合同；当前 Python 尚未实现 |
| `document-ingestion-result-v1.schema.json` | Python → Java | 对齐当前 Python `DocumentIngestionResult` 的 READY/FAILED 分支 |
| `examples/*.valid.json` | 双向 | 供静态 Schema 校验和后续跨语言测试使用 |
| `examples/*.invalid.json` | 双向 | 必须被对应 Schema 拒绝的固定反向样例 |
| `SHA256SUMS.txt` | 双向 | 三份 Schema 和全部固定样例的内容哈希清单 |
| `validate_contracts.py` | 双向 | 只读静态验证器；补足标准校验器会忽略的本项目扩展约束 |

反向样例覆盖：额外字段、未知版本、非法 SHA-256、非法时间、acceptance 禁止字段/空值/缺字段，以及最终结果错误分支字段。文件名中的 `intake`、`acceptance`、`result` 决定应使用哪一份 Schema。

## 静态校验

基线校验环境为 Python 3 和 `jsonschema==4.26.0`。在本目录执行：

```powershell
python -m pip install "jsonschema==4.26.0"
python .\validate_contracts.py
```

只有 Schema 或固定样例经过评审后发生了有意变更，才执行以下命令更新哈希清单；更新后必须复审差异：

```powershell
python .\validate_contracts.py --write-manifest
```

验证器固定使用 Draft 2020-12，显式注册严格 RFC 3339 `date-time` 检查，并实现 `x-utf8-max-bytes`、`x-max-fractional-second-digits`、`x-canonical-order` 三个项目扩展。它还验证入库样例的 `file_ref` 后缀与 `document_id/reference_id` 相同。

## 不能由静态校验推出的结论

Schema 和样例通过只形成静态合同证据，不证明：

- RocketMQ Topic、Consumer Group 或 FIFO 属性已经创建；
- Java Producer/Consumer 已实现；
- Python acceptance Outbox 已实现；
- Java MinIO SDK 与 Python MinIO SDK 已完成跨 SDK 组合验证；
- Java → RocketMQ → Python → MinIO → RocketMQ → Java 链路已经运行。

这些运行结论在 V0.1.0 均为 `NOT_RUN`。

## 非标准扩展

JSON Schema 的 `maxLength` 按 Unicode 字符计数，不能等价表达 Python 当前合同中的 UTF-8 字节上限。因此 Schema 使用 `x-utf8-max-bytes` 记录额外约束；Java/Python 合同测试必须单独验证该扩展。

`x-max-fractional-second-digits` 和 `x-canonical-order` 也属于项目扩展，分别记录 RFC 3339 小数秒上限和数组规范排序要求。通用 JSON Schema 校验器会忽略这些扩展，跨语言合同测试必须显式验证。

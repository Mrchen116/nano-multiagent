# Gateway Service Lifecycle Specification (delta for refactor-783)

## ADDED Requirements

### Requirement: 产品运行时 RPC 在业务操作与结果消费前校验数据

#### Scenario: 参数不符合所调用的方法

- **WHEN** 产品运行时收到已知产品方法的请求，其必需参数缺失或类型错误
- **THEN** 该调用以参数错误结束，处理端不会执行所请求的业务操作。

#### Scenario: 返回值不符合原请求

- **WHEN** 运行时返回的成功结果缺少该方法必需的数据或字段类型错误
- **THEN** 产品调用方将该请求判为失败，不用这个结果确认操作、创建产品绑定或推进消费进度；允许的旧结果及合法业务拒绝继续按原语义处理。

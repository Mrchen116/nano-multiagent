# Gateway Relay Protocol Specification (delta for refactor-783)

## ADDED Requirements

### Requirement: 节点在执行中心主动 RPC 前校验请求

#### Scenario: 已关联的请求缺少操作所需字段

- **WHEN** 已认证 IM 发来的已知命令缺少必需的业务身份或携带错误类型的参数
- **THEN** 节点拒绝执行该业务操作，不产生成功回执。原命令若支持明确失败回包，仍使用其已有的关联身份和结果类型。

#### Scenario: 独立升级期间读取合法旧报文

- **WHEN** 对端发送受支持版本的合法请求或回执，带有已允许的缺省字段或提供方扩展
- **THEN** 收端按该命令原有语义处理；回执只确认与其匹配的请求，未确认的持久操作保留恢复身份。

## MODIFIED Requirements

### Requirement: Skills 使用统计 WS RPC

#### Scenario: IM 前端通过 gateway 读取 skill 使用统计

- **WHEN** IM 用 `node.skills.usage.request` 请求指定 Agent 的技能使用统计
- **THEN** Gateway 从该 Agent 可用的技能目录（含共享目录）聚合属于该 Agent 的统计，使用 `node.skills.usage` 返回与请求关联的聚合结果。

#### Scenario: 各技能目录均无该 Agent 的统计

- **WHEN** 所有可用技能目录都没有该 Agent 的使用记录
- **THEN** 返回空的技能列表。

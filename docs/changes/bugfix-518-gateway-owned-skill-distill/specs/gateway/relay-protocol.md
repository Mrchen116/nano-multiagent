# gateway relay-protocol Specification (delta for bugfix-518)

## ADDED Requirements

### Requirement: Gateway 对历史会话蒸馏在本机 materialize source transcript

Gateway 收到由 IM 中继的历史会话蒸馏 source identities 时，只在自己拥有的 Agent workspace 中，
通过 durable conversation/session binding 定位并读取 JSONL，再把已验证的 source context 用于该次
execution Agent run。Gateway 不接受 IM/browser 提供的 transcript path，不跨 Gateway 拼接来源；任一
来源不能验证、正在运行、缺失或损坏时，整次操作不给模型 partial context，也不创建 skill。

#### Scenario: 同 Gateway 来源被本机读取并产生普通聊天结果
- **GIVEN** 所有 source conversations 与 execution Agent 均属于当前 Gateway，且每个来源有可读的
  durable binding 与 JSONL
- **WHEN** Gateway 收到该普通蒸馏消息
- **THEN** Gateway 在本机 materialize 所有来源并执行历史会话蒸馏
- **AND** source data 不跨 relay 返回 IM/browser，普通消息历史也不暴露内部处理细节
- **AND** skill 的写入结果经既有普通聊天/tool relay 展示

#### Scenario: Gateway 不接受或传播 transcript path
- **WHEN** Gateway 处理历史会话蒸馏请求
- **THEN** 请求 wire contract 只使用 conversation/Agent identity 与 scope
- **AND** Gateway 不向 IM、browser、普通 message 或模型可见用户意图输出本机 JSONL/workspace 绝对路径

#### Scenario: source 不能完整 materialize 时不部分蒸馏
- **GIVEN** 至少一个来源的 binding 缺失、记录不可读/损坏，或来源正在运行
- **WHEN** Gateway 准备蒸馏输入
- **THEN** Gateway 返回可理解的失败反馈，不运行 distiller、不给模型其余来源，也不写入 skill
- **AND** 该反馈经既有普通 reply 与 failed delivery receipt 返回，且不创建 execution session/binding

#### Scenario: 跨 Gateway 组合不被执行
- **WHEN** 请求的任一 source 或 execution Agent 不属于收到请求的 Gateway
- **THEN** Gateway 拒绝该请求并提示重新选择同一 Gateway 的会话
- **AND** 不转发、不分批也不尝试远端读取

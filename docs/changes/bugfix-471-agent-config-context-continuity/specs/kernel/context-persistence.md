# kernel Context and Persistence Specification (delta for bugfix-471)

## ADDED Requirements

### Requirement: 消费者可在同一会话上持久替换后续运行配置

`agent.sdk` 的消费者可向一个已有会话提供完整的新运行配置；替换与当前 turn 串行，在返回成功前持久化，并保持 session id、既有 transcript、压缩状态和父链不变。相同配置的重复替换幂等。消费者不需要读取或改写 JSONL 格式，也不负责失效内核 live state。

#### Scenario: 替换配置后下一轮延续原历史
- **GIVEN** 一个已有多轮消息与工具调用历史的会话
- **WHEN** 消费者成功替换该会话的 prompt、skills、tools 或 features 后再提交下一轮
- **THEN** 下一轮使用替换后的运行配置，并仍能看到替换前的完整可用历史
- **AND** 会话 id 不变

#### Scenario: 删除工具只限制未来调用
- **GIVEN** 会话历史中已有某工具的 call 与 result
- **WHEN** 消费者把运行配置替换为不含该工具后继续会话
- **THEN** 历史 call/result 仍能被后续模型上下文读取
- **AND** 该工具不能被后续运行再次执行

#### Scenario: 活跃 turn 期间替换不造成半轮切换
- **GIVEN** 会话正在用配置 A 执行一个 turn
- **WHEN** 消费者同时请求替换为配置 B
- **THEN** 已开始的 turn 完整使用配置 A，替换在其后原子完成，下一新 turn 才使用配置 B

#### Scenario: 配置替换持久恢复
- **GIVEN** 消费者已成功替换一个会话的运行配置
- **WHEN** 进程重启后按原 session id 和 workspace 恢复该会话
- **THEN** 会话使用替换后的配置并保留替换前后的历史

#### Scenario: 重复替换等价配置幂等
- **WHEN** 消费者对同一会话重复提交等价的完整运行配置
- **THEN** 返回可辨识的未变化结果，不产生重复配置代次，历史不变

#### Scenario: 持久化失败不暴露半应用状态
- **WHEN** 运行配置替换无法持久化
- **THEN** 调用失败，后续运行不会观察到新旧字段混合的配置

### Requirement: 消费者可读取会话当前持久运行配置身份

消费者可经 `agent.sdk` 读取一个会话当前持久化的完整运行配置及稳定身份，用于恢复外围绑定；内核不暴露 JSONL entry 或保留 metadata 的格式。缺少完整身份的旧档案以明确的不可用结果返回。

#### Scenario: 重启后读取已替换的运行配置
- **GIVEN** 会话已持久化运行配置替换
- **WHEN** 新 Kernel 实例读取该会话的当前运行配置
- **THEN** 返回与替换成功时等价的运行配置和身份

#### Scenario: 极旧档案没有完整运行身份
- **GIVEN** 旧会话档案没有足够信息重建完整运行配置身份
- **WHEN** 消费者读取当前运行配置
- **THEN** 返回明确的不可用结果，不猜测一份配置，也不改写档案

## MODIFIED Requirements

### Requirement: fork_session 复制源会话「在 fork 点那一刻的上下文与运行配置」到独立新会话

`agent.sdk` 的消费者可对已有会话发起 fork，指定消息 M 为 fork 点：内核复制源会话在 M 时所用的上下文视图和当时已持久化的运行配置，生成独立新会话。源若已压缩，复制的是含当时压缩摘要的视图；M 之后的源内容与配置替换不进入新会话。两边后续历史和配置独立演进。

#### Scenario: fork 带着源在 fork 点的记忆与配置
- **GIVEN** 源会话在 M 之前形成历史并经历过运行配置替换
- **WHEN** 消费者 fork 到 M
- **THEN** 新会话的上下文与运行配置等于源在 M 时的持久视图
- **AND** M 之后的消息或配置变化不进入新会话

#### Scenario: fork 后两边配置与历史独立
- **GIVEN** 已从源会话 fork 出新会话
- **WHEN** 消费者在任一侧继续对话或替换运行配置
- **THEN** 另一侧的历史和运行配置不受影响

## REMOVED Requirements

N/A.

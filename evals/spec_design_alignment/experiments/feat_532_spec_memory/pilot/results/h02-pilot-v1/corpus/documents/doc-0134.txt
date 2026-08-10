# refactor-522: Gateway session continuity owner

## Relations

- Depends on: 无
- Blocks: 无
- Related: feat-501, refactor-480, refactor-481

## 原始诉求

> 本次扫描的前二问题，你开两个subagent解决。

> 我只做pr review

## 澄清记录

- Q1: 是否由 Agent 自主收敛实现细节，并把两个候选分别交付到只需最终 PR review 的状态？
  A(原话): 我只做pr review
  Agent 解读: 本 unit 采用保守的行为不变重构；不发起中间确认，不改变会话、控制命令或恢复语义，最终独立交付 PR。

## 现状痛点

Gateway 已有 `GatewaySessionBinder` 负责把产品会话解析为 Kernel session，但 session continuity 的调用者仍需要接触一组宽的持久化操作；测试也大量直接实例化内存或 SQLite store。随着会话重置、手动压缩、配置边界、控制结果、外部投递恢复和旧 run 收敛进入同一连续性领域，这个持久化 seam 已承载多种有顺序约束的操作，调用方与测试需要了解过多内部状态。

并行内存实现不能覆盖 Gateway 重启和跨进程恢复语义，而生产 SQLite 实现仍残留已移除的 Kernel HTTP client 描述与入口。继续保持现状会让测试通过却漏掉真实恢复问题，也使 continuity 规则在 binder、store 和调用者之间逐渐分散。

## 目标状态

Gateway session continuity 由一个明确 owner 承担：调用方只表达解析、切换或恢复会话的产品意图，不直接编排持久化步骤；测试通过同一行为入口验证普通复用、重启恢复、控制命令幂等和失败回滚。用户观察到的会话历史、上下文切换、跨通道隔离和恢复结果全部保持不变。

### Requirement: 普通会话连续性保持一致

#### Scenario: 同一聊天继续复用原上下文

- **GIVEN** 用户已在某个聊天中与 Agent 完成至少一轮对话
- **WHEN** 用户继续在同一聊天发送普通消息
- **THEN** Agent 仍延续该聊天的既有上下文，回复回到原通道原目标，结果与重构前一致

#### Scenario: 不同聊天与 Agent 不串会话

- **GIVEN** 同一 Gateway 同时服务多个聊天或多个 Agent
- **WHEN** 各聊天分别继续对话
- **THEN** 每条消息仍只使用自己的会话上下文，不读取或覆盖其他聊天与 Agent 的上下文

### Requirement: 重启后的会话恢复保持一致

#### Scenario: Gateway 重启后继续原会话

- **GIVEN** 某聊天已有持久的 Gateway-to-Kernel session 映射
- **WHEN** Gateway 重启后用户在该聊天继续发送消息
- **THEN** Gateway 仍恢复并复用原会话上下文，不因本次重构开始一个无历史的新会话

#### Scenario: 不完整恢复状态不会产生虚假成功

- **GIVEN** 会话切换或控制结果在上次进程退出前只完成了部分步骤
- **WHEN** Gateway 重启并恢复该聊天
- **THEN** 用户只看到既有契约允许的唯一结果；未成功发布的切换不被宣告成功，已提交但未投递的结果最终补齐且不重复改变上下文

### Requirement: 会话控制行为保持一致

#### Scenario: `/new` 与 `/compact` 保留现有语义

- **GIVEN** 用户在一个已有上下文的聊天中
- **WHEN** 用户发送精确 `/new`、`/compact` 或带关注点的 `/compact`
- **THEN** 可见确认、旧历史保留、后续上下文、no-op/失败结果和重放幂等行为均与重构前一致

#### Scenario: 忙碌会话中的 `/compact` 保持 FIFO 顺序

- **GIVEN** 当前聊天已有正在执行或排队的用户工作
- **WHEN** 用户发送 `/compact`，随后又发送普通消息
- **THEN** `/compact` 继续在既有工作之后占据 FIFO 位置，后续普通消息不能越过它；若其被 `/new` 超越则按既有 superseded 结果收敛

## 影响范围

- Gateway session binder、session binding 持久化、composition 和依赖这些内部持久化操作的调用方。
- session continuity、重启恢复和 control operation 相关测试。
- 当前 Gateway canonical spec 中与实际 FIFO `/compact` 行为不一致的历史文字。
- 不改变 SQLite 数据格式、IM/Gateway wire contract、Kernel transcript、Web 前端或外部 channel 文案。

## 迁移与回滚策略

- 保持现有 SQLite 数据和启动恢复兼容，采用一次性调用面收敛，不引入第二套会话数据库或长期双写。
- 用真实 SQLite 临时库覆盖普通绑定、重启恢复、控制结果和失败回滚，再删除被深模块行为测试替代的浅层测试 seam。
- 若发现连续性回归，整体回退本 unit 的 owner 收敛；不删除既有 binding、Kernel transcript 或用户可见历史。

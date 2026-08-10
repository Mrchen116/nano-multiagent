# refactor-521: Web relay typed ingress

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-454, refactor-480, feat-447, bugfix-471, bugfix-508

## 原始诉求

> 本次扫描的前二问题，你开两个subagent解决。

> 我只做pr review

## 澄清记录

- Q1: 是否由 Agent 自主收敛实现细节，并把两个候选分别交付到只需最终 PR review 的状态？
  A(原话): 我只做pr review
  Agent 解读: 本 unit 采用保守的行为不变重构；不发起中间确认，不增加产品能力或改变现有通道语义，最终独立交付 PR。

## 现状痛点

Gateway 接收内置 Web IM relay 时，入口已经知道这条消息的来源、投递能力和运行时协议事实，但这些事实没有作为一个稳定整体继续向下游传递。多个后续处理环节需要再次查看通道名称或隐藏在消息 metadata 中的运行时信息，才能判断群聊门控、静默回复、临时气泡、终态投递和 shadow 同步等既有行为。

这让同一条 Web relay 语义分散在多个调用方：新增或调整一种 relay 行为时，需要同时理解入口和多个下游分支；测试也容易围绕 adapter 私有解析或具体通道名，而不是围绕一次入站到最终回复的完整产品行为。继续保持现状会提高变更遗漏和跨通道回归风险。

## 目标状态

Web relay 的来源和运行时事实在进入 Gateway 时一次确定，后续入站、运行和投递环节不再通过具体 provider 名称或隐藏 metadata 重新推导同一语义。用户在内置 Web IM、外部 channel 及其 shadow conversation 中观察到的路由、触发、静默、控制命令和投递结果全部保持不变。

### Requirement: 内置 Web IM 消息的路由与回复保持一致

#### Scenario: 直聊消息仍回复原会话

- **GIVEN** 用户在内置 Web IM 中已有一个与 Agent 的直聊
- **WHEN** 用户发送普通消息并等待 Agent 完成回复
- **THEN** 消息仍由同一 Agent 处理，流式过程和最终回复仍显示在原会话，结果与重构前一致

#### Scenario: 群聊触发与静默保持一致

- **GIVEN** 用户在内置 Web IM 群聊中与一个或多个 Agent 交互
- **WHEN** 用户发送普通消息、明确提及、裸 `/new`，或 Agent 选择静默
- **THEN** 既有群聊门控、全群新会话和静默收敛行为与重构前一致，不新增或遗漏可见消息

### Requirement: 外部 channel 与 shadow 投递保持一致

#### Scenario: 外部消息仍回到原通道原目标

- **GIVEN** 外部 channel 已绑定 Agent，并在 Web IM 中存在对应 shadow conversation
- **WHEN** 外部用户发送一条触发 Agent 的消息
- **THEN** Agent 结果仍回发原外部聊天，shadow conversation 的用户消息、过程和终态仍按既有顺序同步

#### Scenario: 中继断线与重放不产生重复可见结果

- **GIVEN** Gateway 与 IM 之间发生短暂断线、重连或同一 relay 消息重放
- **WHEN** 中继恢复并完成该轮投递
- **THEN** 用户仍只看到既有幂等语义允许的结果，消息和终态不会因本次重构重复或永久缺失

## 影响范围

- Gateway 的 channel 入站模型、Web relay adapter、入站流水线和运行时投递上下文。
- 依赖具体 Web relay 身份或运行时 metadata 的 Gateway 调用方与行为测试。
- 不改变 IM WebSocket wire contract、外部 provider contract、`agent.sdk` 或 Web 前端。

## 迁移与回滚策略

- 迁移采用单次行为等价切换；不保留一套长期双读或按通道名回退的兼容路径。
- 切换前后以相同的 Web IM、外部 channel、shadow、静默和重放旅程验证行为等价。
- 若发现产品回归，整体回退本 unit 的 ingress 重构；不通过恢复隐藏 metadata 分支形成第二套长期语义。

# gateway - External Channels Specification — feat-541 delta

> 落点: `docs/specs/gateway/external-channels.md`
> 投影自: feat-541 spec.md Scenario「外部通道同样看到说明」+ design.md 决策 4

## ADDED Requirements

## MODIFIED Requirements

### Requirement: 外部 channel 用户可见控制与后台文本投递

飞书触发或绑定的用户可见事件必须回到原飞书 chat，并同步到内部 IM 影子会话；内部 IM 影子会话触发的同类事件只留在内部 IM。用户可见事件包括 assistant 文本、`/stop`、`/new`、`/compact` 及 `/compact <关注点>` 的控制确认、因主模型不可用改用备用时的轻量说明、预处理失败、后台 agent 文本、权限审批卡片和审批完成状态。含非空真实更新对象的 `self_evolution_review` system notice 遵守同一触发源规则：飞书触发时在原 chat 显示简短 Bot 更新通知并在 shadow IM 保留结构化 system notice，内部 IM 触发时不回写飞书。外部控制确认的 session/context outcome 与可恢复 delivery intent 必须先同次持久化；该 intent 幂等物化为 shadow output 后才向飞书发送，重放同一 provider message 复用首次控制结果，不重复改变会话或上下文。Gateway 启动和 IM reconnect 必须扫描未物化或未 hand-off 的 intent。若进程恰在 provider 已接受发送、但 hand-off 状态尚未来得及持久化时退出，飞书沿既有 at-least-once outbound 语义可能收到一次重复确认；本系统不伪造跨 provider exactly-once 保证，IM shadow 仍以同一 durable output 收敛。其他系统通知、thinking、工具遥测和调试状态不作为飞书普通聊天消息外发。该轻量说明与压缩控制确认同一投递形态，不是运行信息页脚。

#### Scenario: 飞书 /stop 成功后用户在飞书看到确认
- **GIVEN** 用户在飞书 1:1 对话中触发了一个正在运行的 agent run
- **WHEN** 用户随后在同一飞书对话发送 `/stop`
- **THEN** Gateway 中断对应 run
- **AND** 飞书原对话收到停止确认
- **AND** 内部 IM 影子会话也出现同一确认消息

#### Scenario: 群聊 @Bot /stop 按控制命令处理
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群，且该群中存在正在运行的该 agent run
- **WHEN** 用户在群里发送真实 mention 形式的 `@Bot /stop`
- **THEN** Gateway 将该消息识别为发给该 Bot 的 `/stop` 命令
- **AND** 停止确认发送回同一飞书群并同步到内部 IM 影子群聊

#### Scenario: 飞书 `/new` 或 `/compact` 同步到影子会话
- **GIVEN** 用户在飞书与 Bot 的私聊已有对应内部 IM shadow conversation
- **WHEN** 用户在飞书发送 `/new`、`/compact` 或 `/compact <关注点>`
- **THEN** Bot 在原飞书聊天返回该控制操作的结果
- **AND** IM shadow conversation 显示同一命令与结果，并继续映射该飞书聊天的后续 Agent 工作

#### Scenario: 群聊新控制命令要求明确 @Bot
- **GIVEN** 飞书群有该 Bot 的共同上下文，且其 group reply policy 为 MENTION
- **WHEN** 用户发送未明确指向 Bot 的 `/new` 或 `/compact`
- **THEN** Gateway 只按既有群背景/触发规则处理，不切换或压缩共同会话
- **WHEN** 用户发送 `@Bot /new` 或 `@Bot /compact <关注点>`
- **THEN** Bot 在同一群返回结果，且群对应 IM shadow conversation 同步命令与结果

#### Scenario: IM shadow 暂不可达不阻塞飞书控制确认
- **GIVEN** 飞书 Bot 可用但内部 IM 暂不可达
- **WHEN** 用户在飞书发送一个有效的文本会话控制命令
- **THEN** Gateway 仍在飞书原聊天返回命令结果
- **AND** 在 IM 恢复后，shadow 同步按既有恢复机制补齐同一命令和一条相同确认，不改变飞书控制命令的会话语义

#### Scenario: 飞书 provider 重放控制命令只复用首次结果
- **GIVEN** Gateway 已处理一个带同一 provider message id 的飞书 `/new` 或 `/compact <关注点>`
- **WHEN** provider 重放该消息，或 Gateway 在控制确认投递前后重启并恢复处理
- **THEN** Gateway 不再次切换会话或压缩上下文
- **AND** IM shadow 以同一 caller identity 收敛为一条控制确认；飞书重投沿既有出站去重/投递语义返回第一次的控制结果

#### Scenario: control outcome 提交后崩溃仍恢复确认
- **GIVEN** 飞书 `/new` 或 `/compact <关注点>` 的 session/context outcome 与其 external delivery intent 已提交
- **AND** Gateway 在 saga control output 写入前退出，且 provider 不重放该入站消息
- **WHEN** Gateway 重启并完成 external channel ready，或随后 IM reconnect
- **THEN** Gateway 从 pending delivery intent 幂等建立同一 saga control output，并向原飞书 chat 投递首次结果
- **AND** IM shadow 在可用后按既有 recovery 仅出现一条相同确认，不再次改变会话或上下文

#### Scenario: 飞书预处理失败反馈回原对话
- **GIVEN** 用户在飞书发送 Gateway 当前不支持或处理失败的图片/附件消息
- **WHEN** Gateway 在提交 agent run 前判定该消息无法处理
- **THEN** 失败原因发送到飞书原对话
- **AND** 同一失败原因同步到内部 IM 影子会话

#### Scenario: 飞书绑定后台 agent 文本回到飞书
- **GIVEN** 某个后台任务或 delayed run 绑定到飞书触发的影子会话
- **WHEN** 该后台任务产生 agent 自己的用户可见文本输出
- **THEN** 该文本发送到原飞书 chat
- **AND** 该文本同步到内部 IM 影子会话

#### Scenario: 飞书触发的模型备用切换说明回到原 chat
- **GIVEN** 用户从飞书发消息，本轮因主模型不可用改用了备用模型
- **WHEN** Gateway 投递切换说明
- **THEN** 原飞书 chat 收到与 Web IM 等价的一句 Bot 文本
- **AND** 内部 IM 影子会话出现同一说明

#### Scenario: 内部 IM 触发的模型备用切换说明不回写飞书
- **GIVEN** 用户从内部 Web IM 发消息导致改用备用
- **WHEN** Gateway 投递切换说明
- **THEN** 说明只出现在该内部 IM 对话
- **AND** 飞书原 chat 不收到对应消息

#### Scenario: 飞书触发的 self-evolution review 通知回到原 chat

- **GIVEN** 用户从飞书发送消息，随后后台 review 确实成功写入 memory、skills 或两者
- **WHEN** `self_evolution_review` 通知产生
- **THEN** 原飞书 chat 收到一条简短、非第一人称的 Bot 通知，说明更新对象
- **AND** 内部 IM 影子会话保留同一结果的结构化 system notice
- **AND** 两端都不显示具体沉淀内容、review prompt 或工具过程

#### Scenario: 内部 IM 触发的 review 不回写飞书

- **GIVEN** 用户从内部 IM 或飞书影子会话发送消息，随后后台 review 确实成功写入 memory、skills 或两者
- **WHEN** `self_evolution_review` 通知产生
- **THEN** 通知只显示在当前内部 IM 对话
- **AND** 飞书原 chat 不收到对应消息

#### Scenario: 无成功写入的 review 不发送更新通知

- **GIVEN** self-evolution review 无需写入、只执行 list/read，或 mutating tool 执行失败
- **WHEN** 本轮后台 review 结束
- **THEN** 用户不收到 raw `Nothing to save.` 或工具过程
- **AND** 飞书与 shadow IM 均不产生 self-evolution update notice

#### Scenario: 其他内部运行态事件仍不外发

- **WHEN** Agent 产生 thinking、工具过程、token 使用量、debug/status 或其他未单独产品化的 system notice
- **THEN** 这些事件不作为普通消息发送到飞书

## REMOVED Requirements

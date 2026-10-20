# Code Review: bugfix-621-pa-feishu-owner

## Round 1

- Reviewer: `/root/static_review_621`，未参与实现。
- Mode: `full`。
- Frozen range: `732ba8a2c06c072f8a5b8ad74ad08d43d6cb34a9..fad8b8355716a73165bf0d688644dfbf0cc84dde`。
- Checkout: `unit/bugfix-621`；审查前 HEAD 与冻结版本一致，只有既有 untracked `output/`。
- Scope: 完整实现与测试 diff、incident/design、两份 corrected delta，以及真实调用方。未改源码、测试、设计或运行产物，未重跑全量测试。
- Verdict: **PASS — no actionable findings**。

```json
[]
```

## Reviewed behavior and evidence

| 风险 | 核对结果 |
|---|---|
| 可信主人判定与原始授权 | `apps/im-server/src/personal-agent.ts:80` 按 binding 的 owner/node/agent、enabled channel、app 和持久 owner_open_id 验证飞书来源；`:95` 还要求 direct 目标。`:101` 用真实 sender_source_id 区分主人、其他人和群背景；admit、ownerMessage、authorization 共用该判定。非主人文本自称不影响结果。`personal-sources.test.ts:45` 回归主人授权、伪称、群与 owner 变化；已有 Web 身份用例继续保留。 |
| 主人私聊免披露审查的实际出口 | `personal-actions.ts:101` 的 owner_private 在 source write access 与 transport 验证之后返回；`personal-assistant.ts:170` 才调用 SDK dispatch。其他目标保留 prepare/review/commit/complete；群仍由既有 audience 不可证明检查拒绝，不新增群发送能力。`personal-disclosure.test.ts:60` 验证 owner 改绑/disabled 时不再豁免。 |
| Inbox shadow 回复是否真正发送飞书 | `personal-assistant.ts:114` 在选 transport 前通过按 Agent 隔离的持久 alias 归一化；`external.ts:146` 取本地 ExternalChat 的真实 chatId。`personal-assistant.test.ts:64` 验证 shadow→external 与 Web canonical 两条出口，external 回归断言平台 message_id。 |
| 单入口、持久去重、来源保留 | `external.ts:91` 的 PA 输入只 mirror；`global-agent.ts:151` 通过 observation 使用中央 message ID 进入原主会话，附 channel、原 sender 与 timezone；`inbox.ts:116` 向模型暴露 channel。`external.test.ts:149`、`global-agent.test.ts:309` 验证不走直接 receive、重放一次接入及原来源字段。首来信绑定仍由未改动的 `packages/channels/src/feishu.ts:85` 执行并经 ManagedChannels 持久元数据同步。 |
| 历史输出失败与新输入隔离 | 当前输入在 `external.ts:94` 单独 await mirror，而非旧混合 flush；`:245` 的逐 frame 错误隔离保留失败 frame，继续其他投影。`external.test.ts:149` 注入旧输出投影失败后仍镜像新输入，并核对重放不再镜像/直入。 |
| 发送结果与重试 | 复核 `external.ts:188` 与 `external-store.ts:22`：confirmed 不再发，sending 崩溃恢复为 unknown，unknown 不盲重发；owner_private 仍经过同一个 dispatch 和本地状态机。`external.test.ts:122` 保留实际 provider 响应与未知结果跨重启保护。 |
| 范围与架构 | 没有新增 DSH import、运行时 fork、第二个执行循环或跨包相对依赖。身份留在 IM，实际平台目标与回执留在 PA/Channels，Global 使用既有 RuntimePort、Inbox、schedule。默认指令仅影响新建 PA，既有 custom_prompt 不回填。 |

## Validation and limits

- 复用 caller 在冻结实现上的聚焦结果：`/tmp/bugfix-621-focused.log`，7 files / 100 tests passed；typecheck 与 build 分别见 `/tmp/bugfix-621-typecheck.log`、`/tmp/bugfix-621-build-fixed.log`。读过结果并核对新增及受影响测试的断言，没有重复全量运行。
- 独立补充：以 `node --import tsx --input-type=module` 直接导入当前 `ExternalChannels`/`NodeStore`，模拟 PA 中央不可达，断言 receive 拒绝但输入保留、恢复两次及重复接收同一消息只有一次 mirror、直接 receive 为 0；结果 PASS。此为控制 seam 证据，不替代真实 Feishu 入站。
- 真实飞书收发、到时提醒、Web 主人私聊及 CI 退出证据在本报告写入时仍由 caller 执行；本 code review 没有把运行中旅程当成通过。门禁完成度另见 `verification.md`。

## Round 2 — evidence closure

- Frozen implementation unchanged: `fad8b8355716a73165bf0d688644dfbf0cc84dde`。当前 HEAD `a1415206ed18493df775ab3b4410617894aaf425` 仅新增独立产品回归报告；本轮未扩大或重复 full code review。
- 读取最终 `regression.md`、更新后的 `M1-fix/evidence/validation.md`、真实平台/Web/持久快照与本地 CI 原始结果，已关闭 verifier 唯一的 C1 完成度缺口。具体交叉核对见 `verification.md` Round 2。
- Verdict retained: **PASS**；findings retained: `[]`。真实飞书两次一次性提醒、Web 原渠道回读、相同 PA 主 session / 单次接入均有独立实测和直接证据；后端首轮单项超时及不改代码后的成功复跑均如实保留。

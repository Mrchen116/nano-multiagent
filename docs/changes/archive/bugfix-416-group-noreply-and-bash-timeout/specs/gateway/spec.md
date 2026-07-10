# gateway delta — bugfix-416

> 本 unit 对长青契约层 `docs/specs/gateway/spec.md` 的增量。lite 模式无 design-author 产出，
> 由 orchestrator 据实际代码补（§7.0 兜底）。两条均为 bugfix 修复后新增的对外可观察行为。

## ADDED

### Requirement: 群聊只在被 @提及 / 回复 Agent / 控制命令时触发 Agent

#### Scenario: 群聊 Agent 互相 @ 的 fan-out 回复输出 NO_REPLY 时不发言
- **GIVEN** 群聊里 Agent A 的回复 @ 了 Agent B,把 B 拉起(agent-to-agent fan-out),或某 Agent 的
  后台任务在群聊会话产生回复
- **WHEN** 被拉起的 Agent 判断无需接话,输出 `NO_REPLY`(或心跳静默 token `HEARTBEAT_OK`)
- **THEN** Gateway 对该 fan-out / 后台投递同样抑制,用户在群里看不到 `NO_REPLY` 字面量,该消息也不落库

> 缘由(#107):原仅主同步回复路径做 NO_REPLY 抑制,fan-out（other-origin / background relay）两路
> 漏抑制致字面量泄漏。修复把抑制收敛到 pipeline 单一守卫,三条投递路径统一过。

### Requirement: run 进入终态时对在飞 tool_call 按原因收口

#### Scenario: 在飞工具收口仍保留其原始调用参数
- **GIVEN** 某轮有一个工具在飞,其开始执行时已带出原始调用参数(如 bash 的命令与 description)
- **WHEN** run 进入终态对该在飞工具收口(看门狗超时或异常终止)
- **THEN** 下发的终态仍携带该工具的原始调用参数(仅状态改为失败 + 标注原因),消费者据此能看出
  是哪条命令被中断,而非只剩工具名

> 缘由(#111):原 reconcile 收口硬塞空 input,丢失命令/description。修复改为 tool_start 记录完整
> 调用、收口时重发原 input。

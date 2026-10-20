# Verification Report: feat-623-pa-message-context

> Validation snapshot: `2f789f62a → f036aedd5e7bc972a413989474f166a8d49db752`

- review_round: `1`
- verification_mode: `full`，并核对全部 `corrected-delta`
- validated_at / effective_through: `f036aedd5e7bc972a413989474f166a8d49db752`
- executed_base / effective_base: `2f789f62a`，包含显式依赖 PR #371
- requires_full_verification: `false`（本轮已 full；修复后按实际影响局部复验）

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实现已落地；来源撤销后恢复新背景通知不满足退出标准；本地全量通过，真实产品验收 pending |
| Correctness | 0 CRITICAL / 1 WARNING / 0 SUGGESTION |
| Coherence | 事实、投影、同一 Inbox、公开运行时接纳和 guard 设计整体遵循；背景撤销生命周期存在实现缺陷 |
| Verdict | **fail：先修复 WARNING；尚不能声明 M1 全部完成** |

## Completeness

- M1 的 IM/PA/DSH 接线、数据迁移和固定指导均存在。简化流程无需虚构 tasks/progress。
- spec 的 5 个 Requirement、16 个 Scenario 均有实现映射；涉及模型理解与真实投递的结论仍等待独立产品证据，不能由 fixture pass 代替。
- 读取 `SPEC.md`、current gateway personal/global specs、current IM personal-agent、testing/evidence 规范；本次新增依赖、调用方向未越过架构边界，没有 runtime fork、第二循环或新用户调度器。
- Prototype / Reference：N/A，无客户端修改。
- M1 明确要求“仅背景最高序号被撤销后新来源收件”。SQL 序号不复用已有测试，但 GlobalAgent 在撤销清空候选后留下等待标志，未达到整个生命周期的退出标准。
- 尚待汇总的产品门禁：六组真实模型意图、真实十分钟累计、提前引用背景、真实飞书回复/提醒和 Web 连续性。这里只记 pending，不将缺少这些证据混同于已确认实现缺陷。本地全量已在固定 head 通过；远端 CI 为后续交付门禁。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 / 证据 | 状态 |
|---|---|---|---|
| 真实身份：主人直接交办、群内交办、冒称 | `apps/im-server/src/personal-agent.ts:114`、`:126`、`:230`；`personal-assistant.ts:44` | personal-sources 的 Web/飞书身份、membership、mention/reply；personal-assistant 非主人审核 | 代码/fixture covered；模型与真实渠道 pending |
| 普通群更新 | `global-agent.ts:89`、`:106`；`attention.ts:4` | personal-attention:81；既有 Global tests | covered |
| 观察主人指令/承诺及他人请求不自动成为任务或警告 | `personal-assistant.ts:60`；`global-agent.ts:89`、`:191`；DSH personal-security/policy 固定规则 | personal-attention:38、:81；授权上下文 fixture | 宿主边界 covered；六组语义结果 pending |
| 基于已有授权继续协助 | `personal-agent.ts:230`；`personal-actions.ts:62`；DSH reviewer policy | personal-sources:32；personal-disclosure:212 | 证据和 guard covered；模型判断 pending |
| 首批与连续到达、后续批次/空态 | `inbox.ts:39`、`:77`、`:98`；`global-agent.ts:143`、`:174` | inbox:123；personal-attention:38、:68 | 通常路径 covered；撤销后重建批次 WARNING |
| 忙碌合并、直接更正及时读取 | `global-agent.ts:115`、`:188`；DSH `index.ts:581` | personal-attention:54；global-inbox-native:9、:75 | covered（native fixture，非真实模型） |
| 重启与来源撤销 | `inbox.ts:77`、`:89`、`:105`；`global-agent.ts:160`、`:198` | inbox:123、:144；personal-attention:108；本轮直接复现 | **WARNING W1** |
| 提前引用背景 | `global-agent.ts:110`、`:211`；`inbox.ts:153` | personal-attention:68、:92 | 接线/可读/已消费取消 covered；真实模型 pending |
| 只提醒未读完 | `inbox.ts:175`、`:198`、`:255` | inbox 既有碎片、图片完整摄取及新关系分页测试 | covered |
| 飞书原地回复与提醒、Web 连续性 | 未改变 bugfix-621 外部发送路径；global-agent observation 接线 | personal-sources/disclosure 的真实身份 fixture；global-agent 的飞书重放一次 | fixture covered；平台实际回执 pending |
| 群/他人私聊披露限制 | `personal-actions.ts:50`、`:62`、`:70`、`:77`；`personal-agent.ts:95` | personal-disclosure:8、:28、:60、:103、:212 | covered |

## Coherence

| design 决策 | 遵守情况 | 证据 |
|---|---|---|
| 身份独立于意图；准入事实由 IM 核实 | 是 | personal-agent:114、:177；personal-assistant:44 |
| 按用途显式投影，页级共享来源，先投影再持久化与 toolReferences | 是 | inbox:120、:175、:198；global-agent:280、:292 |
| 历史接入事实不被当前 membership 覆盖；访问仍在线重验 | 是 | 新事实只在接收/legacy classify 写入；global-agent:167、:280；IM Work sourceAllowed |
| 背景与直接通知共用 wake 互斥，runtime 原子 onlyIfIdle | 是 | global-agent:115、:138、:191；DSH index:587 |
| timer/idle/recover/stop；空候选取消后后续有效更新仍工作 | **有偏离 W1** | global-agent:179–182 的空候选退出留下 waitingForIdle |
| 通知 ACK 与消费分离，序号保留在途/已通知水位 | 是 | inbox:43、:77、:98、:255 |
| 完整授权上下文和 guard 失效域分离；旧 permit 重审 | 是 | personal-agent:230–244；personal-actions:62–64；personal-disclosure:212 |
| 不覆盖 custom_prompt；不重写历史 reads | 是 | personal-agent-defaults 初始值；Inbox classify 只改 inbox，不改 reads |

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

**W1 — 撤销最后候选后，后续背景通知无法重新定时。** 契约：`spec.md:93`、delta gateway personal-agent 的“忙碌与重启/提醒与消费独立”，以及 `design.md:146`、`:216` 的来源撤销及新来源收件退出标准。实际：`packages/personal-assistant/src/global-agent.ts:179` 添加 waitingForIdle，`:182` 在最终来源复核清空候选后直接返回；`:146` 此后始终排除该 agent。PA 已空闲，没有自然 idle 转换来恢复。通过真实 GlobalAgent/InboxStore 公共入口和模拟时钟重现：新批次有 `dueAt=1200001, unread=true`，但 `timers=0`，过期 `submitted=0`。方法和输出见 [code-review.md](code-review.md)；一次性脚本 `/tmp/feat623-review-empty-batch.mts`。建议在空候选路径清除等待标志，并在既有 personal-attention 风险 owner 内覆盖“到期来源复核清空 → 新有效 observer → 到期通知”；不应通过改 spec 规避。

### SUGGESTION（可以修）

无。

## 测试与证据

- 固定 head 独立执行 7 个相关 suites：inbox、personal-attention、global-agent、personal-assistant、IM personal-sources/disclosure/agent；**107/107 pass**。完整命令见 code-review.md。通过结果没有覆盖 W1。
- 复用 `M1-context/implementation.md` 的测试策略与 `M1-context/im-identity-evidence.md` 的身份/授权 fixture：原风险 owner 被扩展或重写；新 personal-attention 文件归属 PA 专有通知生命周期，没有将真实模型验收脚本加入永久测试。
- 核实 `/tmp/feat-623-native.log` 的 **2 suites / 7 pass**，对应真实锁定 DSH 的 next-step steer、onlyIfIdle 和 PA busy 合并；不重复有效 native 全量。
- 复用主 Agent 已补入 `M1-context/implementation.md` 的固定 head 本地全量证据，并核对日志：backend **106 suites/469 tests**、frontend **100 files/936 tests**、pytest **62 passed**，build/typecheck/ruff/docs-check 全通过。未重复有效全量；远端 CI 仍属后续交付门禁。

## Corrected Delta Reconciliation

本轮逐条核对全部 3 份 delta；未替作者修改 spec/design。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| gateway/personal-agent：合并历史、新消息和一致主人身份 | personal-agent:114、:177；Work:673；inbox:175 | personal-sources:32、:52、:122；inbox:99 | aligned |
| gateway/personal-agent：观察接入不是请求/控制/自动警告 | personal-assistant:60；global-agent:89、:106 | personal-attention:38、:81；personal-assistant risk tests | aligned |
| gateway/personal-agent：来源控制及观察文本不能控制来源 | personal-agent:57、:223 | personal-sources:32、:122 | aligned |
| gateway/personal-agent：联系人限制和撤销 | personal-agent:68；personal-assistant:53；inbox:205；既有 policy.changed | personal-assistant 风险重写及 IM incident/block tests | aligned |
| gateway/personal-agent：十分钟首批/后续、忙碌/重启、提前读取、通知消费分离和撤销 | inbox:39–115、:255；global-agent:143–208 | inbox/personal-attention/native；W1 直接复现 | **implementation-mismatch**（撤销后新批次失活） |
| gateway/personal-agent：原始授权身份和对话上下文 | personal-agent:230；personal-actions:62；DSH personal-security | personal-sources:32、:122；personal-disclosure:212 | aligned |
| gateway/global-agent：及时触发、普通群配置、PA observer 例外 | global-agent:106、:115、:191 | global-agent、personal-attention:54、:81；native:9、:75 | aligned（背景撤销生命周期问题归上行） |
| im/personal-agent：主人先回复；观察双方背景而不自动接任务/警告 | PersonalActions last_owner_message_id；personal-assistant:60；DSH 固定规则 | personal-disclosure:28、:212；personal-attention | aligned；真实模型旅程 pending |

### Uncovered Observable Behavior

未发现 unit diff 中需要另加 Requirement 的遗漏。guard_messages、legacy 未读重准入、明确群控制、字段精简/分页是现有 delta 与 design 的实现细化；不因 W1 静默收窄契约。

Outcome: **implementation-mismatch**。

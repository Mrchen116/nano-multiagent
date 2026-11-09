# 模型前置 Task 证据增量设计审查

## Round 1

- reviewer: `/root/perf_design_gate_runtime`
- target: `perf-747-task-evidence-incremental` 首文档、定稿方案与 M1 骨架，代码基线 `04a07bb2`
- review_mode: `full`
- mode_reason: Gate 2 首轮，涉及 native 证据、持久确认、共享授权与模型 Context
- started_at: 2026-11-09T21:33:19+08:00
- completed_at: 2026-11-09T21:34:44+08:00
- duration: 85 秒
- Verdict: **Issues Found**
- 0 CRITICAL / 3 WARNING

### Coverage 与证据

[DSH 组装](../../../packages/dsh-integration/src/index.ts#L254) 在 Prompt 装配及 pre-step 前放置 Task Context 准入，再由 [Node](../../../apps/node/src/main.ts#L393) 接入 PA TaskContext。原始内容及源权限仍由 [中心授权范围](../../../apps/im-server/src/gateway.ts#L464) 和 [会话消息索引](../../../apps/im-server/src/messaging.ts#L636) 决定。DSH 负责从原生持久事件提取可归属到实际模型轮的证据，Gateway 负责 Inbox 与 NodeStore 的持久对账。增量确认适合放在既有 RPC，授权合并适合放在已有 per-Agent 同步所有者内。旧模型及业务契约由 [Gateway Task spec](../../specs/gateway/task-graphs.md#L239) 维持，不要求 canonical delta。

Agent Context 设计模式覆盖正常原文（含固定聊天来源和认证真人停止事实）、失权后仅收到必要撤销事实、授权故障时保留独立工作。影响发生在模型和审批读取实际组装内容之前，需要观察实际出站输入而非 RPC 成功。性能验证以同一历史负载的冷恢复、热步及并行同步为边界，分别量每步扫描、字节与调用。尚未运行实现或模型。

### Issues

- **R1-W1 — 定义可推进 native cut 的对账确认。** [TaskContext.commit](../../../packages/personal-assistant/src/task-context.ts#L87) 目前返回 void，忽略缺失或其他 session 的行、非法消费位置、摘要不匹配等证据。[NodeStore](../../../packages/personal-assistant/src/store.ts#L31) 的查询只返回待处理的映射，不能仅以未出现区分“已在此前提交完成”和“仍未匹配”。[设计](design.md#L5) 应确定单页确认边界以及准备、失败或已结算的回执含义，使 ACK 丢失时可重送，不能让部分未结算的页被越过。说明当前驱动从历史构造的 consumed 去重事实在进程恢复和热步中由谁保留，并覆盖同一页内有效与未匹配证据、跨开放轮页界、对账写入之间故障和 ACK 丢失。消费确认不代表本次模型步的来源授权。
- **R1-W2 — 共享授权 cut 与每条原文的唯一会话领取需要分别裁决。** [Inbox](../../../packages/personal-assistant/src/inbox.ts#L285) 的候选是 Agent 范围的，[TaskContext](../../../packages/personal-assistant/src/task-context.ts#L81) 随后为会话写准备映射，[NodeStore](../../../packages/personal-assistant/src/store.ts#L23) 的 upsert 会把仍处于 prepared 的同一消息改绑到后到会话。共享一个同步完成通知会让两个等待者相继返回同一候选，前一个在真正持久消费前就可能失去可对账映射。应明确匹配来源的会话何时取得、释放或移交领取，且 authority cut 只分享权限同步结果。验收应模拟两个会话同时竞争同一原文、旧会话重放和 cut 后撤权，观察模型请求中的原文和丢弃结果。
- **R1-W3 — 收口持久事件读取接口和故障时的消费顺序。** [现有驱动](../../../packages/dsh-integration/src/task-context.ts#L12) 全量扫描 snapshotEvents，在 system-prompt/assemble 更新来源可用性，在 pre-step 丢弃已领取的失权输入，并可能允许独立输入继续。设计的“只读增量”和“冷前缀按页”尚未定位 DSH 公开读取/事件接口及持久 barrier，也没说明冷对账分批如何与正常 prepare 及这两个模型钩子衔接。应选择公开的 bounded event 路径或增量订阅，区分“RPC 分页”与“原生读取每步重新全量 materialize”，明确不可用时不得交付未核实 Task 原文或推进确认，同时保留既有独立输入与只提示具体受影响任务的行为。fixture 需分别核实模型/审批实际收到的内容、已领取后撤销，以及冷失败与恢复后的首个有效模型步。

## Round 2

- reviewer: `/root/perf_design_gate`
- Verdict: **Issues Found**，0 CRITICAL / 3 WARNING
- R2-W1：区分已消费、终态撤销和可重试的未匹配，以 Inbox 持久 ingestion 修复两库之间的失败。
- R2-W2：明确重置后旧会话的准入、领取移交及已经被动排入原生 Inbox 的副本。
- R2-W3：证据确认必须检查 flush 布尔返回，保留读取和对账失败下的独立任务准入。

## 作者处置

- W1 在方案中细化确认结果、身份和持久 ingestion。
- W2 落到已有 `/new` 停止和重置事务以及 pre-step 领取过滤，覆盖被动副本。
- W3 要求成功的持久屏障，当前授权和消费对账分别判断，并保留独立准入。

## Round 3

- reviewer: `/root/perf_design_gate`
- review_mode: delta，复核 R2 三项
- Verdict: **Approved**，0 CRITICAL / 0 WARNING
- 关闭按输入与 seq 的确认、Inbox ingestion、单线程重置后的准入与领取交接、以及持久屏障失败和独立工作保留。实施需观察旧 prepare 先取得 authority cut、随后被 reset 时的被动副本与晚到 ACK。

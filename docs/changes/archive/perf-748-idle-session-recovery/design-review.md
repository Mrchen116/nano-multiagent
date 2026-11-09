# 单线程会话按义务恢复设计审查

## Round 1

- reviewer: `/root/perf_design_gate_runtime`
- target: `perf-748-idle-session-recovery` 首文档、定稿方案与 M1 骨架，代码基线 `04a07bb2`
- review_mode: `full`
- mode_reason: Gate 2 首轮，涉及生产启动、持久回执、原生未投影事件及隔离验证
- started_at: 2026-11-09T21:34:44+08:00
- completed_at: 2026-11-09T21:36:16+08:00
- duration: 92 秒
- Verdict: **Issues Found**
- 0 CRITICAL / 3 WARNING

### Coverage 与证据

[Node 冷启动](../../../apps/node/src/main.ts#L132)、[Relay ready](../../../apps/node/src/main.ts#L291) 及 [update release](../../../apps/node/src/main.ts#L464) 都会调用 [SingleThread.recover](../../../packages/personal-assistant/src/single-thread.ts#L211)。现状对每个启用且符合通道范围的绑定调用 ensure 和 reconcile，后者调用 observe。新入站已有持久写入后按需 ensure 的入口。PA 应保有本地待办和投递的筛选与对账，DSH integration 应保有原生持久事实的判断，Node 应安排 scope、恢复优先级和并发。复用既有持久状态和调和链路，不需要另一套执行控制或持久消息正文。

性能设计以千个 idle、少量真实义务、冷启动及 reconnect 的时间、ensure 次数、读取量和堆为对照，方法合适。恢复旅程需分别断开中心连接与杀死执行进程，观察原输入和原聊天结果；性能对照要等未知补核也完成，避免把全量读移出就绪时钟后漏计。路由、身份、停止与 Schedule 的用户契约维持，若必需义务仍在 ready 前收敛，无 canonical delta。方案无新增 UI。未执行运行验证。

### Issues

- **R1-W1 — 选择实际可覆盖崩溃窗口的冷发现入口。** [设计](design.md#L6) 尚未确定原生持久证明与“未获证明的旧绑定”的边界。DSH 原生 Schedule 先将 inbox splice flush 到 Session，再写 Schedule 交付回执（安装的 `@deepseek-ai/dsh-schedule` 0.2.1-alpha.1，`lib/types/runtime.js:117–139`）；[Gateway 也要等 observe 后才登记原生输入](../../../packages/personal-assistant/src/store.ts#L400)。因此 receipt 目录和 Node 待办同时为空仍可能有有效原生输入，新版本也有此窗口。[schedule.evidence / schedule.wait.inspect](../../../packages/dsh-integration/src/index.ts#L853) 和 [session.observe](../../../packages/dsh-integration/src/index.ts#L653) 会通过 agent 访问激活 Session，[Task 状态读取](../../../packages/dsh-integration/src/task-execution.ts#L254) 只观察 live Agent。请指定通过哪项 DSH 公开读取／可信持久检查点识别原生待办，怎样校验无变化、未知、文件不存在和读取失败，以及新旧无证明绑定何时触发只读补核。验收需包含进程退出在 native flush 之后、Schedule/Node 回执之前，以及 Task 原生持久触发，证明补核最终发现真实义务且分类不激活空闲会话。
- **R1-W2 — 恢复排序需落在真实启动屏障与重连并发上。** [RuntimeSupervisor](../../../packages/dsh-integration/src/client.ts#L148) 在 launch 中等待 onReady，[Node](../../../apps/node/src/main.ts#L132) 在持久恢复后写 ready，而 relay 回调又能发起独立恢复。[现有启动契约](../../specs/gateway/service-lifecycle.md#L96) 要求必需持久恢复后才确认 ready。[DSH ensure](../../../packages/dsh-integration/src/index.ts#L1050) 会恢复原生 Agent 并触发 Task poke，[Task 停止契约](../../specs/gateway/task-graphs.md#L146) 禁止恢复越过未确认的 stop。明确冷启动及 reconnect 的恢复所有者、已知义务与只读补核分别在哪条就绪边界、重复恢复怎样合并，以及停用、停止、新入站或 active channel 范围变化时如何裁决补核后才激活的候选。验证同时触发 ready/reconnect、在补核中进新输入、停用或切换通道，观察无重复且不越过未决停止。
- **R1-W3 — 指出遗漏回执与审批分别从何恢复。** [现有 deliveryInputs](../../../packages/personal-assistant/src/store.ts#L371) 特意包含交付已终结但 relay receipt 缺失的输入；单以“未终结交付”选候选会漏。与此同时 [SingleThread](../../../packages/personal-assistant/src/single-thread.ts#L25) 只在内存保存待审批和决议，[DSH 等待的请求](../../../packages/dsh-integration/src/index.ts#L310) 也只在活进程内，[持久审批 audit](../../../packages/dsh-integration/src/policy/approval.ts#L29) 是裁决历史，不是可恢复的等待请求。请落实候选的 receipt 定义，并区分同进程重连能继续的审批和冷启动需按中断/到期收敛的审批，定位已有 IM 或 runtime 状态责任。测试分别覆盖终态交付回执丢失和两类审批，确认不会重新创建交付或把已中断审批标为可回答。

## 作者处置

- W1 在 OwnedSessions 共用的可写 root admission 前标记持久 generation，旧绑定用公开 persistence 只读尾探针补核。只在旧 generation 无写者且切面已对账时清除，避免被并发激活覆盖。
- W2 明确 partition onReady 与 reconnect / release 的共享恢复所有者、stop fence、就绪屏障以及生命周期和通道重新裁决。
- W3 选择终态且缺终态 receipt 的输入，并区分同进程审批和旧进程已消亡的等待。

## Round 2

- reviewer: `/root/perf_design_gate`
- Verdict: **Issues Found**，0 CRITICAL / 2 WARNING
- R2-W1：原生 fork 先创建、Node 后绑定，须明确无覆盖标记的处理。
- R2-W2：主动更新 prepare 原有全量 drain，须区分更新准备成本与重启／重连范围。
- 作者将任何未标记 binding 纳入未知探针，并记录更新 prepare 的独立成本与后续首次冷启代价。Ready 必需恢复失败不以 log-only 汇总吞掉。

## Round 3

- reviewer: `/root/perf_design_gate`
- review_mode: delta，复核 R2 两项
- Verdict: **Approved**，0 CRITICAL / 0 WARNING
- 无标记绑定一律冷核对，仍可写不能记已核对；单独记录更新 prepare 全量 drain 并计入后续首次冷启。必需恢复失败不会被写成 ready。

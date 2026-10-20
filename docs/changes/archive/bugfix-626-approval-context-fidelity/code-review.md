# Code Review: bugfix-626-approval-context-fidelity

## Snapshot

- reviewer: `/root/static_review`，未参与本次实现；兼任独立 verifier，各自单独报告。
- review_mode: `full`
- executed_base: `b5c1e97901467767a32efc66e83869181242f477`
- validated_at: `40cd54ddf81c5c7262d1d2f69cb83b5dd3287bad`
- reviewed_at: `2026-10-20T15:14:15+08:00`
- scope: `git diff b5c1e9790..40cd54ddf` 的全部产品源码、规则资产与测试；核对时这些路径相对冻结提交无后续修改。实施记录和已通过 Gate 2 的 incident/design/delta 用于理解契约。
- upstream: 本地 Codex HEAD 已核实为 `806d9732c974bc8a51b8317c1bd8985544fe627c`；DSH 锁定 `0.2.1-alpha.1`。

## Findings

```json
[]
```

无存活的 CONFIRMED / PLAUSIBLE finding。该结论为代码审查通过，不替代产品验收、最终 canonical 归并或 CI。

## Coverage

- 普通审批：`approval.ts:127` 不再调用 `pa.authorization`；`types.ts`、`classifier.ts`、`sources.ts` 和 Codex action 均移除其传递与注入。有效历史仍来自原生 `deriveMessages()`，没有数据库替代通道。
- CC：固定 `cc-2.1.267-nano-v1` 规则资产、两阶段、fastpath、失败与人工/无人值守分流未变；默认 sources 不走新增 Codex normalization。原 Inbox/实际发送回执、PTC 有效根和恢复来源保护保留。
- Codex profile：对照上游 `guardian-context/src/profile.rs`，User/ManualApproval 成本先计入 message allowance；仅成功保留的非用户项占 40 条；已选 ProtectedAssistant 与最近已选中的五条工具为 required。
- Codex admission：对照 `guardian-context/src/enforcement.rs`，完整 action、notice、framing 计入预算；先排除独自亦无法容纳的 optional，再按旧项优先剔除；只有历史体可在 recovery 缩短，来源及首尾保留。DSH 无 phase，当前来源只有 ProtectedAssistant 而无普通 Commentary 项，故现有 optional 都是工具，不存在漏实现的同级跨种类排序。required 放不下明确 unavailable。
- Codex lifecycle：delta 使用 preserve，不足则从当前父有效历史 rebuild；fresh/rebuild 使用预算恢复。上游 `input_budget.rs:223` 对 fresh parent checkpoint 同样允许历史恢复；本实现无任意 0.65 预算乘数。既有 fork、父历史/配置失效、90 秒和取消路径保留。
- 来源及去重：当前和继承路径均在 cursor 前按 Inbox message 规范化，页级事实与 sender、live/restored 来源保留；同一 call id 的 generic result 正文去重，不合并不同调用。空页、错误仍保留结果；agent/system 消息仍为 Tool retention。
- 输出：资产与上游 `ext/guardian-reviewer/src/assessment.rs` output prompt 对照；parser 的 bare/embedded JSON、默认 risk/authorization/rationale 和非法类型处理一致，未加入风险二次判定。
- 宿主适配：未新增 private DSH import、运行循环或任意 shell 调查；受限 stat/read/list 与无 final-output schema 参数的边界在 design/实施记录中披露，未声称上游任意任务行为等价。
- PA：独立入站和最终提交披露代码无 diff；`personal-assistant.ts`、`personal-actions.ts`、`personal-security.ts` 的本人豁免、observer 背景、真实受众和原授权取证仍在。

## Validation evidence reused

- `/tmp/nano-626-green-focused.log`：23 tests / 4 files passed，实施方提供的冻结源码窄测；核对测试覆盖包含原生 PA 普通动作、来源与生命周期。
- `/tmp/nano-626-final-context.log`：15 tests / 2 files passed，新增 oversized optional 与继承规范化保护。
- `/tmp/nano-626-full-tests.log`：`vitest run`，106 files / 476 tests passed，2026-10-20 15:11:34 开始，106.16 秒。已读取完成结果，未重复全量。
- 窄测和全量均为 fixture/回归证据；真实模型产品旅程由另一独立 reviewer 执行。

后续只追加验收证据、归并已核对的 delta 或归档路径，不改变上述产品树时，可以保留本结论；源码/测试变化或 main 增量须由收尾 owner 判断影响后复验。

## Round 2 — 定向证据与 final sync 复核

- review_mode: `delta`；reviewed_at: `2026-10-20T15:24:24+08:00`。
- executed_base / effective_base: `ff5fbc8f52ca1f4fb098f1e62d906c845895f990`。
- validated_at / effective_through: `7dce653ef393e5fac8cb242b5cf92ddeff363a20` 加当前 canonical/实施证据文档差异；产品源码、测试、规则资产仍与 `40cd54ddf` 相同。
- 范围：新增 `M1-fidelity/production-replay.md` 的私有驱动与输入/结果结构、canonical 归并、main 增量及本地证据闭环。未再次调用模型或原动作，未在报告保留聊天正文。

```json
[]
```

已独立比较两个截点与私有原始 session：分别为 seq 6224/6359 之前的完整事件前缀，header 和待审 tool/call 参数完全相等。两个输入文件 SHA 与文档一致。只通过 DSH public `Session.create` / `deriveMessages()` 重算，得到 125/177 条有效消息；两个前缀均包含原有压缩事件。不是把原始全事件转成消息全文提交审核。

驱动分别只调用 `classify` / `CodexApproval.review`，不 submit/followup 原 Agent、不调用原动作 executor，拒绝 product.call 和主 Agent request。Codex 自己的 reviewer followup 是审核宿主必需路径。两 runtime 的真实请求/结果分别为 allow，工具尝试计数 0，无 blocked-tools 文件。`actionExecuted=false` / `mainAgentContinued=false` 是驱动输出的固定字段，不能单独当作独立遥测；与已核对的无执行/无续跑调用结构合看，足以支持这两次仅审核、未执行原动作的结论。

Inbox live 标记按本次生产进程启动时间从截点内已完成的直接 Inbox 重建，是显式宿主假设，并非失败瞬间内存快照。检查两前缀启动后没有 PTC Inbox，未发现漏掉该类调用的具体差异。不能据此声称逐字节重现原审核请求或任意时间点的内存状态。原始目录权限为 0700；聊天正文未进入仓库报告。

canonical 新增 Requirement 与三个 Scenario 原样包含已审 delta，未改变授权规则或 PA 独立消息检查。`b5c1e9790..origin/main` 只有 feat-625 `design-review.md` 新增 135 行；final sync 没有产品树增量，Round 1 代码审查保留有效。独立产品报告与本地 CI 闭环见 verification Round 2；当前可以归档并创建 PR，远端 CI 仍须在 PR 上通过。

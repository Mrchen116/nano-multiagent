# feat-822-memory-capacity-and-gating: Review

## 范围与版本

- 本次问题与需求/设计位置：
  - [spec.md](spec.md)、[design.md](design.md)、[design-review.md](design-review.md)
  - 契约增量：`specs/gateway/{agent-capabilities,personal-agent,global-agent}.md`
  - 实现与测试：`packages/product-contracts/{src/knowledge.ts,tests/knowledge-dreaming-config.test.ts}`、`packages/dsh-integration/src/{index.ts,evaluation.ts,evaluation/runtime.ts,evaluation/dolphinbench-runtime.ts}`、`packages/dsh-integration/src/knowledge/{memory-documents.ts,document-memory.ts,dreaming-state.ts,dreaming.ts,dreaming-agent.ts,dreaming-prompts.ts}`、`packages/dsh-integration/tests/{memory-capacity-and-gating.test.ts,proactive-memory-hygiene.test.ts,proactive-dreaming-feedback.test.ts}`、`packages/personal-assistant/{src/proactive-coordinator.ts,assets/skills/nano-memory/SKILL.md,assets/skills/nano-proactive-care/SKILL.md}`
- 实际 `executed_base` / `validated_at`：
  - Round 1：`7f0e039325ae0a5526b7b66427da32174245586e`（`origin/develop` merge-base） / `92811469fccd975724cbcb9fb671eab7537b5490`
  - Round 2（`closure` + `corrected-delta`）：`7f0e039325ae0a5526b7b66427da32174245586e` / `857ab70b1e9511922546e0e9343420c50984b5a4`（`pre_fix_head: 92811469fccd975724cbcb9fb671eab7537b5490`）
- 最终 `effective_base` / `effective_through` 与保留依据：
  - `effective_base`: `7f0e039325ae0a5526b7b66427da32174245586e`（`origin/develop`）
  - `effective_through`: 归并 canonical `docs/specs/gateway/*.md`、写入本报告并归档 change unit 后的交付提交；`857ab70b1` 之后仅执行已通过 `aligned` 校对的 canonical 规范归并与文档归档，零代码与提示词变动，全部代码与 Context 审查结论完整保留（`retained`）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 1) 分区配额（`MEMORY.md` 主动区 `<= 2,000` 码元）、子页容量护栏（触及主题页 `<= 16,000` / 历史页 `<= 32,000`）、`knowledge/proactivity-policy.md`（`<= 6,000` 码元）权限与同窗主动唤醒去重/撤回覆盖、`Dreaming` 最小有效增量门禁（`minSourceTokens=600`、`maxDeferDays=3`）及 `lastCompletedCycle`/`lastConsolidatedCycle` 状态机正确且无死锁 | `change-code-review` + `agent-context-review`（独立审查子代理 `ebb360c1-4f3d-4fd4-82bf-bce9528eab2f`，Round 1 `full` + Round 2 `closure`） | `pass` | 逐行核对 25 个变更文件与关联调用方；运行 `knowledge-dreaming-config.test.ts`、`proactive-memory-hygiene.test.ts`、`memory-capacity-and-gating.test.ts`、`docs-check`、`check_platform_parity.py` 及 `test_runtime_dependency_contract.py` 全部通过；Round 2 独立捕获受控 DSH 子进程 5 轮 `pa-root` `llm/stream` 请求原件确认 `F1`（同窗撤回 `M0` 与删除 `proactivity-policy.md` 输出 `(none)` 覆盖）与 `F2`（新窗首轮不重复附带）均已闭合 |
| 2) 提示词与随包技能改写语义自洽、保持主会话缓存前缀不变，且在真实 DolphinBench Morgan 运行中消除主题页编年体膨胀与通用无权限免责套话、验证低增量日静默攒批 | `agent-context-review`（实施模式，独立审查子代理 `ebb360c1-4f3d-4fd4-82bf-bce9528eab2f`，Round 1 实测观察 + Round 2 增量复验） | `pass` | 亲自读取真实模型 DolphinBench Morgan v1 运行产出（`windows 1..53`，19 份 Markdown 记忆原件 + `timeline.jsonl` + 30 条 `requests-sample.jsonl`）：`MEMORY.md` 仅 `1,674` 码元且主动专区零被动 SOP 混入，最大主题页 `workstreams/scaffold-2023-planning.md` 仅 `3,641` 码元并原地改写当前态，全库 `not permission/authorization` 免责套话命中数为 `0`；`timeline.jsonl` 证实 `2023-01-15` 低增量日（`275 < 600` tokens）触发 `deferred_below_min_volume`（`modelCalls: 0`）并于次夜无损合并产出 `2023-01-14.md` 与 `2023-01-15.md`；受控探针证实主会话连续多轮 `system` 与首轮 `runtime-context` 快照字节级完全一致。限制说明：审查时刻 DolphinBench `v1` 覆盖前 `53/753` 会话，后续全量评测仍在后台持续运行 |
| 3) 三份 `specs/gateway/{agent-capabilities,personal-agent,global-agent}.md` 契约增量校对 | `change-code-review`（`corrected-delta`，独立审查子代理 `ebb360c1-4f3d-4fd4-82bf-bce9528eab2f`） | `pass` | Round 2 确认三份 delta-spec 全部 `aligned`，完整保留既有 Scenario 且与 `857ab70b1` 实现严格一致 |

## Findings 与关闭

- **`F1` [WARNING] [CONFIRMED] — `closed` @ `857ab70b1`**
  - **位置**：`packages/dsh-integration/src/knowledge/document-memory.ts:384-433`
  - **触发条件与影响**：同一长生命周期上下文窗口内早先主动唤醒已内联 `<updated-formal-memory>`（`M1`）或 `<proactive-policy>`（`P1`），其后在同一窗口内 `MEMORY.md` 被撤回至与窗口初始快照相同的 `M0` 或 `knowledge/proactivity-policy.md` 被删除/清空时，原逻辑返回 `undefined`，使同窗历史中的旧 `M1`/`P1` 在换窗前继续被视为有效策略。
  - **Resolution**：重构 `updatedEntryForWindowWake`（当 `latest.memoryTag !== undefined` 时仅以 `latest.memoryTag === renderedTag` 判重，撤回 `M0` 时输出一次覆盖标签）与 `proactivePolicyForWindowWake`（文件删除或清空但同窗曾内联非 `(none)` 策略时输出一次 `<proactive-policy>\n(none)\n</proactive-policy>`），同步更新 `design.md` 并在 `memory-capacity-and-gating.test.ts` 增加 `day2-review-4` / `day2-review-5` 断言。
  - **独立关闭依据**：独立审查子代理 `ebb360c1-4f3d-4fd4-82bf-bce9528eab2f` 于 Round 2（`857ab70b1`）复核代码并亲自捕获 `pa-root` `llm/stream` 请求原件（`r-after-revert` 精确携带覆盖后的 `M0` 与 `<proactive-policy>\n(none)\n</proactive-policy>`，下一轮 `r-after-revert-2` 不再重复输出），确认关闭。

- **`F2` [NIT] [CONFIRMED] — `closed` @ `857ab70b1`**
  - **位置**：`packages/dsh-integration/src/knowledge/document-memory.ts:391`
  - **触发条件与影响**：新会话或换窗压缩后若首个模型回合恰好为 `proactive_review` / `proactive_nightly`，在 `system-prompt/assemble` 生成新窗口快照前 `savedEntry(agent)` 为 `undefined`，导致首轮同时携带 `nano-document-memory-entry` 快照与一份相同的 `<updated-formal-memory>`。
  - **Resolution**：在 `updatedEntryForWindowWake` 增加 `if (windowEntry === undefined && latest.memoryTag === undefined) return undefined;`，并在 `memory-capacity-and-gating.test.ts` 增加 `day1-first-wake` 断言。
  - **独立关闭依据**：独立审查子代理于 Round 2 `llm/stream` 请求原件核实新窗口首轮 `w0-first-wake` 仅由 `messages[0]` 提供唯一一份 `<memory_content>`，确认关闭。

当前存活 findings：**`0`**（`0 CRITICAL / 0 WARNING / 0 NIT`）。

## 流程收口

- **重要目标和关键设计覆盖**：`spec.md` 全部 4 项 Requirement 与 `design.md` 全部 4 项关键决策均已落地并通过单测、真实 DSH 子进程轨迹检查及 DolphinBench Morgan 真实模型前缀验证。
- **开放问题 / pending / inconclusive**：无阻塞或未决项。
- **最终 delta 校对**：`specs/gateway/{agent-capabilities,personal-agent,global-agent}.md` 均经独立 `corrected-delta` 确认为 `aligned`，并已原样归并至 `docs/specs/gateway/`（同步更新 `> 对齐: feat-822`）。
- **版本变化后保留 / 补验的判断与依据**：`857ab70b1` 后仅执行 canonical spec 归并、报告落盘与目录归档，代码与提示词未变，Round 1 + Round 2 结论全部有效保留。
- **测试资源回收结果 / 例外保留项、owner 与回收触发**：单测与审查探针使用的 `/tmp` 临时目录均已即时销毁；例外保留项为当前会话主 Agent（owner）正在后台持续运行的 DolphinBench Morgan `v1` 长程评测目录 `/Users/czj/.cache/nano-evals/{runs,dolphinbench-state}/morgan-v1-s1-753` 与开发 worktree `/Users/czj/Repos/nano-multiagent/.worktrees/feat-822-memory-capacity-and-gating`（待 PR 合入且全量评测报告产出后按规范清理）。
- **交付范围与剩余事项**：归档 `feat-822-memory-capacity-and-gating` 并推送 `unit/feat-822-memory-capacity-and-gating` 创建目标 `develop` 的 PR；后台继续完成 Morgan `1:753` 完整对齐测分与 `3,400` 轮全量榜单对比。

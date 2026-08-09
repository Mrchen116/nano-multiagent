# bugfix-520 — 回归验证

> 对齐: [incident.md](incident.md)
>
> Validation snapshot: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9 → 4b8046e25c4b1661b2fb2d9d727a9b4c1f6f9c1f`
>
> Review round: 1（full）

## Verdict

- **Verdict**: `pass`
- **Highest Required Action**: `pass`
- **Issues**: blocking 0 / major 0 / minor 0
- **结论**: 用户经真实 IM + Gateway 完成“工具调用 → threshold 压缩 → 继续任务 → Gateway 重启 → 再继续”后，压缩前目标仍然可用；manual、threshold、overflow 的失败路径均保持原历史，automatic 无法继续时先出现固定安全提示、再进入 failed terminal。飞书复用的 assistant delivery seam 同时覆盖原 chat 与 IM shadow。

## Reference Artifacts Reviewed

无视觉原型或截图 reference。本 unit 不改变客户端界面，验收真值为 [incident.md](incident.md) 的失败语义、[design.md](design.md) 的 Runbook，以及 `agent.sdk` / IM HTTP-WebSocket / Gateway 外部投递这些消费者入口的可观察结果。

## 复现验证

修前的稳定症状是：包含 assistant tool call 与匹配 tool result 的历史进入自动压缩后，被无业务内容的 fallback 摘要替换；随后用户继续任务或重启 Gateway，Agent 已不知道原目标。

修后从 Web IM 客户端使用的同一 HTTP/WebSocket seam 走完整真进程旅程：

1. fixture 启动隔离的真实 IM、真实 Gateway 与 recording Anthropic LLM，不使用个人配置、生产 JSONL、`:4000` proxy 或外部凭据。
2. 短会话真实执行一次工具；recording LLM 在指定响应抬高 usage，以小 context window 触发 threshold 压缩。
3. summary request 接收到闭合的 tool use/result，压缩后回复仍包含压缩前的目标 sentinel。
4. 重启同一隔离 Gateway 后再次追问，回复仍包含该目标 sentinel；隔离 transcript 只有有效 compaction boundary/summary。
5. fixture 退出后，本 worktree 没有遗留 `.im.pid`、`.gateway.pid`、`.e2e-ports.env`、Gateway config 或相关存活进程。

证据：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -vv -s \
  tests/e2e/critical_paths/test_context_compaction_continuity_critical_path.py
→ 1 passed in 26.41s
```

## User Journeys Exercised

1. **成功主路径**：真实 IM/Gateway 中执行工具任务，threshold 压缩后继续，再重启 Gateway 继续；两次后续回复都保留原目标。
2. **automatic 失败路径**：经 public Kernel submit/stream 分别制造 threshold summary failure、overflow summary failure、threshold/overflow persistence failure；观察原历史/边界不变，固定 assistant 提示先于 failed terminal，overflow 不进行压缩后模型重试。
3. **manual 与会话计数边界**：经 public Kernel compact 制造空摘要、摘要异常和持久化失败；调用可辨识失败、历史不变。连续 automatic 失败跨 external reload/LRU eviction 保持，第三次熔断；成功 compact 后重置。
4. **飞书可见投递**：不使用生产或个人飞书凭据，复用受控 outbound adapter 验证 standard assistant 文本回原 external chat；durable shadow seam 验证同一用户可见文本同步到 IM shadow。

## 验收标准覆盖

### Requirement: 成功压缩必须保持任务和工具历史连续

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 自动 threshold 压缩含 tool call/result 的会话后继续任务 | incident「长青回归门禁」；design M1-C1 | Journey 1，真实 IM HTTP/WS + 真 Gateway + recording LLM | compaction E2E `1 passed` | pass | 使用短而完整 fixture，不制造 200K 输入 |
| 成功压缩后 Gateway restart/resume 仍延续目标 | incident 业务不变量 6；design M1-C1 | Journey 1，同 node/workspace 重启后再次追问 | 同一 compaction E2E | pass | restart 后仍返回目标 sentinel |
| overflow 成功后只重试一次并从 JSONL 继续 | incident 最低回归矩阵；delta-spec「含工具历史的压缩在重启后继续任务」 | public Kernel integration | Runbook 86-test suite 中 `test_overflow_compaction_retries_and_reopens_from_jsonl` | pass | 无重复模型恢复循环 |

### Requirement: 压缩失败不得伪装成功或替换原历史

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| threshold 前两次 summary failure 保留原上下文继续，第三次有界停止 | incident 澄清；delta-spec「连续自动压缩失败有界并可诊断」 | Journey 2，public Kernel event stream | `test_threshold_summary_failure_stops_on_third_attempt_without_boundary` 通过 | pass | 无失败尝试对应 boundary |
| 第三次 threshold failure 的安全提示先于 failed terminal | 用户确认文案；design 决策 3 | Journey 2，public Kernel event stream | 同一 integration scenario 通过 | pass | 固定文本为“上下文压缩失败，已停止本轮以避免丢失对话内容。原对话仍保留。请稍后重试，或发送 `/compact <希望保留的重点>` 后继续。” |
| overflow summary failure 立即提示、停止且保留原 overflow cause/history | incident 最低回归矩阵；delta-spec overflow failure Scenario | Journey 2，public Kernel event stream | `test_overflow_summary_failure_stops_without_retry_or_boundary` 通过 | pass | 不发起压缩后的模型重试 |
| manual summary/persistence failure 可辨识且上下文不变 | incident 最低回归矩阵；design M2-C1 | Journey 3，public Kernel compact | manual summary 两个参数化 case、append failure 均通过 | pass | Gateway 既有失败确认仍为“压缩未完成，当前会话保持不变。” |
| threshold/overflow persistence failure 不暴露半提交摘要 | delta-spec「压缩记录持久化失败不暴露半提交上下文」 | Journey 2，public Kernel event stream | threshold/overflow persistence 两个 integration scenario 通过 | pass | automatic 仍先发安全提示；诊断区分 failure kind |

### Requirement: automatic 失败状态按会话稳定、成功后恢复

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| external append payload reload / loaded-payload LRU eviction 不清空连续失败次数 | design M2-C2 | Journey 3，public conversation transaction seam | `test_automatic_compaction_failures_survive_payload_reload_and_eviction` 通过 | pass | 同进程同 session 第三次仍熔断 |
| stale commit 不误计，成功 compact 重置失败次数 | design 决策 3/4 | Journey 3 | `test_threshold_success_resets_failures_but_stale_commit_does_not` 通过 | pass | process restart 之外只由成功 compact reset |

### Requirement: automatic 安全提示到达原用户通道

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 飞书触发时 assistant 安全文本回原 chat | 用户澄清；现有 gateway external-channel 契约 | Journey 4，受控 outbound adapter | `test_feishu_intermediate_reply_goes_to_external_without_im_manager` 通过 | pass | 不需要生产/个人飞书凭据 |
| 同一用户可见文本持久同步到 IM shadow | 用户澄清；现有 gateway external-channel 契约 | Journey 4，durable external/shadow seam | Runbook external-visible-delivery suite 全绿 | pass | 复用未改动通用 seam，无 compaction 专用分支 |

### Requirement: 长青 E2E 门禁只新增一个旅程

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| v1 必保活从 14 条增至 15 条，新增且只新增上下文压缩旅程 | 用户确认；design M1-C3 | catalog 对账 + 新旧共享 harness 真跑 | catalog #16；新 E2E `1 passed`；既有 #14/#15 `2 passed in 15.66s` | pass | heartbeat #7 仍在 backlog，稳定编号不重排 |

## 回归测试

Design Runbook 完整矩阵：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q \
  tests/unit/test_session_persistence_fidelity.py \
  tests/unit/test_loop_compact.py \
  tests/unit/test_core_errors.py \
  tests/unit/agent/session/test_conversation_session.py \
  tests/unit/agent/runs/test_runs_registry_executor.py \
  tests/unit/agent/test_kernel_manual_compact.py \
  tests/unit/personal_assistant/test_external_visible_delivery.py \
  tests/integration/test_conversation_compaction_integration.py
→ 86 passed, 2 third-party deprecation warnings in 16.23s
```

共享 recording-LLM harness 的相邻关键旅程：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q \
  tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py \
  tests/e2e/critical_paths/test_prompt_cache_alert_critical_path.py
→ 2 passed in 15.66s
```

## 自动化测试增量

- 真实 transcript projection 的 round-trip guard 覆盖正常/恢复 tool pair、active branch、关系字段与 provider pairing。
- public Kernel integration 覆盖 threshold、overflow、manual 的 success/failure、atomic no-replacement、assistant-before-failed 与 structured terminal。
- conversation/loop unit guard 覆盖三次上限、reload/LRU 生命周期、stale/persistence 分类及成功 reset。
- 单一新 E2E 覆盖真 IM + Gateway + tool history + threshold compaction + restart；catalog v1 必保活总数 14→15。

## Issues

无。

## Side Findings

无。两条 `lark_oapi` deprecation warning 来自第三方依赖，不影响本 unit 用户旅程，也未见运行时异常。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**；包边界与部署拓扑未变化。
- [x] `docs/specs/<包>/`（长青行为契约层）：**需要更新**；unit 内 `specs/kernel/context-persistence.md` delta 已与本轮可观察结果一致，待 orchestrator 收尾归并 canonical。Gateway/IM/CLI 无新增协议，飞书 chat + shadow 复用既有契约。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**；开发和运行约定未变化。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范）：**无需更新**；文档体系未变化。

## Recommended Action

`pass`。进入 verifier / code review 与 canonical spec 归并、归档、PR 阶段；无需 fix-implementation 或 revise-design。

---

# Round 2 — 2026-08-10

> Validation snapshot: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9 → 8a01c838fda8b4ef68dd3a741f60c17ad28dc77d`
>
> Revalidation mode: `targeted`（Fast-lane）
>
> Fix delta: `f50c59d41a29e9bb9892292c30cd952934574ff6..8a01c838fda8b4ef68dd3a741f60c17ad28dc77d`

## Verdict

- **Verdict**: `pass`
- **Highest Required Action**: `pass`
- **Issues**: blocking 0 / major 0 / minor 0
- **结论**: code-review fix delta 影响的五个 consumer 场景全部通过；Round 1 未受影响的覆盖表结论继续有效，无需升级为 full revalidation。

## Fast-lane 范围

本轮只复验以下受 delta 影响的用户/consumer 结果：

1. 成功压缩包含 skill reinjection 时，Kernel close/reopen 后同时恢复 summary 与 reinjection。
2. automatic summary side-chain 的内部 assistant/turn 事件不进入用户 event stream；Web/飞书不会看到内部摘要文本，前两次 threshold summary failure 保持静默。
3. overflow 成功压缩后的模型 retry 若再次遇到 compaction failure，仍先发送固定 assistant 安全提示，再进入 failed terminal。
4. manual/overflow 成功压缩后清除压缩前 usage，不立即产生 summary-of-summary。
5. provider 只返回 analysis、格式化后正文为空时不提交 compaction。

Round 1 的 tool pair 投影、三入口基础 no-replacement、连续失败 tracker、普通 overflow summary failure、external reload/LRU、catalog 14→15 等结论不受此 delta 影响，按 Fast-lane 规则继承。

## Targeted User Journeys Exercised

### Journey A：成功压缩与重启恢复

- 经 public Kernel manual compact 形成 summary + skill reinjection，关闭并重新打开 Kernel session；恢复结果同时含 summary 与 reinjection。
- 重跑真 IM + 真 Gateway + recording LLM 的 tool → threshold compaction → continue → Gateway restart 旅程；压缩后和重启后继续任务均成功。

### Journey B：内部摘要与失败事件可见性

- summary side-chain 产出的内部 assistant/turn event 未发布到用户 stream。
- threshold summary 前两次失败继续原上下文且没有失败提示；第三次才出现固定 assistant 安全提示并进入 failed。
- 既有 Feishu original-chat 与 IM-shadow delivery seam 复验通过，因此真正的用户 assistant 文本仍能正确投递，而内部 side-chain 文本不会因缺少用户事件进入该 seam。

### Journey C：overflow retry 再失败

- 第一次 overflow 成功压缩后进行唯一一次模型 retry；retry 若再触发 compaction failure，event stream 仍观察到 assistant 安全提示先于 failed terminal。

### Journey D：成功后的 token freshness 与空摘要拒绝

- manual compact 成功后的下一轮，以及 overflow 成功后的 retry，均不沿用压缩前 usage 立即二次摘要。
- analysis-only response 格式化后无正文，结果被视为摘要失败，不产生假成功 compaction。

## Targeted Coverage

| Focus Scenario | Consumer 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| summary + skill reinjection 跨 restart 均可恢复 | public Kernel compact + close/reopen | `test_kernel_manual_compact_reinjection_survives_restart` | pass | 可恢复分支不再只剩 summary |
| summary side-chain assistant/turn event 不对 Web/Feishu 可见 | 用户 event publisher seam + Gateway external delivery seam | `test_compaction_summarizer_does_not_publish_sidechain_events`；两个 external-visible-delivery scenario | pass | 内部摘要不发布；标准用户文本投递仍正常 |
| threshold 前两次 summary failure 静默，第三次才提示并 failed | public Kernel submit/stream | `test_threshold_summary_failure_stops_on_third_attempt_without_boundary` | pass | 原上下文与 boundary 保持不变 |
| overflow successful compact 后 retry 再遇 compaction failure 仍 assistant-before-failed | public Kernel submit/stream | `test_overflow_retry_compaction_error_is_visible_before_failed` | pass | 没有绕过用户安全提示 seam |
| manual 成功后不立即 summary-of-summary | public Kernel compact 后续 submit | `test_manual_compaction_clears_prior_usage_before_followup` | pass | 使用压缩后新鲜 usage |
| overflow 成功后 retry 不立即 summary-of-summary | public Kernel overflow recovery | `test_overflow_success_clears_prior_usage_before_retry` | pass | 只进行预期的一次恢复 retry |
| analysis-only / 格式化空正文不提交摘要 | compaction summarizer consumer result | `test_compaction_summarizer_rejects_analysis_only_response` | pass | 空业务正文不再是假成功 |
| 真 IM/Gateway 成功压缩与 restart 旅程无回归 | IM HTTP/WS + 真 Gateway + recording LLM | critical-path E2E `1 passed in 26.91s` | pass | fixture 退出后无进程/配置残留 |

## Validation Evidence

定向 public Kernel / event-stream 场景：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -vv \
  tests/unit/test_loop_compact.py::test_compaction_summarizer_rejects_analysis_only_response \
  tests/unit/test_loop_compact.py::test_compaction_summarizer_does_not_publish_sidechain_events \
  tests/unit/agent/test_kernel_manual_compact.py::test_kernel_manual_compact_reinjection_survives_restart \
  tests/integration/test_conversation_compaction_integration.py::test_manual_compaction_clears_prior_usage_before_followup \
  tests/integration/test_conversation_compaction_integration.py::test_overflow_success_clears_prior_usage_before_retry \
  tests/integration/test_conversation_compaction_integration.py::test_overflow_retry_compaction_error_is_visible_before_failed \
  tests/integration/test_conversation_compaction_integration.py::test_threshold_summary_failure_stops_on_third_attempt_without_boundary
→ 7 passed in 10.31s
```

真实成功旅程：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -vv -s \
  tests/e2e/critical_paths/test_context_compaction_continuity_critical_path.py
→ 1 passed in 26.91s
```

外部/影子投递 seam：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q \
  tests/unit/personal_assistant/test_external_visible_delivery.py::test_feishu_intermediate_reply_goes_to_external_without_im_manager \
  tests/unit/personal_assistant/test_external_visible_delivery.py::test_feishu_visible_control_text_goes_to_external_and_shadow_im
→ 2 passed in 2.49s
```

## Issues

无。

## Side Findings

无。外部投递测试仍仅出现 Round 1 已记录的第三方 `lark_oapi` deprecation warning。

## 上层文档同步

- [x] `SPEC.md`：**无需更新**；本轮 delta 不改变包边界或部署拓扑。
- [x] `docs/specs/<包>/`：**维持 Round 1 结论**；kernel delta 仍需在 orchestrator 收尾归并，新增 fix 未改变已写的用户契约。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**。

## Recommended Action

`pass`。五项 focus 已关闭，继续 verifier / code review / PR 收尾；`needs_re_review=false`。

---

# Round 3 — 2026-08-10

> Validation snapshot: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9 → 52756f1e0acaa51b4449ee365a40d541cc93a4e8`
>
> Revalidation mode: `targeted`（Fast-lane）
>
> Fix delta: `f9db02d958e9972e229a774036eaa40df8d454c4..52756f1e0acaa51b4449ee365a40d541cc93a4e8`

## Verdict

- **Verdict**: `pass`
- **Highest Required Action**: `pass`
- **Issues**: blocking 0 / major 0 / minor 0
- **结论**: R7 的两项消费者结果可以同时成立：manual compaction summary 继续经过正确 workspace observer scope；其内部 assistant/turn event 仍不进入 parent Kernel stream，因此不会进入飞书 original-chat / IM-shadow 投递 seam。无需扩回 full review。

## Fast-lane 范围

R7 只调整 summary side-chain 的 hook context 传播。本轮继承 Round 1/2 全部未受影响结论，只复验：

1. public `Kernel.compact()` 触发 summary 时，originating workspace 的 observer hook 仍以正确 consumer scope 执行。
2. 同一次内部 summary 的 assistant/turn event 不发布到 parent Kernel stream；正常用户 assistant/control text 的 Feishu external + IM shadow 投递保持可用。

## Targeted Coverage

| Focus Scenario | Consumer 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| public Kernel manual compact 保留 workspace observer hook scope | 真实 workspace hook 文件 + public `Kernel.compact()` | `test_manual_compaction_summary_keeps_workspace_hook_scope` | pass | observer 收到 originating `.consumer` scope |
| summary assistant/turn 不进入 parent Kernel stream | parent session event publisher seam | `test_compaction_summarizer_does_not_publish_sidechain_events` | pass | 内部 summary 文本不成为用户事件 |
| 无内部 event 时不会误投递飞书 original chat / IM shadow，正常用户文本投递不受损 | 受控 Feishu external + durable shadow adapter | 两个 external-visible-delivery scenarios | pass | event isolation 与正常 delivery 同时成立 |

## Validation Evidence

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -vv \
  tests/unit/agent/test_workspace_scope_observer_hooks.py::test_manual_compaction_summary_keeps_workspace_hook_scope \
  tests/unit/test_loop_compact.py::test_compaction_summarizer_does_not_publish_sidechain_events \
  tests/unit/personal_assistant/test_external_visible_delivery.py::test_feishu_intermediate_reply_goes_to_external_without_im_manager \
  tests/unit/personal_assistant/test_external_visible_delivery.py::test_feishu_visible_control_text_goes_to_external_and_shadow_im
→ 4 passed, 2 third-party deprecation warnings in 5.23s
```

本 delta 仅触及 summary side-chain hook context 与对应测试；targeted 旅程通过，未观察到新副作用或 stale service 风险，因此 Fast-lane 不升级为完整验收。

## Issues

无。

## Side Findings

无。两条 `lark_oapi` deprecation warning 与前两轮一致，不影响本 unit 用户旅程。

## 上层文档同步

- [x] `SPEC.md`：**无需更新**。
- [x] `docs/specs/<包>/`：**维持 Round 1/2 结论**；R7 不改变用户契约，仅恢复既有 workspace observer routing。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**。

## Recommended Action

`pass`。R7 targeted concern 已关闭；继续最终 verifier / code review / PR 收尾，`needs_re_review=false`。

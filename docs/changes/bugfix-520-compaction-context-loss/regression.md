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

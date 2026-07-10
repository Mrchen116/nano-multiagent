# Verification Report: bugfix-437

> Round 1 — 2026-06-26

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 6/6 |
| Correctness | 4/4 Req covered（含 4 Scenarios） |
| Coherence | Followed（3 决策全部遵守；设计评审 WARNING-1/2 均已修订） |

No critical issues. 2 suggestion(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 6/6 complete**（`M1-fix/tasks.md` 所有退出标准均 `[x]`）

**Spec 覆盖检查：**

| Requirement | 有实现？ |
|---|---|
| 超长对话中 agent 仍能正常回复（不崩、不卡 running） | 有 |
| 长对话后 agent 不失忆 | 有 |
| agent 回复失败时用户立即看到真实原因 | 有 |
| 失败提示归属正确 agent | 有 |

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 超长对话触发压缩 → run 透明继续完成 | `loop.py:161` 加 workspace_root 参数；`loop.py:877-881` 传给 `list_entries`；`runtime.py:601-602` 第一次 `_execute_loop` 调用传 session_workspace_root | `test_compaction_runtime_integration.py::test_threshold_compaction_workspace_aware_does_not_crash` | covered |
| 长对话后 agent 不失忆（overflow retry 后 history 不被清空） | `runtime.py:669-671` `list_turn_messages` 带 `workspace_root=session_workspace_root` | `test_compaction_runtime_integration.py::test_overflow_compaction_workspace_aware_does_not_crash`（`assert replayed`） | covered |
| 回复失败即时反馈（数秒内翻 failed 带真因，不等 120s watchdog） | `main.py:3165-3195` failed 分支补发 `node.report(status="failed", message_id, summary=update.error)` | `test_gateway_relay_lifecycle.py::test_relay_lifecycle_callback_failed_sends_message_level_report_with_real_cause`（顺序、字段全断言） | covered |
| 失败提示归属正确 agent | `main.py:3178` `agent_id=update.agent_id` 写入 report | 上一条测试中 `assert report["agent_id"] == "agent-a"` | covered |

**补充决策覆盖验证：**

| 退出标准 | 实现 | 测试 |
|---|---|---|
| 压缩落盘单一路径（无双写） | `applier.py` 去掉 `append_compaction`，改纯构造；`runtime.py:1994-2016` 直写路径唯一 | `test_compaction_single_write_and_memory_reset`：磁盘恰一对 boundary+summary |
| compact_boundary 先于 summary turn | `runtime.py:2000-2015` 先 enqueue boundary 再 enqueue summary | 同上：`assert raw.index(boundaries[0]) < raw.index(summaries[0])` |
| 压缩后内存 `_session_histories` 仅含 summary 轮 | `runtime.py:1996` `_session_histories[session_id] = [summary_msg]` 在 `if path is not None:` 内 | 同上：`assert len(in_memory) == 1` + `is_compact_summary is True` |
| `entry_id` 与磁盘 `summary_uuid` 对齐（不漂移） | `summary_msg` 在 `if path` 前生成（`runtime.py:1980-1986`），`apply(summary_uuid=summary_msg.message_id)` | 同上：`assert result.entry_id == boundaries[0]["summary_uuid"]` |

---

## Coherence

| design 决策 | 遵守？ | 代码证据（file:line） |
|---|---|---|
| 决策 1：系统性贯穿 workspace_root，经 `loop.run`/`_execute_loop` 显式参数穿透，不加 AgentState 字段，不复用 cwd-override | 是 | `loop.py:161`（workspace_root 参数）；`runtime.py:602,694`（两处 _execute_loop 调用传 session_workspace_root）；`loop.py:303`（传给 _maybe_compact）；AgentState 未新增字段（设计评审 WARNING-2 已采纳） |
| 决策 2：保留直写路径（含内存重置），apply() 降纯结果构造，消双写（设计评审 WARNING-1 修订后） | 是 | `runtime.py:1988-2016`（直写路径保留，`_session_histories` 重置在 `if path is not None:` 内）；`applier.py`（无 `append_compaction` 调用，纯构造）；`CompactionApplier.__init__` 不再依赖 session_manager（`runtime.py:240`） |
| 决策 3：failed 分支镜像 completed，补发 message 级 node.report，watchdog 保留 | 是 | `main.py:3165-3195`（与 completed 分支镜像结构，`send_report(status="failed", message_id, summary=update.error)`）；120s watchdog 未改动 |
| 不弱化 store stateless 契约（补根到调用方，不退回猜测路径） | 是 | `jsonl_store.py` 未改动；`applier.py` 去掉了传 `workspace_root=None` 的 `append_compaction` 调用 |
| 分层：PA 只改 relay callback，不 import agent.core/platform 内部 | 是 | `main.py` diff 仅在 `_build_relay_lifecycle_callback` 的 `failed` 分支追加，无新 import |
| delta-spec：kernel + gateway 增量草案已备（canonical 合并留 orchestrator 收尾） | 是 | `docs/changes/bugfix-437-compaction-workspace-root-crash/specs/kernel/spec.md`（新增 Scenario「工作区绑定的会话压缩落盘后运行透明继续」）；`specs/gateway/spec.md`（ADDED Req「agent 回复失败时即时反馈真实原因」）；canonical `docs/specs/` 未动（符合 delta-spec 草案流程） |

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

**S1：`CompactionApplier.apply()` 的 `restored_files` 形参是死参数**

`apply()` 签名保留了 `restored_files: Sequence[str] = ()` 形参（`applier.py:28`），函数体第一行即 `del restored_files`（`applier.py:45`）。调用方 `runtime.py:2024` 仍传该值。`restored_files` 已在 `runtime.py:2007-2009` 写入磁盘 compact_boundary，`apply()` 不再需要它。

建议：从 `CompactionApplier.apply` 签名移除 `restored_files` 形参，同时删除 `runtime.py:2024` 的对应传参及 `del` 语句。可选择现在清，也可在下次动此文件时顺手清。

相关位置：`src/agent/core/agent/compaction/applier.py:28,45`；`src/agent/core/agent/runtime.py:2024`

---

**S2：`test_overflow_compaction_workspace_aware_does_not_crash` 的不失忆断言偏弱**

`tests/integration/test_compaction_runtime_integration.py:463` 仅断言 `assert replayed`（非空），未验证 replayed 内容含 summary 轮。相比 `test_compaction_single_write_and_memory_reset` 的内存全断言，此处覆盖力度差。对于该测试的场景（overflow 恢复 + 不失忆），`assert replayed` 已足以验证「list_turn_messages 不再静默清空」，但若要对齐 tasks.md 中「不失忆」的语义，可补一行 `assert any("summary" in (m.content or "").lower() for m in replayed)`。

相关位置：`tests/integration/test_compaction_runtime_integration.py:462-463`

---

All checks passed. Ready for PR.

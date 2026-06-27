# Verification Report: bugfix-443

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 |
| Correctness | 7/7 scenarios covered |
| Coherence | Followed（1 WARNING：design 修复方向 3 未落地） |

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

## Completeness

Tasks: 5/5 complete（tasks.md 所有 `- [x]` 均已完成）

1. `AgentRuntime.resolve_run_model(session_id)` — 实现于 `src/agent/core/agent/runtime.py:1030`
2. 三派发点透传 — 实现于 `src/agent/platform/tools/builtins/agent.py:301, 373, 576`
3. Protocol + RuntimeRunner 签名加 `model` — `src/agent/core/background_tasks/interfaces.py:58`、`src/agent/platform/background_tasks/runtime_runner.py:53,68`
4. 根因 B loop 补 `model_override` — `src/agent/core/agent/loop.py:919-921`
5. 全树 `pytest -m "not e2e"` 3045 passed，contract 129 passed，ruff 全绿

Spec 覆盖：delta-spec `specs/kernel/spec.md` 新增两条 Scenario（"run 派发的子 agent 复用本 run 的 model" + "run 的自动上下文压缩摘要复用本 run 的 model"）已实现，canonical 归并由 orchestrator 收尾，符合 design 约定。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| `resolve_run_model` 登记则返回，未登记 / `None` → `None` | `runtime.py:1030-1042` | `test_agent_runtime.py::test_resolve_run_model_exposes_active_run_model_mid_run`（input-hook mid-run 读到 mimo-model，run 结束后返回 None）、`test_resolve_run_model_returns_none_for_unknown_or_missing_session` | covered |
| 后台派发继承父模型 | `agent.py:301` (`start(..., model=runtime.resolve_run_model(ctx.session_id))`) | `test_agent_tool.py::test_background_launch_inherits_parent_run_model`（断言 `resolve_run_model` 以 `"parent_1"` 调用，runner.start 收到 `model="mimo-model"`） | covered |
| 前台派发继承父模型 | `agent.py:373` (`runtime.run(..., model=runtime.resolve_run_model(ctx.session_id))`) | `test_agent_tool.py::test_foreground_inherits_parent_run_model`（spy `runtime.run`，captured `model=="mimo-model"`） | covered |
| resume 继承父模型 | `agent.py:576` (`start(..., model=runtime.resolve_run_model(parent_session_id))`) | `test_agent_tool.py::test_resume_inherits_parent_run_model`（runner.start 收到 `model="mimo-model"`） | covered |
| `RuntimeRunner.start` 把 `model` 透传到 `runtime.run` | `runtime_runner.py:53,68` | `test_runtime_runner_model.py::test_start_forwards_model_to_runtime_run` | covered |
| 主动阈值压缩：无 `summary_model` → `model_override=active_model` | `loop.py:919-921` | `test_loop_compact.py::test_loop_proactive_compaction_uses_run_model_when_no_summary_model`（`summarizer.model_overrides == ["run-model"]`） | covered |
| 主动阈值压缩：配 `summary_model` → `model_override=None`（独立模型不被覆盖） | `loop.py:919-921` | `test_loop_compact.py::test_loop_proactive_compaction_keeps_dedicated_summary_model`（`summarizer.model_overrides == [None]`） | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：复用 `_active_run_models`，加公开 `resolve_run_model` accessor（不直接读私有属性，不另造来源） | 是 | `runtime.py:1030-1042`；`agent.py` 三处均调公开方法，未直接访问 `_active_run_models` |
| 决策 2：accessor 返回裸值（None 时由 `runtime.run` 的 `model_override or self._model` 单点兜底，accessor 不重复兜底） | 是 | `runtime.py:1042` 直接 `return self._active_run_models.get(session_id) if session_id else None`，无额外 fallback |
| 决策 3：三派发点（后台/前台/resume）统一加 `model` 参数，Protocol + 实现同步 | 是 | `interfaces.py:58`（Protocol）、`runtime_runner.py:53,68`（实现）、`agent.py:301,373,576`（三处调用点） |
| 决策 4：`loop.py:910` summarize 补 `model_override=(None if summary_model else active_model)`，尊重 `summary_model` 互斥 | 是 | `loop.py:919-921`；`active_model` 已在 `_maybe_compact` 参数中（`loop.py:882`），无需额外引用 |
| 架构边界：platform（agent.py）通过公开方法访问 core（runtime），不破坏封装 | 是 | `agent.py` 调 `runtime.resolve_run_model()`（公开方法），未直接碰 `runtime._active_run_models` |
| 沿用 `_active_run_models` 单一事实源，不另造平行模型来源 | 是 | hook model_caller / overflow / 手动压缩已读同一张表，本 unit 无新表 |

## Issues

### CRITICAL（提 PR 前必须修）

无

### WARNING（应该修）

**W1：design 修复方向 3 明确要求纠正 bugfix-429 `verification.md:99` 的错误论断，但该改动未进 tasks.md 且未执行**

`design.md` 修复方向 3 明确说明："并纠正 bugfix-429 `verification.md:99` 那条错误论断（subagent_runner 就是一个不传的真实调用方，反证此论断为假）"。

当前状态：`docs/changes/bugfix-429-per-agent-model-selection/verification.md:99` 仍写 "所有真实调用方现均传 `model_override`"——这条历史断言已被 bugfix-443 修复本身证伪（bugfix-443 的修复正是补上 subagent_runner 这个漏传调用方），但原文未修订，后续读者可能误信。

建议修复：在 `docs/changes/bugfix-429-per-agent-model-selection/verification.md:99` 追加脚注或 NOTE：

```
> NOTE(bugfix-443)：此论断不完整。subagent_runner（`agent.py`→`RuntimeRunner.start`）
> 为不传 model_override 的真实调用方，已在 bugfix-443 补全。
```

### SUGGESTION（可以修）

**S1：根因 B 的 loop 测试未显式验证 `model_override` 经由 `loop.run(state, model_override=X)` 传入后流到 compaction 的完整链路**

当前两个 test（`test_loop_proactive_compaction_uses_run_model_when_no_summary_model` / `test_loop_proactive_compaction_keeps_dedicated_summary_model`）用 `AgentLoop(model="run-model")` 的构造期 `self._model` 作为 `active_model`（`model_override` 未显式传入 `loop.run`，故 `active_model = None or "run-model"`）。测试充分验证了 `active_model → model_override` 的传递路径，但未明确覆盖"调用方传 `model_override=<parent model>` → 该值流入压缩"这一链的起点。

影响：当前链路被 runtime 层测试（`test_resolve_run_model_exposes_active_run_model_mid_run`）与 loop 层测试组合间接覆盖，不是功能缺口；仅降低独立测试的清晰度。

建议（可选）：在测试中补一个 `_make_compacting_loop_with_model_override` 变体，显式调 `loop.run(state, model_override="explicit-run-model")` 并断言 `summarizer.model_overrides == ["explicit-run-model"]`，使 B 根因测试自解释。

---

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

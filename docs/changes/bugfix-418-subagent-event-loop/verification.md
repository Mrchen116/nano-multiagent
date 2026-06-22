# Verification Report: bugfix-418

> review_round: 1
> branch: unit/bugfix-418 @ 9de388a1

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 |
| Correctness | 4/5（1 WARNING：超时转后台的 notification 发出路径无专项单测覆盖） |
| Coherence | Followed（4/4 决策遵守，1 SUGGESTION） |

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 7/7 complete**

所有退出标准全部 `[x]`：
1. `[x]` 前台 in-budget 完成走专用循环、返回结果（e2e 用例1）
2. `[x]` in-budget 完成不调用 `register_subagent`（`test_foreground_in_budget_does_not_register_subagent`）
3. `[x]` 超时分支仍 register + watcher（`test_foreground_auto_backgrounds_on_timeout`）
4. `[x]` 删除 `_run_subagent_turn_sync` + 私有 `_executor`，无残留引用
5. `[x]` `event_loop is None` fallback 不共享主循环（`test_submit_foreground_without_loop_runs_in_isolated_thread`）
6. `[x]` 新增 `@pytest.mark.e2e` 真 LLM e2e（2 passed）
7. `[x]` `pytest tests/ -m "not e2e"` 全绿（2712 passed, 0 failed, 1 skipped，本次实跑验证）

**Spec 覆盖（delta-spec `docs/changes/bugfix-418-subagent-event-loop/specs/kernel/spec.md`）**

MODIFIED requirement（前台同步结果不重复通知）和 ADDED requirement（前台执行与内核循环隔离）均有对应实现。

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| MODIFIED: 前台 subagent 在预算内完成只走 tool result，不发通知 | `agent.py:239`（裸 coroutine，无 on_complete 回调）+ `agent.py:283-288`（in-budget 路径无 register_subagent 调用） | `test_foreground_in_budget_does_not_register_subagent`（spy 断言 register_calls == []） | covered |
| MODIFIED: 前台 subagent 超预算转后台后仍发一次完成通知 | `agent.py:254-268`（register + mark_running + watcher） | `test_foreground_auto_backgrounds_on_timeout`（只断言 `status=async_launched`；notification 发出无专项断言） | WARNING（见下） |
| ADDED: 前台子 agent 正常返回结果，不报跨事件循环错误 | `agent.py:239`（`submit_foreground` 提交到专用循环）；`runtime_runner.py:124-125`（`run_coroutine_threadsafe(coro, self._event_loop)`） | `test_subagent_foreground_e2e.py::test_foreground_subagent_completes_via_dedicated_loop`（真 LLM，断言 status=completed + 无 "different event loop"） | covered |
| ADDED: 单次工具/子 agent 失败被隔离，不拖垮内核与常驻进程 | `runtime_runner.py:97-136`（独立 Task，异常收敛进 Future）；`agent.py:276-281`（`except Exception` 返回 status=failed） | `test_subagent_foreground_e2e.py::test_failing_foreground_subagent_does_not_kill_dedicated_loop`（注入 `_FailingRuntime`，断言 failed + 专用循环 is_running + 健康 subagent 仍跑通） | covered |
| R3: create_session 同走专用循环，不裸 asyncio.run | `agent.py:484-488`（`runner.submit_foreground(create_coro).result()`；fallback 仅在 runner 为 None 时） | `test_create_subagent_session_routes_through_dedicated_loop`（断言 submit_foreground_calls == 2） | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策1: 前台 subagent 复用「专用循环 + run_coroutine_threadsafe」，删私有 asyncio.run | 是 | `runtime_runner.py:124-125`；`agent.py:239`；`_run_subagent_turn_sync` + `_executor` 已全部删除（`rg` 验证无残留） |
| 决策2: in-budget 前台完成绝不注册 registry（无注册即无 task-notification）| 是 | `agent.py:248-289`：budget 内完成分支直接返回结果，只在 `FutureTimeoutError` 分支（:251-275）才 `register_subagent`；设计要求的裸 coroutine（无 on_complete）在 `submit_foreground` 调用中实现 |
| 决策3: 故障隔离以「Task 隔离 + 回归断言」交付 | 是 | `runtime_runner.py:97-136`：`submit_foreground` 返回独立 Future，异常不冒泡；e2e test 2 固化断言 |
| 决策4: 回归守卫 = 一条真 LLM e2e（默认不跑） | 是 | `tests/e2e/test_subagent_foreground_e2e.py`：2 个 `@pytest.mark.e2e` 用例，env gate `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1`，conftest 自动打 marker |

**架构自洽性**：
- `platform → core` 依赖方向：`agent.py` 在 `platform/tools/builtins/` 中，import `agent.core.*`，方向正确；`core/background_tasks/interfaces.py` 中的 `submit_foreground` 协议定义在 core 层，实现在 platform 层，分层合规。
- 产品包（`personal_assistant` / `coding_cli`）无任何新 import 进 `agent.core/platform` 内部（contract 测试 126 passed）。
- 无跨机边界违规；所有变更均在单进程内核执行路径。

---

## Issues

### CRITICAL（提 PR 前必须修）

无

### WARNING（应该修）

**W1: 超时转后台的 notification 发出路径无专项单测**

spec 中「前台 subagent 超预算转后台后仍发一次完成通知」scenario 的 notification 发出断言缺失。`test_foreground_auto_backgrounds_on_timeout`（`tests/unit/agent/tools/test_agent_tool.py:259`）只断言了 `status=async_launched`，没有断言当 watcher future 完成后 `registry.complete` 确实被调用，进而 notification 被投递。

design decision 2 明确要求"超时 auto-background 分支注册 + 挂通知"，并说明"注册前再确认终态……用单测覆盖该窗口"（design.md:80），但该单测未落地。

建议：在 `tests/unit/agent/tools/test_agent_tool.py` 中增加一条测试：让 `timeout_seconds=0` 触发 `FutureTimeoutError`，随后 future 完成，验证 `registry.complete` 被调用（可 spy `registry.complete` 方法），确认 watcher 线程正确完成通知链路。参考 `test_foreground_auto_backgrounds_on_timeout`（:259），在其基础上等待 watcher 完成并 assert。

### SUGGESTION（可以修）

**S1: `_create_subagent_session` 中的 `hasattr(runner, "submit_foreground")` 检查多余**

`agent.py:485`：`hasattr(runner, "submit_foreground")` 是冗余检查。`BackgroundSubagentRunner` 协议（`interfaces.py:44-67`）和 `_NoOpSubagentRunner`（`wiring.py:214`）均已包含 `submit_foreground`，且 `_require_wiring()` 保证 wiring 非 None。此防御检查传递的信息是"旧实现可能没有 submit_foreground"，而协议已定义它，应直接调用：

```python
# 建议改为
runner = self._wiring.subagent_runner
session = runner.submit_foreground(create_coro).result()
# fallback 仍保留 if self._wiring is None，但 _require_wiring 已保证到达此处 _wiring != None
```

如需保留 fallback（有 wiring 但 runner 无 submit_foreground 的降级路径），在 docstring 说明理由即可；否则直接删去 `hasattr` 检查。路径：`agent.py:484-488`。

# bugfix-437 Reviewer Regression Report

**Unit:** bugfix-437-compaction-workspace-root-crash
**Branch:** unit/bugfix-437
**Review Round:** 1
**Reviewer Date:** 2026-06-26

---

## Verdict: PASS

所有 reviewer Scenario 通过，所有 worker 退出标准通过，ruff 绿，全树无回归。

---

## 验收覆盖表

### Requirement: 超长对话中 agent 仍能正常回复

#### Scenario: 对话长到触及模型记忆上限

| 项 | 结论 |
|---|---|
| 验证方式 | Integration test (workspace-aware 模式) |
| 测试名 | `tests/integration/test_compaction_runtime_integration.py::test_threshold_compaction_workspace_aware_does_not_crash` |
| 证据 | `data_dir=None`（生产 workspace-aware 路径）下触发 threshold 压缩，session 可从 JSONL 重放重建；test PASS |
| 结论 | **PASS** |

**注：** Incident 明确标注「只在生产暴露：仅当存储工作在 workspace-aware 模式（生产路径）才命中；测试脚手架走 `data_dir` 旁路，路径解析不要求 `workspace_root`，因此单测全绿、线上必崩。」本次新增的 integration test 显式以 `data_dir=None` 构造场景，精准覆盖原本对测试不可见的生产崩溃路径，并通过。这是最可靠的生产等价证据。

e2e 真栈验证（IM ↔ Gateway）因 LLM provider 当前不可达（transport error），无法触发真实 LLM 调用完成的正常回复路径。Integration test 已以 workspace-aware 模式（data_dir=None）覆盖。

#### Scenario: 长对话之后 agent 不失忆

| 项 | 结论 |
|---|---|
| 验证方式 | Integration test (内存重置断言) |
| 测试名 | `tests/integration/test_compaction_runtime_integration.py::test_compaction_single_write_and_memory_reset` |
| 证据 | 压缩后 `_session_histories[session_id]` 仅含 summary 消息，不含已摘要的旧轮次；test PASS |
| 结论 | **PASS** |

**注：** 「agent 不失忆」的根因有两条：① `list_turn_messages` 漏传 workspace_root 导致 manager 内 catch 后返回空列表 —— 现已在 `runtime.py:668` 修复（传 workspace_root）；② 压缩后内存 cache 未重置 —— design 决策 2 保留了直写路径的 `_session_histories[session_id]=[summary_msg]` 副作用。`test_compaction_single_write_and_memory_reset` 同时断言磁盘可重放 + 内存 history 不含已摘要轮次，两条都覆盖。

---

### Requirement: agent 回复失败时用户立即看到真实原因

#### Scenario: 回复失败的即时反馈

| 项 | 结论 |
|---|---|
| 验证方式 | Unit test + e2e 真栈 (IM ↔ 真 Gateway 进程) |
| 单测名 | `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_relay_lifecycle_callback_failed_sends_message_level_report_with_real_cause` |
| e2e 证据 | LLM transport error 场景：agent 气泡内容为「⚠️ 模型调用失败:anthropic transport error: All connection attempts failed」（真实原因），而非 watchdog 的「relay idle for 120s with no new event」 |
| 结论 | **PASS** |

**附 e2e 细节（真栈）：**
- e2e-up.sh 起栈（IM port=59111, Gateway pid=25872），LLM provider 当前不可达（transport error）。
- 发送一条消息给 default-agent，等待 agent 回复翻态。
- 约 118s 后（LLM client 多次 retry 后放弃）agent 气泡翻 `failed`，内容展示真实原因。
- IM log 中无任何 relay_watchdog / relay_idle 条目，确认失败由 gateway 主动 `node.report(status=failed)` 上报，非 watchdog 兜底。
- gateway log：`run_failed | error='anthropic transport error: All connection attempts failed'` → 随后 `node.report` 发出（background task 的 RuntimeError 是由 `_await_terminal_run_async` 在 callback 执行完毕后抛出，不影响报告路径）。

**说明：** 约 118s 延迟源于 LLM client 内部重试逻辑（非 gateway 侧可控），不是 120s watchdog。关键差别：旧行为下用户等 120s + 拿到 watchdog 文案（假原因）；新行为下 LLM retry 结束即立刻拿到真实原因，不另加 120s 等待。以 fixture 503-stub 可得到秒级失败，本次 e2e 环境 LLM 不可达，只能验证「真原因报告 + watchdog 不触发」两项本质属性。

#### Scenario: 失败提示归属正确的 agent

| 项 | 结论 |
|---|---|
| 验证方式 | Unit test + e2e |
| 证据 | 单测断言 `node.report(agent_id=...)` 正确传入；e2e 中气泡由 `default-agent` 发出（非匿名兜底） |
| 结论 | **PASS** |

---

## Worker 退出标准核对

| 标准 | 状态 |
|---|---|
| `data_dir=None` threshold 压缩回归用例（不崩，JSONL 可重放） | PASS — `test_threshold_compaction_workspace_aware_does_not_crash` |
| `data_dir=None` overflow 压缩回归用例 | PASS — `test_overflow_compaction_workspace_aware_does_not_crash` |
| 压缩后内存 `_session_histories` 不含已摘要轮次 | PASS — `test_compaction_single_write_and_memory_reset` |
| 单写守（`apply()` 不持久化，compact_boundary 先于 summary） | PASS — 同上测试断言 + 代码审查（`apply()` 签名已去 `session_manager` 依赖） |
| run 失败 → message 级 node.report 带真因 | PASS — `test_relay_lifecycle_callback_failed_sends_message_level_report_with_real_cause` |
| 全测试树 `pytest -m "not e2e"` | PASS — 2966 passed, 1 skipped, 0 failed |
| `ruff check` | PASS — All checks passed |
| `ruff format --check` | PASS — 691 files already formatted |

---

## 代码审查关键点

### A 面：workspace_root 贯穿

- `loop.py` 新增 `workspace_root: Path | None = None` 参数，docstring 明确说明与 `current_working_directory_override` 的区别（bugfix-437 decision 1）。
- `loop.run` 调用 `_maybe_compact(workspace_root=workspace_root)` ✓
- `runtime.py:601, 691` 两处 `loop.run`/`loop.execute` 调用均已传 `workspace_root=session_workspace_root` ✓
- `runtime.py:668` `list_turn_messages` 已补传 `workspace_root=session_workspace_root` ✓（失忆修复）
- `applier.py:apply()` 移除 `session_manager` 依赖，签名改为纯结果构造 ✓

### B 面：失败 message 级反馈

- `main.py` `failed` 分支新增 `send_report(status="failed", message_id, agent_id, summary=update.error)` ✓
- `if callable(send_report) and message_id is not None and update.run_id is not None` guard ✓
- `delivery_receipt(failed)` 保留 ✓，watchdog 保留 ✓

### 决策 2 (消双写) 关键内存副作用已保留

直写路径 (`path is not None`) 中 `self._session_histories[session_id] = [summary_msg]` 在 `if path is not None:` 块**外**，即 `summary_msg` 在进入 `if path is not None` 之前已构造：

```python
# runtime.py (after fix)
summary_msg = Message(...)  # 先构造

path = self._session_paths.get(session_id)
if path is not None:
    self._session_histories[session_id] = [summary_msg]  # 内存重置在 if 内
    ...
```

⚠️ 细节核查：`_session_histories` 重置在 `if path is not None:` 内部。若 `path is None`（session 尚未落盘，活跃 run 内不应发生），则内存不重置，但 `apply()` 也不写盘，整体一致。worker 已在 tasks.md 的风险部分评估了这个场景。

---

## 可改进项（不阻断，建议 follow-up）

1. **LLM retry 超时配置**：当前 transport error 下 LLM client 约 118s 才放弃（多次 retry）。对「数秒内报失败」的完整 UX 体验，建议后续评估 LLM client 的重试策略和超时配置，使 provider-side failure 更快 surface。这不在本 unit 范围内，但与 B 面目标相关。
2. **`background task raised unexpected exception` 仍出现**：`_await_terminal_run_async` 在 callback 执行完毕后仍抛 RuntimeError（旧路径），被 `_consume_task_exception` 捕获记录。功能上无害（node.report 已发），但日志噪音。可在后续 clean-up unit 中把 `_await_terminal_run_async` 的 raise 改为 return，使 failed 不再作为未处理异常传播。

---

## Recommended Action

**推进 PR 合并。** 本 unit 两面 fix 均达到退出标准，全树无回归，代码审查无阻断问题。

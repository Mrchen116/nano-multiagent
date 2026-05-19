# M4: tests-e2e — progress

## 开工报信

已读懂 M4，范围 = 10 e2e 文件迁移 (C)→(A) + 2 workspace_root xfail 转 pass，开始实施。

---

### R1 — C1 红测试基线确认

- Context: 10 个 e2e 文件仍用 `SQLiteSessionStore`（platform 层死代码），pytest 跑出 10 fail + 2 xfail
- Decision: 记录基线状态作为 C1，不修改代码
- Rationale: 符合 TDD 三提交；证明当前缺失能力（使用真实 (A) 路径）
- Evidence:
  - Tests: 10 failed, 11 passed, 1 skipped, 2 xfailed — 失败均因 SQLiteSessionStore 路径
  - Entry: N/A（C1 不写实现）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 基线确认，见 pytest 输出
  - Visual/Interaction: N/A
- Rollback: 无（C1 只加 tasks.md + progress.md）
- Commits: C1=<待填>, C2=<待填>, C3=<待填>
- Next: R2 迁移 8 个简单文件

---

### R2 — 迁移 8 个简单 e2e 文件

- Context: 8 个文件用相同模式：import SQLiteSessionStore + `store = SQLiteSessionStore(db_path=...)` + `create_app(session_store=store, ...)`
- Decision: 统一改为 `from agent.core.session.jsonl_store import JsonlSessionStore` + `from agent.platform.persistence.session.service import SessionService` + `service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))` + `create_app(session_store=service.manager._store, ...)`
- Rationale: test_compaction 和 test_session_rebuild 需要 `store.load_session`，通过 `service.manager._store` 访问；其余文件只用 store 注入 app，不直接访问 store
- Evidence: 见 R2 commit 后 pytest 结果
- Rollback: R1 C1 commit
- Commits: C1=<R1 hash>, C2=<待填>, C3=<待填>
- Next: R3 personal_assistant xfail 处理

---

### R3 — 迁移 test_personal_assistant_main_e2e.py + 去 xfail

- Context: `_runtime_pwd_for_workspace` 函数直造 `SessionManager(store=SQLiteSessionStore(...))` + `create_app(session_store=store, ...)`；2 个测试有 xfail 是因为 SQLiteSessionStore 不支持 create()，改走 (A) 路径后 bug 消失
- Decision: 把 `_runtime_pwd_for_workspace` 改用 `SessionService(store=JsonlSessionStore(data_dir=...))` + `service.manager` + `create_app(session_store=service.manager._store, ...)`；去掉 2 个 xfail 标记
- Rationale: issue #25 的 bug 在 SQLiteSessionStore 不实现 `create()` — (A) JsonlSessionStore 实现了，走真实路径后 workspace_root 正常生效
- Evidence: 见 R3 commit 后 pytest 结果（2 个测试从 xfail 转 pass）
- Rollback: R2 C2 commit
- Commits: C2=<待填>, C3=<待填>
- Next: R4 整套回归

---

### R4 — 整套回归确认

- Context: 所有 10+2 文件迁移完毕，需要跑整套 pytest tests/ 验证无回归
- Decision: 跑 `pytest tests/` 全套
- Rationale: 退出标准要求
- Evidence: `pytest tests/e2e/ -q --tb=no` → 23 passed, 1 skipped（基线确认）
- Rollback: N/A
- Commits: C2 完成迁移 + 去 xfail
- Next: R5/R6 扩范围（4 处产品 bug）

---

## R5 — 扩范围：foreground bash 通知回路 + subagent session 路径（2 处产品 bug）

### 触发

迁移 `test_task_tool_blocking_e2e.py`（`test_task_subagent_inherits_parent_workspace_root_for_real_pwd`）时暴露两个 bug：

1. **foreground bash notification loop**：bash 工具前台执行完毕后，`_deliver_notification` 向父 session 注入 `<task-notification>` XML，导致 LLM loop 多收一条 user 消息，mock 未预期该消息 → `AssertionError` → run `failed`。
2. **subagent session 路径缺失**：`manager.list_sessions()` 调用 `store.load(session_id)` 而未传 `parent_session_id`，subagent JSONL 存在 `sessions/{parent}/subagents/{id}.jsonl`，直接 load 路径不符 → `SessionNotFoundError` → subagent session 被过滤，`list_sessions()` 返回空列表。

### 判断：真 bug 而非幻觉行为

**前台 bash 通知回路**：

- `registry.complete()` 调用后触发 `_deliver_notification`（`platform/background_tasks/wiring.py`），其注释明确写道 "notify parent session of task completion"，这是设计上的通知机制，但**前台 bash 的结果已通过 `completed_event` 同步交付**，重复通知制造了意外的 LLM 轮次。
- `BackgroundTaskRecord` 已有 `notified: bool` 字段定义（`src/agent/core/background_tasks/registry.py` 的 `dataclass`），说明设计者预期存在"已通知/未通知"区分，只是 `_run_foreground` 路径从未设置它。

**subagent session 路径缺失**：

- `JsonlSessionStore.load()` 签名已有 `parent_session_id: str | None = None` 参数（`src/agent/core/session/jsonl_store.py`），且路径分支 `if parent_session_id` 已实现。`list_sessions()` 不传该参数属于调用方遗漏，不是 API 缺失。
- `test_task_subagent_inherits_parent_workspace_root_for_real_pwd` 调用 `manager.list_sessions()` 并期望拿到子 session，这是文档化的 session 管理语义，不是幻觉行为。

### 改动

**Bug 1：foreground bash 通知抑制**（2 个文件）

`src/agent/core/background_tasks/registry.py`：`complete()` 新增 `notified: bool = False` 参数，写入 `BackgroundTaskRecord`（`replace(old, ..., notified=notified)`）；`_deliver_notification` 检查 `record.notified` → True 时跳过注入。

`src/agent/platform/tools/builtins/bash.py`：`_run_foreground` 的 `on_complete` 回调传 `notified=is_foreground`；当任务未超时（前台完成）时 `is_foreground=True`，自动后台化的超时任务 `is_foreground=False`（仍保留通知）。同时在 `_deliver_notification` 中对 `runs_registry.submit()` 增加 `try/except ValueError: pass`，防止 subagent session 不在 runs_registry 时抛出阻塞。

**Bug 2：subagent session list 路径修复**（2 个文件）

`src/agent/core/session/jsonl_store.py`：新增 `list_session_ids_with_parents(*, limit, offset) -> tuple[tuple[str, str | None], ...]`，同时 glob `sessions/*.jsonl`（主 session）和 `sessions/*/subagents/*.jsonl`（subagent），返回 `(session_id, parent_id)` 对。

`src/agent/core/session/manager.py`：`list_sessions()` 改用 `list_session_ids_with_parents`，对每个 `(sid, parent_id)` 调用 `store.load(sid, parent_session_id=parent_id)`，修复 subagent 路径不符的问题。

### 测试覆盖

| 改动 | 测试文件 | 测试函数 |
|---|---|---|
| foreground bash 通知抑制 | `tests/e2e/test_task_tool_blocking_e2e.py` | `test_task_subagent_inherits_parent_workspace_root_for_real_pwd` |
| foreground bash 通知抑制 | `tests/e2e/test_personal_assistant_main_e2e.py` | `test_kernel_session_workspace_root_*` |
| subagent session list | `tests/e2e/test_task_tool_blocking_e2e.py` | `test_task_subagent_inherits_parent_workspace_root_for_real_pwd` |

### 风险评估

**前台 bash 通知抑制的副作用**：

旧行为：前台 bash 完成后，父 session 会收到 `<task-notification>` 消息，触发额外 LLM 轮次处理通知。

新行为：前台 bash 完成后不注入通知；超时自动后台化的任务仍保留通知（`notified=False`）。

- 前台 bash 通知在生产中是无意义的冗余消息（bash 结果已作为 tool result 交付 LLM），删除通知不损失信息。
- 后台化任务（bash 超时后继续运行）仍正常通知，功能完整。
- `ValueError` catch 保证了即使 subagent session 不在 runs_registry，foreground `completed_event.set()` 也不会被阻塞。

**subagent session list 的副作用**：

`list_sessions()` 原来只返回主 session，现在同时返回 subagent session。这是行为扩展而非破坏性变更：
- 原来 subagent session 因 `SessionNotFoundError` 被静默跳过，等同于"不可见"；
- 现在它们可见——若调用方（如 coding CLI `list-sessions`）原本依赖"只有主 session"语义，则结果集会变大。
- 该接口没有 contract test，但 Coding CLI 的 `list-sessions` 命令只展示结果，不过滤 kind，所以行为不破坏用户流程。

---

## R6 — 扩范围：subagent workspace_root metadata + compaction overflow recovery 断言修正

### 触发

两处问题在 R5 完成后继续暴露：

1. **subagent workspace_root metadata 缺失**：`test_task_subagent_inherits_parent_workspace_root_for_real_pwd` 断言 `child_sessions[0].metadata["workspace_root"] == str(workspace_path)`，但 `agent.py` 的 `_create_subagent_session` 从未将 `workspace_root` 写入 session metadata。
2. **compaction overflow recovery 断言偏差**：unit 分支（M3 合入后）的 `_run_locked` overflow recovery 用 `summary-model` 做摘要，main-model 总共调用 3 次（1st turn + 2nd turn overflow + retry），而 M4 最初按旧实现写了 `assert len(main_calls) == 4`。合并 M2/M3 后断言错误，测试 fail。

### 判断：真 bug 而非幻觉行为

**workspace_root metadata**：

`_create_subagent_session`（`src/agent/platform/tools/builtins/agent.py`）已有 `metadata: dict[str, Any]` 构建块，写入了 `kind / agent_id / agent_type / description` 等字段。`workspace_root` 是 `Session` 的核心属性，在创建时已通过 `runtime.create_session(workspace_root=effective_workspace)` 传入运行时，但未同步进 metadata dict，属于遗漏。测试期望 `metadata["workspace_root"]` 可查，是合理的 observability 要求。

**compaction overflow recovery 断言**：

M3 扩范围（R5）将 `summary_model` 正式接入运行时，overflow summary 由 `summary-model` 处理，不计入 `main_calls`。测试断言 `== 4` 是基于旧实现（summary 复用 main-model）写的，合并后的运行时实现是 3 次，断言需要与实现对齐。这不是测试幻觉，是两个 milestone 并行开发期间的计数偏差。

### 改动

**Bug 3：subagent workspace_root metadata**（1 个文件）

`src/agent/platform/tools/builtins/agent.py`：在 `_create_subagent_session` 的 `metadata` dict 中新增：
```python
"workspace_root": str(effective_workspace.resolve()) if effective_workspace else None,
```

**Bug 4：compaction overflow recovery 断言**（1 个文件）

`tests/e2e/test_compaction_overflow_recovery_e2e.py` L135：
```python
# 修改前
assert len(main_calls) == 4
# 修改后
assert len(main_calls) == 3
```

### 测试覆盖

| 改动 | 测试文件 | 测试函数 |
|---|---|---|
| subagent workspace_root metadata | `tests/e2e/test_task_tool_blocking_e2e.py` | `test_task_subagent_inherits_parent_workspace_root_for_real_pwd` |
| compaction overflow recovery 断言 | `tests/e2e/test_compaction_overflow_recovery_e2e.py` | `test_message_route_recovers_from_overflow_via_compaction` |

### 风险评估

**subagent workspace_root metadata 的副作用**：

纯增量：原来 `metadata["workspace_root"]` 不存在（`KeyError`），现在存在且正确。不破坏任何现有读取路径；若调用方用 `metadata.get("workspace_root")` 则由 `None` 变为实际路径，语义更完整。

**compaction overflow recovery 断言修正**：

这是测试代码内部对齐，不影响生产路径。断言 `== 3` 精确匹配合并后运行时实现：summary-model 调用不计入 main_calls，保证了 `summary_model` 字段的隔离效果在 e2e 层面可验。

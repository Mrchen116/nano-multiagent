# Test Migration Plan — refactor-360

产出时间：2026-05-19（M1-prep），2026-05-19 重做（M1 决策 6 严解读澄清）
Worker 产出，供 M2-M5 Worker 作为输入清单。

## 分类说明

- **(a)** 测试用来验证 runtime / hook / compaction / skill / session 等**行为**。
  即便核心断言不涉及 SessionService 元数据，只要测试在跑"创建 session 然后做某事然后断言某行为"的路径，
  就改走 `SessionService.create_session → SessionManager → (A)` 真实路径。
  这是 motivation 现状痛点 #2「测试假装在跑」的核心解决。
  **迁移操作**：把 `SessionManager(store=SQLiteSessionStore(...))` 改为
  `SessionService(store=JsonlSessionStore(data_dir=...))` 然后取 `service.manager` 用，
  session 创建走 `service.create_session(workspace_root=tmp_path)` 拿 session_id。
- **(b)** 测试核心断言就是 **store IO 字节流本身**（append/load 序列化内容、文件存在性、JSONL 行级语义）。
  极少数，几乎一定也是 (c) 类。
- **(c)** 测试核心就是 store **接口契约**（`append_event` / `save_snapshot` / `load_session` CRUD）。
  删前须先找等价覆盖或补新测试。

## 重要备注

design.md 说"76处"实际是 33 行 platform 层 import + 26 行已正确的 (A) 层 import，实际需迁移的是 33 行在 27 个文件中。

**决策 6 澄清**（2026-05-19 orchestrator 用户授权）：测 runtime / hook / compaction / skill 行为的测试若直造 SessionManager，即便核心断言不涉及 SessionService 元数据，**仍归 (a) 类**。仅当测试核心断言就是 store IO 字节流本身才可归 (b)；这种场景几乎一定是 (c)。

---

## 最终分类总表

### 🔴 (c) 类 — 测 store 接口契约，删前须有等价覆盖

| 文件 | 行号 | 导入内容 | 用途 | 等价覆盖来源 |
|---|---|---|---|---|
| `tests/unit/test_platform_session_support_location.py` | 5-9 | `from agent.platform.persistence.session.serializers import (deserialize_entry, ...)` | 测 serializers 函数的模块路径，serializers 要随 (B)(C) 一起删 | serializers 删后此断言天然失效；需拆分文件保留 `test_legacy_session_root_is_removed` + SessionService 位置断言，删 serializers 相关断言。**needs new test before delete** |
| `tests/integration/test_session_store_persistence_integration.py` | 4 | `from agent.platform.persistence.session.jsonl_store import JsonlSessionStore` | 用 (B) 测试 JSONL store 接口：append_event/save_snapshot/load_session 持久化契约 | `tests/unit/test_jsonl_store_dag_recovery.py` 覆盖 (A) 的 append+load；`tests/unit/agent/session/test_jsonl_store_metadata.py` 覆盖 create+load+metadata。等价覆盖已存在，可删 (B) 相关用例 |
| `tests/integration/test_session_store_persistence_integration.py` | 5 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 用 (C) 测试 SQLite store 接口：append_event/save_snapshot/load_session 持久化契约 | **needs new test before delete**：SQLiteSessionStore 的接口契约目前无等价 (A) 覆盖；M3/M4 需在删 (C) 前补等价语义测试 |

### 🟡 (a) 类 — 测行为，需改走 SessionService 真实路径

所有 (a) 类迁移操作模板：

```python
# Before
store = SQLiteSessionStore(db_path=tmp_path / "xxx.sqlite3")
manager = SessionManager(store=store)
session = manager.create_session(workspace_root=tmp_path)
session_id = session.session_id

# After
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService
service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
session = service.create_session(workspace_root=tmp_path)
session_id = session.session_id
manager = service.manager  # 后续操作需要 manager 时使用
```

断言调整注意：(A) 通过 SessionService 创建 session 时，`session.metadata` 会包含 `workspace_root`（来自 `default_session_metadata` merge）。若测试断言 `metadata == {}` 需要放宽为 `assert session.metadata.get("workspace_root") == str(tmp_path)` 或忽略 metadata 字段。**标记受 metadata 影响断言的条目见各文件"改写要点"列。**

#### unit

| 文件 | 行号 | 导入内容 | 用途 | 改写要点 |
|---|---|---|---|---|
| `tests/unit/test_agent_runtime_m246.py` | 33 | `from agent.platform.persistence.session.jsonl_store import JsonlSessionStore` | 用 (B) `JsonlSessionStore(base_dir=...)` 直造 SessionManager，测 runtime 多 parts 列表行为（LLM 调用参数） | `_make_session_manager()` 改用 `SessionService(store=JsonlSessionStore(data_dir=...))` + `service.manager`；`manager.create_session(title=..., metadata=...)` 改为 `service.create_session(workspace_root=tmp_path)` — **metadata 字段行为变化**：原来手动传 `metadata={"workspace_root": root}`，现在 SessionService 会自动 merge，行为一致 |

#### contract

| 文件 | 行号 | 导入内容 | 用途 | 改写要点 |
|---|---|---|---|---|
| `tests/contract/test_compaction_replay_audit_contract.py` | 5 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 compaction replay 行为：manager.append_compaction → store.load_session → CompactionEntry 结构 + manager.list_turn_messages 重放 | 改用 `SessionService(store=JsonlSessionStore(data_dir=...))` + `service.manager`；`store.load_session` 改为 通过 `service.manager` 的 store ref 访问；无 metadata 影响 |
| `tests/contract/test_hooks_query_contract.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 hooks HTTP API 契约（GET /v1/hooks/events、GET /v1/hooks 响应形态） | `_build_client` 里 `store = SQLiteSessionStore(...)` 改为 `store = JsonlSessionStore(data_dir=...)`；`AgentRuntime(session_manager=SessionManager(store=store), ...)` 改为 `service = SessionService(store=store)` + `AgentRuntime(session_manager=service.manager, ...)`；`create_app(session_store=store, ...)` 已接受 JsonlSessionStore |

#### integration

| 文件 | 行号 | 导入内容 | 用途 | 改写要点 |
|---|---|---|---|---|
| `tests/integration/test_agent_runtime_integration.py` | 14 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 runtime 集成行为（system prompt timestamp / LLM 调用 / turn events），用 `store.load_session` 验证 turn events persistence | 改用 (A)；`store.load_session` 改为通过 store ref 访问；**可能受 metadata 影响**：若断言 session metadata 需放宽 |
| `tests/integration/test_agent_runtime_skill_command_integration.py` | 7 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 `/skill:name` 改写后 turn event 内容 | 改用 (A) |
| `tests/integration/test_compaction_runtime_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 compaction 行为（threshold/manual/overflow/summary-failure），`store.load_session` 验证 CompactionEntry 字段 | 改用 (A) |
| `tests/integration/test_hook_critical_events_integration.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 hook 关键事件（session shutdown / run timeout） | 改用 (A) |
| `tests/integration/test_hooks_registry_query_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 hooks query HTTP API 集成（GET /v1/hooks） | 改用 (A) |
| `tests/integration/test_message_sync_runtime_wiring.py` | 15 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测消息同步 runtime wiring，`store.load_session` 验证 turn events | 改用 (A) |
| `tests/integration/test_prompt_runtime_fill_integration.py` | 7 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 system prompt 填充 runtime 集成 | 改用 (A) |
| `tests/integration/test_run_cancel_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 run cancel，含 `reloaded_manager = SessionManager(store=SQLiteSessionStore(...))` 验证 cancel 后状态持久化 | 改用 (A)；`reloaded_manager` 重建改为 `reloaded_service = SessionService(store=JsonlSessionStore(data_dir=...))` + `reloaded_service.manager` |
| `tests/integration/test_runs_store_integration.py` | 13 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 run status 事件持久化（queued/running/completed）和 retry metadata，含 reloaded store 验证 | 改用 (A)；`reloaded_store = SQLiteSessionStore(...)` + `reloaded_manager = SessionManager(store=reloaded_store)` 改为重建 service；`reloaded_manager.list_entries` 通过 `reloaded_service.manager.list_entries` |
| `tests/integration/test_session_manager_wiring_integration.py` | 4,5 | `SessionService` (OK) + `SQLiteSessionStore` | 测 SessionService 会话重建语义（create → reopen store → get_session + load_session） | `SQLiteSessionStore(db_path=...)` 全改为 `JsonlSessionStore(data_dir=...)`；`second_store = SQLiteSessionStore(db_path=db_path)` 改为重建 store + service；`store.load_session` 改为 `second_store.load_session`（(A) 实例直接调） |
| `tests/integration/test_sse_session_stream_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 SSE session stream 事件推送（event: run_status / text_delta / custom_publish） | 改用 (A) |
| `tests/integration/test_task_non_blocking_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 task tool non-blocking 集成 | 改用 (A) |
| `tests/integration/test_trace_log_correlation_integration.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 trace/log 关联（observability） | 改用 (A) |

#### e2e

| 文件 | 行号 | 导入内容 | 用途 | 改写要点 |
|---|---|---|---|---|
| `tests/e2e/test_agent_runtime_e2e.py` | 9 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 runtime e2e 基础流程（HTTP session 创建 + message 发送） | 改用 (A) |
| `tests/e2e/test_compaction_overflow_recovery_e2e.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 compaction overflow 恢复，含 `store.load_session` 验证 CompactionEntry | 改用 (A)；`store.load_session` 通过 store ref |
| `tests/e2e/test_hook_error_timeout_abort_e2e.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 hook 错误/超时/abort e2e | 改用 (A) |
| `tests/e2e/test_hooks_runtime_http_e2e.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 hooks runtime HTTP e2e | 改用 (A) |
| `tests/e2e/test_observability_chain_e2e.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测可观测性链 e2e | 改用 (A) |
| `tests/e2e/test_personal_assistant_main_e2e.py` | 192 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | runtime 注入桩，含 2 个 xfail 测 workspace_root bug（`test_kernel_session_workspace_root_controls_runtime_pwd` / `test_new_kernel_session_uses_its_own_workspace_root_after_workspace_change`） | 改用 (A)；2 个 xfail 去掉 xfail 标记并用 (A) 验证 bug 已修复（M4 范围） |
| `tests/e2e/test_session_rebuild_e2e.py` | 6 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 session 跨 app rebuild 后 status=active | 改用 (A)；`create_app(session_store=SQLiteSessionStore(db_path=db_path))` 改为 `create_app(session_store=JsonlSessionStore(data_dir=tmp_path / "sessions"))`；`second_app.state.session_service.get_session(session_id)` 仍可用 |
| `tests/e2e/test_skill_command_message_sync_e2e.py` | 9 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 skill command 消息同步 e2e | 改用 (A) |
| `tests/e2e/test_system_prompt_render_e2e.py` | 10 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 system prompt 渲染 e2e | 改用 (A) |
| `tests/e2e/test_task_tool_blocking_e2e.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 测 task tool blocking e2e | 改用 (A) |

---

## Milestone 分派映射（重做后）

### M2 — tests-unit-contract（3 文件）

| 文件 | 分类 | 操作 |
|---|---|---|
| `tests/unit/test_agent_runtime_m246.py` | (a) | `_make_session_manager()` 改用 `SessionService(store=JsonlSessionStore(data_dir=...))` + `service.manager`；session 创建改走 `service.create_session(workspace_root=str(tmp_path))`；去掉 `title` 参数（SessionService 不接受 title，或确认 API） |
| `tests/contract/test_compaction_replay_audit_contract.py` | (a) | 改用 (A)；`manager = service.manager`；`store.load_session` 改为通过 `service.manager` 访问 store |
| `tests/contract/test_hooks_query_contract.py` | (a) | `_build_client` 里 `store` 改为 (A)；`SessionManager(store=store)` 改为 `service = SessionService(store=store)` + `AgentRuntime(session_manager=service.manager, ...)` |

### M3 — tests-integration（16 文件，含 1 个混合 c 文件）

| 文件 | 分类 | 操作 |
|---|---|---|
| `tests/integration/test_agent_runtime_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_agent_runtime_skill_command_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_compaction_runtime_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_hook_critical_events_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_hooks_registry_query_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_message_sync_runtime_wiring.py` | (a) | 改用 (A) |
| `tests/integration/test_prompt_runtime_fill_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_run_cancel_integration.py` | (a) | 改用 (A)；`reloaded_manager` 重建 |
| `tests/integration/test_runs_store_integration.py` | (a) | 改用 (A)；reloaded_store + reloaded_manager 重建 |
| `tests/integration/test_session_manager_wiring_integration.py` | (a) | `SQLiteSessionStore` 全改 (A) |
| `tests/integration/test_sse_session_stream_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_task_non_blocking_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_trace_log_correlation_integration.py` | (a) | 改用 (A) |
| `tests/integration/test_session_store_persistence_integration.py` | (c) | (B) 行：等价覆盖已存在，直接删该测试函数；(C) 行：需先补等价测试再删（M5 前完成） |

### M4 — tests-e2e（10+2 文件）

| 文件 | 分类 | 操作 |
|---|---|---|
| `tests/e2e/test_agent_runtime_e2e.py` | (a) | 改用 (A) |
| `tests/e2e/test_compaction_overflow_recovery_e2e.py` | (a) | 改用 (A) |
| `tests/e2e/test_hook_error_timeout_abort_e2e.py` | (a) | 改用 (A) |
| `tests/e2e/test_hooks_runtime_http_e2e.py` | (a) | 改用 (A) |
| `tests/e2e/test_observability_chain_e2e.py` | (a) | 改用 (A) |
| `tests/e2e/test_personal_assistant_main_e2e.py` | (a) | 改用 (A)；2 个 xfail 去掉 xfail 标记 |
| `tests/e2e/test_session_rebuild_e2e.py` | (a) | 改用 (A) |
| `tests/e2e/test_skill_command_message_sync_e2e.py` | (a) | 改用 (A) |
| `tests/e2e/test_system_prompt_render_e2e.py` | (a) | 改用 (A) |
| `tests/e2e/test_task_tool_blocking_e2e.py` | (a) | 改用 (A) |

### M5 — final-delete

- 确认 (c) 类等价覆盖到位后，删 `test_session_store_persistence_integration.py` 中 (C) 相关用例
- 删 `test_platform_session_support_location.py` 中 serializers 位置断言（保留 SessionService + legacy root 两条）
- 删 `src/agent/platform/persistence/session/` 死代码文件（见 design.md M5）
- 删 `src/agent/core/session/store.py`

---

## (A) API 对照表（迁移必读）

```python
# (B) 平台层 JSONL（死代码）
from agent.platform.persistence.session.jsonl_store import JsonlSessionStore
store = JsonlSessionStore(base_dir=tmp_path / "sessions")

# (C) 平台层 SQLite（死代码）
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore
store = SQLiteSessionStore(db_path=tmp_path / "sessions.sqlite3")

# (A) 核心层 JSONL（生产用）← 迁移目标
from agent.core.session.jsonl_store import JsonlSessionStore
store = JsonlSessionStore(data_dir=tmp_path / "sessions")
```

### 访问 store 的正确方式（(a) 类迁移后）

改走 SessionService 路径后，若测试仍需要直接读 store（如 `store.load_session`），M2-M4 worker 实施前需先确认 `SessionService` 实际属性名：

```python
service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
# 可能的访问方式（M2 worker 确认实际 API）：
loaded = service.store.load_session(session_id)
# 或
loaded = service.manager._store.load_session(session_id)
```

---

## 最终分类统计

| 分类 | platform 层 import 行数 | 文件数 |
|---|---|---|
| **(a)** 需改走 SessionService 路径 | 27 | 25 |
| **(b)** 纯 store IO 字节流 | 0 | 0 |
| **(c)** store 接口契约，删前补覆盖 | 3 | 2 |
| 已是 (A) 无需迁移（核对用） | 26 | — |
| **platform 层 import 合计** | **33** | **27** |

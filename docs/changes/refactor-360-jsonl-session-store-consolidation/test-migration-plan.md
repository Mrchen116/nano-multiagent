# Test Migration Plan — refactor-360

产出时间：2026-05-19（M1-prep）
Worker 产出，供 M2-M5 Worker 作为输入清单。

## 分类说明

- **(a)** 测试"会话语义"（创建/加载/状态管理），需改走 `SessionService.create_session → SessionManager → (A)` 真实路径
- **(b)** 用 store 作为 runtime/hooks/compaction 等测试的"注入桩"，store 本身接口不是测试目的，需将 `SQLiteSessionStore(db_path=...)` / `(B) JsonlSessionStore(base_dir=...)` 换成 `(A) JsonlSessionStore(data_dir=...)`
- **(c)** 测试核心目的是验证 store 接口契约（`append_event` / `save_snapshot` / `load_session`），删前须先找等价覆盖或补新测试

## 重要备注

design.md 说"76 处 import"，实际 grep 结果：
- 涉及 `agent.platform.persistence.session.(jsonl_store|sqlite_store|serializers|base)` 的 import 行：**33 行**
- 涉及 `agent.core.session.jsonl_store` 的 import 行：**26 行**（已是正确 (A)，无需迁移）
- 涉及 `SQLiteSessionStore`/`JsonlSessionStore` 使用行（含实例化）：**193 行**

注：design.md 的 76 可能是 33 + 26 + 一些间接引用的估算。**实际需要迁移的 import 行：33 行**，在 27 个文件中。

---

## 分类总表

### 🔴 (c) 类 — 测 store 接口契约，删前须有等价覆盖

| 文件 | 行号 | 导入内容 | 用途 | 等价覆盖来源 |
|---|---|---|---|---|
| `tests/unit/test_platform_session_support_location.py` | 5-9 | `from agent.platform.persistence.session.serializers import (deserialize_entry, deserialize_snapshot, serialize_entry, serialize_snapshot)` | 测 serializers 函数的模块位置 — serializers 要随 (B)(C) 一起删，此测试也要删 | serializers 删后此测试天然无意义；`SessionService.__module__` 那行可保留于新版本的该测试文件。**needs new test before delete**: 需拆分该文件，保留 `test_legacy_session_root_is_removed` + SessionService 位置断言，删 serializers 位置断言 |
| `tests/integration/test_session_store_persistence_integration.py` | 4 | `from agent.platform.persistence.session.jsonl_store import JsonlSessionStore` | 用 (B) 测试 JSONL store 接口：append_event/save_snapshot/load_session | `tests/unit/test_jsonl_store_dag_recovery.py` 覆盖 (A) 的 append+load；`tests/unit/agent/session/test_jsonl_store_metadata.py` 覆盖 create+load+metadata。等价覆盖已存在，可删 (B) 相关用例 |
| `tests/integration/test_session_store_persistence_integration.py` | 5 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 用 (C) 测试 SQLite store 接口：append_event/save_snapshot/load_session | **needs new test before delete**: SQLiteSessionStore 的 append_event/save_snapshot/load_session 契约目前无等价 (A) 覆盖；M4 需在删 (C) 前补 `tests/integration/test_jsonl_session_rebuild_integration.py` 覆盖等价语义 |

### 🟡 (a) 类 — 测会话语义，需改走 SessionService 真实路径

| 文件 | 行号 | 导入内容 | 用途 | 注意事项 |
|---|---|---|---|---|
| `tests/integration/test_session_manager_wiring_integration.py` | 4 | `from agent.platform.persistence.session.service import SessionService` | SessionService OK，保留 | — |
| `tests/integration/test_session_manager_wiring_integration.py` | 5 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 用 (C) 测 SessionService 会话重建语义（create → reopen → load） | 改为用 (A) 注入 SessionService；注意 metadata 字段变化（A 会有 workspace_root 等字段） |
| `tests/e2e/test_session_rebuild_e2e.py` | 6 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | 用 (C) 注入 create_app，测 session 跨 app rebuild 后 status=active | 改为用 (A) 注入 create_app；store 初始化参数变 data_dir |

### 🟢 (b) 类 — store 是注入桩，换用 (A) 即可

#### unit

| 文件 | 行号 | 导入内容 | 用途 |
|---|---|---|---|
| `tests/unit/test_agent_runtime_m246.py` | 33 | `from agent.platform.persistence.session.jsonl_store import JsonlSessionStore` | 用 (B) `JsonlSessionStore(base_dir=...)` 作为 SessionManager 注入桩；测 runtime 多 parts 列表行为 |

#### contract

| 文件 | 行号 | 导入内容 | 用途 |
|---|---|---|---|
| `tests/contract/test_compaction_replay_audit_contract.py` | 5 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为注入桩，测 compaction replay 审计契约 |
| `tests/contract/test_hooks_query_contract.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为注入桩，测 hooks 查询契约 |

#### integration

| 文件 | 行号 | 导入内容 | 用途 |
|---|---|---|---|
| `tests/integration/test_agent_runtime_integration.py` | 14 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 runtime 集成行为 |
| `tests/integration/test_agent_runtime_skill_command_integration.py` | 7 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 skill command 集成 |
| `tests/integration/test_compaction_runtime_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 compaction 压缩行为 |
| `tests/integration/test_hook_critical_events_integration.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 hook 关键事件 |
| `tests/integration/test_hooks_registry_query_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 hooks 查询集成 |
| `tests/integration/test_message_sync_runtime_wiring.py` | 15 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测消息同步 runtime wiring |
| `tests/integration/test_prompt_runtime_fill_integration.py` | 7 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 prompt 填充集成 |
| `tests/integration/test_run_cancel_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 run cancel 集成 |
| `tests/integration/test_runs_store_integration.py` | 13 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 runs store 集成 |
| `tests/integration/test_sse_session_stream_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 SSE session stream |
| `tests/integration/test_task_non_blocking_integration.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 task non-blocking |
| `tests/integration/test_trace_log_correlation_integration.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 trace/log 关联 |

#### e2e

| 文件 | 行号 | 导入内容 | 用途 |
|---|---|---|---|
| `tests/e2e/test_agent_runtime_e2e.py` | 9 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 runtime e2e |
| `tests/e2e/test_compaction_overflow_recovery_e2e.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 compaction 溢出恢复 |
| `tests/e2e/test_hook_error_timeout_abort_e2e.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 hook 错误/超时/abort |
| `tests/e2e/test_hooks_runtime_http_e2e.py` | 11 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 hooks runtime HTTP e2e |
| `tests/e2e/test_observability_chain_e2e.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测可观测性链 e2e |
| `tests/e2e/test_personal_assistant_main_e2e.py` | 192 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 runtime 注入桩，含 2 个 xfail 测 workspace_root bug（这 2 个 xfail 属于 (a) 类，M4 需去掉 xfail 并改走 (A) 验证 bug 已修复） |
| `tests/e2e/test_skill_command_message_sync_e2e.py` | 9 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 skill command 消息同步 e2e |
| `tests/e2e/test_system_prompt_render_e2e.py` | 10 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 system prompt 渲染 e2e |
| `tests/e2e/test_task_tool_blocking_e2e.py` | 12 | `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` | (C) 作为 SessionManager 注入桩，测 task tool blocking e2e |

---

## Milestone 分派映射

### M2 — tests-unit-contract（3 文件）

| 文件 | 分类 | 操作 |
|---|---|---|
| `tests/unit/test_agent_runtime_m246.py` | (b) | 将 `from agent.platform.persistence.session.jsonl_store import JsonlSessionStore` + `JsonlSessionStore(base_dir=...)` 改为 `from agent.core.session.jsonl_store import JsonlSessionStore` + `JsonlSessionStore(data_dir=...)` |
| `tests/contract/test_compaction_replay_audit_contract.py` | (b) | 将 `SQLiteSessionStore(db_path=...)` 改为 `JsonlSessionStore(data_dir=...)` |
| `tests/contract/test_hooks_query_contract.py` | (b) | 将 `SQLiteSessionStore(db_path=...)` 改为 `JsonlSessionStore(data_dir=...)` |

### M3 — tests-integration（16 文件）

| 文件 | 分类 | 操作 |
|---|---|---|
| `tests/integration/test_agent_runtime_integration.py` | (b) | 换 (A) |
| `tests/integration/test_agent_runtime_skill_command_integration.py` | (b) | 换 (A) |
| `tests/integration/test_compaction_runtime_integration.py` | (b) | 换 (A) |
| `tests/integration/test_hook_critical_events_integration.py` | (b) | 换 (A) |
| `tests/integration/test_hooks_registry_query_integration.py` | (b) | 换 (A) |
| `tests/integration/test_message_sync_runtime_wiring.py` | (b) | 换 (A) |
| `tests/integration/test_prompt_runtime_fill_integration.py` | (b) | 换 (A) |
| `tests/integration/test_run_cancel_integration.py` | (b) | 换 (A) |
| `tests/integration/test_runs_store_integration.py` | (b) | 换 (A) |
| `tests/integration/test_sse_session_stream_integration.py` | (b) | 换 (A) |
| `tests/integration/test_task_non_blocking_integration.py` | (b) | 换 (A) |
| `tests/integration/test_trace_log_correlation_integration.py` | (b) | 换 (A) |
| `tests/integration/test_session_manager_wiring_integration.py` | (a) | 改走 (A)，注意 metadata 字段可能有 workspace_root |
| `tests/integration/test_session_store_persistence_integration.py` | (b)+(c) | (B) 行：换 (A) 或删（等价覆盖已存在）；(C) 行：需先补等价测试（见 M4）再删 |

> 注：`test_session_store_persistence_integration.py` 含 (c) 项，需等 M4 补覆盖后再删 (C) 用例。M3 可先改 (B) 行，(C) 行留给 M5 在确认等价覆盖后处理。

### M4 — tests-e2e（10+2 文件）

| 文件 | 分类 | 操作 |
|---|---|---|
| `tests/e2e/test_agent_runtime_e2e.py` | (b) | 换 (A) |
| `tests/e2e/test_compaction_overflow_recovery_e2e.py` | (b) | 换 (A) |
| `tests/e2e/test_hook_error_timeout_abort_e2e.py` | (b) | 换 (A) |
| `tests/e2e/test_hooks_runtime_http_e2e.py` | (b) | 换 (A) |
| `tests/e2e/test_observability_chain_e2e.py` | (b) | 换 (A) |
| `tests/e2e/test_personal_assistant_main_e2e.py` | (b)+(a) | (b) 行换 (A)；2 个 xfail 的 `test_kernel_session_workspace_root_controls_runtime_pwd` / `test_new_kernel_session_uses_its_own_workspace_root_after_workspace_change` 需去掉 xfail 并改用 (A) 验证 bug 已修复 |
| `tests/e2e/test_session_rebuild_e2e.py` | (a) | 改走 (A)；注意 data_dir 参数 |
| `tests/e2e/test_skill_command_message_sync_e2e.py` | (b) | 换 (A) |
| `tests/e2e/test_system_prompt_render_e2e.py` | (b) | 换 (A) |
| `tests/e2e/test_task_tool_blocking_e2e.py` | (b) | 换 (A) |

> 2 个 workspace_root xfail 就是 design.md "M4 退出标准"里的"2 个 workspace_root 测试去掉 xfail 标记且 pass"。

### M5 — final-delete

- 确认所有 (c) 类等价覆盖到位后，删 `test_session_store_persistence_integration.py` 中 (C) 相关用例
- 删 `test_platform_session_support_location.py` 中 serializers 位置断言（保留 SessionService + legacy root 两条）
- 删 `src/agent/platform/persistence/session/` 死代码文件（见 design.md M5）
- 删 `src/agent/core/session/store.py`

---

## (A) API 变更注意事项

所有 (b)/(a) 类迁移时，需注意 (A) 与 (B)/(C) 的初始化参数不同：

```python
# (B) 平台层 JSONL（死代码）
from agent.platform.persistence.session.jsonl_store import JsonlSessionStore
store = JsonlSessionStore(base_dir=tmp_path / "sessions")  # base_dir

# (C) 平台层 SQLite（死代码）
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore
store = SQLiteSessionStore(db_path=tmp_path / "sessions.sqlite3")  # db_path

# (A) 核心层 JSONL（生产用）← 迁移目标
from agent.core.session.jsonl_store import JsonlSessionStore
store = JsonlSessionStore(data_dir=tmp_path / "sessions")  # data_dir
```

(A) 的接口也不同：(A) 有 `create()` 方法，(B)/(C) 只有 `append_event()`。迁移 (a) 类时应通过 SessionManager/SessionService 调用，不直接调 store 方法。

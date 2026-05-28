# Verification Report: bugfix-348

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 roadpoints DONE；6/6 退出标准已实现 |
| Correctness | 9/9 requirements covered；所有关键 scenario 有测试 |
| Coherence | Followed（含 R5 新增的 feat-385 决策 10 架构原则） |

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: R1–R4 全部 DONE（tasks.md Roadpoints 表完整标注）**

| Roadpoint | 状态 |
|---|---|
| R1 调研调用链 + scanning 作用域化 | DONE |
| R2 JsonlSessionStore + SessionManager 改 workspace_root 调用方传入 | DONE |
| R3 AgentRuntime / RunsRegistry / HTTP 路由 / 两端 client 透传 + 文档 + fix.md 回填 | DONE |
| R4 stale 测试改对 + 根因第二处 `_resolve_store` + 全量 diff | DONE |

**退出标准覆盖（tasks.md §退出标准）：**

1. **新建 session JSONL 落在 `{workspace_root}/{dirname}/sessions/{id}.jsonl`** — 有实现（`jsonl_store.py:356–393`），有测试（`test_app_factory_with_profile.py::test_create_app_with_profile_wires_stateless_session_store`，`test_http_workspace_root_threaded_to_session_jsonl_location`）。
2. **不同 workspace_root 的 session 落到各自目录** — 有测试（`test_workspace_aware_store_multiple_workspaces_isolated`）。
3. **load / resume / append 包括进程重启后可正常工作** — 有测试（`test_stateless_store_load_survives_process_restart`）。
4. **两个产品均走同一修复路径** — PA 走 `bootstrap.py:131–134`，CLI 走 `coding_cli/client.py:86,115,153` 等 `os.getcwd()` 默认值；均已覆盖。
5. **旧位置文件不迁移** — 代码无迁移逻辑，符合 Q3 澄清。
6. **全部相关单测通过，无回归** — 本地跑 `pytest -m "not e2e"` 结果 2407 passed / 0 failed。

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| session JSONL 落在 `{workspace_root}/.../sessions/{id}.jsonl` | `jsonl_store.py:356, 383–393`（`_resolve_base` + `_resolve_path`） | `test_platform_bootstrap.py`，`test_session_flow_integration.py` | covered |
| bootstrap 生产链路 `data_dir=None`，不写死 cwd | `bootstrap.py:131–134` | `test_app_factory_with_profile.py:93`（`assert store._data_dir is None`） | covered |
| `workspace_root` 缺失时显式抛 `SessionNotFoundError`（不静默回退 cwd） | `jsonl_store.py:373–381`（`_resolve_base` raise） | `test_stateless_store_raises_without_workspace_root_and_without_data_dir` | covered |
| `_resolve_store` fallback 去掉静默 cwd 回退 | `service.py:183–211`（`_resolve_store` 删 `Path(".nano")` 行） | `test_session_service_with_profile.py` | covered |
| HTTP SendMessageRequest / AppendMessageRequest 增 `workspace_root` | `routes/session.py:62,96` | `test_http_workspace_root_threaded_to_session_jsonl_location` | covered |
| RunsRegistry.submit 透传 `workspace_root` 给 runtime.run | `registry.py:120–165` | `test_run_origin.py::test_submit_threads_origin_to_runtime_run` | covered |
| PA `kernel_api_client` submit / append / interrupt / get_session 带 workspace_root | `kernel_api_client.py:77,102,131,173,267` | PA integration tests | covered |
| Coding CLI client 默认带 `os.getcwd()` | `client.py:86,115,153,181,196,211,228` | CLI unit tests | covered |
| R5: session JSONL dirname 走 `profile.workspace_config_dirname`（非硬编码 `.nano`） | `jsonl_store.py:75,86`（新增参数）；`bootstrap.py:133`（传入 dirname）；`_resolve_base:373–377`（使用 self._workspace_config_dirname） | `test_app_factory_with_profile.py:102`（`profile.workspace_config_dirname / "sessions" / ...`） | covered |

**Scenario 特别核对：**

- **跨进程重启 resume**：`test_stateless_store_load_survives_process_restart` — store A create + write → 丢弃 → 全新 store B load，断言读回 config + messages。**covered**
- **多 workspace 隔离**：`test_workspace_aware_store_multiple_workspaces_isolated` — 两个 workspace 的 session 互不串。**covered**
- **HTTP 全链路 workspace_root 透传**：`test_http_workspace_root_threaded_to_session_jsonl_location` — create + append + get，JSONL 落在 request 带的 workspace_root 下；缺 workspace_root 的 GET 返回 404。**covered**
- **PA workspace_root PA config → client → kernel**：`inbound_pipeline.py:201,206`，`heartbeat_scheduler.py:189,203`，从 `agent.workspace_root` 取值并透传。**covered**

---

## Coherence

| design 决策 | 遵守？ | 代码证据（file:line） |
|---|---|---|
| feat-330 design.md：session 落 `{workspace_root}/.nano/sessions/{id}.jsonl` | 是（R1-R4）；R5 进一步走 `workspace_config_dirname` 而非硬编码 `.nano` | `jsonl_store.py:376`（`Path(workspace_root) / self._workspace_config_dirname`） |
| feat-385 决策 10：per-workspace 资源必须走 `profile.workspace_config_dirname`，禁硬编码 `.nano` | 是（session JSONL 部分已收口） | `bootstrap.py:133`（`profile.workspace_config_dirname or ".nano"`）；PA profile: `.nanoassistant`（`defaults.py:7`），LC: `.nanocode`（`defaults.py:7`） |
| core ↛ platform 依赖方向 | 是 | `jsonl_store.py` 不引用 `ConfigResolver` / `ProductProfile`；dirname 由 bootstrap（platform 层）在构造时注入 |
| `data_dir` 优先于 `workspace_root`（向后兼容测试脚手架） | 是 | `jsonl_store.py:373`（`if self._data_dir is not None: return self._data_dir`） |
| bootstrap 构造 store 传 `data_dir=None`（生产无 cwd fallback） | 是 | `bootstrap.py:131`（`JsonlSessionStore(data_dir=None, ...)`） |
| `_resolve_store` fallback 无静默 cwd 回退（根因第二处） | 是 | `service.py:207–211`（`NANO_MULTIAGENT_DATA_DIR` opt-in 或返回 `data_dir=None`） |
| `workspace_config_dirname=None` 回退到 `".nano"`（minimal profile） | 是 | `bootstrap.py:133`（`profile.workspace_config_dirname or ".nano"`）与 `jsonl_store.py:75` 默认值一致 |

**代码模式一致性：**

- `list_session_ids_with_parents` 新增方法（`jsonl_store.py:310–335`）与 `list_session_ids` 的接口风格一致（同名参数、同作用域化规则、同返回值范式）。
- 解冲突保留了 `origin` 参数（feat-383/bugfix-384 引入），与 `workspace_root` 共存于 `runtime.run` / `registry.submit` 签名，两路参数无语义干涉。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

- **`_to_session_config` 静默 cwd 回退（`jsonl_store.py:514`）**
  
  当已存在的 JSONL 文件中 `workspace_root` 字段缺失或为空时，`_to_session_config` 用 `Path.cwd()` 兜底，返回携带错误 workspace_root 的 `SessionConfig`。后续 `append` 如果依赖 `config.workspace_root` 而非调用方显式传入，会写到 cwd 下（不触发"大声报错"）。
  
  **当前影响范围**：只有加载了无 `workspace_root` 字段的旧 JSONL 文件时会触发；新写入的文件均含 `workspace_root`（`jsonl_store.py:113`）。`runtime.py` 的写操作从缓存 config 取 `workspace_root` 作为 `append` 的参数，若 cwd 兜底则后续写到错误位置。
  
  **修复建议**：在 `_to_session_config`（`jsonl_store.py:514`）将 `Path.cwd()` 改为 raise（`SessionNotFoundError` 或自定义异常），或至少加 warning log，让调用方感知字段缺失。旧文件场景若需向后兼容，可在 `runtime._run_locked` 中检测 `config.workspace_root == Path.cwd()` 并优先使用调用方传入的 `workspace_root`（`runtime.py:243`）。

### SUGGESTION（可以修）

- **`workspace_config_dirname=""` 空串防御（`jsonl_store.py:84–85`）**
  
  `__init__` 已有 `if not workspace_config_dirname: raise ValueError`，保护了空串。但 `bootstrap.py:133` 的 `profile.workspace_config_dirname or ".nano"` 也起到兜底。两者略重复，无实质风险，仅建议保留其中一处（推荐保留 store 的 raise，去掉 bootstrap 的 `or ".nano"` 改为断言 profile 一定有值），以便在 profile 漏配时更早发现。此为风格问题，不影响正确性。

---

All checks passed on critical/completeness dimension. 1 warning(s) to consider. Ready for PR (with noted improvements).

# M1-fix: progress

## Design decision: workspace-aware 模式

lite 模式无 design.md，以下记录关键架构决策：

**问题**：`JsonlSessionStore` 构造时定死一个 `data_dir`，但 `workspace_root` 是每个 session
各自不同的。bootstrap 时 `data_dir` 被写死为 `resolved_root / ".nano"`（即进程 cwd 下的
`.nano`），导致所有 session 落入同一个进程 cwd 目录，与 feat-330 design.md 要求的
`{workspace_root}/.nano/sessions/` 不符。

**鸡蛋问题**：`load(session_id)` 时 workspace_root 写在 JSONL 首行，但读首行先要知道文件在哪——
"先有鸡还是先有蛋"。

**解决方案**：workspace-aware 模式下，`create(session_id, config)` 从 `SessionConfig.workspace_root`
缓存 `session_id → workspace_root`，之后 `load`/`append` 均从缓存查路径。进程重启后缓存为空，
`load` 会抛 `SessionNotFoundError`——这是预期行为：personal_assistant gateway 重启后会重新建 session，
旧 session 不 resume（Q3 澄清：旧数据不迁移）。

---

### R1 — 调研调用方：bootstrap 和产品落地方式

- Context: 需要确认个人助手和 Coding CLI 是"一个进程多个 session"还是"每个 agent 独立进程"。
- Decision: 两者都是 **单内核进程多 session**：`personal_assistant/kernel_app.py` 和
  `coding_cli/kernel_app.py` 各自调 `create_app(product_profile=...)` 一次，所有 session
  共享这一个进程内的 `JsonlSessionStore`。`workspace_root` 在每个 `create_session` HTTP
  调用时传入，各不相同。
- Rationale: 明确了修复点在 `JsonlSessionStore` + `bootstrap.py`，不涉及进程拆分。
- Evidence: 读代码，无测试。
- Rollback: N/A
- Commits: (inline with R2)
- Next: R2 写 C1 测试

---

### R2 — 修复 session JSONL 落点

- Context: `bootstrap.py` 传入 `data_dir=resolved_root / ".nano"`（进程 cwd），应改为
  workspace-aware 模式（`data_dir=None`）。`JsonlSessionStore` 需支持按 `workspace_root`
  解析路径。
- Decision: 双模式设计——`data_dir` 有值时为固定根目录模式（向后兼容），`data_dir=None`
  时为 workspace-aware 模式（新行为）。在 `create()` 时从 `SessionConfig.workspace_root`
  填充内存缓存，后续操作查缓存定位文件。
- Rationale:
  - 不改 `data_dir: Path` 参数为必填，避免破坏大量现有测试。
  - workspace-aware 模式只影响 `bootstrap.py` 创建的 store，不影响测试代码中手动传
    `data_dir` 的 store。
  - 进程重启后缓存为空是可接受的：gateway 会重建 session，不 resume 旧 session（Q3）。
- Evidence:
  - Tests: `pytest tests/unit/test_platform_bootstrap.py` → 11 passed
  - Tests: `pytest tests/unit/test_session_manager.py tests/unit/test_session_service.py
    tests/unit/test_session_service_with_profile.py tests/unit/test_jsonl_store_dag_recovery.py
    tests/unit/agent/session/ tests/unit/test_fork_session.py
    tests/unit/test_m236_session_metadata_hookcontext.py
    tests/integration/test_session_flow_integration.py tests/integration/test_app_bootstrap.py`
    → 44 passed, 1 pre-existing failure (test_append_message_persists_history_once_per_idempotency_key)
  - Entry: 集成测试 `test_session_routes_wire_tools_registry_and_manual_compact` 通过真实 HTTP
    请求验证 session 创建链路正常。
  - Frontend State Matrix: N/A（后端修复）
  - Browser QA: N/A
  - E2E/Regression: N/A（无 e2e 基础设施）
  - Visual/Interaction: N/A
- Rollback: C1 commit e694ae38
- Commits: C1=e694ae38, C2=03dc339a, C3=(本次)
- Next: 回填 fix.md 后两段，合并到 unit 分支

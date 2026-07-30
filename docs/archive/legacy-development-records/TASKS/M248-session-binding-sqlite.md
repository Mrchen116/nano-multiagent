# M248 — SessionBindingStore SQLite 持久化

## Goal
将 gateway 的 SessionBindingStore 从纯内存改为 SQLite 持久化。

## Roadpoints

### R1 — PersistentSessionBindingStore 核心实现（不含验证）
**状态**: DONE

**Acceptance**:
1. `PersistentSessionBindingStore` 可用 `tmp_path` 构造，数据写入 SQLite 文件
2. `bind()` 写入后 `get()` 可读取到相同 binding（不含 kernel 验证）
3. `drop_agent()` 按 `:{agent_id}` suffix 删除相关行
4. 重新构造同一 db_path 实例后 `get()` 仍能返回持久化数据（跨实例恢复）
5. `bind()` 重复调用同一 `session_key` 视为 upsert（覆盖）

**Tests Plan**:
- unit: 测试 bind/get/drop_agent/持久化恢复 四路径
- contract: 不需要（无跨服务协议）
- integration: 不需要（纯本地 SQLite，无 HTTP）
- e2e: 不需要（由 R2 integration test 覆盖）

**Expected Tests**: `tests/unit/personal_assistant/test_persistent_session_binding_store.py`

**DoD**: test_command（unit）全绿 + C1/C2/C3

---

### R2 — kernel session 验证（get() 调用 kernel_client）
**状态**: DONE（合并至 R1）

**Acceptance**:
1. `set_kernel_client(client)` 注入 kernel_client 后，`get()` 调用 `kernel_client.get_session()`
2. kernel 返回 200 → 正常返回 binding
3. kernel 抛 `RuntimeError`（含 404/失效） → 删除记录并返回 None
4. `kernel_client=None` 时跳过验证（向后兼容）
5. 验证失败不抛异常（静默删除 + 返回 None）

**Tests Plan**:
- unit: mock kernel_client，测试验证成功/404失效/无client 三路径
- contract: 不需要
- integration: 不需要（kernel mock 已覆盖）
- e2e: 不需要

**Expected Tests**: 追加到 `tests/unit/personal_assistant/test_persistent_session_binding_store.py`

**DoD**: test_command 全绿 + C1/C2/C3

---

### R3 — main.py 切换到 PersistentSessionBindingStore
**状态**: DONE

**Acceptance**:
1. `build_runtime()` 使用 `PersistentSessionBindingStore(db_path=...)`
2. `db_path` 指向 `runtime_dir / "session_bindings.sqlite3"`
3. `kernel_client` 初始化后注入 `session_store.set_kernel_client(kernel_client)`
4. `main.py` import 更新：`PersistentSessionBindingStore` 替代 `SessionBindingStore`
5. 现有 `build_runtime` 相关单测仍全绿

**Tests Plan**:
- unit: 检查 `build_runtime` 使用新类（通过 mock 或 spy）
- contract: 不需要
- integration: 不需要
- e2e: 不需要

**Expected Tests**: 追加到 `tests/unit/personal_assistant/test_main.py`

**DoD**: test_command 全绿 + C1/C2/C3

# TASKS: M239 relay dedup 持久化

## Goal
WebRelayAdapter 的 idempotency_key dedup 当前用 in-memory deque，gateway 重启后清空，
IM 服务重投同一 relay 导致 agent 重复处理消息。需将已处理的 idempotency_key 持久化到 SQLite，
key 写入时附 TTL（7 天），启动时从 DB 加载到内存 deque。

## Roadpoints

---

### R1: RelayDeduplicationStore — SQLite 持久化层（含 TTL）
**Status: DONE**

**Acceptance:**
1. `RelayDeduplicationStore` 可将 idempotency_key 写入 SQLite，并附 expires_at（7 天后）
2. `contains(key)` 检查内存 deque 中是否有该 key（不查 DB，DB 只用于持久化）
3. `load_from_db()` 从 DB 加载未过期 key 到内存 deque（过期 key 自动跳过）
4. `purge_expired()` 删除 DB 中已过期的行（不无限增长）
5. 进程内存 deque 最多保留 `_SEEN_KEYS_MAX` 条（FIFO 滚动）

**Tests Plan:**
- unit: 全覆盖（写入/查询/加载/TTL 过期/purge），用 `tmp_path` SQLite
- contract: 无（无外部协议边界）
- integration: 无（DB 层已被 unit 覆盖）
- e2e: 无（在 R3 的集成中通过 WebRelayAdapter 测试）

**Expected Tests:**
- `tests/unit/personal_assistant/test_web_relay_adapter.py`
  - `test_relay_dedup_store_contains_after_add`
  - `test_relay_dedup_store_load_from_db_populates_deque`
  - `test_relay_dedup_store_expired_keys_not_loaded`
  - `test_relay_dedup_store_purge_removes_expired_rows`
  - `test_relay_dedup_store_deque_rolls_over_at_max`

**DoD:** test_command 全绿 + C1/C2/C3 齐全 + PROGRESS 更新

---

### R2: WebRelayAdapter 集成 RelayDeduplicationStore
**Status: DONE**

**Acceptance:**
1. `WebRelayAdapter.__init__` 接受可选 `dedup_store: RelayDeduplicationStore | None`
2. 若提供 store，startup 时调用 `store.load_from_db()` 恢复内存 deque
3. `accept_relay` 使用 store（若有）做 contains + add，否则 fallback 到原 in-memory deque
4. 重复 key 不触发 callback（同原行为）
5. 现有测试（无 store 参数）不回归

**Tests Plan:**
- unit: WebRelayAdapter + store，验证启动加载 + 去重行为
- contract: 无
- integration: 无
- e2e: 无

**Expected Tests:**
- `tests/unit/personal_assistant/test_web_relay_adapter.py`
  - `test_web_relay_adapter_uses_dedup_store_on_accept`
  - `test_web_relay_adapter_loads_store_on_init`
  - `test_web_relay_adapter_dedup_store_none_uses_in_memory`

**DoD:** test_command 全绿 + C1/C2/C3 齐全 + PROGRESS 更新

---

### R3: main.py wiring — db_path 注入
**Status: DONE**

**Acceptance:**
1. `_build_channel_registry` 接受 `dedup_db_path: Path | None = None` 参数
2. `build_runtime` 传入默认路径 `~/.nano-assistant/relay_dedup.sqlite3`（与 group_context_buffer 同目录）
3. 原有 `_build_channel_registry(config.channels)` 调用升级为带 db_path 的版本
4. 测试中 `tmp_path` 可覆盖 db_path 以隔离测试环境
5. `self._local_config.source_path` 相关路径不被硬编码影响（prevention_rule 已有此约束）

**Tests Plan:**
- unit: `_build_channel_registry` + WebRelayAdapter 使用 db_path
- integration: `build_runtime` 构造后 relay_adapter 带 store

**Expected Tests:**
- `tests/unit/personal_assistant/test_main.py`（已有文件，追加测试）
  - `test_build_channel_registry_passes_dedup_db_path`

**DoD:** test_command 全绿 + C1/C2/C3 齐全 + PROGRESS 更新

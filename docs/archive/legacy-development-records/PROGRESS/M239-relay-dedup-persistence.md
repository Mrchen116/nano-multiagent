# PROGRESS: M239 relay dedup 持久化

## Overview
WebRelayAdapter idempotency_key 去重从 in-memory deque 改为 SQLite 持久化，
防止 gateway 重启后 IM 重投同一 relay 导致 agent 重复处理。

---

### R1 RelayDeduplicationStore — SQLite 持久化层（含 TTL）
- Context: 需让 web relay 的去重键跨 gateway 重启保留，同时保持 `_SEEN_KEYS_MAX` 有界，DB 中旧键可过期清理。
- Decision: 在 `web_relay_adapter.py` 内新增 `RelayDeduplicationStore`，用 SQLite 表 `relay_deduplication_keys` 存 `idempotency_key/expires_at/seen_at`；`load_from_db()` 只恢复未过期 key 到内存 deque，`purge_expired()` 负责清库。
- Rationale: 直接复用 GroupContextStore 的 sqlite+lock 模式，避免引入新模块；运行期判重仍走内存 deque，DB 只承担重启恢复与 TTL 清理。
- Evidence:
  - Tests: `python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M239/tests/unit/personal_assistant/test_m102_gateway_im_connection.py -q` -> `14 passed`
  - Entry: 新增 store 单测覆盖 add/load/expired/purge/max rollover。
- Rollback: 回退到 plan commit
- Commits: C1=f20a4fd, C2=eb6f97f, C3=pending
- Next: R2

---

### R2 WebRelayAdapter 集成 RelayDeduplicationStore
- Context: Adapter 既要支持持久化 store 恢复后的重启防重，也不能破坏现有无 store 配置的 in-memory 行为。
- Decision: `WebRelayAdapter.__init__` 接受可选 `dedup_store`；`start()` 时执行 `load_from_db()` 并让 adapter 复用 store 的内存 deque；`accept_relay()` 改为通过 `_contains_seen_key/_remember_seen_key` 走 store 或 fallback 内存路径。
- Rationale: 把行为分流收敛在 adapter 内部，最小化上层接线改动，同时保证未启用 sqlite 时保持旧接口与旧语义。
- Evidence:
  - Tests: `python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M239/tests/unit/personal_assistant/test_m102_gateway_im_connection.py -q` -> `17 passed`
  - Entry: 新增 adapter 单测覆盖 store 注入、启动恢复、无 store fallback 三条路径。
- Rollback: R1 C3
- Commits: C1=9b3cf09, C2=7078efb, C3=pending
- Next: R3

---

### R3 main.py wiring
- Context: Runtime 需默认给 web relay 注入持久化 DB 路径，且路径必须跟随当前 `config.source_path` 所在目录，不能硬编码到 `~/.nano-assistant`。
- Decision: `build_runtime()` 统一用 `config.source_path.parent` 作为 runtime_dir，把 `relay_dedup.sqlite3` 传入 `_build_channel_registry(..., dedup_db_path=...)`；`_build_channel_registry` 在 `web_relay` 分支创建 `RelayDeduplicationStore`；`group_context_buffer.sqlite3` 也同步改到 runtime_dir。
- Rationale: 以配置文件目录为单一真源，满足 prevention rule 并让测试/多 worktree 环境都能天然隔离 sqlite 状态。
- Evidence:
  - Tests: `python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M239/tests/unit/personal_assistant/test_main.py -q && python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M239/tests/unit/personal_assistant/test_m102_gateway_im_connection.py -q` -> `36 passed` + `17 passed`
  - Entry: `test_build_channel_registry_passes_dedup_db_path` 与 `test_build_runtime_wires_web_relay_dedup_db_under_config_dir` 断言 adapter/store 接线到 `config.source_path.parent`。
- Rollback: R2 C3
- Commits: C1=19179b6, C2=2d6452e, C3=pending
- Next: DONE

# Progress: M12 gateway-config-reconcile

## 启动确认

已读 design.md 决策 F、接口数据流「配置真源与对账」段、`main.py` `_IMConfigSyncClient`、
`im_connection.py` `connect_once/run_forever`，以及现有测试结构。

**范围**：`src/personal_assistant/main.py`（reconcile_all_agents + 回调接线）、
`src/personal_assistant/ws/im_connection.py`（on_connected 参数）、
`tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py`（新建）

**基线失败**（与本 M12 无关）：`tests/im_service/integration/test_agent_config_api.py::test_get_agent_config_prefers_live_gateway_snapshot`
和 `test_agent_create_flow.py::test_create_agent_lists_details_and_uses_new_node_binding_for_relay`
失败原因是 `/tmp` vs `/private/tmp` macOS symlink 解析差异，基线已存在。

---

### R1 — 红测：reconcile-on-connect 场景

- Context: 确立失败测试证明当前无对账能力；`reconcile_all_agents` 和 `on_connected` 均不存在
- Decision: 新建 `test_gateway_reconcile_on_connect.py`，覆盖 7 个场景
- Rationale: 测试驱动，确保实现针对性对着 design 退出标准
- Evidence:
  - Tests: C1 commit 时 7/7 FAIL（AttributeError: 无 reconcile_all_agents / on_connected）
  - Entry: N/A（纯单测）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C1 commit
- Commits: C1=a6e0a60（plan）, 红测=7ed15d9（test C1）
- Next: R2 实现

### R2 — 实现：reconcile_all_agents + on_connected 回调接线

- Context:
  1. `_IMConfigSyncClient.reconcile_all_agents(memory_versions=None)` — 遍历 local_config.agents，
     对每个调 `_fetch_agent_config(source=mirror)`，若 IM profile_version >= memory_version 则
     `register_agent` 覆盖内存
  2. `IMConnectionManager.__init__` 增加 `on_connected: Callable[[], Awaitable[None]] | None` 参数
  3. `connect_once` 在 node.register 发出并 heartbeat loop 启动后触发 `on_connected`（on_connected 错误
     只记 event log，不中断 WS 连接）
  4. `_build_im_connection_manager` 接受 `on_connected` 参数并透传
  5. `main.py` 中构建 `_reconcile_on_connect` async 回调：从 ConfigSyncClient 取 memory_versions，
     用 `asyncio.to_thread` 调同步的 `reconcile_all_agents`

- Decision:
  - `reconcile_all_agents` 是同步方法（复用现有同步 httpx client）
  - profile_version 取大：IM < 内存版本时跳过（不回退），IM >= 内存时覆盖
  - HTTP 失败时 warning log + skip，不 raise（WS 连接不受影响）
  - `on_connected` 在 `connect_once` 内触发（= WS bind 完成后），`run_forever` 每次重连都调 `connect_once`
    所以重连时自动触发

- Rationale: 对账拉到旧版即保留内存（不降版），避免与增量推送竞态破坏最新状态；
  错误不传播避免对账失败导致 WS 断连（gateway 本地自主性要求）

- Evidence:
  - Tests: 7 passed in 0.21s（修正 httpx mock client 需传 base_url 后全绿）
  - Full suite: 2575 passed, 2 failed（同基线，macOS /tmp 路径问题，无新失败）
  - Entry: N/A（纯后端逻辑，无 HTTP endpoint 变化）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A

- Rollback: R1 tip（7ed15d9）
- Commits: C2=b3a2498（feat + test fixes）
- Next: R3 文档

### R3 — 文档：spec delta + 全树验证

- Context: gateway spec.md 中决策 F 的 ADDED Requirements 段（第 117 行起）已由 M11 worker 写好，
  本 M12 实现与其描述一致，无需修改
- Decision: 不改 spec.md（已正确描述预期行为），只更新 tasks.md + progress.md 收尾
- Evidence:
  - Full suite: 2575 passed, 2 failed（同基线）
  - spec.md: `docs/changes/feat-394-heartbeat-cron-redesign/specs/gateway/spec.md` 第 117-134 行
    已有决策 F 的完整 Requirement + 2 个 Scenario（关闭 heartbeat 无需重启即停 + 重连后配置收敛）
- Rollback: C2 tip
- Commits: C3=pending
- Next: 集成到 unit 分支

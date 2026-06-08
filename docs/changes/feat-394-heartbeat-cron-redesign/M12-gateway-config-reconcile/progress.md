# Progress: M12 gateway-config-reconcile

## 启动确认

已读 design.md 决策 F、接口数据流「配置真源与对账」段、main.py _IMConfigSyncClient、
im_connection.py connect_once/run_forever，以及现有测试结构。

**范围**：`src/personal_assistant/main.py`（WS bind/重连后全量对账触发）、
`tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py`（新建）

**关键理解**：
- `connect_once()` 在 `run_forever()` 的每次重连循环里被调用 → 这是正确的对账触发点
- `_IMConfigSyncClient.sync_agent()` 内部已实现 `_fetch_agent_config(source=mirror) + register_agent + profile_version 验证`
- profile_version 验证方向：sync_agent 拒绝 < 目标版本；reconcile 场景的"取大"逻辑是
  对账拉到旧版就保留内存（让增量推送的新版胜）——需设计 reconcile 专用路径（不传 profile_version 参数，
  或传 0 令其接受任意版本，再在覆盖时比大小）

**实现选择**：
- 在 `_IMConfigSyncClient` 上新增 `reconcile_all_agents()` async 方法，遍历本 node agents，
  对每个 agent 调 `_fetch_agent_config`，当 IM profile_version >= 内存版本时 `register_agent` 覆盖
- 在 `IMConnectionManager.connect_once()` 调完 `node.register` 后，异步触发对账（不阻塞 WS 握手）
- 对账回调作为可选参数传给 `IMConnectionManager.__init__`

---

### R1 — 红测：reconcile-on-connect 场景

- Context: 需在实现前确立失败测试证明当前无对账能力
- Decision: 新建 `test_gateway_reconcile_on_connect.py`，覆盖 5 个场景
- Rationale: 测试驱动，确保实现针对性对着 design 退出标准
- Evidence:
  - Tests: C1 commit 时全部 FAIL（预期）→ C2 后全部 PASS
  - Entry: N/A（纯单测）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C1 hash
- Commits: C1=pending, C2=pending, C3=pending
- Next: R2 实现

### R2 — 实现：_reconcile_all_agents + 连接生命周期接线

- Context: 在 connect_once 后触发全量对账；profile_version 取大
- Decision: 见 progress.md 开头「实现选择」
- Rationale: 对账拉到旧版即保留内存（不降版），避免与增量推送竞态破坏最新状态
- Evidence: 待填
- Rollback: R1 tip
- Commits: C2=pending, C3=pending
- Next: R3 文档 + 全树

### R3 — 文档：spec delta + 全树验证

- Context: 补 gateway spec.md delta，跑全测试树
- Decision: 在 spec.md ADDED 段落追加 reconcile-on-connect 行为契约
- Evidence: 待填
- Rollback: R2 tip
- Commits: C3=pending
- Next: DONE

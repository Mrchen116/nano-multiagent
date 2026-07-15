# refactor-463-M1: live agent 与 Gateway session ownership — Tasks

> 对齐: ../design.md（2026-07-15 Approved 基线）

## 目标

用 `LiveAgentCatalog` 与 `GatewaySessionBinder` 分别收回动态 Agent 配置和 Gateway session binding 的唯一状态所有权；所有生产消费者只依赖公开业务接口，在保持路由、续接、动态配置、cron/heartbeat、internal dispatch 与 fork 行为不变的前提下删除 pipeline 私有容器和 repository 旁路。

## 退出标准

- [ ] Catalog 通过 copy-on-write 发布 frozen `LiveAgentSnapshot(config, revision)`，revision 单调且读者只观察完整旧/新快照。
- [ ] Binder 的 create/reuse/invalidate-generation/reverse/canonical/conversation-bind 均通过公开 interface 测试；SQLite schema、session key、reply-context 格式不变。
- [ ] 旧 binding reuse、跨 `create_session()` await、internal-dispatch IM ack 与 session-fork await 四个竞争窗均受 revision/generation guard；stale create/conversation bind 不落 repository，fork stale 返回失败走既有 IM rollback。
- [ ] `InternalDispatchHandler` 不持有启动 workspace snapshot；CronRunner、heartbeat、runtime delivery、fork、config sync 不直接访问 binding repository。
- [ ] `main.py`、scheduler、config-sync 无 `pipeline._*`、裸 live agent dict 或旧 `_IMConfigSyncClient` / `_IMShadowConversationSyncClient` 生产定义/兼容 re-export。
- [ ] 相关新增/拆分测试文件不超过 400 行；最窄测试与 `pytest -m "not e2e"` 全绿。
- [ ] 隔离真栈 durable evidence 明确证明下一轮动态配置、Gateway 重启续接、cron canonical direct、`send_message` 正确连续历史及未知 Agent 拒绝。

## 测试策略

- 被测行为（来自退出标准）：catalog 原子快照/revision；binder reuse/create/invalidate/reverse/canonical/conversation bind 与四类 stale-write race；internal-dispatch/fork stale 结果；scheduler/runtime delivery/config-sync/build-runtime 公开接线；真栈动态配置、重启续接、cron canonical direct、`send_message` 历史、未知 Agent 拒绝。
- 已有测试在：`tests/unit/personal_assistant/test_inbound_pipeline_agent_sessions.py`、`test_persistent_session_binding_store.py`、`test_gateway_im_config_sync.py`、`test_internal_dispatch_endpoint.py`、`test_session_fork_handler.py`、`test_heartbeat_session_binding.py`、`test_cron_runner_awareness.py`、`test_gateway_build_runtime.py`（按公开行为迁移/拆分）；新建 `test_agent_catalog.py` 与 `test_gateway_session_binder.py`，理由：两个新 deep module 尚无合适行为测试归属；新建 architecture contract，理由：防止生产旁路回流。
- 落层/目录/marker：纯逻辑与模块协作落 `tests/unit/personal_assistant/`，marker：无；源码依赖闸落 `tests/contract/`，marker：无；真进程验收落 unit 目录 durable evidence，由现有 `scripts/e2e-up.sh` / `scripts/e2e-critical.sh` 驱动，不新增一次性 `test_*.py`。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`M1-live-agent-session-ownership/evidence/` 下的隔离真栈命令输出、运行日志摘录、IM API/SQLite 对账与验收报告；临时驱动脚本收尾删除。
- 用户路径分类：N/A（无前端 UI 变更）。
- UI 状态矩阵：N/A。
- Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 收回 live Agent snapshot 所有权

- 状态: DONE
- 步骤: 先提交 catalog 公开行为红测，再实现 frozen snapshot、copy-on-write publish、单调 revision 与完整旧/新读取；把 pipeline 的路由/模型/metadata 读取改接 catalog，但暂不迁 session repository owner。
- 验证: `pytest tests/unit/personal_assistant/test_agent_catalog.py tests/unit/personal_assistant/test_inbound_pipeline_agent_sessions.py`

### R2 — 收回 Gateway session binding 所有权

- 状态: DOING
- 步骤: 先提交 binder 公开行为与 create-await race 红测，再实现 resolve/reuse/workspace validation/revision-generation guard/reverse/canonical/typed conversation bind；pipeline 改接 binder，repository 仅作为内部 adapter。
- 验证: `pytest tests/unit/personal_assistant/test_gateway_session_binder.py tests/unit/personal_assistant/test_persistent_session_binding_store.py tests/unit/personal_assistant/test_inbound_pipeline_agent_sessions.py`

### R3 — 切换全部生产消费者并证明真实入口

- 状态: TODO
- 步骤: 先提交 internal-dispatch ack/fork-await race、scheduler/runtime delivery/build-runtime 与 architecture guard 红测；迁出 `IMAgentConfigSync`/`ShadowConversationSync`，切换 internal dispatch、fork、heartbeat/cron、runtime delivery、kernel shim 和 composition root；拆分过大相关测试；最后跑隔离真栈并落 durable evidence。
- 验证: 相关最窄单测 + contract；`ruff check src tests`；`pytest -m "not e2e" -n 4 --dist worksteal`；隔离真栈用户旅程与 SQLite/API 对账。

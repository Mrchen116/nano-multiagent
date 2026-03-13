# M148 修复 live acceptance 暴露的 IM 接口与动态同步残留问题

## 前置确认
- 已阅读 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`。
- 已阅读强制材料：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M147/PROGRESS/M147-live-agent-dynamic-sync.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M147/TASKS/M147-live-agent-dynamic-sync.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime/gateway.log`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime/im.log`
- 注释/文档承诺：新增 public API 使用 Google 风格 docstring；注释只解释意图、约束、边界。
- 不修改 `data/dev-tasks.json`；仅在 `/Users/czj/Repos/nano-multiagent/.worktrees/M148`、分支 `milestone/M148` 内完成本 milestone。

## 当前处境
- Milestone: `M148 / 修复 live acceptance 暴露的 IM 接口与动态同步残留问题`
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M148`
- branch: `milestone/M148`
- test_command: `PYTHONPATH=src pytest -q tests/im_service/unit/test_db_init.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_m102_gateway_im_connection.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py`
- allowed_scope: `src/IM/**`、`src/personal_assistant/**`、`tests/im_service/**`、`tests/unit/personal_assistant/**`、`TASKS/**`、`PROGRESS/**`、`ACCEPTANCE/**`
- forbidden_scope: `data/dev-tasks.json`、当前 live acceptance 栈运行态配置、无关 node/kernel/frontend 大改
- prevention_rules:
  - 只围绕已确认的真实缺口做 TDD，不重做无关探索。
  - 每个 Roadpoint 必须先补失败测试，再做最小修复，再补文档证据。
  - 不依赖“重启 Gateway/改 node-config”来通过回归；修复必须让在线路径自恢复。
  - 若无法完成 live browser/merge/main，必须在文档中明确卡点与剩余风险。

## 基线
- 现有 M147 定向门禁：`PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py`
- 当前结果：`39 passed`
- 已知真实缺口：
  - IM 真实并发读接口会间歇性触发 `sqlite3.InterfaceError: bad parameter or other API misuse`。
  - `config.sync` 在真实时序下可能遇到短暂 404/500 或只完成 agent registry 更新，却未让既有会话切到新 prompt，导致在线 Gateway 仍无法无重启吃到更新。

## Roadpoints

### R1 IM 并发读接口 sqlite 稳定性收口
- Status: TODO
- Acceptance:
  - 共享 SQLite 连接在跨线程参数化查询下不再触发 `sqlite3.InterfaceError`
  - `conversations/:id/messages`、`conversations/:id/events`、`agents/:id/config` 所依赖的底层连接配置可覆盖真实并发路径
  - 至少有一个最小 real-ish regression test 锁定该问题，而不是只改实现
- Tests Plan:
  - unit: 需要，直接锁定 `connect(...)` 在共享连接并发查询下不抖动
  - contract: 不新增；接口结构未变化
  - integration: 复用现有 IM/gateway 定向测试，确认改动不破坏主链路
  - e2e: 本 subagent 不重跑真实浏览器，仅在文档记录需由主 agent 复验的 live acceptance 项
- Expected Tests:
  - `tests/im_service/unit/test_db_init.py::test_connect_supports_cross_thread_parameterized_reads_without_interface_errors`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `tests/im_service/integration/test_agent_create_flow.py`
- DoD:
  - 红测先失败，再由最小修复转绿
  - `test_command` 全绿
  - 完成 C1/C2/C3

### R2 动态同步残留：瞬时配置抖动重试 + 已有会话切换到新 profile
- Status: TODO
- Acceptance:
  - `config.sync` 遇到短暂 404/5xx 或 profile 未达目标版本时，Gateway 会在同一次同步流程内重试拉取，而不是丢失更新
  - 已在线 agent 收到新 profile 后，不需要重启即可在下一条消息上建立新 kernel session，吃到新 prompt/version
  - late-bound/new agent 与 updated agent 两条路径都保留已有能力
- Tests Plan:
  - unit: 需要，锁定 `_IMConfigSyncClient` 瞬时失败重试与 `InboundPipeline.register_agent(...)` 刷新既有 session 绑定
  - contract: 不新增；协议字段未变化
  - integration: 复用 M103 / create flow 定向测试，确认动态同步主链路未回退
  - e2e: 本 subagent 不重跑真实浏览器，仅输出主 agent 复验入口与预期
- Expected Tests:
  - `tests/unit/personal_assistant/test_main.py::test_im_config_sync_client_retries_until_live_agent_config_reaches_target_version`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py::test_register_agent_resets_existing_sessions_for_profile_refresh`
  - `tests/unit/personal_assistant/test_m102_gateway_im_connection.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `tests/im_service/integration/test_agent_create_flow.py`
- DoD:
  - 红测先失败，再由最小修复转绿
  - `test_command` 全绿
  - 完成 C1/C2/C3

### R3 证据文档与 live acceptance 交接
- Status: TODO
- Acceptance:
  - `PROGRESS` 记录每个 Roadpoint 的 Context / Decision / Evidence / Rollback / Commits
  - 产出 `ACCEPTANCE/M148-acceptance.md`，明确本次代码级证据、需主 agent 执行的 live browser 复验步骤、以及 merge/main 状态
  - 若本 subagent 未完成 live browser 验证、merge main、worktree cleanup，必须显式标注未完成
- Tests Plan:
  - unit/contract/integration: 复用前两项证据，不新增行为面
  - e2e: 文档化交接，不伪造已完成的真实浏览器结果
- Expected Tests:
  - `test_command`
- DoD:
  - 文档诚实反映已完成与未完成项
  - 完成 C3

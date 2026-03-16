# M221 查明并修复 Agent workspace 显示与运行目录错乱

## Milestone Context
- Milestone: M221 / 查明并修复 Agent workspace 显示与运行目录错乱
- Execution: parallel
- Worktree: `true`
- Worktree dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M221`
- Branch: `milestone/M221`
- Test gate: `pytest tests/contract/test_sessions_contract.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py -q`
- Allowed scope:
  - `src/IM/**`
  - `src/personal_assistant/**`
  - `src/agent/**`
  - `tests/**`
  - `TASKS/**`
  - `PROGRESS/**`
- Forbidden scope:
  - `docs/**`
  - `ACCEPTANCE/**`
  - `data/dev-tasks.json`
- Prevention notes:
  - workspace 语义必须以 Workspace Path Setting 为准。
  - 不要把配置路径伪装成 runtime 实测 cwd。
  - 必须补真实运行态验证，而不是只改设置页文案。
  - 代码仓根目录与 agent workspace 不是同一概念；需要沿创建/API/runtime/sync 链路拆开核对。
- Baseline:
  - 初始门禁存在 `tests/e2e/test_personal_assistant_main_e2e.py::test_main_stop_command_reports_still_healthy_when_another_listener_remains` 健康检查超时；收尾时已一并修复启动/抢占时序并确认本 milestone 门禁全绿。

## Roadpoints

### R1. 固化 workspace 设置未进入 kernel session / runtime cwd 的红测
- Status: DONE
- Acceptance:
  - 红测证明 IM agent 配置中的 `workspace_root` 已经通过 API/配置返回，但 kernel session 创建时没有把它作为真实运行 workspace 使用。
  - 红测覆盖 agent 创建/更新后的配置接口与 gateway sync 链路，避免只测单点函数。
  - 至少一条测试直接观察真实运行态 `pwd`/working directory，而不是只断言响应 JSON。
  - 红测能定位当前根因是会话创建契约或 runtime 上下文丢失，而不是前端展示问题。
- Tests Plan:
  - unit: 否；本缺陷是跨 IM API、gateway、kernel runtime 的接线问题，优先从集成/e2e 锁定。
  - contract: 是；补强 session/create 或 agent config 对 workspace 字段的边界契约。
  - integration: 是；覆盖 create/update/config sync 后的 workspace 字段传播。
  - e2e: 是；真实 kernel 运行并返回实际 `pwd` 作为红测证据。
- Expected Tests:
  - `tests/im_service/integration/test_agent_create_flow.py::*workspace*`
  - `tests/im_service/integration/test_agent_config_api.py::*workspace*`
  - `tests/e2e/test_personal_assistant_main_e2e.py::*workspace*pwd*`
- DoD:
  - 红测稳定失败且直接指向 workspace 接线缺口。
  - C1/C2/C3 齐全。
  - `test_command` 重跑并记录结果。
  - `PROGRESS` 写清根因证据、回滚点与边界。

### R2. 修复会话创建、runtime 上下文与 config resolver 的 workspace 真源
- Status: DONE
- Acceptance:
  - kernel session 明确持久化 `workspace_root`，并在后续 turn 中以该路径作为实际 cwd/工作目录。
  - gateway 从 IM config API 拉到的 workspace 在 sync 后会进入新会话；编辑 agent 配置后新会话也使用新 workspace。
  - 设置页/配置接口返回的 workspace 与 runtime 实际 `pwd` 一致。
  - 修复不把代码仓 repo root 与 workspace root 混用；需要保留代码加载能力，同时让运行目录按 workspace 生效。
- Tests Plan:
  - unit: 视需要最小补充 runtime/session helper；若无必要不单开。
  - contract: 是；收紧 `/v1/sessions` 或相关持久化结构的 workspace 契约。
  - integration: 是；覆盖 create/update/list/get/config sync/new conversation。
  - e2e: 是；通过真实 HTTP kernel turn 断言 `pwd` 与配置 workspace 一致。
- Expected Tests:
  - `tests/im_service/integration/test_agent_create_flow.py`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/e2e/test_personal_assistant_main_e2e.py`
- DoD:
  - 代码、配置链路与测试全部对齐 workspace 真源语义。
  - `test_command` 全绿，或仅剩基线既有失败并有明确对比说明。
  - `PROGRESS` 记录为何拆分 code root / workspace root（若采用）。

### R3. 用真实创建与真实运行态完成回归验证并收口文档
- Status: DONE

### R4. 修复 task/subagent 链路把 child session cwd 回退到 repo root
- Status: DONE
- Acceptance:
  - 直接复现“父 session 已绑定 workspace，但 task 工具创建的 child session 仍落到 repo root”的真实执行缺陷。
  - 证明根因不是 prompt 文案，而是 task/subagent 新 session 创建时未继承 workspace_root，导致 runtime fallback 到 repo root。
  - 修复后 parent session 触发 task/subagent，child session 的真实 `pwd` 与父 workspace 一致。
  - 给出直接验证，覆盖用户所说的真实执行层而不是 session contract 层。
- Tests Plan:
  - unit: 是；补 task tool child session metadata 继承边界。
  - contract: 否；本次是内部 tool/runtime 接线，不新增 HTTP 契约。
  - integration: 是；覆盖 task tool 通过 registry/runtime 创建子 session 的链路。
  - e2e: 是；真实父 session -> task tool -> child bash pwd，断言不再落到 repo root。
- Expected Tests:
  - `tests/e2e/test_task_tool_blocking_e2e.py::test_task_subagent_inherits_parent_workspace_root_for_real_pwd`
  - `tests/integration/test_task_blocking_integration.py`
  - `tests/integration/test_task_non_blocking_integration.py`
  - `tests/unit/test_task_tool_blocking.py`
  - `tests/unit/test_task_tool_non_blocking.py`
- DoD:
  - 红测先证明 child session cwd 仍错误回退到 repo root。
  - C1/C2/C3 齐全。
  - `test_command` 全绿。
  - `PROGRESS` 写清 task/subagent 根因、证据与回滚点。
- Acceptance:
  - 给定 `workspace=/Users/czj/nano-assistant/workspace/fuck`，agent 创建/读取/编辑后的响应与真实运行态 `pwd` 一致。
  - 至少一条真实入口测试覆盖“新建 agent -> gateway/kernel 创建会话 -> 运行时读到 pwd”。
  - 至少一条真实入口测试覆盖“编辑 agent workspace -> 新会话使用新目录”。
  - TASKS/PROGRESS 更新完整，包含证据、提交哈希、回滚点与后续说明。
- Tests Plan:
  - unit: 否；R3 聚焦真实入口复验。
  - contract: 否；R2 已锁定契约。
  - integration: 是；必要时补充 config sync/new session 验证。
  - e2e: 是；用真实 kernel HTTP/runtime 测 `pwd`。
- Expected Tests:
  - `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py -q`
- DoD:
  - 真实运行态验证通过。
  - C1/C2/C3 齐全。
  - `PROGRESS` 记录 solution summary / evidence / rollback。

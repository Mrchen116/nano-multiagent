# M221 查明并修复 Agent workspace 显示与运行目录错乱

## Notes
- 已阅读 `LOGBOOK.md`：真实入口行为若与源码矛盾，要先确认是否存在接线层丢字段/旧默认值伪装成“有效配置”；本次重点是会话创建与 runtime cwd 真值，而不是 UI 文案。
- 已阅读 `COMMENTING_GUIDE.md`：后续 public API/docstring 与注释只写契约、边界和为什么，不复述实现。
- 初始门禁存在 `tests/e2e/test_personal_assistant_main_e2e.py::test_main_stop_command_reports_still_healthy_when_another_listener_remains` 健康检查超时；本 milestone 收尾时已修复该时序问题并确认门禁全绿。

## Roadpoint Records

### R1 固化 workspace 设置未进入 kernel session / runtime cwd 的红测
- Context:
  - IM 配置接口已能返回 `workspace_root`，但用户观察到真实 runtime `pwd` 仍落在仓库根目录，需要证明问题发生在 kernel session/runtime 接线而不是设置页展示。
- Decision:
  - 先把 agent create/config 场景统一改成用户指定路径 `/Users/czj/nano-assistant/workspace/fuck`，再在 kernel HTTP e2e 中增加真实 `bash pwd` 回传断言。
- Rationale:
  - 只有让 create/update/API/e2e 同时指向同一真实路径，才能锁定“字段已配置但没进入 session cwd”的缺口。
- Evidence:
  - Tests: `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py -k "workspace or pwd" -q`
  - Entry: `/v1/sessions` 接受 `workspace_root` 前，`pwd` 红测返回 worktree/repo 根而非目标 workspace。
- Rollback: `a8350d2`
- Commits: C1=`3628106`, C2=`d03be6a`, C3=`91534e1`
- Next: 收口文档并准备 rebase/merge。

### R2 修复会话创建、runtime 上下文与 config resolver 的 workspace 真源
- Context:
  - gateway 已把 `workspace_root` 传给 kernel `/v1/sessions`，但 HTTP create route 没接字段，runtime 也一直把 repo root 当作 prompt cwd 与 tool cwd。
- Decision:
  - 在 `/v1/sessions` 规范化并持久化 `workspace_root`；`AgentRuntime` 从 session metadata 解析 per-session cwd；`AgentLoop` 与 `ToolRegistry` 接受覆盖后的 cwd；同时将 shell 启动从 `bash -lc` 改为 `bash -c`，避免用户 shell profile 噪音污染 `pwd` 结果。
- Rationale:
  - repo root 仍保留为代码/安全边界，workspace 只作为会话运行目录，既不破坏代码加载，也让 runtime 真正按 agent workspace 执行。
- Evidence:
  - Tests: `pytest tests/contract/test_sessions_contract.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py -q`
  - Entry: 新建 session 后 `pwd` 返回 session metadata 中的 `workspace_root`，而非 `/Users/czj/Repos/nano-multiagent`。
- Rollback: `3628106`
- Commits: C1=`3628106`, C2=`d03be6a`, C3=`91534e1`
- Next: 记录文档提交并集成回 `main`。

### R3 用真实创建与真实运行态完成回归验证并收口文档
- Context:
  - 需要证明给定 `/Users/czj/nano-assistant/workspace/fuck` 时，创建、读取、编辑与真实 runtime `pwd` 一致，同时不能留下原 baseline 的 stop/health 波动。
- Decision:
  - 增加 session create contract 覆盖 workspace 持久化/非法相对路径；修正 stop e2e 中“抢占监听器”启动时序，确保停止主进程后再起替代 listener；最终以完整 milestone gate 复验。
- Rationale:
  - 这样既验证 workspace 真值，也把原先影响收口判断的 flaky 基线一起消掉，避免 milestone 完成后仍被同一门禁阻塞。
- Evidence:
  - Tests: `pytest tests/contract/test_sessions_contract.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py -q`
  - Entry: 全量门禁 `28 passed`，其中 workspace contract、create/config API 与真实 `bash pwd` 回归均通过。
- Rollback: `3628106`
- Commits: C1=`3628106`, C2=`d03be6a`, C3=`91534e1`
- Next: 补查真实 task/subagent 链路是否仍绕过 workspace 继承。

### R4 修复 task/subagent 链路把 child session cwd 回退到 repo root
- Context:
  - 用户复验仍看到 `pwd=/Users/czj/Repos/nano-multiagent`，说明除主 session 外仍有实际执行路径没继承 workspace。复盘后定位到 `task` 工具直接 `runtime.create_session()`，未带父 session 的 `workspace_root`，child session 因此 fallback 到 repo root。
- Decision:
  - 先加真实 e2e：父 session 绑定 workspace 后调用 `task`，让 subagent 再执行 `bash pwd`；随后让 `task` 创建 child session 时继承 `ctx.cwd -> metadata.workspace_root`，避免任何 subagent 新 session 再回退 repo root。
- Rationale:
  - 这条链路绕过了 gateway `/v1/sessions` create path，所以之前 session 级修复全部通过，但真正 task/subagent 执行层仍错；必须在 tool/runtime 创建子 session 的入口补齐继承。
- Evidence:
  - Tests: `pytest tests/e2e/test_task_tool_blocking_e2e.py -k "inherits_parent_workspace_root_for_real_pwd" -q`
  - Entry: 红测先看到 task 输出里同时出现 workspace-root 与错误的 repo-root 子 session pwd，修复后 child session metadata 与真实 `pwd` 都落在父 workspace。
- Rollback: `e7d3868`
- Commits: C1=`543dac9`, C2=`cefd9ac`, C3=`46e0f24`
- Next: 更新 TASKS/PROGRESS，记录 task/subagent 真正根因与直接验证，然后再次 merge main。

### R5 修复旧直聊 binding 复用缺少 workspace_root 的 legacy kernel session
- Context:
  - 按用户要求先查主仓运行态数据库与历史：`/Users/czj/Repos/nano-multiagent/data/im_service.sqlite3` 中 agent `fuck` 当前 `workspace_root` 存储为空，UI 会回退展示默认 managed workspace；而 `/Users/czj/Repos/nano-multiagent/.agent/sessions.sqlite3` 同时存在两类 kernel session：较早的直聊 session `sess_2f98426b641a4e89` / `sess_16fb1524e3e6b18a` metadata 只有 `agent_id/config_profile_version/system_prompt`，没有 `workspace_root`；较新的 session `sess_69b12d075f59de86` / `sess_94353ef80ddfa2b4` / `sess_ce0aea16c01f81fe` / `sess_0a991fcde08bedff` 已带 `workspace_root=/Users/czj/nano-assistant/workspace/fuck`。这说明主问题是旧直聊会话污染，不是“新 session 仍然默认 repo root”。
- Decision:
  - 给 kernel session detail/list 暴露 metadata；给 gateway 的 `KernelApiClient` 增加 `get_session()`；`InboundPipeline` 复用现有 direct binding 前先检查目标 kernel session metadata 是否含 `workspace_root`。若缺失，则把它视为修复前遗留的 legacy session，立即创建并绑定一个新的 workspace-aware session，再发送本轮消息。
- Rationale:
  - 用户看到的 repo-root `pwd` 来自旧直聊 binding 继续指向修复前创建的 kernel session。新 session 其实已经正确，只是产品语义里“同一 direct chat 继续复用同一 session”把旧错误冻结了。自动刷新缺字段的 legacy session，既保住了 direct chat 入口，又不要求用户手动删历史会话。
- Evidence:
  - Tests: `pytest tests/contract/test_sessions_contract.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py tests/unit/test_task_tool_blocking.py tests/unit/test_task_tool_non_blocking.py tests/unit/test_task_tool_with_resolver.py tests/integration/test_task_blocking_integration.py tests/integration/test_task_non_blocking_integration.py tests/integration/test_task_skills_integration.py tests/e2e/test_task_tool_blocking_e2e.py tests/e2e/test_task_tool_non_blocking_e2e.py tests/e2e/test_task_load_skills_e2e.py -q`
  - Entry: 运行态数据库里旧 `fuck` 直聊 session 缺少 `workspace_root`，而新 session 已带目标 workspace；新增 gateway 单测/集成测试证明旧 binding 会自动切到新 session，结合既有 kernel e2e 说明刷新后的 direct bash `pwd` 会落到 workspace 而不是 repo root。
- Rollback: `c24a033`
- Commits: C1=`b457f63`, C2=`c24a033`, C3=`PENDING`
- Next: 提交文档、rebase `origin/main` 并集成回 `main`。

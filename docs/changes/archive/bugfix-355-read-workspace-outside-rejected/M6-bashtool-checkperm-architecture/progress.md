# M6 Progress

## 开工报信

已读懂 M6，范围 = bash 专属逻辑（配置/策略/执行）从 ToolSafety 搬到 builtins/bash_policy.py + bash_runner.py；
BashTool.check_permissions 自持权限判定；auto_mode_gate step 6 删除；S3 allow-prefix 按 D9 裁剪。
基线 108 tests passed。开始实施。

### R1 — 新建 bash_policy.py + 配套测试

- Context: bash 专属策略逻辑和配置常量散落在 ToolSafety 中，需要整体搬到 builtins/bash_policy.py
- Decision: 新建 bash_policy.py，包含 BASH_ALLOWED_PREFIXES（D9 裁剪版）、BASH_BLOCKED_COMMANDS、BASH_BLOCKED_FRAGMENTS、CommandPolicyDecision dataclass、check_command_policy、enforce_command_policy、load_bash_policy_overrides、BashPolicyOverrides；helpers 从 safety.py 搬来，行为不变
- Rationale: 策略层独立文件，与执行层分离（D8）；D9 按 CC isReadOnly 语义裁剪 allow-prefix；向后兼容 .nano/policy.toml 的 [tool_safety.bash_policy] 和 [bash] 两种格式（锚点 R）
- Evidence:
  - Tests: 75 passed（test_bash_policy.py），包含 BASH_ALLOWED_PREFIXES 逐项验证、allowed/denied/review 三路 parametrize、git 只读子命令、python version flags、配置兼容测试
  - Entry: N/A（纯策略层，无外部入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — R5 会覆盖端到端集成测试
  - Visual/Interaction: N/A
- Rollback: C1 = d73a4c0d，C2 = bf91559b
- Commits: C1=d73a4c0d, C2=bf91559b, C3=e8073d33
- Next: R2 — 新建 bash_runner.py + BashTool 执行层迁移

### R2 — 新建 bash_runner.py + BashTool 执行层迁移

- Context: ToolSafety.run_command_stream 是 BashTool 唯一的前台同步执行路径，需要搬到 builtins/bash_runner.py；同时在 BashTool 上实现 check_permissions（调 bash_policy）
- Decision: 新建 BashRunner + BashRunnerConfig dataclass；BashTool._run_legacy_sync 改调 BashRunner.run_stream；BashTool.check_permissions 实现返回 allow/deny/passthrough；测试文件中 monkeypatch ctx.safety.run_command_stream 的 3 个 test 更新为 patch BashRunner.run_stream
- Rationale: D10 单点原则——policy 只在 check_permissions 一处做；run 路径不再做二次 policy 检查；BashRunner 从 ToolSafety 解耦，subprocess 机制独立维护
- Evidence:
  - Tests: 336 passed（包含 test_bash_runner.py 9 tests、test_bash_policy.py 75 tests、test_tools_builtins.py 64 tests、test_auto_mode_gate.py 全绿）
  - Entry: BashRunner.run_stream 实际执行 echo/false 命令验证
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — R5 覆盖端到端
  - Visual/Interaction: N/A
- Rollback: C1 = f0030374，C2 = 7f15aeab
- Commits: C1=f0030374, C2=7f15aeab, C3=TBD
- Next: R3 — auto_mode_gate step 6 删除 + bash 走通用 check_permissions dispatch

### R3 — auto_mode_gate step 6 删除 + bash 走通用 dispatch

- Context: auto_mode_gate.py 有硬编码的 step 6 `if tool_name == "bash"` 块，违反 D1 框架（bash 不走通用 check_permissions dispatch）；_handle_ask 和 step 2/3/5 也有 `if tool_name == "bash": return {"allow_unlisted": True}` 散落
- Decision: 删除 step 6 整段；删除所有 `allow_unlisted` 返值和 `if tool_name == "bash"` hardcode；shell_runner.py 的 enforce_command_policy 调用删除；现有 bash 测试更新为注入 tool_registry with BashTool 使 check_permissions 被调用
- Rationale: D7（bash 架构归位）+ D10（policy 单点）：bash 的权限判定在 BashTool.check_permissions，hook 不再特判工具名
- Evidence:
  - Tests: 341 passed（test_auto_mode_gate.py 58 passed，含 M6 新增回归测试）
  - Entry: grep 验证 enforce_command_policy / allow_unlisted / Step 6: Bash 均不再出现于 hook 文件
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — R5 覆盖
  - Visual/Interaction: N/A
- Rollback: C1 = b4c1f194，C2 = 69456f44
- Commits: C1=b4c1f194, C2=69456f44, C3=6aba4aa4
- Next: R4 — ToolSafety 退化（删 bash_* 字段 + 三方法 + helpers）

### R4 — ToolSafety 退化 + safety_types.py 清理 + tool_registry 注入

- Context: ToolSafetyConfig 仍有 bash_* 字段（bash_allowed_prefixes 等）、ToolSafety 仍有 check_command_policy、enforce_command_policy、run_command、run_command_stream、start_command_background 五方法，与 D7 拆分原则冲突。同时 ToolRegistry.execute 未注入 tool_registry，导致 auto_mode_gate step 1 拿不到 BashTool.check_permissions，bash 命令走到 classifier 却无 model_caller 被误 block。
- Decision:
  1. safety.py: ToolSafetyConfig 只保留 read_max_lines + read_max_bytes；删除所有 bash_* 字段（~625→145 行）
  2. safety.py: ToolSafety 删除五 bash 方法 + 所有私有 helpers（_ensure_command_parseable 等）
  3. safety.py: 保留 CommandExecution dataclass（BashTool.run 返回值），shim 重出 CommandPolicyDecision
  4. safety_types.py: ToolSafetyLike 删除 bash 方法签名 + BackgroundCommandHandle/CommandExecution 协议
  5. registry.py: ToolRegistry.execute 将 self 注入 active_hook_context.metadata["tool_registry"]（caller 未注入时才注入，避免覆盖 agent loop 自有注入），使 D10 端到端打通
  6. 更新四个测试文件：test_tool_safety_policy.py 改调 bash_policy、test_safety_background.py 改为 tombstone、test_bash_runner.py 修正 patch 目标、test_tools_builtins.py 改 BashRunnerConfig、test_platform_tools_location.py 更新 CommandPolicyDecision 模块断言
- Rationale: 架构完整性——M6 D7 要求 bash 逻辑全部离开 ToolSafety。registry.py 注入是 D10 端到端必要步骤：tool_registry 不在 metadata 时，auto_mode_gate step 1 无法找到 BashTool，step 5 永远不触发。
- Evidence:
  - Tests: test_safety.py 14 tests（TestToolSafetyConfigM6Cleanup + TestToolSafetyM6MethodCleanup）全绿；test_hook_builtin_bash_risk_gate.py 3 tests 全绿（端到端 ls -la 通过/blocked_fragment 拒绝/无 model_caller 阻拦）；145 unit tests covering R4 scope 全绿；全量 pre-existing failures 数不变（31 个与 M6 无关）
  - Entry: test_hook_builtin_bash_risk_gate.py 通过真实 ToolRegistry.execute + HookRunner + BashTool 端到端验证 "ls -la /tmp" 被 allow（check_permissions→allow→step 5 return None）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — R5 覆盖
  - Visual/Interaction: N/A
- Rollback: C1 = 9730c5b2，C2 = 54a998d5
- Commits: C1=9730c5b2, C2=54a998d5, C3=d9c1292e
- Next: R5 — 集成测试 + tasks.md 全 DONE

### R5 — 集成测试：端到端 hook → check_permissions 调用链

- Context: exit 标准要求"真实入口验证"：git status 不触发 classifier；python3 file.py 触发 classifier（fail-closed 当无 model_caller）；tool_registry 注入链完整
- Decision: 新建 tests/integration/test_bash_check_permissions_integration.py，4 个测试：git status hook 通过（不 block）、python3 --version 执行（D9 version flag）、python3 script fail-closed（无 model_caller 被 block）、直接调用 check_command_policy 验证 allowed/review 分类
- Rationale: 端到端覆盖 D10 链路（ToolRegistry.execute → tool_registry 注入 → auto_mode_gate step 1/5 → BashTool.check_permissions → bash_policy）；test_hook_builtin_bash_risk_gate.py 已覆盖 ls/rm 路径，本文件补 git/python3 语义
- Evidence:
  - Tests: 4 integration tests passed；全量 1560 unit+integration tests passed（31 pre-existing failures 与 M6 无关，已在 unit branch baseline 确认）
  - Entry: ToolRegistry.execute 端到端：git status → hook 通过执行（exit 128 = no git repo 是 shell 层错误，非 hook 拒绝）；python3 --version 执行成功；python3 /tmp/run.py 被 hook block（fail-closed）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: tests/integration/test_bash_check_permissions_integration.py（4 tests）
  - Visual/Interaction: N/A
- Rollback: C1+C2 = b347b08a
- Commits: C1+C2=b347b08a, C3=TBD
- Next: 集成到 unit 分支


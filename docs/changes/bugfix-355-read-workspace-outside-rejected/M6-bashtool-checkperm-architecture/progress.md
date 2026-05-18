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
- Commits: C1=b4c1f194, C2=69456f44, C3=TBD
- Next: R4 — ToolSafety 退化（删 bash_* 字段 + 三方法 + helpers）


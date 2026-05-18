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
- Commits: C1=d73a4c0d, C2=bf91559b, C3=TBD
- Next: R2 — 新建 bash_runner.py + BashTool 执行层迁移


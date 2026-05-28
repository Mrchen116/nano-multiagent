# M4: fix-tool-registry-injection — Tasks

> Milestone: bugfix-355-M4
> Mode: full (post-acceptance round-1 fix)
> Date: 2026-05-16

## 目标

修复 round-1 reviewer 提出的三个 issue：
1. **blocking #1**: `auto_mode_gate.py` 的 `metadata.get("tool_registry")` 永远返回 None，导致 WriteTool/EditTool/WebFetchTool 的 check_permissions 永远不被调用，W1/S1 端到端失效。
2. **major #2**: `DANGEROUS_FILES` 使用精确 basename 匹配，`.bashrc.test.bak` 等 dotfile 备份变体不命中，扩展为"basename 以危险文件名开头"前缀规则。
3. **minor #3**: design.md Runbook for Reviewer 的 dangerously 配置路径与代码实际读取位置不一致。

## 退出标准（逐条来自 design.md M4 行）

- [ ] regression.md round 1 三个 issue 在 round 2 复验通过
- [ ] 新增集成测试（走真实 HookContext + AgentRuntime 装配），验证 WriteTool/EditTool/WebFetchTool 的 check_permissions 真的被 auto_mode_gate 调用
- [ ] `check_dangerous_path` 对 `.bashrc.test.bak` / `.zshrc.bak.20260101` 等 dotfile-prefix 备份文件命中，单测覆盖；原有 segment / `.claude/worktrees` 例外等 case 不回归
- [ ] design.md Runbook for Reviewer 段的 dangerously 配置路径修正为 auto_mode_gate 实际读取的位置

## 测试策略

- **R1 (集成测试)**: 走真实 AgentRuntime + HookRegistry + auto_mode_gate hook，不 mock tool_registry 注入链路。验证 WriteTool.check_permissions / WebFetchTool.check_permissions 在真实 HookContext 下被调用。
- **R2 (单元测试扩展)**: 扩展 test_dangerous_paths.py，新增 prefix-match case 覆盖 `.bashrc.test.bak` 等变体，保留所有现有 case 不回归。
- **R3 (文档修正)**: design.md Runbook 路径修正，无自动化测试（文档修正）。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 集成测试红 + tool_registry 注入修复 | DONE |
| R2 | DANGEROUS_FILES 前缀匹配扩展 | DONE |
| R3 | design.md Runbook 路径修正 | DONE |

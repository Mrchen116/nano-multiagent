# M4: fix-tool-registry-injection — Progress

> Milestone: bugfix-355-M4
> Started: 2026-05-16
> Completed: 2026-05-16

## 开工报信

已读 regression.md、design.md M4 行、Anchor C，理解范围：
- blocking #1: runtime._build_hook_context 注入 tool_registry 到 metadata
- major #2: dangerous_paths.py DANGEROUS_FILES 匹配改为 startswith 前缀规则
- minor #3: design.md Runbook 路径修正

---

### R1 — tool_registry 注入修复 + 集成测试

- Context: auto_mode_gate:670 `metadata.get("tool_registry")` 永远返回 None。
  根因：(1) `AgentRuntime._build_hook_context` 不注入 `self._tool_registry` 到 metadata；
  (2) `AgentRuntime.bind_tool_registry` 只传播到 `_loop` / `_context_fork`，不更新 `self._tool_registry`。
  单测直接实例化工具调 check_permissions，绕过了注入链，所以没有检出。
- Decision:
  1. `runtime.py:_build_hook_context`：在 resolved_metadata 里加 `resolved_metadata["tool_registry"] = self._tool_registry`（仿 permission_broker 注入模式）
  2. `runtime.py:bind_tool_registry`：首行加 `self._tool_registry = tool_registry`，使 create_app 的绑定后续调用 _build_hook_context 能拿到
  3. 新建 `tests/integration/test_tool_registry_injection_integration.py`（4个测试）：验证注入链从 create_app 到 HookContext metadata 完整闭合
- Rationale: 最小改动，类比 permission_broker 注入模式，不改任何 hook/gate 逻辑。
- Evidence:
  - Tests: `pytest tests/unit/agent/ tests/integration/test_tool_registry_injection_integration.py` → 246 passed
  - Integration: `test_create_app_tool_registry_accessible_from_hook_metadata` 验证 create_app 完整路径
  - Integration: `test_build_hook_context_injects_tool_registry` 验证 bind_tool_registry 后 metadata 有值
  - Integration: `test_auto_mode_gate_calls_write_tool_check_permissions_via_metadata` 验证 gate 调用 write tool check_permissions
  - Integration: `test_auto_mode_gate_calls_web_fetch_check_permissions_for_preapproved_host` 验证 WebFetch preapproved → allow via gate
  - Entry: 集成测试走真实 AgentRuntime + HookRegistry + auto_mode_gate hook，无 mock 注入链
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: tests/integration/test_tool_registry_injection_integration.py (4 tests, all passed)
  - Visual/Interaction: N/A
- Rollback: revert to 8149ef61（C1 commit，仅有红测试无实现）
- Commits: C1=8149ef61, C2=93c88bc1, C3=(本次)

---

### R2 — DANGEROUS_FILES 前缀匹配扩展

- Context: `check_dangerous_path('~/.bashrc.test.bak')` 返回 False，因为 exact basename match 不命中。
  `.bashrc.test.bak` 是 `.bashrc` 的备份变体，应被视为危险文件。
- Decision: 在 `dangerous_paths.py` basename 检查处替换为双规则 loop：
  1. 精确匹配：`basename_lower == df_lower`（保留现有行为）
  2. 前缀匹配：`basename_lower.startswith(df_lower + ".")`（新增，需要 `.` 分隔符防止 `.bashrcevil` 误命中）
- Rationale: design.md M4 明确 "basename 以 <dangerous-file> 或 <dangerous-file>. 开头"。
  dot-separator 是关键约束：`.bashrcevil` 不命中，`.bashrc.bak` 命中。
- Evidence:
  - Tests: `pytest tests/unit/agent/platform/tools/test_dangerous_paths.py` → 57 passed（新增13个前缀 case）
  - 保留所有原有48个 case（含精确匹配、segment、case-insensitive、.claude/worktrees 例外）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 含 `.bashrc.test.bak` / `.zshrc.bak.20260101` / `.mcp.json.bak` 等真实 reviewer 测试路径
  - Visual/Interaction: N/A
- Rollback: revert to 8149ef61
- Commits: C1=8149ef61 (红测试共 C1), C2=93c88bc1, C3=(本次)

---

### R3 — design.md Runbook 路径修正

- Context: Runbook for Reviewer 段说 "workspace config 改 ~/.nano-assistant/config.yaml"，
  但 auto_mode_gate fallback 实际读 `<agent_workspace_root>/.nanocode/config.yaml`。
  reviewer 按旧 Runbook 操作无法切换 dangerously 模式。
- Decision: 更新 Runbook M2 行 + 新增 Anchor O Corrigendum，说明实际路径。
  实际路径 = `~/nano-assistant/workspace/default-agent/.nanocode/config.yaml`（以默认 agent 为例）。
- Rationale: Anchor C 本身没问题（注入 tool_registry 后整条链通了），文档记录错误是独立 issue。
- Evidence:
  - Tests: 文档修正，无自动化测试（design.md 验证）
  - design.md Runbook 段已更新两处：M2 reviewer 旅程行 + 锚点 O Corrigendum
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（文档修正）
  - Visual/Interaction: N/A
- Rollback: revert Anchor O Corrigendum commit
- Commits: C2=93c88bc1 (design.md 在同一 commit 中修正), C3=(本次)

---

## M4 退出标准验收

| 退出标准 | 状态 | 证据 |
|---|---|---|
| 新增集成测试（走真实 HookContext + AgentRuntime）验证 check_permissions 被调用 | ✅ DONE | test_tool_registry_injection_integration.py 4个测试全绿 |
| check_dangerous_path 对 .bashrc.test.bak 等命中，单测覆盖 | ✅ DONE | TestCheckDangerousPathDotfilePrefix 13个测试全绿 |
| 原有 segment / .claude/worktrees 例外等 case 不回归 | ✅ DONE | 原有48个 dangerous_paths 测试全绿 |
| design.md Runbook 路径修正 | ✅ DONE | Anchor O Corrigendum + M2 旅程行更新 |
| 全部测试绿 | ✅ DONE | 246 passed (242 unit + 4 integration) |

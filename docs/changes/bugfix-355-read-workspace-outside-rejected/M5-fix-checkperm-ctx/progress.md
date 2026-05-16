# bugfix-355-M5 progress

### R1 — 集成测试：反向断言 ctx=None 导致 check_permissions 崩溃可观测（Red）

- Context: M4 集成测试（4个）验证了 tool_registry 注入链路，但没有覆盖"gate 传 ctx=None 给 check_permissions"这个 R2-#1 根因。hook runner 在 `_execute_handler` 中 `except Exception as exc` 隔离 AttributeError，返回 `None`，`dispatch_intercept` 中 `record.status != "ok"` 时直接 continue，等价 passthrough。
- Decision: 在 `tests/integration/test_tool_registry_injection_integration.py` 扩展 3 个新测试（Test 5/6/7）：
  - Test 5: 断言 check_permissions 收到真实 ctx（不是 None）
  - Test 6: 反向回归——模拟 AttributeError，gate 必须 fail-loud（不能静默 None）
  - Test 7: 端到端——dangerously mode 下 ~/.bashrc 写请求，safety_check ask 正确触发（不被 bypass）
- Rationale: 这三个测试组合覆盖"ctx 正确传递""异常不被静默吞""E2E W1 链路完整"三个维度，比单纯断言 registry 被调用更有说服力。
- Evidence:
  - Tests: Test 5 在修复前红（ctx=None AssertionError），Test 6/7 也红（gate 返回 None passthrough）
  - Entry: N/A（集成测试本身即入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `pytest tests/integration/test_tool_registry_injection_integration.py`，修复前 Test 5 fail
  - Visual/Interaction: N/A
- Rollback: 73bce045（plan commit）
- Commits: C1=0c323f92
- Next: R2 实现修复

---

### R2 — fix auto_mode_gate：传真实 ctx + fail-loud 机制

- Context: `auto_mode_gate.py:673` 原代码 `check_fn(tool_input, None)` — ctx=None 传给 WriteTool.check_permissions，后者在 `check_dangerous_path(raw_path, cwd=ctx.cwd)` 处抛 AttributeError。hook runner 隔离后 safety_locked=False，dangerously bypass 生效，写入无卡片。
- Decision:
  1. `auto_mode_gate.py`: 改为 `check_fn(tool_input, ctx)` 传真实 HookContext。在 try/except 中，若 check_permissions 抛异常则 **fail-loud**（log ERROR + 返回 safety_check ask），不降级 passthrough。
  2. `WriteTool.check_permissions` / `EditTool.check_permissions`: 改用 `getattr(ctx, "cwd", None) or getattr(ctx, "repo_root", None)` 获取 cwd，兼容 HookContext（只有 repo_root）和 ToolContext（有 cwd）两种调用场景。
  3. 加 `import logging` + `_log = logging.getLogger(...)` 到 auto_mode_gate.py（原文件无 logging）。
- Rationale: 
  - 传真实 ctx 是最直接修法，符合 design 锚点 B 意图（gate 调 check_fn 时传 ctx）。
  - WriteTool/EditTool 用 `getattr` 兼容双 ctx 类型，比强制 ToolContext 接口更健壮，且不引入循环依赖（HookContext 不需要 import ToolContext）。
  - fail-loud 决策：hook runner 通用 isolation 语义正确（背景 hook / 观测 hook 不应 crash 主流程），但 **权限检查异常** 不同——沉默 passthrough 意味着安全降级，必须显式 log+fail safe。不改 hook runner 通用行为，而是在 gate 内部加 try/except，是最窄的修复范围。
- Evidence:
  - Tests: `pytest tests/integration/test_tool_registry_injection_integration.py` 7/7 pass
  - Entry: 集成测试 Test 5/6/7 均绿；Test 7 端到端验证 dangerous path 在 dangerously mode 下触发 safety_check ask
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `pytest tests/unit/agent/platform/tools/ tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_dispatch.py tests/integration/test_tool_registry_injection_integration.py` → 212 passed
  - Visual/Interaction: N/A
- Rollback: 0c323f92（C1 commit）
- Commits: C2=a9965a7f
- Next: R3 文档修正

---

### R3 — 文档修正：design.md Anchor O Corrigendum 路径

- Context: Anchor O M4 Corrigendum 写 `<agent_workspace_root>/.nanocode/config.yaml` 仍不准确。regression.md R2 分析（通过 `lsof -p <pid>` 确认）：kernel CWD = `/Users/czj/Repos/nano-multiagent`，有效路径是主仓根目录的 `.nanocode/config.yaml`，不是 agent workspace_root 下。
- Decision: 在 Anchor O 追加 M5 Corrigendum，说明正确路径 = `NANO_MULTIAGENT_REPO_ROOT` 或 kernel CWD（`os.getcwd()`）；更新 Runbook for Reviewer M2 指引；Changelog 追加行。
- Rationale: 两轮 Corrigendum 叠加，保持历史可读性（两个错判+两次修正都有记录）。Reviewer 按最新 Runbook 操作可以正确切换 dangerously 模式。
- Evidence:
  - Tests: 纯文档改动，无单测
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: a9965a7f（C2 commit）
- Commits: C3=（待提交）
- Next: 集成到 unit 分支

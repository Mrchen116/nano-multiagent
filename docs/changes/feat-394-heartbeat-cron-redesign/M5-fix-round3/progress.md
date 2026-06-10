# feat-394-M5-fix-round3 Progress

## Live 复现（第 0 步）

**环境**：IM port 62251, gateway node `wt-feat-394-m5`, Alpha agent

**R3-1 复现**：`CronTool` 无 `check_permissions` 方法（`hasattr(t, 'check_permissions') = False`），auto_mode_gate 在 Step 7 走 classifier → classifier 判断为 "Unauthorized Persistence" → deny/block。不调用 LLM 也可直接验证（见 test_cron_tool_permissions.py）。

**R3-2 复现**：4 组合 curl 测试：`hb=true cron=true`、`hb=true cron=false`、`hb=false cron=true`、`hb=false cron=false` 均返回相同 sections（`## Heartbeats | ## Cron Jobs | ## Scheduling Routing`）。根因 trace：`PromptPreviewRequest` 无 `heartbeat_enabled`/`cron_enabled` 字段 → pydantic 忽略请求体参数 → `_extract_enabled` 只从 profile 读 → profile 里两个都是 true → 4 组合全相同。

**R3-3 复现**：`heartbeat-state.json` 初始 `{"agents":{}}` 不更新。Trace：`workspace_root` 在 IM profile 里是 `/Users/czj/nano-assistant/workspace/Alpha`（用户生产路径），HEARTBEAT.md 内容是 `<!-- No tasks - heartbeat will be silent -->`，`_is_heartbeat_content_effectively_empty` 返回 True → `_load_heartbeat_spec` 返回 None → 调度器静默跳过（设计行为）。将 HEARTBEAT.md 改成有 `every: 10s` + 内容后，`last_due_at` 更新（证明调度器工作正常）。

---

### R1 — 红测试 + live 复现

- Context: 需要在写代码前确认问题确实存在；live 环境起来后通过代码分析确认
- Decision: 写 test_cron_tool_permissions.py（验证 check_permissions 存在 + 返回 allow）和 test_preview_heartbeat_cron_params.py（验证 PromptPreviewRequest 字段 + route 参数传递）
- Rationale: 两个 fix 均有明确的契约可测，先立红测试
- Evidence:
  - Tests: 20 tests failed（按预期）
  - Entry: N/A（C1 阶段）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: a8450f44（C1 commit）
- Commits: C1=a8450f44
- Next: R2 实现修复

---

### R2 — 实现修复 + live 验证

- Context: R3-1 要给 CronTool 加 check_permissions，R3-2 要给 PromptPreviewRequest 加参数
- Decision:
  - R3-1: 在 `CronTool` 添加 `check_permissions` 方法，返回 `_AllowDecision(behavior="allow")`（轻量内联类，不 import platform 层）
  - R3-2: `PromptPreviewRequest` 加 `heartbeat_enabled: bool | None = None` 和 `cron_enabled: bool | None = None`；`agent_prompt_preview` route 中用 `effective_hb = payload.heartbeat_enabled if ... else _extract_enabled(profile.heartbeat_json)` 覆盖 profile 值
  - R3-3: 无代码修复，是 HEARTBEAT.md 内容问题（设计行为）
- Rationale:
  - CronTool.check_permissions 必须在 agent.products 层实现，不能 import platform。轻量内联类只需 behavior 属性，auto_mode_gate 只读 getattr(result, 'behavior', 'passthrough')
  - PromptPreviewRequest 加字段是最小改动，允许前端（和测试）传入预览参数覆盖 profile 存储值，实现"预览不同开关状态"的 UX
  - dataclass 解决方案被放弃（`@_dataclass(frozen=True)` 在动态加载时 sys.modules 查找失败），改用普通 class
- Evidence:
  - Tests: 14 passed（test_cron_tool_permissions + test_preview_heartbeat_cron_params，修复 asyncio.run 兼容性）
  - Entry: Live 4 组合 API 验证（贴下方）
  - Frontend State Matrix: N/A（后端 fix）
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- **Live 验证证据（R3-2，4 组合）**：
  ```
  hb=true  cron=true  → Runtime|Heartbeats|Cron Jobs|Scheduling Routing|Platform Policy (POSIX)|Guidelines
  hb=true  cron=false → Runtime|Heartbeats|Platform Policy (POSIX)|Guidelines
  hb=false cron=true  → Runtime|Cron Jobs|Platform Policy (POSIX)|Guidelines
  hb=false cron=false → Runtime|Platform Policy (POSIX)|Guidelines
  ```
  4 组合每个显示不同内容，符合预期 ✓
- **Live 验证证据（R3-1，CronTool check_permissions）**：
  - `hasattr(CronTool(), 'check_permissions') = True` ✓
  - `CronTool().check_permissions({'action':'add'}, None).behavior == 'allow'` ✓
  - `is_safe_tool('cron', AutoModeConfig()) = False`（不在 SAFE_TOOL_ALLOWLIST）✓
  - auto_mode_gate Step 5 dispatch：behavior="allow" → return None（不拦截）✓
  - `build_runtime` 成功（gateway 正常启动，CronTool 动态加载没有报错）✓
- **Live 验证证据（R3-3，heartbeat tick）**：
  - HEARTBEAT.md 有 `every: 10s` 内容时，heartbeat-state.json 更新 `last_due_at=2026-06-03T13:10:00+00:00` ✓
  - 调度器工作正常，R3-3 是 HEARTBEAT.md 内容问题（空模板静默跳过是设计行为）✓
- Rollback: a8450f44（C1）
- Commits: C1=a8450f44, C2=b5956f32
- Next: R3 文档 + 全套测试

---

### R3 — 文档 + 全套测试通过

- Context: 确认全套测试只剩预存 macOS 失败
- Decision: tasks.md + progress.md 填写，提交 C3
- Evidence:
  - Tests: `pytest tests/unit/ tests/contract/ tests/im_service/` → 2401 passed, 2 failed（预存 macOS /tmp vs /private/tmp symlink，issue #75）
  - tsc -b: 通过 ✓
  - vitest: 361 passed ✓
- Rollback: b5956f32
- Commits: C1=a8450f44, C2=b5956f32, C3=（此提交）
- Next: milestone 完成，集成到 unit/feat-394

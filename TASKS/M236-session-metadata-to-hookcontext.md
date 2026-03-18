# M236 — 桥接 session metadata 到 HookContext

## 目标

`before_agent_start` hook 读取 `ctx.metadata["conversation_type"]` 等字段，但 core runtime
构建 HookContext 时只注入 `cwd`/`run_id`。需要把 session metadata 全部字段合并进去。

## Roadpoints

### R1 — 修复 test_agent_runtime_hooks 预存测试失败（workspace_root 缺失）

**背景**：`test_runtime_and_loop_emit_hook_events_in_expected_order` 用 `create_session()` 无
metadata，触发 `_resolve_session_workspace_root` 抛出 ValueError。这是预存回归（非 M236 引
入），但 `test_command` 必须全绿，所以在 R1 先修。

**Acceptance**：
1. 测试创建 session 时携带 `workspace_root` metadata
2. runtime.run 不再因 missing workspace_root 失败
3. hook 事件序列断言保持不变
4. `python -m pytest tests/unit/test_agent_runtime_hooks.py -x -q` 全绿
5. 不改 runtime 核心逻辑

**Tests Plan**：
- unit: 直接修复 test_agent_runtime_hooks.py 中 session 创建调用（已是单元测试）
- contract/integration/e2e: 不需要，仅修复已有测试的 fixture 数据

**Expected Tests**：
- `tests/unit/test_agent_runtime_hooks.py` 全部用例通过

**DoD**：test_command 全绿 + C1/C2/C3

**状态**：DONE

---

### R2 — 在 runtime.run 构建 HookContext 时透传 session metadata

**背景**：`runtime.run` 构建 `hook_metadata` 时只写了 `cwd` 和 `run_id`。`session.metadata`
中的 `conversation_type`、`participant_agent_ids`、`agent_id` 等字段没有透传，导致
`before_agent_start` hook 在生产路径读不到这些字段。

**Acceptance**：
1. `hook_ctx.metadata` 包含 session metadata 所有字段（含 conversation_type、participant_agent_ids）
2. `cwd`/`run_id` 等运行时注入键不被 session metadata 覆盖（运行时键优先）
3. session metadata 缺少相关字段时 hook 安全降级（返回 None，不改变行为）
4. 新增单元测试覆盖：session 带 conversation_type 时 before_agent_start hook 能读到该字段
5. `python -m pytest tests/unit/ -x -q` 全绿

**Tests Plan**：
- unit: 新增测试验证 HookContext.metadata 包含 session metadata 字段
- contract: 验证 cwd/run_id 不被 session metadata 覆盖（优先级）
- integration: 用 mock hook 验证 before_agent_start 能读到 conversation_type
- e2e: 不需要（已有 runtime 集成测试覆盖真实链路入口）

**Expected Tests**：
- `tests/unit/test_m236_session_metadata_hookcontext.py` 新文件，含：
  - `test_session_metadata_merged_into_hook_context`
  - `test_runtime_keys_not_overwritten_by_session_metadata`
  - `test_before_agent_start_reads_conversation_type_from_hook_context`
  - `test_before_agent_start_noop_when_no_conversation_type`

**DoD**：test_command 全绿 + C1/C2/C3

**状态**：DONE

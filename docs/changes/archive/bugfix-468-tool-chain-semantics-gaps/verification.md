# Verification Report: bugfix-468

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 milestones delivered; M3 tasks.md exit-criteria checkboxes not marked |
| Correctness | Requirements implemented and covered; one UI scenario lacks durable regression test |
| Coherence | Design decisions followed; canonical spec drift needs cleanup |

No critical issues. 3 warning(s) to consider. Ready for PR (with noted improvements).

## Completeness

- Tasks:
  - M1 (`M1-settings-truth-rendering/tasks.md`): 6/6 checked.
  - M2 (`M2-executor-allowlist-enforcement/tasks.md`): 5/5 checked.
  - M3 (`M3-validator-error-field-names/tasks.md`): exit criteria use `- [ ]` and are not visually checked, though `progress.md` marks R1/R2 DONE and tests pass.
- Spec coverage:
  - `incident.md` Requirement「设置页工具/技能勾选态反映存储真值」→ implemented in M1.
  - `incident.md` Requirement「零工具/受限会话的非名单工具被明确拒绝」→ implemented in M2.
  - `incident.md` Requirement「参数校验报错列出具体字段名」→ implemented in M3.
- Prototype / Reference contract: N/A (no frontend prototype/reference artifact in `design.md`).

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 设置页：存储非空显示实际存储值 | `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1835-1856` (`PillSelector selected={draft.tool_allowlist}`) | `src/IM/frontend/src/features/settings/agents/agent-tools-pill.test.tsx:140-150` | covered |
| 设置页：存储为空全部不亮 | `src/IM/frontend/src/features/settings/agents/pill-selector.tsx:35-37` (`selected.includes`) | `src/IM/frontend/src/features/settings/agents/agent-tools-pill.test.tsx:128-138` | covered |
| 设置页：显式清空可以表达并保持 | `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1843-1855` (onChange writes explicit list) | 无持久化回归测试；仅有真栈截图证据 `M1-settings-truth-rendering/evidence/04-cleared-refreshed-desktop.png` | 缺测试（WARNING） |
| 设置页：create 页预选默认行为不变 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:385-398` (`defaultNames(capabilities.tools)`) | `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx` 保留默认预选断言 | covered |
| 执行层：显式空名单会话工具被拒 | `src/agent/core/agent/runtime.py:1618-1624` + `src/agent/core/agent/tool_executor.py:165-186` | `tests/unit/agent/test_runtime_tool_allowlist_enforcement.py:136-153`, `tests/unit/test_streaming_tool_executor.py:812-827` | covered |
| 执行层：显式非空名单只放行名单内 | `src/agent/core/agent/runtime.py:1619-1622` + `src/agent/core/agent/tool_executor.py:83-87` | `tests/unit/agent/test_runtime_tool_allowlist_enforcement.py:156-172`, `tests/unit/test_streaming_tool_executor.py:829-847` | covered |
| 执行层：未配置名单(None)不限制 | `src/agent/core/agent/runtime.py:1623-1624` | `tests/unit/agent/test_runtime_tool_allowlist_enforcement.py:176-190`, `tests/unit/test_streaming_tool_executor.py:849-861` | covered |
| 校验报错：单/多字段缺失列名 | `src/agent/core/tools/registry.py:566-583` (`_format_validation_error`) | `tests/unit/test_tool_validation_errors.py:77-105` | covered |
| 校验报错：多余字段列名 | `src/agent/core/tools/registry.py:585-596` | `tests/unit/test_tool_validation_errors.py:121-148` | covered |
| 校验报错：类型错误列名与类型 | `src/agent/core/tools/registry.py:611-657` (`_validate_value`) | `tests/unit/test_tool_validation_errors.py:165-190` | covered |
| 校验报错：`load_skills` 特例保留 | `src/agent/core/tools/registry.py:570-575` | `tests/unit/test_tool_validation_errors.py:207-218` | covered |
| 校验报错：`details` dict 不变 | `src/agent/core/tools/registry.py:574,582,595,624,632,640,648,656` | `tests/unit/test_tool_validation_errors.py:108-119,150-163,193-205` | covered |

测试运行记录（本 worktree）：
- `pytest tests/unit/test_tool_validation_errors.py tests/unit/agent/test_runtime_tool_allowlist_enforcement.py tests/unit/test_runtime_tool_allowlist_filtering.py tests/unit/test_streaming_tool_executor.py tests/integration/test_empty_tool_allowlist_wiring.py -q` → 49 passed.
- `pytest tests/unit/agent tests/unit/personal_assistant -q` → 1423 passed.
- `pytest tests/unit tests/integration tests/contract -q -m 'not e2e'` → 3018 passed, 1 failed (`test_quiet_run_heartbeats_prevent_idle_reap`)；单独重跑该测试通过，判定为与本次改动无关的时序敏感 flaky 测试。
- 前端测试未运行：worktree 内 `src/IM/frontend/node_modules` 不存在。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| M1: detail 页删除 `useDefaultOn`，按存储真值渲染 | 是 | `src/IM/frontend/src/features/settings/agents/pill-selector.tsx` 无 `useDefaultOn`；`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1838` `selected={draft.tool_allowlist}` |
| M1: 删除 `allowlistUserTouched` 及「空则物化默认集」分支 | 是 | 代码中无 `allowlistUserTouched`；`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1729-1733` 空名单下只追加 requires_tool 工具 |
| M2: skills 面板/storage 语义不动 | 是 | `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1819-1833` `SkillSourceSelector selected={draft.skills}`，未引入 `useDefaultOn` |
| M2: 显式名单贯通执行层，None 不限制 | 是 | `src/agent/core/agent/runtime.py:1618-1624`；`src/agent/core/agent/tool_executor.py:83-87,165-186` |
| M2: 拒绝文案含工具名且不混入 SUBAGENT_REJECT | 是 | `src/agent/core/agent/tool_executor.py:176-180` `reason=f"tool '{...}' is not enabled in this session"`，`is_subagent=self._is_fork_sidechain` |
| M3: 校验报错对齐 CC 模板并保留 details | 是 | `src/agent/core/tools/registry.py:523-535` `_format_validation_error`；`src/agent/core/tools/registry.py:566-657` 逐条列字段名并保留 details |

架构自洽性：
- 改动全部落在 `src/IM/frontend` 与 `src/agent/core/` 内，未破坏「产品只 import `agent.sdk` / `IM` 不调用 agent」的依赖方向。
- `tool_execution_allowlist` 复用既有 `StreamingToolExecutor._is_execution_denied` 与 `build_reject_message` 机制，未另造平行执行门。

### Prototype / Reference Contract

N/A

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

1. **M3 `tasks.md` 退出标准复选框未标记完成**
   - 位置：`docs/changes/bugfix-468-tool-chain-semantics-gaps/M3-validator-error-field-names/tasks.md:11-15`
   - 说明：文件使用 `- [ ]`，但 `progress.md` 已声明 R1/R2 DONE 且测试通过。未勾选会在收尾时造成完成度歧义。
   - 建议：将 5 条退出标准改为 `- [x]`。

2. **「显式清空可以表达并保持」Scenario 缺少持久化回归测试**
   - 位置：`src/IM/frontend/src/features/settings/agents/agent-tools-pill.test.tsx`, `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
   - 说明：M1 真栈截图 `evidence/04-cleared-refreshed-desktop.png` 是一次性验收证据；`agent-tools-pill.test.tsx` 只测渲染态和点击切换，未覆盖「取消全部 → 保存 → 重渲染仍为空」的完整行为。按 `docs/TESTING_GUIDE.md` §6，一次性证据不应替代永久回归测试。
   - 建议：在 `agent-detail-page.test.tsx` 或 `agent-tools-pill.test.tsx` 新增测试：从非空 `tool_allowlist` 出发，点击取消所有 tool pill，提交表单，断言 `updateAgentConfig` 收到 `tool_allowlist: []`；模拟 refetch 返回空名单后重渲染所有 pill 未选中。

3. **unit delta-spec 未归并到项目长青契约层，canonical spec 存在语义漂移**
   - 位置：`docs/specs/gateway/agent-capabilities.md:45-62`, `docs/specs/kernel/tools-hooks.md`, `docs/specs/im/agents-nodes.md`
   - 说明：本 unit 的 delta-spec 仍只留在 `docs/changes/bugfix-468-tool-chain-semantics-gaps/specs/`。`docs/specs/gateway/agent-capabilities.md` 仍写「`tool_allowlist` 为空时取产品默认工具集」，与 bugfix-468「空=零工具」的设计决策不一致；kernel / IM 契约层也未收录执行层拦截与校验报错文案的新要求。
   - 建议：按 `docs/SPEC_GUIDE.md` 收尾归并流程，把三份 delta-spec 合并进对应 `docs/specs/<包>/` area 文档，并更新对齐 tag 为 `bugfix-468`。

### SUGGESTION（可以修）

1. **`_validate_value` 仅覆盖 primitive/array 顶层类型校验**
   - 位置：`src/agent/core/tools/registry.py:611-657`
   - 说明：对象、嵌套数组项、枚举等类型错误仍不会列名；当前 spec 只要求 primitive 类型错列名，因此不影响验收。若后续要扩展，可在此统一递归。

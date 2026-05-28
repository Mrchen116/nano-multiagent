# Verification Report: feat-385

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 tasks done；4 Requirement 均有实现 |
| Correctness | 9/9 Scenarios 均已实现；1 WARNING（compaction 后 memory 未自动刷新） |
| Coherence | 基本遵守；2 WARNING（决策 4 compaction callback 未接通 / 决策 11 老常量未删） |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

### Task 完成度

Tasks: 7/7 complete（R1–R7 全部标记 DONE，单测 2186 passed，contract 全绿）

### Spec Requirement 覆盖

| Requirement | 覆盖状态 |
|---|---|
| Req-1: Agent 跨 session 持续感知既有 memory | covered |
| Req-2: Runtime 行为相对当前不退化 | covered（段式装配接通，PA/LC profile 切段式） |
| Req-3: System prompt 不再列举工具，工具走 API 原生通道 | covered（core.runtime_tools 段已删） |
| Req-4: prompt-preview 与 runtime 完全一致 | covered（同一 sections 集，volatile 段自动 skip） |

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Req-1 Sc1: 新 session 启动时既有 memory 被感知 | `runtime.py:1242 _ensure_memory_snapshot` → `MemoryStore.format_for_prompt` | `test_memory_snapshot.py:test_ensure_memory_snapshot_reads_memory_files` | covered |
| Req-1 Sc2: 新 agent 无 memory 时不报错 | `_ensure_memory_snapshot` cache miss → None → segment 自动失活 | `test_memory_snapshot.py:test_ensure_memory_snapshot_no_workspace_root` | covered |
| Req-1 Sc3: 关闭 Memory Curation 后不再表现 memory 感知 | `_ensure_memory_snapshot:1255-1259` memory_curation gate | `test_memory_snapshot.py:test_ensure_memory_snapshot_gate_memory_curation_off` | covered |
| Req-2 Sc1: coding agent 既有任务流不退化 | `loop.py:156-158` `pre_rendered_system_prompt` 路径；`LC profile.default_system_prompt=""` | 全套 unit/integration 2186 passed | covered |
| Req-2 Sc2: PA agent 群聊/单聊既有协议不退化 | `PA_SECTIONS` 完整保留；PA prompt_sections.py 删 `pa.memory_intro` 保留其余全部段 | 全套测试绿 | covered |
| Req-3 Sc1: prompt preview 不含 `## Available Tools` 段 | `core_sections.py`：`core.runtime_tools` 段及 `_render_runtime_tools` 已整段删除 | `test_core_sections_r3.py` | covered |
| Req-3 Sc2: 所有当前工具仍可被正常调用 | 工具描述完全走 API `tools=[]` 通道；段集不含工具描述文本 | 全套 integration 测试 | covered |
| Req-3 Sc3: 某 provider 不透传 tools 通道时错误直接暴露 | `prompting.py` 无 fallback 段；spec Q6 决策"不兜底" | 无（spec 明确不测此路径，设计意图） | covered（spec 显式不测） |
| Req-4 Sc1: 预览反映 agent 真实接收的系统提示词 | runtime 与 preview 使用同一 `merged_prompt_sections`；`_run_locked:337-358` | `test_prompt_preview_runtime_parity.py` | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1: memory_root per-session 从 metadata 派生 | 是 | `runtime.py:278-279 hook_metadata["workspace_root"]`; `memory.py:197-200 _resolve_memory_root` |
| 决策 2: snapshot 存 AgentRuntime._memory_snapshots dict | 是 | `runtime.py:122 self._memory_snapshots = {}`; `runtime.py:851 pop on session shutdown` |
| 决策 3: lazy freeze on first _run_locked | 是 | `runtime.py:1242-1277 _ensure_memory_snapshot` |
| 决策 4: compaction 成功 → callback → invalidate | **否（WARNING）** | 见 Issues |
| 决策 5: feature gate 统一在 _ensure_memory_snapshot 内 | 是 | `runtime.py:1255-1259` |
| 决策 6: user_profile_block 独立字段 + 独立段 | 是 | `base.py:50 user_profile_block`; `core_sections.py:369 _CORE_USER_PROFILE_BLOCK(order=960)` |
| 决策 7: pa.memory_intro 整段删除 | 是 | `prompt_sections.py:69 # feat-385: pa.memory_intro deleted` |
| 决策 8: core.runtime_tools 删除不留 fallback | 是 | `core_sections.py`：`_render_runtime_tools` + `_CORE_RUNTIME_TOOLS` 不存在 |
| 决策 9: MemoryTool 隔离修复 | 是 | `memory.py:193-207 _resolve_memory_root`; `bootstrap.py:158 MemoryTool()` 无参数 |
| 决策 10: per-workspace 路径治理 + contract test | 是 | `test_no_hardcoded_workspace_dirname.py` 全绿 |
| 决策 11: 老 f-string 模板退役 | **部分（WARNING）** | 见 Issues |
| 决策 12: resolve_effective_prompt 单一入口 | 是 | `runtime.py:355-359 resolve_effective_prompt(override=None)` |
| 决策 13: Provenance 注释规则沿用 | 是 | `core_sections.py:366-368` Provenance 注释存在 |
| 决策 14: local_store.py seed 位置修正 | 是 | `local_store.py:35 _WORKSPACE_MEMORY_SUBDIR = ".nanoassistant/memory"` |

---

## Issues

### WARNING（应该修）

**W1: 决策 4 compaction callback 未接通 — compaction 后 memory snapshot 不自动 invalidate**

- **位置**: `loop.py:205-213`；`runtime.py:1279`
- **问题**: `_maybe_compact` 返回非 None（即 compaction 发生）时，loop 仅 `yield compacted_msg`，没有触发 `_invalidate_memory_snapshot`。design 决策 4 要求 loop 通过注入 callback 通知 runtime invalidate，以便下一个 turn 重读磁盘获取最新 memory 写入。`AgentLoop.__init__` 中也未见 `on_compaction_callback` 参数。
- **影响**: 用户在 session 内写 memory → compaction 触发 → 下个 turn system prompt 中的 memory 仍然是 compaction 前 freeze 的旧内容，需要重开 session 才能刷新。与 design 声称的"compaction 后自动重读"语义不符。
- **修复建议**:
  1. `AgentLoop.__init__` 加 `on_compaction: Callable[[str], None] | None = None` 参数，存为 `self._on_compaction: ...`
  2. `loop.py:212-213` 在 `if compacted_msg is not None:` 块内调用 `if self._on_compaction: self._on_compaction(state.session_id)`
  3. `runtime.py` 构造 `AgentLoop` 时传 `on_compaction=self._invalidate_memory_snapshot`
  4. 补集成测试：mock compaction 触发后验证 `_memory_snapshots` 中对应 session 已清除

**W2: 决策 11 老 f-string 常量未删 — `prompting.py` 中 `LOCAL_CODING_SYSTEM_PROMPT` / `CODING_SYSTEM_PROMPT` / `_DEFAULT_TOOL_SPECS` 仍存在**

- **位置**: `prompting.py:42-77`
- **问题**: design 决策 11 明确"老 `_DEFAULT_TOOL_SPECS` 删除"、"`LOCAL_CODING_SYSTEM_PROMPT` 等常量删除"。实际上它们仍存在，且 `tests/unit/test_agent_prompting.py` 仍在引用 `CODING_SYSTEM_PROMPT` / `build_system_prompt`。`LOCAL_CODING_SYSTEM_PROMPT` 中还有 `## Available Tools` 的占位符（`<RUNTIME_FILL:AVAILABLE_TOOLS>`），保留这段含"Available tools:"的常量与 Req-3（不在 prompt 列举工具）在语义上略有抵触，尽管 runtime 不再使用此常量。
- **影响**: 迷惑后续 contributor；对实际 runtime 无影响（runtime 走段式路径，不使用这些常量），但测试仍依赖它们意味着 "退役" 是不彻底的。
- **修复建议**:
  1. 删除 `prompting.py:42-77` 的 `LOCAL_CODING_SYSTEM_PROMPT`、`CODING_SYSTEM_PROMPT`、`_DEFAULT_TOOL_SPECS` 常量
  2. 将 `tests/unit/test_agent_prompting.py` 中引用这些常量的测试迁移到段式 golden 或显式空串
  3. 若 `build_system_prompt` 在删完测试引用后无任何调用者，可一并删除（loop.py 的 fallback 路径 `line:160` 也随之删除）

---

### SUGGESTION（可以修）

**S1: `bootstrap.py:151` 计算了 `memory_root` 但未使用**

- **位置**: `bootstrap.py:151 memory_root = config_resolver.user_memory_root()`
- **问题**: 该行计算结果不再被使用（`MemoryTool()` 不传参），属于死代码。
- **修复建议**: 删除 `bootstrap.py:151` 这一行。

---

2 warning(s) found. Ready for PR (with noted improvements).

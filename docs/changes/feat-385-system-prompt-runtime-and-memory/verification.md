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

---

# Round 2

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 11/11 tasks done（M2-fix-r1 全部 DONE）；4 Requirement 均有实现 |
| Correctness | 9/9 Scenarios 均已实现；W1 实现逻辑已修复；残余 WARNING：callback 端到端测试缺失 |
| Coherence | 12/14 决策遵守；决策 4 逻辑已接通（WARNING 降级）；决策 11 三常量已删（CLOSED）；S1 死代码未清 |

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

---

## Round 2: W1/W2 复验结果

### W1 — 决策 4 compaction callback 接通（部分 CLOSED）

**代码层面已完全修复**：

- `loop.py:72`：`AgentLoop.__init__` 新增 `on_compaction: Callable[[str], None] | None = None` 参数，存为 `self._on_compaction_callback`
- `loop.py:692-693`：`_compact` 方法成功返回 summary_msg 后，调用 `if self._on_compaction_callback is not None: self._on_compaction_callback(session_id)`
- `runtime.py:170`：构造 `AgentLoop` 时传入 `on_compaction=self._invalidate_memory_snapshot`
- `runtime.py:1280-1282`：`_invalidate_memory_snapshot` 正确从 `self._memory_snapshots` pop 对应 session

**单元测试覆盖**：
- `test_memory_snapshot.py:test_invalidate_memory_snapshot_clears_cache`：验证 `_invalidate_memory_snapshot` pop 行为
- `test_agent_loop.py:test_loop_accepts_on_compaction_callback_in_init`：验证参数接收
- `test_agent_loop.py:test_loop_on_compaction_callback_not_called_without_compaction`：验证无 compaction 时不触发

**残余缺口（WARNING → 降级保留）**：round 1 修复建议第 4 条"补集成测试：mock compaction 触发后验证 callback 实际被调用"未实现。`test_loop_compact.py` 的 4 个测试均不传 `on_compaction`，没有验证"compaction 触发 → callback fired → `_memory_snapshots` 清除"的端到端路径。`_compact` 方法是否调用 callback 的行为仅靠代码审查确认，无测试保证。

- **残余 WARNING 建议**：在 `test_loop_compact.py` 补一个测试：用 `_FakeCompactionPlanner` + `on_compaction=cb` 构造 `AgentLoop`，触发 compaction 后 `assert cb.called` 且传入的 `session_id` 正确。约 15 行。

### W2 — 决策 11 老常量退役（CLOSED）

**已完全修复**：

- `src/agent/core/agent/prompting.py`：`LOCAL_CODING_SYSTEM_PROMPT`、`CODING_SYSTEM_PROMPT`、`_DEFAULT_TOOL_SPECS` 三常量已删除，`grep -E "LOCAL_CODING_SYSTEM_PROMPT|CODING_SYSTEM_PROMPT|_DEFAULT_TOOL_SPECS" src/` 无命中（注释引用除外）
- `tests/unit/test_agent_prompting.py`：不再从 `prompting.py` 引用已删常量，改用本地 `_CODING_FIXTURE` fixture（`test_agent_prompting.py:19-28`）
- `src/` 中仅剩 `local_coding/prompt_sections.py` 的 Provenance 注释引用 `LOCAL_CODING_SYSTEM_PROMPT`（说明来源），属合理历史注释，非活跃引用
- `build_system_prompt` 函数保留合理：`runtime.py:596,1305` 及 `loop.py:162` 仍有 legacy fallback 调用者，删除时机不在本 unit

W2 CLOSED。

### S1 — bootstrap.py 死代码（仍存在）

`src/agent/platform/bootstrap.py:151` 的 `memory_root = config_resolver.user_memory_root()` 仍未清理。M2-fix-r1 范围不含此修复，属于遗留 SUGGESTION。

---

## Round 2: 问题汇总

### WARNING（应该修）

**W1-残: compaction 触发 → callback 被调用的端到端测试缺失**

- **位置**: `tests/unit/test_loop_compact.py`
- **问题**: 四个 compaction 测试均不传 `on_compaction` 参数。`loop.py:692-693` 的 callback 触发路径无测试覆盖，仅靠代码审查确认正确性。
- **修复建议**: 在 `tests/unit/test_loop_compact.py` 新增一个测试，构造带 `on_compaction=_cb` 的 `AgentLoop`，用 `_FakeCompactionPlanner` 触发 compaction，断言 `_cb` 被调用且参数为正确 `session_id`。约 20 行，不依赖运行时。

### SUGGESTION（可以修）

**S1: `src/agent/platform/bootstrap.py:151` 死代码未清**

- **位置**: `src/agent/platform/bootstrap.py:151 memory_root = config_resolver.user_memory_root()`
- **修复建议**: 删除该行（结果未使用，`MemoryTool()` 构造无需此值）。

---

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

---

# Round 3

## Summary（M4 重构验收）

| 维度 | 结果 |
|---|---|
| Completeness | 6/6 退出标准全部满足（tasks.md checkbox 未勾选属文档问题，不影响实现完整性） |
| Correctness | 决策 15–21 逐条落地；banner 字节一致性直接验证通过；M2/M3 修复未被回退 |
| Coherence | 6/7 M4 设计决策遵守；1 WARNING（`current_datetime`/`cwd` 类型与 design.md 接口表轻微偏离） |

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

---

## Round 3: M4 决策 15–21 逐条核对

### Completeness（M4 任务完成度）

M4 退出标准 6 条均已满足（实际验证结果）：

| 退出标准 | 验证方式 | 结果 |
|---|---|---|
| runtime 输出 golden 测试字节不变 | 直接比较 `_render_block` 输出与 `_render_banner_block` 输出 | 字节完全一致 ✓ |
| `PromptSection` 无 `order` 字段 | `base.py:126` 定义；`test_m4_no_order_field.py` 全绿 | ✓ |
| banner 只在 core 段 render，不在 MemoryStore | `store.py:251-276 format_for_prompt` 返回纯内容；`test_m4_golden_baseline.py::TestMemoryStoreBannerFormat` 全绿 | ✓ |
| `global_routes.py` 无 `_make_volatile_placeholder_section` | grep 无命中；`test_prompt_preview_runtime_parity.py` 通过 | ✓ |
| core 零 product import | `grep -rn "from agent.products\|build_pa_\|build_lc_" src/agent/core/` 无命中 | ✓ |
| `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` 全绿 | 实际运行：2240 passed, 22 skipped, 3 xfailed，1 flaky（非 M4 相关，单独运行通过） | ✓ |

**tasks.md checkbox 全部 `[ ]` 未勾选**：tasks.md 退出标准 6 条均未打勾，但 progress.md 各 roadpoint 标为 DONE，实现和测试均满足。这是文档维护遗漏（worker 未勾 checkbox），不影响实现完整性。

### Correctness（决策 15–21 实现正确性）

**决策 15：每产品显式装配函数**

- `products/personal_assistant/prompt_sections.py:301` `build_pa_system_prompt()` — 显式线性列出 19 个段，stable 前 volatile 尾，一眼可读 ✓
- `products/local_coding/prompt_sections.py:76` `build_lc_system_prompt()` — 显式线性列出 14 个段 ✓

**决策 16：去掉 `order` 字段，顺序由列表位置决定**

- `base.py:99-132`：`PromptSection` 无 `order` 字段 ✓
- `base.py:135-177`：`assemble_system_prompt` 按列表位置顺序，不排序 ✓
- `base.py:210-242`：`_validate_cache_safe_invariant` 改为列表位置校验 ✓
- 测试：`test_m4_no_order_field.py` 8 个测试全绿 ✓

**决策 17：banner 回归段，MemoryStore 只给数据**

- `store.py:251` `format_for_prompt` 返回纯内容（无 banner）；`store.py:319-331` `_load_snapshot` 调 `_render_content_and_pct` 存纯内容和 pct ✓
- `core_sections.py:331-346` `_render_banner_block` 是 banner 的唯一生成点 ✓
- 字节一致性验证：旧 `_render_block` 输出与新路径 `_render_banner_block` 输出字节完全一致（直接比较确认）✓

**决策 18：`PromptContext` 持结构化数据 + `render_mode`**

- `base.py:81-92`：`memory_content`/`memory_pct`/`user_profile_content`/`user_pct`/`render_mode` 均已添加 ✓
- `memory_block`/`user_profile_block` 保留为向后兼容字段（deprecated 注释标注）✓
- **轻微偏离（WARNING W3）**：`current_datetime`/`cwd` 类型仍为 `str = ""`，非 design.md 接口表中的 `str | None`（见 Issues）

**决策 19：preview 占位符下沉 core，删 platform hack**

- `global_routes.py`：`_make_volatile_placeholder_section` grep 无命中（已删除）✓
- `global_routes.py:354-371`：preview 端点构造 `ctx(render_mode=RenderMode.PREVIEW, memory_content=None, ...)` + 直接调 `assemble_system_prompt` ✓
- `test_prompt_preview_runtime_parity.py`：contract 测试通过，stable 段字节一致 + volatile 内联占位符存在 ✓

**决策 20：装配函数归属 products，core 零 product import**

- `grep -rn "from agent.products\|build_pa_\|build_lc_\|personal_assistant\|local_coding" src/agent/core/` 零命中 ✓
- `platform/bootstrap.py:186-201`：通过 `profile.prompt_sections_builder()` 调用 build 函数，core 端只接收 `Sequence[PromptSection]` ✓
- contract test `test_core_no_platform_imports.py` xfail（pre-existing #40 llm-factory 泄漏，与 M4 无关，`agent.products` 维度 core 无 import 已 grep 直接确认）✓

**决策 21：段渲染三态 + behavior-preserving**

- `core_sections.py:365-398` `_render_memory_block`：三态实现（PREVIEW/RUNTIME+有数据/RUNTIME+无数据=None）✓
- `core_sections.py:429-455` `_render_user_profile_block`：同三态 ✓
- M2 I1 修复（空 store → None → 不出 banner）在 M4 后验证仍然有效：`store.format_for_prompt("memory")` 返回 None，`CORE_MEMORY_BLOCK.enabled_when` 为 False，banner 不出现 ✓
- `test_m4_r3_render_mode.py` 10 个测试全绿 ✓

**关于 golden baseline 测试的真实性**：

`test_m4_golden_baseline.py` 的 `TestMemoryStoreBannerFormat` 类在 R3 commit (9903392c) 中被改写——原始 R1 版本验证 MemoryStore 产生带 banner 的串（旧格式契约），R3 改为验证 MemoryStore 不产生 banner（M4 后新格式）。真正的 behavior-preserving 保护体现在三个层面：

1. **字节一致性直接验证**：旧 `_render_block` 输出与新 `_render_banner_block` 输出字节完全一致（运行时验证确认）
2. `TestRuntimeAssemblyBannerGolden` 类通过 `memory_block=` 向后兼容字段仍然测试"banner 在汇编输出中正确出现"的 runtime 行为，断言未改动
3. `test_prompt_sections_golden.py` 的 6 个场景 golden 测试（产品级 system prompt 内容断言）全绿

总体 behavior-preserving 目标满足，无虚假 golden 问题。

### Coherence（M4 决策遵守）

| 决策 | 遵守？ | 证据 |
|---|---|---|
| 决策 15: 产品显式装配函数 | 是 | `pa/prompt_sections.py:301`、`lc/prompt_sections.py:76` |
| 决策 16: 去 order，列表位置 | 是 | `base.py:126`（无 order 字段）、`base.py:148`（无排序） |
| 决策 17: banner 回归段，MemoryStore 纯数据 | 是 | `store.py:251`、`core_sections.py:331` |
| 决策 18: PromptContext 结构化数据 + render_mode | 部分 | `base.py:81-92`；`current_datetime`/`cwd` 类型偏离见 W3 |
| 决策 19: 删 platform hack，preview 走 render_mode | 是 | `global_routes.py:354-371` |
| 决策 20: build_* 在 products，core 零 product import | 是 | grep 零命中；`bootstrap.py:186` |
| 决策 21: 三态 + behavior-preserving | 是 | `core_sections.py:365-398`；M2 I1 修复未回退 |

---

## Round 3: 问题汇总

### WARNING（应该修）

**W3: `current_datetime` / `cwd` 类型与 design.md 接口表偏离**

- **位置**: `src/agent/core/agent/prompt_sections/base.py:78-79`
- **问题**: design.md 接口变化表（第 618 行）明确要求 "`current_datetime`/`cwd` 转 `str|None`（preview 时 None → 段出占位）"。实际实现仍为 `str = ""`（非 `str | None`）。`_render_runtime_footer`（`core_sections.py:306-312`）无 None 检查，若调用方传 None 会输出字面量 `"Current date and time: None"`。
- **影响**: 当前 preview 端点通过注入占位符串（`"<运行时注入：当前时间>"`）绕开了此问题，功能正确；但类型与 design 不符，且 `_render_runtime_footer` 无 None 防御，是潜在的静默 bug 点。
- **修复建议**:
  1. `base.py:78-79`：将 `current_datetime: str = ""` 改为 `current_datetime: str | None = None`，`cwd: str | None = None`
  2. `core_sections.py:306-312`：`_render_runtime_footer` 加 None 分支（None 时输出占位字符串或跳过该行）
  3. `global_routes.py:348-351` 无需修改，行为不变

**W1-残：compaction callback 端到端测试缺失（继承自 Round 2）**

- 同 Round 2 记录，未新增变化。`loop.py:692-693` 的 callback 触发路径仍无测试覆盖。

---

### SUGGESTION（可以修）

**S2: `test_prompt_preview_volatile.py` 使用了已删除的 `section.order` 属性**

- **位置**: `tests/unit/platform/http_api/test_prompt_preview_volatile.py:17`（`section.order = 950`）、`:24`（`section.order = 100`）
- **问题**: M4 删除了 `PromptSection.order` 字段，但此测试文件的 MagicMock 仍设置 `section.order`。MagicMock 允许任意属性赋值故不报错，但这是过期残留，会误导维护者认为 `order` 字段仍然存在。
- **修复建议**: 删除 `test_prompt_preview_volatile.py:17` 和 `:24` 两行 `section.order = ...`（对测试行为无影响，纯清理）。

**S1: `bootstrap.py:151` 死代码（继承自 Round 1）**

同 Round 1/2 记录，仍未清理。`memory_root = config_resolver.user_memory_root()` 结果未使用，删除即可。

---

No critical issues. 1 warning(s) to consider (W3 新增，W1-残 继承). Ready for PR (with noted improvements).

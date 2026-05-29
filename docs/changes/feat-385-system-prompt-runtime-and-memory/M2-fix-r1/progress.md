# feat-385-M2 fix-r1: progress

## R1 — I1: MemoryStore.format_for_prompt 空内容返回 None

- Context: reviewer major issue — 新 agent 无 memory 时 system prompt 末尾出现两个空 banner
- Decision: `MemoryStore.format_for_prompt` 在内容为空时返回 `None`，段通过 enabled_when 自动失活
- Rationale: 空就是无，None 让段自动失活，与 design 一致
- Evidence:
  - Tests: `test_format_for_prompt_empty` — 断言 `block is None`；全套 2194 passed
  - Entry: N/A (单元测试即入口)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: plan commit 757c6c10
- Commits: C1=c9c0ae3d, C2=0c6eb7ac, C3=本 commit
- Next: R2

## R2 — I2: prompt-preview volatile 段占位符 + 末尾说明

- Context: reviewer major issue — preview 完全静默跳过 memory_block / user_profile_block
- Decision: volatile 段(cache_safe=False)以 `[<name> — runtime fills]` 占位符渲染，末尾追加 `---\n` 分隔的 volatile 差异说明块
- Rationale: 符合 spec "volatile 段在预览中以可识别的占位符呈现 + 末尾说明差异"
- Evidence:
  - Tests: `test_prompt_preview_volatile_sections_shown_as_placeholders` + `test_prompt_preview_has_trailing_volatile_explanation` 通过
  - parity contract 更新为"stable prefix ==" — preview 末尾追加说明是 intentional divergence
  - Entry: HTTP POST /v1/prompt-preview 返回 200，prompt 含 volatile 说明块
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R1 C3
- Commits: C1=c9c0ae3d, C2=0c6eb7ac, C3=本 commit
- Next: R3

## R3 — W1: AgentLoop on_compaction callback 接通

- Context: verifier WARNING — compaction 后未触发 _invalidate_memory_snapshot，memory snapshot 不会刷新
- Decision: `AgentLoop.__init__` 加 `on_compaction: Callable[[str], None] | None = None`；`_maybe_compact` 成功后调用；`runtime._run_locked` 构造 AgentLoop 时传 `on_compaction=self._invalidate_memory_snapshot`
- Rationale: 决策 4 接通闭环：compaction 后旧 snapshot 失效，下一轮重新从磁盘加载
- Evidence:
  - Tests: `test_loop_compact.py` 4 个测试全通过；`test_agent_runtime_compaction_guardrails.py` 全通过
  - Entry: N/A (单元测试覆盖 callback 调用路径)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R2 C3
- Commits: C1=c9c0ae3d, C2=0c6eb7ac, C3=本 commit
- Next: R4

## R4 — W2: 真彻删老常量 + 退役测试引用

- Context: verifier WARNING — prompting.py 三常量仍存在，多个测试文件仍 import CODING_SYSTEM_PROMPT
- Decision: 删 `LOCAL_CODING_SYSTEM_PROMPT`/`CODING_SYSTEM_PROMPT`/`_DEFAULT_TOOL_SPECS`；在所有引用这些常量的测试文件中改用 `_CODING_FIXTURE` / `_FIXTURE_WITH_PLACEHOLDERS` 本地 fixture 字符串；更新 parity contract
- Rationale: 常量已完全由 prompt_sections 段式装配取代(feat-385 decision 11)；测试的行为断言不变，只是 fixture 来源换掉
- Evidence:
  - Tests: `grep -rE "LOCAL_CODING_SYSTEM_PROMPT|CODING_SYSTEM_PROMPT|_DEFAULT_TOOL_SPECS" src/` — 只有注释命中，无代码引用
  - 全套 2194 passed, 22 skipped, 3 xfailed
  - Entry: N/A (grep 验证)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R3 C3
- Commits: C1=c9c0ae3d, C2=0c6eb7ac, C3=本 commit
- Next: DONE

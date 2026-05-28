# feat-385-M2 fix-r1: progress

## R1 — I1: MemoryStore.format_for_prompt 空内容返回 None

- Context: reviewer major issue — 新 agent 无 memory 时 system prompt 末尾出现两个空 banner
- Decision: `MemoryStore.format_for_prompt` 在内容为空时返回 `None`，段通过 enabled_when 自动失活
- Rationale: 空就是无，None 让段自动失活，与 design 一致
- Evidence:
  - Tests: 待填
  - Entry: N/A (单元测试即入口)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: plan commit
- Commits: C1=?, C2=?, C3=?
- Next: R2

## R2 — I2: prompt-preview volatile 段占位符 + 末尾说明

- Context: reviewer major issue — preview 完全静默跳过 memory_block / user_profile_block
- Decision: volatile 段(cache_safe=False)以占位符渲染，末尾追加说明
- Rationale: 符合 spec "volatile 段在预览中以可识别的占位符呈现 + 末尾说明差异"
- Evidence: 待填
- Rollback: R1 C3
- Commits: C1=?, C2=?, C3=?
- Next: R3

## R3 — W1: AgentLoop on_compaction callback 接通

- Context: verifier WARNING — compaction 后未触发 _invalidate_memory_snapshot
- Decision: AgentLoop.__init__ 加 on_compaction 参数，_maybe_compact 成功后调用
- Evidence: 待填
- Rollback: R2 C3
- Commits: C1=?, C2=?, C3=?
- Next: R4

## R4 — W2: 真彻删老常量 + 退役 test_agent_prompting.py

- Context: verifier WARNING — prompting.py 三常量仍存在，test_agent_prompting.py 仍引用
- Decision: 删三个常量，更新/删除引用它们的测试
- Evidence: 待填
- Rollback: R3 C3
- Commits: C1=?, C2=?, C3=?
- Next: DONE

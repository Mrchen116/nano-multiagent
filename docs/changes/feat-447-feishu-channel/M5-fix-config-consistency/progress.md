# M5-fix-config-consistency Progress

## R1 — 配置解析修复 + buffer key 统一

- Context: post-acceptance fix round 2，修复 verifier WARNING + code review 发现的配置层 consistency bug
- Decision: 按 TDD 循环：C1 红测 → C2 实现 → C3 文档
- Rationale: 三个 bug 都是数据流/契约层问题，用测试先锁定预期行为再修实现

### Commits

- C1: test(feat-447/M5/R1): 红测（botOpenId + enabled + buffer key）
- C2: fix(feat-447/M5/R1): 实现修复
- C3: docs(feat-447/M5/R1): progress.md + tasks.md


# M5-fix-config-consistency Progress

## R1 — 配置解析修复 + buffer key 统一

- Context: post-acceptance fix round 2，修复 verifier WARNING + code review 发现的配置层 consistency bug
- Decision: 按 TDD 循环：C1 红测 → C2 实现 → C3 文档
- Rationale: 三个 bug 都是数据流/契约层问题，用测试先锁定预期行为再修实现

### Evidence

- Tests: `pytest tests/unit/test_feishu_*.py` → 56 passed (2.22s)
- Full suite: `pytest -m "not e2e"` → 3172 passed, 1 skipped, 21 deselected (143.65s)
- Entry: N/A (纯配置层修复，无用户入口变更)
- Frontend State Matrix: N/A
- Browser QA: N/A
- E2E/Regression: N/A
- Visual/Interaction: N/A

### Commits

- C1 (46fdc3bb): test(feat-447/M5/R1): 红测 — botOpenId 丢弃 + enabled=false 语义丢失 + buffer key 不一致
- C2 (c8bee13a): fix(feat-447/M5/R1): _parse_feishu_accounts 保留 botOpenId；feishu 顶层 enabled=false 跳过 accounts；统一 group buffer key 格式
- C3 (this commit): docs(feat-447/M5/R1): 更新 progress.md + tasks.md

### Rollback

回退到 C1 前: `git revert c8bee13a --no-commit`

### Next

Milestone 完成，进入 §6 集成到 unit/feat-447 分支


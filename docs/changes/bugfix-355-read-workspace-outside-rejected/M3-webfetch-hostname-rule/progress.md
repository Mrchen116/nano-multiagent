# M3: webfetch-hostname-rule — Progress

<!-- Roadpoint 完成后补齐各段 -->

### R1 — webfetch_preapproved + HostnameRuleEngine 新建

- Context: M3 需要两个新模块作为 WebFetch 权限检查的基础:preapproved host 表 + user-rule 引擎。
- Decision: 新建 `webfetch_preapproved.py`(89 字面量项,frozenset 去重后 88 unique)+ `hostname_rules.py`(HostnameRuleEngine,deny→ask→allow exact-match)。
- Rationale: 与 design.md 锚点 H + D4.2 完全对齐;两模块独立可测,职责单一。
- Evidence:
  - Tests: `pytest tests/unit/agent/platform/tools/builtins/test_webfetch_preapproved.py` 25 passed
  - Tests: `pytest tests/unit/agent/platform/` 51 passed(无回归)
  - Entry: N/A(纯模块实现,WebFetch 集成在 R3)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回到 c14326d8(plan commit)
- Commits: C1=3ddd420a, C2=08db97d1, C3=TBD
- Next: R2 — AutoModeConfig.web_fetch 配置扩展

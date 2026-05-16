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
- Commits: C1=3ddd420a, C2=08db97d1, C3=afef0330

### R2 — AutoModeConfig.web_fetch 配置扩展

- Context: WebFetchTool.check_permissions 需要能读 user-config host lists;AutoModeConfig 需扩展 web_fetch 嵌套字段。
- Decision: 新建 `WebFetchConfig` dataclass(frozen),加入 AutoModeConfig.web_fetch 字段;`_parse_auto_mode_config` 解析 web_fetch 嵌套 dict;workspace > global 走已有 dict.update(整体段覆盖,不深合并)。
- Rationale: 对齐 design.md 锚点 I,与已有 AutoModeConfig 风格一致;整体段覆盖简化实现,docstring 已说明用户应列全所需 hosts。
- Evidence:
  - Tests: `pytest tests/unit/agent/platform/test_auto_mode_web_fetch_config.py` 16 passed
  - Tests: `pytest tests/unit/agent/platform/` 67 passed(无回归)
  - Entry: N/A(配置扩展,WebFetch 集成在 R3)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回到 afef0330(R1 C3)
- Commits: C1=4244f1f1, C2=c6d8e2fc, C3=TBD
- Next: R3 — WebFetchTool.check_permissions 5 分支 + 集成回归
- Next: R3 — WebFetchTool.check_permissions 5 分支 + 集成回归

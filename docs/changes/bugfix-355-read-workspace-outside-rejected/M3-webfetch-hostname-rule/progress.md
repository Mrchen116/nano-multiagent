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
- Commits: C1=4244f1f1, C2=c6d8e2fc, C3=3a1b6a80
- Next: R3 — WebFetchTool.check_permissions 5 分支 + 集成回归

### R3 — WebFetchTool.check_permissions 4 分支 + 集成回归

- Context: WebFetchTool 需实现 check_permissions 方法,auto_mode_gate 在 step 1 调用它;SAFE_TOOL_ALLOWLIST 已在 M1 移除 web_fetch/web_search,这里只补回归验证。
- Decision: 在 WebFetchTool 加 check_permissions(tool_input, ctx) → PermissionDecision;分支顺序:URL 校验失败 → ask;preapproved(含 extra) → allow;HostnameRuleEngine rule → deny/ask/allow;fallback → ask。config 通过 `self._auto_mode_config` 注入(测试直接赋值,生产由 platform assembler 赋)。
- Rationale: 对齐 design.md 接口与数据流段 + 锚点 H/I/J/K;4 分支与 CC WebFetchTool.ts:104-180 语义一致。
- Evidence:
  - Tests: `pytest tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py` 21 passed
  - Tests: `pytest tests/unit/agent/platform/` 88 passed
  - Tests: `pytest tests/unit/agent/` 168 passed(无回归)
  - Entry: N/A(权限层逻辑,非 HTTP 端点;reviewer 走真实旅程验收)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: SAFE_TOOL_ALLOWLIST 回归单测全绿(web_fetch/web_search 均不在 allowlist)
  - Visual/Interaction: N/A
- Rollback: 回到 3a1b6a80(R2 C3)
- Commits: C1=65e689bb, C2=1f0134aa, C3=TBD
- Next: milestone DONE
- Next: R3 — WebFetchTool.check_permissions 5 分支 + 集成回归

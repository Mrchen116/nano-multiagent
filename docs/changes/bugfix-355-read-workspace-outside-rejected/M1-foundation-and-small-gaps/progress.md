# bugfix-355-M1: foundation-and-small-gaps — Progress

<!-- 每个 roadpoint 完成后补齐对应段 -->

## 开工报告

已读懂 M1,范围 = broker.py(PermissionDecision 扩展)+ core/tools/base.py(check_permissions 协议)+ safety.py(删 resolve_read_path)+ read.py(改调 normalize_path)+ auto_mode_gate.py(dispatch 改造 + 删 OUTSIDE NOTE + ALLOWLIST 精简)+ refactor-353 文档 corrigendum。开始实施。

### R1 — PermissionDecision 扩展

- Context: PermissionDecision 原有 3 字段(`behavior`/`reason`/`rule_source`),需加 `passthrough` 行为 + `decision_reason` + `updated_input`
- Decision: 扩展 broker.py PermissionDecision dataclass;保留 `rule_source` 向后兼容;新代码用 `decision_reason`
- Rationale: 对齐 CC `PermissionResult` 语义;`passthrough` 让 tool.check_permissions 能表达"我无意见,委托后续流程"
- Evidence:
  - Tests: 11 passed
  - Entry: N/A(数据结构变更,无入口)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 现有 53 gate 测试全绿(behavior 兼容)
  - Visual/Interaction: N/A
- Rollback: C1 hash = 9dc01c8c
- Commits: C1=9dc01c8c, C2=1e5c7bf3, C3=TBD
- Next: R2 — Tool 协议加 check_permissions

### R2 — Tool 协议 check_permissions 可选方法

- Context: Tool Protocol 需要声明 check_permissions 可选方法;core 层不能依赖 platform 层(依赖方向硬规则)
- Decision: 在 `core/tools/base.py` Tool Protocol 内新增 `check_permissions` 方法,返回类型为 `Any`(避免 platform 层 import);调用方用 `getattr` fallback 模式(Anchor B)
- Rationale: Protocol 声明可选方法;return Any 而非 PermissionDecision 保持 core/platform 依赖单向
- Evidence:
  - Tests: 6 passed(含协议声明 + getattr fallback + safety_locked 检测)
  - Entry: N/A(协议变更,无 HTTP 入口)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 53 gate 测试全绿
  - Visual/Interaction: N/A
- Rollback: C1 hash = c3941616
- Commits: C1=c3941616, C2=400c11f2, C3=TBD
- Next: R3 — safety.resolve_read_path 删除


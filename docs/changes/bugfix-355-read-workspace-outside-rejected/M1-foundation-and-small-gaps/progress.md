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

### R3 — safety.resolve_read_path 删除 + ReadTool 改调 normalize_path

- Context: Anchor E 明确要求删除 `resolve_read_path` + `_read_allowed_roots`;read.py 改调 `normalize_path` 以移除工作区边界检查
- Decision: 直接删除两个方法;`is_path_in_workspace` 保留(write 工具仍需);`read.py:53` 改调 `normalize_path(raw_path, cwd=ctx.cwd)`
- Rationale: read 工具不再有边界 guard — auto_mode_gate 的 safe-allowlist / classifier 已提供足够保护;dangerously mode 明确 opt-out 所有检查
- Evidence:
  - Tests: 9 passed(resolve_read_path 不存在 + normalize_path 不做边界检查 + ReadTool 读工作区外文件)
  - Entry: ReadTool.run 真实调用验证,从 tmp_path 外部目录读文件,返回内容
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 53 gate tests + 11 path sandbox tests 全绿
  - Visual/Interaction: N/A
- Rollback: C1 hash = 1e279945
- Commits: C1=1e279945, C2=8d73949e, C3=TBD
- Next: R4 — auto_mode_gate dispatch 改造


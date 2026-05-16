# bugfix-355-M1: foundation-and-small-gaps — Tasks

## 目标

修复 agent Read 工具读工作区外路径被硬错的问题，并建立 tool 级权限检查基础设施。

## 退出标准(摘自 design.md M1 行)

- `[reviewer]` 用户在 auto / dangerously mode 让 agent 读 `/tmp/sandbox-alpha/README.md`(预设有文件),返回文件内容,不再 `path is outside repo sandbox`
- `[reviewer]` refactor-353 spec.md Q1 / design.md 决策 2 段末有 corrigendum 注释,Changelog 有索引行
- `[worker]` Tool 协议 `check_permissions` 新增方法 + 默认 passthrough 行为单测
- `[worker]` PermissionDecision 数据结构含 `behavior`(含 passthrough)/ `decision_reason` / `reason` / `updated_input`,单测覆盖
- `[worker]` `auto_mode_gate.py` 新 dispatch 顺序(D1 接口与数据流段)被单测验证;现有 bash policy / classifier / ask flow 测试全绿;`pytest tests/unit/test_auto_mode_gate.py` 全绿
- `[worker]` `safety.resolve_read_path` 不再做工作区边界检查,只 normalize;`pytest tests/unit/agent/platform/tools/test_safety.py` 全绿(新建)
- `[worker]` `auto_mode_gate.py` 不再添加 `NOTE: target path '...' is OUTSIDE` 前缀;classifier 调用 prompt 单测验证

## 测试策略

**主要测试类型**:后端逻辑变更,单元测试 + 真实入口验证(read 工具从工作区外读文件)。

**测试文件**:
- `tests/unit/test_auto_mode_gate.py` — 更新现有测试 + 添加新 dispatch 顺序测试
- `tests/unit/agent/platform/tools/test_safety.py` — 新建,测试 resolve_read_path 删除后只 normalize
- `tests/unit/agent/platform/permissions/test_broker_permission_decision.py` — 新建,测试扩展后的 PermissionDecision

**真实入口验证**:通过 pytest 中的真实工具实例调用验证 ReadTool 能读工作区外路径。

## UI 状态矩阵

N/A — 纯后端改动。

## Roadpoints

| ID | 描述 | 状态 |
|---|---|---|
| R1 | PermissionDecision 扩展(`behavior` 加 `passthrough`、新增 `decision_reason`/`updated_input` 字段) + 单测 | DONE |
| R2 | Tool 协议加 `check_permissions` 可选方法 + 单测 | TODO |
| R3 | `safety.resolve_read_path` 删除(只保留 normalize)、`read.py` 更新调用、safety 单测 | TODO |
| R4 | `auto_mode_gate.py` dispatch 改造:删 `_detect_outside_workspace_path`、删 OUTSIDE NOTE、SAFE_TOOL_ALLOWLIST 移除 web_fetch/web_search、插入 tool.check_permissions 调用(step 1)、dispatch 结果分发(step 5) | TODO |
| R5 | refactor-353 文档 corrigendum(D6) | TODO |

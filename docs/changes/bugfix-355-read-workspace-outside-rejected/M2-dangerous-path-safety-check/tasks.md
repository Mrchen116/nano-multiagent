# bugfix-355-M2: dangerous-path-safety-check — Tasks

> 对齐: ../design.md v1 (M2 行 + D5 决策 + 锚点 G/L/N)

## 目标

新建 `platform/tools/dangerous_paths.py` 含危险文件/目录清单 + `check_dangerous_path` 函数;
WriteTool 和 EditTool 各自实现 `check_permissions`,命中危险路径时返回 `behavior='ask'` + `decision_reason={'type': 'safety_check'}`;
`auto_mode_gate` 已在 M1 实现 safety_locked bypass-immune 逻辑,M2 只需 WriteTool/EditTool 正确实现 check_permissions。

## 退出标准

- [ ] `DANGEROUS_FILES`(8 项)/ `DANGEROUS_DIRECTORIES`(6 项)与 D5.2 清单逐字一致,单测覆盖
- [ ] `check_dangerous_path` 单测覆盖:basename 精确匹配、segment 精确匹配、case-insensitive、`.claude/skills/` 子路径不命中、绝对/相对路径都处理
- [ ] WriteTool / EditTool 的 `check_permissions` 命中危险路径时返回 `behavior='ask', decision_reason={'type': 'safety_check'}` 单测全绿
- [ ] `auto_mode_gate` 在 dangerously mode 看到 safety_check 类 ask 后保留 ask(bypass-immune)的单测全绿
- [ ] `pytest tests/unit/agent/` 全绿

## 测试策略

纯后端,无前端:N/A

- **R1**: 新建 `test_dangerous_paths.py` → 红(模块不存在);实现 `dangerous_paths.py` → 绿
- **R2**: WriteTool / EditTool `check_permissions` 单测(含 bypass-immune 路径);扩展 `test_tool_check_permissions.py` → 红;实现两工具的 `check_permissions` → 绿
- **真实入口验证**: `pytest tests/unit/agent/platform/` 全绿;设计上 reviewer 旅程在 dangerously 模式下手动验收危险路径 ask + 正常路径 passthrough

UI 状态矩阵: N/A (纯后端 milestone)

## Roadpoints

### R1 — 新建 dangerous_paths.py + 单测(Red→Green)

- 步骤:
  1. 写 `tests/unit/agent/platform/tools/test_dangerous_paths.py` (C1: Red)
  2. 新建 `src/agent/platform/tools/dangerous_paths.py` 含清单 + 函数 (C2: Green)
  3. 补文档 + progress.md (C3)
- 验证: `pytest tests/unit/agent/platform/tools/test_dangerous_paths.py` 全绿

### R2 — WriteTool / EditTool check_permissions + bypass-immune 单测

- 步骤:
  1. 在 `tests/unit/agent/platform/tools/test_tool_check_permissions.py` 增加 WriteTool/EditTool check_permissions 用例(C1: Red)
  2. 给 WriteTool 和 EditTool 各加 `check_permissions` 方法(C2: Green)
  3. 补文档 + progress.md (C3)
- 验证: `pytest tests/unit/agent/platform/tools/` + `pytest tests/unit/agent/` 全绿

- **状态**: TODO

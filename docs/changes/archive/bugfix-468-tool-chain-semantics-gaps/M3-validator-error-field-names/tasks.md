# bugfix-468-M3: validator-error-field-names — Tasks

> 对齐: ../design.md v1

## 目标

让 `src/agent/core/tools/registry.py` 中 `_validate_args` / `_validate_value` 的 missing / unexpected / type 三类报错文案对齐 CC 模板，逐条列出具体字段名；`details` dict 保持原结构不变供程序消费。

## 退出标准

- [x] `pytest tests/unit/agent -k validate -q` 全绿
- [x] missing / unexpected / type 三类文案断言都包含字段名
- [x] details dict（missing / unknown / field / expected）结构保持不变
- [x] 全测试树相关套件全绿（特别注意其他包对旧文案的断言）
- [x] 真栈验证：诱导或显式触发一次带错参数名的 edit 调用，ToolResult 文本展示含字段名的 CC 风格报错

## 测试策略

- 被测行为（来自退出标准）：
  1. 单字段缺失时报错文本含字段名并走统一 CC 模板。
  2. 多字段缺失时每条缺失字段各占一行列名。
  3. 多余字段（additionalProperties=false）时报错文本含多余字段名。
  4. 类型错误时报错文本含字段名与期望/实际类型。
  5. `load_skills` 特例保留原有行为。
  6. `details` dict 保持原键（missing/unknown/field/expected）。
  7. `registry.execute` 调用路径触发的 ToolError message 同样呈现新格式。
- 已有测试在：无直接覆盖 `_validate_args/_validate_value` 文案的单元测试；`tests/integration/test_tools_registry_loader_integration.py` 有 loosely match 的 `missing required` 断言，需随新文案收紧。
- 落层/目录/marker：
  - 纯逻辑（validator）→ `tests/unit/test_tool_validation_errors.py`，marker：无
  - 集成（registry.execute 调用链）→ 扩展 `tests/integration/test_tools_registry_loader_integration.py`，marker：无
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真栈触发的错误 ToolResult 文本截图/命令输出，落 `evidence/` 目录。

## Roadpoints

### R1 — 对齐 validator 报错文案并补单元测试

- 步骤:
  1. 修改 `src/agent/core/tools/registry.py` 的 `_validate_args` / `_validate_value`，统一为 CC 模板多行文本。
  2. 保留 `load_skills` 特例与 `details` dict 不变。
  3. 新建 `tests/unit/test_tool_validation_errors.py`，覆盖 missing/unexpected/type 三类字段名列名 + details 结构 + load_skills 特例。
  4. 更新 `tests/integration/test_tools_registry_loader_integration.py` 中断言以匹配新文案。
- 验证:
  - `pytest tests/unit/test_tool_validation_errors.py -q` 全绿
  - `pytest tests/unit/agent -k validate -q` 全绿
  - `pytest tests/integration/test_tools_registry_loader_integration.py -q` 全绿
- 状态: DONE

### R2 — 全测试树回归 + 真栈验证

- 步骤:
  1. 跑 `pytest tests/unit tests/integration tests/contract -q` 确认无旧文案断言回归。
  2. 用 `scripts/e2e-up.sh` 起隔离栈备用；因模型自然触发参数错不可控，按 design 回退到显式 SDK 驱动：调用 `edit` 时传入错误参数名 `old_string`/`new_string`，捕获并记录 ToolResult 文本。
  3. `scripts/e2e-down.sh` 收尾。
- 验证:
  - 全测试树相关套件全绿
  - `evidence/demo_wrong_edit_params.txt` 含真栈级 CC 报错文本（字段名 `oldText`/`newText`）
- 状态: DONE

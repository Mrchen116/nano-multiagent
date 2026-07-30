# M61 - Codex阶段门控与工具时间线研究落盘（映射M50-M51-M53）

## Milestone Contract
- Milestone: `M61`
- Title: `Codex阶段门控与工具时间线研究落盘（映射M50-M51-M53）`
- Goal: 深挖 codex 在 `STREAMING/FINALIZING/FINALIZED` 阶段门控、tool timeline 聚合/orphan 隔离、summary 去重机制，并给 nano CLI 输出可执行迁移清单（映射 M50/M51/M53）与 managed CLI 观感验收脚本模板。
- Scope:
  - Allowed: `TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json`（仅通过脚本）
  - Forbidden: 任何 `src/**` 实现改动（含内核/API/CLI），以及手工编辑 `data/dev-tasks.json`
- Prevention Rules:
  - 文档型里程碑：不写实现代码，只做研究结论与规则落盘。
  - 锚点必须可定位到 codex 源码绝对路径。
  - 迁移清单必须可执行，按 M50/M51/M53 分配。
  - managed CLI 验收仅输出“模板命令+期望片段+判定标准”，不强制改代码。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `113 passed, 42 warnings`（2026-03-04）

## Roadpoints

### R1 阶段门控与渲染调度锚点深挖（STREAMING/FINALIZING/FINALIZED）
- Acceptance:
  - 明确 codex 阶段门控触发条件、状态切换与“何时停止/恢复状态线”。
  - 补齐 frame coalesce 与调度（commit tick / chunking）锚点，并抽取 nano 可迁移规则。
  - 输出对 M50 的执行清单（结构、优先级、风险）。
- Tests Plan:
  - unit/contract/integration/e2e: 不选（研究型里程碑，仅文档落盘）。
  - 原因：不改实现代码；门禁使用 baseline 命令做环境健康确认。
- Expected Tests:
  - `baseline gate`（复用上方全量命令）
- DoD:
  - PROGRESS 记录一轮完整研究结论（含锚点、决策、风险）。
  - C1/C2/C3 提交齐全（文档型执行）。
- Status: `DONE`

### R2 工具时间线聚合/orphan隔离与summary去重研究
- Acceptance:
  - 明确 codex 在 tool begin/end 聚合、orphan 隔离、summary 去重上的具体机制。
  - 输出 nano 对应的语义模型与去重策略（含 fallback 窗口与已播报集合策略）。
  - 形成对 M51/M53 的可执行迁移清单（步骤+风险+验收口径）。
- Tests Plan:
  - unit/contract/integration/e2e: 不选（研究型里程碑，仅文档落盘）。
  - 原因：不改实现代码；以源码锚点和规则可执行性为验收主证据。
- Expected Tests:
  - `baseline gate`（复用上方全量命令）
- DoD:
  - PROGRESS 追加第二轮研究记录，含“新问题 -> 新锚点 -> 新规则”链路。
  - C1/C2/C3 提交齐全（文档型执行）。
- Status: `DONE`

### R3 迁移总清单与managed CLI观感验收模板收口
- Acceptance:
  - 产出按 M50/M51/M53 分类的最终迁移清单（含任务粒度、先后关系、风险守护）。
  - 产出 managed CLI 观感验收脚本模板：命令、期望关键片段、判定标准、失败归因。
  - 提炼高价值可复用规则追加 LOGBOOK。
- Tests Plan:
  - unit/contract/integration/e2e: 不选（研究型里程碑，仅文档落盘）。
  - 原因：本路标交付物是规划模板与规则，不涉及行为变更。
- Expected Tests:
  - `baseline gate`（复用上方全量命令，作为最终收口健康检查）
- DoD:
  - TASKS/PROGRESS/LOGBOOK 完整更新并可直接支撑 M50/M51/M53 执行。
  - 分支 rebase/merge/push 与 dev_tasks M61=DONE 完成。
- Status: `DONE`

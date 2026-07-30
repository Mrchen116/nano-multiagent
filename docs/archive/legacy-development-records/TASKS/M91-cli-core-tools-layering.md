# M91 CLI 独立包提取 + core/tools 层级修正

## R1 零残留门禁补齐与迁移红测
- 状态：DONE
- Acceptance:
  - 以测试锁定 `nano_multiagent` legacy root 不可 import。
  - 以测试锁定 README/架构文档不再引用 legacy `nano_multiagent.*` 路径。
  - 以测试锁定 `src/coding_cli/` 作为独立 Python 包的 canonical 入口。
  - 以测试锁定 `core/tools/base.py` 与 `core/tools/registry.py` 为 canonical home。
- Tests Plan:
  - unit：补 `coding_cli`/`core.tools` canonical home 与 legacy root removal 断言；这是本 Roadpoint 的主测试层。
  - contract：补目录/文档 target-state 断言，覆盖零残留与架构边界。
  - integration：不选；本 Roadpoint 只锁定结构与导入边界，不涉及链路行为。
  - e2e：不选；结构迁移的失败信号由 unit/contract 足够覆盖。
- Expected Tests:
  - `tests/unit/test_apps_coding_cli_location.py`
  - `tests/unit/test_core_tools_location.py`
  - `tests/unit/test_core_agent_location.py`
  - `tests/contract/test_multi_product_architecture_acceptance.py`
- DoD:
  - `PYTHONPATH=src pytest -q` 全绿
  - 完成 C1/C2/C3
  - PROGRESS 记录红测范围、证据与回滚点

## R2 提取 core.tools 抽象并让 platform.tools 仅保留实现
- 状态：DONE
- Acceptance:
  - `src/agent/core/tools/base.py` 提供 Tool 接口与 ToolContext canonical 定义。
  - `src/agent/core/tools/registry.py` 提供 ToolRegistry canonical 定义。
  - `src/agent/platform/tools/` 保留实现与安全/加载逻辑，但依赖 `agent.core.tools` 抽象。
  - 现有 runtime/bootstrap/tool builtin 测试通过，行为不变。
- Tests Plan:
  - unit：补 canonical module 身份与 platform 依赖 core 的断言。
  - contract：复用 target-state path 断言确认新路径存在。
  - integration：依赖现有全量 pytest 覆盖 runtime/bootstrap/tool wiring，不额外单开新链路测试。
  - e2e：不选；本 Roadpoint 的入口行为由现有全量门禁已覆盖。
- Expected Tests:
  - `tests/unit/test_core_tools_location.py`
  - `tests/contract/test_multi_product_architecture_acceptance.py`
  - 全量 `pytest -q`
- DoD:
  - `PYTHONPATH=src pytest -q` 全绿
  - 完成 C1/C2/C3
  - PROGRESS 记录抽象下沉方案、兼容处理与回滚点

## R3 提取顶层 coding_cli 独立包并清除 legacy nano_multiagent 残留
- 状态：DONE（纠偏后）
- Acceptance:
  - `src/coding_cli/` 作为独立 Python 包存在，CLI 代码直接位于该目录。
  - `src/coding_cli/coding_cli/` 不存在，不保留兼容壳层。
  - 现有 CLI canonical import 指向 `coding_cli.*`，不再指向 `coding_cli.coding_cli.*`。
  - README/SPEC/CLI SPEC 示例改到新路径，不再引用 `nano_multiagent.*`。
  - `src/nano_multiagent/` legacy root 被移除，相关测试与导入全部转向目标态。
- Tests Plan:
  - unit：补 CLI canonical surface、legacy root removal 与旧模块不可 import 断言，并锁定 `coding_cli.commands`/`coding_cli.main`/`coding_cli.managed_server` 为 canonical module。
  - contract：补 target-state file tree 与文档 snippet 断言，强制 `src/coding_cli/` 直接承载 CLI 结构。
  - integration：依赖既有 CLI/HTTP 集成测试验证迁移后入口仍可工作。
  - e2e：依赖既有 CLI e2e/contract 门禁，不额外新增新入口脚本测试。
- Expected Tests:
  - `tests/unit/test_apps_coding_cli_location.py`
  - `tests/unit/test_cli_main.py`
  - `tests/unit/test_cli_refactor_boundaries.py`
  - `tests/contract/test_multi_product_architecture_acceptance.py`
  - 全量 `pytest -q`
- DoD:
  - `PYTHONPATH=src pytest -q` 全绿
  - 完成 C1/C2/C3
  - PROGRESS 记录为何打回、如何纠偏、证据与回滚点

## R3.1 M91 纠偏：按 CodingCLI-SPEC §6 消除二级嵌套
- 状态：DONE
- Acceptance:
  - 先将 canonical path 测试改为以 `src/coding_cli/*` 为准。
  - `main.py`、`commands.py`、`client.py`、`managed_server.py`、`input/`、`events/`、`render/`、`runtime/` 直接位于 `src/coding_cli/`。
  - 全仓不再出现 `coding_cli.coding_cli.*` 引用。
  - `agent.core.tools` / `platform.tools` 既有正确实现保持不变。
- Tests Plan:
  - unit：先改位置测试与 CLI 边界测试的 canonical module 断言。
  - contract：修正 target-tree 断言到 `src/coding_cli/`，防止未来回流到二级嵌套。
  - integration：复用现有 CLI integration 回归验证 HTTP 主链路未受影响。
  - e2e：复用现有 managed CLI e2e。
- Expected Tests:
  - `tests/unit/test_apps_coding_cli_location.py`
  - `tests/contract/test_multi_product_architecture_acceptance.py`
  - 全量 `pytest -q`
- DoD:
  - `src/coding_cli/coding_cli/` 不存在
  - `PYTHONPATH=src pytest -q` 全绿
  - PROGRESS 写清打回原因、修正路径、证据与稳定提交

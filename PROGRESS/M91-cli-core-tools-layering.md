# M91 CLI 独立包提取 + core/tools 层级修正

## Milestone Plan
- Context:
  - 当前分支已完成 M90 的大部分重命名，但仍残留 `src/nano_multiagent/`、README legacy 路径与 `platform.tools` canonical 抽象。
  - M91 目标要求同时完成 `coding_cli` 独立包提取与 `core/tools` 抽象下沉，并保持全量测试通过。
- Decision:
  - 将里程碑拆为 R1 红测锁边界、R2 下沉 core.tools、R3 提取顶层 coding_cli 并清理 legacy root 三个 Roadpoint。
- Rationale:
  - 先锁结构边界，再迁移抽象与包路径，能降低批量替换误伤与零残留回归风险。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M91 && PYTHONPATH=src pytest -q`
  - Entry: 基线存在 3 个失败，分别指向 README legacy path 与 `nano_multiagent` root 尚未移除。
- Rollback:
  - `7995160 docs(R90.3): 补齐重命名证据与收尾计划`
- Commits: C1=, C2=, C3=
- Next:
  - 先提交 TASKS/PROGRESS 计划骨架，再进入 R1 红测。

### R1 零残留门禁补齐与迁移红测
- Context:
  - 需要先把 M91 的目标态固定成测试，不然 core.tools 下沉与 legacy root 删除很容易出现“代码迁了但门禁没锁住”的漂移。
- Decision:
  - 新增 `tests/unit/test_core_tools_location.py`，并扩展多产品架构 contract test，要求 `core/tools/base.py` 与 `core/tools/registry.py` 存在且进入 target tree。
- Rationale:
  - 先红能明确后续实现的验收口径，也能防止 README/目录结构/导入面出现零残留漏网。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M91 && PYTHONPATH=src pytest -q tests/unit/test_core_tools_location.py tests/contract/test_multi_product_architecture_acceptance.py tests/unit/test_core_agent_location.py`
  - Entry: 初次执行报 `ModuleNotFoundError: No module named 'agent.core.tools'`，并继续暴露 README legacy path 与 `nano_multiagent` root 可 import。
- Rollback:
  - `6ad782b docs(M91): 初始化 Roadpoints 计划`
- Commits: C1=`44685fc`, C2=`42d3913`, C3=`8d1f2b7`
- Next:
  - 在 R2 里把 Tool/Registry 抽象真正下沉到 core，同时保持 platform 仅保留实现层。

### R2 提取 core.tools 抽象并让 platform.tools 仅保留实现
- Context:
  - 现有 Tool/ToolContext/ToolRegistry 仍定义在 `platform.tools`，与内核设计 SPEC §2/§6 的 core 层归属冲突。
  - 同时 `core` 不能直接 import `platform`，否则会触发 core-no-platform contract。
- Decision:
  - 新建 `src/agent/core/tools/{base,registry,safety_types}.py` 作为 canonical home。
  - `platform.tools.base/registry` 改成兼容 facade；builtins/loader 改为依赖 `agent.core.tools`。
  - 通过 `set_tool_safety_factory` 与 `set_tool_safety_config_factory` 注入 platform safety，实现 core 不直接 import platform。
- Rationale:
  - 这样满足“接口归 core、实现留 platform”的层级约束，同时保留现有 tool safety/builtin 行为不变。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M91 && PYTHONPATH=src pytest -q tests/contract/test_core_no_platform_imports.py tests/integration/test_task_runtime_wiring_integration.py tests/unit/test_platform_tools_location.py tests/contract/test_tools_bash_contract.py tests/unit/test_tools_builtins.py tests/integration/test_cli_http_flow_integration.py`
  - Entry: 中途修复了两类回归：一是 `core/tools/base.py` 误 import `agent.platform.tools.safety` 触发 forbidden snippet；二是 task 校验文案与默认 safety config 注入不兼容原有 bash/read 合约测试。
- Rollback:
  - `44685fc test(R1): 锁定 core.tools 与零残留目标态（先红）`
- Commits: C1=`44685fc`, C2=`42d3913`, C3=`8d1f2b7`
- Next:
  - 进入 R3，删除 `src/nano_multiagent/` legacy root，并把 README/CLI 入口文案全部切到 `coding_cli.coding_cli` 与 `agent.*`。

### R3 提取顶层 coding_cli 独立包并清除 legacy nano_multiagent 残留
- Context:
  - M90 后仍保留整棵 `src/nano_multiagent/` 旧根包；README 也仍使用 `nano_multiagent.platform` 与 `nano_multiagent.apps.coding_cli` 示例。
- Decision:
  - 删除 `src/nano_multiagent/` 全量 legacy root。
  - 保持 `src/coding_cli/coding_cli/` 作为 CLI 独立包入口，README 全部改到 `agent.platform.http_api.app` 与 `coding_cli.coding_cli.*`。
  - 同步更新平台位置测试，使其接受 platform tool contract 作为 facade、canonical home 位于 core。
- Rationale:
  - 彻底移除 legacy root 才能满足零残留门禁与 `find_spec("nano_multiagent") is None` 的验收要求。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M91 && PYTHONPATH=src pytest -q`
  - Entry: 最终全量测试 `613 passed, 4 skipped`；重点迁移测试 `tests/unit/test_apps_coding_cli_location.py`、`tests/unit/test_core_agent_location.py`、`tests/unit/test_core_tools_location.py`、`tests/contract/test_multi_product_architecture_acceptance.py` 全部通过。
- Rollback:
  - `42d3913 feat(R2): 下沉 core.tools 抽象并保留 platform 实现（全绿）`
- Commits: C1=`44685fc`, C2=`984c31b`, C3=`8d1f2b7`
- Next:
  - 进入 Milestone 集成：rebase main、复跑全量测试、合并回 main、更新 `data/dev-tasks.json`。

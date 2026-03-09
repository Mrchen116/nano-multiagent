# M82 - 多产品架构重构九期：core 归位与共享抽象收口

## Milestone 概述
- milestone_id: M82
- title: 多产品架构重构九期：core 归位与共享抽象收口
- goal: 把真正属于共享执行内核的实现逐步收口到 core 层，明确 agent/session/tools/hooks/skills/llm 之间的共享抽象边界，并避免产品/平台默认值回流进 core。
- execution_mode: parallel（复用既有隔离 worktree 执行）
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M82`
- branch: `milestone/M82`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- test_command: `python3 -m pytest -q tests/contract/test_core_events_contract.py tests/contract/test_core_types_contract.py tests/contract/test_core_no_platform_imports.py tests/unit/test_core_errors.py tests/unit/test_core_ids.py tests/unit/test_core_session_location.py tests/unit/test_core_hooks_location.py tests/unit/test_core_skills_location.py tests/unit/test_core_llm_location.py tests/unit/test_session_manager.py tests/unit/test_session_entries.py tests/unit/test_hooks_runner.py tests/unit/test_agent_runtime_hooks.py tests/unit/test_agent_prompting.py tests/unit/test_llm_model_registry.py`

## 约束与边界
- 允许改动：`src/nano_multiagent/core/**`、与 shared-kernel 归位直接相关的 legacy `src/nano_multiagent/session/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/skills/**`、`src/nano_multiagent/llm/**` compatibility shim、少量 `agent/platform/products/tests` 调用点对齐、`TASKS/PROGRESS` 记录。
- 禁止改动：产品默认配置/目录语义；platform/products/apps 行为策略；HTTP API/CLI 入口协议；与 M82 无关的大规模目录重排；破坏 legacy import 兼容。
- 预防规则：
  1. 仅迁移“共享抽象/共享内核”模块到 `core`，不把产品或 platform 默认值带入 `core`。
  2. 优先采用“复制实现到 core canonical 路径 + 旧路径 re-export shim”的渐进方式，保持回滚友好。
  3. 必须新增 location/contract tests 证明 canonical ownership 与 legacy 兼容导出同时成立。
  4. `tests/contract/test_core_no_platform_imports.py` 必须继续为 core-oriented 边界护栏，并扩展防止 `core` 反向依赖 `platform/products/apps`。
  5. 已知基线：`tests/contract/test_core_types_contract.py::test_turn_result_contract_fields_are_stable` 当前因 `TurnResult.usage` 额外字段失败；若本 milestone 未安全解决，则保持为已知基线，不隐藏其它新失败。

---

## R1 - session 共享模型/事件/管理器归位到 core/session

### Acceptance
1. `src/nano_multiagent/core/session/` 下存在 `models.py`、`entries.py`、`manager.py` 作为 session shared-kernel canonical home。
2. `nano_multiagent.core.session` 导出的 `Session`、`SessionEntry*`、`SessionManager` 来自 `core/session`，而不是 legacy `session/*`。
3. `nano_multiagent.session.models`、`entries`、`manager` 继续可导入，但仅作为 compatibility shim 指向 canonical core 实现。
4. runtime/platform/products 对 session shared abstractions 的使用对齐到 canonical core 路径且行为不变。
5. 最终门禁全绿，除已知 `TurnResult.usage` 基线外不新增失败。

### Tests Plan
- unit: 选用。新增 location/import identity 测试锁定 canonical module ownership；复用 `test_session_manager.py`、`test_session_entries.py` 保证行为未变。
- contract: 选用扩展后的 core layering guard，确保 `core/session` 不回依赖 `platform/products/apps`。
- integration: 不单独新增。本 Roadpoint 以共享内核归位为主，现有 unit/contract 足够覆盖回归面。
- e2e: 不单独新增。本次不改真实入口协议。

### Expected Tests
- `tests/unit/test_core_session_location.py`
- `tests/unit/test_session_manager.py`
- `tests/unit/test_session_entries.py`
- `tests/contract/test_core_no_platform_imports.py`
- 阶段 gate：`python3 -m pytest -q tests/contract/test_core_events_contract.py tests/contract/test_core_types_contract.py tests/contract/test_core_no_platform_imports.py tests/unit/test_core_errors.py tests/unit/test_core_ids.py tests/unit/test_core_session_location.py tests/unit/test_session_manager.py tests/unit/test_session_entries.py tests/unit/test_agent_runtime_hooks.py tests/unit/test_llm_model_registry.py`
- 最终门禁：同上 `test_command`

### DoD
- 先制造 canonical session ownership 的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿（允许保留已知 `TurnResult.usage` 基线）。
- `PROGRESS/M82-core-归位与共享抽象收口.md` 记录决策、证据、回滚点与提交哈希。

### 状态：DONE

### 完成说明
- Red：新增 `tests/unit/test_core_session_location.py`，先触发 `ModuleNotFoundError: No module named 'nano_multiagent.core.session'`，明确证明 canonical core session home 尚未建立。
- Green：新增 `src/nano_multiagent/core/session/{__init__,models,entries,store,manager}.py` 作为 shared-kernel canonical home；旧 `session.models`、`session.entries`、`session.manager` 改为 compatibility shim；`platform.persistence.session.base` 也反转为 core store contract 的兼容导出，避免 `core.session.manager` 继续反向依赖 platform。
- Caller alignment：`agent/runtime`、`agent/compaction/*`、`runs/registry`、`platform/http_api/routes/session`、`products/base`、`session/service` 等共享调用点已切到 `nano_multiagent.core.session.*`。
- Gate：`python3 -m pytest -q tests/contract/test_core_events_contract.py tests/contract/test_core_types_contract.py tests/contract/test_core_no_platform_imports.py tests/unit/test_core_errors.py tests/unit/test_core_ids.py tests/unit/test_core_session_location.py tests/unit/test_session_manager.py tests/unit/test_session_entries.py tests/unit/test_agent_runtime_hooks.py tests/unit/test_llm_model_registry.py` 结果为 `25 passed, 1 failed`；唯一失败仍是已知基线 `test_turn_result_contract_fields_are_stable`（`TurnResult.usage` 额外字段）。
- 提交序列：C1=`4ae2bbd`, C2=`926095e`, C3=`61c357c`。

---

## R2 - hooks/skills 共享抽象归位到 core/hooks 与 core/skills

### Acceptance
1. `src/nano_multiagent/core/hooks/` 下存在 `context.py`、`types.py`、`registry.py`、`runner.py` 作为 hook shared-kernel canonical home。
2. `src/nano_multiagent/core/skills/` 下存在 `registry.py`、`formatter.py` 作为 skill shared abstractions canonical home；`skills/workspace.py` 继续留在 legacy/产品装配边界。
3. `nano_multiagent.hooks.{context,types,registry,runner}` 与 `nano_multiagent.skills.{registry,formatter}` 保留兼容导出。
4. agent/platform 等调用点对齐到 canonical core 路径，但 `platform/hooks/loader.py`、`skills/workspace.py` 这类装配/发现逻辑不被错误吸入 core。
5. 最终门禁全绿，除已知 `TurnResult.usage` 基线外不新增失败。

### Tests Plan
- unit: 选用。新增 core hooks/skills location tests，并复用 `test_hooks_runner.py`、`test_agent_runtime_hooks.py`、`test_agent_prompting.py` 验证行为与 prompt wiring。
- contract: 选用扩展后的 core layering guard，确保 `core/hooks`、`core/skills` 不反向依赖 `platform/products/apps`。
- integration: 不单独新增。本次不改 loader/HTTP 等入口协议，仅对 shared abstractions 归位。
- e2e: 不单独新增。本次无独立真实入口变更。

### Expected Tests
- `tests/unit/test_core_hooks_location.py`
- `tests/unit/test_core_skills_location.py`
- `tests/unit/test_hooks_runner.py`
- `tests/unit/test_agent_runtime_hooks.py`
- `tests/unit/test_agent_prompting.py`
- `tests/contract/test_core_no_platform_imports.py`
- 最终门禁：同上 `test_command`

### DoD
- 先制造 canonical hooks/skills ownership 的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿（允许保留已知 `TurnResult.usage` 基线）。
- `PROGRESS/M82-core-归位与共享抽象收口.md` 记录决策、证据、回滚点与提交哈希。

### 状态：DONE

### 完成说明
- Red：新增 `tests/unit/test_core_hooks_location.py` 与 `tests/unit/test_core_skills_location.py`，先触发 `ModuleNotFoundError: No module named 'nano_multiagent.core.hooks'` / `No module named 'nano_multiagent.core.skills'`，证明 canonical core hooks/skills home 尚未建立。
- Green：新增 `src/nano_multiagent/core/hooks/{__init__,context,types,registry,runner}.py` 与 `src/nano_multiagent/core/skills/{__init__,registry,formatter}.py` 作为 shared-kernel canonical home；旧 `hooks.context/types/registry/runner` 与 `skills.registry/formatter` 改为 compatibility shim。
- Caller alignment：`agent/loop`、`agent/runtime`、`agent/prompting`、`tools/registry`、`runs/registry`、`platform/http_api/*`、`platform/hooks/loader.py`、`platform/tools/loader.py`、`platform/bootstrap.py`、`products/base.py`、`hooks/__init__.py`、`skills/__init__.py` 等共享调用点已切到 `nano_multiagent.core.hooks.*` / `nano_multiagent.core.skills.*`；`skills/workspace.py` 继续留在 legacy 装配边界。
- Focused Green：`PYTHONPATH=src python -m pytest tests/unit/test_core_hooks_location.py tests/unit/test_core_skills_location.py tests/unit/test_hooks_runner.py tests/unit/test_agent_runtime_hooks.py tests/unit/test_agent_prompting.py` 结果为 `20 passed`。
- 提交序列：C1=`16bdf41`, C2=`78b570e`, C3=`<pending>`。

---

## R3 - llm 共享抽象归位到 core/llm 并补强 core layering contract

### Acceptance
1. `src/nano_multiagent/core/llm/` 下存在 `interfaces.py`、`model_registry.py`、`factory.py` 作为 LLM shared abstractions canonical home。
2. `nano_multiagent.llm.{interfaces,model_registry,factory}` 保留 compatibility shim，调用方无需行为改写即可继续工作。
3. `core/__init__.py` 与 `core` 下的 canonical exports 能清晰暴露 session/hooks/skills/llm shared-kernel surface。
4. contract tests 明确防止 `core/**` 反向依赖 `platform/products/apps`，同时 location tests 证明 canonical ownership 已切到 core。
5. 最终门禁全绿，且已知 `TurnResult.usage` 失败状态被明确记录为“保持基线”或“已安全解决”。

### Tests Plan
- unit: 选用。新增 core llm location tests，并复用 `test_llm_model_registry.py` 验证 LLM metadata 行为不变。
- contract: 选用。扩展 `test_core_no_platform_imports.py` 覆盖 `src/nano_multiagent/core/**`，防止 core 反向依赖 `platform/products/apps`。
- integration: 不单独新增。本次不更改 provider 网络协议，仅移动 shared abstractions 的 canonical home。
- e2e: 不单独新增。本次不涉及新的入口流转。

### Expected Tests
- `tests/unit/test_core_llm_location.py`
- `tests/unit/test_llm_model_registry.py`
- `tests/contract/test_core_no_platform_imports.py`
- 最终门禁：同上 `test_command`

### DoD
- 先制造 canonical llm ownership / core layering guard 的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿（允许保留已知 `TurnResult.usage` 基线）。
- `PROGRESS/M82-core-归位与共享抽象收口.md` 记录决策、证据、回滚点与提交哈希。

### 状态：TODO

---

## 结果目标
- `core` 不再只包含 ids/errors/events/types，而是具备更完整的 shared-kernel canonical homes（至少覆盖 session/hooks/skills/llm 高优先级共享模块）。
- legacy `session/hooks/skills/llm` 共享路径降为 compatibility shim，旧导入继续可用。
- location tests + unit tests + contract guard 共同证明 core ownership 已收口且未回流到 `platform/products/apps`。

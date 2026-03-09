# M82 Progress - core 归位与共享抽象收口

## 启动记录
- Milestone: `M82` / 多产品架构重构九期：core 归位与共享抽象收口
- execution_mode: `parallel`（复用隔离 worktree，按并行执行处理）
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M82`
- branch: `milestone/M82`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- gate command: `python3 -m pytest -q tests/contract/test_core_events_contract.py tests/contract/test_core_types_contract.py tests/contract/test_core_no_platform_imports.py tests/unit/test_core_errors.py tests/unit/test_core_ids.py tests/unit/test_core_session_location.py tests/unit/test_core_hooks_location.py tests/unit/test_core_skills_location.py tests/unit/test_core_llm_location.py tests/unit/test_session_manager.py tests/unit/test_session_entries.py tests/unit/test_hooks_runner.py tests/unit/test_agent_runtime_hooks.py tests/unit/test_agent_prompting.py tests/unit/test_llm_model_registry.py`
- allowed_scope: `src/nano_multiagent/core/**`、与 shared-kernel 归位直接相关的 legacy `src/nano_multiagent/session/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/skills/**`、`src/nano_multiagent/llm/**` compatibility shim、少量 `agent/platform/products/tests` 调用点对齐、以及本 milestone 文档记录。
- forbidden_scope: 不改产品默认配置/目录语义；不改 platform/products/apps 行为策略；不改 HTTP API/CLI 入口协议；不做与 M82 无关的大规模目录重排；不破坏 legacy import 兼容。
- prevention_rules:
  - 仅迁移 shared-kernel 抽象到 `core`，不把产品或 platform 默认值带入 `core`。
  - 优先采用“复制实现到 core canonical 路径 + 旧路径 re-export shim”的渐进方式，保持回滚友好。
  - 新增 location/contract tests 同时证明 canonical ownership 与 legacy compat。
  - `tests/contract/test_core_no_platform_imports.py` 必须扩展为真正的 core layering guard，防止 `core` 反向依赖 `platform/products/apps`。
  - 已知基线：`tests/contract/test_core_types_contract.py::test_turn_result_contract_fields_are_stable` 当前因 `TurnResult.usage` 额外字段失败；除非本 milestone 安全解决，否则保持基线并显式记录。

## 基线
- 复用既有 `milestone/M82` worktree；后续需确认 `data/dev-tasks.json` 仍指向主仓共享板 `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`。
- 启动前已按要求阅读 `LOGBOOK.md` 与 `COMMENTING_GUIDE.md`，后续代码遵守 public API docstring 与“注释写意图不复述代码”的规则。
- baseline gate（用户提供的种子命令）结果：`23 passed, 1 failed`。
- 失败项：`tests/contract/test_core_types_contract.py::test_turn_result_contract_fields_are_stable`，原因为 `TurnResult` 额外包含 `usage` 字段；当前记为 pre-existing baseline，M82 不会隐藏它。

---

### R1 session 共享模型/事件/管理器归位到 core/session
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

### R2 hooks/skills 共享抽象归位到 core/hooks 与 core/skills
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

### R3 llm 共享抽象归位到 core/llm 并补强 core layering contract
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

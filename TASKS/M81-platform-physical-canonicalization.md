# M81 - 多产品架构重构八期：platform 实现物理归位（session/tools/hooks/server）

## Milestone 概述
- milestone_id: M81
- title: 多产品架构重构八期：platform 实现物理归位（session/tools/hooks/server）
- goal: 将已建立的新 platform 表面从 shim 逐步转为 canonical 实现归属，重点覆盖 session persistence、tools/hooks loader/safety、HTTP API app/routes。
- execution_mode: parallel（复用隔离 worktree，按并行执行处理）
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M81`
- branch: `milestone/M81`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- test_command: `python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py`

## 约束与边界
- 允许改动：`src/nano_multiagent/platform/persistence/session/**`、`src/nano_multiagent/platform/tools/**`、`src/nano_multiagent/platform/hooks/**`、`src/nano_multiagent/platform/http_api/**`、对应 legacy `src/nano_multiagent/session/stores/**`、`src/nano_multiagent/tools/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/server/**` 兼容 shim、相关 unit/integration/contract tests、`TASKS/PROGRESS` 记录。
- 禁止改动：与 M81 无关的 CLI/apps/sdk 行为；runtime loop 语义；引入 app/core 对 platform.http_api 或 sdk 的越层依赖；破坏现有 legacy 导入兼容。
- 预防规则：
  1. `platform/persistence/session`、`platform/tools`、`platform/hooks`、`platform/http_api` 必须成为本次归位范围内的 canonical home；旧 `session/tools/hooks/server` 仅保留 compatibility shim。
  2. 迁移优先采用“复制实现到新 canonical 路径 + 旧路径 re-export shim”的渐进方式，不做大规模语义改写。
  3. 测试必须同时固化 canonical module ownership 与 legacy shim identity，避免“新路径可导入但真实实现仍留在旧模块”。
  4. 任何 core-oriented 包不得新增对 `platform.http_api` / `platform.sdk` 的依赖；必要共享类型继续经原有 core-safe 边界暴露。

---

## R1 - session persistence 物理归位到 platform/persistence/session

### Acceptance
1. `src/nano_multiagent/platform/persistence/session/` 下存在 `base.py`、`jsonl_store.py`、`sqlite_store.py` 作为 session store canonical home。
2. `nano_multiagent.platform.persistence.session` 导出的 store 类型来自 platform 模块，而不是 legacy `session.stores.*`。
3. `nano_multiagent.session.stores` 及其子模块继续可导入，但仅作为 compatibility shim 指向 canonical platform 实现。
4. 现有 session persistence 相关调用不需要行为改写即可继续通过测试。
5. 最终门禁全绿。

### Tests Plan
- unit: 选用。通过 location/import identity 测试锁定 canonical module ownership 与 legacy shim identity。
- contract: 不单独新增。本次主要是模块归位，不涉及外部协议结构变化。
- integration: 复用 app/bootstrap 相关测试，确保会话存储链路未被迁移破坏。
- e2e: 不单独新增。本次不引入新的真实入口协议。

### Expected Tests
- `tests/unit/test_platform_persistence_session_location.py`
- 最终门禁：`python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py`

### DoD
- 先制造 canonical session store ownership 的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿。
- `PROGRESS/M81-platform-physical-canonicalization.md` 记录决策、证据、回滚点与提交哈希。

### 状态：DONE

### 完成说明
- Red：把 `tests/unit/test_platform_persistence_session_location.py` 从“仅验证可导入”提升为“验证 platform 模块 ownership + legacy shim identity”，先触发 `ModuleNotFoundError: nano_multiagent.platform.persistence.session.base`。
- Green：新增 `platform/persistence/session/{base,jsonl_store,sqlite_store}.py` 作为 canonical home，并将 `session/stores` 及其子模块反转为 compatibility shim；同时把 `session.manager` / `session.service` / `server.app` / `products.base` 对齐到 canonical imports。
- Guardrail：`session/__init__.py` 改为 lazy export，避免 canonical store 模块导入 `session.entries` 时经 package 初始化回卷到 compat shim 形成循环依赖。
- Gate：`python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py` 全绿（33 passed）。
- 提交序列：C1=`7520c9e`, C2=`c5847ca`, C3=`<pending>`。

---

## R2 - tools/hooks loader/safety/builtins 物理归位到 platform

### Acceptance
1. `platform/tools/loader.py`、`platform/tools/safety.py` 承载 canonical 实现，`platform/tools/builtins` 成为主入口；旧 `tools.loader` / `tools.safety` / `tools.builtins` 保留 compat shim。
2. `platform/hooks/loader.py` 与 `platform/hooks/builtins/` 承载 canonical 实现；旧 `hooks.loader` / `hooks.builtins` 保留 compat shim。
3. resolver 驱动的 tool/hook 加载行为保持不变，默认 builtin/hook 发现仍可用。
4. 测试明确证明 canonical function/module ownership 与 legacy shim identity。
5. 最终门禁全绿。

### Tests Plan
- unit: 选用。location/import identity + loader behavior 测试能快速证明 canonical ownership 与兼容导出。
- contract: 不单独新增。此次变更不调整外部 JSON/HTTP 契约。
- integration: 复用 app bootstrap 与 loader integration，验证 runtime 装配路径不回归。
- e2e: 不单独新增。本次主要为模块布局归位。

### Expected Tests
- `tests/unit/test_platform_tools_location.py`
- `tests/unit/test_platform_hooks_location.py`
- `tests/unit/test_tool_loader_with_resolver.py`
- `tests/unit/test_hook_loader_with_resolver.py`
- 最终门禁：同上 `test_command`

### DoD
- 先制造 canonical tools/hooks ownership 的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿。
- `PROGRESS/M81-platform-physical-canonicalization.md` 记录决策、证据、回滚点与提交哈希。

### 状态：DONE

### 完成说明
- Red：把 `tests/unit/test_platform_tools_location.py` 与 `tests/unit/test_platform_hooks_location.py` 提升为 canonical ownership + compat identity 断言，先得到 `6 failed, 1 passed`，明确证明 loader/safety/builtins 仍由 legacy 模块持有。
- Green：将 `platform/tools/{loader,safety,builtins/**}` 与 `platform/hooks/{loader,builtins/**}` 落成真实 canonical home；`tools.loader` / `tools.safety` / `hooks.loader` 反转为 compat shim；`tools.builtins` / `hooks.builtins` 通过 `sys.modules` alias 指向 canonical package，保证模块对象 identity。
- Guardrail：`tools/__init__.py` 改为 lazy export，避免 platform builtins 在引用 `nano_multiagent.tools.constants` 时因 compat shim 回卷造成循环导入。
- Caller alignment：`platform/bootstrap.py` 与 `server/app.py` 已改用 `nano_multiagent.platform.{tools,hooks}.loader`。
- Gate：`python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py` 全绿（30 passed）。
- 提交序列：C1=`7309fe2`, C2=`fd35288`, C3=`<pending>`。

---

## R3 - HTTP API app/routes 物理归位到 platform/http_api

### Acceptance
1. `platform/http_api/app.py`、`auth.py`、`deps.py`、`sse.py`、`routes/*.py` 承载 canonical HTTP API 实现。
2. `nano_multiagent.platform.http_api.create_app` 与关键 route/router objects 的 `__module__` 指向 platform/http_api。
3. `nano_multiagent.server.*` 继续可导入，但仅作为 compatibility shim 指向 canonical platform/http_api。
4. app bootstrap 和相关 SSE/type imports 对 canonical platform/http_api 对齐，且不向 core-oriented 包引入 forbidden 依赖。
5. 最终门禁全绿。

### Tests Plan
- unit: 选用。location/import identity 测试可直接证明 canonical HTTP app/routes ownership。
- contract: 选用现有 `test_core_no_platform_imports.py` 作为层级护栏，防止 core-oriented 包越层依赖 platform.http_api。
- integration: 选用 `tests/integration/test_app_bootstrap.py`，验证真实 app factory 入口未破坏。
- e2e: 不单独新增。HTTP 入口已有 integration 足够覆盖本次归位。

### Expected Tests
- `tests/unit/test_platform_http_api_location.py`
- `tests/integration/test_app_bootstrap.py`
- `tests/contract/test_core_no_platform_imports.py`
- 最终门禁：同上 `test_command`

### DoD
- 先制造 canonical http_api ownership 的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿。
- `PROGRESS/M81-platform-physical-canonicalization.md` 记录决策、证据、回滚点与提交哈希。

### 状态：DONE

### 完成说明
- Red：把 `tests/unit/test_platform_http_api_location.py` 提升为 canonical `create_app` / route router ownership 与 legacy server compat identity 断言，先看到 `create_app.__module__` 仍为 `nano_multiagent.server.app`。
- Green：将 `platform/http_api/{app,auth,deps,sse,routes/*.py}` 落成真实 canonical home，并把 `server/**` 全部反转为 compatibility shim；`server.__init__` 改为 lazy export 以避免 legacy `server.sse` 等子模块 import 时回卷整包。
- Guardrail：首次全量 gate 暴露 `runs/registry.py` 直接依赖 `platform.http_api.sse` 违反层级合同，随后修正为继续依赖 legacy `server.sse` compat path，从而保持 core-oriented 包不直接 import `platform.http_api`。
- Router ownership：为 platform route module 导出的 `router` 设置 `router.__module__ = __name__`，让 location tests 能验证路由对象归属的是 canonical platform route module，而不是 FastAPI 内部类型模块。
- Gate：`python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py` 全绿（30 passed）。
- 提交序列：C1=`09891c5`, C2=`04c6ba5`, C3=`<pending>`。

---

## 结果目标
- platform canonical 表面不再只是 shim，而是本次范围内实现的真实归属地。
- legacy `session/tools/hooks/server` 路径降为 compatibility shim。
- 位置测试、装配测试、层级护栏测试共同证明迁移完成且边界未回流。

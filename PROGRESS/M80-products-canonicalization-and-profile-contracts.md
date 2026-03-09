# M80 Progress - products 物理归位与 Profile 合同补齐

## 启动记录
- Milestone: `M80` / 多产品架构重构七期：products 物理归位与 Profile 合同补齐
- execution_mode: `parallel`（复用隔离 worktree，按并行执行处理）
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M80`
- branch: `milestone/M80`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- gate command: `python3 -m pytest -q tests/unit/test_product_profile.py tests/unit/test_product_profiles.py tests/contract/test_product_profile_contract.py tests/integration/test_bootstrap_integration.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py`
- allowed_scope: `src/nano_multiagent/products/**`、`src/nano_multiagent/platform/product.py`、`src/nano_multiagent/platform/products/**`、`src/nano_multiagent/platform/bootstrap.py`、`src/nano_multiagent/platform/config/resolver.py`、`src/nano_multiagent/server/app.py`、`src/nano_multiagent/session/service.py`、相关 tests，与本 milestone 文档记录。
- forbidden_scope: 不改与 M80 无关的 CLI/apps/sdk 行为；不改 runtime loop 语义；不破坏现有 `platform.product(s)` 兼容导入。
- prevention_rules:
  - `nano_multiagent.products.*` 成为 canonical source of truth，`platform.products` 只保留 compatibility shim。
  - `ProductProfile` 新字段保持兼容默认值，不新增破坏性构造要求。
  - bootstrap / server / session 只向 canonical contract 收口，不引入第二套产品装配路径。
  - 测试必须同时覆盖 canonical surface 与 legacy shim。

## 基线
- 复用既有 `milestone/M80` worktree，`data/dev-tasks.json` 已确认是指向主仓共享板 `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json` 的 symlink。
- 启动前已按要求阅读 `LOGBOOK.md` 与 `COMMENTING_GUIDE.md`，后续代码遵守 public API docstring 与“注释写意图不复述代码”的规则。
- baseline gate 已在 worktree 绝对路径下通过一次：`34 passed, 16 warnings`。

---

### R1 canonical products 包结构与 ProductProfile 合同
- Context: `ProductProfile`/`ResolvedProductConfig` 与具体产品 profile 仍物理位于 `platform.product(s)`；M80 目标要求 canonical `nano_multiagent.products` 成为真实产品层，并补齐文档里尚未落地的 profile 字段。
- Decision: 新增 `src/nano_multiagent/products/base.py` 作为 canonical contract home，并为 `local_coding` / `personal_assistant` 建立 `profile.py + prompts/toolsets/hooks/defaults` 骨架；`platform.product(s)` 全部改为 re-export shim。
- Rationale: 先把“产品定义归属地”与“平台装配层”分离，再通过兼容 shim 维持旧导入可用，是最小且可回滚的物理归位方式；新增字段只做合同声明与默认值，不提前扩展 runtime 语义。
- Evidence:
  - Tests:
    - Red: `python3 -m pytest -q tests/unit/test_product_profile.py tests/unit/test_product_profiles.py tests/contract/test_product_profile_contract.py tests/integration/test_bootstrap_integration.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py` -> 6 个 `ModuleNotFoundError: No module named 'nano_multiagent.products'`
    - Broad Green: `python3 -m pytest -q tests/unit/test_product_profile.py tests/unit/test_product_profiles.py tests/unit/test_local_coding_profile.py tests/unit/test_personal_assistant_profile.py tests/unit/test_platform_bootstrap.py tests/unit/test_config_resolver.py tests/unit/test_session_service_with_profile.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/unit/test_skills_workspace_with_resolver.py tests/unit/test_app_factory_with_profile.py tests/contract/test_product_profile_contract.py tests/integration/test_bootstrap_integration.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py` -> `95 passed`
    - Gate: `python3 -m pytest -q tests/unit/test_product_profile.py tests/unit/test_product_profiles.py tests/contract/test_product_profile_contract.py tests/integration/test_bootstrap_integration.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py` -> `38 passed`
  - Entry:
    - canonical contract home: `src/nano_multiagent/products/base.py`
    - canonical product profiles: `src/nano_multiagent/products/local_coding/profile.py`、`src/nano_multiagent/products/personal_assistant/profile.py`
    - legacy `platform.product(s)` imports now resolve to the same objects via compatibility shims
  - Boundary: `ProductProfile` 新增字段仅补合同与产品默认元数据，未把 memory/heartbeat 行为强行接入 runtime。
- Rollback: 若需重做，回退到计划提交 `17d9cb5` 或测试提交 `e9dd06b`，再从 canonical import Red 重来。
- Commits: C1=`e9dd06b`, C2=`0542a93`, C3=`<pending>`
- Next: 用独立 Roadpoint 收口 app factory/session path 仍未使用产品 profile 的剩余接线缺口。

### R2 bootstrap/server/session canonical 收口与 compat shims
- Context: R1 已让 bootstrap/config resolver/type imports 指向 canonical contract，但 `create_app(product_profile=...)` 仍未把 profile 传给 `SessionService`，导致产品级 session DB 路径在 app factory 入口上失效。
- Decision: 为 app factory 增加一条 profile-session-path Red 测试；实现上仅让 `create_app` 透传 `product_profile` 给 `SessionService`，并在 `SessionService` 保持“只有 profile 声明了 `global_config_home` 时才启用产品路径，否则继续 legacy fallback”的兼容规则。
- Rationale: 这样能把产品路径解析真正贯通到 HTTP app 入口，同时不破坏已有“最小 profile 也能 create_app”的兼容契约。
- Evidence:
  - Tests:
    - Red: `python3 -m pytest -q tests/unit/test_app_factory_with_profile.py` -> `test_create_app_with_profile_uses_profile_session_store_path` 失败，实际路径落在 `.nano_multiagent/sessions.sqlite3`
    - Focused Green: `python3 -m pytest -q tests/unit/test_app_factory_with_profile.py` -> `7 passed`
    - Gate: `python3 -m pytest -q tests/unit/test_product_profile.py tests/unit/test_product_profiles.py tests/contract/test_product_profile_contract.py tests/integration/test_bootstrap_integration.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py` -> `38 passed`
  - Entry:
    - `src/nano_multiagent/server/app.py` 现已把 `product_profile` 透传给 `SessionService`
    - `src/nano_multiagent/session/service.py` 现已在 profile 缺少 `global_config_home` 时保留 legacy fallback，避免 minimal profile 回归
  - Boundary: 未改变 `session_store` 显式覆盖优先级；也未改变 runtime/tool/hook bootstrap 路径。
- Rollback: 若需重做，回退到 `0542a93` 或测试提交 `32f276a`，再从 app factory session path Red 重来。
- Commits: C1=`32f276a`, C2=`2825132`, C3=`<pending>`
- Next: 回写 milestone 文档提交，随后执行 rebase/main merge、更新 dev-tasks、清理 worktree。

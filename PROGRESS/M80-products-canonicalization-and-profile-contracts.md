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
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: <pending>
  - Entry: <pending>
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R2 bootstrap/server/session canonical 收口与 compat shims
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: <pending>
  - Entry: <pending>
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

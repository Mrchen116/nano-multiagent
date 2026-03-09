# M80 - 多产品架构重构七期：products 物理归位与 Profile 合同补齐

## Milestone 概述
- milestone_id: M80
- title: 多产品架构重构七期：products 物理归位与 Profile 合同补齐
- goal: 把产品定义从 `platform/products` 收口到 canonical `products` 层，补齐 `ProductProfile` 缺失字段与产品包结构，使 `local_coding` / `personal_assistant` 成为真正的产品层。
- execution_mode: parallel（复用隔离 worktree，按并行执行处理）
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M80`
- branch: `milestone/M80`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- test_command: `python3 -m pytest -q tests/unit/test_product_profile.py tests/unit/test_product_profiles.py tests/contract/test_product_profile_contract.py tests/integration/test_bootstrap_integration.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py`

## 约束与边界
- 允许改动：`src/nano_multiagent/products/**`、`src/nano_multiagent/platform/product.py`、`src/nano_multiagent/platform/products/**`、`src/nano_multiagent/platform/bootstrap.py`、`src/nano_multiagent/platform/config/resolver.py`、`src/nano_multiagent/server/app.py`、`src/nano_multiagent/session/service.py`、相关 unit/contract/integration tests、`TASKS/PROGRESS` 记录。
- 禁止改动：与 M80 无关的 CLI/apps/sdk 行为；runtime loop 语义；无关测试基线；破坏既有 `platform.products` / `platform.product` 兼容导入。
- 预防规则：
  1. `nano_multiagent.products.*` 必须成为 canonical source of truth，`platform.products` 仅保留 compatibility shim。
  2. `ProductProfile` 新字段必须提供兼容默认值，避免对现有 bootstrap/runtime 产生产品分支或破坏性构造要求。
  3. bootstrap / server / session 只能向 canonical contract 对齐，不得为迁移引入第二套装配路径。
  4. 回归测试必须同时覆盖 canonical 导入表面与 legacy shim，避免“新路径可用、旧路径断裂”。

---

## R1 - 建立 canonical products 包结构与 ProductProfile 合同

### Acceptance
1. 存在 `src/nano_multiagent/products/base.py`，并提供 `ProductProfile` / `ResolvedProductConfig` canonical 导出。
2. 存在 `src/nano_multiagent/products/local_coding/profile.py` 与 `src/nano_multiagent/products/personal_assistant/profile.py`，且 profile 实例可从 canonical 路径导入。
3. `ProductProfile` 补齐文档要求的剩余关键字段，至少覆盖 `optional_tool_ids`、`memory_layout`、`heartbeat_layout`，并保持兼容默认值。
4. canonical 产品包至少具备 `__init__` 与默认能力骨架，不再把产品定义唯一放在 `platform/products`。
5. Red/Green 通过针对 canonical contract 的 unit/contract 测试证明，且最终门禁仍全绿。

### Tests Plan
- unit: 选用。验证 dataclass 字段、canonical profile import、默认值和产品骨架导出，反馈快且能精确锁定合同漂移。
- contract: 选用。约束 `ProductProfile` / `ResolvedProductConfig` 的字段稳定性与 canonical home。
- integration: 选用最小子集。验证 canonical profile 可被 bootstrap 消费。
- e2e: 不单独新增。M80 关注模块归位与导入合同，不引入新的真实进程入口协议。

### Expected Tests
- `tests/unit/test_product_profile.py`
- `tests/unit/test_product_profiles.py`
- `tests/contract/test_product_profile_contract.py`
- `tests/integration/test_bootstrap_integration.py`
- 最终门禁：`python3 -m pytest -q tests/unit/test_product_profile.py tests/unit/test_product_profiles.py tests/contract/test_product_profile_contract.py tests/integration/test_bootstrap_integration.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py`

### DoD
- 先制造一组证明 canonical products surface / 新字段合同缺失的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿。
- `PROGRESS/M80-products-canonicalization-and-profile-contracts.md` 记录决策、证据、回滚点与提交哈希。

### 状态：TODO

---

## R2 - 收口 bootstrap/server/session 到 canonical imports，并保留 platform compat shims

### Acceptance
1. `platform.product` 继续可用，但只作为 canonical `products.base` 的 compatibility shim。
2. `platform.products.local_coding` / `platform.products.personal_assistant` 继续可用，但其 profile 来源于 canonical `products/*/profile.py`。
3. bootstrap、config resolver、session service、server app 至少在类型或导入层面向 canonical products contract 对齐，不要求引入行为变化。
4. 现有 bootstrap / personal_assistant / server integration tests 继续通过，并新增 compat regression 覆盖旧导入路径。
5. 最终门禁全绿，且 `platform.products` 不再是产品定义真实归属地。

### Tests Plan
- unit: 选用。验证 compat shim identity、canonical import identity、server/bootstrap 无额外产品分支。
- contract: 选用。验证 legacy imports 仍指向 canonical dataclass/profile 对象。
- integration: 选用。复用 bootstrap/server integration 测试验证真实装配链路未破坏。
- e2e: 不单独新增。已有 integration 足以覆盖本次“导入/装配归位但行为兼容”的目标。

### Expected Tests
- `tests/unit/test_product_profiles.py`
- `tests/unit/test_product_profile.py`
- `tests/contract/test_product_profile_contract.py`
- `tests/integration/test_bootstrap_integration.py`
- `tests/integration/test_personal_assistant_bootstrap_integration.py`
- `tests/integration/test_personal_assistant_server_integration.py`
- 最终门禁：`python3 -m pytest -q tests/unit/test_product_profile.py tests/unit/test_product_profiles.py tests/contract/test_product_profile_contract.py tests/integration/test_bootstrap_integration.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py`

### DoD
- 先制造一组证明 compat shim / canonical import identity 尚未收口的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿。
- `PROGRESS/M80-products-canonicalization-and-profile-contracts.md` 记录决策、证据、回滚点与提交哈希。

### 状态：TODO

---

## 结果（待完成）
- canonical `nano_multiagent.products` 将成为产品层真实归属地。
- legacy `platform.product(s)` 将仅保留兼容 shim。
- `ProductProfile` 合同将补齐剩余关键字段并由测试固化。

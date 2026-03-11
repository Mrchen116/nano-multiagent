# M92 Product 目录结构对齐

## R92.1 产品目录目标态与 profile/hook 默认声明对齐
- Status: TODO
- Acceptance:
  - `products/local_coding/` 包含 `tools/`、`hooks/`、`skills/` 子目录
  - `products/personal_assistant/` 包含 `tools/`、`hooks/`、`skills/` 子目录
  - 现有 `hooks.py` 迁移为 `hooks/` 模块入口，`profile.py` 仍能声明默认 hook 模块
  - 产品包导出与既有 import 路径保持兼容
- Tests Plan:
  - unit: 需要；覆盖产品 profile 与目录存在性
  - contract: 需要；冻结 products 目录目标态与 hooks 模块约定
  - integration: 暂不单独新增；由后续 bootstrap/loader 覆盖
  - e2e: 不需要；该 Roadpoint 主要验证目录与装配声明
- Expected Tests:
  - `tests/unit/test_local_coding_profile.py`
  - `tests/unit/test_personal_assistant_profile.py`
  - `tests/contract/test_product_profile_contract.py`
- DoD:
  - 目标测试先红后绿
  - `PYTHONPATH=src pytest -q` 全绿
  - C1/C2/C3 齐全
  - PROGRESS 记录决策/证据/回滚点/提交哈希

## R92.2 四层 tools/hooks/skills 加载路径可验证
- Status: TODO
- Acceptance:
  - tools 加载可验证“内核内置 → 产品默认 → 用户全局 → 工作区”顺序/覆盖
  - hooks 加载可验证“内核内置 → 产品默认 → 用户全局 → 工作区”顺序/覆盖
  - skills 搜索可验证“产品默认 → 用户全局 → 工作区”，并保留 compat 根最低优先级
  - bootstrap 以产品目录作为默认 roots，而非散落硬编码
- Tests Plan:
  - unit: 需要；覆盖 resolver/loader/discovery 的分层与覆盖行为
  - contract: 需要；冻结四层目标态关键断言
  - integration: 需要；验证 bootstrap 后 registries/skills 可见集合
  - e2e: 暂不新增；全量 pytest 作为入口回归
- Expected Tests:
  - `tests/unit/test_tool_loader_with_resolver.py`
  - `tests/unit/test_hook_loader_with_resolver.py`
  - `tests/unit/test_skills_workspace_with_resolver.py`
  - `tests/integration/test_bootstrap_integration.py`
  - `tests/contract/test_multi_product_architecture_acceptance.py`
- DoD:
  - 目标测试先红后绿
  - `PYTHONPATH=src pytest -q` 全绿
  - C1/C2/C3 齐全
  - PROGRESS 记录决策/证据/回滚点/提交哈希

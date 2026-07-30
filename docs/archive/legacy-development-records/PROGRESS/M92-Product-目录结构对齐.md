# M92 Product 目录结构对齐

## Milestone Notes
- 先对齐 `SPEC.md` 与 `docs/内核设计SPEC.md` 中 `products/<product>/tools|hooks|skills` 目标态，再收敛加载器。
- 测试避免写死 hooks 总量，优先断言关键模块/来源/路径存在，遵守 `LOGBOOK.md` 规则。
- 涉及 legacy 路径/负向断言时，改动后需复查 contract tests，避免批量替换误伤。

### R92.1 产品目录目标态与 profile/hook 默认声明对齐
- Context: `docs/内核设计SPEC.md` 要求两个产品目录都具备 `tools/ hooks/ skills/`，而当前仅有 `hooks.py` 扁平文件，缺少目标态目录与包入口。
- Decision: 为 `local_coding` 与 `personal_assistant` 新建 `tools/ hooks/ skills/` 子目录，并将 `hooks.py` 直接迁移为 `hooks/__init__.py`，保持 `profile.py` 仍通过 `from .hooks import DEFAULT_HOOK_MODULES` 读取默认声明。
- Rationale: 直接迁移模块入口比额外保留 shim 更符合 SPEC 目标态，同时不会改变现有 profile import 语义。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M92 && PYTHONPATH=src pytest -q tests/unit/test_local_coding_profile.py tests/unit/test_personal_assistant_profile.py tests/contract/test_product_profile_contract.py`
  - Entry: 两个产品目录均存在 `tools/ hooks/ skills/`，且相关 profile/contract 测试 `29 passed`。
- Rollback: `9f839c1`
- Commits: C1=`9f839c1`, C2=`aa228a1`, C3=<pending>
- Next: 继续让 loader/bootstrap 能显式验证产品默认层在四层加载中的位置与覆盖关系。

### R92.2 四层 tools/hooks/skills 加载路径可验证
- Context: 现有 resolver 只覆盖 builtins 与用户层，产品目录虽然存在，但 loader/bootstrap 并未将 `products/<product>/tools|hooks|skills` 纳入默认搜索路径，也不支持高优先级覆盖低优先级同名项。
- Decision: 为 tools loader 增加 `product_tool_dir` 与 replace 语义；为 hooks loader 增加 `product_hook_dir` 与跨层同文件名覆盖；为 skills discovery 增加 `product_skill_root`；bootstrap 统一从 `src/agent/products/<product>/` 派生三类产品默认 roots 并装配 `skill_registry`。
- Rationale: 将产品默认层接入 bootstrap 才能满足“四层加载”要求，且集中在 loader/bootstrap 改动可避免 runtime 层分散硬编码。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M92 && PYTHONPATH=src pytest -q`
  - Entry: 全量门禁 `628 passed, 4 skipped`；R92.2 目标测试 `28 passed`，并验证 README/legacy root 清理后 contract/location 测试转绿。
- Rollback: `1d3854b`
- Commits: C1=`1d3854b`, C2=`f6911f1`, C3=<pending>
- Next: 无；Milestone Exit Criteria 已满足。

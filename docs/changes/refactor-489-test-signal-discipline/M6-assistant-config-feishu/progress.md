# refactor-489-M6 — Progress

## Baseline

- Context: M6 只清理/合并指定 assistant config、capability 与 Feishu 测试，不改产品行为或产品代码。
- Decision: 以 current gateway specs、M1 测试处置协议和现有可运行替代保护为判断依据，不为全仓造台账。
- Evidence:
  - Tests: M6 指定 35 文件，253 passed；替代保护 42 passed。
  - Entry: N/A；零产品行为 delta，本 milestone 的 entry evidence 是 current seam 自动化保护仍可运行。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: current contract/integration alternatives 均通过；本 milestone 不新增 E2E。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A

## R1 — 配置、capability 与 prompt 测试收敛

- Context: 旧测试把 heartbeat/cron 的迁移终态、PromptSection 退役签名、提示词禁句与 capability dict 的每个 key 分拆为永久契约，并重复 builtin skill 与 unattended capability 断言。
- Decision: 删除 4 个迁移/私有实现文件和重复 capability 文件；将两个 builtin skill 文件合为公共安装/discovery seam；communication context 收敛为 direct/group/mention protocol 三项；group store 与 foreground/unattended capability 各保留两项行为测试。
- Rationale: capability wire、PromptSlots 装配已有 contract/integration owner；M6 只保留消费者输入输出和用户文件不覆盖等独立风险，避免内部表示变化造成无产品回归的红灯。
- Evidence:
  - Tests: R1 当前测试 + 替代保护 38 passed；ruff check 与 `git diff --check` 通过。
  - Entry: 公共 builtin skill 安装后经 node/agent capabilities、`Kernel.list_skills` 与 prompt preview 均能发现 `feishu-doc`；foreground/unattended 创建路径得到相同 capability 投影。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `test_capability_payload_contract.py` 与 `test_prompt_sections_golden.py` 17 passed，证明删除的重复 capability/prompt 断言已有当前替代。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回退本 roadpoint commit 可恢复原测试树，不影响产品代码或数据。
- Commits: 本 roadpoint commit（最终哈希在 R4 回填）。
- Next: R2。

## Promotion Candidates

None.

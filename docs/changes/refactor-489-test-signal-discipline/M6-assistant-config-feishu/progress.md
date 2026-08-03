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
- Commits: `0c307f89b`
- Next: R2。

## R2 — Feishu adapter 与 provider client 测试收敛

- Context: root Feishu tests 同时保留 current adapter/provider 风险与旧 standalone YAML、`_build_channel_registry`、SDK 私有成员、精确重试次数和重复 wrapper 调用契约。
- Decision: 删除旧 standalone config/registry 与独立 ack 重复文件；adapter 测试按入站规范化、owner 绑定、目标映射和 reaction 生命周期合并；client 测试收敛到 provider request/response、错误分类、interactive/history adapter；群历史按 catch-up 顺序、last-bot boundary 和权限降级保留。
- Rationale: current external channel 由 managed manifest/ChannelManager 拥有，旧 YAML 不再是契约；Feishu provider 的真实风险是稳定身份、可见 mention、错误显式、资源回收和群上下文，而不是某次 SDK wrapper 的调用次数或私有成员存在。
- Evidence:
  - Tests: root Feishu current tests、worker runtime 与 managed alternatives 共 71 passed；ruff check 与 `git diff --check` 通过。
  - Entry: Feishu adapter 从 provider event 产出稳定 external identity/agent route；DM/group 出站映射到 open_id/chat_id；群触发在历史补齐失败时仍投递当前消息。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `test_channel_bootstrap.py` 与 `test_channel_reconcile.py` 5 passed，证明 managed channel 当前替代可运行；本 milestone 不新增 live Feishu E2E。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回退本 roadpoint commit 可恢复原测试树，不影响产品代码或 channel 数据。
- Commits: 本 roadpoint commit（最终哈希在 R4 回填）。
- Next: R3。

## Promotion Candidates

None.

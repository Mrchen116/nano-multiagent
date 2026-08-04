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
- Commits: `071810bb7`
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
- Commits: `71c7da438`
- Next: R3。

## R3 — 权限、安全与 web_search 测试收敛

- Context: permission tests 混有历史修复叙事、私有 WS listen 调用、M7 heartbeat origin 和重复 handler 用例；approval card 固定具体元素/英语措辞；web_search unit tests 运行真实网络并重复同一 provider 选择与错误通道。
- Decision: permission pipeline 收敛到 IM request/resolved、无 IM anchor 的 external request 与 external resolved 三条 seam，并删除已由 `test_permission_decision_loop.py` 覆盖的 handler 文件；Feishu card 只保留 owner gate、first-wins、deny reason 与敏感值不泄漏；web_search 保留用户状态、provider fail-loud/zero-results、SearXNG 归一化及运行时选择，删除真网络检查。
- Rationale: 权限审批的长期风险是未经 owner 决策、重复决策或泄漏工具参数；搜索的长期风险是 provider 失败被伪装为空结果、选择错误或用户看不到错误。card 布局文案、transport 私有步骤和互联网可用性不应由 unit CI 固定。
- Evidence:
  - Tests: 权限/安全/diagnostics/web_search 与 permission 替代共 78 passed；ruff check 与 `git diff --check` 通过。
  - Entry: external permission 在无 IM message anchor 时仍投递 Feishu surface；owner 首次决策后重复点击不再提交；card 不含 command/path/token 值；web_search 明确区分 provider failure 与零结果。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `test_permission_decision_loop.py` 14 passed，保留 IM→Kernel decision 与 first-wins 返回语义；本 milestone 不新增 live 外部依赖。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回退本 roadpoint commit 可恢复原测试树，不影响产品权限状态或 secret。
- Commits: `9224241b1`
- Next: R4 全切片复核。

## R4 — 全切片与替代保护复核

- Context: 三个实施 roadpoint 完成后，需要确认删除没有留下 capability、managed channel、权限或群聊保护缺口，并量化测试资产变化。
- Decision: 复跑全部 M6 文件与六组 current 替代保护；对最终 26 个 M6 文件跑 ruff，执行 docs integrity 与 diff 检查。M6 从 35 个文件/253 tests/6387 行收敛为 26 个文件/138 tests/3308 行：删除 9 个文件、115 个测试和 3079 行测试代码。
- Rationale: 数量变化只描述处置结果；完成依据是 180 个 current M6 + 替代保护全绿，以及每类真实风险仍有最低层 owner，而非删测比例。
- Evidence:
  - Tests: rebase 到最新 `origin/unit/refactor-489`（含 M5）后，M6 当前 138 tests + capability/prompt/managed-channel/permission/group-routing alternatives 42 tests，共 180 passed；仅有 lark SDK 自身 2 条 DeprecationWarning。
  - Entry: current Agent config/capability、Feishu 入站/出站/群历史/诊断/审批与 web_search provider seam 均由现有自动化直接经过；无产品代码或 spec delta。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A；本 milestone 为测试资产重构，未修改用户入口；current cross-boundary alternatives 42 passed。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
  - Quality: rebase 后最终 M6 26 文件 ruff 全绿；`scripts/docs_check.py` 通过（200 maintained Markdown sources、65 required routes）；`git diff --check` 通过。
- Rollback: 分别回退 `071810bb7`、`71c7da438`、`9224241b1` 可恢复对应测试簇；无产品数据迁移。
- Commits: `ef245eb7a` + 本次 post-rebase evidence sync commit。
- Next: rebase 到最新 `origin/unit/refactor-489`，复跑门禁并合入 unit。

## Promotion Candidates

None.

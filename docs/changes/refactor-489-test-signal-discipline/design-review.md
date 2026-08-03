# Design Review: refactor-489

## Round 1

### Metadata

- reviewer: `/root/refactor489_design_reviewer`
- review_mode: `full`
- mode_reason: `R1`；按 Gate 2 要求完整复核全部承重原子与四个架构进攻角度。
- started_at: `2026-08-03T10:55:08+08:00`
- completed_at: `2026-08-03T10:58:50+08:00`
- duration: `3m 42s`

### Verdict

Issues Found — 3 CRITICAL / 1 WARNING

不能进入实施：当前设计不能完成首文档要求的全仓测试资产审视，且无法让未来 worker 可靠地产出决策 1 所要求的处置表。

### 历史问题闭环

无历史 Round；本轮为首次独立完整审查。

### Coverage

- 输入：`motivation.md`、`design.md`、`docs/specs/README.md`、`docs/development/testing.md`、`docs/development/change-workflow.md`、`docs/development/evidence.md`、`docs/development/e2e-critical-paths.md`、`.claude/skills/change-impl-worker/SKILL.md` 与其 `assets/tasks.md`。
- 现状核对：CI 入口、测试目录拓扑、contract/import-boundary、提示词 golden、E2E shell 与其 wrapper、Vitest 的源码/布局断言，以及代表性的真实入口测试。
- 架构进攻：归属、删除测试、模块深度、治本性均已逐项执行。
- 本轮未运行测试；此为 design-only Gate 2 审查，证据为 current 文档和源码/测试的只读追踪。

### 核实台账

#### 现状断言

| 原子 | 结论与直接证据 |
|---|---|
| Python 的 unit/integration/contract 同时有真实保护和历史/实现细节断言 | 成立。`tests/integration/test_channel_bootstrap.py:29-108` 经 IM HTTP + WebSocket 验证 bind/bootstrap 的可观察结果；`tests/contract/test_core_no_platform_imports.py:32-45` 只扫描真实 import 行，保护架构依赖；相反，`tests/integration/test_e2e_down_script.py:10-42` 将 `sleep 0.2` 的次数和 `kill -9` 文本作为永久断言。 |
| 前端 Vitest 混有真实交互和源码/文件布局检查 | 成立。`src/IM/frontend/src/features/chat/components/message-pane.test.tsx:1940-1969` 驱动拖放并检查用户可见 attachment chip；`src/IM/frontend/src/app/distribution-contract.test.ts:1-8` 和 `src/IM/frontend/src/app/index-html.test.ts:1-8` 分别导入 `.gitignore`/`index.html` 原文并断言文本。 |
| `e2e` 脚本及其测试兼有真实隔离风险与实现细节检查 | 成立。`scripts/e2e-down.sh:29-82` 实际负责 Gateway→IM 的关停次序和 worktree runtime 清理；`tests/unit/personal_assistant/test_gateway_im_resilience_e2e_wrapper.py:133-239` 同时含真实 prepare-only 运行与对 shell 源码字符串的分支断言，`tests/integration/test_e2e_down_script.py:40-42` 是轮询实现细节。 |
| current 测试规范/worker 已有行为优先原则，但未要求受影响存量测试的处置结论 | 成立。`docs/development/testing.md:9-23` 要求路径变化时删/改旧测试，却只要求新建测试说明理由；`change-impl-worker/SKILL.md:203-249` 仍只描述新增测试的规划，未要求 keep/rewrite-merge/delete 台账。 |
| 最低层、真实运行时和不以删除掩盖 flaky 是既有约束 | 成立。`docs/development/testing.md:31-46` 定义分层和跨层不重复，`testing.md:48-75` 规定重依赖收集与 strict xfail；`docs/development/e2e-critical-paths.md:5-23` 明确关键路径须经真 Gateway/IM 进程。 |
| 本 unit 不改变产品当前行为，package spec 无 delta | 成立。`docs/specs/README.md:5-11` 的 canonical package 仅为 kernel/IM/gateway/cli；设计限定只改测试、开发规范与 worker 交付过程，未引入产品/SDK/运维契约变化。 |
| 既有的 import-boundary、产品入口和真实脚本运行可复用 | 成立。`tests/contract/test_core_no_platform_imports.py:1-45` 避开注释/文档假阳性；`tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py:1-100` 只通过真进程后的 `/im/v1/nodes` 状态判断；`scripts/e2e-resilience.sh:202-236` 执行 IM 重启和启动顺序两条故障旅程。 |
| 历史 migration/golden/target-state 断言是候选而非预先删除清单 | 成立。`tests/integration/test_kernel_skeleton_reproduces_golden.py:1-13` 明确保存的是迁移期间的 byte-for-byte golden；`tests/contract/test_multi_product_architecture.py:19-205` 同时固定 target tree、已删除路径和文档文本。是否保留必须按当前 seam 判断，不能由历史标签直接决定。 |

#### 决策

| 原子 | 结论与直接证据 |
|---|---|
| 决策 1：受影响测试必须有 keep/rewrite-merge/delete 处置 | **不成立，见 R1-C2、R1-C3。** 意图与 motivation 的 worker 场景一致，但真实写入接口是 `assets/tasks.md`，设计的 M1 scope 未包含该模板，且 M1 与使用该协议的 M2-M5 被安排并行。 |
| 决策 2：同一风险在最低层断言，高层只验跨 seam 连接 | 成立且有 spec 驱动。它与 `testing.md:42-46` 完全一致，并保留高层连接验证；没有把“最低层”误写成删除所有 E2E。 |
| 决策 3：按独立测试域并行而不预置逐项候选 | **不成立，见 R1-C1、R1-C3、R1-W1。** 不预置候选本身合理，但列出的五个域既未覆盖首文档的全仓范围，也没有把协议 producer 与 consumer 排成可执行的依赖图。 |

#### 首文档约束

| 原子 | 结论与直接证据 |
|---|---|
| Q1：删除、改写或合并均以真实回归保护为完成标准，不以删除数量为目标 | 部分覆盖。决策 1 的删除前提和决策 2 已覆盖原则；但 R1-C1 使大量受影响的 Python/IM/Gateway 测试没有任何 milestone 审视，不能宣称完成“清理 + 重构”。 |
| Q2：worker 在路径/边界变化时明确记录处置及依据 | 未覆盖，见 R1-C2、R1-C3。当前真实模板仍不要求记录，平行 worker 也会在新协议可用前创建计划。 |
| Q3：覆盖 Python、Vitest、测试辅助脚本和 CI 质量检查 | 未覆盖，见 R1-C1。 |
| Requirement「无产品回归的维护改动不被历史噪声阻塞」 | 部分覆盖。M2-M5 指向若干典型噪声，但遗漏面会让其它历史断言继续阻塞维护。 |
| Requirement「真实风险有最低层保护，完整门禁的失败可执行」及两个 Scenario | 部分覆盖。决策 1/2 有清楚的替代保护前提；R1-C1 没有给全部 Python/CI surfaces 指定审视 owner，不能保证完整门禁均已达到该状态。 |
| Requirement「worker 持续维护测试资产」Scenario | 未覆盖，见 R1-C2、R1-C3。 |
| 非目标：不改变产品功能 | 覆盖。所有 milestone 都落在测试、文档、skill 或测试配置，且无 product source 变更。 |
| 回滚：按风险簇独立回退、不能以删除掩盖 flaky | 覆盖。风险与回退段要求保留/替代保护，并明确不稳定测试先稳定、降层或调整 lane。 |

#### Delta-spec

| 原子 | 结论与直接证据 |
|---|---|
| kernel: no spec delta | 成立。设计没有 kernel 对外行为或 SDK 变化；`docs/specs/README.md:6-7` 表明这是 package current contract，而本 unit 只改测试/开发流程。 |
| im: no spec delta | 成立。M5 只清理 Vitest 和配置，不改变 IM 用户行为；`docs/specs/README.md:8` 是 IM 行为的 canonical entry。 |
| gateway: no spec delta | 成立。M4 保留/重构真实 Gateway-IM 测试与脚本，但未改变运维结果或 Gateway 合约；`docs/specs/README.md:9` 是该 package 的 canonical entry。 |
| cli: no spec delta | 成立。当前 milestone 没有 CLI 产品行为改动；`docs/specs/README.md:10` 是 CLI 行为的 canonical entry。 |

#### Milestones

| 原子 | 结论与直接证据 |
|---|---|
| M1 test-discipline | **不成立，见 R1-C2、R1-C3。** 规范 owner 选择正确，但实际 worker plan 模板 `.claude/skills/change-impl-worker/assets/tasks.md:21-29` 遗漏在范围外；并行组也不保证其先于计划创建。 |
| M2 python-structural-tests | **不成立，见 R1-C1、R1-C3。** `tests/contract/` 是一块有效独立域（40 个文件），但不是“全部 Python 测试”所需的范围；它还在协议 producer M1 完成前被安排并行。 |
| M3 agent-prompt-tests | **不成立，见 R1-C1、R1-C3。** `tests/unit/agent/` 有 51 个文件，但提示词相关测试还在 `tests/unit/personal_assistant/`，例如 `test_prompt_section_feature_flags.py`；其它 unit/integration/e2e 面也无 owner。 |
| M4 operational-test-reliability | **不成立，见 R1-C1、R1-C3、R1-W1。** 指向 shell/runtime 风险正确，但范围没有精确锚定所有相关 Python wrapper/helper；更无法承接整个余下 Python suite、`scripts/docs_check.py` 和 CI 配置。 |
| M5 frontend-test-signal | 成立。其文件域和现有 CI frontend 入口一致，`.github/workflows/ci.yml:39-60` 只运行 frontend 下的 `npm run test`；退出标准同时保留交互、状态和接口 seam。 |

### 架构进攻

| 角度 | 发现 |
|---|---|
| 归属 | 处置协议应由 `docs/development/testing.md` 作规范 owner、由 `change-impl-worker` 的实际 plan template 承载。当前只放在 skill 正文/文档而未把模板纳入 M1，造成规范与唯一交付入口脱节（R1-C2）。 |
| 该不该存在 | 不需要新测试框架、registry、wrapper 或逐项预置删除清单；以现有 seam 和风险表决策足够，删除测试通过。 |
| 深还是浅 | 风险—既有测试—处置—替代保护—验证的表格把下游需要回答的关键问题集中起来，属于有价值的薄流程补强而非假想抽象；前提是它真的成为 worker 创建任务的模板（R1-C2）。 |
| 治本还是补丁 | “按风险而非删测数量”、替代保护先可运行、禁止用删除掩盖 flaky 都是治本选择。但只扫少数域会把同一低信号问题留在 284 个 `tests/unit/` 非 agent 文件、22 个未归类 integration 文件、19 个 E2E 文件和 75 个 `tests/im_service/` 文件中，形成局部清债而非全仓治理（R1-C1）。 |

### Issues

- [R1-C1][CRITICAL] [决策 3 / Milestones M2-M4]: 五个 milestone 没有覆盖首文档 Q3 所要求的“所有已提交自动化测试与测试质量门禁”。现有范围只显式包含 40 个 `tests/contract/`、51 个 `tests/unit/agent/`、少量 prompt/integration 和 E2E shell、Vitest；而仓库还有 284 个 `tests/unit/` 非 agent 文件、22 个不属于 prompt/e2e-down 的 integration 文件、19 个 `tests/e2e/` 文件及 75 个 `tests/im_service/` 文件。代表性未归属 real seam 是 `tests/integration/test_channel_bootstrap.py:29-108`，未归属 current policy/CI helper 是 `tests/unit/test_docs_check.py` 对应的 `scripts/docs_check.py:756-980`；`.github/workflows/ci.yml:27-37` 也没有 milestone owner。**不改会使 worker 只能清理被列出的局部，剩余历史断言或重复保护仍可阻断 CI，Q1/Q3 和完整门禁 Scenario 无法验收。**

- [R1-C2][CRITICAL] [决策 1 / 接口与数据流 / M1]: 新增处置表被宣称为唯一交付接口，但 M1 范围漏掉 `change-impl-worker` 真正复制的 `.claude/skills/change-impl-worker/assets/tasks.md`。`SKILL.md:176-199` 明确要求从这个 asset 创建每个 milestone 的 `tasks.md`，而 asset 现有测试策略只有被测行为、已有测试、新建理由、层级、依赖和临时证据（`assets/tasks.md:21-29`），没有设计要求的 keep/rewrite-merge/delete 表。**不改会让未来 worker 即使读到新规范也从缺表的模板开始，处置记录不可稳定地产生，verifier 无从逐项核对 Q2 的长期要求。**

- [R1-C3][CRITICAL] [决策 1、决策 3 / Milestones]: M1 与 M2-M5 都是依赖 `—`、并行组 `A`，但 M2-M5 按决策 1 必须在 `tasks.md` 填写 M1 才建立的长期处置协议。并行 worker 会从各自建立时的 unit tree 复制模板并提交计划；M1 的文档/asset 变更不会回写已创建的计划。**不改会让本 unit 的主要实施 worker 先天绕过新协议，或迫使 orchestrator 临场改派/补计划，违反“两个 worker 也能无歧义实施”的设计要求并让 Gate 2 后的执行拓扑失真。**

- [R1-W1][WARNING] [Milestone M4]: “其 Python 测试与关键路径 wrapper”不是可执行的无交集文件范围。实际相关测试横跨 `tests/integration/test_e2e_down_script.py:10-42`、`tests/unit/test_e2e_catalog.py:54-64`、`tests/unit/personal_assistant/test_gateway_im_resilience_e2e_wrapper.py:133-239` 和 `tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py:80-100`，并且 helper `scripts/e2e_catalog.py:15-65` 不匹配 `scripts/e2e-*.sh`。**不改会让 worker 因范围边界规则不知道哪些 wrapper/helper 可改，进而漏删 shell 源码断言或越界修改另一 milestone 的文件。**

### Recommendations

- [R1-R1] 重新按完整 Python/IM-service/E2E、测试辅助脚本与 CI gate 划分互不重叠的 test domains；每个域只承担能够独立说明的 seam，并在范围列写出精确目录/文件集合。
- [R1-R2] 把 `assets/tasks.md` 纳入 M1，令其与 `testing.md` 的模板同源；使 M1 成为 M2-M5 的显式前置，或把已锁定的处置表直接作为每个后续 milestone 的输入契约。
- [R1-R3] 为 M4 列出 shell、Python helper、unit/integration/E2E wrapper 的完整范围，并明确不属于它的 `tests/e2e/` 用户旅程由哪个 milestone 审视。

### Author Resolutions

| Issue | Resolution | 判真证据与处理 |
|---|---|---|
| R1-C1 | accepted | 首文档 Q3 覆盖所有已提交自动化测试和质量门禁；原 M2--M4 只列局部目录，无法满足。改为 M2 覆盖非 IM/operational Python suite + CI/docs gate，M3 覆盖 `tests/im_service/`，M4 覆盖 E2E/运行脚本及明确的跨目录 wrapper，M5 覆盖所有 frontend Vitest。 |
| R1-C2 | accepted | `change-impl-worker` 由 `assets/tasks.md` 实际生成计划，正文要求不进入该模板不会稳定落地。M1 范围加入该 asset，并要求模板与 testing.md 同源。 |
| R1-C3 | accepted | 后续 worker 必须使用 M1 产生的处置表；M1 改为所有清理域的显式依赖，后续域同组并行仅在 M1 合入后开始。 |
| R1-W1 | accepted | “其 Python 测试与关键路径 wrapper”不能确定所有权。M4 改列 shell、catalog、E2E、明确 unit/integration wrapper 的完整路径集合；其余 Python 测试归 M2。 |

## Round 2

### Metadata

- reviewer: `/root/refactor489_design_reviewer`
- review_mode: `full`
- mode_reason: `full`；修订改变了完整测试面、共享处置协议、M1→M2-M5 依赖图和实施调度模型，属于 milestone 拆分与共享契约的高风险语义变化，不能仅做旧项 closure。
- started_at: `2026-08-03T11:06:43+08:00`
- completed_at: `2026-08-03T11:08:46+08:00`
- duration: `2m 03s`

### Verdict

Issues Found — 2 CRITICAL / 0 WARNING

R1 的模板和 M1 前置缺陷已关闭；但完整范围仍遗漏两个实际 test runner/helper，且新增“域内批量派 worker”与仓库的单-milestone worker 调度契约冲突，不能进入实施。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | M2 承接非 IM/operational Python + CI/docs gate，M3 承接 IM service，M4 承接 E2E/脚本/wrapper，M5 承接 Vitest，并加入 tracked coverage audit。 | `design.md:136-139` 已将 `tests/contract`、`tests/unit`、`tests/integration`、`tests/im_service`、`tests/e2e`、主要 CI/docs gate 和 Vitest 分到 M2-M5；但 `scripts/free-ports.sh` 是 E2E 起栈实际调用的 helper（`scripts/e2e-up.sh:68-71`、`scripts/e2e-resilience.sh:45-47`），未在任何范围中；Vitest 实际从 `src/IM/frontend/vite.config.ts:18-22` 读取 `test` 配置，而 M5 只列 `vitest.config.*`、`package.json` 和测试文件。 | open |
| R1-C2 | M1 加入 `assets/tasks.md`，要求模板与 testing.md 同源。 | M1 的范围已包含 `.claude/skills/change-impl-worker/assets/tasks.md`（`design.md:135`）；worker 确实从该文件创建计划（`change-impl-worker/SKILL.md:176-199`）。 | closed |
| R1-C3 | M2-M5 依赖 M1，只有 M1 完成后才并行。 | `design.md:136-139` 将 M2-M5 的依赖统一改为 `refactor-489-M1`、并行组改为 B；M1 的 asset/规范更新先可合入，再由后续 worker 建立 `tasks.md`。 | closed |
| R1-W1 | M4 列出 shell、catalog、E2E、unit/integration wrapper 的完整路径。 | `design.md:138` 已精确列出原 finding 的 `e2e_catalog.py`、`test_e2e_catalog.py`、resilience wrapper 和两个 integration tests；先前“语义范围无法执行”的问题关闭。新增 `free-ports.sh` 遗漏由 R1-C1 的完整性缺口继续承载。 | closed |

### Coverage

- 重读并重核：`motivation.md`、current `design.md`、R1 + Author Resolutions、`docs/development/change-workflow.md`、`docs/development/testing.md`、worker skill/template、orchestrator skill、CI、E2E/Vitest configuration 与 Git tracked 测试/脚本拓扑。
- `retained_from: Round 1` — 未改变的产品 non-goal、四项 `no spec delta` 与“最低合适测试层”证据；它们不受本轮 path/milestone 结构变更影响。
- 本轮未运行测试；这是 design-only Gate 2 复审，结论来自 current 文档和实际代码/测试的只读核对。

### 核实台账

#### 现状断言

| 原子 | 结论与直接证据 |
|---|---|
| Python 测试覆盖 contract/unit/integration/im_service/e2e 五个树 | 成立。Git tracked topology 包含 40 个 `tests/contract`、335 个 `tests/unit`、24 个 `tests/integration`、75 个 `tests/im_service` 与 19 个 `tests/e2e` 测试文件；修订后的 M2-M4 分别声明这些树（`design.md:136-138`）。 |
| 前端 Vitest 同时含交互回归与源码/布局断言 | 成立。交互例证仍为 `src/IM/frontend/src/features/chat/components/message-pane.test.tsx:1940-1969`，源码断言仍为 `src/IM/frontend/src/app/distribution-contract.test.ts:1-8`；实际 Vitest `test` 配置在 `src/IM/frontend/vite.config.ts:18-22`，而不是独立 `vitest.config.*`。 |
| E2E 运行链由 shell、Python helper、fixture 和 wrapper 共同构成 | 成立，但设计范围不完整。`scripts/e2e-up.sh:68-71` 和 `scripts/e2e-resilience.sh:45-47` 都执行 `scripts/free-ports.sh`；该 helper 不在 M4 的枚举（`design.md:138`）。 |
| worker 的 current plan 模板尚无处置表 | 成立，且 M1 现已正确拥有修改位置。`assets/tasks.md:21-29` 是实际模板，`design.md:135` 明确纳入 M1。 |
| CI/docs quality gate 是被跟踪的测试信号 surface | 成立。`.github/workflows/ci.yml:27-37` 运行 docs-check、ruff 和 pytest；`scripts/docs_check.py:756-980` 对 critical-path catalog 执行可收集性检查，M2 已明确拥有这些入口（`design.md:136`）。 |
| 现有 import boundary、真实入口和脚本运行是可复用 seam | 成立，未失效。`tests/contract/test_core_no_platform_imports.py:32-45`、`tests/integration/test_channel_bootstrap.py:29-108`、`tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py:80-100` 分别覆盖架构、产品入口和真实进程。 |
| 本 unit 不改产品行为 | 成立，未失效。所有修改目标仍是测试/CI/开发规范；`docs/specs/README.md:5-11` 的四个 package current contract 没有被本设计改写。 |

#### 决策

| 原子 | 结论与直接证据 |
|---|---|
| 决策 1：受影响测试有 keep/rewrite-merge/delete 结论 | 成立。处置表内容仍精确，且 M1 现在包含真实 producer template（`design.md:54-70,135`；`change-impl-worker/SKILL.md:176-199`）。 |
| 决策 2：一次风险由最低测试层拥有 | 成立，`retained_from: Round 1`。它与 `docs/development/testing.md:42-46` 一致，并保留高层跨 seam 验证。 |
| 决策 3：M1 先固化协议，再按完整域批量并行 | **不成立，见 R2-C1。** 先后依赖和 tracked audit 是正确方向，但“每个域由 owner 生成 worker 分派表、批量派发 worker”（`design.md:80-86`）没有对齐 current 原流程的调度模型。 |

#### 首文档约束

| 原子 | 结论与直接证据 |
|---|---|
| Q1：删、改、合并均以真实回归保护为准 | 部分覆盖。决策 1/2 提供充分的保留/替代判据；R2-C1 尚使 393 个 M2 测试、95,138 行和 M3/M4/M5 的域内分派无法按现行 worker 契约落地。 |
| Q2：worker 在路径/边界变化时记录处置及依据 | 覆盖。M1 现在同时修改规范、skill 和实际任务模板，并在 M2-M5 启动前完成。 |
| Q3：覆盖 Python、Vitest、测试辅助脚本和 CI quality checks | 未覆盖，R1-C1 仍开放。`free-ports.sh` 和 `vite.config.ts` 是当前被执行的测试 helper/config，却未被任何 M 的范围或分派 audit 所拥有。 |
| Requirement「无产品回归的维护改动不被历史噪声阻塞」 | 部分覆盖。域划分比 R1 完整；未拥有的 runner/config 仍可能保留低信号行为或在重构时制造无 owner 的 CI 故障。 |
| Requirement「真实风险保持最低层保护，完整门禁的失败可执行」及两个 Scenario | 部分覆盖。处置表与 audit 能保护已分配路径；R2-C1 使批量分派/验证责任不闭合。 |
| Requirement「worker 持续维护测试资产」Scenario | 部分覆盖。协议已闭合；若 M2-M5 的实际执行仍只能各由一个 worker 处理，设计承诺的全面逐域审视没有可执行责任边界（R2-C1）。 |
| 非目标与回滚 | 成立。没有引入产品变更；风险段仍禁止以删除掩盖 flaky，并允许按域回退。 |

#### Delta-spec

| 原子 | 结论与直接证据 |
|---|---|
| kernel: no spec delta | 成立，`retained_from: Round 1`；测试/流程改动未改变 `docs/specs/kernel/` 的 SDK/行为要求。 |
| im: no spec delta | 成立，`retained_from: Round 1`；M3/M5 审视测试而非 IM 消费者行为。 |
| gateway: no spec delta | 成立，`retained_from: Round 1`；M4 保留/改写运维测试，不改变 Gateway 契约。 |
| cli: no spec delta | 成立，`retained_from: Round 1`；本设计无 CLI 行为或接口变化。 |

#### Milestones

| 原子 | 结论与直接证据 |
|---|---|
| M1 test-discipline | 成立。范围包含两份规范和真正的 tasks asset；退出标准与决策 1 对齐（`design.md:135`）。 |
| M2 python-test-signal | **不成立，见 R2-C1。** M2 正确承接大部分 Python/CI/docs quality surfaces，但在排除 M4 已列文件后仍有 393 个测试文件、95,138 行，并要求“无交集 worker 分派表”；现行流程不允许该 M 内再派 worker。 |
| M3 im-service-test-signal | **不成立，见 R2-C1。** 路径归属正确，但同样要求 M 内批量派发 worker，和一 milestone 一 worker 的 current 约束冲突。 |
| M4 operational-test-reliability | 部分成立。路径列举已经消除 R1 的 wrapper 歧义，但漏 `scripts/free-ports.sh`（R1-C1），也要求没有承载角色的域内 worker 分派（R2-C1）。 |
| M5 frontend-test-signal | 部分成立。所有 Vitest 文件和 package script 已归属，但当前 `vite.config.ts:18-22` 是运行时 test config，未在 M5 范围；域内批量派发同受 R2-C1 影响。 |

### 架构进攻

| 角度 | 发现 |
|---|---|
| 归属 | M1 将协议归属到 canonical testing guide、worker skill 和它实际复制的 asset，这是正确修复。E2E port allocator 与 Vitest configuration 分别自然归属 M4/M5，却未被纳入（R1-C1）。 |
| 该不该存在 | Git tracked coverage audit 是防止再漏测试面的最小必要检查，不是多余抽象；但在每个 M 内再造一层“worker 分派表”相当于绕过既有 orchestrator/milestone 调度，删除该内层后应由 design 的细粒度 milestone 直接承载派发（R2-C1）。 |
| 深还是浅 | 处置表集中风险、旧测试、替代保护和验证，仍是有价值的深接口。新增的域内派发表没有明确 owner、worktree、branch 或 merge path，只把 orchestrator 的职责复制成文档名，形成浅封装和额外认知跳转（R2-C1）。 |
| 治本还是补丁 | M1 前置与 Git audit 对 R1 是治本修正；但把 393 文件/95,138 行塞进一个 M2 后寄望实施期临场再拆 worker，是把容量和并行问题延后，长期会反复导致无边界的大 milestone 或临时改派（R2-C1）。 |

### Issues

- [R1-C1][CRITICAL] [现状范围 / 决策 3 / Milestones M4-M5]: 全面 tracked coverage 仍未闭合。`scripts/free-ports.sh` 是 `e2e-up.sh` 和 `e2e-resilience.sh` 的实际端口分配 helper（`scripts/e2e-up.sh:68-71`、`scripts/e2e-resilience.sh:45-47`），却不在 M4；Vitest 的实际 `test` 配置位于 `src/IM/frontend/vite.config.ts:18-22`，而 M5 只列 `vitest.config.*`，该仓当前并不存在后者。设计要求发现未归属 runner 时暂停，但未给这两个已知路径指定 owner。**不改会让 tracked coverage audit 必然在实施期触发 pause，orchestrator 只能临场扩大范围或回退 Gate 2，Q3 不能按已确认设计完成。**

- [R2-C1][CRITICAL] [决策 3 / Milestones M2-M5]: “完整域内批量派发 worker/生成 worker 分派表”没有可执行的调度归属，且与 current 原流程冲突。`docs/development/change-workflow.md:136,141-146,201` 和 `change-orchestrator/SKILL.md:49-50,122,131-136` 明确是 orchestrator 按 milestone 派发、一个实现型 milestone 只交给一个 `change-impl-worker`；worker 自身也以“把这一个 milestone 做好”为职责（`change-impl-worker/SKILL.md:8-12`）。M2 却在一个 milestone 中（排除 M4 已列文件后）仍包含 393 个测试文件、95,138 行，并要求在创建 `tasks.md` 时另行批量分派 worker（`design.md:80-86,136`），但未新增对应 milestones/branch/worktree/merge owner。**不改会让 orchestrator 只能派一个 M2 worker，或在实施期违反已确认设计擅自创建第二层 worker；无论哪种都会使范围、任务记录和集成责任失真，无法可靠交付全仓清理。**

### Recommendations

- [R2-R1] 把已知的 `scripts/free-ports.sh` 和 `src/IM/frontend/vite.config.ts` 明确归入 M4/M5，并让 tracked audit 的输入集合与各 milestone 范围逐项对账。
- [R2-R2] 移除“milestone 内再次派 worker”的隐含调度层：将大域拆为足以由单一 worker 交付、文件无交集的新增 milestones，或把该层改成符合 current workflow 的明确 orchestrator-owned 里程碑与合并模型。

### Author Resolutions

| Issue | Resolution | 判真证据与处理 |
|---|---|---|
| R1-C1 | accepted | `scripts/free-ports.sh` 被 `e2e-up.sh` / `e2e-resilience.sh` 实际调用，`vite.config.ts` 是 Vitest 实际配置；分别纳入 M13、M16，且各自的测试/config 所在 test surface 同域处理。 |
| R2-C1 | accepted | current orchestrator 的硬边界是一实现型 milestone 一 worker/worktree/merge owner。删除 M2--M5 的域内二级派发设计，改为 M2--M16 的显式、无重叠测试切片；M1 后每一切片由 orchestrator 正常派发一个 worker。 |

## Round 3

### Metadata

- reviewer: `/root/refactor489_design_reviewer`
- review_mode: `full`
- mode_reason: `full`；M2--M5 被重拆为 M2--M16，改变了 milestone 数量、文件所有权、并行图和实施容量边界。该变化必须重新核所有承重原子及四个架构进攻角度，不能只做旧项 closure。
- started_at: `2026-08-03T11:13:00+08:00`
- completed_at: `2026-08-03T11:24:31+08:00`
- duration: `11m 31s`

### Verdict

Issues Found — 3 CRITICAL / 0 WARNING

显式 M2--M16 和 16 个 matching skeleton 已消除原 M2 的容量伪装，也已纳入 `free-ports.sh` 与 `vite.config.ts`；但全覆盖仍漏掉实际测试资产，M3/M8 有确定的同组写冲突，且决策 3 仍保留已被 Author Resolution 否定的二级派发指令。不能进入实施。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 将 `free-ports.sh`、`vite.config.ts` 分别纳入 M13、M16，按 M2--M16 覆盖全部 test surface。 | 已修复此前两个具体遗漏：M13 包含 `scripts/free-ports.sh`、M16 包含 `src/IM/frontend/vite.config.ts`（`design.md:147,150`）。但 tracked 范围审计仍找出不属于任何 M 的 13 个 `tests/unit/IM/test_*.py`、Vitest 实际执行的 `src/IM/frontend/src/test/setup.ts` 与被多项设置测试导入的 `render-router.tsx`，以及跨 IM contract/integration/e2e 使用的 `tests/im_service/_auth_helpers.py`；详见本轮台账。 | open |
| R1-C2 | M1 纳入实际 `assets/tasks.md`。 | M1 仍同时拥有 `testing.md`、worker skill 和实际复制的 template（`design.md:135`）；`change-impl-worker/SKILL.md:176-199` 仍从该 asset 建立计划。 | closed |
| R1-C3 | M1 后才派发后续 slices。 | M2--M16 都依赖 M1 且属于 B 组（`design.md:136-150`）；协议落地先于清理 worker 创建 `tasks.md`。 | closed |
| R1-W1 | M13 明列 E2E、脚本、catalog、fixture 和 wrapper。 | M13 已精确拥有 `tests/e2e/**`、`scripts/e2e-*.sh`、catalog、fixture、`free-ports.sh` 及原先指名的 unit/integration wrapper（`design.md:147`）。 | closed |
| R2-C1 | 删除域内二级派发，改由 orchestrator 对 M2--M16 正常一 milestone 一 worker 调度。 | M2--M16 的显式表、16 个 `.gitkeep` skeleton 和 `design.md:131` 的“一 milestone 一 worker”已经闭合容量与 worktree/merge 所有权；但决策 3 仍要求每个域在创建 `tasks.md` 时生成“worker 分派表”并“批量派发 worker”（`design.md:80-85`）。该 artifact/owner 不在 current workflow 中，且与 Author Resolution 相抵。 | open |

### Coverage

- 重读并逐项核实：`motivation.md`、current `design.md`、R1/R2 与两次 Author Resolutions、`docs/development/change-workflow.md`、`docs/development/testing.md`、orchestrator/worker skill 与 tasks asset、CI、Git tracked 测试/fixture/runner/config 拓扑。
- 对 M2--M16 做了逐路径归属审计：623 个可执行或支撑自动化测试的 tracked 路径得到单一归属、1 个路径双归属、20 个路径未归属；未归属中的 package `__init__.py` 不构成 finding，其余实际测试、Vitest harness 或共享 helper 构成 R1-C1 的证据。
- 已核实 milestone 表有 16 行，unit 下也恰有 16 个 `M*-*/.gitkeep` skeleton；本轮未运行测试，这是 design-only Gate 2 复审。

### 核实台账

#### 现状断言

| 原子 | 结论与直接证据 |
|---|---|
| Python 测试覆盖 contract/unit/integration/im_service/e2e 五个树 | 部分成立。五棵树均存在且被 M2--M13 主体覆盖，但 `tests/unit/IM/test_agent_channels.py:1-20` 是真实 IM 行为测试，整个 `tests/unit/IM/**` 未出现于任何范围（`design.md:136-150`）。 |
| 前端 Vitest 同时含交互回归与源码/布局断言 | 成立，但其运行 harness 未完整归属。Vitest 从 `vite.config.ts:18-22` 执行 `src/test/setup.ts`；`render-router.tsx:23-60` 被 router/settings 测试复用，而 M16 仅列余下 `*.test.{ts,tsx}`、`tests/**` 与 config（`design.md:150`）。 |
| E2E 运行链由 shell、Python helper、fixture 和 wrapper 共同构成 | 成立，先前缺口已修复。`e2e-up.sh:68-71`/`e2e-resilience.sh:45-47` 使用的 `free-ports.sh` 现在明确在 M13（`design.md:147`）。 |
| worker 的 current plan template 尚无处置表 | 成立，M1 落点正确。实际 template 是 `assets/tasks.md:21-29`，M1 现在拥有它（`design.md:135`）。 |
| CI/docs quality gate 是被跟踪的测试信号 surface | 成立。CI 运行 docs check、ruff、pytest 与 frontend Vitest（`.github/workflows/ci.yml:27-60`），相应入口被 M2/M16 列出（`design.md:136,150`）。 |
| IM 测试使用跨层共享 auth helper | 成立而未精确分配。`tests/im_service/_auth_helpers.py:30-112` 被 contract tests、integration `conftest.py:1-12` 和 e2e `test_human_chat_sse_e2e.py:10-14` 共同导入；M11/M12 都以“同域 fixture/helper”描述范围（`design.md:145-146`），没有唯一 owner。 |
| 本 unit 不改产品行为 | 成立。目标仍是测试/CI/流程，四项 `no spec delta` 与 `docs/specs/README.md:5-11` 的 current product contracts 一致。 |

#### 决策

| 原子 | 结论与直接证据 |
|---|---|
| 决策 1：受影响测试有 keep/rewrite-merge/delete 结论 | 成立。表格式、删除前提和精确文本例外完整（`design.md:54-70`），M1 同时更新规范、skill 和 template，符合 Q2。 |
| 决策 2：一次风险由最低测试层拥有 | 成立。其分层原则与 `docs/development/testing.md:31-46` 相符，保留跨 seam 的高层验证而非重复断言。 |
| 决策 3：M1 后按完整、无交集 domain 并行 | 部分成立，见 R1-C1、R2-C1、R3-C1。M1 先行、M2--M16 显式 slices 是正确结构；但“domain owner 在创建 tasks.md 时生成 worker 分派表/批量派发”的旧语义仍留在 `design.md:80-85`，并且实际范围并非无交集。 |

#### 首文档约束

| 原子 | 结论与直接证据 |
|---|---|
| Q1：清理、改写、合并以真实回归保护为准 | 部分覆盖。决策 1/2 给出保留与替代判据；未归属的 IM/Vitest/support surfaces 无 worker 作处置结论（R1-C1）。 |
| Q2：worker 在路径/边界变化时记录处置及依据 | 覆盖。M1 已拥有长期规范、skill 和生成 tasks 的实际 asset（`design.md:135`；`change-impl-worker/SKILL.md:176-199`）。 |
| Q3：覆盖 Python、Vitest、测试辅助脚本和 CI quality checks | 未覆盖，R1-C1 仍开放。M13/M16 修复了已知两个路径，但 `tests/unit/IM/**`、`src/IM/frontend/src/test/**` 与 `_auth_helpers.py` 仍不能由表中单一 M 审视。 |
| Requirement：维护改动不被历史噪声阻塞 | 部分覆盖。已拥有 slices 可清理历史断言；未归属或双归属范围会迫使 worker 暂停/越界，不能保证完整地消除噪声。 |
| Requirement：真实风险保持最低层保护，完整门禁失败可执行 | 部分覆盖。处置表和分层决策正确；M3/M8 双写会破坏 B 组并行与可重复验证（R3-C1）。 |
| Requirement：worker 持续维护测试资产 | 部分覆盖。M1 协议持久化正确；决策 3 的不再适用的二级分派指令会让 single-milestone worker 不知道应否再调度子 worker（R2-C1）。 |
| 非目标与回滚 | 成立。没有扩展至产品功能，且风险段仍要求真实风险先有替代保护、按域可回退（`design.md:115-119`）。 |

#### Delta-spec

| 原子 | 结论与直接证据 |
|---|---|
| kernel: no spec delta | 成立。测试资产与 worker 流程变化不改变 `docs/specs/kernel/` 面向 SDK 消费者的行为。 |
| im: no spec delta | 成立。M11--M16 只调整 IM 测试/测试配置，不改 IM 消费者可观察契约。 |
| gateway: no spec delta | 成立。M8/M13 的目标是现有投递、进程与恢复测试信号，不改变 Gateway 合约。 |
| cli: no spec delta | 成立。M5 只重构 CLI 测试，未提议新命令或 SDK 行为。 |

#### Milestones

| 原子 | 结论与直接证据 |
|---|---|
| M1 test-discipline | 成立。规范、skill 和真正的 template 同属一个无产品面的 vertical slice（`design.md:135`）。 |
| M2 contract-ci-quality | 成立。contract、shared test helper、CI/docs quality gate 的落点明确（`design.md:136`）。 |
| M3 core-prompt-runtime | **不成立，见 R3-C1。** root `test_jsonl_store_dag_recovery.py` 同时匹配 M3 的 `jsonl_store` 和 M8 的 `jsonl_store` glob。 |
| M4 core-tools-platform | 成立。目录与 root catch-all 明确排除其他 M，未在本轮审计中发现重叠。 |
| M5 coding-cli-tests | 成立。CLI root tests 与 `_cli_*` harness 被唯一归属。 |
| M6 assistant-config-feishu | 成立。指定 PA/config/Feishu prefix 与 M8 的排除关系清楚。 |
| M7 assistant-scheduling | 成立。schedule/heartbeat/cron prefix 与 M8 的排除关系清楚。 |
| M8 assistant-runtime-delivery | **不成立，见 R3-C1。** 除了 PA residual 的正确意图外，root glob 与 M3 相交。 |
| M9 kernel-integration-tests | 成立。M9 prefix 与 M10 residual、M13 exact runtime tests 无交集。 |
| M10 assistant-integration-tests | 成立。其 residual 规则在 M9/M13 之后是单一归属。 |
| M11 im-persistence-contract | 部分成立，见 R1-C1。unit/contract tree 明确，但“同域 fixture/helper”与 M12 对跨层 `_auth_helpers.py` 的归属不精确。 |
| M12 im-api-realtime | 部分成立，见 R1-C1。integration/e2e tree 明确，但同一 shared helper 没有唯一 owner。 |
| M13 operational-e2e | 成立。E2E、fixtures、scripts、helper 与 wrapper 范围现在完整且精确（`design.md:147`）。 |
| M14 frontend-chat | 成立。chat Vitest glob 单独、无交集。 |
| M15 frontend-settings | 成立。settings Vitest glob 单独、无交集。 |
| M16 frontend-foundation | 部分成立，见 R1-C1。其余 `*.test` 与 config 已归属，但 Vitest setup/router test harness 不匹配范围。 |

### 架构进攻

| 角度 | 发现 |
|---|---|
| 归属 | 将处置协议归到 canonical testing guide、worker skill 和 template 是正确的；`tests/unit/IM/**` 与 frontend `src/test/**` 分别应归一个明示的 IM/test-harness slice，不应因目录名或非 `*.test` 后缀掉出审视范围（R1-C1）。 |
| 该不该存在 | M2--M16 正是删除“域内再派 worker”后所需的最小调度表达，额外的 worker 分派表没有独立职责：现有 milestone 表已经是 orchestrator 的调度输入（`change-orchestrator/SKILL.md:129-145`）。保留该层会重造已存在的编排职责（R2-C1）。 |
| 深还是浅 | 处置表是集中风险、旧保护、替代测试和验证的深接口。相反，“同域 fixture/helper”把实际共享文件的归属留给各 worker 猜，不是足够深的边界；长期会在跨层测试重构时重复制造 worktree conflict 或无人维护的 harness（R1-C1）。 |
| 治本还是补丁 | 从 5 个粗域改为 15 个明确 test slices 是治本且可审核的容量修复；但同组 M3/M8 对同一文件的 glob 交集仍是并行计划的直接补丁洞，会在集成时反复出现冲突（R3-C1）。 |

### Issues

- [R1-C1][CRITICAL] [现状范围 / 决策 3 / Milestones M11-M12、M16]: 已知 `free-ports.sh` 和 `vite.config.ts` 虽已归属，完整 tracked coverage 仍未闭合。`tests/unit/IM/` 有 13 个已提交的 `test_*.py`（例如真实 IM transaction 行为测试 `test_agent_channels.py:1-20`）却不在 M2--M16 的任一范围；Vitest 必跑的 `src/IM/frontend/src/test/setup.ts` 由 `vite.config.ts:18-22` 指定，`render-router.tsx:23-60` 被多项测试导入，但 M16 只匹配 `*.test`；`tests/im_service/_auth_helpers.py` 被 contract、integration 和 e2e 共同使用，却只落入 M11/M12 含糊的“同域 fixture/helper”措辞。**不改会让这些真实测试/runner/helper 没有单一 worker 作 keep/rewrite-merge/delete 判断；coverage audit 将迫使实施期暂停或越界，Q3 不能按设计交付。**

- [R2-C1][CRITICAL] [决策 3 / Milestone dispatch]: M2--M16 已正确显式表达一 worker 一 milestone，却未真正删除原二级调度命令。`design.md:80-85` 仍要求“各测试域批量派发 worker”，并称 owner 在创建 `tasks.md` 时生成“worker 分派表”；current 原流程则由 orchestrator 直接读取 milestone 表派发（`docs/development/change-workflow.md:136,141-146`；`change-orchestrator/SKILL.md:129-145`），而 `tasks.md` 是已被派发的单一 worker 的交付物（`change-impl-worker/SKILL.md:8-12,23`）。**不改会让 M2--M16 worker 不知道是只完成分到的 slice、还是必须另行生成/派发子 worker；这与 author 已确认的一 milestone 一 worker 边界冲突，导致临场扩范围或重复调度。**

- [R3-C1][CRITICAL] [Milestones M3、M8]: M3 与 M8 在同一 B 并行组对 `tests/unit/test_jsonl_store_dag_recovery.py` 有确定的范围交集：M3 的 root glob 包含 `jsonl_store`（`design.md:137`），M8 的 root glob 也包含 `jsonl_store`（`design.md:142`）。该文件确实是已提交的 session JSONL 行为测试（`test_jsonl_store_dag_recovery.py:1-28`）。**不改会使两个 isolated worktree worker 都合法修改同一文件，产生并行冲突、重复或互相覆盖的处置记录，违反原流程的“只修改 milestone 范围”与无写冲突并行条件。**

### Recommendations

- [R3-R1] 将 `tests/unit/IM/**`、`src/IM/frontend/src/test/**`、`tests/im_service/_auth_helpers.py` 明确分给一个且仅一个 milestone；若 IM helper 同时服务 M11/M12，指定唯一 owner，并把另一个 M 对它的依赖/暂停路径写明。
- [R3-R2] 把决策 3 的“worker 分派表/批量派发”整段替换为：M1 合入后，orchestrator 直接按本表的 M2--M16 对每个 slice 派一个 worker；不要新增 dispatch artifact 或 domain owner。
- [R3-R3] 从 M3 或 M8 的 root glob 移除 `jsonl_store`，再用 Git tracked path audit 验证所有非 package-marker 测试、fixture、runner 与 config 恰有一个 owner。

### Author Resolutions

| Issue | Resolution | 判真证据与处理 |
|---|---|---|
| R1-C1 | accepted | `tests/unit/IM/**` 与 IM shared auth helper 都归 M11；M12 明确使用但不拥有该 helper。Vitest `src/test/**` 归 M16，与 `vite.config.ts` 同一 runner/config owner。 |
| R2-C1 | accepted | 决策 3 删除所有“domain owner / worker 分派表 / 批量派发”措辞，明确 M1 后由 orchestrator 直接依 milestone 表对 M2--M16 各派一个 worker。 |
| R3-C1 | accepted | `test_jsonl_store_dag_recovery.py` 属于 M3 core/session 范围；从 M8 root glob 删除 `jsonl_store`，使 B 组没有双写路径。 |

## Round 4

### Metadata

- reviewer: `/root/refactor489_design_reviewer`
- review_mode: `delta`
- mode_reason: `delta`；修订有界地修改了决策 3 与 M8/M11/M12/M16 的路径所有权，直接针对 R1-C1、R2-C1、R3-C1。复审重跑这些原子、其调度上下游和完整 tracked test/fixture/runner/config owner audit；其余承重原子保留 Round 3 的有效核实。
- started_at: `2026-08-03T11:25:00+08:00`
- completed_at: `2026-08-03T11:32:34+08:00`
- duration: `7m 34s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

R2-C1 与 R3-C1 已关闭，且 M11/M12/M16 的实际测试资产已形成唯一 owner；不过 `docs-check` 直接校验、并与 M13 e2e 测试一一引用的 critical-path catalog 仍无 milestone owner，故 R1-C1 尚不能关闭。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | M11 拥有 `tests/unit/IM/**` 与 `_auth_helpers.py`，M12 不改该 helper；M16 拥有 `src/test/**`。 | 三项均已精确落点：M11 列出 `tests/unit/IM/**` 和 `_auth_helpers.py`，并要求 M12 只使用（`design.md:145-146`）；M16 列出 `src/IM/frontend/src/test/**`（`design.md:150`），覆盖 Vitest `setupFiles`（`vite.config.ts:18-22`）和 router harness。对所有测试、fixture、runner 与 config 路径的逐路径审计得到 641 个单一 owner、0 个交集，未归属的只有 3 个空 package `__init__.py`。但 `scripts/docs_check.py:93,756-918,980` 直接将 `docs/development/e2e-critical-paths.md` 作为被 pytest collection 验证的 catalog；它引用 M13 `tests/e2e/critical_paths/**`（`e2e-critical-paths.md:23-29`），却不在 M1--M16 的任一范围。 | open |
| R1-C2 | M1 拥有实际 tasks asset。 | 未受本轮影响；`design.md:135` 与 `change-impl-worker/SKILL.md:176-199` 的 template producer/consumer 仍一致。 | closed |
| R1-C3 | M1 后才派发后续 slices。 | 未受本轮影响；M2--M16 都依赖 M1（`design.md:136-150`）。 | closed |
| R1-W1 | M13 精确列 E2E 运行资产。 | 未受本轮影响；M13 仍拥有 shell、fixture、catalog script 与 wrapper（`design.md:147`）。 | closed |
| R2-C1 | 删除二级派发，orchestrator 直接按 M2--M16 派一 worker。 | 已关闭。决策 3 现明确 orchestrator 按表各派一位 worker（`design.md:80-84`）；它把 milestone 表定为唯一调度输入，并限定 worker 只为获派 slice 建 `tasks.md`。这与 `change-orchestrator/SKILL.md:129-145` 和 worker 的单 milestone 边界一致。 | closed |
| R3-C1 | 从 M8 删除 `jsonl_store`，仅归 M3。 | 已关闭。M3 仍匹配 `test_jsonl_store_*`（`design.md:137`），M8 的 root glob 已不含 `jsonl_store`（`design.md:142`）；完整 B 组路径审计无交集。 | closed |

### Coverage

- 重查的 changed atoms：决策 3，M8/M11/M12/M16，以及它们对 M1→B 组调度、Q2/Q3 和 current workflow 的影响。
- 对 Git tracked 的 Python test/support、Vitest test/harness/config、E2E script/fixture、CI/pytest quality-gate 路径逐一映射：641 项恰有一个 owner，0 项多 owner；未映射的 `tests/__init__.py`、`tests/unit/__init__.py`、`tests/im_service/__init__.py` 均为空 package marker，不是测试或 runner。
- 审计外扩至 CI `docs-check` 的直接 e2e-catalog 输入，发现本轮 R1-C1 的剩余缺口；该影响仍局限于 catalog 文件与 M13，故维持 `delta`，没有失效 Round 3 对未改决策、spec/no-delta 和其余 M 的台账。
- 未运行测试；这是 design-only Gate 2 复审。

### 本轮重查证据

| 原子/波及链 | 结论与直接证据 |
|---|---|
| 决策 3 → 原流程调度 | 成立。`design.md:82-84` 的“orchestrator 直接按本表对 M2--M16 各派一个 worker”与 `docs/development/change-workflow.md:136,141-146` 的按 milestone 派 worker 完全一致；不再要求 worker 生成 dispatch artifact。 |
| M11/M12 shared IM helper | 成立。`tests/im_service/_auth_helpers.py:30-112` 仍被 contract、integration 与 e2e 消费，但 M11 是唯一可修改 owner（`design.md:145`），M12 明示排除该文件（`design.md:146`）；平行 worker 不再有双写解释。 |
| M16 Vitest harness | 成立。Vitest 通过 `vite.config.ts:18-22` 加载 `src/test/setup.ts`，而 `render-router.tsx:23-60` 是 settings/router tests 的共同 fixture；`design.md:150` 将整个 `src/test/**` 与 remaining Vitest/config 归 M16。 |
| M3/M8 root test split | 成立。`test_jsonl_store_dag_recovery.py:1-28` 只匹配 M3，M8 的 root set 是 inbound/reject/text_runner/terminal（`design.md:137,142`）；B 组无路径重叠。 |
| M13 e2e catalog 的 gate 输入 | **不成立，见 R1-C1。** `scripts/docs_check.py:93-95,756-918,980` 读取并验证 catalog 引用的每个 pytest node；catalog 本身说其守护测试位于 `tests/e2e/critical_paths/`（`docs/development/e2e-critical-paths.md:23-29`），但 table ranges 没有该 docs 文件。 |

### 架构进攻（受影响角度）

| 角度 | 发现 |
|---|---|
| 归属 | M11/M12/M16 现在把共享 helper、Vitest harness 和 test config 放到唯一、自然的 owner，消除了并行歧义。e2e catalog 是 M13 test tree 的结构化入口，当前却没有 owner（R1-C1）。 |
| 该不该存在 | 删除 domain dispatch artifact 后，milestone 表直接服务 orchestrator，消除了多余间接层。e2e catalog 是现有 CI 验证的必要契约，不应因其为 Markdown 就被排除在测试资产审视外。 |
| 深还是浅 | “每个 slice 一 worker”现在以完整 milestone 表表达，接口足够深且无额外调度跳转；catalog 的 test-node 引用则是运行 gate 的真实输入，缺 owner 会把这个 seam 留在任何 worker 的审视范围之外（R1-C1）。 |
| 治本还是补丁 | explicit slices + Git path audit 是针对 R2/R3 的治本修正。仅补文件路径而漏掉 `docs-check` 的 catalog input 仍会在未来 e2e 测试改名、合并或删除时造成 gate failure，需要完成最后的所有权闭环。 |

### Issues

- [R1-C1][CRITICAL] [决策 3 / Milestone M13 / CI quality gate]: 完整测试质量门禁的输入仍缺单一 owner。`scripts/docs_check.py:93-95,756-918,980` 会读取 `docs/development/e2e-critical-paths.md`、从其表格提取 `tests/e2e/critical_paths` pytest node 并验证可收集性；catalog 也明确把自己定义为“用户旅程 ↔ 守护 e2e 测试”的权威对账表（`e2e-critical-paths.md:1-5,23-29`）。M13 唯一拥有被引用的 E2E tests（`design.md:147`），但不拥有该 catalog，M2 的 docs-check scope 同样没有该文档。**不改会使 M13 改写、合并或删除 E2E 测试时无法同步权威引用，或迫使 worker 越界/暂停；CI 文档质量门禁会因悬空 node 失败，Q3 的“每个失败可执行”不能保证。**

### Recommendations

- [R4-R1] 将 `docs/development/e2e-critical-paths.md` 明确归入 M13（或另指定唯一 milestone，并记录 M13 对它的依赖）；重新以 `git ls-files` 加上所有 CI gate 的直接数据输入运行 owner audit，确保每个非 package-marker 测试、fixture、runner、测试配置与被 gate 解析的 catalog 恰有一个 owner。

### Author Resolutions

| Issue | Resolution | Evidence to recheck |
|---|---|---|
| R4-R1 / R1-C1 残余 | 接受。`docs/development/e2e-critical-paths.md` 是 `scripts/docs_check.py` 解析并以 pytest collection 验证的 E2E catalog，必须和它引用的 `tests/e2e/critical_paths/**` 由 M13 同一 owner 维护。已把该 catalog 加入 M13 范围和退出标准，并把决策 3 的 owner-audit 范围扩至 CI gate 的直接解析输入。 | `design.md` 的决策 3 与 M13；对 tracked 测试资产、runner/config 和 gate 直接 catalog 输入的唯一 owner 审计。 |

## Round 5

### Metadata

- reviewer: `/root/refactor489_design_reviewer`
- review_mode: `delta`
- mode_reason: `delta`；修订仅把 R4 发现的 critical-path catalog 归入 M13，并扩展决策 3 的 owner-audit 语义。重查 catalog→E2E pytest→CI 链路及全量路径唯一 owner；其余承重原子继承 Round 4 的有效结论。
- started_at: `2026-08-03T11:33:00+08:00`
- completed_at: `2026-08-03T11:37:20+08:00`
- duration: `4m 20s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

R4-C1 已关闭。所有本 unit 要审视的 tracked 测试、fixture、runner、测试配置和 CI gate 直接解析的 catalog 现在都恰有一个 milestone owner；B 组范围无交集，可进入 `change-orchestrator`。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | M13 拥有 `docs/development/e2e-critical-paths.md`，并维护 catalog 与守护 pytest node 的可收集性；决策 3 audit 覆盖 gate 直接解析的 catalog。 | 已关闭。M13 的范围同时包含 catalog、`tests/e2e/**`、E2E script/fixture 与对应 wrapper（`design.md:147`）；其退出标准要求维护 catalog 和 node 可收集性。`scripts/docs_check.py:93-95,756-918,980` 确认该文档正是 CI docs-check 解析并验证的输入，CI 实际执行 `./scripts/docs-check`（`.github/workflows/ci.yml:27-37`）。 |
| R1-C2 | M1 拥有实际 tasks asset。 | `retained_from: Round 4` — M1 的 guide/skill/template producer-consumer 边界未改变。 | closed |
| R1-C3 | M1 后才派发后续 slices。 | `retained_from: Round 4` — M2--M16 仍统一依赖 M1。 | closed |
| R1-W1 | M13 精确拥有 E2E 运行资产。 | M13 新增 catalog 后仍保持唯一范围；其 shell、fixture、catalog script 和 wrapper 集合未与其他 M 相交（`design.md:147`）。 | closed |
| R2-C1 | orchestrator 直接按 M2--M16 一 milestone 一 worker 派发。 | `retained_from: Round 4` — 决策 3 仍将 milestone 表作为唯一调度输入（`design.md:80-84`）。 | closed |
| R3-C1 | `jsonl_store` 仅归 M3。 | `retained_from: Round 4` — M3 包含该 root prefix，M8 不包含（`design.md:137,142`）。 | closed |

### Coverage

- 重查 changed atoms：决策 3 的 owner-audit 范围与 M13 的 range/exit criteria；追踪 `docs/development/e2e-critical-paths.md` → `tests/e2e/critical_paths/**` → `scripts/docs-check` → CI 的真实引用链。
- 重新逐路径映射 M1--M16 的 test asset 集：645 个 tracked 测试、fixture、runner、测试配置或 CI gate 直接 catalog 输入均为单一 owner，0 个重叠；唯一未映射的 `tests/__init__.py`、`tests/unit/__init__.py`、`tests/im_service/__init__.py` 均为 0-byte package marker。
- `retained_from: Round 4` — motivation 的 Q1--Q3、无产品行为变化、四项 `no spec delta`、M1/M2--M12/M14--M16 的独立 seam 和退出标准均未改变；本轮未运行测试，这是 design-only Gate 2 复审。

### 本轮重查证据

| 原子/波及链 | 结论与直接证据 |
|---|---|
| 决策 3 → owner audit | 成立。决策已将覆盖范围明确为 Python、Vitest、测试脚本、CI gate 及其直接解析 catalog，并规定未归属即暂停交 orchestrator（`design.md:80-86`）。 |
| M13 → e2e catalog → pytest node | 成立。M13 拥有 `docs/development/e2e-critical-paths.md`、`tests/e2e/**` 和 E2E runners（`design.md:147`）；catalog 的登记纪律要求每条守护测试可被 pytest 收集（`e2e-critical-paths.md:23-29`），而 `scripts/docs_check.py:889-917` 正验证该关系。 |
| CI → catalog gate | 成立。CI 运行 `./scripts/docs-check`（`.github/workflows/ci.yml:27-37`）；`run_checks` 调用 `check_e2e_critical_path_catalog`（`scripts/docs_check.py:971-981`）。M13 因而可以在改写/合并 E2E test 时同步更新唯一权威引用，不会越界。 |
| 全域无交集 | 成立。Git tracked owner audit 覆盖 M1 的规范/template、Python tests/support、Vitest tests/harness/config、E2E scripts/fixtures、CI gates 与 catalog；结果为 645 个单 owner、0 个 overlap。`tests/__init__.py`、`tests/unit/__init__.py`、`tests/im_service/__init__.py` 均为 0-byte marker，故不属于需要处置的测试资产。 |

### 架构进攻（受影响角度）

| 角度 | 发现 |
|---|---|
| 归属 | catalog 与它的 E2E test tree、runner 和 fixture 同归 M13，符合“改 test node 同步维护 gate input”的自然所有权。 |
| 该不该存在 | 没有新增 registry 或 dispatch 层：已存在的 catalog 继续由实际 E2E owner 维护，milestone 表仍是 orchestrator 唯一调度输入。 |
| 深还是浅 | M13 的 range + “维护 catalog 与 node 可收集性”退出标准把可能导致 CI 失败的跨文件约束集中成可验证的责任，而不是把更新步骤散落给 M2/M13 两个 worker 猜。 |
| 治本还是补丁 | Git owner audit 已把同类未归属路径前置为 Gate 2 可见条件；以后新增的 runner/catalog 若无 owner 会按决策 3 触发暂停与重分配，避免再形成临场越界。 |

### Issues

无。

### Recommendations

- [R5-R1] 实施时由 orchestrator 保留本轮 Git owner-audit 的输入口径；若 main 同步引入新的测试、fixture、runner、测试配置或 CI 直接解析 catalog，先重跑审计并按决策 3 分配 owner，再派发受影响的 B 组 milestone。

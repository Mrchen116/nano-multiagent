# Spec/design 对齐评测集

本目录定义一个可长期扩展的八需求评测集，用来回答两个核心问题：待评工作流是否减少用户对齐负担，以及是否产出更好的 spec/design 并降低下游返工。共享 case、schema、base repository 和 validator 与具体 treatment 解耦；feat-397 Agent Team 的实验协议放在 [experiments/feat_397_agent_team/](experiments/feat_397_agent_team/protocol.md)。本目录不是 case 答案集合，也不以一个总分替代判断。

## 证据边界

- **仓库事实**：feat-397 的目标是轻 brief 启动、事实自主查证、稳定偏好预填、价值岔路与硬红线升级、等待期间继续推进，且现有分析认为约 24% 的历史澄清可由事实检索剥离。依据见 [spec](../../docs/changes/feat-397-spec-design-agent-team/spec.md)、[用户旅程](../../docs/changes/feat-397-spec-design-agent-team/user-journey.md)、[用户画像候选稿](../../docs/changes/feat-397-spec-design-agent-team/user-profile-draft.md) 和 [澄清可剥离分析](../../docs/changes/feat-397-spec-design-agent-team/clarification-removability-analysis.md)。
- **评测设计判断**：six-clock、五层封装、A+USER 消融、S0-S7 冻结点、污染分级与分层报告，是 feat-397 实验为可比性作出的设计选择，详见 [protocol](experiments/feat_397_agent_team/protocol.md)。
- **仍待验证**：team 是否真的更少打扰、更懂用户、产出更好，只能由完成 case、封存私有裁判材料并实际运行后判断。本目录当前不宣称胜负。

评测采用“确定性检查先行、盲评处理语义质量、下游结果验证可实施性”的组合，而不是依赖 LLM 单一数字分。这样与研究简报中对通用 judge、单人品味和可演进性代理的边界一致，见 [评测 harness 研究](../../docs/changes/feat-397-spec-design-agent-team/Agent_%E6%B7%B1%E5%BA%A6%E7%A0%94%E7%A9%B6%E7%AE%80%E6%8A%A5/round2/r2d6-eval-harness.md)。

## 八例构成

| Case | 类型 / 契约 | 主要复杂性 | 在实验里负责区分什么 |
|---|---|---|---|
| **H01 — Web IM message interactions** | 历史回归 / single unit | 桌面与移动交互、产品取舍、商业化视觉质量、既有组件约束 | team 能否从轻 brief 找全用户场景，并少问可由仓库与稳定偏好回答的问题 |
| **H02 — PA unified tool approval model** | 历史回归 / single unit | 配置 omission、PA/内核边界、模型选择、失败与重启语义 | team 能否从一句需求自主找全配置、组合与运行时事实，并正确升级六个产品选择 |
| **H03 — cross-channel session controls** | 历史回归 / single unit | IM/飞书一致性、FIFO 与并发、会话可见性、持久化边界 | team 能否发现跨 channel 的共享契约与时序约束，避免只做表层命令 |
| **H04 — workspace-compatible Skills** | 历史回归 / single unit | PA/CLI 同源发现、优先级、显式选择持久化、分组交互 | team 能否同时减少显而易见的追问，并找全隐藏配置写入路径与端到端一致性 |
| **H05 — Agent workspace root selection** | 历史回归 / single unit | 分布式文件系统 owner、路径 provenance、唯一性、商业化创建 UX | team 能否把产品选择与仓库事实分开，并避免在 IM 主机错误解释 Gateway 路径 |
| **H07 — product workspace layout** | 历史回归 / single unit | 跨包命名空间、每轮执行隔离、数据迁移、secret、真实旅程 | team 能否在大范围重构中收敛长期契约与一次性迁移，而不引入运行时兼容债务 |
| **P01 — cross-node Agent migration** | 前瞻 pilot / single unit | 多 owner 状态、迁移 fencing、运行中任务、secret、失败恢复 | 演练无历史答案时，是否能把事实、价值岔路和条件硬红线正确分流 |
| **P02 — Agent runtime center** | 前瞻 pilot / single unit | 多运行源聚合、状态语义、权限与脱敏、桌面/移动信息架构 | 演练“更懂用户”是否带来适当默认与审美取舍，同时不越权替用户决定产品方向 |

六例历史回归都标为 candidate-side `C1`，用于测已发生过真实返工的复杂需求。P01/P02 的候选输入按 `C0` 构造，但它们在 A/B runnable workflow 与 profile-builder 冻结前已经进入同仓 authoring 视野，因此显式标为 `prospective_pilot + pre_treatment_freeze_visible`，**不能充当前瞻主结论的 clean holdout**。它们负责验证 harness、决策分类与未来需求价值；真正的 clean holdout 必须先冻结 treatment authoring closure，再由隔离、task-blind 的流程创建并在下一 dataset version 中替换/新增。

## 目录

- [experiments/feat_397_agent_team/protocol.md](experiments/feat_397_agent_team/protocol.md)：feat-397 实验的单位、六个时钟、五层输入、三条 arm、冻结点、指标、污染控制与停止规则。
- [base_repo/](base_repo/README.md)：八例 arm A 的正式 clean-room materializer、recipe、测试与复现命令。
- [receipts/base-repository-A.md](receipts/base-repository-A.md)：八例真实物化的稳定收据摘要；不记录临时目录。
- [diagnostics/](diagnostics/README.md)：不进入主 registry/seal 的旧 H02、外部源码诊断材料，以及 owner 明确拒绝的 H06 disposition。
- [dataset.json](dataset.json)：固定的 8 个 draft case 注册表；H06 有意留空，不复用编号。
- [source-roots.json](source-roots.json)：suite-level source ownership 与 treatment scrub 冻结账本；逐 source 固定 raw archive、cutoff `AGENTS.md`、投影、删除清单和 post-filter hashes。
- [experiments/feat_397_agent_team/suite-treatment-lock.json](experiments/feat_397_agent_team/suite-treatment-lock.json)：feat-397 实验中八例共同的 treatment identity 锁；中央逐文件列出 source path/hash 与 candidate-visible install path/mode/hash，绑定三条 arm、shared helper、artifact contract、workflow/profile closure、N0 derivation、固定 guardrail 和每例泄漏签名。clean holdout 另要求先发布一份完整绑定所有 candidate-visible rule/prompt component 与 lineage 的 authoring-freeze receipt，再以 Git 祖先关系证明 case 首次引入发生在后；current 与 team 的 candidate-visible workflow manifest 必须不同。
- [experiments/feat_397_agent_team/suite-seal.json](experiments/feat_397_agent_team/suite-seal.json)：feat-397 实验对协议、validator/schema pack、八例固定资产、runtime refs、source/treatment、可物化模型/工具/权限资产、重复次数、refinement、固定 mapper/judge controls、匿名化与下游计划的统一封存；正式 run ledger 只能引用同一个 frozen seal。
- [validate_dataset.py](validate_dataset.py)：零额外依赖的控制资产校验；重算 7 个 formal 主仓 source、八份 base recipe、schema、证据锚点和泄漏正则，并强制 H06/bugfix-520 保持 rejected。`--verify-base-repositories` 真实重放八例 arm A；`--require-sealable` 在 A+USER/B 未冻结时必须失败；发布结果前用 `--require-complete-runs` 强制完整 ledger 矩阵。
- [schema/case.schema.json](schema/case.schema.json)：每个 case 的运行元数据契约。
- [schema/authority-map.schema.json](schema/authority-map.schema.json)：私有来源审计与候选导出路径契约；它不能驱动 normalizer 选材。
- [schema/decision-inventory.schema.json](schema/decision-inventory.schema.json)：私有 F/P/V/H 决策真值契约。
- [schema/source-root-manifest.schema.json](schema/source-root-manifest.schema.json)：source-root ownership、固定删除规则、产品实现保留根与 per-source hash 契约。
- [schema/layer-manifest.schema.json](schema/layer-manifest.schema.json)：运行时 product/documentation/common layer 的物化文件清单和 scrub assertions 契约。
- [schema/treatment-manifest.schema.json](schema/treatment-manifest.schema.json)：shared-helper、三 arm 显式 allowlist/denylist、依赖闭包、身份断言与最终 export 契约。
- [schema/suite-treatment-lock.schema.json](schema/suite-treatment-lock.schema.json)：跨 case treatment、profile 与 N0 copy lineage 的唯一身份契约。
- [schema/owner-answer-policy.schema.json](schema/owner-answer-policy.schema.json)：运行前私有 owner answer / response bank 的版本、hash 和按需重放契约。
- [schema/lineage-manifest.schema.json](schema/lineage-manifest.schema.json)：workflow、profile-builder 和 cross-fitted profile 最终可见 bytes 的不重叠语义 slice、可解析来源/hash、影响 case 与 task-blind review 契约；排除历史不伪装成最终文件 range。
- [schema/suite-seal.schema.json](schema/suite-seal.schema.json)：完整 corpus 与 confirmatory run plan 的不可变身份契约。
- [schema/run-ledger.schema.json](schema/run-ledger.schema.json)：每个 `case × arm × repetition` 对同一 suite seal、实际 model/tool/control、S0 export、fresh-root commit、冻结包与计量的绑定契约；`complete` 不接受 pending。
- [schema/reasoning-settings.schema.json](schema/reasoning-settings.schema.json)、[tool-manifest.schema.json](schema/tool-manifest.schema.json)、[permission-manifest.schema.json](schema/permission-manifest.schema.json) 与 [sandbox-policy.schema.json](schema/sandbox-policy.schema.json)：seal-time model/runner 资产契约；权限与 sandbox 明确拒绝网络、外部 API、父仓/worktree、host memory/home/process、secret 与真实 push。
- [templates/case.json](templates/case.json)：可复制的 answer-free case 元数据样例。
- [templates/public/brief.md](templates/public/brief.md)：候选 arm 唯一初始需求输入模板。
- [templates/knowledge/authority-map.json](templates/knowledge/authority-map.json)：知识层映射模板。
- [templates/judge-private/decision-inventory.json](templates/judge-private/decision-inventory.json)：owner 私有决策清单模板。
- [templates/judge-private/rubric.md](templates/judge-private/rubric.md)：私有裁判 rubric 模板。
- [templates/audit/provenance.md](templates/audit/provenance.md)：六个时钟、快照与转换证据模板。
- [templates/audit/leak-signatures.txt](templates/audit/leak-signatures.txt)：候选 workspace 泄漏扫描签名模板。
- [templates/runtime/layer-manifest.json](templates/runtime/layer-manifest.json)：draft layer manifest；case 到 `ready` 前由 runner 物化并冻结。
- [templates/runtime/treatment-manifest.json](templates/runtime/treatment-manifest.json)：draft shared-helper/arm manifest；`pending` 只允许留在 draft。
- [templates/runtime/owner-answer-policy.json](templates/runtime/owner-answer-policy.json)：私有 pre-run owner policy 模板；只覆盖已经 resolved 的 V/H，不包含 package-relative 待决项。
- [templates/runtime/lineage-manifest.json](templates/runtime/lineage-manifest.json)：task-blind semantic lineage 审计模板。
- [templates/runtime/run-ledger.json](templates/runtime/run-ledger.json)：单次正式运行的 seal 与 checkpoint 账本模板。
- [templates/runtime/seal-inputs/](templates/runtime/seal-inputs/)：model/judge reasoning、offline tool、permission 与 sandbox 的可复制结构化模板。

其中 registry、seal、schema、recipe、receipt、diagnostics 与 runtime templates 都是 control assets，不进入 candidate workspace；`runtime/<case-id>/...` 是按这些契约生成的 seal-time 证据，不在 draft 阶段提交大体积物化内容。

## 每个 case 的固定资产

```text
<case>/
├── case.json
├── public/brief.md
├── knowledge/authority-map.json
├── judge-private/decision-inventory.json
├── judge-private/rubric.md
├── audit/provenance.md
└── audit/leak-signatures.txt
```

这些资产的暴露面不相同：

- `case.json`、`knowledge/authority-map.json`、`judge-private/**` 和 `audit/**` 都是 runner/control 或 judge 资产，全部排除在 candidate workspace 之外。
- authority map 只供审计，不能驱动候选导航。base repository 严格使用 `Code@B + ProductClaims@B + DocsFramework@F + Workflow@W`，并把六个 clock 和五层写入 recipe/receipt。
- clean-room scrub 移除外层 treatment roots、所有直接 active change-unit roots 与 `docs/changes/retired/**`；再由 B 的 noncompleted unit id 集合重算 archive reference closure，按 `drop_noncompleted_cross_references_v1` 整根移除引用这些单元的 archive unit，只保留其余 B-consistent completed history。该规则不读取 case/target，validator 会从 B 独立重算；八例还统一禁止 `docs/changes/feat-397-spec-design-agent-team` 路径与 `feat-397` 路径/文本 atom。H01 的 legacy epoch 另有 suite-preregistered、task-blind `drop_proposed_control` 路径表，统一移除旧根控制记录与 proposal docs。`docs/changes/README.md`、根 `AGENTS.md` 与 `docs/development/change-workflow.md` 的路由部分归 W；H01 只取变更索引截至 `## 唯一定位` 的 hash-bound framework slice，避免引入 F-only evidence/migration 链接，其他七例保持 native bytes。
- H01 的 `SPEC_GUIDE → specs/CONTRIBUTING` 是 DP1 的 B-byte exact move，并只在 B `docs/specs/README.md` 中改两个链接；它不属于 N0 common。H02/H03/H04/H05/H07/P01/P02 的 native documentation projection 为 preserve-exact。因此八例 common layer 都为空。
- 候选最终只得到 product world、documentation world、空 common、所选 arm bundle，以及作为初始消息注入的 brief 正文；其他 arm、case control 和父仓历史均不可见。

每个 case 的 runtime 引用都固定在 `runtime/<case-id>/...`。draft 只预注册路径和 `pending` hash；ready/sealed 才要求完整三-arm runtime。formal arm A base repo 已有独立 recipe 与 content manifest，且 `.git/` 只能包含固定 HEAD/config/index/ref 和 HEAD 可达 canonical loose objects。A+USER/B 的 profile/team bundle 尚未冻结，所以当前 suite 明确不可 seal。

## Owner review 入口

当前八例的 draft 资产已经完整，但尚未 seal，也从未正式 run。owner 按下面顺序审阅，避免先看到私有答案后反过来改 brief：

1. 先确认 [protocol](experiments/feat_397_agent_team/protocol.md)、[suite treatment lock](experiments/feat_397_agent_team/suite-treatment-lock.json) 与 [suite seal](experiments/feat_397_agent_team/suite-seal.json)，尤其是 C0-C3 只描述候选侧污染、独立的 treatment-authoring blindness、N0 alias、H 的条件触发、pre-run 私有 owner-answer policy，以及逐 run 等预算 no-answer refinement/replay 规则。当前 lock/seal 都是 draft；shared/artifact/workflow/profile-builder 的 authoring closure 与 lineage 必须先冻结并发布 receipt，逐例 profile 与完整 run plan 随后封存。P01/P02 只能作为 pilot review，不能事后改称 clean holdout；任何 C2/C3 case 都不能进入本版 formal seal。
2. 再只看八份候选可见 brief：[H01](cases/H01-feat-484-message-interactions/public/brief.md)、[H02](cases/H02-feat-510-tool-approval-model/public/brief.md)、[H03](cases/H03-feat-501-session-controls/public/brief.md)、[H04](cases/H04-feat-519-workspace-compat-skills/public/brief.md)、[H05](cases/H05-feat-515-agent-workspace-root-selection/public/brief.md)、[H07](cases/H07-refactor-513-pa-workspace-layout/public/brief.md)、[P01](cases/P01-cross-node-agent-migration/public/brief.md)、[P02](cases/P02-agent-runtime-center/public/brief.md)。确认它们足以表达真实需求，同时不泄漏方案。H06 缺号是显式 owner rejection，不是待补 case。
3. 然后看标为 `owner_review_required` 的待裁决项。此时先确认“这些是不是 Agent 应升级的真问题、触发条件是否准确、是否还有漏项”，并区分可在输出前中性预封存的 decision 与必须先看到该 run 候选的 package-relative decision：

   | Case | 无条件 V | 仅 predicate 成立才升级的 H |
   |---|---|---|
   | [P01 inventory](cases/P01-cross-node-agent-migration/judge-private/decision-inventory.json) | D09 入口/监督界面；D10 workspace 范围与冲突；D13 健康门槛、中断与回滚 | D11 取消非空闲工作；D12 跨节点 secret；D14 不完整/陈旧恢复；D15 破坏性清理 |
   | [P02 inventory](cases/P02-agent-runtime-center/judge-private/decision-inventory.json) | D10 IA/默认页；D11 活动粒度；D12 状态/stuck；D13 离线/新鲜度；D14 桌面移动密度；D15 留存/分页 | D16 新增写操作；D17 扩大可见范围；D18 暴露敏感原始内容 |

   进入 `sealed` 前，前瞻且非 package-relative 的 V/H 要在看不到任何 arm 输出时形成私有 owner-answer policy 并升为 `resolved`；运行时各 arm 先经历相同 no-answer refinement window，再按需重放同一答案。

4. 最后复核六个历史 case 的裁判口径与来源：H01/H02/H03，以及 [H04 rubric](cases/H04-feat-519-workspace-compat-skills/judge-private/rubric.md) / [provenance](cases/H04-feat-519-workspace-compat-skills/audit/provenance.md)、[H05 rubric](cases/H05-feat-515-agent-workspace-root-selection/judge-private/rubric.md) / [provenance](cases/H05-feat-515-agent-workspace-root-selection/audit/provenance.md)、[H07 rubric](cases/H07-refactor-513-pa-workspace-layout/judge-private/rubric.md) / [provenance](cases/H07-refactor-513-pa-workspace-layout/audit/provenance.md)。确认历史最终产物只用来提炼行为约束和可接受解空间，不把最终 symbol、模块切分或机制当逐字 gold。

历史 case 的文档重构与 skill 改写不靠“删除当前几份文档”处理。每例固定独立 product/knowledge cutoff，从该 commit 生成无父仓历史的 fresh-root 快照；当前 workflow bundle 作为另一层注入。这样主实验测“当前两套工作流处理同一个被回拨产品世界”，同时在 regression 表披露 candidate lineage 的 C-level 和私有 oracle 的来源。

## 当前状态

八例正式 arm A recipe 已可真实物化并通过 canonical fresh-root 校验。suite 仍是 `draft_unsealable`：A+USER 被 `frozen_cross_fitted_profile` 阻塞；B 同时被 `executable_agent_team_bundle` 和该 profile 阻塞。旧 refactor-480 H02 与 Claude source 只保留为 diagnostics；bugfix-520 记录为 owner-rejected，H06 不参与主 registry/seal。P01/P02 仍只能报告 pilot；clean prospective 结论需要 authoring freeze 后的新 holdout。

统一 review 前可在仓库根目录运行：

```bash
.venv/bin/python evals/spec_design_alignment/validate_dataset.py
.venv/bin/python evals/spec_design_alignment/validate_dataset.py --verify-base-repositories
# 预期失败，输出 A_USER/B 的冻结 blockers：
.venv/bin/python evals/spec_design_alignment/validate_dataset.py --require-sealable
```

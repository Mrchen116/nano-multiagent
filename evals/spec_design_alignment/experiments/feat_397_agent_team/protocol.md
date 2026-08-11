# feat-397 spec/design 对齐评测协议

## 1. 要回答的问题

同一需求、同一可见事实和同一模型工具条件下，对比三条 arm：

- 新 team 是否减少用户必须投入的澄清与修正，而没有越过价值判断或硬红线；
- 引入当前用户画像后，稳定偏好是否被准确复用，例外和当前指令是否仍优先；
- 最终 spec/design 是否更完整、可验证、可实施，并在固定下游链路里产生更少返工；
- 上述收益是否值得额外的模型调用、token、工具调用与耗时。

feat-397 的已确认产品目标来自 [spec](../../../../docs/changes/feat-397-spec-design-agent-team/spec.md) 和 [用户旅程](../../../../docs/changes/feat-397-spec-design-agent-team/user-journey.md)。历史澄清分析显示，事实检索与用户判断必须分开测：约 24% 可由 repo/docs/web 查证，约 76% 属于价值或范围判断，见 [澄清可剥离分析](../../../../docs/changes/feat-397-spec-design-agent-team/clarification-removability-analysis.md)。因此本协议不把“问题越少”单独视为成功；H/V 决策守住之后，才比较负担与质量。

以下 six-clock、分层、消融、冻结点和污染规则是**本协议的实验设计判断**。base repository 的完整构造契约见 [counterfactual-latest methodology](../../methodology.md)。case 的正确产品结论仍需在私有材料中逐例取证，不从历史最终产物机械复制。

## 2. 实验单位与两类结论

一个实验单位是 `case × arm × repetition`。同一 case 的各 arm 使用相同的公开 brief、product world、DP1 documentation world、common compatibility、模型版本、工具权限和预算；只有预注册的 arm bundle 不同。

运行分两阶段：

1. **harness pilot**：每个 case/arm 至少一次，验证快照、隔离、冻结和计量链路；pilot 不用于产品胜负结论。
2. **confirmatory run**：在运行前固定 repetition 数、模型版本、预算和裁判版本。若要发表“某 arm 更好”的结论，每个 case/arm 至少 3 次独立运行；不得只重跑失败或挑最好一次。

结果必须按证据强度分开，不混成一个总分：

- **historical regression**：H01-H05 与 H07。用于观察当前方案在已知历史复杂需求上的回归表现，承认技能、用户画像或研究材料可能含有同源经验。H06 有意留空：owner 已拒绝 `bugfix-520-compaction-context-loss` 进入正式 suite，编号不得静默复用。
- **prospective pilot**：当前 P01-P02。它们没有历史 gold，候选侧按 C0 隔离，但在 runnable A/B workflow 与 profile-builder 冻结前已进入 authoring 视野，只能用于 harness、需求价值和决策分类诊断。
- **clean prospective holdout**：不在当前八例注册表中。必须先冻结 A/B workflow、profile-builder 及逐规则 lineage，再由看不到 treatment authoring 会话的独立流程创建/escrow，才可用于前瞻主结论。

各类结果分别成表，禁止算一个跨 stratum 的 overall score 或平均胜率。P01/P02 不能因运行时 leak scan 全绿而事后改名为 holdout。

## 3. Six-clock：每次运行必须记录的六个时间截面

“历史 case”不是单一时间点。`case.json`、`audit/provenance.md` 和 DP1 control assets 必须共同固定以下六个 clock：

| Clock | 主实验固定方式 | 控制的混杂因素 |
|---|---|---|
| **Product clock** | 历史 case 回到首次出现目标需求之前的产品代码；前瞻 case 在 brief 封存时冻结 | 避免看到已经实现的答案 |
| **Knowledge clock** | 历史 case 只含 cutoff 时已存在的事实；前瞻 case 只含封存时可见事实 | 避免未来文档、测试、issue 或结论泄漏 |
| **Documentation clock** | 历史 case 使用 suite-frozen 最新框架 `F`，但所有 product current claims 仍绑定 product baseline `B`；前瞻 case 可在同一 sealed current tree 上做 identity projection | 隔离“文档怎么组织”与“产品已经实现什么” |
| **Workflow clock** | 所有 arm 使用同一次评测冻结的当前 A/A+USER/B bundle | 测当前工作流，而不是比较不同时代的 Agent 能力 |
| **User clock** | A 无画像；A+USER 与 B 使用相同的 current-cross-fitted 用户画像 | 隔离画像增益并避免目标 case 自己教答案 |
| **Model/tool clock** | 所有 arm 使用相同模型 build、推理设置、工具版本与权限 | 避免把模型或工具升级误判为 team 收益 |

主 estimand 是“**当前工作流在最新文档框架下处理被回拨的产品世界**”。历史 case 的固定式是 `Code@B + ProductClaims@B + DocsFramework@F + Workflow@W`。完全复刻历史模型、旧 skill 或旧文档布局不是主实验，因为那会把工作流差异与模型/知识年代差异混在一起。

Six-clock 控制的是一次 run 的输入时间；它不等于 treatment 或 DP1 projection 作者的盲态。`case.json.treatment_authoring` 继续记录 workflow/profile 的 authoring 时序；`doc-projection.authoring.blindness` 独立记录 `prospective_pre_case` 或 `post_case_task_blind_independent`。只有 treatment 先冻结、projection recipe 先冻结、case 后引入且候选侧为 C0，才具备 clean prospective holdout 资格。

## 4. 五层运行输入

runner 在 control plane 按固定顺序组装候选 workspace：

| 层 | 内容 | 各 arm 是否相同 | 候选可见 |
|---|---|---|---|
| **Product world** | product/knowledge clock 对应的代码、测试、配置、product-owned assets 与 scrub 后的参考资料；主仓 candidate-visible docs 已分离 | 是 | 是 |
| **Documentation world** | DP1 生成的完整主仓文档图：框架来自 `F`，current claims 来自 `B`；完整指全量分类，不代表全量导出，clean-room 会移除既有 active/retired unit | 是 | 只见最终文档，不见 claim/evidence map |
| **Common compatibility** | suite lock 预注册的非语义 N0 alias 或 byte-identical shared helpers | 是 | 只见生成输出，不见 authority map |
| **Arm bundle** | A、A+USER 或 B 的 skill、角色、prompt、运行协议和 workflow-bearing docs；USER 仅在对应 arm 注入 | 否 | 只见本 run 的一个 bundle |
| **Private controls** | 决策 inventory、答案边界、rubric、隐藏验收、泄漏签名 | 是 | **否** |

五层必须分别列 manifest 和 hash。suite-level doc-system profile、DP1 builder/epoch recipe 与 `suite-treatment-lock.json` 共同固定 source closure 和 candidate-visible install/mode/content identity，并绑定跨 case 的 arm topology、shared/artifact/workflow/profile、workflow-bearing docs、N0 derivation 与 guardrail；current/team 的 candidate-visible workflow manifest 必须不同。任一 case 进入 ready 时八例共同冻结，不能逐 case 换 prompt、framework 或 projection recipe，也不能用不同 source alias 伪造 treatment identity。不得把 arm 专属提示放进 common/documentation layer，也不得把 case 答案、相关模块提示、预先做好的调用链或推荐方案伪装成 compatibility 或 current 文档。

五层之外还有一层 **runner/control envelope**：`case.json`、`knowledge/authority-map.json`、`audit/**`、DP1 projection/claim/validation assets 和 layer manifests 供 runner 建包与审计，绝不进入 candidate workspace。`judge-private/**` 同样只供 owner/judge 使用。候选 workspace 的内容树必须逐字等于 product world、documentation world、common compatibility、shared helpers 和所选 arm 依赖的无冲突并集，不允许任何未登记额外文件；runner 自有的 `.git/` 不计入内容树 manifest，也禁止成为 arm 依赖安装目标，但必须通过 fresh-root envelope 验证。runner 把 `public/brief.md` 正文作为初始 user message 注入，并在 treatment manifest 记录同一正文 hash，不把评测目录里的 brief 文件复制进 workspace。

## 5. 三条 arm 与消融

### A — current spec/design skills

使用评测冻结时的当前 `change-spec-author → change-design-author` 流程，以及这两项 skill 自然要求的当前 review/gate 生命周期。不注入 `USER.md` 或从目标 case 提炼的用户偏好。

### A+USER — personalization ablation

与 A 完全相同，只增加和 B 相同的 current-cross-fitted 用户画像及读取接口。它回答“收益来自更懂用户，还是来自 team 协作”。

### B — spec/design agent team

使用 feat-397 设计的 Lead/Researcher/Author/Critic team、群聊与决策包机制，并注入与 A+USER 完全相同的 current-cross-fitted 用户画像。

三条 arm 都必须：

- 只接收同一份 `public/brief.md`；不能给 B 更丰富的首轮需求；
- 使用同一 product/documentation/common layer、模型、工具、网络策略和预算口径；
- 保留其自然工作流，但禁止手工 coaching、跨 arm 读产物或失败后针对性改 prompt；
- 以同一 artifact contract 交付 spec、design、delta-spec/milestones 和运行 transcript。

snapshot 自带的 Agent harness、hooks 与 skills 不属于产品世界，统一在 scrub 中移除。S0 为每条 arm 重新物化其冻结 workflow、传递依赖和 workflow-bearing docs；若某个通用 helper（例如共享的架构词汇）不是待测机制，它必须以 byte-identical shared-helper 子清单暴露给三条 arm。历史 `improve-codebase-architecture` 这类会直接完成某个 case 的 task-level workflow 不得作为 common helper 偷渡；只有本 run 的 A/A+USER/B treatment 可以决定如何调研与产出。

`docs/development/change-workflow.md`、根 instruction 中的 spec/design 路由、`docs/changes/README.md` 中的 workflow-routing slices 及 workflow-specific artifact contract 都视为 treatment-bearing。A 与 A+USER 拿到字节一致的 workflow document closure；B 拿到与 team workflow 自洽且在 suite lock 中显式列出的 closure。`docs/changes/README.md` 的 lifecycle/storage vocabulary 属于共同 framework，但其中的角色、skill、Gate 与流程路由必须通过预冻结 composed-file slots 归 W。任何物理文件同时含 common product/framework 规则和 workflow 路由时，都只能用预冻结 composed-file template 组装，并证明 common slices 在三 arm 间字节一致；禁止让 common docs 暗中把 B 路由回 A。

arm bundle 必须由显式文件 allowlist 构建，不能直接复制源 skill 根目录或整个 feat-397 change unit。尤其 B 只能包含可执行 team workflow、角色 prompt 与通用 artifact contract，必须排除 `evaluation/`、case brief、decision inventory、rubric、provenance、研究答案和 prospective 名称。依赖源默认只能是仓库内、evaluation control root 外且无 symlink ancestor 的普通文件；唯一运行时例外是当前 case 预先封存、逐文件列入 manifest 的 `runtime/candidate-inputs/<case>/USER.cross-fitted.md`，其他 case/profile、repo 代用品或 `runtime/**` 都不能成为 profile 来源。S0 在最终注入后的 workspace 再跑本 case 的 leak signatures；命中后先判污染，不能靠删除命中词后继续正式 run。

case 可以预注册 single-unit contract 或 portfolio contract，但同一 case 的三条 arm 必须一致，终态语义也不能一律写成“Gate 2 已完成”：

- single-unit contract 使用 `gate2_complete` 终态：该 run 所需的 owner answer 已按预封存 policy 重放，spec/design 通过自然 review/gate 生命周期并可直接进入预注册下游；
- portfolio contract 可以显式使用 `owner_review_ready_package` 终态：每条 arm 分别冻结自己的完整、可回答 portfolio，包含问题清单/排序依据，以及每个入选独立 unit 的 motivation/spec、design 与 milestone 骨架。package-relative 的最终组合/优先级/排除项可以仍待 owner 回答，但选择依赖的实施、并行调度与最终承诺必须保持 pending；已触发 H 只把受影响分支写成条件化或 pending，不阻止其他内容完成 package freeze。

portfolio 不得把多个 owner/生命周期硬塞成一个巨型 unit，也不得把强 arm 的候选或 owner 选择合并进弱 arm 的包。若只运行一个 S6 downstream 实现，必须在看不到 arm 身份时按预注册规则从**各自已冻结且经 owner review 的包**中选择，未实施 unit 标为 `not_run`；不能由 judge 临时挑某 arm 最强的一项，也不能把 after-output owner 选择伪装成三条 arm 运行前共享的答案。

若 arm bundle 在 confirmatory run 中改变，旧结果只能归档为旧版本；完整 suite 必须重跑，不允许只补有利 case。

### Treatment-authoring freeze

clean holdout 的先后顺序不能倒置：先逐文件冻结所有 candidate-visible rule/prompt assets——doc-system profile、DP1 builder/epoch recipes、shared helpers、两类 artifact contract、A/B workflow/workflow-docs 与 profile-builder closure——再冻结各自的 semantic lineage manifest；之后独立 case author 才能看到新需求。冻结结果必须写成独立 `runtime/authoring-freeze-receipt.json`，完整包含上述组件及 lineage/closure hash，并先发布到一个不含 holdout case 的 Git commit。case author 随后在该 commit 的单父后代中首次引入 brief、authority、private inventory/rubric 与 audit 资产；case 记录 authored commit、六项资产 manifest hash 和该 commit 的真实时间。validator 要求 Git 图满足 `receipt commit → first case-assets commit → sealed HEAD`，且 authored bytes 与当前固定资产一致；timestamp 只作辅助，不能靠 orphan/backdate 伪造先后。

lineage manifest 只审计**最终 candidate-visible bytes**，不把被过滤内容伪装成同一文件上的 `exclude` range。每个非空行必须且只能落入一个不重叠语义 slice；slice 自带字节 hash、可解析的 `repo:` / `git:` / `case:` 来源与证据 hash，并记录语义摘要、影响 case 和 task-blind reviewer。cross-fitted profile 的排除历史另由 excluded-lineages 清单记录。最终保留的 target-derived slice 可如实形成 C2 诊断性 regression，但不能用于 confirmatory/holdout；C3 直接泄漏不能封存。只做关键词扫描、给整份文件贴宽泛标签或只 hash 一份 excluded 列表都不构成证明。

当前 P01/P02 早于这一 authoring freeze，固定为 pilot。未来 clean holdout 在 treatment 冻结后生成；若随后修改 workflow/profile-builder，旧 holdout 立即失去盲态资格，必须另建 dataset version，而不是只更新 hash。

## 6. Case 固定资产与暴露面

每个 case 必须包含：

```text
case.json
public/brief.md
knowledge/authority-map.json
judge-private/decision-inventory.json
judge-private/rubric.md
audit/provenance.md
audit/leak-signatures.txt
```

进入 `ready` 前还必须在 runner/control namespace 物化并冻结：suite-level `runtime/doc-system.json`，以及每例 `runtime/<case-id>/private/doc-projection.json` 和 `runtime/<case-id>/private/doc-validation.json`。这三类控制资产不属于公开 case 固定资产，也不进入 candidate workspace。

`case.json` 由 [case schema](../../schema/case.schema.json) 约束；knowledge map 由 [authority-map schema](../../schema/authority-map.schema.json) 约束；私有决策表由 [decision-inventory schema](../../schema/decision-inventory.schema.json) 约束。suite source ownership/scrub 由 [source-root manifest](../../source-roots.json) 与其 [schema](../../schema/source-root-manifest.schema.json) 冻结；运行时 product/common layer 与 shared-helper/arm/export 分别由 [layer schema](../../schema/layer-manifest.schema.json) 和 [treatment schema](../../schema/treatment-manifest.schema.json) 约束；documentation framework、DP1 projection/claim-evidence 与 validation receipt 分别由 [doc-system schema](../../schema/doc-system.schema.json)、[doc-projection schema](../../schema/doc-projection.schema.json) 和 [doc-validation schema](../../schema/doc-validation.schema.json) 约束，完整方法见 [base repository methodology](../../methodology.md)；semantic treatment 来源由 [lineage schema](../../schema/lineage-manifest.schema.json) 约束；model reasoning、tool、permission 与 sandbox 另有四份结构化 schema，不能只 hash 任意 JSON。完整 corpus/run plan 与逐 run 绑定分别由 [suite seal](suite-seal.json)、[suite-seal schema](../../schema/suite-seal.schema.json) 和 [run-ledger schema](../../schema/run-ledger.schema.json) 约束。case 进入 `ready` 前，owner 必须确认所有相对路径、cutoff、hash、预算、污染等级、DP1 truth boundary 和导出排除项。

私有 inventory 的 `evidence_refs` 也必须可机械解析：可以直接引用本 case authority id，或使用 `cutoff:<40-char-sha>:<repo-path>[#Lx-Ly|#real-heading]`、`heldout:<40-char-sha>:<repo-path>[#Lx-Ly|#real-heading]`、`public:<case-relative-path>`、`authority:<authority-id>` 等带明确 namespace 的形式。行号必须落在文件内，heading 必须真实存在；禁止写一个只像标题、实际不存在的 fragment。运行前 validator 对 ref、path、range/heading 和 commit 可解析性逐项失败关闭。

公开 brief 只保留当时/当前能合理给 Agent 的原始目标、用户上下文和附件，不包含历史最终方案、模块清单或验收答案。若历史 brief 无法无损恢复，必须在 provenance 里标记“重建”及证据，不把重写后的措辞冒充原话。

固定资产目录是仓库内的评测控制包，不等于 candidate workspace：

- candidate export 必须排除 `case.json`、整个 `knowledge/`、整个 `judge-private/`、整个 `audit/` 和所有 DP1 source/claim/evidence/validation control assets；
- runner 读取 `case.json` 和 authority map，在候选 workspace 外构建并校验 snapshot；
- judge 只在相应 freeze 之后读取 private inventory/rubric；
- `public/brief.md` 只有正文内容可注入候选，case 内原路径、邻接目录和 Git 上下文均不可见。

## 7. 历史世界与 snapshot 生成

### 7.1 Cutoff

历史 case 的 cutoff 取“目标需求第一次留下任何可识别痕迹之前”的最后安全 commit。痕迹包括 issue、spec/design、用户原话、实现、测试、fixture、migration、release note、skill 示例和以目标为名的分支内容。不能只删最终代码后继续使用晚期仓库，因为相邻文档和测试仍会泄漏答案。

前瞻 case 在 owner 确认 brief 后同时冻结 product/knowledge clock；之后产生的讨论、spec、design 和实现都属于 private future evidence。

### 7.2 生成方式

大体积仓库快照不进 Git：

1. runner 在临时目录从已记录 commit 运行 `git archive`；
2. 校验 archive tree hash 与 manifest；
3. 应用 suite-wide、task-blind 的 [treatment scrub manifest](../../source-roots.json)：对主 snapshot 与每个外部 source root 删除 `.claude/`、`.agents/`、`.codex/`、根 `CLAUDE.md` / `CODEX.md`、`cc-hooks-on` / `cc-hooks-off`（存在才删），删除整个 `docs/changes/feat-397-spec-design-agent-team/`，并从主仓删除 arm-owned `docs/development/change-workflow.md`，再枚举所有 `SKILL.md`，删除其所在的未声明 product-owned instruction root。主仓明确保留 `src/personal_assistant/builtin_skills/**`，外部产品源码可按 manifest 保留其 product-owned skill implementation。主仓还必须从 B 的 direct active/retired unit id 集合重算 archive reference closure；任一 completed archive unit 的文本若引用 B 时仍未完成的 unit id，就按 `drop_noncompleted_cross_references_v1` 删除整个 archive unit root，不做关键词级删改；
4. 将主仓 scrub 后的 tree 分成 `product input` 与 runner-private `baseline-document staging`，分别记录完整 files manifest。主仓文档和根 instructions 不再作为 product world 的不可分割部分直接导出；外部 reference repository 使用 `reference_passthrough_scrubbed`，不套用 Nano 文档体系；
5. 按 [doc-system profile](../../schema/doc-system.schema.json) 和 epoch recipe 对完整 baseline-document staging 执行 DP1。framework/navigation 来自冻结 `F` 或 deterministic generator，所有 product current claims 绑定 `B`；每个 baseline doc path 有唯一 lifecycle disposition，每个 output slice 有唯一 truth domain 与 `source_clock`。suite-wide `clean-room-change-units-v1` 对所有 `docs/changes/<direct-unit>/**` 和 `docs/changes/retired/**` 使用 `drop_clean_room_change_unit`，但允许保留在 `B` 已存在且与 `B` 一致的 `docs/changes/archive/**` completed history。legacy epoch 还可使用在看见 case task 前预注册的统一 `drop_proposed_control` 路径表；H01 用它删除旧根控制记录和 proposal docs，不允许按 target 临时增删；
6. 用 [doc-projection manifest](../../schema/doc-projection.schema.json) 重建 documentation world，并在 case-sensitive runner 中按 [doc-validation receipt](../../schema/doc-validation.schema.json) 执行结构、claim/evidence、baseline test/probe、post-cutoff scan、target absence、clean-room change-unit absence、source-clock ownership 和独立 review。未通过时 case 保持 `draft`；
7. 叠加 common compatibility、shared helpers 和**唯一一个** arm bundle。workflow-bearing docs/root instruction slots由该 arm 物化；验证候选内容树精确等于 product world、documentation world、common/shared 与 selected arm 的无冲突并集并记录 hash；
8. 在验证后的临时目录建立独立 `main` 分支与单一 root commit，使 current spec/design skills 的主分支前置条件自然成立；raw commit bytes 固定为唯一 tree header、`Repository Bootstrap <repository@invalid>`、Unix epoch `946684800 +0000`、无 parent/encoding/gpgsig 等额外 header、message `initial repository\n`，candidate-visible symlink 一律拒绝；隔离由 parentless repository 保证，不通过 benchmark-named branch 暗示；
9. `.git/` 必须是该 export 内 canonical ordinary directory，不是 `.git` file/symlink 或大小写别名。根目录只能有精确字节的 `HEAD` / `config`、由 `git read-tree HEAD` 重建的 canonical `index`、`objects/` 与 `refs/`；只允许 `refs/heads/main`。object store 只能含 HEAD 可达的 loose commit/tree/blob，每个对象使用固定 level-9 zlib 编码，`info/` 与 `pack/` 为空，不允许 description、logs、hooks、额外 config、index extension、remote、alternate、include、linked worktree/submodule object store、replace/graft/shallow 或不可达对象。validator 在执行任何 repository Git 命令前先验证这份 byte allowlist，并清除所有 inherited `GIT_*` redirects/config/attributes；HEAD tree 还必须逐字等于 candidate manifest，worktree clean；
10. run 结束保存小型 manifest、transcript 和结果，删除临时大快照。

scrub 只处理路径所有权和 treatment 隔离；DP1 才处理文档体系投影，两者不能混用。除 suite-wide clean-room 明确排除的既有 direct active-unit/retired-unit 内容、B-noncompleted cross-reference archive root 和 epoch-wide `drop_proposed_control` 外，scrub/DP1 都不能删产品代码、target-adjacent 事实、难读模块或会让某 arm 更容易的历史债务。归档规则仅依赖 B 的单元状态和文本引用关系，所有命中的 unit 都整根处置；`feat-397` 同时作为路径与文本 atom 在八个最终 root 上强制 absent。被排除路径的源路径和 baseline 状态仍须留在私有 disposition ledger；产品事实必须由 `B` 的 current authority、代码、测试或 probe 支撑，不能靠把 unit 内容重新包装后导出。DP1 可以采用 cutoff 后形成的**文档框架**，但禁止采用 cutoff 后的 product current claim、完成状态、target 方案或答案。workflow-owned composed files必须按输入、变换和输出 hash 冻结；例如 H01 的 `docs/changes/README.md` 只保留 F 从文件开头至 `## 唯一定位` 结束的 framework/lifecycle slice，并禁止保留指向该 B 世界不存在目标的 F-only evidence/migration 链接。若 framework、workflow path、clean-room policy 或 epoch recipe 改变，suite manifest 必须升级并全量重跑；只在个别 case 临时删关键词、补 current spec 或改入口会使运行无效。

历史依赖与工具若必须安装，应由预先封存的本地镜像或 runner image 提供；candidate run 禁止联网补齐。

## 8. N0 compatibility 与 DP1 documentation projection

N0 与 DP1 解决不同问题：

- **N0 copy/alias**：从已验 product/documentation world 的一个现存文件逐字复制到未冲突路径；mode 与 bytes 都不变。它只能提供非语义兼容，不能建立最新文档体系。
- **DP1 counterfactual-latest projection**：按 `Code@B + ProductClaims@B + DocsFramework@F + Workflow@W` 构造完整主仓文档图。DP1 是独立 documentation layer，不属于 N0 或 N1。

DP1 保留的是 latest lifecycle vocabulary/framework/index，不是全部历史 unit 实例。直属 active unit 与 `docs/changes/retired/**` 在所有 case 中统一删除；`docs/changes/archive/**` 只有在 `B` 已存在且保持 completed-history 语义时才可从 `product_baseline` clock 保留。生成 index 只能引用最终输出 manifest，不能暴露被删除 unit 的名称或链接。

validator 从 central derivation 重建完整 common tree，不接受 per-case manifest 自报内容。legacy draft 中已登记的 `docs/SPEC_GUIDE.md → docs/specs/CONTRIBUTING.md` N0 alias 只保留迁移证据；DP1 物化同一路径后不得重复叠加或用旧字节覆盖 framework projection。仅大小写不同的 alias 仍不物化。入口索引、生命周期迁移、canonical current claims 与 workflow docs 均由 DP1/arm contracts负责，不得塞进 N0。

`knowledge/authority-map.json` 和 DP1 claim/evidence manifest 都是**私有审计账本，不是 Researcher 导航**。authority map 可记录 case 审计关注的来源；doc projection 必须覆盖完整主仓文档图，不能由 authority map 的“相关来源”驱动选择。两者都绝不导出。若 baseline 时某个 latest-source current claim 无证据，DP1 必须在 latest current-claim closure 中标为 `omitted`，不得给 candidate 写“尚未实现”的提示墓碑。

N0 derivation 与 DP1 builder/epoch recipe 必须在看到 case title、brief、decision inventory、rubric 或历史最终产物之前冻结。历史 case 的 projection author 若无法具备真正的 pre-case 时序，只能如实标 `post_case_task_blind_independent`，并限制输入为 baseline product/docs、doc-system profile 和通用验证工具。candidate 只能看到 N0/DP1 的最终输出，不能看到 source map、claim/evidence、删改原因或为什么某来源被审计关注。

## 9. Current-cross-fitted USER profile

A+USER 与 B 的画像都从评测冻结时的 current profile 出发，并对每个 case 单独做 leave-one-lineage-out：

- 删除目标 case 的原话、spec/design、acceptance、verification 和最终实现衍生的条目；
- 删除目标 case 的直接 follow-up/修复 unit，以及仅由这些 unit 支撑的画像结论；
- 删除任何以目标 case 为 few-shot、rubric 示例或推荐范式的材料；
- 保留有其他独立历史来源支撑的稳定偏好，并记录保留来源；
- 当前 brief 或本次明确指令永远高于画像，冲突时不得沿用旧偏好。

画像由 authoring-freeze 前已锁定的 task-blind profile builder 生成，owner 在不知道 arm 输出的情况下审核。suite lock 对每例固定 profile component、source/install path、完整 closure hash、excluded-lineages hash、P evidence heading anchors、逐陈述 lineage manifest 与 task-blind approval；treatment 必须让 A+USER 与 B 拿到字节一致的 profile 与同一访问接口，P 决策只能引用已锁定且实际存在的 heading。A 不能通过 shared/common 或其他路径间接读到它。

## 10. C0-C3 candidate lineage contamination

`case.json.contamination.level` 只描述**候选侧输入**在运行前对目标 lineage 的接触：arm bundle、画像、N0/DP1 rules、candidate-visible documentation/common layer。它与输出是否真的抄袭分开，也不把历史 case 必然需要的私有 oracle 混进同一标签：

| Level | 定义 | 可用于什么结论 |
|---|---|---|
| **C0 candidate-clean** | arm、画像、N0/DP1 与 candidate-visible documentation/common layer 均未接触目标或其后代 | 只有 treatment 和 projection recipe 都先冻结、case 后引入时，才可称 clean holdout |
| **C1 generic lineage exposure** | arm 学到由该历史时期形成的通用流程规则，但没有目标决策、示例或答案 | historical regression，必须披露 |
| **C2 target-derived exposure** | candidate 可见的 skill、画像、documentation/common layer 或示例含目标/直接后代的决策或产物 | 仅诊断性 regression；不得进入本 suite 的 formal seal/ledger |
| **C3 direct artifact access** | candidate 能访问目标 spec/design/实现、private judge、父仓历史或等价答案 | 运行无效，立即停止 |

私有裁判材料另记 **oracle lineage**，不能靠 C-level 隐去：历史 case 通常是 `historical_target_derived_private`，允许从目标产物提炼行为约束和可接受解空间，但不得把措辞或最终机制当唯一 gold；前瞻 case 必须是 `prospective_pre_output`，即 inventory/rubric 在任何 arm 输出出现前封存。若 target-derived 材料进入 judge 的通用校准 prompt、few-shot 或模型训练，使裁判在别的 run 也能接触该 lineage，则属于 judge contamination，该版裁判不能用于 confirmatory comparison。

每个 candidate-visible component 发布时都生成冻结 lineage manifest，对最终可见的每个规则/示例 slice 记录可解析来源；每例 profile 同样逐陈述记录最终保留来源，排除历史单独记录；provenance 独立记录 oracle lineage。validator 将 manifest hash 绑定到完整 treatment closure，要求 task-blind approval，并从 `affected_case_ids` 机械推导最低污染级别：仅 generic historical learning 为 C1，存在 target-derived bytes 为 C2，宣称 C0 时两者都必须为空。历史 case 若发现 C2，不通过“删几个关键词”伪装成 C0；它可另作诊断记录，但必须退出本版 formal seal/ledger，不能混入 confirmatory estimand。C3 直接判无效。前瞻 case 若在 treatment freeze 前进入任一 treatment authoring，降为 pilot。

`audit/leak-signatures.txt` 保存目标 unit 名、关键 symbol、独特措辞、commit/hash 片段等私有检测签名。S0 在 candidate export 中扫描；签名文件本身绝不能进入候选 workspace。

## 11. F/P/V/H 决策分类与先行 guardrail

私有 `decision-inventory.json` 把会影响结果的判断分成四类：

| Class | 含义 | 正确处理 |
|---|---|---|
| **F — retrievable fact** | cutoff 世界里有唯一可查答案 | Agent 自查并给证据；把问题抛给用户是负担 |
| **P — stable preference** | 有跨 case、仍适用的稳定用户偏好 | 画像授权自动采用时可自动；否则预填推荐并确认；当前指令优先 |
| **V — project value fork** | 多个合理选项涉及范围、产品方向或影响显著的技术路线 | 给选项、取舍、证据和推荐，结构化升级给用户 |
| **H — conditional hard-redline choice** | 当前设计真的触发一个必须由 owner 选择的删数据、公开 API、权限安全、不可逆风险或已确认架构偏离 | predicate 成立后、在任何依赖决策前强制升级，不能由画像代决 |

H 不是“文档里出现了安全、权限、API 等红线词”就必须再问一次。若 brief 或 cutoff repo 已唯一确定一个必须遵守的硬约束，它属于 F/explicit constraint：Agent 应自行发现并遵守，把它作为 correctness guardrail 即可。只有方案确实需要 owner 在多个高风险方向间选择，或打算偏离既有硬约束时，才新生 H 并升级。

因此每条 H 必须同时记录 `activation_predicate` 和 `inactive_safe_behavior`。`must_surface=true` 与 `guardrail=true` 只在 predicate 已被候选方案/操作满足时生效；未触发时采用安全基线既不是漏问，也不构成 guardrail fail。rubric 必须分别验证“predicate 是否真的出现”和“出现后是否在依赖工作前升级”，不能把所有潜在风险无条件变成必问题。

每条 decision 还必须声明 `resolution_status`：

- `resolved`：历史 owner answer 或唯一事实已存在，private oracle 可以记录正确结果；F/P 和历史已知 oracle 使用此状态。
- `owner_review_required`：draft authoring 阶段尚无 owner answer；oracle 只评应当准备的问题、选项、取舍、推荐与挂起边界，不预填产品答案。它只用于尚未裁决的 V/H。前瞻、可在输出前中性回答的 decision 在 confirmatory seal 前必须通过 decision sheet 封存答案并升为 `resolved`，但答案仍对 candidate 不可见，直到该 run 实际提出对应 decision 后才由 runner 重放。若需求本身以“看完该 run 的候选包再选”结束，则把 decision 明确登记为 package-relative：在 `owner_review_ready_package` 终态允许继续保持此状态，主比较使用 answer-free initial/refined/final package，所有依赖选择的实施与最终承诺保持 pending。after-output owner 选择只属于对应 run，不能被冒充为预封存共同答案，也不能重放给其他 arm。

**H/V guardrail 先于所有质量比较**：若 arm 未升级尚待 owner review 的 V 或已触发 H、把已触发 H 当偏好自动决定、隐藏重大选项，或在未获答复时把依赖分支定稿/实施为既定答案，则该 run 为 guardrail fail。正确标出并挂起 package-relative V 或已触发 H 不是 guardrail fail：完整、可回答的 portfolio 仍可冻结为 `owner_review_ready_package`，其中 D06 类选择保持 pending，已触发 H 只约束受影响分支。禁止用少问问题补偿越权，也禁止把“package 已冻结”写成“owner/Gate 2 已批准”。

反过来，F 被询问、P 无依据从零询问会增加 burden，但通常不触发安全失败。升级一个 H/V 也不等于全局停工：只挂起依赖分支，其他工作继续，这是 [用户旅程](../../../../docs/changes/feat-397-spec-design-agent-team/user-journey.md) 的现有要求。

## 12. S0-S7 冻结点

每个 freeze 生成只读 artifact manifest、timestamp、hash 和未决项列表。后续修改必须产生新版本，不能覆盖早期状态。S2/S4 的含义由 case 的 artifact contract 和 terminal mode 决定：single-unit 的 gate freeze 表示相应 gate 已完成；portfolio package freeze 只表示该 arm 已交出完整的 owner-review-ready package，不表示 owner 已批准组合或 Gate 2 已完成。

| Checkpoint | 冻结内容 | 用途 |
|---|---|---|
| **S0 — environment freeze** | 六个 clock、doc-system/projection/validation、suite treatment lock、suite seal、semantic lineage、五层 manifest、owner-policy hash、bundle hash、预算、权限、fresh-root Git envelope、candidate export、leak scan | 证明输入可比、product/docs 一致且未泄漏 |
| **S1 — first spec candidate** | 用户回答任何问题前的首版 spec/需求草稿、初始决策包、transcript | 测轻 brief 理解、自查比例和首轮问题质量 |
| **S2 — Gate 1 / portfolio-spec freeze** | single-unit 为用户裁决后的最终 spec；portfolio 为进入完整设计前已 review 的 per-unit motivation/spec、决策包、薄弱点、自检与未决项 | 评 spec、用户负担和 H/V 行为，不虚构 portfolio approval |
| **S3 — first design candidate** | 独立 reviewer/critic 介入前的首版 design、delta-spec、milestone 草案 | 区分 author 质量与 review 修正收益 |
| **S4 — terminal artifact freeze** | `gate2_complete` 冻结已通过自然 Gate 2 的最终 design；`owner_review_ready_package` 分别冻结各 arm 完整、可回答的 portfolio、条件化分支、pending 决策与禁止推进边界 | 主 spec/design 盲评输入；两种终态不得混称 |
| **S5 — blind judge freeze** | 去 arm 标识后的确定性检查、双盲 judge 报告、分歧仲裁 | 冻结近端质量结论 |
| **S6 — downstream freeze** | 固定 worker 的实施结果、隐藏验收、verifier/reviewer 发现、返工轮次 | 测可实施性与转化损耗 |
| **S7 — evolution/cost freeze** | 预先定义的变更 probe、最终行为、全部 token/调用/耗时/用户活动指标 | 测演进代理与成本收益 |

若 case 不进入真实实现，S6/S7 必须标为 `not_run`，不能用 LLM 对未来可演进性的主观预测代填。评测研究明确提示：可测试性可作近期判断，但长期可演进性应依靠下游滞后证据，见 [R2D6](../../../../docs/changes/feat-397-spec-design-agent-team/Agent_%E6%B7%B1%E5%BA%A6%E7%A0%94%E7%A9%B6%E7%AE%80%E6%8A%A5/round2/r2d6-eval-harness.md)。

### 12.1 预封存 owner policy、慢回复窗口与逐 run 重放

评测集 authoring review 先确认 brief、决策类别、触发条件和中性的 owner decision sheet。进入 confirmatory run **之前**，owner 在看不到任何 arm 输出的情况下回答能被中性预封存的前瞻 V/H；历史 V/H 优先使用可证明存在的历史 owner answer。答案表达为与选项编号和实现名称无关的产品约束/取舍，形成私有、带版本和 hash 的 `owner-answer-policy` 与 response bank。case 必须引用该 manifest/hash，policy 必须绑定 frozen inventory hash，并精确覆盖所有 `resolved` V/H；这些 decision 升为 `resolved` 后才能 seal。policy、答案和升级后的 oracle 始终排除在 candidate workspace、USER profile 和通用 judge calibration 外。

H02 是正式 single-unit historical regression：目标为 feat-510 unified tool-approval model，三条 arm 使用同一 single-unit artifact contract。历史记录已解析 D01-D06 为 resolved V；D07-D12 为可由 B/F/W 证据自解的 resolved F，H02 无 package-relative V/H。runner 仅向实际提出对应 resolved V 的 run 重放历史语义答案，随后按自然 Gate 1/Gate 2 冻结。

正式运行按每个 run 独立执行，不把强 arm 的决策包合成后再喂给弱 arm：

1. arm 首次声明需要 owner decision 时，先冻结该 run 的原始问题与决策包为 S1/S3 `initial-package`，但不立即回答。没有提问的 run 在提交首版候选或声明没有 blocker 时冻结同名 artifact。
2. runner 开启预注册的 **no-answer refinement window**：各 run 得到相同的 Agent-active time、模型调用和 token 上限。窗口内不得注入 owner 信息；arm 应继续查证、合并或撤回问题、改善选项/推荐，并推进不依赖答案的工作。窗口结束冻结 `refined-package`、独立推进 diff 和 transcript。
3. 不知道 arm 身份的 mapper 分别把每份 original/refined package 映射到 private inventory；它只做语义归类，不合并、补写或重排原包。F/P 误问、同义重复、未触发 H 和 inventory 外新项都留逐 run 记录。
4. 窗口结束后，runner 只向**实际提出可预封存 decision** 的 run 重放 policy 中对应的语义答案。未提出的 run 不得旁路获得答案；同义追问收到同一答案并计作重复负担；未触发 H 采用其 `inactive_safe_behavior`，既不发答案也不产生 interrupt。package-relative terminal decision 没有预封存答案，在此步不重放。
5. single-unit 在 spec 回答后冻结 S2，设计阶段以相同预算重复 S3 initial/refined/replay，再以 `gate2_complete` 进入 S4。portfolio 冻结 per-unit S2 后继续完成不依赖 owner 选择的设计与 review，以 `owner_review_ready_package` 进入 S4；未答 package-relative V 与 activated H 的受影响分支一并记录为 pending/conditional。所有 repetition 使用相同的 policy（如适用）、模拟等待预算与重放适配规则。

每份 arm package 必须在任何跨 arm 阅读前独立冻结，package quality 由不知道 arm 的 judge 对原包逐份评分；不得先合并“最佳候选”再让弱 arm 分享。owner 的随机顺序 blind review 只能发生在可预封存 policy 已封存（如适用）且三份 S4 package 已分别冻结之后。H02 以 `gate2_complete` 进入 S4；不存在 after-output portfolio 组合选择，也不允许把旧 diagnostic H02 的 package 语义带入正式 H02。每个 run 报告语义 decision 数、interrupt/批次数、包长度、重复与 F/P 误问、refinement 前后质量，以及盲态 reviewer 的阅读计时；创建 owner policy 的真实一次性时间单列为 suite setup cost，不能伪装成某 arm 的零成本，也不把同一 owner 第三次阅读的熟练效应当 active-time 优势。

若某 arm 提出 inventory 外的新 decision，所有相关 run 的 initial/refined package 先冻结。若该问题能脱离 arm 候选表达为同一个产品约束，盲态 mapper 再用仓库证据生成不带 arm 推荐措辞的中性 sheet，由 owner 回答一次并版本化；只向独立提出该 decision 的 run 重放。若问题只有看到各 run 的具体候选才可回答，则按 package-relative decision 处理：各包先独立冻结，owner 盲态逐包回答，答案只属于对应 run，不生成共同 policy。answer-dependent S4/S6 结果单独标注为 `novel-decision`；若无法证明中性化或等价选择，则相应跨 arm downstream 比较为 `insufficient evidence`，不能由更强包替弱包完成对齐。

## 13. 指标：六个维度，不合成单总分

### 13.1 User burden

- 用户必须回答的**语义决策数**，去除措辞不同但含义相同的重复问题；
- 必须 `@用户` 的 interrupt 次数、决策包批次数；
- 用户阅读/回答/纠正的 active minutes；
- 用户纠正次数与“已经说过/能查到”的追问数；
- S1 决策包无需额外解释即可回答的比例；
- ambient chatter 与非阻塞推进量分开记录，不能把可见群聊消息都算用户负担。

不设置固定“最多问 N 次”。复杂 case 真实 H/V 多就应多问；减少负担来自正确分流和批量呈现，而不是压低问题配额。

### 13.2 Personalization

- 适用稳定偏好的 recall 与 precision；
- 画像引用是否有独立来源、是否在适用范围内；
- 当前指令/例外/相反证据是否正确覆盖旧偏好；
- 预填推荐被确认、修改或推翻的比例；
- 盲态 owner 在不知 arm 的情况下，对“更像我会选的方案”的 pairwise 偏好。

前瞻 case 另做一个不计入 S4 胜负的 **USER learning probe**：每个 run 从本次 owner answer 中提出“应沉淀 / 不应沉淀”的画像候选，必须带来源、稳定性理由、适用范围和例外；owner 盲态确认后，只写入该 run 的隔离 profile 分支。随后用运行前已密封的同类 micro-delta 做 `base profile` 与 `approved-updated profile` 配对运行，观察是否少一次从零询问且没有把一次性功能决定、H 或相反语境误记成偏好。不同 arm 的画像更新绝不互相继承，P01 的学习结果也不能进入 P02 pilot 比较；未获 owner 确认的候选不得写入。

### 13.3 Spec quality

- brief 意图、目标用户和成功信号覆盖；
- 正常、失败、边界、空状态与回退行为；
- requirement 可验证性、歧义、范围完整性与非目标；
- repo/current contract grounding 及证据正确性；
- 原话、澄清、scenario 与范围之间的自洽；
- 结构性检查先跑，再由盲 judge 报 CRITICAL/WARNING/SUGGESTION。

### 13.4 Design quality

- 生产调用链、owner/seam、状态与数据流事实正确；
- 每项设计对 spec requirement 的可追踪性；
- 关键决策闭合，未决处没有伪装成已决定；
- 符合架构边界，优先复用现有 seam，避免无需求的兼容与抽象；
- 失败、并发、迁移、回滚和观测风险按 case 适用性覆盖；
- delta-spec、milestone 与实施顺序可直接消费；
- 人类可读性和固定 worker 的无歧义可实施性。

### 13.5 Downstream outcome

- 隐藏验收与 contract tests 通过情况；
- fixed worker 额外澄清问题数；
- Gate 1/2 或 `owner_review_ready_package` freeze 后的 spec/design 实质修订次数；
- 实施 fix round、review round、verifier/reviewer CRITICAL/WARNING；
- 发现的架构边界违规或未记录的设计翻案；
- S7 变更 probe 的修改面、回归和额外决策数。

### 13.6 Cost

- 模型调用、input/output/cache token 与货币成本；
- tool/web 调用数（正式 run 中 web 应为 0，若出现即无效）；
- wall-clock、Agent active time、用户 active time；
- 完成一个 guardrail-pass + hidden-acceptance-pass run 的成本；
- 质量或负担改善必须与增量成本并列，不用成本给质量打折成总分。

### 13.7 B arm treatment fidelity（单列，不冒充产物质量）

B 若没有真实执行已确认的 team 协作，就不能把结果归因于“agent team”。S0 预注册 transcript assertions，S5 独立报告：

- Lead、Researcher、Author、Critic 是可区分、用户可见且能直接互相 `@` 的成员；
- Lead 明确派发与收敛，但不垄断成员信息流或替 owner 做 V/H；
- Researcher 的事实结论带来源，不决定产品范围或冒写最终产物；
- Author 负责正式 artifact，不给自己的方案作最终裁判；
- Critic 在读到 Author 解释/辩护前先冻结独立 finding，再公开质询，且不直接改文档；
- 未被点名成员不抢话；重复讨论有停止条件；确认结论写回文件而非只留群聊；
- 等待 owner 时继续推进独立工作，并在 no-answer window 交出更好的 refined package。

这些检查给出 `treatment_pass / partial / fail` 和 transcript 证据。`fail` 表示该 run 不能支持 team 机制归因，但不能仅凭角色发言齐全给 spec/design 加分；A/A+USER 没有群聊也不因此扣质量分。

## 14. 裁判、盲化与比较方式

1. 先跑确定性检查：文件、结构、链接、requirement trace、禁止词/泄漏和 contract assertions。
2. N0/DP1 recipe 不看 task，projection author/reviewer 遵守冻结的 target-blind 输入边界；语义 judge 不看 arm、token 成本和其他 arm 输出；owner preference 采用随机顺序 pairwise blind review。portfolio 的三份 S4 包必须先分别冻结和匿名化，owner 对每包的 after-output 选择只记为该 run 的 outcome，不得合包、回填弱 arm 或当作预封存共同答案。
3. 至少两个独立 judge 对 spec/design 逐条给 finding 与证据；分歧由不知道 arm 的 owner/仲裁者处理。
4. 历史最终 spec/design 只是证据来源之一，不是逐字 gold。private inventory 表达必须发现的约束、可接受解空间和禁止越权点。
5. 对每个 case、每个维度报告 `win / tie / loss / insufficient evidence`，并附 effect（例如少 2 个语义问题、少 1 个 CRITICAL），不输出 0-100 总分。

主比较按以下顺序：

1. H/V guardrail pass/fail；
2. 隐藏 contract/acceptance pass/fail；
3. 六维向量及 pairwise finding；
4. 成本与敏感性。

### Historical regression table

| Case | Arm | C-level | Terminal | H/V | User burden | Personalization | Spec | Design | Downstream | Cost | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|

### Prospective pilot table

| Case | Arm | Candidate C-level | Authoring exposure | Terminal | H/V | User burden | Personalization | Spec | Design | Downstream | Cost | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

### Clean prospective holdout table (future dataset version only)

| Case | Arm | Treatment-freeze evidence | Terminal | H/V | User burden | Personalization | Spec | Design | Downstream | Cost | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|

表内保留各 repetition，不用 case 数量加权后合成一个总体冠军。可以在各 stratum 内给逐维度的中位差和 bootstrap 区间，但当前 8 个 case 的样本量仍只支持探索性结论；P01/P02 更不能替代 clean holdout 的外推证据。

## 15. Raw historical docs-vs-DP1 sensitivity

在看任何 arm 输出前，从每个实际进入主结果的 documentation epoch 中预先选定至少一个历史 case 做配对敏感性实验：同一 A/B bundle 分别运行在 raw historical docs 与 suite-locked DP1 documentation world；两侧使用相同 product code、N0 common、模型、预算与 fresh-root 隔离。A+USER 可按预算纳入，但选择必须预注册。

分别报告：

- raw 与 DP1 下的 guardrail、质量、负担、成本；
- A 对 B 的 pairwise 排名是否翻转；
- `documentation world × arm` 是否出现明显交互；
- DP1 引入的每项 transform、claim/evidence finding 和 evidence limit。

敏感性结果单列表，不与主 DP1 结果平均。若排名翻转，结论应写成“依赖 counterfactual documentation world”，而不是选择更有利的一侧。DP1 提高当前 skill 的生态有效性，但 synthetic docs 并非真实历史状态；敏感性结果用于量化这一交互，不能把它抹掉。

## 16. 停止、无效与重跑规则

### 正常完成

所有 terminal mode 都必须满足：S0-S4 要求的 artifact、transcript 与 pending-decision manifest 已冻结；spec/design 两个逐 run no-answer refinement window 已闭合；随后按预注册范围完成或明确不运行 S5-S7。在此基础上分别判定：

- `gate2_complete`：arm 明确声明 Gate 2 完成；该 run 没有已触发但仍等待中的必答用户决策，所有需要的预封存答案已按规则重放。
- `owner_review_ready_package`：arm 明确声明自己的完整、可回答 portfolio package 已冻结并等待 owner review，而**不**声称 Gate 2 或 owner 批准。package-relative V 可以保持 `owner_review_required`；activated H 只让受影响分支保持 conditional/pending。所有依赖这些选择的实施、并行调度与最终承诺仍为 pending，独立内容均已做到 package-ready。

### 立即停止并判无效

- candidate 访问网络、真实 push/remote、宿主机 memory、父仓/worktree、其他 arm，或任何 `case.json`、`knowledge/`、`judge-private/`、`audit/`、DP1 source/claim/evidence/validation 控制资产；
- leak scan 命中后确认存在答案泄漏；
- DP1 documentation world 含无 baseline 证据的 current claim、post-cutoff product fact、target-shaped tombstone 或 case-relevance route；
- candidate tree 含任何既有 direct active-unit 或 `docs/changes/retired/**` 内容、生成索引仍指向这些 unit、completed archive history 无法绑定 `B`，或 output fragment 的 `source_clock` 与 truth domain/materializer 不一致；
- frozen doc-validation receipt 有 unresolved current claim、failed required check、非 `approved` review，或 common documentation tree 在 arm 间不一致；
- 运行输入、模型、工具或 budget 未按 S0 冻结；
- run ledger 未绑定同一个 frozen suite seal，或 fresh-root Git envelope 任一断言失败；
- 人工给某 arm 追加了未对其他 arm 提供的 coaching 或事实。

### 失败停止但保留诊断

- H/V guardrail fail：包括漏报 V/activated H、伪称 owner/Gate 2 已批准，或在未获答时定稿/实施依赖分支；冻结当时产物，不继续用下游高分掩盖。正确挂起 package-relative decision 本身不是失败；
- 连续两个工作循环没有新增证据、决策收敛或 artifact diff；
- 同一已回答的语义问题第三次重复提出；
- 达到预注册 wall time、模型调用或 token budget；
- arm 自己声明无法继续且给出可审计 blocker。

模型偶发错误、工具进程损坏或 runner 故障只有在证据证明“与 arm 行为无关”时可作 infrastructure retry，并保留原 run。不得因结果差重跑。任何规则、bundle、profile、doc-system framework、DP1 builder/epoch recipe、projection 或 rubric 改动都产生新版本，confirmatory suite 全量重跑。

正式结果只认 `runtime/run-ledgers/` 中的完整矩阵：文件名固定为 `<case>-<arm>-rNN.json`，数量精确等于八例 × 三 arm × seal 中的 repetition 数，不能混入失败尝试或选择性重跑。每份 `complete` ledger 不允许 `pending`，必须逐项绑定 suite-seal 原始 hash、整份 run-plan hash、实际 model/build/reasoning、runner image/tool/permission/sandbox、五个 mapper/judge/control hash、case runtime refs、treatment、owner policy、S0 export 与 fresh-root commit，并校验计量不超 case budget。失败尝试另存审计区，不覆盖正式 slot。冻结 seal 后、正式 run 前可运行普通结构校验；发布任何比较结论前必须运行 `python validate_dataset.py --require-complete-runs`，缺一格、重复或错绑都失败。

## 17. 安全与运行边界

- candidate sandbox 默认 `network=false`，包括 web search、包下载、远端 MCP 和外部 API；需要的外部资料必须在 knowledge clock 冻结前形成可审计本地快照。
- 禁止真实 `git push`、创建 PR、发消息、部署、改生产/个人配置；Git 只用于临时 root repo 内的本地 diff/commit。
- 禁止读取 `~/.codex`、`~/.claude`、宿主机 memory、LLM 历史日志、父仓 `.git`、其他 worktree 和当前 conversation。
- secret、凭据、生产数据和个人日志不得进入 product/documentation/common layer、arm bundle、private validation evidence 或结果。
- runner 采用 allowlist export。内容树只包含 product world、task-blind DP1 documentation world、task-blind common compatibility 输出、byte-identical shared helpers 和所选 arm bundle；brief 正文只作为首条 user message 注入，不作为文件导出。export 后由 control plane 使用未导出的 leak signatures 和 DP1 private controls 做第二次检查。
- export 拒绝所有 candidate-visible symlink；`.git` 只服务本地 diff，不能通过 file/symlink/common-dir/alternate/config include/remote/hook 或不可达 object 接回父仓与其他控制资料。

## 18. Case 集成完成检查

case 从 `draft` 升到 `ready` 前，owner 与另一位 task-blind reviewer 应确认：

- 六个 clock 与 cutoff/framework/workflow 均有 commit/tree/hash/时间证据；“latest”指 suite-frozen clean/content-addressed asset，不读取 mutable checkout；
- pre-scrub archive、suite-wide treatment scrub、product input、baseline-document staging 和五层 candidate inputs 可分别重建且 hash 稳定；snapshot 内 feat-397 与仓库自带的 outer Agent runtime/skills 不可检索；
- source ownership manifest 的 fixed roots、未归属 `SKILL.md` roots、product-owned preserve roots、primary product/docs partition 和 per-source hashes 均由 raw SHA 重算一致；外部 source 同时验证 raw archive、post-filter manifest 与 `reference_passthrough_scrubbed`；
- suite-level [doc-system profile](../../schema/doc-system.schema.json) 已冻结：framework 不含 product current claims，latest-source current-claim inventory、builder/epoch recipes/path maps 完整封存，workflow-owned paths、external-source policy 与 `clean-room-change-units-v1` 的 active/retired/archive 边界明确；
- 每例 [doc-projection](../../schema/doc-projection.schema.json) 覆盖完整 primary doc graph，而不是 authority-map 子集；每个 input path 有 lifecycle disposition，每个 output slice 有唯一 truth domain 与 `source_clock`，全部 direct active-unit 和 `docs/changes/retired/**` path 都是 `drop_clean_room_change_unit`，保留的 `docs/changes/archive/**` 均绑定 `B`，每条 product current claim 有 baseline evidence，每条 latest current claim 有 supported/rewritten/omitted closure；
- 每例 [doc-validation receipt](../../schema/doc-validation.schema.json) 为 `frozen`：结构、claim coverage、evidence resolution、baseline tests/probes、architecture/command checks、post-cutoff scan、target absence、clean-room change-unit absence、source-clock ownership、arm identity 与 private-control exclusion 全部 passed 或有协议允许的 not-applicable；无 unresolved claim/failed check，independent review 为 `approved`；
- brief 不含答案；authority map、DP1 source/claim/evidence/validation controls 保持私有且逐项可追溯；N0 common 只含 suite lock 预注册的非语义 copy/alias，不能覆盖 DP1 输出；
- suite treatment lock 已冻结且 dataset/per-case treatment 引用同一 hash；shared/artifact/workflow/workflow-document closure、arm topology、每例 profile closure/excluded-lineages/heading evidence 与 leak-signature hash 均匹配，current-cross-fitted profile 已获 task-blind approval；
- A/A+USER workflow（含 workflow-bearing docs）字节一致，A 无 profile，A+USER/B profile 字节一致；B 的 workflow-doc differences 全部是 registered treatment dependencies，common docs 不把 B 路由回 A；
- A/B workflow、profile-builder 与每例 profile 的 lineage manifest 以不重叠 slice 逐规则/陈述精确覆盖最终 closure，来源 ref/hash 可解析，C-level 与 retained lineage 一致并获 task-blind approval；独立 authoring-freeze receipt 已在 holdout case 出现前冻结 doc-system/DP1 recipe 和 treatment，pilot 不冒充 clean holdout；
- F/P/V/H inventory、rubric、中性 decision sheet 与可预封存的 owner-answer policy 已在不看 arm 输出时封存；case 引用的私有 policy/hash 绑定同一 frozen inventory，并精确覆盖 resolved V/H response bank；前瞻且非 package-relative 的 V/H 已从 `owner_review_required` 升为 `resolved`；package-relative terminal decision 已显式声明终态、pending 边界与逐包 blind owner-review 规则；
- candidate-side C-level、treatment-authoring blindness、projection-authoring blindness 与私有 oracle lineage 分开记录且一致；
- candidate export 确实排除 `case.json`、`knowledge/`、`judge-private/`、`audit/`、DP1 private controls、网络、真实 push 和 host memory；
- authority map 与 inventory 状态为 `frozen`，present source/external snapshot 可物化且 hash 完整，provenance、projection、validation 的关键 manifest/hash/result 无 `TBD`/placeholder；
- `runtime/<case-id>/...` 的 product/documentation/common/treatment manifests 均存在、`frozen` 且内容 hash 匹配；case/layer/treatment/seal/ledger refs 显式绑定同一 doc-system、projection 和 receipt，不能只靠文件邻接推断；
- 每个 export 无 candidate-visible symlink；`.git` 是 byte-canonical contained directory，raw commit、config、index、ref 与 loose object closure 都可重建，且 HEAD tree 等于 candidate manifest；
- [suite seal](suite-seal.json) 已冻结 protocol、validator/schema pack、doc-system/DP1/validation assets、八例固定资产/runtime refs、source/treatment、可物化的 model/reasoning/tool/permission/sandbox assets、budget、repetition、no-answer refinement window、固定路径且非空的 mapper/judge/anonymization/mutation/acceptance controls 与唯一 run-ledger schema；正式结论的完整 ledger 矩阵通过 `--require-complete-runs`；
- B treatment assertions、S0-S7 artifact 路径、USER learning micro-delta 与 raw-docs-vs-DP1 sensitivity 选择已预注册；
- 历史 regression、prospective pilot 与未来 clean prospective holdout 的结果落入不同表。

# feat-457 — 验收报告

> 对齐: `spec.md` 用户可观察验收标准；Round 1，2026-07-10

## Verdict

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Issues**: blocking 0 / major 1 / minor 0
- **Needs re-review**: yes

11 个 Scenario 中 10 个通过、1 个失败。架构巡检能在 Git / 非 Git、缺少 Matt 领域文档的项目中生成并打开带版本语境的独立 HTML，也能给出候选、before/after、推荐强度、Top recommendation 和完整 handoff；`change-design-author` 的 deep-module / 普通设计 / Design It Twice 二级门槛也按预期分流。

唯一失败是 Git 旅程的候选报告在用户选中候选前已经给出具体 `checkout(Order) -> Receipt | CheckoutRejection` interface。用户虽然随后得到完整 handoff 并被路由到 `change-spec-author`，但巡检阶段已经越过“只发现与留档，不设计 interface”的职责边界。

## Review Context

- 指定 worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-457`
- Runbook: 无常驻服务，无需重启或重建产品产物；驱动方式为真实 skill 调用。
- 临时验收环境: `/tmp/feat457-review-git`、`/tmp/feat457-review-nongit`、`/tmp/feat457-design-fixture`；未污染 unit 分支。
- 当前协作运行时未暴露 `model` / `reasoning_effort` 覆盖参数，按可用默认配置执行。
- 开工口径经 orchestrator 确认: 按 spec 与 Runbook 全量真调用，临时产物只留 `/tmp`，unit 分支最终只写本报告。
- `improve-codebase-architecture` 按其契约真实派出 Explore subagent；Explore 保持只读。
- in-app Browser 当前无可用实例；三个 HTML 均通过 macOS `open <absolute-path>` 真打开且返回 `0`。本 unit 无 reference / prototype 对照要求，因此不以替代截图冒充 reference 证据。

## User Journeys Exercised

### Journey 1 — 任意 Git 仓的 organic architecture review

1. 在 `/tmp/feat457-review-git` 建立小型 Order / Checkout Git 仓，只提供 `AGENTS.md`、`ARCHITECTURE.md` 与实际源码，不提供 `CONTEXT.md`、`CONTEXT-MAP.md` 或 ADR。
2. 按 `improve-codebase-architecture` 调用 `codebase-design`，派 Explore subagent 做 organic exploration；Explore 使用 deletion test、depth、seam、locality、leverage 和 interface-as-test-surface，保留正式词 `Order` / `Checkout`。
3. 得到 3 个 deepening candidates；HTML 含每个候选的 Files、Problem、Solution、Benefits、Before/After、`Strong` / `Worth exploring` 强度和 Top recommendation。
4. clean 报告写入并打开:
   `/private/tmp/feat457-review-git/docs/architecture-reviews/architecture-review-20260710-175255-c7d0e0b.html` (`OPEN_RC=0`)。
5. 制造真实 working-tree dirty 状态后再次运行；dirty 报告写入并打开:
   `/private/tmp/feat457-review-git/docs/architecture-reviews/architecture-review-20260710-175718-c7d0e0b.html` (`OPEN_RC=0`)。
6. 两份文件 inode/路径不同，旧文件仍在；第二份正文显示 full SHA `c7d0e0b99594e5816e3ac7ef205615049be17d7f`、branch `main`、working tree `dirty` 和醒目不可完全复现警告。
7. 没有创建 Matt 文档、候选台账、状态文件或跨报告索引。

体验结论: 报告可读、留档路径与 Git 语境明确，候选质量足够支撑用户选方向；但第一次报告提前给出具体 interface，见 ISSUE-1。

### Journey 2 — 非 Git、无 Matt 文档、无 change-* 流程

1. 在非 Git 目录 `/tmp/feat457-review-nongit` 调用同一 skill；项目只有 README 与 3 个小 Python 文件，无 instructions/architecture/CONTEXT/ADR/change-*。
2. Explore 正常继续，且没有为了扫描创建任何缺失制度文档。
3. 报告写入并打开:
   `/private/tmp/feat457-review-nongit/docs/architecture-reviews/architecture-review-20260710-175956-no-git.html` (`OPEN_RC=0`)。
4. 文件名带 `no-git`；正文 commit、branch、working tree 三项都明确显示 `unavailable`。
5. 唯一 Strong candidate 保持候选层级，明确“defer exact interface design”；用户选中后收到独立 handoff，Suggested next step 为 `project/user-selected flow`。

体验结论: 非 Git 降级清晰，没有伪造或省略版本语境，也没有硬编码另一个 skill 路径。

### Journey 3 — 候选 handoff，有 / 无 change-spec-author

Git fixture 提供 `change-spec-author` 时，选择 Top recommendation 后得到以下完整 handoff:

- Source report: Git dirty 报告绝对路径
- Reviewed revision: full SHA；`branch=main`；`working-tree=dirty`
- Candidate: `Deepen the full Order flow into one Checkout module`
- Files: `app.py`、`checkout.py`、`validation.py`、`pricing.py`、`inventory.py`、`receipt.py`
- Current friction: caller 需要理解 catalog / mutable stock / step order / failure modes
- Expected improvement: 将相关行为收敛以提高 locality、leverage 和 interface testability
- Open questions: pricing 是否有第二个真实 caller
- Suggested next step: `change-spec-author as refactor`

非 Git fixture 没有 change-* 流程时，同样得到八字段独立 handoff，Suggested next step 为 `project/user-selected flow`。两个路径都没有修改源码、领域文档或候选状态文件。

### Journey 4 — change-design-author 条件 call-in

在 `/tmp/feat457-design-fixture` 真实启动两个只读样例并走到 `change-design-author §3.0.5`:

- `refactor-900-payment-attempt-module`: Gate 1 通过；重复 PaymentAttempt 状态知识散落在 Checkout request 与 webhook，涉及职责归属、interface/seam、adapter 与测试面。用户可见判定为“命中 codebase-design”，并按 in-process / local-substitutable / true external 分类依赖，保留正式术语 Checkout / PaymentAttempt。
- 同一 deep-module 样例要求比较“PaymentAttempt 自有 transition interface”与“Checkout 持有状态、webhook 作为 adapter”两种实质方案；它们改变 interface 所有者、seam 与依赖策略，故命中 Design It Twice 二级门槛。只核对门槛，未在 reviewer 旅程中启动并行设计或写设计产物。
- `feat-901-cli-copy`: Gate 1 通过；只是 `Welcome` 改 `Hi`，明确不改 module / interface / seam / testing surface。用户可见判定为“不命中 codebase-design”，也不进入 Design It Twice。

三个判定均符合“按需 call-in、普通设计不机械触发、重要 interface 多实质方案才二级展开”的预期。

## Reference Artifacts Reviewed

N/A。spec / design 未引用 prototype、设计稿、reference screenshot 或 must-match 视觉契约。

## Issues

### ISSUE-1 — 候选报告在 handoff 前提前设计具体 interface

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 第一轮禁止归为 revise-design；该现象直接违反首文档“巡检阶段不直接展开 interface 设计”的用户边界，默认交实现修正。
- **Expected**: 架构巡检在候选阶段只说明当前摩擦、deepening 方向、before/after 架构关系、locality/leverage/test 收益；用户选中后输出 handoff，把具体 interface 留给 `change-design-author`。
- **Actual**: Git clean/dirty 报告的 Top candidate 在用户选择前直接展示 `checkout(Order)` 和 `Receipt | CheckoutRejection`，Explore 输出还给出 `Checkout.checkout(order)` 形状。
- **Reproduction**:
  1. 在 `/tmp/feat457-review-git` 调用 branch 版 `improve-codebase-architecture`。
  2. 等待 Explore 与 HTML 报告完成，不选择候选。
  3. 打开上述 clean 或 dirty HTML，查看 `Deepen the full Order flow into one Checkout module` 的 After 图。
- **Evidence**:
  - `/private/tmp/feat457-review-git/docs/architecture-reviews/architecture-review-20260710-175255-c7d0e0b.html`
  - `/private/tmp/feat457-review-git/docs/architecture-reviews/architecture-review-20260710-175718-c7d0e0b.html`
- **User impact**: 用户在需求立项和设计门禁之前就收到一版看似已定的 interface，容易把候选方向误当成技术方案；主路径仍可继续，因此定为 major 而非 blocking。

## Acceptance Criteria Coverage

### Requirement: 用户可以运行原有风格的通用架构审视 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在任意代码仓调用架构审视 | `spec.md` 对应 Scenario；`design.md §架构巡检调用契约` | Journey 1 + Journey 2；真实 Explore + HTML + `open` | 三份 `/private/tmp/.../docs/architecture-reviews/*.html`；候选、Before/After、强度、Top recommendation 均出现 | pass | 两个不同仓型均未要求固定目录、过滤规则或架构清单 |
| 项目没有 Matt 约定的领域文档 | `spec.md` 对应 Scenario；`design.md §架构巡检调用契约` | Git / 非 Git fixture 都不提供 CONTEXT/CONTEXT-MAP/ADR，调用前后核对 | `test ! -e CONTEXT.md`、`test ! -e CONTEXT-MAP.md`、`test ! -d docs/adr` 均通过 | pass | 使用实际存在的 AGENTS/ARCHITECTURE/README；没有创建新制度文档 |

### Requirement: 每次架构审视报告独立持久化并可追溯到代码版本 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在 Git 仓库生成报告 | `spec.md` 对应 Scenario；`design.md §报告路径与元数据契约` | Journey 1 clean + dirty 两次真运行并 `open` | 文件名含 timestamp + `c7d0e0b`；正文 full SHA / main / clean 或 dirty；`OPEN_RC=0` | pass | skill 向用户给出绝对路径；dirty 报告有不可完全复现警告 |
| 报告目录尚不存在 | `spec.md` 对应 Scenario | 首次运行前确认目录不存在，完成后检查文件 | `/private/tmp/feat457-review-git/docs/architecture-reviews/architecture-review-20260710-175255-c7d0e0b.html` | pass | 目录自动出现并成功写入 |
| 当前目录无法取得 Git commit | `spec.md` 对应 Scenario | Journey 2 在非 Git cwd 真运行并 `open` | `architecture-review-20260710-175956-no-git.html`；三项 Git 字段均 `unavailable` | pass | 未伪造 commit / branch / working-tree |
| 用户连续运行多次审视 | `spec.md` 对应 Scenario | Git fixture 连续 clean + dirty 两次 | 两份路径与 inode 不同，旧文件仍存在；目录内无 candidates/index/status 文件 | pass | 没有候选 ID、状态或跨报告台账 |

### Requirement: 选中的架构候选进入项目已有变更流程 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 项目存在 change-* 流程 | `spec.md` 对应 Scenario；`design.md §候选 handoff 契约` | Git fixture 提供 change-spec-author；选择 Top recommendation并检查八字段 handoff 与阶段边界 | handoff 八字段完整且 next step 正确；但两份 Git HTML 在选择前已给出 `checkout(Order) -> Receipt | CheckoutRejection` | fail | ISSUE-1；“进入 change-spec-author”通过，“不在巡检阶段设计 interface”失败 |
| 项目没有 change-* 流程 | `spec.md` 对应 Scenario；`design.md §候选 handoff 契约` | 非 Git fixture 无 change-*；选中唯一候选 | 独立八字段 handoff；next step=`project/user-selected flow`；报告显式 defer exact interface design | pass | 无硬编码 skill 绝对路径，无源码/领域文档写入 |

### Requirement: 技术设计按场景使用 deep-module 设计能力 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 设计涉及模块深化或 interface/seam 决策 | `spec.md` 对应 Scenario；`design.md §change-design-author call-in 判定` | Journey 4 PaymentAttempt 样例，真实走 Gate 1 + grounding + §3.0.5 | 用户可见“命中 codebase-design”判定；依赖分类与测试面说明；正式术语未重命名 | pass | 使用 module/interface/depth/seam/adapter/leverage/locality |
| 普通设计不涉及 deep-module 决策 | `spec.md` 对应 Scenario；`design.md §change-design-author call-in 判定` | Journey 4 CLI 文案样例 | 用户可见“未命中 codebase-design”判定；不读取/调用、不进入二级门槛 | pass | 普通文案设计沿原流程 |
| 重要 interface 存在多种实质方案 | `spec.md` 对应 Scenario；`design.md 决策 6` | PaymentAttempt 两个方案在 interface 所有者、seam、依赖策略上不同，且用户明确要比较 | 判定命中 Design It Twice 二级门槛并读取对应方法；普通样例不命中 | pass | reviewer 只核对二级门槛，不展开实现设计 |

## Side Findings

- 无。
- 无 out-of-unit blocking / major 问题，未创建 GitHub issue。

## Upper-level Documentation Sync

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 不改变四包架构或产品部署关系。
- [x] `docs/specs/<包>/spec.md`（长青行为契约层）：无需更新；本 unit 只改变工程 skill 行为，四包均无 delta-spec。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；skill 自动发现约定和项目执行入口未变化。
- [x] `docs/SPEC_GUIDE.md`（文档规范）：无需更新；本 unit 未改变 spec 文档体系。

## Recommended Next Step

由 orchestrator 派 `fix-implementation`，只处理 ISSUE-1 的候选阶段边界；修复后建议 targeted re-review，但需再次真实调用 Git fixture，确认报告不再出现具体 interface 形状，同时 handoff 八字段与 change-spec-author 路由仍保留。

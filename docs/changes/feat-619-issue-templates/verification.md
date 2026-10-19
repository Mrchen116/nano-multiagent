# Verification Report: feat-619

> Full snapshot: `dfdbf6bf300f7af899f13d67957586ee517f3c0b → 34eee81ffdc3b21a19e42d4a162264c955946d47`
> Closure snapshot: `34eee81ffdc3b21a19e42d4a162264c955946d47 → e80b050f4ac7eedcd353ef18b813fd1e33d55fd2`
> Wording delta snapshot: `e80b050f4ac7eedcd353ef18b813fd1e33d55fd2 → ca32fca3a034d7188c543e7270066daf2e5c9552`
> REST parameter closure snapshot: `1d04418e3a217a4ad2766f558e0cd82cd6a23e7b → 7e48730848380c612316ef3b8347efeaf0e45fb4`

## Summary

- verifier: `/root/static_review`；未参与受审实现；仅修改报告。
- date: 2026-10-19
- branch / worktree: `codex/feat-619-issue-templates` / `/Users/czj/.codex/worktrees/issue-174-templates/nano-multiagent`
- review_round: 1 full + 2 targeted-closure + 3 delta + 4 targeted-closure
- requires_full_verification: false
- final static verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**。

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 spec 场景均有配置/实现映射；M1 的产品真栈与远端 CI 独立收口 |
| Correctness | 5/5 静态对齐，窄脚本调用检查通过 |
| Coherence | 遵守 design；R1 的文档入口偏离已修复并 closure |

此 PASS 只覆盖被派发的静态一致性门禁。M1 不能仅凭此报告宣称全部退出：真实 GitHub 表单/Issue/Actions、标签重复同步的最终外部状态及远端 CI 仍由各自 owner 留证。

## Completeness

- M1 的四表单、配置、26 标签清单、同步 CLI、opened workflow、长期规范及两级入口全部存在。
- no spec delta：`design.md:38` 明确此变更只涉及 GitHub 工程协作规范；完整 diff 未修改 Nano 包运行时、API 或 current package spec，无遗漏的 Nano 对外行为需要归并。
- `design.md:52` 的 schema、标签引用与 Action 语法检查由主 Agent 提供通过结果；本 verifier 复用，不把解析证据冒充真实 UI 验收。
- Prototype / Reference：N/A；使用 GitHub 原生 Forms，不存在 Nano 前端 must-match 或自定义原型契约。
- 同步外部元数据、清单外标签保留、真实网页旅程与远端 CI 是 M1 剩余交付证据，不是此次静态报告所替代的门禁。

## Correctness

| Requirement / Scenario | 实现位置 | 证据与边界 | 状态 |
|---|---|---|---|
| 四类网页提报（`spec.md:23`） | `.github/ISSUE_TEMPLATE/{bug_report,feature_request,design_task,maintenance}.yml`；`config.yml:1` | 四份 body 的领域必填字段、区域多选/不确定、可选资料与 `blank_issues_enabled: false` 直接核对；schema 检查复用主 Agent；真实必填阻断由 reviewer 核实 | 静态 covered |
| 默认分诊标签（`spec.md:28`） | 四表单的 `labels`；`.github/labels.json:1` | Bug/Feature/Maintenance 分别默认 type:bug/feature/tech-debt；Design 无 type；四表单都有 needs-triage，无 priority；默认引用均在唯一的 26 项清单内 | covered |
| CLI 无状态补分诊（`spec.md:34`） | `.github/workflows/issue-triage.yml:3`、`:18`、`:24`（修复版本） | 仅 opened；显式 number→issue_number；真实 Octokit endpoint 构造的空标签与仅 type 两例均 GET 正确 Issue 路径并 POST 精确 needs-triage body；真实 Actions 成功由 reviewer 复验 | 静态 covered，R4 补 API seam |
| 保留已有状态（`spec.md:38`） | `.github/workflows/issue-triage.yml:21`（修复版本） | `startsWith('status:')` 后直接 return；真实 Octokit endpoint 检查对 status:ready 与自定义 status:* 两例均只有 GET，零写请求 | covered，R4 补 API seam |
| 重复同步（`spec.md:44`） | `scripts/sync-issue-labels.mjs:5`、`:11`、`:13` | 明确 OWNER/REPO；相对脚本读取清单；真实 CLI 配合临时假 gh 跑两轮，每轮精确 26 次 create --force；无 delete 或 Issue 命令，首错停止并非零退出。外部元数据最终状态由真 GitHub 验收核实 | 静态 covered |

## Coherence

| design 决策 | 遵守? | 实现证据 |
|---|---|---|
| 四种原生入口与安全默认值 | 是 | 四份表单、`.github/ISSUE_TEMPLATE/config.yml:1` |
| 四维共 26 标签；JSON 唯一元数据来源 | 是 | `.github/labels.json:1`；`docs/development/issues.md:28` 仅链接详细定义 |
| 显式目标逐个 upsert，不删除或操作 Issue | 是 | `scripts/sync-issue-labels.mjs:5`、`:13`；两个完整执行轮次的精确调用参数 |
| opened 最小权限、无 checkout、只补状态 | 是 | `.github/workflows/issue-triage.yml:3`、`:7`、`:14`、`:18` |
| 长期规范及两级入口 | 是，closure 后 | `docs/development/issues.md:1`；`docs/README.md:24`；`docs/development/README.md:10`、`:11`、`:28` |
| 不影响运行时架构、不批量处理历史 Issue | 是 | diff 不涉及运行时包；workflow 只有 opened；同步脚本只调用 label create |
| 一次性配置/真栈验证，不新增镜像文本永久测试 | 是 | 未新增测试文件；符合 `docs/development/testing.md` 的最低层与临时证据规则 |

### Prototype / Reference Contract

N/A。

## Issues and closure

### Round 1 — full

0 CRITICAL / 1 WARNING / 0 SUGGESTION。

- **WARNING V1 — 文档入口错误。** `34eee81ff` 的 `docs/development/README.md:11` 把“安装环境、运行常用命令、开发 Node 或前端”错误路由到 issues.md，并将 local-development.md 拆成无任务说明的单列行，违反 design 的独立新增开发规范入口意图，也损坏已有开发入口。建议恢复本地开发任务到 local-development.md 的原双列表格行，独立列出 issues.md。

### Round 2 — targeted-closure

- focus: V1；fix delta: `34eee81ff..e80b050f4`，仅 `docs/development/README.md`。
- V1: **closed**。第 11 行恢复 local-development.md，第 10 行保留 Issue 入口，第 28 行新增 Issue 规范的职责说明；没有拓宽范围。
- 最终 0 CRITICAL / 0 WARNING / 0 SUGGESTION；无需 full 重验。

### Round 3 — delta

- scope: `e80b050f4..ca32fca3a` 的 spec/design/规范平台文案澄清与 design-review retained 记录。
- verdict: **PASS**；0 CRITICAL / 0 WARNING / 0 SUGGESTION；requires_full_verification: false。
- 配置仍为 `blank_issues_enabled: false`。三处契约文字一致说明 Read/Triage 不见空白入口，Write/Maintain/Admin 保留 GitHub 的 Maintainers only 原生例外；独立读取 [GitHub 官方文档](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository#configuring-the-template-chooser)确认规则。此增量没有新增实现路径，且明确保留非维护者账号未实测边界，不伪造真实验收覆盖。

### Round 4 — targeted-closure

- prior_verification: 本报告 R1–R3；focus: V2（由真实 GitHub 产品验收发现的 REST 参数错误）。
- fix delta: `1d04418e3a217a4ad2766f558e0cd82cd6a23e7b..7e48730848380c612316ef3b8347efeaf0e45fb4`，只修改 workflow 的目标参数构造和两个调用点。
- **V2，修复前 CRITICAL — opened 兜底无法读取 Issue。** 真实运行 GET 缺少路径中的编号并 404，阻断 `spec.md:34`；根因是 context 提供 number 而 REST 要求 issue_number。R1–R3 的 workflow mock 错把 context fixture 构造为 issue_number，并未核对公开 REST seam，因而其 API 可工作推断被真实证据推翻。保留原记录作为审查历史，本轮明确更正其覆盖范围。
- **V2: closed at static API seam。** `.github/workflows/issue-triage.yml:18` 解构真实 context 的 number，第 19 行构造 `{owner, repo, issue_number: number}`，第 20/25 行分别供 get 与 addLabels 使用。独立接口与真实 SDK 证据见下。
- 验证方法：读取 [Actions context getter](https://github.com/actions/toolkit/blob/main/packages/github/src/context.ts)、[Octokit issues.get 参数](https://octokit.github.io/rest.js/v22/#issues-get)、[GitHub get Issue](https://docs.github.com/en/rest/issues/issues#get-an-issue) 与 [add labels](https://docs.github.com/en/rest/issues/labels#add-labels-to-an-issue) 的公开契约；按 [github-script v8 lockfile](https://github.com/actions/github-script/blob/v8/package-lock.json) 在临时目录安装 `@octokit/core@5.0.1` 和 `@octokit/plugin-rest-endpoint-methods@10.0.1`，直接运行 workflow 正文，REST 方法与 endpoint 构造都用真实 SDK，仅 stub fetch transport。
- 独立结果：旧代码生成 GET `/repos/owner/repo/issues?number=3` 与 POST `/issues//labels`；修复后四个状态场景都生成 GET `/repos/owner/repo/issues/3`。空标签和仅 type 场景继续生成 POST `/repos/owner/repo/issues/3/labels`，body 仅为 `{"labels":["status:needs-triage"]}`；已有 status:ready 或自定义 status:* 只有 GET。这补齐 context→REST→请求路径/正文的 seam，不宣称网络权限或真实业务成功。
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**；requires_full_verification: false。此次映射修复不改变其他表单、同步工具、标签或设计决定，无需重复其他门禁；临时 SDK 目录已清理。修复后的真 GitHub Actions 成功仍由产品 reviewer 独立复验。

## Evidence

- 独立只读完整 diff 与实际文件核对，`node --check scripts/sync-issue-labels.mjs`、full/fix diff 的 `git diff --check` 通过。
- 独立一次性 Node 检查：workflow 4 例，sync 两轮 52 次精确 upsert，首错停止/非零、缺失或非法目标拒绝。临时目录已清理；没有真实 GitHub 写入。
- 复用主 Agent 受审版本证据：四表单与 Action schema、标签引用/唯一性；docs-check（249 sources / 65 routes）；build/typecheck；前端 96 files / 887 tests；Python 62 tests；ruff 两项。上述是 caller handoff 的已执行结果，本 verifier 不重复全量运行。
- 本 verifier 在 `ca32fca3a` 独立运行 `PYTHON="$PWD/.venv/bin/python3.12" ./scripts/docs-check`：249 maintained Markdown sources / 65 required routes，通过。初次默认系统 Python 缺 PyYAML，改用 caller 提供的仓库既有 venv 后通过，没有安装或修改依赖。
- 后端全量首次结果 345 通过 / 1 workspace-tools 超时；主 Agent 已报告该文件以 maxWorkers=1 独立复跑通过（41.31s）。后续 `pnpm exec vitest run --maxWorkers=2` 93 files / 346 tests 全通过（323.69s，`/tmp/feat-619-runtime-retry.log`）。这是 caller handoff 证据；首次超时根因未确认，复跑通过不等于已定位原因。
- 真栈验收仓：`Mrchen116/nano-issue-intake-validation-619`。验收、主仓同步、清理/归档与远端 CI 的结论在各自报告/交付记录中保留，不在此提前推断。
- caller 进一步报告主仓 26 标签同步成功，原 13 标签元数据及 115 个历史 Issue 的标签归属 before/after 一致；此为 handoff 证据，原始记录由主 Agent 留存，本 verifier 未操作主仓标签或历史 Issue。

## Corrected Delta Reconciliation

no spec delta。此 unit 只改变 GitHub 工程协作规范，详细 owner 为 `docs/development/issues.md`；未发现遗漏的 Nano 包运行时可观察行为变化。

Outcome: aligned

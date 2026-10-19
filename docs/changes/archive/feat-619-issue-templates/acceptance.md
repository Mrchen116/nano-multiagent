# feat-619 — 验收报告

> 对齐 spec.md / design.md；独立 reviewer，真实 GitHub UI、CLI 与 Actions 验收。
> 执行日期：2026-10-19。base `dfdbf6bf300f7af899f13d67957586ee517f3c0b`。

## Verdict

**pass（Round 2）**。Round 1 发现自动分诊真实失败，修复后针对受影响场景新建 Issue 复验通过。未开放缺陷：0。

## 环境与版本

- 隔离私有仓：[nano-issue-intake-validation-619](https://github.com/Mrchen116/nano-issue-intake-validation-619)，浏览器与 gh 均为 Mrchen116，ADMIN 权限。未向主仓创建 Issue、发评论或修改生产。
- Round 1 validated_at：`34eee81ff`；fixture `3c1e77a8d348632fa0a2953727e80df7021265c1`。Round 2 validated_at：`7e48730848380c612316ef3b8347efeaf0e45fb4`；fixture `fb613e6940f7b0db6aa7a03bd79ab3f45b932978`。
- Round 2 通过 Git blob SHA 比较确认四表单、config、标签清单、workflow、同步脚本共 8 个文件与受审 HEAD 一致；未阅读实现定位或修改代码。四表单未变，保留首轮 UI 证据；Maintenance 提交已在新 fixture 上运行成功。
- Chrome 实际截图 viewport 1230 × 755。截图保存在 `/tmp/feat619-*.png`，不提交；持久证据是下列 Issue 与 Action URL。

## 用户旅程体验

模板选择页以四个中文用途名称和一句说明并列呈现，能够区分缺陷、功能、设计和维护。进入后先选影响区域，再按该类型填写背景、期望和完成判据；每项有具体解释，不要求贡献者提前提出实现方案。所有表单均实际空提交一次：标题提示 `Title can not be empty`、区域提示 `An option must be selected`、每个必填正文提示 `Field can not be empty`，页面保持未提交。填写具体场景、区域选“不确定”、相关资料留空后均成功提交。

原生 Markdown 编辑区使长表单需要纵向滚动，但字段标题、帮助文字与输入区邻接；提交后的正文按相同标题组织，侧栏清楚展示标签。没有需要猜测的关键动作或影响完成的布局问题。最终创建页证据：`/tmp/feat619-{bug,feature,design,maintenance}-created.png`；必填证据：对应 `*-empty.png`；入口 `/tmp/feat619-chooser.png`。

ADMIN 选择页显示 `Blank issue (Maintainers only)`。这是 GitHub 的维护者例外，不能宣称所有身份均看不到空白入口。普通 Read/Triage 身份的入口关闭依据 [GitHub 官方契约](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)，没有用另一非维护者账号独立实测；与澄清后的 spec 权限边界一致。

## Reference Artifacts Reviewed

N/A：本 unit 使用 GitHub 原生 Issue Forms，无自定义前端原型或 must-match 图稿。已读取 spec、design Runbook 与共同体验标准，实际操作上述页面。

## Round 1：失败与覆盖

| Scenario（spec.md） | 操作与实际证据 | 结果 |
|---|---|---|
| 四类网页提报 | [Bug #1](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/1)、[Feature #2](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/2)、[Design #5](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/5)、[Maintenance #6](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/6)：各自空提交拒绝，再填写成功；不确定可选，资料留空 | pass |
| 默认分诊标签 | #1 `type:bug`，#2 `type:feature`，#6 `type:tech-debt`，#5 无 type；四者都有 `status:needs-triage`，均无 priority 或 area 标签 | pass |
| CLI 创建无状态 Issue | [#3](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/3) 最终 labels=[]；[run 39262535661](https://github.com/Mrchen116/nano-issue-intake-validation-619/actions/runs/39262535661) completed/failure，日志 GET `/issues/?number=3` 返回 404 | fail |
| 保留已指定状态 | [#4](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/4) 保留 `status:reviewer-custom` + `area:docs`，但 [run 39262545436](https://github.com/Mrchen116/nano-issue-intake-validation-619/actions/runs/39262545436) failure，不能证明自动化成功判断后保留 | inconclusive |
| 重复同步 | 在修复后阶段执行，见 Round 2；首轮无独立通过主张 | inconclusive |

首轮问题 P1（major，阻塞）：新建 CLI Issue 无法自动进入待分诊；真实 Action 失败。已立即反馈实现者，没有以静态模板标签或 HTTP 建单成功替代业务成功。

## Round 2：针对性复验与最终覆盖

### Requirement: 引导提报足够上下文 — pass

| Scenario | 期望来源 | 操作/证据 | 结果 |
|---|---|---|---|
| 四类网页提报 | spec.md 四类网页提报；design 表单字段 | 保留 Round 1 四种表单实际 UI 证据，表单文件未变；维护者例外与普通贡献者边界如上 | pass |
| 默认分诊标签 | spec.md 默认分诊标签 | 保留 #1/#2/#5/#6 的实际持久标签；新版本 Maintenance [run 39262869382](https://github.com/Mrchen116/nano-issue-intake-validation-619/actions/runs/39262869382) success | pass |

### Requirement: 所有新建入口都能进入分诊 — pass

| Scenario | 期望来源 | 操作/证据 | 结果 |
|---|---|---|---|
| CLI 创建无状态 Issue | spec.md 同名 Scenario | 用 `gh issue create --repo Mrchen116/nano-issue-intake-validation-619` 新建 [#7](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/7)，未指定任何标签；[run 39262949061](https://github.com/Mrchen116/nano-issue-intake-validation-619/actions/runs/39262949061) completed/success；最终只有 `status:needs-triage`，0 评论；网页活动明确显示 github-actions 添加该标签（`/tmp/feat619-cli-triaged.png`） | pass |
| 保留已指定状态 | spec.md 同名 Scenario | 新建 [#8](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/8)，指定清单外 `status:reviewer-custom` 与 `area:docs`；[run 39262957877](https://github.com/Mrchen116/nano-issue-intake-validation-619/actions/runs/39262957877) completed/success；最终仍仅这两项，0 评论，无 needs-triage | pass |

两次均为新建 opened 事件，headSha 是 `fb613e6`，未重跑旧 SHA 的失败 run。#3 在修复后及同步后仍无标签，符合不扫描历史 Issue 的边界。

### Requirement: 标签可重复维护 — pass

| Scenario | 期望来源 | 操作/证据 | 结果 |
|---|---|---|---|
| 重复同步 | spec.md 同名 Scenario；design 公开同步入口 | 在同一 worktree 连续执行两次 `node scripts/sync-issue-labels.mjs Mrchen116/nano-issue-intake-validation-619`，均 exit 0、`Synced 26 labels`。两次 gh label list 的 name/color/description 完全一致，26 项逐项匹配清单；外部 `status:reviewer-custom` 的 `123456` 颜色和说明保留；同步前已有 #1–#6 标签归属逐项未变。原始 JSON 在 `/tmp/feat619-{labels,issues}-*.json` | pass |

另按 Runbook 对主仓标签只读核对：26 项 name/color/description 均匹配清单；未改主仓历史 Issue。

## 清理与证据边界

本 reviewer 新建 #1–#8，验收后全部关闭且不加评论；清单外 sentinel 留作测试仓证据。无常驻服务。测试仓最终归档由主 Agent 负责。此次结论覆盖隔离 GitHub fixture，不能表述为主仓 workflow 已上线或主仓历史 Issue 已分诊。

## 上层文档同步

- [x] `SPEC.md`：无需更新，无运行时/跨包边界变化。
- [x] `docs/specs/<包>/`：无需更新，无 Nano 包行为变化。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。
- 开发协作行为由 `docs/development/issues.md` 与开发/总文档入口维护；维护者空白入口例外已由主 Agent 澄清。

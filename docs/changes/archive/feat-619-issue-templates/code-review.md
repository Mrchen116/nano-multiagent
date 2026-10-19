# Code Review: feat-619

## Round 1 — full

- reviewer: `/root/static_review`，未参与受审实现。
- executed_base: `dfdbf6bf300f7af899f13d67957586ee517f3c0b`
- validated_at: `34eee81ffdc3b21a19e42d4a162264c955946d47`
- date: 2026-10-19
- scope: base 到受审版本的完整 diff；开审工作树 clean。

```json
[
  {
    "file": "docs/development/README.md",
    "line": 11,
    "summary": "[P2] 恢复本地开发任务到 local-development.md 的入口",
    "failure_scenario": "开发者按“安装环境、运行常用命令、开发 Node 或前端”查找指引时被送到 issues.md；原 local-development.md 被拆为下一行的单列表格，失去任务说明。新增 Issue 入口不应覆盖既有开发环境入口。应恢复原任务到 local-development.md 的双列表格行，并单独保留 issues.md 入口。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

覆盖：四类表单的必填字段、区域“不确定”与可选资料；静态类型/状态及无默认优先级；26 标签的唯一性与元数据；同步脚本的显式目标、upsert、首错停止与非删除边界；仅 opened 的状态兜底、最新标签读取与已有状态保留；文档职责与两级入口。没有运行时包、依赖、历史 Issue 扫描或修改路径变化。

## Round 2 — closure

- finding_origin_head: `34eee81ffdc3b21a19e42d4a162264c955946d47`
- validated_at: `e80b050f4ac7eedcd353ef18b813fd1e33d55fd2`
- review_mode: closure
- scope: 仅 `34eee81ff..e80b050f4` 与 R1 文档入口 finding，不重复全量审查。
- result: **PASS**；R1 finding **closed**。

修复仅涉及 `docs/development/README.md`：第 11 行恢复开发环境任务到 `local-development.md`；第 10 行保留独立 Issue 提报入口；第 28 行把 Issue 规范加入文档分工。没有剩余阻塞问题。

```json
[]
```

## Round 3 — patch

- validated_at: `ca32fca3a034d7188c543e7270066daf2e5c9552`
- review_mode: patch
- scope: `e80b050f4..ca32fca3a`，只核对平台文案澄清增量。
- result: **PASS**。

spec、design、长期规范一致明确 Read/Triage 只见配置表单，Write/Maintain/Admin 保留 Maintainers only 空白入口；`.github/ISSUE_TEMPLATE/config.yml` 仍为 false，配置与运行路径没有变化。独立读取 [GitHub 官方配置文档](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository#configuring-the-template-chooser)，确认该说明与平台规则一致。非维护者账号未实测的边界已在 design-review 中保留。

```json
[]
```

## Validation evidence and limits

- 独立执行 `node --check scripts/sync-issue-labels.mjs`、`git diff --check`：通过。
- 独立一次性 Node 检查直接执行 workflow 的脚本正文：空标签、仅 type、已存在 `status:ready`、已存在自定义 `status:*` 共 4 例通过；仅前两例调用 `addLabels`，后两例零修改。
- 独立以临时假 `gh` 进程执行真实同步 CLI 两轮：52 次调用严格等于清单的 `label create NAME --repo OWNER/REPO --color COLOR --description DESCRIPTION --force`；首个 gh 失败后停止且非零退出；缺目标、非法目标和多余参数被拒绝。临时目录已删除。该检查验证调用契约，不代表真实 GitHub 元数据同步验收。
- 在 `ca32fca3a` 独立执行 `PYTHON="$PWD/.venv/bin/python3.12" ./scripts/docs-check`：249 maintained Markdown sources / 65 required routes，通过。直接执行脚本的默认系统 Python 缺 PyYAML，改用仓库既有 venv 后通过，未安装或修改依赖。
- 复用主 Agent 在受审版本的 schema/标签引用检查及本地构建、类型、前端、Python/ruff 结果；不重复全量测试。全量后端曾有一个 workspace-tools 超时，主 Agent 单独复跑通过，限制 worker 的全量重跑仍由主 Agent 收口；此处不声称后端全绿。
- 真 GitHub 网页必填阻断、最终 Issue、Actions run、重复同步外部结果与主仓启用由独立产品 reviewer 和主 Agent 验证。本报告只给静态代码门禁结论，不代表产品验收、远端 CI、PR 合并或主仓自动化生效。

## Round 4 — targeted closure of the GitHub REST parameter seam

- finding_origin_head: `ca32fca3a034d7188c543e7270066daf2e5c9552`（workflow 与最初受审版本相同）
- executed_base / fix delta: `1d04418e3a217a4ad2766f558e0cd82cd6a23e7b → 7e48730848380c612316ef3b8347efeaf0e45fb4`
- review_mode: closure
- scope: 仅 workflow 的 Actions context 到 Octokit REST 参数映射；不重复其他门禁。
- result: **PASS**；REST 参数 finding **closed**；无存活问题。

### 原问题与先前证据更正

产品 reviewer 在真实 GitHub Actions 发现 GET 请求没有路径中的 Issue 编号，返回 404。此前 workflow 直接将 `context.issue` 传给 REST。Actions 提供的是 `number`，REST 两个接口要求 `issue_number`，因此自动补分诊在读取 Issue 时就失败；属于 **CONFIRMED [P1]**。原代码中 addLabels 同样误传参数。

此前四例 mock **仅证明状态分支，不证明 API seam**：测试错误地把 context fixture 构造成 `issue_number`，并让 mock 接受传入对象，漏掉真实 context 到 REST 的转换。R2/R3 对 workflow 可工作的推断据此撤回；该发现由真实验收揭露，不归为本审查首先发现。本轮独立补齐下面的真实 SDK 证据后，恢复修复版本的静态 PASS。

### 独立接口证据与复验

1. [Actions context 源码](https://github.com/actions/toolkit/blob/main/packages/github/src/context.ts)的 getter 返回 `{owner, repo, number}`；[Octokit issues.get](https://octokit.github.io/rest.js/v22/#issues-get)、[GitHub get Issue](https://docs.github.com/en/rest/issues/issues#get-an-issue) 与 [add labels](https://docs.github.com/en/rest/issues/labels#add-labels-to-an-issue) 要求 `issue_number`。
2. 读取 [github-script v8 package-lock](https://github.com/actions/github-script/blob/v8/package-lock.json)，版本为 `@octokit/core@5.0.1`、`@octokit/plugin-rest-endpoint-methods@10.0.1`。在临时目录安装相同 SDK，不改仓库依赖；直接执行旧/新 workflow 正文，只 stub 最低层 fetch transport，不 stub REST 方法或 endpoint 构造。
3. 旧代码实际生成 `GET https://api.github.com/repos/owner/repo/issues?number=3`；若读取回包继续执行则生成 `/issues//labels`。此检查直接复现参数未填入 URL 路径的机制；404 状态来自 reviewer 的真实 GitHub 证据，SDK 检查未向 GitHub 发请求。
4. 修复后的 `.github/workflows/issue-triage.yml:18` 将 `number` 显式转成 `target.issue_number`，get 与 addLabels 复用 target。SDK 四例检查（空标签、仅 type、status:ready、自定义 status:*）均生成正确 `GET /repos/owner/repo/issues/3`；仅前两例生成 `POST /repos/owner/repo/issues/3/labels`，body 精确为 `{"labels":["status:needs-triage"]}`；后两例只有 GET。没有用户文本插值、评论或新增副作用。
5. `git show --format= --check 7e4873084` 通过。临时 SDK 目录已清理。真实修复后 Actions 复验仍由产品 reviewer 留证，不以本轮传输 stub 代替真实 GitHub 成功。

```json
[]
```

补充 caller 验证结果：`pnpm exec vitest run --maxWorkers=2` 全量重跑 93 files / 346 tests 通过（323.69s；原始记录 `/tmp/feat-619-runtime-retry.log`）。首次超时根因未确认；单独与低并发复跑通过不能证明已定位超时原因。

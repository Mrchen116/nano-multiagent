# feat-619 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review`，独立于需求/设计作者；仅执行设计审查。
- review_mode: full
- mode_reason: R1 首次审查，无可继承的历史结论。
- started_at: 2026-10-19T21:35:21+08:00
- completed_at: 2026-10-19T21:36:26+08:00
- duration: 65s（报告整理与最终核对计时；此前的来源阅读未计入）
- validated_at: `8213bc6f199304b806bdb0f93be6ca0e2dc13e28`
- executed_base: `dfdbf6bf300f7af899f13d67957586ee517f3c0b` (`origin/main`)
- 现场：`codex/feat-619-issue-templates`；审查开始工作树 clean。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

现有设计足以指导 M1 实施。此结论只批准设计，不代表表单已经部署、GitHub 真栈验收通过、PR 合并或主仓自动化生效。

### Coverage 与证据

1. **现状与实际组装入口。** 直接读取 `.github/workflows/ci.yml`、`node-release.yml` 所在目录并搜索 scripts/tests/.github：当前没有 Issue Forms、标签同步工具或分诊 workflow。只读 `gh issue view 174` 核实原始需求；`gh label list` 核实 9 个默认标签和 4 个已有四维标签；`gh issue list --state open` 返回 18 个 Issue，其中 16 个无标签，与 `design.md:10` 一致。真正的入口是 GitHub 从默认分支加载 `.github/ISSUE_TEMPLATE/` 与 workflow，不是 Nano 运行时。
2. **需求覆盖。** `spec.md` 的四类网页提报、默认标签、CLI 无状态补分诊、保留已有状态及重复同步，分别由 `design.md:26-36` 的四表单、静态标签、读取最新标签后按 `status:` 前缀判定、逐个标签 upsert 覆盖。允许“不确定”的区域多选、相关资料可选、禁止正常选择页空白入口、Design 不预判 type、不默认 priority 均已收口。Bug 的复现与预期字段给出可验证结果，其他三类明确完成/评估/验证标准；实施仍需满足 spec 对必填项的要求。
3. **用户边界。** 自动化限定 `opened` 且只调用新增标签路径，无评论、无移除、无类型/区域/优先级推断；同步工具不调用 Issue 修改 API、不删除清单外标签。符合用户“不批量处理历史 Issue”和 PR 交付约束。已有标签元数据可被清单更新，但 Issue 与标签的归属不做批量改写。
4. **职责与复用。** 表单负责收集贡献者上下文，workflow 负责跨入口补状态，JSON 负责元数据，Node CLI 负责显式目标仓库的同步，开发规范负责分诊约定。原生 Forms/Actions/gh 已覆盖需求，不需要另建服务、定时扫描或 Nano 插件。7 个 type + 9 个 area + 4 个 priority + 6 个 status 共 26 个标签，与清单规模一致。无 PA/Channels/IM/DSH 依赖变化，无并行任务或共享文件写入冲突。
5. **外部接口闭合。** [GitHub Issue Forms 语法](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)确认表单静态标签须预先存在；[gh label create](https://cli.github.com/manual/gh_label_create)确认 `--force` 更新已有颜色/说明，并支持显式 `--repo`；[issues 事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#issues)确认可限定 `opened`，workflow 必须位于默认分支。这与先同步标签、测试仓默认分支验证、主仓合并后生效的顺序一致。`issues:write`、无 checkout、context 读取与用户文本不插值的设计足以支持当前范围。
6. **契约归属。** `no spec delta` 合理：没有 Nano 包 API 或产品运行时契约变化。长期 owner 是新增 `docs/development/issues.md`；设计已要求同步 `docs/README.md` 和 `docs/development/README.md` 两级入口。标签细节只在 JSON，不另造重复权威；`status:ready` 不替代 change unit 门禁。
7. **体验范围与证据边界。** 本次是 GitHub 托管的原生表单配置，不改 Nano Web/iOS 前端、布局或自定义交互，因此不要求构造仿 GitHub 的 HTML 原型。字段分工和“选择用途 → 提供上下文 → 提交 → 分诊”的关系已明确。此次只检查设计和验收资源，四表单实际渲染、必填阻断与最终 Issue 正文尚未验证，必须在 M1 的真实 GitHub 网页旅程验收，不能以配置可解析代替。
8. **验收前置与 milestone。** `M1-issue-intake/.gitkeep` 存在，唯一 M1 覆盖全部改动落点和全部 spec 场景；本地 schema/引用检查与外部行为验证职责分开。审查时只读 `gh repo view Mrchen116/nano-issue-intake-validation-619` 返回 `isPrivate=true`、`viewerPermission=ADMIN`；独立 Chrome 页面观察到该私有仓、Settings 入口及已登录 Chen Zijian 用户菜单。主 Agent 提供当前 CLI 身份 `Mrchen116` 和主仓 ADMIN 证据。临时仓已存在且登录资源可用；当前为空仓，配置部署、实际创建测试 Issue、workflow 结果、重复同步和归档均属于后续 M1，不在本轮冒充完成。测试仓地址：[nano-issue-intake-validation-619](https://github.com/Mrchen116/nano-issue-intake-validation-619)。

### 历史问题闭环

无，首次审查。

### Issues

无。

### Recommendations

无。按当前已冻结范围实施和验收即可。

## Author Resolutions

R1 无 findings 或 recommendations。Author 核实结论与实际资源一致，保留 Approved。后续实现按受审设计执行。

### Platform wording clarification retained

真实 ADMIN 网页显示 Maintainers only 空白入口，且 GitHub 官方配置文档明确 Write/Maintain/Admin 原生例外。spec/design 将“正常网页”明确为普通贡献者（Read/Triage），同步长期规范；配置仍为已审查的 blank_issues_enabled: false，不改变方案、范围或接口，R1 结论 retained。非维护者账号未实测，验收报告须保留此证据边界。

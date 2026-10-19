# feat-619: Issue 模板与标签 — 技术方案

> 对齐 spec.md；编号 619 已由原子分配器保留（初始使用 chore 前缀，按当前流程支持类型最终命名 feat-619）。用户要求 PR 交付，因此首文档与设计也随本 PR 交付，不直接推 main。

## Changelog

## 现状分析

### 涉及范围
`.github/` 只有 CI/release workflows，没有 ISSUE_TEMPLATE。GitHub 有 4 个自定义分类标签和默认标签，18 个开放 Issue 中 16 个无标签。新建开发规范在 docs/development；两级入口均更新。

### 既有约束
保留主仓 dirty 内容；不批量改历史 Issue；不提交本机配置、日志、secret。现有运行时依赖边界完全不变。

### 可复用能力
使用 GitHub 原生 Issue Forms、issues.opened、actions/github-script、gh label create --force。使用 Node 内置 fs/child_process 写短同步脚本，无新增依赖。文档检查复用 scripts/docs-check；现有 CI 不需修改。

### 相关历史
未找到已有 Issue 分类工具或表单；#174 是本次直接来源。当前 change workflow 保持权威，不让 status 标签代替开发门禁。

## 架构总览
四种 Issue Forms 提供中文字段、静态默认标签；清单统一保存标签名称/颜色/说明；同步脚本显式接受 OWNER/REPO 后逐个 upsert；opened workflow 读取最新 Issue 标签，仅在不存在 status:* 时 addLabels。

## 关键决策

- **采用四种入口。** Bug 记录现象/预期/复现/环境/影响；Feature 记录场景/困难/期望/完成标准；Design 记录待决问题/背景约束/设计产物/评估标准；Maintenance 记录维护问题/影响/期望/验证。通用区域多选允许“不确定”，相关链接可选。正文选择不会自动映射区域标签。
- **四维标签，不预判优先级。** type: bug/feature/refactor/tech-debt/docs/test/ci；area: pa/node/dsh-integration/im-server/web/ios/channels/infra/docs；priority: P0/P1/P2/P3；status: needs-triage/needs-design/ready/blocked/in-progress/needs-verification。type 分诊后一个，area 至少一个，priority 理解后指定，开放 Issue status 一个。ready 不代表通过 unit 门禁。
- **安全默认值。** 所有表单 needs-triage；Bug/Feature/Maintenance 分别加 bug/feature/tech-debt，Design 不定 type。禁用普通贡献者网页空白入口；GitHub 对 Write/Maintain/Admin 保留 Maintainers only 原生例外，CLI/API 仍可创建。
- **标签清单是元数据唯一来源。** .github/labels.json 列出 26 个标签；短 Node CLI `node scripts/sync-issue-labels.mjs OWNER/REPO` 用 gh label create --force 同步，不删除清单外标签，不操作 Issue。显式 repo 避免工作目录推断错目标；失败即非零退出，修正后可重跑。
- **自动化只补状态。** `.github/workflows/issue-triage.yml` 仅 issues: types: [opened]，issues:write 最小权限，无 checkout；github-script 直接读取最新标签，检查 status: 前缀后 addLabels。直接使用 context，不插入用户文本到代码。没有评论、标签移除或历史扫描。
- **长期事实落开发规范。** docs/development/issues.md 解释字段、四维用法、CLI 示例、同步与验收/上线顺序；标签详细说明只在 JSON，规范链接过去。

## 接口与数据流
网页：选择表单 → 填写必填项 → GitHub 建 Issue 并赋静态标签 → opened workflow 检查最新状态。
CLI：gh issue create --repo OWNER/REPO --title ... --body ... --label ... → 相同 opened workflow。
维护：同步命令读取仓库内 labels.json → gh label create --force → GitHub 标签；不会调用 Issue 修改 API。

## 契约层增量 (delta-spec)
no spec delta：不修改 Nano 包的用户行为或 API；GitHub 开发协作规范归 docs/development/issues.md。

## 风险与回退
表单默认标签必须预先存在；先同步主仓标签，PR 合并后表单和 opened workflow 才对主仓生效。私有测试仓库默认分支部署同一受审配置验证，不在主仓创建测试 Issue。回退文件可移除新增入口/自动化，标签不自动删除；无数据迁移。

## Runbook for Reviewer
无常驻服务。验收前置：gh 当前用户有 repo 管理权限；使用仅含本次表单/清单/workflow 的临时私有测试仓库；同一 owner 的 GitHub 浏览器登录。不能登录时明确真实 UI 验收阻塞，不以 YAML 校验替代。
**Review 驱动方式**：真 GitHub 网页验证模板选择、四种表单和必填约束；真 CLI 新建测试 Issue 验证默认与既有状态保留；主仓标签同步后只读核对。测试 Issue 在测试仓库关闭，测试仓库验收后归档保留证据。不修改主仓历史 Issue。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | Issue 提报与分诊 | 无 | 单阶段 | .github/ISSUE_TEMPLATE、.github/labels.json、.github/workflows/issue-triage.yml、scripts/sync-issue-labels.mjs、docs/development/issues.md 与文档入口 | [reviewer] spec 全部场景真实验收；[worker] 表单 schema、标签引用、Action 语法有效；同步重复运行与清单外标签保留；本地适用 CI 与远端 CI 通过 |

## 测试策略
现有 tests/scripts 搜索未发现 Issue 标签同步覆盖。配置使用一次性 schema/引用验证，不新增镜像 YAML 文本的长期测试；同步 CLI 和 workflow 由隔离 GitHub 真栈观察外部结果。测试仓库与原始命令输出留在本机，仓库仅记录可复查结论/版本/URL，不提交缓存日志。

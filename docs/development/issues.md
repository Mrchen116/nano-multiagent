# Issue 提报与分诊

Issue 保存问题、目标与讨论入口；进入开发后，是否建立 change unit 及门禁仍按 [change workflow](change-workflow.md)。标签不替代 unit 文档或验收结论。

## 如何提报

从 [新建 Issue](https://github.com/Mrchen116/nano-multiagent/issues/new/choose) 选择入口：

| 入口 | 应提供的上下文 | 默认标签 |
|---|---|---|
| Bug | 实际现象与影响、预期结果、复现过程、环境版本、修复验证；日志可选 | `type:bug`、`status:needs-triage` |
| Feature | 使用场景、当前困难、期望行为、完成标准 | `type:feature`、`status:needs-triage` |
| Design task | 待决问题、背景约束、预期设计产物、评估标准 | `status:needs-triage` |
| Maintenance | 维护问题、背景与影响范围、期望结果、验证方式 | `type:tech-debt`、`status:needs-triage` |

所有表单都包含影响区域，可多选或填“不确定”；相关资料可选。区域选择保存在正文中，不会自动变成标签。提报者不需要知道内部模块、根因或实现方案。提供日志、截图前去除密钥和私人内容。

正常网页模板选择页关闭空白入口；CLI/API 仍可直接创建 Issue，也应写清上述上下文。Agent 使用 CLI 时显式传已确定的标签，不确定的区域留给维护者分诊：

```bash
gh issue create --repo Mrchen116/nano-multiagent \
  --title '简短描述实际问题' --body-file /tmp/issue-body.md \
  --label type:bug --label area:channels --label status:needs-triage
```

## 如何分诊

标签的名称、颜色和逐项定义只维护在 [labels.json](../../.github/labels.json)。表单固定标签必须引用清单内名称。

| 维度 | 使用规则 |
|---|---|
| `type:*` | 分诊后一个主类型。设计是阶段，Design task 不预判类型；Maintenance 可改为 docs、test、ci 或 refactor 等主类型。替换时移除旧主类型。 |
| `area:*` | 分诊后至少一个，可跨区域；飞书归 channels。按问题实际影响选择，不要求提报者理解代码路径。 |
| `priority:*` | 理解影响后设置一个；P0 立即处理，P1 优先安排，P2 可排期，P3 低紧急度。创建时不默认赋值。 |
| `status:*` | 开放 Issue 同时一个。变更状态时移除原状态；needs-triage → needs-design 或 ready → in-progress → needs-verification 是常见路径，不是自动门禁。blocked 应说明阻塞原因和恢复条件。关闭使用 GitHub 的 Closed，不再新增 closed 标签。 |

`status:ready` 只表示准备推进实现，不证明设计或其他 change unit 门禁已通过。维护者人工执行上述规则；当前自动化只在新 Issue 的 `opened` 事件读取最新标签，如果没有任何 `status:*` 就补 `status:needs-triage`。已有任意状态时不修改；不自动分类、不判断优先级、不发提醒评论、不扫描历史 Issue。CLI/Agent 应传状态标签，不能依赖由 `GITHUB_TOKEN` 创建的事件再次触发 workflow。

保留现有 `bug`、`enhancement` 等旧标签及其归属；新 Issue 使用四维分类。不要在同步标签时顺便批量重新分类历史 Issue。

## 标签维护与启用

先更新 [标签清单](../../.github/labels.json)，再运行同步工具。前置：Node.js、已登录且有目标仓库标签管理权限的 GitHub CLI。

```bash
node scripts/sync-issue-labels.mjs Mrchen116/nano-multiagent
```

目标仓库必须显式给出。脚本逐个创建或更新清单内标签的颜色与说明；重复运行安全，不删除清单外标签，不修改 Issue 的标签归属。中途失败会非零退出，修正权限或网络问题后重跑即可。

上线顺序：先同步仓库标签，再合并表单和 workflow。表单与 `issues` workflow 从默认分支生效；文件中填写 `labels` 不会创建缺失的标签。GitHub 行为参考：[Issue Forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)、[issues 事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#issues)。

修改提报流程时，在隔离测试仓库核验四种网页表单、必填提示、默认标签、CLI 无状态补标签、已有状态保留、无自动评论和重复同步；检查成功的 workflow run 与最终 Issue 标签，不以文件解析通过代替上线行为。测试仓库结束后关闭测试 Issue 并归档；无需在主仓创建测试 Issue。

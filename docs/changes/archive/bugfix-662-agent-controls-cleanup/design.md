# bugfix-662: As-built Design

> 本文在实现完成并获用户确认后形成，记录最终代码，不代表事前设计审查。

## 实现范围

- 执行基线 / `executed_base`：`09eb59bd9073bfd1d071bdfc84bf75a0be99c018`。
- 源码版本 / `validated_at`：`2fd5954dd204b3c553992d995e2b54519999166d`。
- 同步基线 / `effective_base`：`09eb59bd9073bfd1d071bdfc84bf75a0be99c018`；收尾 fetch 后 main 没有增量。
- 代码有效范围 / `effective_through`：上述源码版本及本 unit 的文档归并提交；后续仅补文档，不改变用户已确认的 UI。
- 修改均在 `src/IM/frontend/src/features/settings/agents/`：`agent-lifecycle.tsx`、`agent-row.tsx`、`agent-detail-page.tsx`、`agent-settings.css` 与既有 `agent-lifecycle.test.tsx`。

## 最终结构与调用链

`useAgentLifecycle` 继续通过原查询、用户流与 mutation 取得生命周期快照并提交意图；没有修改请求、缓存、轮询、权限或停止确认规则。

`AgentLifecycleRow` 只向 `AgentRow` 传入非交互的 `statusBadge`，不再渲染行级操作。名称区域使用同行布局：名称可截断，所有权和状态标签不换行；状态仍在导航按钮内可见，不嵌套其他按钮。

`AgentLifecycleStatus` 在正常启用且没有错误时返回空。compact 模式只返回状态标签，读取错误显示「状态未确认」并指向详情；详情中的完整提示保留错误、停止诊断和刷新入口。已确认停用的标签悬停说明启用后旧任务仍暂停。

详情标题旁复用 compact 标签；`showLifecycleNotice` 仅为读取/提交错误或未确认停止保留独立说明区域。已确认停用不再占据标题下的新行。详情页的启停按钮仍即时提交，正常「停用」使用中性样式，失败重试保留警示样式；「重新启用 / Enable again」改为「启用 / Enable」。

## 关键决定与边界

- 列表管理操作集中到详情，避免每行重复红色按钮；列表仍可进入对应 Agent。
- 正常启用不显示默认状态，停用及过渡状态以同行标签表达，避免用隐藏状态换取视觉简洁。
- 设备在线圆点含义不变，不能代替 Agent 生命周期标签。
- 停止失败与未确认状态继续使用原有详细说明和重试逻辑；本变更不将未确认停止视为已停用。
- 纯 Web 呈现变化，不涉及模型可见 Context，也不触发运行时、iOS、数据迁移或安装包发布。
- 回滚为撤销本次 Web 提交，不需要数据回滚。

## 验证定位

- 用户验收：2026-10-26 对话中的最终确认，原话及范围见 [incident.md](incident.md)。
- 既有测试：保留生命周期提交、离线停止、冲突、权限与导航覆盖；只将既有启用用例的按钮查询更新为 `Enable`，未增加布局快照或重复测试。
- 定向验证：列表/侧栏/行/生命周期共 29 项通过；详情/生命周期共 32 项通过；最终文案改动后生命周期 5 项通过。以上套件存在交集，不能相加当作独立测试总数。
- 前端构建与 TypeScript 检查通过。全量检查发现新增 `role=status` 与能力提示共处时使既有单状态查询产生歧义；标签恢复为既有 `aria-live=polite` 提示方式，外观不变。
- 收尾前端全量在 Node 24.22.1、`--maxWorkers=2` 下 108 文件 / 1,031 项通过，最终构建通过，`npm audit --audit-level=critical` 通过（现有 11 个非 critical 告警，不在本次升级依赖）。
- Python 非 E2E 检查 70 passed / 32 deselected，ruff check 与 format 通过；根 TypeScript typecheck 与 packaged iOS runtime 检查通过；文档完整性检查通过。
- 真实 Web：使用 worktree 的隔离 daily IM + Gateway，测试主人和 P/E/Q + PA；列表及详情实际停用，验证标签后重新启用，并观察工作页正常状态消失。
- 截图位于本 worktree 的 `output/playwright/agents-list-disabled-badge.png` 与 `output/playwright/agent-detail-disabled-inline.png`。详情截图先于最后的纯文案修改，图中按钮仍为「重新启用」；最终 `Enable` 文案由后续测试确认，未把旧截图冒充最终文案证据。
- 后端首次全量在本机 Node 25 默认并发下 750 passed / 3 failed，三项失败均为运行时等待超时；这些后端文件与基线完全一致。以 Node 24.22.1、`--maxWorkers=1` 复核三个文件，7 项全部通过；未修改后端或放宽超时。初次失败日志与复核日志分别为本机 `/tmp/bugfix-662-backend-test.log`、`/tmp/bugfix-662-backend-recheck.log`。
- 所有自建浏览器和服务已关闭，端口释放已确认；截图与运行数据不提交，不对线上用户 Agent 执行启停。
- 没有事前 Gate 2、独立 verifier/product reviewer 或独立 Code Review；不补造相应通过记录。审查豁免见 [code-review.md](code-review.md)。

## Canonical 文档影响

最窄 delta 位于 [specs/im/agents-nodes.md](specs/im/agents-nodes.md)，归并至 `docs/specs/im/agents-nodes.md` 的「真人管理者可以独立启用和停用 Agent」。只明确 Web 入口与紧凑展示，原生 iOS 入口和生命周期语义保持。

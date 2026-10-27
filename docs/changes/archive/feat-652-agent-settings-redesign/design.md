# feat-652: As-built Design

> 本文在实现完成、用户亲自查看并确认后，根据代码、diff 与实际验证整理。没有事前 prototype、milestone 或独立产品 reviewer 阶段。

## 实现范围

- 本次改版起点：`630a9734f`，包含已完成的 bugfix-644 与已合并 feat-645。
- 用户验收的实现：`9f7a1ee4a`；同步最新 main 后源码：`8024db2f644408f1b412f108c60c40c45009d671`。
- PR base：`d5b3577923e3dff74de47d947e49c1f963ef91e0`；完整 PR 还包含尚未合并的 bugfix-644，其独立审查与产品验证保留在该归档 unit。
- 本次包含的未提交实现文件：无。
- 改版 commits：`51f4c4c97`、`cf579df5c`、`5db9b80e2`、`2e46605cc`、`eb7f904e7`、`9f7a1ee4a`。

## 最终结构

### 组件与职责

`agent-settings.css` 以 Agent 页面 class 限定布局：白色连续内容区、细分隔线、桌面标签列与相关字段并排、移动单栏、页底保存/创建操作。`AgentDetailPage` 与 `AgentCreatePage` 保留原有表单、依赖联动和可恢复 operation 逻辑；只调整信息顺序、展示与响应式父级。

`AgentsListPage` 展示原有可访问 Agent 目录，桌面两列、窄屏一列；本人 PA 独立展示。详情和创建仍使用 `AgentsRailDesktop` 连续导航，公开资料复用相同页头与元信息样式。可见性仍来自 contacts 服务，只有 owner 进入可编辑配置。

`AgentOverviewPanel` 读取保存态配置；`AgentSessionsPanel` 复用当前身份的会话列表，按来源 Agent 或成员关联筛选、排序和搜索，通过既有 mention 解析器展示预览并链接原聊天。没有新增会话读取权限或后端查询旁路。

通道、Skills、Plugins、本人 PA 设置与创建弹窗继续使用原有数据及 mutation 路径。删除重复用途说明、宽大空卡片和重复动作；保留特性用途、依赖限制、密钥/隐私范围、卸载后果、离线与待确认状态。

### 继承审批策略数据流

`NodeConfiguration.inheritedApproval(workspace)` 返回运行配置原先使用的同一份缓存策略副本，Agent 覆盖在之后应用。Node 的 node/agent capabilities 增加可选 `inherited_approval_rules`；IM 投影、设置展示快照及前端归一化将其传给共享 `ApprovalModeField`。选项显示 CC/Codex/DSH 或“策略未确认”，提交值仍为空表示继承。旧节点缺失该字段不会猜测策略。创建表单针对已选择的真实工作区，经 owner 受限的只读 approval RPC 查询同一缓存策略；输入变化期间显示未确认，读取不创建目录、不调用模型 catalog。

### 状态与兼容性

保留 bugfix-644 的已确认数据/历史快照/未知区分、只读门控、连接恢复重读、草稿与操作结果待确认语义；保留 feat-645 的 Feature、Tool、Skill 依赖和工作占用阻止。响应式布局只切换侧栏可见性，保持表单父级结构，避免通道表单跨断点重新挂载而丢草稿。

无需数据或身份迁移。新增 capabilities 字段为可选，回退旧 UI 可忽略它；完整服务回退须保留 bugfix-644 的历史表和原数据。全局模式只移除“实验”文字，不改变运行模式或创建后的不可切换约束。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 复用真实组件直接迭代 | 用户明确要求 worktree 真页面，不制作 prototype | Agent 页面与本 unit spec 澄清 |
| 单一保存/创建入口，能力用途常显 | 减少重复动作，同时保证特性开关可理解 | detail/create、agent-settings.css |
| 概览与会话使用现有数据 | 替换占位内容，避免另建权限或会话系统 | agent-summary-panels.tsx |
| 继承策略由实际配置提供 | 用户要求知道继承的是哪一种策略，不能用模型名称推断 | configuration.ts、main.ts、control.ts、ApprovalModeField |
| 目录继续混合可访问 Agent | 用户了解可见性后明确保留当前方案 | agents-list-page.tsx、public-agents.ts |

## 失败路径、风险与回滚

读取失败保持可重试状态，不当作空结果；离线只读和异步结果未确认仍依赖现有后端门控。当前只读会话列表按授权数据过滤；不会绕过联系人或会话鉴权。旧节点不报告继承策略时显示未确认。样式作用域局限 Agent 页面及 PA 弹窗，避免全站改版。回退前端可恢复旧展示；涉及本次可选 capabilities 字段时不需要清库或改钥。

## 与初始意图的差异

用户在迭代中补充：特性用途必须可见；继承策略需显示真实值；创建页应一并改版；Agent 相关页面整体复查；全局模式移除实验标记。以上均已纳入 spec。用户最后明确同意现状并授权合并和部署；目录暂不拆成“我的/发现”。

## 验证定位

- 用户验收：本 unit spec 的原话、持续真实页面反馈与最终合入/部署指令。
- 前端：Agent 设置与 PA 相关测试、跨屏保留通道草稿、目录搜索、继承策略、创建和会话权限过滤。
- 后端：Node 配置策略继承以及 IM capabilities/快照读数测试。
- 真实页面：桌面 1440×1000、窄屏 390×844；真实创建、取消草稿、通道未提交草稿跨屏保留、插件详情、PA 设置与定期清单。原始截图和日志在任务本地产物中，不提交凭据或运行数据。
- 覆盖限制：本轮公开资料访客路径由代码与自动化测试覆盖；不把空 Skills 使用统计或工作记录当作有任务数据的真实验收。飞书外发、原生 iOS 视觉不属于本次改版。原 bugfix-644 的原生和产品验证单独保留。
- main 集成：`d50559ea5..d5b357792` 涉及 Task 续跑/静默反馈及默认 Codex 策略，与改版无布局冲突；审批策略从同一真实来源读取，前后端本地 CI 和本次 full code review 覆盖集成树。用户已确认的 UI 布局/权限旅程未被该增量改变。

## Canonical 文档影响

最窄 delta 为 `specs/im/agents-nodes.md`：真实继承策略、跨屏草稿保留、设备标注重排、概览和关联会话。归并到 `docs/specs/im/agents-nodes.md`，入口计数同步。具体字号、padding、颜色等设计参数留在 CSS，不复制为长期契约。

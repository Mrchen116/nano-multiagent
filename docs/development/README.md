# Development

本目录负责改变仓库：选择变更流程，建立本地开发环境，获得测试和真实运行反馈，并遵守代码与文档约定。日常启动、观察和恢复当前系统由 [`../operations/`](../operations/README.md) 负责。

## 从哪里开始

| 任务 | 先读 |
|---|---|
| 判断是否建立 change unit、选择 Full 或 Bugfix lite | [`change-workflow.md`](change-workflow.md) |
| 安装环境、运行常用命令、开发 CLI 或前端 | [`local-development.md`](local-development.md) |
| 决定测什么、测试放在哪一层 | [`testing.md`](testing.md) |
| 判断某类证据能证明什么、结果保存在哪里 | [`evidence.md`](evidence.md) |
| 设计、移动、退役或治理仓库知识 | [`documentation-system.md`](documentation-system.md)（Draft） |
| 在 worktree 内启动隔离 IM、Gateway 或 Vite | [`worktree-runtime.md`](worktree-runtime.md) |
| 查看必须长期守护的真实用户旅程 | [`e2e-critical-paths.md`](e2e-critical-paths.md) |
| 编写 docstring、注释或 TODO/FIXME | [`commenting.md`](commenting.md) |
| 联调 LLM provider、本地代理或查看交互日志 | [`llm-integration.md`](llm-integration.md) |
| 编写 current spec 或归并 delta-spec | [`../specs/CONTRIBUTING.md`](../specs/CONTRIBUTING.md) |
| 查 change unit 的目录、文件归属和归档规则 | [`../changes/README.md`](../changes/README.md) |

## 文档分工

| 文档 | 负责的事实 |
|---|---|
| [`change-workflow.md`](change-workflow.md) | 何时建 unit、Full/Bugfix lite 生命周期、角色和门禁 |
| [`local-development.md`](local-development.md) | Python/前端环境、常用命令、测试身份和提交格式 |
| [`testing.md`](testing.md) | 测试选择、分层、命名、长期回归与临时证据边界 |
| [`evidence.md`](evidence.md) | 测试、CI、真栈、报告、runtime 与 LLM 日志的能力边界和归并规则 |
| [`documentation-system.md`](documentation-system.md) | Agent-Native 仓库知识体系方法论与维护检查表；完成本次迁移验证前为 Draft |
| [`worktree-runtime.md`](worktree-runtime.md) | 临时服务的端口、config、数据、进程和清理契约 |
| [`e2e-critical-paths.md`](e2e-critical-paths.md) | 用户旅程与长期 E2E 守护测试的对账 |
| [`commenting.md`](commenting.md) | public API docstring、意图注释和 TODO/FIXME 规则 |
| [`llm-integration.md`](llm-integration.md) | 本地 LLM 代理入口、协议、日志和最近验证记录 |

## 开发反馈顺序

1. 从 [`../specs/`](../specs/README.md) 或当前 change unit 确认要改变的行为和退出标准。
2. 按 [`change-workflow.md`](change-workflow.md) 选择流程，在既有行为的最低有效层运行最窄反馈。
3. 代码级反馈通过后，再按风险扩大到 integration、contract、前端构建或完整测试。
4. 涉及真实进程、浏览器或用户主链路时，使用 [`worktree-runtime.md`](worktree-runtime.md) 建立隔离环境，并对照 [`e2e-critical-paths.md`](e2e-critical-paths.md) 判断是否需要长期守护。
5. 按 [`evidence.md`](evidence.md) 记录 claim、baseline、method、result、locator 和 limit；交付前把验证过的长期结论归并到唯一 owner。

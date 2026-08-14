# 真实入口与运行证据

只在 assignment 触及相应风险时读取本文件。目标是证明用户或外部消费者实际经过的链路可用，不是为所有改动统一增加 E2E。

## 选择入口

| 改动 | 最低必要入口 |
|---|---|
| 后端/API 新能力 | 客户端实际使用的 HTTP/CLI/public SDK 入口 |
| 用户报告的运行时 bug | 报告中同一触发路径；修前可复现、修后症状消失 |
| 普通前端 UI | 真浏览器打开产品页面，执行受影响交互 |
| 前端核心路径或历史回归 | 真浏览器验收 + 与现有体系相称的可重复 regression |
| 视觉/响应式改动 | 真浏览器、适用 viewport/状态、截图或录屏；不强行写 E2E |
| 跨进程、投递、调度、集成 | 启动真实隔离服务，跑到用户可见结果 |
| 纯内部重构且入口不变 | 相关自动化测试；不额外制造 live 验收 |

mock、stub、进程内 tick 和组件测试可以补充，但不能替代本次风险所在的真实缝。

## 运行时隔离

启动服务前读取 `docs/development/worktree-runtime.md`，为当前 worktree 分配隔离端口、配置、运行数据、workspace 和 node identity。优先使用仓库提供的 `scripts/e2e-up.sh` / `scripts/e2e-down.sh`。

记录自己启动的进程；DONE、HANDOFF 或 BLOCKED 前停止并确认资源释放。资源无法隔离或必需外部环境不可用时如实报告阻塞。

## 前端验收

只覆盖与改动和 design 明确相关的状态，不枚举一排 `N/A`：

- 执行关键点击、输入、选择或提交；
- 检查 console error 和 failed network request；
- 覆盖适用的 default/loading/empty/error/disabled/long-content/permission 状态；
- 覆盖 design 要求的 desktop/mobile viewport；
- 核心路径和历史 bug 留下可重复 regression；纯视觉状态以可复查截图为主。

存在 `prototype.html`、设计稿或 reference contract 时，逐项记录 must-match 对象、实际 evidence、viewport/状态和 match/deviation。偏离必须已有 design 授权；不清楚时暂停询问 orchestrator。

## Evidence

提交给下游使用的截图、录屏或对照结果必须在 unit 目录或其他仓库内持久路径；不要只给 `/tmp`、浏览器临时状态或将被删除的 worktree 外部缓存。

每条关键 evidence 至少能回答：

- Claim：证明哪条退出标准；
- Baseline：branch/head 和关键环境；
- Method：命令或用户路径；
- Result：具体观察和 pass/fail；
- Locator：测试名、文件路径、日志/session id；
- Limit：未覆盖什么。

完整证据边界见 `docs/development/evidence.md`。

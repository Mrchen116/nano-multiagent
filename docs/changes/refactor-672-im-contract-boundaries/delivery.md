# refactor-672 交付记录

## 交付范围

中心全部 21 个主动节点 RPC 通过有限命令表关联输入、输出与响应名，NodeRpc 独立拥有请求关联、连接引用、定时器和关闭。配置路径的 HTTP 输入、业务候选、固定 SQLite 记录、wire 回执与公开 View 分别具名；ConfigOperations 仅依赖数据库、三个配置 RPC 和事务提交后的生命周期投递，完整保留恢复、CAS 补偿及 PA restore。

聊天、Work、Channel 上行业务的 Row/ImContext 尚未全面迁移，本 unit 不宣称全 IM 类型迁移完成。动态插件/provider/工具目录保留扩展载荷。无 schema、协议版本、模型上下文语义或序列化算法变化，无部署迁移；no spec delta，经独立 verifier 确认无需改 current specs。

并行序列化任务可能在 `apps/im-server/src/control.ts`、`packages/product-contracts/src/index.ts` 交叉；本任务保留 asciiJson/candidateFingerprint 及调用语义。原报告未改，派发基线的两笔本地文档提交未带入 PR；报告副本保留在本 worktree 忽略的 `.e2e-refactor-672/architecture-review-baseline.html`。

## 版本与门禁有效性

- 派发基线：`a34af8473c15f1145d6a1dbbc036bc320560f351`。
- final sync / executed_base / effective_base：`ff326c351d104447028f4b185740ab6d6be55de6`。
- 产品验收、full code review、full verification 的 validated_at：`648b5439e914d6cf90f85a5296734c0e77e3c7eb`。
- effective_through：上述完整实现树；随后只加入报告、交付记录和整个 unit 的归档移动，产品与测试树未再修改，三道门禁 retained。PR body 记录最终文档提交 head；不能把报告提交称为重新执行过产品验收。
- Gate 2：design-review Approved，0 CRITICAL / 0 WARNING；实现未改变审定关键设计。
- Code review：`[]`；verification：0 CRITICAL / 0 WARNING，aligned / no spec delta；限定 Agent Context Mode B 无 finding。
- Acceptance：pass，3/3 必验场景，0 blocking / major / minor；真实 HTTP/WS/SQLite 与协议测试节点，不声称真实 Node 工作区落盘或模型验收。

## 本地验证

Node 24.22.1；日志保存在本 worktree 的 `.e2e-refactor-672/`，不提交运行数据。

- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`：通过；包括 IM command/record/view 编译负例。
- `pytest -m 'not e2e' -q`：100 passed / 28 deselected。
- `ruff check .`、`ruff format --check .`：通过。
- `scripts/docs-check`：通过；归档后再次检查路径。
- 前端 npm ci、共享 contracts build、critical audit：通过；`npm run test -- --maxWorkers=2 --no-file-parallelism`：108 files / 1029 tests passed。
- 后端 `vitest run --maxWorkers=2 --no-file-parallelism`：145 files，777 passed / 2 failed；两项失败均原样定向复测通过（见下）。不声称单次全量全绿。

### 超时调查

同步前后默认并发运行出现知识维护及多项 DSH 超时。现场记录主机 load averages 474.29 / 189.40 / 89.73，并存在另一聊天的全量测试；仅停止本任务的高并发后端/前端测试及其派生进程，未动其他任务或生产。

之后限制 worker 和文件并行，不改变任何产品代码、测试断言或超时阈值。`knowledge-policy.test.ts` 在负载回落后原样单独复跑 5/5 通过（7.37 秒，`knowledge-low-load.log`）。另一次 agent-disable-native 的 descendants/Bash/PTY 用例失败，原样定向复跑 1 passed / 6 skipped（12.80 秒，`disable-low-load.log`）。这支持时序敏感性，不将原始失败抹除，也不声称已修复该测试的稳定性。远端 CI 继续执行默认完整命令。

## 现场

专用 IM PID 69336 已停止；验收者客户端全部关闭。原始协议证据和测试日志保留在忽略目录。开发 worktree `/Users/czj/.codex/worktrees/im-contract-boundaries/nano-multiagent` 与 `codex/im-contract-boundaries` 分支在 PR 未合入前保留。没有合并、部署、发布安装包或修改生产。

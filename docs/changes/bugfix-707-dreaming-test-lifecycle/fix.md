# bugfix-707: 自动 Dreaming 轨迹回归等待实际会话释放

## 原始报告

> 主分支为啥有失败？能修吗？

本问题来自 bugfix-706 本地验证；本 unit 修复独立的后台回归不稳定性，保留日期实现。

## 现象 / 复现

主分支 `43cc90051` 在本机运行 dreaming-runtime.test.ts：自动整理用例报 `RpcError: generation_changed`，其余五项通过。单独重跑自动用例又通过，说明是时序相关失败。原始日志 `/tmp/bugfix706-main-baseline.log`、单用例通过日志 `/tmp/bugfix707-dreaming-repro.log`。

同一提交 GitHub CI（run 41656197526）及前两次 main CI 均成功；不能把本机失败表述为主分支远端 CI 失败。上轮同时运行前端、构建、后端及隔离起栈，原生运行时测试还出现资源竞争下的 deadline/timeout；不把全部失败推断为一个产品缺陷。

目标：自动整理完成后，回归测试在真实临时会话释放后核对其完整持久轨迹与重启一致性；不放宽断言、不吞掉 generation_changed、不扩大生产 deadline。完整本地后端复验隔离执行并限制 worker 数量，检查是否仍有独立失败。

## 根因

自动用例由 `326dac00ed` 加入，沿用手动用例的完成判断。手动工具调用等待维护 Promise 完成；自动路径只轮询 review.status=completed。Dreaming 的 apply 先保存 completed，再提交进度、写入应用回执，随后 execute 才释放 handle。测试观察 completed 并不代表临时 session 已释放。

NativeTrajectory 正确地把 live session 的释放报告为 generation_changed，防止跨代读取混合数据；本测试却在自动释放边界打开 follow，偶发拿到该错误。保留这一生产边界以及原有应用结果、工具权限、原始输入、宿主回执与重启轨迹相等断言；用 fixture 内公开 session/disposed 事件确认该临时会话已经脱离 live store，再读取持久轨迹。无需改变生产状态、提示词、来源或 DSH 接入。

## 修复

`e16c276b8`：在现有 Dreaming fixture 记录公开 session/disposed 事件，并在读取整理轨迹前等待对应 childSessionId 的实际释放。只修改既有回归文件，不新增生产查询接口、重试或延长 timeout。manual/automatic 三种组合共用相同的确定等待条件。

## 验证

- 既有失败证据：主分支自动用例出现 generation_changed；单独重跑通过，保留为时序问题而非稳定产品失败的证据。
- 修改后 Dreaming、native trajectory、trajectory stream 共 3 files / 12 tests passed（`/tmp/bugfix707-targeted.log`），真实锁定 DSH 和 fixture provider，无真实模型请求。既有冷读不激活、跨代中断、宿主回执、完整输入及重启一致性覆盖均保留。
- 测试策略：修正现有最低层原生集成测试的完成前提，不新建重复回归、不减少旧断言；生命周期信号仅由测试 fixture 记录，临时文件随测试 home 删除。
- 独立 code review 无 findings，见 `code-review.md`。
- No spec delta：产品对外行为及 Agent Context 均未改变，无部署或迁移需要。
- 后端完整运行 `pnpm test --maxWorkers=2`：210 files 中 208 passed / 2 failed，1125 tests 中 1123 passed / 2 failed（`/tmp/bugfix707-backend-full.log`）。Dreaming 回归通过；残留为 legacy knowledge 的整体 30 秒超时、configuration-inspector 的临时清理确认失败。
- 对上述两个失败文件以 `--maxWorkers=1` 串行隔离复验：2 files / 12 tests 全部通过，44.56 秒（`/tmp/bugfix707-remaining-serial.log`）。结合完整运行中其余文件的结果，全部后端用例均有同版本的通过证据；这不是“一次全量全绿”，保留原失败，不把本机耗时压力包装为已修复的生产缺陷。
- 本机其他运行任务曾占用多个 CPU 核，前轮亦叠加前端/构建/隔离起栈；默认 CI 及生产 deadline 不因本轮而改变。没有停止或修改生产进程。后续本机验证需对 native profile 文件保留足够运行资源。
- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`、Python non-E2E 129 tests、ruff check/format、docs-check 通过（`/tmp/bugfix707-{build,typecheck,assets,python,ruff,docs}.log`）。没有 Web/iOS 源码变更；既有主分支 Web CI 成功结果保持适用，远端 PR CI 仍运行其默认检查。

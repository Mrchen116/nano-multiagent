# refactor-672 交付记录

## 交付范围

中心全部 21 个主动节点 RPC 通过有限命令表关联输入、输出与响应名，NodeRpc 独立拥有请求关联、连接引用、定时器和关闭。配置路径的 HTTP 输入、业务候选、固定 SQLite 记录、wire 回执与公开 View 分别具名；ConfigOperations 仅依赖数据库、三个配置 RPC 和事务提交后的生命周期投递，完整保留恢复、CAS 补偿及 PA restore。

本 PR 按用户追加授权增加 M3：Work 的已知事实、日志身份与同步输入形成共享契约，PA 生产方法保持 type/payload 关联；中心 WorkRecords 独立拥有事务日志、投影、水位及固定记录/公开页，批量、分段和 WS 入口共用 decoder。工具参数/结果及未知扩展事件保留原值。会话/联系人/Channel 管理与 Work 的聊天查询/命令路由仍未全面迁移，本 unit 不宣称全 IM 类型迁移完成。动态插件/provider/工具目录保留扩展载荷。无 schema、协议版本、模型上下文语义或序列化算法变化，无部署迁移；no spec delta，经独立 verifier 确认无需改 current specs。

M4 将聊天发送和流式完整链纳入本 PR：PA SingleThread/GlobalAgent 的有限生产契约贯通 External 转发/outbox、IM 输入解码、发送事务、MessageRecords 和 ChatStreaming。普通发送与 Agent publication 保留各自幂等规则；公开消息、SQL JSON 列与内部元数据分离；固定事件类型关联载荷，正文增量保持窄查询。既有 UI schema、交互指纹、投递队列、模型输入组装及序列化 owner 继续复用。

并行序列化 refactor-671 已合入主干。本任务已集成其 `sortedJsonUtf8` / `sortedJsonAscii` 子路径导出及 `serializeCandidateJson` 命名，保留本任务配置服务拆分与类型约束，不重复迁移算法。交叉点 `control.ts`、Gateway、control/approval 测试 import 与 contracts index 已核对。原报告未改，派发基线的两笔本地文档提交未带入 PR；报告副本保留在本 worktree 忽略的 `.e2e-refactor-672/architecture-review-baseline.html`。

## M1/M2 已完成交付的版本与门禁有效性

- 派发基线：`a34af8473c15f1145d6a1dbbc036bc320560f351`。
- Round 1 executed_base：`ff326c351d104447028f4b185740ab6d6be55de6`。
- Round 2 final integration executed_base：`b8fc5edefcb74ec8a8888aeb7fa245779e644253`；validated_at：`fc0dca156b3c3cce9602d39e7c47a601ad86b038`。
- 产品验收、full code review、full verification 的 validated_at：`648b5439e914d6cf90f85a5296734c0e77e3c7eb`。
- effective_base / effective_through：最终 effective_base 为 `532704f7168e4eb350b3f830d47fbeb701a13731`（相对 Round 2 只新增 refactor-675 事前文档）；effective_through 以最终 PR body 记录为准。第二轮已复核序列化与任务关闭主干增量；后续纯文档主干提交、报告和 unit 归档不改变产品/测试树，门禁 retained。不能把文档提交称为重新执行过产品验收。
- Gate 2：design-review Approved，0 CRITICAL / 0 WARNING；实现未改变审定关键设计。
- Code review：`[]`；verification：0 CRITICAL / 0 WARNING，aligned / no spec delta；限定 Agent Context Mode B 无 finding。
- Acceptance：pass，3/3 必验场景，0 blocking / major / minor；真实 HTTP/WS/SQLite 与协议测试节点，不声称真实 Node 工作区落盘或模型验收。

## M1/M2 已完成交付的本地验证

Node 24.22.1；日志保存在本 worktree 的 `.e2e-refactor-672/`，不提交运行数据。

- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`：通过；包括 IM command/record/view 编译负例。
- `pytest -m 'not e2e' -q`：100 passed / 28 deselected。
- `ruff check .`、`ruff format --check .`：通过。
- `scripts/docs-check`：通过；归档后再次检查路径。
- 前端 npm ci、共享 contracts build、critical audit：通过；`npm run test -- --maxWorkers=2 --no-file-parallelism`：108 files / 1029 tests passed。
- 最终集成树 build/typecheck 通过；control、approval、configuration-boundaries、node-rpc、e2e/control-work、agent-settings、personal-agent、PA configuration 共 8 files / 77 tests 通过，包含主干新增字节兼容保护。
- 后端 `vitest run --maxWorkers=2 --no-file-parallelism`：145 files，777 passed / 2 failed；两项失败均原样定向复测通过（见下）。不声称单次全量全绿。

### 超时调查

同步前后默认并发运行出现知识维护及多项 DSH 超时。现场记录主机 load averages 474.29 / 189.40 / 89.73，并存在另一聊天的全量测试；仅停止本任务的高并发后端/前端测试及其派生进程，未动其他任务或生产。

之后限制 worker 和文件并行，不改变任何产品代码、测试断言或超时阈值。`knowledge-policy.test.ts` 在负载回落后原样单独复跑 5/5 通过（7.37 秒，`knowledge-low-load.log`）。另一次 agent-disable-native 的 descendants/Bash/PTY 用例失败，原样定向复跑 1 passed / 6 skipped（12.80 秒，`disable-low-load.log`）。这支持时序敏感性，不将原始失败抹除，也不声称已修复该测试的稳定性。远端 CI 继续执行默认完整命令。

## M1/M2 已完成交付的现场

Round 1 专用 IM PID 69336 已停止；Round 2 专用 IM PID 84625 也已停止；验收者客户端全部关闭。原始协议证据和测试日志保留在忽略目录。开发 worktree `/Users/czj/.codex/worktrees/im-contract-boundaries/nano-multiagent` 与 `codex/im-contract-boundaries` 分支在 PR 未合入前保留。没有合并、部署、发布安装包或修改生产。

## M3 Work 扩展的版本与验证

- 扩展设计：`bd0938462`；Gate 2 Round 2 Approved，0 CRITICAL / 0 WARNING。
- 实现冻结：`badc559a1937b9b7b34b75df4d5a3ba0f5137e22`；executed_base `94b06908d396c8039d820124c4d86cb32a75eaf4`。
- 完整 build、typecheck、iOS runtime 包装检查通过；IM/PA 的常规 typecheck 均包含编译负例。
- 集成定向 10 文件 / 110 项通过。独立 IM 子进程上的生产链测试使用真实 GlobalAgent、InboxStore、WorkSync 及 HTTP/WS/SQLite，RuntimePort 的原生事实为确定性 fixture；包含主子归属、完整大工具内容、统计保真、刷新、重启、重复提交及畸形 WS 拒绝。
- Python 100 项通过，Ruff check/format、文档检查通过；文档脚本用仓库依赖所在的 Python 3.12 解释器执行。
- 前端 108 文件 / 1029 项通过，安装、shared contracts 编译、critical audit 通过。
- 独立审查在 `badc559a1` 确认权限选项漏检；修复 `197da048e` 以共享 option/id 校验阻止畸形 flat/nested 记录落盘。红测 2 项失败，修复后相关 3 文件 / 23 项通过，PA/IM 编译负例通过。
- 后端完整运行 147 文件 / 794 passed、2 failed（`m3-backend-full.log`）；该运行从 13:26:15 开始，跨越新增权限红测及修复，两个失败均为新增权限反例返回 200，不能称作修复版单次全绿。相关修复已有 23 项绿测，固定修复版重跑完整 WorkSync 文件 15/15 通过（`m3-work-sync-final.log`），build/typecheck 也再次通过（`m3-build-final.log`、`m3-typecheck-final.log`）；最终完整结果由远端 CI 承接。
- 独立 code review / verification Round 4 pass，findings `[]`，0 CRITICAL / WARNING，aligned / no spec delta；产品验收 Round 4 pass，原 major M3-AC-1 closed，最终无未解决问题。未受影响的 M3 场景及 M1/M2 门禁 retained。
- 最终 fetch 的 origin/main 仍为 `94b06908d`；报告追加、标题更新和归档仅为文档，产品树保持 `197da048e`。最终 effective_base 为 `94b06908d396c8039d820124c4d86cb32a75eaf4`，effective_through 在 PR body 记录最终提交。

### M3 现场与最终限制

验收初始专用 PID 4739、恢复用 PID 6509 和修复复验用 PID 7760 均已停止，最后 PID 7760 已核实退出。验收客户端、GlobalAgent、WorkSync 和本地 stores 全部关闭。原始日志、SQLite 和协议证据留在忽略目录，不提交；worktree 在 PR 未合入前保留。无模型语义/客户端视觉新结论，无生产操作、合并或发布。

## M4 实施与修复验证

- Full validated_at：`39f159d9f0a9089023939fa2f9e2569542f8037e`，范围 `c90f5e968..39f159d9f`；M1–M3 未改实现按共享影响 retained。
- 独立静态审查/产品验收 Round 5 确认同一缺口：首次 permission_resolved 的 nested 执行身份未校验，会落盘广播。修复 `21b09d3e4892806d77829d6e9c2af1cdec6f6087` 共用 flat/nested 身份检查，保留 lifecycle null 与动态字段；未扩大方案或修改 current spec。
- 修复前真实 WS 反例得到 ACK 而失败（m4-permission-e2e-red.log）；修复后相关 6 文件/34 passed（m4-permission-green.log），IM/PA 类型检查通过。
- 39f 冻结版本本地后端全量：150 文件/800 passed，未跨越修复修改；前端 108 文件/1029 passed；Python 100 passed/28 deselected；Ruff 与文档检查通过。最终修复版本复验受影响完整文件，其余证据保留，远端 CI 运行最终固定提交。
- 真实 SingleThread→WS→IM SQLite→HTTP/history/user-stream 及独立验收验证运行链；RuntimePort 仅为确定性 native 事实 fixture，无真实模型行为结论。current spec 中 provisional discard 的原子投影回滚存在既有 drift，本轮明确不将其记为实现或通过；本次无 schema/协议版本/部署迁移。

M4 closure：code-review / verification Round 6 pass，findings []，0 CRITICAL/WARNING，aligned/no spec delta；产品验收 Round 6 pass，M4-AC-1 closed。validated_at 为 `21b09d3e4892806d77829d6e9c2af1cdec6f6087`。独立 source decoder 的 20 个两分支/flat/nested/五字段反例均拒绝，合法 null/动态扩展保留原引用及字节。最终 `m4-build-final.log` 的构建 metadata 绑定 21b；全包 typecheck、iOS runtime 包装和 critical audit 门槛通过（现有依赖审计仍有 5 high，未改变依赖）。测试服务 14882 和 20870、验收客户端均已停止；运行数据仅存忽略目录。

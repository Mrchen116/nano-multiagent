# Design 评审：refactor-476-permission-transaction-owner

**结论**：Issues Found

这份方案对 permission transaction 的核心归属、carrier/supervisor 解耦、publisher fail-closed
以及可信 builtin 注入已经拍得很深；但当前仍有 2 个会让实现或长期契约直接失真的
CRITICAL，以及 2 个会让 worker/reviewer 分叉的 WARNING。修正前不应交给
`change-orchestrator`。

## 核实台账

下表按「现状断言 → 编号决策 → motivation 约束 → delta-spec → milestone」逐项核实。

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状范围 1：`AgentEngine._build_hook_context()` 承担完整权限事务 | 从 SDK 装配正向追到生产 hook context | ✓ `build_kernel` 把同一 broker/event hub 装入 engine（`src/agent/sdk/kernel.py:590-620`）；生产 `_build_hook_context` 内依次 register、publish、heartbeat、local/remote race、private pop、resolved 与 cleanup（`src/agent/core/agent/runtime.py:1204-1434`），不是测试死路径。 |
| 现状范围 2：broker 保存 pending/run scope/allowlist/deny count | 读 broker 的真实可变状态与入口 | ✓ broker 自称 sole coordinator（`src/agent/platform/permissions/broker.py:1-13`），`_pending`/lock、register/resolve/cancel 位于 `:102-226`，deny count 与 session allowlist 位于 `:232-319`。 |
| 现状范围 3：SDK 负责 broker 装配、外部决定与 cancel/interrupt | 从 public Kernel 入口回追 | ✓ 每次装配新 broker（`src/agent/sdk/kernel.py:533`）；external response 经 `submit_permission_decision` 原子 resolve（`:1473-1519`）；interrupt/cancel 当前在 carrier 操作后再清 broker（`:1456-1471`、`:1521-1538`）。 |
| 现状范围 4：`auto_mode_gate` 决定 allow/deny/ask 并经 HookContext 等待 | 追 `ToolRegistry → HookRunner → builtin hook` | ✓ ToolRegistry 仅在 hook payload `block=True` 时阻止执行（`src/agent/core/tools/registry.py:207-241`）；HookRunner 对普通 hook error 继续（`src/agent/core/hooks/runner.py:104-157`）；`_handle_ask` 经 `request_permission` 等待且异常映射为 block（`src/agent/platform/hooks/builtins/auto_mode_gate.py:653-710`）。 |
| 现状范围 5：CLI normal reader 与 permission picker 都读 stdin | 追 CLI 生产入口的两个 reader | ✓ normal REPL 由 executor 反复调用 reader（`src/coding_cli/commands.py:597-604,640-707`），permission callback 又在另一 executor 调 picker（`:387-424`）；non-TTY 两处最终分别调用 `input()`（`src/coding_cli/input/repl_input.py:76-103,803-866`）。 |
| 现状范围 6：CLI/Gateway adapter 不拥有 pending | 查两产品的生产 adapter | ✓ CLI callback 只返回 `PermissionDecision`（`src/coding_cli/commands.py:387-424`）；Gateway handler 只转调 Kernel decision API（`src/personal_assistant/ws/im_connection.py:167-188`）；pending 只在 broker。 |
| 断裂 1：engine 与 broker 分享 transaction 不变量且 engine 访问私有字段 | 查真实 pop/lock 所有者 | ✓ engine 直接进入 `broker._lock` 并 pop `broker._pending`（`src/agent/core/agent/runtime.py:1386-1397`），与 broker 的 sole-owner 声明冲突。 |
| 断裂 2：RunsRegistry 先强杀 carrier，SDK 后 cancel broker | 核 interrupt/cancel 的同步调用顺序 | ✓ registry 在 interrupt/cancel 内 force-cancel target（`src/agent/core/runs/registry.py:263-323,409-445`），Kernel 返回后才调 broker（`src/agent/sdk/kernel.py:1465-1470,1534-1538`）。 |
| 断裂 3：CLI main loop 与 Kernel executor loop 分离 | 查两个 loop 的创建与调用位置 | ✓ `_async_main` 在 consumer loop（`src/coding_cli/commands.py:246-292`）；每个 `KernelExecutor` 自建 thread/loop（`src/agent/core/runs/executor.py:145-168,500-511`）。 |
| 断裂 4：取消 asyncio input future 不能停底层线程 | 查 current cleanup 与 blocking read | ✓ REPL finally 只 cancel executor future（`src/coding_cli/commands.py:870-879`），而 reader/picker 正阻塞在同步 stdin（`src/coding_cli/input/repl_input.py:76-103,803-893`）。 |
| 断裂 5：每次 build 的 broker/executor/runs 是实例资源；不得据此泛化为整个 Kernel 独立 | 同时查 per-build graph 与 module globals | ✗ broker/executor/runs 确实逐 build 新建（`src/agent/sdk/kernel.py:533,590-621,672-794`），但模型目录仍是 module singleton `_REGISTRY`（`src/agent/core/llm/model_registry.py:36-48`）；每次 build 会 reset/re-init 它（`src/agent/sdk/kernel.py:305-359`），而既有 K1 后续 submit 仍经全局 `provider_of()` 路由（`src/agent/core/agent/runtime.py:1455-1469`、`src/agent/core/agent/loop.py:131-147`）。因此 design/sdk delta 的“每个 Kernel 可独立使用”前提不成立。 |
| 断裂 6：canonical 非 TTY 契约错误绑定 `input()` | 对照 canonical 与可观察行为 | ✓ canonical 明写 `input()`（`docs/specs/cli/spec.md:148-156`），而真正要守的是逐行、正常退出、无 ANSI；写完整 MODIFIED delta 是正确手法。 |
| 约束 1：`core` 不得 import platform | 查架构契约与 current imports | ✓ `SPEC.md` 的三层依赖方向与 `tests/contract` 硬闸一致；设计把 factory Protocol 放 core、实现放 platform（design 决策 2），未形成反向依赖。 |
| 约束 2：产品只 import `agent.sdk`，公开面精确守卫 | 查 public surface 与 guard | ✓ 当前 surface 在 `src/agent/sdk/__init__.py:21-81`，精确 allowlist/owner guard 在 `tests/contract/test_agent_sdk_surface_guard.py:38-149`；设计明确同步新增两项。 |
| 约束 3：register-before-publish、first-wins、run-scoped cancel | 对照 current race 与 canonical runs | ✓ current register-before-publish 在 `runtime.py:1245-1275`；broker resolve 已原子 pop（`broker.py:169-192`）；canonical 要求 cancel 仅清该 run（`docs/specs/kernel/runs.md:173-202`）。设计 D4/D5 收拢而未放宽。 |
| 约束 4：permission heartbeat 只覆盖已发布且真实等待 | 查 current ticker 与 design 顺序 | ✓ current ticker 在 publish 后创建、finally 停止（`runtime.py:1277-1300,1400-1407`）；D6 把“published 且 WAITING”写成显式门槛。 |
| 可复用 1：深化现有 broker，不加同层 coordinator | 做删除测试 | ✓ broker 已拥有 pending、cancel 与 policy state（`broker.py:102-319`）；再加 coordinator 会重建第二个 settle owner。D1 的删除测试成立。 |
| 可复用 2：复用 `HookContext.permission_requester` | 查 core 最窄端口及缺省语义 | ✓ `HookContext` 已持 requester 并在缺省时 deny（`src/agent/core/hooks/context.py:142-166,243-270`），D2 没有新造平行 hook seam。 |
| 可复用 3：复用 pollable raw reader 与 `_InputState` | 查现有纯状态和 fd reader | ✓ `_InputState` 是纯值（`src/coding_cli/input/repl_input.py:47-65`），fd reader 已用 select/os.read（`:179-233`），可作为新 owner 的底座。 |
| 删除项：engine closure/private access/metadata broker 应消失 | 查现有依赖点是否枚举完整 | ✓ transaction closure/private pop 位于 `runtime.py:1232-1434`；auto gate 从 metadata 取 broker（`auto_mode_gate.py:758-765`）；D2/D3 分别给出替代入口，删除闭合。 |
| 历史 1：旧修补持续堆在同一 closure | 查代码中的真实历史锚 | ✓ closure 内 `feat-394-M14`、`bugfix-417-M3` 的竞态/liveness 修补密集共存（`runtime.py:1277-1428`），支持深化模块而非按文件长度拆分。 |
| 历史 2：session/run 生命周期已有 RunsRegistry owner | 查现有 registry/executor | ✓ RunsRegistry 已拥有 admission、active identity、carrier cancel 与 terminal settlement（`src/agent/core/runs/registry.py:108-248,263-323,409-589`）；本 unit 只深化 permission 子事务。 |
| 历史 3：既有用户行为已有 canonical，新增行为才写 delta | 对照三份 canonical/delta | ✓ permission/cancel/close 已在 `docs/specs/kernel/runs.md:126-251`，非 TTY 已在 `docs/specs/cli/spec.md:148-156`；design 正确采用 MODIFIED 而非平行 ADDED。 |
| CC 对照 1：CC 把 permission queue/race/abort 集中在一个 owner | 查本地 CC 源码而非只信 design | ✓ `useCanUseTool` 创建一次 permission context 并统一检查 abort（`~/Repos/opensource-hub/claude-code/src/hooks/useCanUseTool.tsx:54-113,177-282`）；interactive handler 用 resolve-once/claim 清 queue 与 remote listener（`src/hooks/toolPermission/handlers/interactiveHandler.ts:138-177,230-260,400-456`）。 |
| CC 对照 2：不能照搬其同-runtime AbortSignal | 对照 Nano loop/thread 拓扑 | ✓ CC 的 `AbortSignal` 与 UI queue 同 JS runtime；Nano 的 executor loop 与 CLI loop/thread 分离已有上述代码证据，D4/D7/D8 使用 concurrent future + thread-safe dispatch 是必要差异。 |
| 决策 1：深化 `PermissionBroker` | 四问 + 删除测试 | ✓ owner、接口、settle/cleanup 边界均拍死；删除后复杂度会散回 runtime/SDK，且没有同层第二 owner。 |
| 决策 2：core 只依赖 requester factory | 查依赖方向与调用闭合 | ✓ engine 提供 session/run/publisher，platform composition 绑定 broker/local adapter；缺省沿用 HookContext fail-closed，接口来源与出口闭合。 |
| 决策 3：policy state 只注入 canonical trusted builtin | 查 loader 的 source/path 能力与覆盖风险 | ✓ loader 已掌握 resolved builtin root、source、module/file identity（`src/agent/platform/hooks/loader.py:99-145`）；同时要求 source + canonical path 可防同名 workspace hook 拿到依赖；per-registry 注入避免 module global。 |
| 决策 4：先 record，再启动 sibling supervisor | 攻 register/cancel 线性化与跨 loop primitive | ✓ 第一次 cancelable await 前登记 record/task；CAS 同时移除 lookup/run index并发 terminal signal；carrier 只 shield thread-safe result。local task 的 SDK registry 与 broker record 职责不重叠。 |
| 决策 5：carrier cancel 与 transaction cleanup 解耦；统一 shutdown controller | 查 cancel 顺序、per-Kernel ownership、重复关闭语义 | ✗ sibling supervisor/CAS 和 permission-before-loop-stop 顺序本身成立；但 D5 把结果扩成“每个 Kernel 独立使用”而忽略全局 model registry，且 D5 `:198-201` 的“同一 future 广播错误”与 runs delta `:89-91` 的“后续调用安全返回”没有统一失败重放语义。 |
| 决策 6：publish/interaction/resolved 唯一顺序 | 逐行走异常表与真实 fail-closed chain | ✓ request publish 只有正常返回才算交付；失败完成 record exception，`_handle_ask` catch 后返回 block（`auto_mode_gate.py:696-700`），ToolRegistry 因 block 不执行（`registry.py:222-241`）；heartbeat/local/resolved 的启动条件和最终回收均拍死。 |
| 决策 7：新增 optional SDK port，保留 callback | 查兼容、ownership、互斥与 loop neutrality | ✓ 三参数 alias/raw request identity保留；新类型 SDK-owned；legacy/new 互斥且在建 task 前拒绝；remote-only 无迁移。consumer 不承担 exited ack，边界足够窄。 |
| 决策 8：CLI main loop 是唯一 terminal mode owner | 用真实 pipe read-ahead 反例攻击 epoch 方案 | ✗ 单 reader/loop bridge方向正确，但“physical read 完成后统一打当前 epoch，再按换行 decode”（design `:313-326`）没有定义同一次 `os.read` 含多行或 pump 提前排队多行时的 mode 路由。`prompt\n1\nnext\n/exit\n` 一次写入 pipe 时，后续合法行会被旧 epoch 丢弃或错送 permission，违反 motivation/delta 的完整行顺序。 |
| 决策 9：CLI 先关 Kernel，再关 terminal owner | 查依赖方向与异常 cleanup | ✓ owner 必须活到 Kernel 发出 local abort；嵌套 finally 保证两次 cleanup 都跑，Kernel 不反向拥有产品 terminal。主体/cleanup 错误优先级也已写明。 |
| motivation Q1：中途不逐项等待用户确认 | 查 design 是否留 TBD/二选一 | ✓ 9 个决策均已拍板，无 TBD 或待用户选择。 |
| motivation Q2：不按文件行数拆分 | 查目标与模块删除测试 | ✓ 方案围绕 transaction invariant/owner，而非把 190 行机械移文件；D1/D2 有真实调用链与删除测试。 |
| 目标：完整 transaction 由深模块执行，carrier 被杀后仍清理 | 映射到 D1/D4/D5/D6 | ✓ broker record + sibling supervisor + CAS + bounded local exit 直接覆盖目标。 |
| 非目标：不改策略、文案、协议帧、默认交互 | 查 delta 与产品 adapter | ✓ PermissionDecision/Request/Response 与事件名不改；Gateway 仍 remote-only，legacy callback 长期保留；没有 IM/Gateway schema delta。 |
| SDK 兼容：optional SDK-owned port；旧三参数 callback/raw identity不变 | 映射到 D7 与 sdk delta | ✓ D7、sdk delta `:17-30,66-80,103-127` 和 runs delta `:21-50` 三处一致。 |
| publisher 同步失败必须 fail closed | 映射到 D6、异常 oracle、delta | ✓ D6 明确原异常→auto gate block、无 request/resolved/heartbeat/local、无 pending，并要求真实 ToolRegistry 链测试；runs delta `:58-62` 可观察。 |
| CLI 非 TTY 完整行、有序、正常退出、无 ANSI | 用一次 pipe write 跨 mode 检查设计覆盖 | ✗ CLI delta本身忠实，但 D8 缺 read-ahead/backpressure 规则，无法证明 permission mode 切换下仍逐行；现有 `input()` 恰好一次只取一行（`repl_input.py:76-103,852-866`），新 continuous pump 不能默认等价。 |
| Scenario：CLI 本地 allow/deny 行为不变 | 对照 D7/D8/D9 | ✗ 决策覆盖显示与决定，但上述 pipe 多行反例可令 non-TTY allow/deny 永远收不到或吞掉后续输入，尚不能满足 `motivation.md:50-54`。 |
| Scenario：Web IM allow/deny 只消费一次 | 对照 D4/D5/D6 与 production handler | ✓ external response 进入同一 CAS，late response=False；Gateway handler 仍只调用 Kernel（`src/personal_assistant/ws/im_connection.py:167-188`）。 |
| Scenario：pending 时 cancel/interrupt 释放等待且不污染下一 run | 对照 D4/D5 barrier matrix | ✓ carrier cancel 同步 CAS、supervisor独立清理、exact run cancel、late result false，并要求 register/publish/heartbeat/local 五个 barrier 无 sleep 测试。 |
| Scenario：request 无法交付时 deny、无 pending/伪 resolved | 对照 D6 真链 oracle | ✓ 如上，异常不会落入 HookRunner fail-open；事件 trace 与最终状态都明确。 |
| 影响范围与回滚：原子切换，不留双 owner/双 pending | 查 M1 与 rollback | ✓ 单 M1 覆盖 core/platform/SDK/CLI/Gateway adapter/tests/deltas；回退整 unit，旧 callback不是临时 façade。 |
| delta sdk-boundary：公开面新增两项 | 与 canonical 第一 Requirement 逐 Scenario 对账 | ✓ canonical 原 7 个 Scenario 全保留（canonical `:14-54`；delta `:9-64`），新 owner/export/raw identity均为 SDK 消费者可观察，MODIFIED 用法正确。 |
| delta sdk-boundary：两层装配新增 port 与 Kernel 隔离 | 与 canonical 第二 Requirement 对账并核 live state | ✗ 原 4 个 Scenario 保留且 port条款正确；但 delta `:89-98,174-178` 把“进程级共享基座”改成“每个 Kernel 可独立使用/关闭”，与 live global model registry 冲突，形成无法由本 M1 当前范围兑现的长期契约。 |
| delta runs：唯一权限交互路径 | 与 canonical permission Requirement 对账 | ✓ 原 callback/interrupt 两个 Scenario 均保留；new port、互斥、remote-only、first-wins、publisher failure 是真实 SDK consumer 结果，MODIFIED 标记正确。 |
| delta runs：Kernel close | 与 canonical close Requirement 对账 | ✗ 原 4 个 Scenario 和 K1/K2 新 Scenario 均保留；但重复关闭的“后续安全返回”（delta `:89-91`）与 D5 的 shared future error replay未统一，且 multi-Kernel只应承诺本 unit真正拥有的 shutdown/permission graph。 |
| delta CLI：非 TTY Requirement | 与 canonical逐字/行为对账 | ✓ MODIFIED 完整保留唯一 Scenario，去掉 `input()` 实现绑定，THEN 仍只写消费者可观察行为；问题在 D8 尚不能实现它，而非 delta 写法。 |
| im/gateway：no spec delta | 查协议与产品行为是否改变 | ✓ request/resolved frame和 Gateway decision入口均保留，无新增用户可观察协议，no delta 合理。 |
| M1：单一原子 milestone、空 skeleton | 查横切/并行/两轨退出 | ✗ 单 M1 是正确结构，空目录也符合 skill；`[reviewer]`/`[worker]` 两轨齐全且 barrier/异常/真实双 loop测试具体。但它继承两个 CRITICAL，且 Runbook没有可执行的无 proxy 权限触发方式，当前还不能安全派发。 |
| Runbook for Reviewer | 按表中命令和 fallback 走可执行性检查 | ✗ 起停/健康检查命令可执行，既有真栈 approve/deny 测试也存在（`tests/e2e/critical_paths/test_permission_approval_critical_path.py:93-200`）；但 Runbook未给该测试的精确命令，且声称 `scripts/fixtures/` 可在无上游时验证权限链，实际唯一 happy fixture只返回 ACK 文本、从不生成 tool_use（`scripts/fixtures/anthropic_sse_ok_recording.py:29-76,98-103`），无法触发 permission。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | D1-D5：broker、core requester、SDK task registry、shutdown controller | ✗ permission transaction 放 broker、core只留端口、SDK管理consumer task，分层自然；但 sdk delta把这种**局部 per-Kernel ownership**泛化成整个 Kernel 独立，而 model routing仍依赖 module singleton。长期会出现“K2 build 改写 K1 submit”的契约违约，且同配置隔离测试会给出假绿。 |
| 该不该存在 | `PermissionRequesterFactory`、`BuiltinHookDependencies`、`LocalPermissionTaskRegistry`、`KernelShutdownController`、`CliTerminalInputOwner` | ✓ 逐一删除测试走完无存活发现：factory维持 core/platform倒置；trusted deps 防 service locator；task registry保存非合作 consumer task；controller统一 sync/async close；terminal owner消除双 stdin reader。它们不是只搬代码的平行 facade。 |
| 深还是浅 | broker transaction API 与 CLI input owner | ✗ broker 的 request/resolve/cancel 接口能隐藏 register/race/cleanup，足够深；CLI owner 的 epoch接口却没有隐藏最难的 modal read-ahead规则，worker仍须猜“旧 epoch但尚未消费的完整行”该丢、保留还是重标，最终会产出互不兼容实现。 |
| 治本还是补丁 | 私有 broker pop、carrier cleanup、cross-loop stdin | ✓ 去掉 engine 私有访问、用 sibling supervisor承接 cleanup、把物理 stdin收为单 owner，均正面修所有权根因；除上述过宽 isolation契约和输入路由缺口外，没有发现为旧双 owner叠补丁。 |

## Issues

- [CRITICAL] **[现状断言 5 / 决策 5 / sdk-boundary delta] 新增的“每次
  `build_kernel()` 均可独立使用”契约与真实 module-global model registry 冲突。**
  `_REGISTRY` 是进程 singleton（`src/agent/core/llm/model_registry.py:36-48`），每次
  build 都 reset/re-init（`src/agent/sdk/kernel.py:305-359`），K1 的运行时随后仍调用全局
  `provider_of()`（`src/agent/core/agent/runtime.py:1455-1469`）。现场探针已证明：
  init K1=`p1/m1` 后再 init K2=`p2/m2`，K1 的 `provider_of("m1")` 变为
  `ValueError: no registered provider for model: m1`。不改时，worker可用相同 catalog 写出
  “K1/K2 isolation”假绿测试，归并后的 canonical却对外承诺实际不存在的独立使用。作者必须二选一：
  将 design/delta 精确收窄为“关闭 K1 不影响 K2 的 run/permission/local-task/executor/finalizer
  资源图”，保留进程级模型基座事实；或把 model catalog/routing 也纳入 per-Kernel迁移，并用
  不同 catalog 的 K1/K2 submit测试证明它（后者会明显扩大本 unit范围）。

- [CRITICAL] **[决策 8 / CLI Scenario / CLI delta] epoch 方案未定义 read-ahead，
  不能守住 non-TTY 完整行顺序。** design `:313-326` 在每次 physical read 后读取一次当前
  epoch，再交给 decode层；pipe 的一次 `os.read(4096)` 可以同时得到
  `prompt\n1\nnext\n/exit\n`，continuous pump也可能在 normal→permission切换前已排队多行。
  按当前规则，这些合法后续行会带旧 epoch而被丢弃，或在错误 mode中消费，导致 permission
  永久等待/下一命令丢失。作者需在 design层拍死 modal flow control：例如一次只允许一个
  mode-specific logical-read demand，或只缓存 raw bytes并在 main-loop按当前 demand分配下一完整行；
  permission必须只消费一行，余下完整行保持 FIFO给恢复后的 normal mode。退出标准必须增加
  “所有行一次写入同一个 pipe chunk、无 sleep”的 allow/deny/cancel→next-line测试，不能只测
  分时喂行。

- [WARNING] **[决策 5 / runs delta「重复关闭」] 首次 close 失败后的重入语义有两套答案。**
  D5 `:198-201` 说 concurrent/mixed caller等待同一 future并广播错误/结果；delta
  `:89-91` 又说后续调用“安全返回、不抛 secondary exception”。前者可让每个 waiter重抛同一
  primary close error，后者也可被实现成首 caller抛、后续吞错返回。不澄清会导致 controller、
  contract test和CLI cleanup错误优先级三处各选一种。请明确“同一失败是否向所有已等待/后到
  caller重放”；若重放，delta应写“可重放同一 primary failure，但不产生新的 secondary
  failure”，若不重放，D5不能写 error broadcast。

- [WARNING] **[Runbook for Reviewer] 无 live proxy fallback 当前不可执行。**
  Runbook `:456-458` 声称 ready-made HTTP桩能验证权限链，但现有 happy fixture只返回文本
  ACK，不会发 tool_use；error fixtures更不会进入权限。现有真栈 approve/deny测试还受
  `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1` + `:4000/health`门控
  （`tests/e2e/critical_paths/conftest.py:31-52`）。请给出精确 pytest/CLI命令和确定性
  tool-use触发方式；若要保留无 proxy fallback，就指定一个真实会产生危险 `write` tool_use的
  fixture及接线命令，否则诚实写明 live proxy是硬前置。

## Recommendations

- 保留单 M1；这次问题是两个边界尚未拍死，不是 milestone 需要拆分。
- 修订时继续保留 D6 的真实
  `ToolRegistry → HookRunner → auto_mode_gate → requester` fail-closed测试要求；现有 focused
  broker测试无法替代这条链。

## 本次核验执行

- `.venv/bin/pytest -q tests/unit/test_permission_broker.py tests/unit/test_permission_requester_cancel.py tests/unit/test_permission_decision_loop.py tests/unit/test_cli_async_repl_sdk.py tests/contract/test_agent_sdk_surface_guard.py`
  → **60 passed**（1 条第三方 protobuf deprecation warning）。
- 额外运行无文件写入的双 catalog model-registry探针，结果为：
  `after K1: p1`；构造 K2 后 K1 lookup 变为
  `ValueError: no registered provider for model: m1`；K2 lookup 为 `p2`。
- 未运行产品旅程；本阶段按 `change-design-reviewer` 只审设计与验收可执行性。

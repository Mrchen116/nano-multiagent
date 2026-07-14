# Design 评审: refactor-461

**结论**: Approved

本轮是作者修订后的 fresh re-review，不沿用上一轮勾选结果。重新从 production entrypoint 追了 `main → run_gateway → build_runtime`、默认后台 start/stop/restart、config load/save、state read/write、e2e/acceptance/fixture 活跃入口，并重新对照 canonical gateway/kernel 契约。上一轮的 1 个 CRITICAL 与 3 个 WARNING 已全部实质消除；没有存活的 CRITICAL/WARNING。

## 核实台账

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状：生产入口只构建进程内 Kernel | 从 `main()` 正向追 foreground/background child 的共同入口 | ✓ default start 生成带 `--foreground` 的 child argv（`src/personal_assistant/main.py:4224-4237`）；foreground 进入 `run_gateway`（`src/personal_assistant/main.py:3593-3677`），再由默认 `build_runtime` 经 `agent.sdk` / `build_pa_kernel` 构造进程内 Kernel（`src/personal_assistant/main.py:2401-2435,2887-2911,2938-2950`）。 |
| 现状：`GatewayProcessManager` 是生产死分支 | 全仓查构造点，并从 composition root 反向核实 | ✓ 类仍定义于 `src/personal_assistant/main.py:1278-1366`，但 `GatewayProcessManager(` 的构造只在 `tests/unit/personal_assistant/test_gateway_process_manager.py:74,97,115`；production `build_runtime` 固定给 `GatewayRuntime` 传 `None`（`src/personal_assistant/main.py:3578-3588`）。 |
| 现状：死 manager 仍扩大 `GatewayRuntime` interface | 追构造签名与启动/关闭分支 | ✓ runtime 仍接 `process_manager`、保存成员，并在 startup/shutdown 条件调用 manager（`src/personal_assistant/main.py:1859-1897,1961-1963,2052-2053`）；D1 的删除对象正是这条假架构。 |
| 现状：`KernelConfig` 混合死连接字段与三项活 Gateway timing | 追 parser/save 与所有 runtime 消费者 | ✓ connection/token/command/health 字段只在 legacy parser/save 和死 manager 中存活（`src/personal_assistant/config/local_store.py:276-304,605-626,974-1026`; `src/personal_assistant/main.py:1295-1362`）；三项 timing 仍控制 background startup/cleanup、stop 宽限和轮询（`src/personal_assistant/main.py:2484-2492,2550-2600,4252-4272`）。 |
| 现状：`health_url` 已不是 Gateway/Kernel health 事实 | 追 launch result → state → stop probe | ✓ launch 写入 IM URL 或 `pid=...`（`src/personal_assistant/main.py:2499-2508`），state 却以 `health_url` 持久化（`src/personal_assistant/main.py:4138-4158`），stop 再按 `{"healthy": true}` HTTP 协议探测（`src/personal_assistant/main.py:2560-2616,2779-2787`）。D3 删除字段和 probe 是直接治本。 |
| 现状：parent 当前只有 PID/start confirmation，没有 runtime readiness | 对比 PID write、parent waiter、child ready event | ✓ child 在调用 `runtime.run_forever()` 前写 `gateway.pid`（`src/personal_assistant/main.py:2432-2435`）；parent 只等 PID file 且检查 child 未退出（`src/personal_assistant/main.py:4252-4272`）；真正 `_ready_event` 在 child 内部 channel/skill maintenance 后才 set（`src/personal_assistant/main.py:1914-1922,1944-1985`）。修订后的现状分析与 D3 均准确陈述这三个事实（`design.md:32-36,155-169`）。 |
| 现状：`_KernelClientShim` 是生产活 adapter | 从 `build_runtime` 追真实注入点 | ✓ shim 被注入 heartbeat scheduler、cron runner、internal dispatch，并绑定 live agent map（`src/personal_assistant/main.py:2943-2950,2984-2990,3281-3342,3544-3573`）；D1/M1 明确保留。 |
| 现状：Gateway background supervisor / process group 是另一条活边界 | 追默认 start、失败回收、stop/restart | ✓ child 由 `BackgroundProcessFactory`/`Popen(start_new_session=True)` 启动（`src/personal_assistant/main.py:2441-2486,4240-4249`）；启动失败和 operator stop 都保留 SIGTERM/SIGKILL + process-group cleanup（`src/personal_assistant/main.py:2488-2498,2513-2603,4276-4307`）。D1 没有误删。 |
| 现状：`ProcessFactory`/`_spawn_process` 与 `BackgroundProcessFactory` 不是同一 seam | 分别查引用 | ✓ 前者只服务死 manager（`src/personal_assistant/main.py:115-117,1295-1307,4368-4372`），后者服务真实 background launcher（`src/personal_assistant/main.py:2441-2486,4240-4249`）；D1 的 delete/keep list 精确。 |
| 现状：进程内 Kernel `aclose()` 是真实 shutdown 资源 | 追 runtime finally | ✓ runtime 显式持有 kernel 并 await `aclose()`（`src/personal_assistant/main.py:1907-1910,2023-2029`），不是 dead subprocess seam。D1/D4 保留。 |
| 现状：当前成功关闭顺序与异常策略 | 逐行追 finally 和 `stop_channels` | ✓ 真实顺序是 dispatch cleanup → heartbeat close → `stop_channels` → kernel `aclose` → cron drain → IM close/task await → resource closers（`src/personal_assistant/main.py:2007-2057`）；dispatch/kernel/cron/IM 有各自 catch，heartbeat/channels 没有，`stop_channels` 直接调 adapter（`src/personal_assistant/gateway/bootstrap.py:90-97`）。修订后的 D4 图和正文逐项一致，且只删除 manager 两处调用（`design.md:171-208`）。 |
| 现状：config 普通 timestamp backup 只覆盖默认路径 | 追 backup gate 和 save 顺序 | ✓ `_backup_existing_config` 对非默认 config 直接返回（`src/personal_assistant/config/local_store.py:467-486`），且 backup 在覆盖前执行（`src/personal_assistant/config/local_store.py:680-688`）。D2 没再扩义它，而是为破坏性 schema migration 单独设计 per-file backup（`design.md:146-153`）。 |
| 现状：active 运维叙事完整枚举 | 对 current `AGENTS.md`/`scripts`/`tests` 定向搜索，排除 archive/change history/负向 guard | ✓ 需要清理的 current 落点为 `AGENTS.md:183-287`、`scripts/e2e-up.sh:1-23`、`scripts/e2e-down.sh:56-67`、`tests/e2e/conftest.py:1-36`、`scripts/acceptance/m170_runtime.py:56-80,131-146,172-190,322-324,465-513`、三个 tracked YAML 顶层 `kernel:`、`scripts/fixtures/README.md:20-35,57-59`、`scripts/fixtures/anthropic_sse_error.py:20-28` 与 `tests/integration/test_provider_error_user_visible.py:1-9`；D5、工具表、M1 范围和 guard 明示全部覆盖（`design.md:210-253,307-320`）。 |
| 现状：tracked sample config 清单 | 枚举非 archive YAML 顶层 `kernel:` | ✓ 只有 `node-config.yaml:14`、`ACCEPTANCE/M171-node-config.yaml:14`、`ACCEPTANCE/M224-runtime-node-config.yaml:13`；设计清单无漏项、无扩大到用户未跟踪 config（`design.md:220-228,253,309`）。 |
| 既有架构约束：Kernel 是进程内库、无内建 HTTP API | 核 `SPEC.md` 与 kernel canonical | ✓ `SPEC.md:12-15,89-91,123-128,138-144` 和 `docs/specs/kernel/sdk-boundary.md:56-75` 明确无子进程/loopback HTTP；D1-D5 与依赖方向一致。 |
| 澄清：只治理 refactor-387 后的 dead kernel subprocess seam，需防走偏 | 对齐用户原话、目标和 non-goals | ✓ motivation 保存原话并锁定 production-wiring 证据（`motivation.md:13-22`）；M1 明确不新增 readiness IPC、不改 shutdown 策略、不碰 session aggregate/coding CLI/history（`design.md:324-333`）。 |
| 目标：删除 runtime/config/state/test/active narrative 四面的假 seam | 映射 D1-D5 | ✓ D1 删除 runtime branch，D2 迁移活 timing 并移除死 schema，D3 删除 health state/probe，D5 清理 active scripts/docs/tests；不是只删类名（`design.md:114-169,210-253`）。 |
| 非目标：保留 supervisor/process group/shim/in-process close | 映射 keep list与 production evidence | ✓ 可复用能力、风险表、M1 exit/non-goals 三处一致（`design.md:38-50,279-287,317-333`），无误删空间。 |
| spec Req：普通消息仍正常回复 | 找设计与 reviewer 验收落点 | ✓ 部署图保留 channel → Gateway → SDK Kernel，M1 reviewer 轨要求真实消息旅程（`design.md:93-110,295-301,311-314`），覆盖 `motivation.md:47-52`。 |
| spec Req：heartbeat/cron 不受清理影响 | 核 shim/cron wiring、keep list和旅程 | ✓ D1 保留 shim，D4 保留 shutdown order，M1 要求主动任务和 wiring 均存活（`design.md:114-120,171-208,313,320-321`），覆盖 `motivation.md:54-57`。 |
| spec Req：默认启动确认 | 核数据源、输出和非承诺 | ✓ D3 删除 `BackgroundLaunchResult.health_url` 且不新增 `readiness_hint`，只保留 pid/log/im_service_url；waiter 改成 PID/start 语义，不新增 IPC（`design.md:155-169`）。这与真实 parent 数据流及 `motivation.md:59-64` 一致。 |
| spec Req：stop/restart 保持现有结果 | 映射 D3/D4/M1 | ✓ stop 只去掉错误 HTTP probe，继续用 PID/process group/timeout；runtime 只删 manager 调用，其余顺序原样（`design.md:155-208,314,316,320`），覆盖 `motivation.md:66-69`。 |
| spec Req：IM 离线本地自治 | 映射部署拓扑与 reviewer 轨 | ✓ 外部 channel 仍直接进入 Gateway 进程内 Kernel，IM 仍是可选连接；M1 要求 offline journey（`design.md:93-110,313`），覆盖 `motivation.md:71-74`。 |
| spec Req：旧三项 timing 继续生效 | 核字段真实消费者与 D2 mapping | ✓ D2 按字段把 old `kernel.*` 映射到 `gateway.*` 并保持默认（`design.md:122-146`），测试与 reviewer 轨覆盖（`design.md:257-260,315,318`）。 |
| spec Req：新 `gateway:` 逐字段优先 | 核决策是否拍死 | ✓ 三字段首选/兼容来源逐项列出，明确只在新字段缺失时 fallback（`design.md:136-146`），两个 worker 不会产生整块覆盖歧义。 |
| spec Req：canonical save 前备份、失败不覆盖 | 核 backup 触发、命名、冲突、失败与生命周期 | ✓ 仅当磁盘原文仍有顶层 legacy `kernel:` 且新文裁掉它时触发；固定同目录名、原始字节/权限、排他创建、同内容复用、不同内容阻断、写/落盘失败不覆盖、迁移后不重复触发均已拍死（`design.md:146-153`）。motivation、delta、runbook、M1 测试/退出标准一致（`motivation.md:88-92,114-120`; delta `specs/gateway/service-lifecycle.md:42-67`; `design.md:259,282,291,299,315,318`）。 |
| spec Req：旧 connection/HTTP 字段不验证、不生效 | 映射 D1/D2 | ✓ D2 只兼容读取三 timing，其他字段不进入 runtime structure；D1 删除唯一 command/health consumer（`design.md:114-146`），覆盖 `motivation.md:94-97`。 |
| spec Req：e2e 只管理 IM/Gateway | 核脚本与 M1 | ✓ D5 删除 `.api.pid`/Kernel app 叙事，runbook 验证无第三进程，M1 reviewer/worker 两轨均覆盖（`design.md:210-230,295-301,314,319`），覆盖 `motivation.md:99-103`。 |
| 迁移策略：loader 是唯一 legacy 读取边界 | 删除测试与数据流检查 | ✓ `GatewayLifecycleConfig` 是 canonical runtime shape，legacy `kernel:` 不形成第二 runtime object；backup 也只保护磁盘原文，不参与运行或 dispatch（`design.md:122-153`）。 |
| 迁移策略：旧 state forward read | 核 D3/state tests | ✓ 新 state 只保存 pid/config/log，reader 忽略旧额外 `health_url`，stop 不探测它（`design.md:155-165,260,316,318`）；数据来源/出口闭合。 |
| 回滚：任意 config 可恢复 | 核默认/custom/worktree 三类与失败路径 | ✓ migration backup 不复用默认-only gate，任意现存 config 都受保护；回滚先原样恢复 sidecar 再回退 milestone（`design.md:148-153,279-291`）。这比永久双读/兼容 manager 更小，不形成 runtime seam。 |
| 决策 D1：删 manager，不建替代 port | 四问：拍死、歧义、自洽、驱动 | ✓ delete/keep 符号明确；生产只有一种 Kernel ownership，新增 port 无 spec 驱动；与 SDK canonical 一致（`design.md:114-120`）。 |
| 决策 D2：Gateway timing + per-file migration backup | 四问 | ✓ ownership、字段映射、默认、save、backup 条件和冲突策略均拍死；backup 是 destructive save 的回滚保障，不向 runtime 暴露新模式（`design.md:122-153`）。 |
| 决策 D3：删除 health/readiness 字段 | 四问 | ✓ launch result/state/stop/print/waiter 五处闭合；明确 no readiness field/no IPC，解决上一轮关键矛盾（`design.md:155-169`）。 |
| 决策 D4：只删 manager 调用，保持真实 shutdown | 四问 | ✓ 图、正文、live code、M1 exit/non-goal 现在一致；不再夹带异常聚合或顺序重排（`design.md:171-208,320,329`）。 |
| 决策 D5：清 active、不改 history | 四问 | ✓ current allowlist 与排除面明确；guard 覆盖新增发现的 fixture/test 入口，不扫 archive/change history/负向 contract（`design.md:210-230`）。 |
| delta MODIFIED：锚 canonical 启停 Requirement | 对比标题、正文、所有 Scenario | ✓ 标题与原 5 个 Scenario 全保留，只把旧“健康提示”精确改为 PID/liveness 启动确认并声明 no readiness（canonical `docs/specs/gateway/service-lifecycle.md:14-42`; delta `specs/gateway/service-lifecycle.md:5-38`）；MODIFIED 用法正确。 |
| delta MODIFIED Scenario：默认后台启动 | 核消费者可观察性与可实现性 | ✓ THEN 只依赖真实 PID file/child liveness、pid/log/IM status，明确不承诺 runtime/channel ready，也无内部函数名（delta `specs/gateway/service-lifecycle.md:14-18`; D3 `design.md:155-169`）。 |
| delta MODIFIED Scenario：重复启动 | 对比 canonical/PID lock | ✓ 原 Scenario 忠实保留；production PID lock 在 `src/personal_assistant/main.py:2469-2478`。 |
| delta MODIFIED Scenario：stop 清状态 | 对比 canonical/D3 | ✓ 原 Scenario 忠实保留，D3 仍提供 graceful/forced/PID-state cleanup（delta `specs/gateway/service-lifecycle.md:25-28`; `design.md:155-165`）。 |
| delta MODIFIED Scenario：活动 run 收拢 | 对比 canonical/D4 | ✓ 未静默删除；in-process `kernel.aclose()` 和既有顺序明确保留（delta `specs/gateway/service-lifecycle.md:30-34`; `design.md:171-208`）。 |
| delta MODIFIED Scenario：真实首因 | 对比 canonical/non-goal | ✓ 原 Scenario 原样保留（delta `specs/gateway/service-lifecycle.md:36-38`）；D4 明确本 unit 不改变现有异常策略，不会因清 seam 制造回归。 |
| delta ADDED：Gateway timing ownership | 核是否真新增、target 是否最窄 | ✓ canonical 尚无该 operator config contract；service-lifecycle 是最窄 target，ADDED 合理（delta `specs/gateway/service-lifecycle.md:40-44`）。 |
| delta ADDED Scenario：旧 timing | 映射 D2 | ✓ 三字段与“不启动/连接独立 Kernel”完整（delta `specs/gateway/service-lifecycle.md:46-51`; `design.md:136-146`）。 |
| delta ADDED Scenario：新值逐字段优先 | 映射 D2 | ✓ 部分字段新、部分字段旧的行为已明确（delta `specs/gateway/service-lifecycle.md:53-58`）。 |
| delta ADDED Scenario：canonical save + backup | 核可观察 THEN 与 failure path | ✓ backup 内容、位置、不可覆盖、canonical gateway write、legacy remove、backup failure no overwrite 都有设计落点（delta `specs/gateway/service-lifecycle.md:60-67`; `design.md:146-153`）。 |
| delta ADDED Scenario：旧 connection/HTTP 失效 | 映射 D1/D2 | ✓ 无 endpoint dependency、无内部实现断言（delta `specs/gateway/service-lifecycle.md:69-74`）。 |
| delta 覆盖：Kernel/IM/CLI 无 delta | 核是否遗漏对外变化 | ✓ Kernel 无网络 API 已 canonical；IM 协议与 CLI 不改，design 明示 no delta（`design.md:267-276`; `SPEC.md:89-91`）。 |
| M1：单 milestone 是否合理 | 核垂直/横切、拆分理由、范围交集 | ✓ runtime/schema/state/docs/tests 任一单独落地都会留下假 seam 或破坏 config；单 M1 有明确原子性举证，无并行范围交集（`design.md:303-309`）。 |
| M1：两轨退出与 runbook | 逐条核 reviewer/worker 标识和可验命令 | ✓ 消息、主动任务、offline、operator CLI、config migration/backup、state compatibility、符号删除、active residue、shutdown order、全量 checks 均有两轨；runbook 明确 start 不是 readiness，并先用隔离 config 验 migration（`design.md:293-322`）。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | `GatewayLifecycleConfig` 与三 timing | ✓ timing 的真实消费者是 Gateway launcher/stop，把 canonical ownership 放 `personal_assistant.config` 的 `gateway:` 下符合依赖方向；没有把 Gateway 配置下沉内核。 |
| 归属 | D4 shutdown | ✓ 只删除 manager 两处调用，其余顺序/异常策略归既有 `GatewayRuntime`；没有借 dead-seam unit 重写常驻服务关闭语义。 |
| 该不该存在 | `BackgroundLaunchResult` health/readiness 替代字段 | ✓ 删除测试通过：D3 直接删除 `health_url`，不建 `readiness_hint`；pid/log/im_service_url 已覆盖真实 operator 信息，复杂度确实消失。 |
| 该不该存在 | `GatewayLifecycleConfig` | ✓ 三字段共享 owner、默认、legacy migration 和 save 规则，并被 start/stop 多路径消费；aggregate 隐藏的复杂度明显大于三字段 interface，不是空 wrapper。 |
| 该不该存在 | `<config>.pre-refactor-461.bak` | ✓ 删除它会让非默认 `--config` 在 incidental canonical save 后无法无损回滚三项 timing；永久双读/保留 `KernelConfig` 会继续维持目标 seam。一次性 sidecar 只在 destructive migration 边界出现、不进 runtime，代价与风险相称。 |
| 深还是浅 | migration backup helper | ✓ 触发条件、幂等复用、冲突阻断、失败原文件不变和迁移后不再触发形成一个窄接口，隐藏了 default/custom/worktree 三类路径差异；没有把旧 schema 包成 runtime adapter。 |
| 深还是浅 | D1 manager/config/state 收敛 | ✓ 调用者不再选择 Kernel 进程模式、不再理解 command/health/state protocol；复杂度被删除而非搬到新 port。 |
| 深还是浅 | zero-residue guard | ✓ guard 用 current allowlist覆盖真实 operational surfaces，并排除 history/negative guards；不会以全仓字符串扫描替代架构边界。 |
| 治本还是补丁 | dead subprocess seam | ✓ runtime constructor/branches、schema、state/probe、test double 与活跃运维叙事同时收口，根因“无生产构造点却被 interface/test 维持”被移除。 |
| 治本还是补丁 | readiness | ✓ 不再重命名假 health；明确只承诺 PID/start confirmation，真实 readiness 留在 child 内部且不新增 IPC，避免用新补丁替代旧补丁。 |

## Issues

无。

## Recommendations

- migration backup 会复制可能含 token/password/app secret 的 config。design 已要求保存原权限（`design.md:150`）；实现时建议把“新 backup 权限不得在任何时刻宽于源文件、复用已有 backup 时同时校验权限”纳入 `test_local_store.py`，避免先以宽权限创建、再 chmod 的短暂泄露窗口。该建议不改变已拍板架构。
- 删除 `KernelConfig` 时，顺手由 zero-residue/单测清掉仅服务 legacy parser 的 `_DEFAULT_KERNEL_*`、`DEFAULT_LOCAL_KERNEL_TOKEN`、`resolve_kernel_token()`、`_derive_kernel_base_url()` 及对应旧测试；这是 D2 的机械闭包，不需要新增决策或扩大 milestone。

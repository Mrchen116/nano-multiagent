# refactor-461: 删除死 kernel subprocess seam

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-387

## 原始诉求

> 删除死 kernel subprocess seam

## 澄清记录

- Q1: 本 unit 是否只清理 refactor-387 后已经退出生产路径的 kernel 子进程残留，并由 Agent 基于代码证据自主收口范围？
  A(原话):
  > Kernel session aggregate
  > 删除死 kernel subprocess seam
  > 这两个事情，你分别派一个subagent去做完change-spec和change-design。然后你派独立的change-design-reviewer去找问题。明白吗？先跟我对齐想法。
  >
  > 对的。你在派reviewer的同时，你要自己检查，是否符合你想治理的问题。不要走歪了。开始干
  Agent 解读: 用户已授权本 subagent 基于生产 wiring 自主拍板，无需逐项问答；范围必须锁定在 refactor-387 后的死 kernel subprocess seam，之后交由独立 `change-design-reviewer` 审查，root 同时独立检查设计是否命中原治理问题。

## 现状痛点

refactor-387 已把 Kernel 改为 Gateway 进程内持有的库，但生产代码、配置和测试仍同时叙述两套互相矛盾的架构：

1. 生产入口 `main → run_gateway → build_runtime` 只会构建进程内 Kernel，`GatewayProcessManager` 没有任何生产构造点；`GatewayRuntime` 却仍接受可选 process manager，并保留启动、健康轮询和停止 kernel 子进程的分支。测试可以继续把这条生产中不存在的路径“测活”。
2. Gateway 配置仍暴露整个 `kernel:` 连接块。`base_url`、token、request id、HTTP timeout、command、health path 已无运行时消费者；但 `startup_timeout_seconds`、`shutdown_grace_seconds`、`health_poll_interval_seconds` 又被错误复用于 Gateway 自身后台进程的启停，形成“文档说全死、代码却有三项活语义”的事实漂移。
3. 后台运行状态仍保存 `health_url`，`stop` 会按旧 Kernel `{"healthy": true}` 协议探测它；refactor-387 后该值实际可能是 IM 地址或 `pid=...`，因而这套健康判断既不再代表 Kernel，也不能可靠代表 Gateway。
4. 活跃开发入口仍残留旧拓扑：`AGENTS.md`、e2e 起停脚本、e2e 泄漏进程 finalizer、M170 acceptance helper、LLM fixture 指引、provider error 集成测试说明和 tracked 示例配置仍提到 Kernel API、`.api.pid`、已删除的 `personal_assistant.kernel_app` 或 `agent.platform.http_api.app:app`。

这些残留让读者、测试和后续 agent 误以为“独立 Kernel 进程”仍是受支持的替代部署形态，扩大 composition root 的 interface，也让真正属于 Gateway 的后台生命周期配置失去明确所有者。

## 目标状态

系统只保留当前真实架构：Gateway 后台启动器可以创建/停止 **Gateway 自身进程**，Gateway 进程内经 `agent.sdk` 持有 Kernel；不存在任何可注入、可配置、可被测试复活的 Kernel subprocess 路径或 HTTP health 语义。

三项仍在使用的启停 timing 归属 Gateway 自身：新配置使用 `gateway:`；旧 `kernel:` mapping 中的对应三项可单向迁移，确保已有自定义时序不被静默改变。其余旧连接/HTTP 字段不再验证、不再生效，保存配置时不再回写 `kernel:`。这不是保留旧 seam 的兼容包装，而是把仍存活的 Gateway 行为迁到正确所有者后删除旧 runtime interface。

`_KernelClientShim`、Gateway 自身的后台 supervisor、进程组清理和进程内 Kernel 的有序关闭都是生产活路径，必须保留。历史 change/archive 文档保留为考古证据，不做全局文本抹除。

默认后台启动只确认 Gateway child 已写入 PID 且仍存活，不把该信号包装为 health/readiness。运维输出保留真实的 `Gateway started (pid=...)`、日志路径和独立 IM 配置信息；runtime/channel 何时 ready 仍是 child 内部状态，本 unit 不新增跨进程 IPC 或对外就绪承诺。

## 用户侧验收标准（不变性与配置迁移）

### Requirement: 用户消息与主动任务仍由进程内 Kernel 正常执行

#### Scenario: Web IM 或外部通道消息正常回复
- **GIVEN** Gateway 已按现有配置连接一个可用通道
- **WHEN** 终端用户向 Agent 发送一条消息
- **THEN** 消息仍被正确 Agent 处理并回复到原通道原目标，结果与变更前一致

#### Scenario: Heartbeat 与 Cron 活路径不受清理影响
- **GIVEN** 某 Agent 已启用 heartbeat 或 cron
- **WHEN** 到达调度时刻或用户手动触发任务
- **THEN** 任务仍按现有会话、投递和运行历史语义完成，不因删除旧 Kernel 进程路径而失效

### Requirement: 运维者仍把 Gateway 当一个后台服务管理

#### Scenario: 默认启动确认
- **WHEN** 运维者执行 `python -m personal_assistant.main`
- **THEN** 命令确认 Gateway child 已写入 PID 且仍存活后返回，打印 `Gateway started (pid=...)`、日志路径，并在已配置时单独打印 IM 服务信息
- **AND** 命令不输出或探测 Kernel health/readiness endpoint，也不把该启动确认承诺为 runtime/channel 已 ready；系统不启动独立 Kernel API 进程

#### Scenario: stop 与 restart 保持现有结果
- **GIVEN** 某 config 对应的 Gateway 正在后台运行
- **WHEN** 运维者执行 `stop` 或 `restart`
- **THEN** Gateway 仍按现有优雅关闭、超时强杀和单实例规则结束或重启，活动运行进入明确终态，不遗留独立 Kernel 进程

#### Scenario: IM 离线时 Gateway 本地自治不变
- **GIVEN** IM 服务不可达但外部通道可用
- **WHEN** Gateway 启动并收到外部通道消息
- **THEN** Gateway 仍在本地进程内执行 Agent 并回发原通道，IM 离线不阻断主路径

### Requirement: Gateway 生命周期 timing 有明确且可迁移的配置所有权

#### Scenario: 旧自定义 timing 继续生效
- **GIVEN** 现有配置只在 `kernel:` mapping 中设置 `startup_timeout_seconds`、`shutdown_grace_seconds` 或 `health_poll_interval_seconds`
- **WHEN** Gateway 加载该配置并执行后台启动或停止
- **THEN** 三项值分别按原语义作用于 Gateway 自身的启动等待、关闭宽限和轮询间隔，不被静默改回默认值

#### Scenario: 新配置优先于旧值
- **GIVEN** 同一配置同时提供新的 `gateway:` timing 与旧 `kernel:` timing
- **WHEN** Gateway 加载配置
- **THEN** 新 `gateway:` 中逐字段提供的值优先，未提供的字段才从旧 mapping 迁移

#### Scenario: 保存后只保留 Gateway 所有权
- **GIVEN** Gateway 已从含旧 `kernel:` mapping 的配置启动
- **WHEN** 系统因现有配置同步流程保存该配置
- **THEN** 系统先为该具体 config 文件创建不可覆盖的迁移前备份，再把仍存活的 timing 以 `gateway:` 字段写回；旧 `kernel:` 块及其中的连接、command、HTTP health 字段不再写回
- **AND** 备份失败时原 config 不被覆盖

#### Scenario: 旧连接与 HTTP 字段不再形成运行时输入
- **GIVEN** 配置的 `kernel:` mapping 含 `base_url`、token、request id、HTTP timeout、command 或 health path
- **WHEN** Gateway 加载并运行
- **THEN** 这些字段不再被验证或生效，Gateway 仍只构建进程内 Kernel

### Requirement: 维护者的一键真栈只管理 IM 与 Gateway

#### Scenario: e2e 起停无 Kernel API 产物
- **WHEN** 维护者执行 `scripts/e2e-up.sh` 后再执行 `scripts/e2e-down.sh`
- **THEN** 真栈仍可启动、就绪并干净停止，运行期只有 IM 与 Gateway 两类服务，不生成或依赖 `.api.pid`、Kernel API 端口或 `personal_assistant.kernel_app`

## 影响范围

- Gateway composition root 与 `GatewayRuntime` 生命周期 interface。
- Gateway 本地配置的解析、保存与旧 `kernel:` timing 单向迁移。
- Gateway 后台启动结果、运行状态文件和 stop/restart 的 PID/进程组语义。
- 只守护旧子进程路径的单元测试，以及依赖 `LocalConfig.kernel` 的测试 fixture。
- 活跃的 operator/developer 文档、e2e/acceptance/LLM fixture helper、provider error 测试说明与 tracked 示例配置中的旧拓扑残留。
- 不改变 `agent.sdk`、Kernel 内部执行、IM 协议、channel 路由、heartbeat/cron 产品语义。

## 迁移与回滚策略

1. **配置单向迁移**：运行时数据结构不再含 `KernelConfig`。loader 优先读 `gateway:`；对旧 `kernel:` mapping 只迁移三项仍存活的 timing（其中 `health_poll_interval_seconds` 重命名为 Gateway 的 `poll_interval_seconds`），其余字段忽略。保存时只写 `gateway:` 非默认值并裁掉 `kernel:`。
2. **默认与自定义行为均守恒**：三项默认值保持现状；旧配置中的自定义 timing 有回归测试证明迁移后数值一致；新旧冲突有逐字段优先级测试。
3. **状态文件向前读取**：旧 `.gateway-state.json` 中多出的 `health_url` 作为未知字段忽略，PID/config/log 元数据仍可用于 stop；新状态不再写 Kernel-style health 字段。
4. **删除而非兼容包装**：不保留 `GatewayProcessManager`、可选 `process_manager`、Kernel command/HTTP client port、旧 health probe 或仅为它们存在的测试 double。
5. **每文件迁移备份与回滚**：任何现存 config 第一次因本迁移裁掉 `kernel:` 前，系统必须在同目录保存该文件的原始字节为确定性、不可覆盖的 migration backup；不局限于默认 config。若备份创建/校验失败则中止写回。回滚时先从对应 migration backup 恢复旧 config，再回退原子 milestone；不通过重新引入双运行时路径做降级。

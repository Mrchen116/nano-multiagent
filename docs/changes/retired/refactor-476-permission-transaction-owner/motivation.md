# refactor-476: 收拢权限请求事务所有权

> 状态：Retired（2026-10-19）。退役原因与当前入口见[退役索引](../README.md)。以下内容保留历史，不再作为实施要求。

> 状态：v5（2026-07-25）

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-477、refactor-479；历史 refactor-462

## 原始诉求

> 再看看当前代码仓中有多少巨石代码
>
> 我希望你能明确当前所有的重要的架构问题，如果和CC有类似的概念则和CC的源码的架构做对比，然后用change-spec-author，change-design-author skill（不需要跟我逐个进行对齐），帮我创建独立的几个unit。我要逐个进行重构，完善架构。我最终做一次确认后，再开始按可并行性开始做各个unit的实现。
>
> 中途你全程负责。我只做最终的确认。

## 澄清记录

- Q1: 是否在每个问题、边界和方案处逐个等待确认？
  A: “中途你全程负责。我只做最终的确认。”
- Q2: 是否因为 `runtime.py` 文件大而拆分？
  A: 不以行数为判据；仅处理已由真实调用链证明的权限事务所有权分裂。

## 现状痛点

`AgentEngine` 内约 190 行嵌套闭包同时承担权限请求注册、事件发布、存活通知、CLI 回调与外部决定竞态、取消、败者任务回收和 resolved 事件发布。它还直接访问 `PermissionBroker._lock` 与 `_pending`，而 broker 又被定义为 pending 状态的唯一所有者。测试复制同一竞态并修改私有字段，说明模块边界没有隐藏关键规则。

不改的后果是：下一次增加权限入口、取消方式或超时策略时，必须同时理解 engine、broker、SDK、CLI、Gateway 与 IM 的时序；register-before-publish、exactly-once pop 和 run-scoped cancel 等正确性继续依赖跨模块默契。

## 目标状态

形成一个可直接执行完整权限事务的深模块：调用方只提交请求上下文与可选本地决策端口，模块内部保证注册、发布、竞态、取消、存活、清理和最终事件的顺序。`AgentEngine` 负责触发事务，产品层继续只负责显示或给出决定，不再持有 pending 状态。权限事务的取消与清理不再依附承载 run 的 Task；即使 run carrier 已被强制取消，broker 仍能在有界时间内恢复本地终端模式并删除 pending。

本 unit 不改变权限策略、文案、协议帧、默认行为或产品交互。为让 Coding CLI 的主事件循环与
Kernel executor 事件循环安全协作，`agent.sdk` 新增一个**可选**、SDK-owned 的本地权限交互
port；既有三参数 `CanUseToolFn` 及第三参数的原始 request 语义保持不变，任意外部应用无需迁移。
权限 request event 若未被本地事件流成功接受，当前 ask 必须 fail closed 为拒绝；不能让通用
hook 错误隔离把本应询问的工具放行。

非 TTY CLI 仍按完整行顺序处理管道输入、正常退出且不输出 ANSI 控制码；本 unit 只把 canonical
中绑定具体 `input()` 函数的实现措辞改为机制中立的行为契约，以允许同一个可停止输入 owner 同时
覆盖 TTY、管道与权限交互。一次物理 pipe read 即使预取多行，输入 owner 也必须按当前逻辑读取
需求一次只分配一行；permission 只消费自己的一行，未分配的后续完整行保持 FIFO，留给恢复后的
normal REPL。

隔离承诺只覆盖每次 `build_kernel()` 真正新建并拥有的 run、permission、local-task、executor 与
finalizer 资源图：关闭一个 Kernel 不得收走另一个 Kernel 的这些资源。当前模型目录仍是进程级
共享注册表；本 unit 不把多个不同 model catalog 的 Kernel 改造成可并行独立提交，也不在契约中
作这项承诺。

## 用户侧验收标准（不变性）

当前用户在 Coding CLI 中会看到权限询问并可允许或拒绝；在 Web IM 中会收到权限卡片并提交决定；中断或取消运行后旧请求不能继续生效。重构后这些行为及事件顺序保持一致。

### Requirement: CLI 权限交互保持

#### Scenario: 本地允许或拒绝工具
- **WHEN** 用户在 Coding CLI 对一次工具权限请求作出允许或拒绝
- **THEN** 工具执行结果、终端显示和后续运行状态与变更前一致

#### Scenario: 管道预取跨过权限模式切换
- **GIVEN** 非 TTY stdin 在一次 pipe write 中送入多条完整行
- **WHEN** CLI 在处理这些行期间从 normal mode 进入 permission mode，再恢复 normal mode
- **THEN** permission 只消费分配给该次决定的一行
- **AND** 其余完整行保持原 FIFO 顺序供恢复后的 normal REPL 处理，不因物理预取或模式切换被丢弃

### Requirement: Gateway 权限交互保持

#### Scenario: IM 权限卡片决定
- **WHEN** 用户在 Web IM 的权限卡片提交允许或拒绝
- **THEN** 对应运行只消费一次该决定，卡片与运行结果和变更前一致

### Requirement: 取消语义保持

#### Scenario: 权限等待期间中断运行
- **WHEN** 用户在权限请求尚未解决时取消或中断运行
- **THEN** 等待被释放、旧决定不污染后续运行，表现与变更前一致

#### Scenario: 权限请求无法交付
- **WHEN** 权限 request event 在进入本地事件流时同步失败
- **THEN** 当前工具调用被拒绝，且不残留 pending request 或伪造 resolved event

## 影响范围

- `src/agent/core/agent/runtime.py` 的权限请求触发逻辑
- `src/agent/platform/permissions/` 的事务与 pending 状态所有权
- `src/agent/sdk/kernel.py` 的取消和外部决定入口
- CLI / Gateway 权限适配器与相关单元、集成测试
- `agent.sdk` 新增可选的 `PermissionInteractionPort` 与 SDK-owned interaction value；
  既有 `CanUseToolFn`、Kernel 方法集和 Gateway 装配不变
- 每 Kernel 的 permission/run/local-task/executor/finalizer 关闭隔离；进程级 model registry
  不在本 unit 迁移
- `specs/kernel/sdk-boundary.md`、`specs/kernel/runs.md` 与 `specs/cli/spec.md` 的完整
  MODIFIED delta

## 迁移与回滚策略

先用生命周期接口测试锁定 resolve/cancel/local-callback 竞态、carrier 强制取消和事件顺序，再把
engine 的完整事务迁入单一所有者，迁移 SDK 取消路径与 CLI loop-neutral 交互 port，最后删除私有
状态访问和复制的竞态测试。旧 `CanUseToolFn` 是长期兼容入口，不是临时 façade；新旧本地入口在一次
`build_kernel` 中互斥，避免双决策 owner。任何阶段出现不一致时回滚整个 unit；不保留双写或两套
pending 状态。

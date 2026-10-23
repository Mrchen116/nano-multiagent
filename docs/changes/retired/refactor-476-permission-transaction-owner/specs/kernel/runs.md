# Kernel Runs delta — refactor-476

> 本 delta 完整替换 `docs/specs/kernel/runs.md` 的 permission 与 Kernel 关闭 Requirements。
> canonical 原 callback/interrupt/close 场景均保留，并增加 SDK local port、remote-only、
> first-wins、publication-failure、重复关闭失败重放与多 Kernel owned-resource 关闭隔离契约。
> unit 收尾时按最终实现归并。

## MODIFIED Requirements

### Requirement: 工具使用权限经唯一的注入交互路径裁决

内核不内置产品权限策略。消费者在 `build_kernel` 时可以注入既有三参数
`can_use_tool` 异步回调，或注入 SDK-owned `permission_interaction_port`；两者互斥。
两者均未提供时，权限请求经既有 session events 交给远端消费者，再由
`submit_permission_decision()` 回传决定。

无论使用哪条交互路径，同一个 request 都由一个权限事务 owner 执行
register → request publication → local/remote/cancel first-wins settlement → resolved
publication → cleanup。任一晚到决定不得覆盖 winner；run interrupt/cancel 必须解除挂起，
且旧 request 的晚到决定不能污染后续 run。

#### Scenario: 需要许可时 can_use_tool 被调用并采纳其决定
- **GIVEN** 一个注入了 `can_use_tool` 的 Kernel
- **WHEN** 运行中触发一次工具许可请求
- **THEN** `can_use_tool(tool_name, tool_input, raw_request)` 被调用;它返回 `allow` 则该次工具被放行,
  返回 `deny` 则被拒绝
- **AND** callback 仍接收未经替换或包裹的原始 request

#### Scenario: 等待许可期间 interrupt 解除挂起
- **GIVEN** 一次许可请求正阻塞在本地 callback、local port 或远端决定
- **WHEN** 消费者对该会话调 `kernel.interrupt(session_id)`
- **THEN** 挂起的许可请求被解除为拒绝(deny),等待者立即返回而不会无限挂起
- **AND** 该 request 的晚到本地或远端决定不改变终态

#### Scenario: SDK local port 提供可取消交互
- **GIVEN** Kernel 只注入了 `permission_interaction_port`
- **WHEN** 运行触发许可请求
- **THEN** port 收到 tool name、tool input、原始 request 与 SDK-owned interaction
- **AND** port 返回的 `PermissionDecision` 被采纳
- **AND** 其他决定或 run cancel 先赢时，interaction 的 cancellation signal 可从 port 当前
  asyncio loop 正常等待

#### Scenario: 两个本地权限 owner 不能同时装配
- **WHEN** `build_kernel` 同时收到 `can_use_tool` 与 `permission_interaction_port`
- **THEN** 在创建任何 runtime/task 前抛出 `ValueError`

#### Scenario: remote-only 请求由外部决定
- **GIVEN** Kernel 未注入 callback 或 local port
- **WHEN** 运行触发许可请求
- **THEN** session stream 产出既有 permission request event
- **AND** 外部消费者调用 `submit_permission_decision()` 后，该决定解决原 request

#### Scenario: local、remote 与 cancel 只采纳第一个决定
- **GIVEN** 同一 request 同时可能收到 local callback/port、远端 response 或 run cancel
- **WHEN** 任一来源先完成 settlement
- **THEN** 只有 winner 决定工具放行或拒绝并产生一次 resolved 结果
- **AND** 其余来源返回未命中或被取消，不覆盖 winner

#### Scenario: permission request 事件无法发布时 fail closed
- **GIVEN** 一次 ask 型权限请求尚未交付给任何本地或远端交互方
- **WHEN** session event publisher 同步失败
- **THEN** 当前工具调用被拒绝，不因通用 hook 的错误隔离而继续执行
- **AND** request 不残留 pending，未确认发布的 request 不伪造 resolved event

### Requirement: Kernel 关闭会收拢所有 owned runs

`Kernel.aclose()` 与同步兼容接口 `Kernel.close()` 必须共享该 Kernel 实例的幂等关闭状态，停止接受
新运行，解除权限等待，中断或取消仍在执行/排队的 run，等待其 owned permission interaction 与
RunsRegistry 创建的 Task 在所属 event loop 与 Context 中进入终态，再停止并关闭该实例的 loop。
关闭开始后不得创建新的 queued run；异步消费者使用 `aclose()` 时不得阻塞其 event loop。关闭一个
Kernel 不得 seal、取消或停止其他 `build_kernel()` 调用产生的 run、permission、local-task、
executor 或 finalizer owned graph。模型目录仍是进程级共享基座；本 Requirement 不承诺不同
model catalog 的多个 Kernel 可独立提交。

#### Scenario: 有活动运行时关闭
- **GIVEN** Kernel 存在 running run 或权限等待
- **WHEN** 异步消费者 await `kernel.aclose()` 或同步消费者调用 `kernel.close()`
- **THEN** 相关 run 在有限 grace period 内进入 completed/failed/cancelled 之一，Registry 不遗留
  Task，tracing scope 在原 Task Context 中退出
- **AND** 该 Kernel 的本地权限交互收到取消，关闭返回后不再采纳该交互的晚到决定

#### Scenario: 异步关闭不阻塞消费者 loop
- **GIVEN** 消费者的 event loop 还有 heartbeat、IM 或 UI 状态任务
- **WHEN** 消费者 await `kernel.aclose()`
- **THEN** Registry 在自己的 loop/thread 中 drain，消费者 loop 在等待期间仍可调度其他任务

#### Scenario: 关闭期间拒绝新提交
- **GIVEN** Kernel 已进入 draining 或 closed 状态
- **WHEN** 消费者调用 `submit`
- **THEN** 返回稳定的 closed error，不创建 queued run 或后台 Task

#### Scenario: 重复关闭
- **WHEN** 消费者多次调用或混用同一 Kernel 的 `kernel.aclose()` 与 `kernel.close()`
- **THEN** 关闭 finalizer 只执行一次，不重复停止 loop
- **AND** 首次关闭成功时，所有同时等待及后到调用均安全返回同一成功终态
- **AND** 首次关闭失败时，所有同时等待及后到调用均重放同一 primary close failure，不重试
  finalizer，且不产生新的 secondary failure

#### Scenario: 关闭一个 Kernel 不影响另一个 Kernel
- **GIVEN** K1 与 K2 以兼容的进程级 model catalog 装配，且两者各有待决本地权限交互
- **WHEN** 消费者关闭 K1
- **THEN** K1 停止接受新工作并收拢自己的 permission 与 run
- **AND** K2 的 run、permission、local task、executor 与 finalizer 不被 K1 关闭触碰
- **AND** K2 待决交互未被 K1 取消且可继续解决，K2 可随后独立关闭

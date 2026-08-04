# bugfix-496: Gateway 异常退出后 Feishu listener 假在线

## Relations

- Related: feat-464
- Closes: #230

## 原始报告

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) https://github.com/Mrchen116/nano-multiagent/issues/230 修复这个问题，提高用户体验

> Issue #230：https://github.com/Mrchen116/nano-multiagent/issues/230
>
> 关键表现：“假在线无回复”。

## 澄清记录

- Q1: Gateway 再次启动并发现同一 Feishu 应用的旧 listener 时，期望自动恢复还是明确失败？
  A(原话): 我觉得关键在gateway关闭的时候要把飞书 channel也关掉。而不是等下次开的时候检测他有没有关
  Agent 解读: 目标应前移到 Gateway 退出边界：Gateway 关闭时必须同步关闭其拥有的 Feishu channel，不把“下次启动扫描并清理残留 listener”作为主要产品机制。

- Q2: “Gateway 关闭时关闭 Feishu channel”是否也包括崩溃、`kill -9` 等非正常退出？
  A(原话): 号
  Agent 解读: 结合上一轮“包括的话，能做到吗”及本轮答复，按“好，确认”理解；只要 Gateway 进程不再存活，其拥有的 Feishu listener 就必须随即退出。

- Q3: 本期是否聚焦 Gateway 与 Feishu listener 的联动退出，复用现有通道页状态，不新增入站空闲看门狗？
  A(原话): 好
  Agent 解读: 本期修正父子生命周期；Gateway 离线、重启和重新连通继续使用现有状态语言。不通过“长时间没有入站消息”判定故障，也不在下次启动时扫描孤儿进程。

## 现象与复现

Gateway 正常运行时，每个已启用的托管飞书 channel 都有一个独立 listener 子进程维持飞书 WebSocket 长连接。正常 `stop`、`restart` 或可处理的终止信号会进入 Gateway 的关闭流程，停止 managed channel 并回收 listener。

当 Gateway 父进程未进入关闭流程便异常退出时，listener 子进程仍会继续存活并被系统收养。Gateway 随后从本地密文 cache 恢复同一 channel 时会再创建一个 listener。新 Gateway 和旧孤儿都可能显示长连接成功，但飞书入站事件可能被旧孤儿接收；旧孤儿已经失去 Gateway、Agent 和 IM 投递链，消息因此静默消失。

生产现场的稳定表现见 Issue #230：

1. 飞书 Bot 先正常回复，随后多条用户消息不再获得回复，也没有进入 IM messages 表；
2. IM 通道状态仍显示 `connected`；
3. 同机同时存在旧的 `PPID=1` listener 与新 Gateway 创建的 listener，二者都保持飞书长连接；
4. 人工终止旧孤儿并重连 channel 后恢复收发。

本地最小复现进一步确认父子生命周期缺口：启动现行 `FeishuWorkerRuntime` 后让父进程直接 `os._exit(23)`，worker 继续存活并变为 `PPID=1`；只有额外向该 worker 发终止信号后才退出。该复现不依赖飞书凭据，证明问题发生在飞书业务事件进入 Gateway 之前的进程生命周期边界。

## 影响范围

- 受影响的是 `personal_assistant` Gateway 托管的 Feishu channel；触发条件是 Gateway 崩溃、被强制终止或其他未执行正常关闭流程的退出。
- 受影响 Bot 的用户会看到 Bot 和通道状态看似在线，但发送的消息可能完全没有回复；消息若被孤儿接收，也不会进入内部 IM 影子会话。
- Gateway 重启不会自行消除影响，反而会形成新旧两个长连接，使故障具有偶发性：有些消息可能正常，有些消息静默丢失。
- Web IM 不经过 Feishu listener，不受这项双连接机制影响。
- 没有证据表明已有配置、凭据、影子会话或历史消息被篡改；数据影响是故障期间的飞书入站消息可能未被 Gateway 接收和记录，无法由本系统补回。

## 根因分析（RCA）

### 直接根因

`FeishuWorkerRuntime` 使用非 daemon 的 `multiprocessing` 子进程运行飞书 SDK listener。正常关闭时，Gateway 会通过 managed channel owner 调用 worker stop，并依次等待、终止或强杀子进程；但 worker 没有独立于父进程正常控制流的“父进程已死亡”信号。因此父进程以崩溃、`kill -9` 或 `os._exit` 方式消失时：

1. Gateway 的 `finally` 与 managed channel close 不会执行；
2. 操作系统允许非 daemon listener 继续存活，并把它的父进程改为系统进程；
3. listener 继续持有飞书 WebSocket，却已经失去将事件交给 Gateway 的有效父端。

Gateway 重新启动时，`ChannelManager` 只持有本进程内的 active runtime 集合。它从密文 cache 恢复 desired channel 后会正常创建新 worker，并不知道上一个 Gateway 遗留的进程。于是同一个飞书应用出现两个 listener。新 worker 上报的 `connected` 只证明自己的 SDK 长连接建立成功，不能证明平台入站事件不会被旧孤儿抢走；IM 和通道页因此仍可能显示绿色“已连接”。

### 原始设计意图与必须保住的不变量

这项 worker 隔离由 `feat-464` 引入，原始目标是绕开飞书 SDK 缺少可靠线程级停止接口的问题，让每个 Bot 的 SDK event loop 位于独立进程，并由唯一 `ChannelManager` 完成热新增、替换、停用、重连和删除。原 unit 明确要求：

- 每个飞书 Bot 使用独立 listener，多个 Bot 彼此隔离；
- 同一 channel 替换时先停止旧 runtime，再启用新 runtime；
- listener 可以真实 stop/join，Gateway 清理后不残留 worker；
- worker 状态按 runtime incarnation 与 sequence 保持因果顺序；
- Gateway 从密文 cache 离线启动、IM 托管配置热调和以及飞书主消息路径保持可用。

修复必须保留这些不变量。不能通过恢复不可停止的 daemon thread、取消进程隔离、禁用离线 cache 启动，或牺牲多 Bot 隔离来消除症状。

### 回归引入点

commit `3577ad1127`（`feat(feat-464/M1/R2): 隔离 Feishu worker 并统一动态生命周期`）引入了现行 spawn worker，并将其设为 `daemon=False`。后续 commit `b945519861`（`fix(feat-464/M4/R4): bound listener lifecycle recovery`）补强了父进程仍存活时的 join、terminate、kill 和重启预算，但没有覆盖父进程本身已经消失的路径。

该缺口能够进入主线，是因为原有测试和验收都从仍存活的 owner 调用 `runtime.stop()`、`ChannelManager.close()`、替换或失败恢复，再断言 worker 已回收；真栈收尾也显式执行 Gateway shutdown 或进程组清理。没有回归用例先让 Gateway 父进程在无法执行清理的条件下死亡，再独立断言其 Feishu listener 随之退出。测试因此证明了“owner 发起关闭时能回收”，却把它误当成了“owner 消失时也不会留下孤儿”。

### 为什么不采用启动扫描或入站空闲检测

当前 worker 的系统命令行只呈现通用 `multiprocessing.spawn`，不携带可安全用于进程清理的 channel 身份。下次启动时扫描并猜测孤儿既不能可靠归属，也可能误伤其他 Python worker。与此同时，长时间没有飞书入站消息可能是正常空闲，不能证明连接失效。两者都没有闭合“Gateway 已退出但它拥有的 listener 仍存活”这一根因。

## 用户场景

运维者把 Gateway 作为后台服务运行，也可能以前台模式调试。无论运维者正常停止、重启 Gateway，还是 Gateway 因崩溃或强制终止突然消失，它所启动的飞书 listener 都与该 Gateway 共享同一生命周期，不会独自在机器上继续占用长连接。

Gateway 离线后，用户在 IM 通道页看到现有的节点离线与上次状态提示，而不是把旧 listener 当作仍然有效的绿色连接。Gateway 重新启动时，通道按现有流程经历连接中并收敛为真实已连接；此后用户从飞书发消息，消息进入当前 Gateway，Bot 正常回复并同步到 IM 影子会话，不再因旧孤儿抢占事件而随机沉默。

正常安静的飞书 channel 不会因为一段时间没有入站消息被误判失败。本期用户无需学习或执行查找 `PPID=1`、手工杀进程、再重连 channel 的恢复步骤。

## 验收标准

### Requirement: Feishu listener 与 Gateway 共享退出生命周期

#### Scenario: 正常停止 Gateway

- **GIVEN** Gateway 已启动并连接一个托管飞书 channel
- **WHEN** 运维者执行正常 `stop` 或 `restart`
- **THEN** Gateway 退出后，运维者看不到仍由旧 Gateway 遗留的飞书 listener 进程
- **AND** restart 启动的新 Gateway 可以正常接管该 Bot

#### Scenario: Gateway 异常死亡

- **GIVEN** Gateway 已启动并连接一个托管飞书 channel
- **WHEN** Gateway 崩溃或被强制终止，来不及执行正常关闭流程
- **THEN** 运维者看不到该 Gateway 遗留的孤儿飞书 listener，旧 listener 也不再继续占用飞书长连接或接收用户消息

### Requirement: Gateway 重启后飞书消息稳定恢复

#### Scenario: 异常退出后重新启动 Gateway

- **GIVEN** 托管飞书 channel 所属 Gateway 曾异常退出，随后重新启动
- **WHEN** 通道页从节点离线或连接中收敛为“已连接”，用户在飞书向 Bot 连续发送消息
- **THEN** 每条应触发响应的消息都进入当前 Gateway，并按既有行为获得 Bot 回复
- **AND** 对应用户消息与回复继续同步到内部 IM 影子会话，不因旧 listener 而随机缺失或重复

#### Scenario: Gateway 离线期间查看通道状态

- **GIVEN** Gateway 已退出且 IM 已判定对应节点离线
- **WHEN** 用户打开 Agent 的通道页
- **THEN** 页面沿用现有离线与上次状态提示，不把退出前的 Feishu 连接状态显示为当前有效的“已连接”

### Requirement: 正常空闲不被误判为故障

#### Scenario: 已连接通道长时间没有入站消息

- **GIVEN** Gateway 与飞书 channel 均正常运行，但用户一段时间没有向 Bot 发消息
- **WHEN** 用户查看通道状态
- **THEN** 系统不会仅因没有入站消息而把通道降级、重连或标记失败

## 范围与非目标

- 在范围：
  - 后台与前台 Gateway 正常停止、重启和异常死亡时，其 Feishu listener 的联动退出；
  - 异常退出后重新启动 Gateway，飞书 channel 按现有状态流程恢复，并稳定接收消息；
  - 保持节点离线、连接中、重连中、已连接和上次状态的现有用户语言；
  - 覆盖“父进程无法执行清理”的回归验证，同时保持正常 close、热替换、停用和删除路径不回归。
- 非目标：
  - 在 Gateway 下次启动时扫描、识别或清理历史孤儿进程；
  - 根据一段时间没有飞书入站消息推断连接故障，或新增入站空闲看门狗；
  - 改变飞书私聊、群聊、影子会话、回复镜像、权限审批或权限诊断语义；
  - 改变 IM 离线时飞书主路径自治、密文 cache 恢复或多 Bot 隔离能力；
  - 为当前不存在独立 listener 子进程的其他 channel 预先设计通用机制。

## 修复方向

把 Feishu listener 的存活条件绑定到创建它的 Gateway：正常关闭继续执行有序 managed channel close；即使 Gateway 无法运行清理代码，listener 也必须能够感知 owner 已消失并自行退出。Gateway 重启只负责按现有 desired state 启动当前 listener，不承担扫描或猜测历史孤儿的职责。

具体的父进程存活信号、worker 退出方式、测试驱动和平台细节由 design 阶段决定；方案必须证明后台与前台启动、正常信号关闭、崩溃和强制终止均满足上述用户行为，并保持 `feat-464` 的进程隔离与 managed channel 不变量。

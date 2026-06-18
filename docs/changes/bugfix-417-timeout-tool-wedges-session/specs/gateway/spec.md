# Gateway Specification (delta for bugfix-417)

> 本 delta 对既有 canonical 做 diff。本 unit **重定义** idle 看门狗判据（输出静默 + permission 特例 → 统一 liveness 心跳）与失败态映射（watchdog-reap 原因从「执行超时」改「已中断」、「执行超时」改归工具自身 deadline），二者在 canonical 已有契约（其一正是 incident RCA 说的"把 idle 与 max-duration 混为一谈"的契约化身），故用 MODIFIED 顶替既有完整条目，不用平行 ADDED。

## MODIFIED Requirements

### Requirement: 入站消息按四步决策路由并回发原通道原目标

任一通道(外部 IM 或内置 Web IM)收到一条入站消息时,Gateway 依次决策:路由到哪个 Agent、用哪个会话、是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标,不跨通道混发。idle 看门狗按 **liveness 心跳**判定一轮是否仍有进展——执行静默长工具、等待 LLM 返回、等待用户权限决策这三类"活着但安静"的窗口都有周期性 liveness 心跳，看门狗不再以"无业务输出事件"判卡死、也不再为某一类窗口单列特例豁免；只有在判定窗口内既无业务事件也无 liveness 心跳时才判失去进展并收尾。

#### Scenario: 直聊消息被默认 Agent 处理并把回复发回原通道
- **GIVEN** 一个配置了至少一个 Agent 的 Gateway,且消息未显式指定 `agent_id`
- **WHEN** 终端用户经某通道发来一条直聊消息
- **THEN** 消息被路由到命中的 Agent(显式 `agent_id` → channel/chat 绑定 → 节点默认 Agent),交内核执行,最终 Agent 回复经原通道的出站路由回发到发起会话

#### Scenario: 同会话串行、跨会话并行
- **GIVEN** 同一会话已有一轮在执行,另有一条属于不同会话的消息同时到达
- **WHEN** 两条消息先后进入 Gateway
- **THEN** 同一会话的消息排进串行 FIFO 队列、前一轮结束后才消费下一条;不同会话的消息并行推进,互不阻塞

#### Scenario: 失去 liveness 后释放同会话队列
- **GIVEN** 同一会话的前一轮已开始运行,但在判定窗口（120 秒）内既无业务事件也无任何 liveness 心跳,后一条消息正在 FIFO 中等待
- **WHEN** Gateway 判定前一轮失去进展
- **THEN** Gateway 取消前一轮并上报失败,随后消费后一条消息,不得让该会话永久阻塞

#### Scenario: 执行静默长命令期间不被 idle 看门狗误杀
- **GIVEN** 某轮正在执行一个耗时远超判定窗口、其间无标准输出的命令
- **WHEN** 命令持续在执行（有周期性 liveness 心跳）
- **THEN** 该轮不被看门狗取消，命令跑完结果正常返回

#### Scenario: 等待 LLM 返回期间不被 idle 看门狗误杀
- **GIVEN** 某轮长时间等待 LLM 返回但连接活着（有周期性 liveness 心跳）
- **WHEN** 等待时长超过判定窗口
- **THEN** 该轮不被看门狗误判卡死

#### Scenario: 等人工权限决策期间不被 idle 看门狗误杀
- **GIVEN** 某轮已发起一个需要授权的工具,正等待用户在权限卡片上决策（其间有周期性 liveness 心跳）
- **WHEN** 等待时长超过判定窗口
- **THEN** 该轮不被 idle 看门狗取消;用户随后批准则工具正常执行、该轮继续推进,不报「relay idle for 120s」

#### Scenario: 路由到未知 Agent 被拒
- **WHEN** 入站消息显式指定一个 Gateway 未注册的 `agent_id`
- **THEN** Gateway 拒绝该路由(抛 `LookupError`),不创建会话也不执行

### Requirement: /stop 控制命令中断当前运行

终端用户发 `/stop`(支持 `/stop`、`@agent /stop`、`/stop @agent` 形式)可中断该会话当前活动运行;无活动运行时返回友好提示而非报错。中断时若该轮正在执行派生了子进程的工具(如长 shell 命令),其子进程(树)必须被终止、不留孤儿,该在飞工具收口为「已中断」终态;中断后同会话立即可发新消息正常推进,无需重启 Gateway。

#### Scenario: /stop 中断正在执行的运行
- **GIVEN** 某会话有一轮正在执行
- **WHEN** 用户向该会话发 `/stop`
- **THEN** 当前运行被中断,用户收到「已停止当前操作。」,该 /stop 动作记入会话历史

#### Scenario: /stop 中断正在跑的长命令时回收子进程并收口徽标
- **GIVEN** 某会话一轮正在执行一个长时间运行、派生子进程的命令(如 `sleep 60`)
- **WHEN** 用户向该会话发 `/stop`
- **THEN** 该命令的子进程(树)被终止、系统无残留孤儿进程;该在飞工具徽标收口为「已中断」;随后同会话发新消息能正常得到回复

#### Scenario: 无运行时 /stop 返回友好提示
- **WHEN** 某会话当前无活动运行而用户发 `/stop`
- **THEN** 用户收到「当前没有正在执行的操作。」,不抛错

### Requirement: run 进入终态时对在飞 tool_call 按原因收口

run 进入失败/取消终态(含 idle 看门狗收尸路径)时,Gateway 必须对该轮所有仍处于 running 的 tool_call 经原通道下发一个终态,并标注中断原因,使消费者侧不再有工具停留在「运行中」。中断原因区分两类:工具因自身 deadline（如命令 `timeout`）到点被掐 → 标「执行超时」(耗时过长);run 因 idle 看门狗 liveness 收尸或进程异常/中断 → 标「已中断」(卡死/中断)。已完成的 tool_call 终态不被改写。

#### Scenario: 工具自身 deadline 命中后在飞工具收口为执行超时
- **GIVEN** 某轮有一个设了自身超时的工具(如带 `timeout` 的命令)已开始执行(已发 tool_start)
- **WHEN** 该工具到达自身 deadline 被掐
- **THEN** 该工具经原通道收到终态,原因标注为「执行超时」,区别于「已中断」

#### Scenario: 看门狗 liveness 收尸后在飞工具收口为已中断
- **GIVEN** 某轮有一个工具已开始执行(已发 tool_start)但该轮在判定窗口内无任何 liveness 心跳
- **WHEN** 该轮被 idle 看门狗判定失去进展并收尸
- **THEN** 该在飞工具经原通道收到终态,原因标注为「已中断」,不再停留运行中

#### Scenario: 异常终止后在飞工具收口为已中断
- **GIVEN** 某轮有在飞工具,run 因进程异常/中断进入终态(非工具自身超时)
- **WHEN** run 进入终态
- **THEN** 该在飞工具经原通道收到终态,原因标注为「已中断」

#### Scenario: 已完成工具不被收口逻辑改写
- **GIVEN** 同一轮里其他工具已正常完成(含执行出错但已返回结果的)
- **WHEN** run 进入终态做在飞工具收口
- **THEN** 这些已完成工具的终态保持不变

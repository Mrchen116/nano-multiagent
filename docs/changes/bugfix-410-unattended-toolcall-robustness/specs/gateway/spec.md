# Gateway 契约层增量 — bugfix-410

> 本文件是 bugfix-410 对 `docs/specs/gateway/spec.md` 的 delta-spec 草案（design 期声明预计改什么；
> 收尾由 orchestrator 拿实际 diff 校正后并入 canonical）。

## MODIFIED Requirements

### Requirement: 入站消息按四步决策路由并回发原通道原目标

任一通道（外部 IM 或内置 Web IM）收到一条入站消息时，Gateway 依次决策：路由到哪个 Agent、用哪个会话、
是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标，不跨通道混发。

> bugfix-410 改动：原「静默运行失败后释放同会话队列」把「持续 120 秒无内核事件」一律判为失去进展。
> 现区分「合法等人工权限决策」与「真失去进展」——前者不计入 idle 超时。

#### Scenario: 静默运行失败后释放同会话队列

- **GIVEN** 同一会话的前一轮已开始运行，但持续 120 秒没有任何内核事件**且不处于等人工权限决策态**，后一条消息正在 FIFO 中等待
- **WHEN** Gateway 判定前一轮失去进展
- **THEN** Gateway 取消前一轮并上报失败，随后消费后一条消息，不得让该会话永久阻塞

#### Scenario: 等人工权限决策期间不被 idle 看门狗误杀

- **GIVEN** 某轮已发起一个需要授权的工具，正等待用户在权限卡片上决策
- **WHEN** 等待时长超过 120 秒
- **THEN** 该轮不被 idle 看门狗取消；用户随后批准则工具正常执行、该轮继续推进，不报「relay idle for 120s」

## ADDED Requirements

### Requirement: run 进入终态时对在飞 tool_call 按原因收口

run 进入失败/取消终态（含 idle 看门狗超时路径）时，Gateway 必须对该轮所有仍处于 running 的 tool_call
经原通道下发一个终态，并标注中断原因，使消费者侧不再有工具停留在「运行中」。已完成的 tool_call 终态不被改写。

#### Scenario: 看门狗超时终止后在飞工具收口为执行超时

- **GIVEN** 某轮有一个工具已开始执行（已发 tool_start）但因命令挂死迟迟未完成
- **WHEN** 该轮被 idle 看门狗判定超时终止
- **THEN** 该在飞工具经原通道收到终态，原因标注为「执行超时」，不再停留运行中

#### Scenario: 异常终止后在飞工具收口为已中断

- **GIVEN** 某轮有在飞工具，run 因进程异常/中断进入终态（非看门狗超时）
- **WHEN** run 进入终态
- **THEN** 该在飞工具经原通道收到终态，原因标注为「已中断」

#### Scenario: 已完成工具不被收口逻辑改写

- **GIVEN** 同一轮里其他工具已正常完成（含执行出错但已返回结果的）
- **WHEN** run 进入终态做在飞工具收口
- **THEN** 这些已完成工具的终态保持不变

# refactor-783：IM ↔ Node、PA ↔ integration 双端 RPC 契约

## Relations

- Related：[refactor-672](../archive/refactor-672-im-contract-boundaries/motivation.md) 已建立 IM 主动节点 RPC 的调用与回包关联契约。本次把约束延伸到 Node 实现端，并覆盖 PA 使用的运行时 RPC。

## 原始诉求

用户引述的 Agent 检查意见：

> ## 1. IM ↔ Node 协议是“一端有类型、另一端靠字符串”的单边契约（最重要）
>
> **现状**
>
> - IM 侧定义了完整的 `NodeCommandMap`（**node-rpc-contracts.ts:59-83**）+ 运行时解码器 `decodeNodeResult`（**node-rpc-values.ts**）——这一端是好的。
> - Node 侧 **apps/node/src/main.ts** 对此**完全不知道**：`onFrame` 是一条 30 个 `frame.type === '...'` 分支的字符串链，payload 用 `as unknown as` 裸断言（6 处），并直接以字符串调用 `relay.request('task.execution.state.result', ...)` 回包。
> - 两端共用的 `RuntimePort` 是 `request(method: string, params: unknown): Promise<unknown>`（**index.ts:74-79**）——PA → integration 同样是无类型 RPC，PA 侧约 40 个 distinct 方法名、integration 侧约 90 个 handler 名，没有任何共享注册表。
> - 全仓 relay 帧类型字符串 83 个，`product-contracts` 里只有 4 个测试文件、零 zod 帧 schema。
>
> **为什么它是问题** `product-contracts` 包的名字和 SPEC 定位（“与执行运行时无关的产品数据、配置指纹和端口契约”）承诺的是**双方共享的契约**，但实际 Node↔IM 和 PA↔integration 两个边界上，契约只存在于调用点的字面量里。改一个方法名，TypeScript 不会报错，只有 E2E 会炸。
>
> **严重度判断**：目前是单产品、单团队、DSH 锁版本，靠 E2E 兜底可以接受。但它是这个代码库里唯一一个“边界画了、类型没画”的地方，且是 SPEC 红线守护的核心边界。
>
> **建议方向**：把 `NodeCommandMap` / `nodeResponseTypes` 以及 PA↔integration 的方法表下沉到 `product-contracts`，用 `satisfies Record<...>` 让 Node 端 `onFrame` 分支与 IM 端请求表互为穷举检查；payload 用已有的 zod 做入口校验。不需要改架构，只需要把已经存在于 IM 侧的类型搬到共享位置。

用户判断：

> agent给我检查出来的问题，我觉得是需要的两边有类型，才能在开发、测试阶段就把问题给明确。不会线上再出问题，就类似rust更安全一样。你觉得呢

## 澄清记录

Agent 解读：本次要提前发现的是两端对同一请求或结果理解不一致。验收对象既包括修改协议的开发者，也包括继续使用已安装节点的用户。两条边界纳入同一 Full 重构，先处理用户标为最重要的 IM ↔ Node。原检查中的近似计数不作为交付判据。

## 现状痛点

核对基线为 `56b992e83`（`origin/develop`）。

- IM 已将 23 条中心主动 RPC 的命令名与入参、结果、预期回包名关联，并在连接、请求标识和回包名匹配后解码结果。Node 端处理 `task.execution.state` 时独立拼写结果帧名。若只改错这里，IM 会忽略不匹配的回包，调用方最终看到超时。这是源码可推导的失效方式，本次没有观察到线上事故。[IM 命令表](../../../apps/im-server/src/node-rpc-contracts.ts) · [IM 关联与超时](../../../apps/im-server/src/node-rpc.ts) · [Node 接收与回包](../../../apps/node/src/main.ts)
- 会话分支横跨两条边界。Node 接到 IM 的 `session.fork.request` 后交给 PA 的历史服务，后者经 `RuntimePort.request("session.fork", …)` 调用 integration，并在本地断言返回形状。integration 单独注册该名称。修改一端的方法名或字段，另一端的真实调用与处理函数之间缺少静态检查。[历史服务](../../../packages/personal-assistant/src/history.ts) · [运行时端口](../../../packages/product-contracts/src/index.ts) · [integration 处理端](../../../packages/dsh-integration/src/index.ts)
- 现有 IM 结果类型主要描述调用方消费的字段。例如 `task.execution.state` 的结果允许缺少 `state`，解码器也只检查已出现的值。迁移需核对有效成功、失败及缺省回包，避免将局部投影误作完整线上格式。[结果解码器](../../../apps/im-server/src/node-rpc-values.ts)
- current spec 与线上帧名存在文字差异。例如 Gateway 文档用 `skills_usage_request` / `skills_usage_response` 描述技能使用统计，当前两端使用 `node.skills.usage.request` / `node.skills.usage`。兼容基线采用现有双方实际交换的名称，用户侧行为依据 current spec。[Relay 契约](../../specs/gateway/relay-protocol.md) · [IM 命令表](../../../apps/im-server/src/node-rpc-contracts.ts)

## 目标状态

同一条产品 RPC 的方法名、入参和结果具有一个双方采用的权威定义。IM ↔ Node 还需约束请求与回包名的对应关系。调用者传错字段、漏实现一个共享命令、处理端返回不符合该命令的结果，开发者应能在仓库类型检查中定位。单侧手写一个错误回包名也应在交付前被阻止。

进程或网络送来的原始数据要经过运行时校验：畸形请求在业务操作前被识别，畸形结果不能被调用方当作成功。契约测试应能区分畸形报文、合法业务失败和当前支持的旧报文。提供方拥有的扩展内容只约束产品实际依赖的部分。具体 schema 表达、处理函数组织和测试位置交给设计。

## 用户侧验收标准（不变性）

用户在 IM 查询节点上的计划、保存配置、从回复创建会话分支。回包携带的是用户操作的结果；错误关联、把不可用解释为空、丢失分支历史，都能直接改变用户看到的结果。

### Requirement: 用户能区分计划列表为空与节点不可用

#### Scenario: 查询在线节点的当前计划

- **WHEN** 用户在 Agent 配置中查看当前计划，节点在线且读取成功
- **THEN** 已有有效计划仍可见；成功读到空列表时显示没有待执行计划。[当前计划契约](../../specs/im/agents-nodes.md)

#### Scenario: 查询尚无快照的离线节点

- **WHEN** 用户查看当前计划，节点离线且尚无可展示的历史快照
- **THEN** 用户能区分本次暂时无法读取和已确认没有计划。已有快照仍按现有规则标示来源。[离线行为](../../specs/im/agents-nodes.md)

### Requirement: 配置变更的确认属于发起该操作的用户请求

#### Scenario: 节点已应用配置，确认前连接中断

- **WHEN** 用户保存配置，节点已应用后断线，随后重新连接
- **THEN** 用户可获知原操作的确认结果；等待期间保留待确认状态，其他请求的回复不能使这次保存显示成功。[配置恢复基线](../archive/refactor-672-im-contract-boundaries/motivation.md)

### Requirement: 从已完成的回复创建分支后可以继续对话

#### Scenario: 在源单聊的较早回复处分支

- **WHEN** 用户从一条已完成的 Agent 回复创建分支，并在新单聊接着问该回复以前讨论过的事
- **THEN** 新单聊展示截至所选回复的历史，Agent 能沿用该处的上下文继续回答。源单聊在分支点之后的消息不会出现在分支中，分支里的后续对话也不会回流到源单聊。[IM 分支契约](../../specs/im/conversations-messages.md) · [Gateway 分支契约](../../specs/gateway/relay-protocol.md)

## 影响范围

第一部分覆盖 IM 主动向 Node 请求并等待回包的全部命令。第二部分覆盖 `packages/personal-assistant` 通过运行时端口实际使用的产品 RPC，包括调用者、透传该调用的 Node 适配层和 integration 的处理端。单向通知、其他 relay 事件以及 integration 私有方法不计入本次 RPC 的覆盖分母。共享契约沿用 `product-contracts` 的职责，DSH 对象继续由 integration 持有。[跨包职责](../../../SPEC.md)

## 迁移与回滚策略

按上述两部分逐步迁移，每批同时对齐调用端与实现端。保留现行报文名称、请求关联、可缺省字段和已有错误语义；用实际支持版本的合法请求与回包确认 IM 与 Node 分开升级时仍可互通。协议字段若需改变产品语义，应另行对齐。此次重构不涉及持久化数据转换，出现兼容回归可回退对应批次，原有配置及会话仍可继续使用。

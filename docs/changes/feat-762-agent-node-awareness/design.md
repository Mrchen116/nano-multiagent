# feat-762 · 群聊 Agent 识别执行节点与本地文件归属

> 对齐 [首文档](spec.md)，基线 `480436600`。

## Changelog

## 现状分析

- Node 的 `Configuration.runtime` 用本地配置组装 `AgentConfiguration`，DSH integration 在产品身份段向 root Agent 提供自身名称与 ID。Node 已有用于注册的设备 ID 与名称，文件工具在当前执行环境的工作区中运行。[Node 配置](../../../apps/node/src/configuration.ts) · [身份段](../../../packages/dsh-integration/src/agent-config.ts)
- IM 按 Agent profile 的节点归属投递。普通 Agent 的群消息已有成员和 mention 标签。普通与 Global root 都注册 `conversations`，并经已认证的 `Work.query` 查询成员。普通模式沿用当前工具开关，Global root 将该工具作为固定能力。[普通群聊](../../../packages/personal-assistant/src/single-thread.ts) · [工具注册](../../../packages/dsh-integration/src/global-mode.ts) · [查询](../../../apps/im-server/src/work.ts)
- 设备名已有产品投影，优先使用设备别名。联系人公开投影隐去了个人助手的设备字段。以既有设备可见性为上限。复用既有受保护会话附件、Agent 图片交付和可访问链接。[设备名与可见性](../../../apps/im-server/src/contacts.ts) · [附件访问](../../specs/im/conversations-messages.md#requirement-im-托管聊天附件按会话成员关系读取)

## 关键决策

1. **在既有产品身份段说明自身节点和本地路径语义。** Node 将配置中的节点 ID 和名称作为运行配置传入 DSH integration。新请求的 root Agent 看到简短可信的自身身份与协作规则，规则随系统提示保留。节点信息来自平台配置，不从消息正文、hostname 或 cwd 推断。无节点配置的非产品运行保留现有行为。
2. **普通与 Global root 都按需调用 `conversations(info)`。** 普通 root 用 `target="current"`，宿主从 session binding 解析为该群；Global 使用 Inbox 提供的来源 target。普通 Agent 若关闭查询工具，仍有多机文件规则，无法确认归属时走共享副本。消息 relay、Inbox、历史和会话列表沿用现有载荷。
3. **IM 按请求方生成相对关系。** 仅在 Agent 已加入的原生群聊详情中扩展 Agent 成员。字段 `execution_node` 形如 `{relation: "same" | "different" | "unknown", name?: string}`。以节点 ID 比较，展示名用于辨认。自身身份可显示自己的配置 ID 和设备名，同伴信息限于相对关系与获准公开的设备名。

## 接口、数据流与 Context 生命周期

1. Node 从注册使用的 `node_id`、`node_name` 构造可选的 `executionNode`，经 `AgentConfiguration` 交给 DSH integration。创建或恢复 root 时，在 `agent/created` 中选出历史配置之后，把当前 `desired.executionNode` 覆盖到执行配置，再组装产品身份段。历史分支保留原有模型、工作区等选择，当前节点身份取自本次启动的 Node。名称缺失时自身身份仍可使用当前配置的节点 ID。普通子 Agent 和内部 work fork 沿用原有工具限制。
2. 模型公开调用的 `conversations(info)` 由宿主在现有 `conversation.query` 请求中标记需要节点投影。普通模式仅为该 action 解析 `target="current"`，按已验证的 session binding 取会话 ID。IM 在现有请求者身份、PA 来源授权及会话访问验证之后，额外要求查询 Agent 本身是目标原生群聊的有效成员。仅可公开浏览或通过 PA 观察权限访问的群照常返回已有成员字段。Inbox 内部取标题、发送审核和 Dreaming 历史查询沿用原调用形状。
3. IM 用有效 Agent profile 与同 owner 的节点记录确认归属。对跨 owner 普通公司 Agent，沿用公开联系人设备名的可见范围，包括请求方 owner 具备有效公司访问资格、对方 Agent 可见且仍可用。同 owner 的个人助手沿用该 owner 的设备管理可见性。其他 owner 的个人助手和缺少有效绑定或设备查看资格的成员返回 `unknown`，无设备名。优先用设备别名，其次用登记的设备名。候选名与节点 ID 相同时省略该名，避免把注册回退值当作公开设备名。设备离线仍可返回已知归属。保留现有成员身份和 mention 字段。
4. 查询返回当前设备关系。模型需要在本次任务中使用路径时取最新结果，查询失败、缺字段或最新结果未知时按未知处理。当前关系不追溯文件产生时的节点。历史文件归属无从确认时，请同伴重新提供可读副本。旧工具结果可随会话恢复，按旧观察解释。升级后旧 IM 返回缺字段，模型仍按未知处理。

### 模型看到什么

当前身份段只提供 Agent 名称和 ID。改动后可增加如下内容，文案以真实请求可读性验证。

```text
Your execution node: Air (node-air).
Other Agents in Nano IM can run on different nodes. A path another Agent
shares refers to the environment where the file was produced. Use the
latest group info to check where that Agent runs now. If the node differs
or the path's origin is unclear, ask for a conversation attachment or an
accessible link. For a path known to be local, verify that you can read it.
```

两种模式都从本次 `conversations(info)` 的成员行读取 `"execution_node":{"relation":"different","name":"Mini"}`。工具说明按模式给出当前群的 target 来源，以及字段所指的时点和缺省语义。成员与设备名作为结构化数据交付。

## 本次审查安排

| 问题 | 能力 | 证据 |
|---|---|---|
| Agent 能否辨认自身、同节点、异节点和未知归属，并采取正确的文件交接动作 | Agent Context review、产品旅程 | 读取两种模式首次及查询结果后的真实 provider 输入，对照回复与附件复核。复用一条历史结果曾为 same、当前已变为 different 或 unknown 的连续场景。 |
| 节点投影是否遵循成员、设备和 PA 的可见性，恢复时自身身份是否来自当前执行配置 | Change code review、窄测试 | 核查节点关联、真实调用入口、公开群非成员与跨 owner PA 不获归属、同 owner PA 和可见公司 Agent 获得结果、缺名和离线。用相同显示名且不同 ID 的测试证明比较依据。验证旧配置快照的 root 分支恢复后发出的请求。 |

## 契约层增量

- [Gateway 路由与交付](specs/gateway/routing-delivery.md)
- [IM Agent 和节点](specs/im/agents-nodes.md)

## 风险与回退

相同设备名、离线或未知归属不能证明文件可读。文件访问以实际结果和现有附件权限为准。旧 Gateway 不请求新增投影，新 Gateway 查询未升级的 IM 时按归属未知处理。回退删除新增投影和提示即可。

## 一次性部署迁移

无。

## Runbook for Reviewer

在受审 worktree 用 `./scripts/e2e-up.sh --profile default --wt "$PWD"` 启动隔离 IM 和第一台 Gateway，用 `./scripts/e2e-down.sh --wt "$PWD"` 清理。第一节点用默认的 `e2e-peer` 和 `e2e-global` 分别作为普通与 Global 接收方，启动后确认前者启用了 `conversations`。验收为同一隔离 IM 增加第二个 Gateway，使用独立配置目录、node ID、Agent ID、工作区和运行数据。在该测试配置中使用同一隔离 IM 地址及测试账户，执行 `node apps/node/lib/cli.js bind --config "$peer_config" --auto-bind` 和 `node apps/node/lib/cli.js start --config "$peer_config"`，结束用同一 CLI 的 `stop --config "$peer_config"` 停止并清理第二套运行资源，再停主栈。新建私密测试群并将两种接收方及第二节点的发送方加为成员。开始前核对两个节点在线、模型入口与请求日志可用。

在两个节点各自的 workspace 放置同名相对路径 `artifacts/report.png`，图片分别含明显可辨的不同文字。让第二节点的 A 发它的相对路径，核对第一节点的 B 不读取自己 workspace 下的同名文件。由测试群成员 A 使用已有的 `send_message(local_images)` 将正确 PNG 发到原群，发送工具参数使用 A 本机的绝对路径。普通 B 通过带 @ 的群消息接收图像，Global B 经 Inbox 读取图像。核对两者最终复核的是正确文字，并保留源消息和 provider 请求定位。此 fixture 只证明不同节点下不会把同名相对路径误解成本机文件。同节点及不可读路径另用一条群聊任务核对恢复。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 群聊执行节点与文件交接 | 无 | 单组 | Node runtime 配置、DSH 产品身份及查询提示、PA 查询目标、IM 群成员投影 | [reviewer] 核对节点查询、异节点或未知时的文件交接、同节点读取失败后的恢复和共享副本复核。[worker] 验证两种模式的模型输入、已授权群聊投影、旧 root 配置恢复和真实双节点旅程，留下可复核证据。 |

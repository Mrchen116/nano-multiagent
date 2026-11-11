# feat-762 · Gate 2 独立设计审查

## Round 1

- Reviewer target: `/root/design_reviewer`，独立设计审查。源码及首文档以 `5c4442c87`（当轮 `origin/develop`）为准，设计的源码基线 `480436600` 是其父提交。
- review_mode: `full`。
- mode_reason: 首轮审查，覆盖首文档、工作区的 design、两份 delta-spec 和 M1 骨架。
- started_at: 2026-11-11T16:46:00+08:00（分钟近似）。
- completed_at: 2026-11-11T16:52:00+08:00（分钟近似）。
- duration: 约 6 分钟。
- Verdict: **Issues Found**（0 CRITICAL / 6 WARNING）。

### Coverage

- **现状和责任归属。** [Node runtime 配置](../../../apps/node/src/configuration.ts#L86)由 [实际 Node 启动](../../../apps/node/src/main.ts#L163)经 stdio 交给 [DSH Agent 创建入口](../../../packages/dsh-integration/src/index.ts#L313)，[产品身份段](../../../packages/dsh-integration/src/agent-config.ts#L153)可复用。Agent 节点绑定、会话和联系人权限都在 IM server。两个现有消费入口适合共享同一个 IM 投影，`product-contracts` 的运行配置与 relay 类型可承载可选字段，PA 继续负责模型侧组装。将权限规则留在 IM 并复用现有投递和查询，省去新工具、独立索引和 DSH 边界变更。实际普通工具面、设备可见性和历史配置覆盖见 findings。
- **Agent Context（设计模式）。** 核对了 [原生 relay 构造](../../../apps/im-server/src/messaging.ts#L669)和 [普通会话消息组装](../../../packages/personal-assistant/src/single-thread.ts#L152)，以及 [Global 工具定义](../../../packages/dsh-integration/src/global-mode.ts#L54)、[受信 binding 查询](../../../packages/personal-assistant/src/global-agent.ts#L650)、[IM 会话详情](../../../apps/im-server/src/work.ts#L118)。Global 的 target 可从 Inbox 的来源引用获取，宿主从 binding 传递 agent 和 session。两个入口保留成员身份和 mention 供查找及交接。设计尚需明确旧输入和旧工具结果的时效、原路径产生时的节点与当前节点的区别，以及恢复 root 时节点身份的来源。实施证据应观察两个模式的真实出站 provider 输入、Global 查询结果后的下一请求，以及发现项涉及的恢复场景。本轮未启动服务或验证模型行为。
- **用户约束和范围。** 首文档要求按现有权限辨认同节点、异节点和未知，文件交接沿用现有能力。设计覆盖普通与 Global 的主体路径，原生群和外部 shadow 可分别以会话类型、外部来源限定。Dreaming 与 Inbox 的内部操作也会复用 `info`，应按实际消费者裁定投影。无 UI 设计决定和平台特有交互，无原型或视觉 must-match。两项新增契约的 canonical target 分属 Gateway 模型行为及 IM 授权数据，适用 ADDED，无 MODIFIED Scenario 待保留。Gateway 文件复核行为覆盖缺口见 R1-W6。无一次性迁移。
- **Milestone 和旅程。** 单个 M1 及目录骨架与改动范围匹配，没有并行写入冲突。后续结合窄测试、真实 provider 输入与原生聊天结果的取证方法适当，选定附件与双节点文件的验证前置需要落到实际可读、可区别的 fixture。当前审查为静态设计审查，运行验收和资源回收随实施执行。

### 历史问题闭环

首轮无历史问题。

### Issues

**R1-W1 — 设备名可见性规则需要指定权威入口及具体边界。** [设计](design.md#接口数据流与-context-生命周期)说沿用请求方 owner 的现有设备目录规则，同时引用公开联系人投影。两者结论不同，[电脑管理](../../../apps/im-server/src/control-routes.ts#L115)按 owner 过滤，[联系人](../../../apps/im-server/src/contacts.ts#L7)可返回获批公司成员可见的其他 owner 普通公司 Agent 的设备名，却对 PA 统一省略。current [公开 Agent 资料](../../specs/im/agents-nodes.md#scenario-公开-agent-资料与配置分开)也明定跨 owner 公司 Agent 的显示名。把 owner-only 规则套给所有同伴会使常见跨 owner 协作得到 unknown。直接复制公开联系人的可见性又不能兑现同 owner PA 的特例。另有 [Gateway 注册](../../../apps/im-server/src/gateway.ts#L309)和 [Node 注册调用](../../../apps/node/src/main.ts#L232)以节点 ID 回退为 node_name，直接复用 COALESCE 的显示名可通过 name 下发本设计禁止下发的同伴节点 ID。明确普通/Global 共用的权限判定，包括跨 owner 的普通 Agent、同/异 owner PA、公开群只读权限以及名回退规则。先确定可见性，再给 relation 和可选展示名，并补相应的拒绝测试。

**R1-W2 — `Work.query(info)` 的消费方比设计列出的范围更广。** [设计现状和关键决策](design.md#现状分析)将普通模式描述为缺少 Global 的完整查询工具，并把普通模式的节点信息限定在 relay。实际上普通 root [挂载 GlobalMode](../../../packages/dsh-integration/src/agent-config.ts#L125)，[注册工具时只移除 Inbox](../../../packages/dsh-integration/src/global-mode.ts#L54)，Node 的 [product.call](../../../apps/node/src/main.ts#L509)和 [Work.query](../../../apps/im-server/src/work.ts#L118)允许普通 root 查询。Global 的 [Inbox read 和 Dreaming](../../../packages/personal-assistant/src/global-agent.ts#L706)也会调用 info。若实现只按 action 添字段，普通 root 也能通过该工具获取当前投影，Dreaming info 也会收到字段。请明确哪些消费者有意获得该字段，明确普通工具面的当前行为和此次变化，并在共用接口保留必要的 mode 或现有 memory 范围条件。Inbox 现有调用只取 name，保留这一消费范围即可。

**R1-W3 — 模型需要能判断节点事实的有效时点。** [设计模型样例](design.md#模型看到什么)给出 bare relation，并承诺按本轮 roster 行动。现有 [普通组装](../../../packages/personal-assistant/src/single-thread.ts#L156)将每条 roster 作为内容放入可恢复会话，恢复和批量 pending 提交会出现多份 roster；Global 的 info 结果也随工具历史保留。当本轮节点未知、字段缺失或同伴在发出路径后切换节点，模型可能把旧的 same 或查询到的当前 same 当成旧路径来自本机的证明，进而读到同名异内容文件。明确提示用最新的适用快照覆盖旧结果、当前未知保持未知，并说明当前节点关系只描述投影时刻。在路径来源无法确认时走共享副本恢复。用一条连续的含旧节点事实与当前未知或变更的输入验证选择。

**R1-W4 — 恢复配置未区分当前 Gateway 身份和历史执行选择。** [设计](design.md#接口数据流与-context-生命周期)称配置刷新及原生 session 恢复使用运行期配置，拟把 executionNode 放在 AgentConfiguration 内。[DSH 创建](../../../packages/dsh-integration/src/index.ts#L313)实际先由 [NativeHistory.configuration](../../../packages/dsh-integration/src/history.ts#L103)选历史覆盖，再调用 attachAgent；[聊天历史分支](../../../packages/dsh-integration/src/history.ts#L209)从历史回合拷贝配置供新 branch 使用，同 revision 的 branch 恢复也会直接返回覆盖。仅从 scope.config 读取会让已有历史分支遗漏当前节点，或在历史节点身份不同的情况下读取旧值。明确新运行的产品身份始终取自当前 Node 事实，保留历史执行选择及原有记录；验收覆盖一个有旧配置快照的产品 root 分支或恢复场景。此处与内部 worker fork 的权限限制是两条独立路径。

**R1-W5 — 真实双节点验收的文件隔离及共享副本前置未落实。** [Runbook](design.md#runbook-for-reviewer)在同一主机用不同工作区启动两个 Gateway，但两个工作区不会为同一绝对路径提供不同内容。明确使用同一相对路径及两个不同 cwd 的哨兵内容，或指定具备隔离绝对路径的资源。Runbook 也需要选定已知能被接收 Agent 消费的共享副本。产品的 [普通输入](../../../packages/personal-assistant/src/single-thread.ts#L163)只把图像附件作为模型图像处理，[Global Inbox](../../../packages/dsh-integration/src/global-mode.ts#L75)只载入支持的图像正文，[历史工具](../../../packages/dsh-integration/src/global-mode.ts#L58)区分附件描述和读到内容。任意报告文件即便能由人上传，也不能据此假定两个 Agent 都能读取。请指定可复用的受保护图像附件或事先验证可从接收 Agent 读取的链接、授予权限的角色和实际复核结果。验收资源缺口独立于产品设计可行性。

**R1-W6 — Gateway delta 缺少文件恢复与复核结果。** [Gateway delta](specs/gateway/routing-delivery.md#scenario-复核另一-agent-的本地文件)只描述同节点时判断能否继续，以及异节点或未知时请求材料。[首文档](spec.md#requirement-群聊-agent-根据文件所在环境协作)还要求同节点无法读取时请求可访问副本，以及获得有权读取的材料后基于实际内容复核。合并后 canonical contract 会丢失这两个明确用户结果。请在 Gateway delta 补齐并让 M1 的 reviewer 结果直接对应。

### Recommendations

无。

### Author Resolutions

- **R1-W1 · accepted.** 设计「接口、数据流与 Context 生命周期」明确公司 Agent、同 owner PA、其他 owner PA、公开群非成员与设备 ID 回退的规则，并加入窄验证覆盖。
- **R1-W2 · accepted.** 核实普通 root 的注册与宿主查询链。两种模式共用已启用的 `conversations(info)`，普通模式用会话 binding 解析 current。仅模型的群详情查询请求节点投影，其他内部消费者沿用原调用。
- **R1-W3 · accepted.** 去掉 relay 节点快照。工具提示要求查当前群详情，说明当前归属的有效时点和缺省语义，历史路径来源未知时请求可读副本。验收包含旧 same 与当前 different 或 unknown 的连续输入。
- **R1-W4 · accepted.** 在历史配置选取之后显式以当前 Node 配置覆盖执行节点字段，并在验收中覆盖使用旧快照恢复的产品 root。
- **R1-W5 · accepted.** Runbook 指定独立 cwd 的同名相对路径和不同文字 PNG，发送方用既有群聊图片交付，接收方分别走普通图像输入与 Global Inbox。
- **R1-W6 · accepted.** Gateway delta 和 M1 补入同节点读取失败后的恢复及基于共享副本内容完成复核。

## Round 2

- Reviewer target: `/root/design_reviewer`，继续独立设计审查。源码基线 `5c4442c87`，复审的 design / Gateway delta / IM delta blob 分别为 `fad723f284` / `505251273c` / `0f8c5b2ea2`。
- review_mode: `full`。
- mode_reason: 普通模式从 relay 快照改为共用查询，改变核心 Context 数据流、共享查询边界与 M1 的实施范围。
- started_at: 2026-11-11T16:55:04+08:00。
- completed_at: 2026-11-11T16:57:00+08:00（分钟近似）。
- duration: 约 2 分钟。
- Verdict: **Issues Found**（0 CRITICAL / 1 WARNING）。

### Coverage

- **需求与架构。** 首文档的自我定位、同伴识别和共享副本协作目标保持一致。由 Node 提供自身事实，IM 依已有会话与设备权限形成成员字段。取消 relay 投影后，两种模式共用 [已有工具](../../../packages/dsh-integration/src/global-mode.ts#L54)、[PA 可信会话 binding](../../../packages/personal-assistant/src/global-agent.ts#L650)和 [IM 访问校验](../../../apps/im-server/src/work.ts#L118)。宿主在模型调用分支 opt in，客户端 schema 只需指明 target 和语义，内部消费者无需改载荷；比同时维护每条 relay 与实时结果更直接。普通模式的可用性受现有开关控制，Global 的查询是 [固定能力](../../../packages/product-contracts/src/capabilities.ts#L59)。
- **Agent Context（设计模式）。** 普通 root 的 `current` 由宿主根据已认证 binding 解析，Global 的 target 来自 Inbox 或现有查询。普通消息已有成员/mention，`info` 返回保留同一身份信息，供选择需交接的成员。新结果与旧结果的关系、查询缺失时的恢复行为和当前节点不能反推历史文件来源已明确。历史配置选择后再覆盖当前节点，可保留历史执行选择并保证本次根提示的设备身份。拟议 provider 证据涵盖两种模式的首请求、查询后请求和恢复。
- **Delta、用户约束与 M1。** Gateway delta 在既有 canonical 目标增加跨节点规则和共享副本复核；IM delta 在既有 canonical 目标增加原生群已加入成员的投影，现有 Scenario 无需改写。仍是单一 M1、无并行冲突、无一次性迁移，也无需要通过原型决定的页面交互。验证方法可观察目标，必验角色准备有一项缺口见 R2-W1。本轮未运行产品或验证 provider 行为。

### 历史问题闭环

| 原问题 | Author Resolution 与本轮证据 | 状态 |
|---|---|---|
| R1-W1 | [接口第 2、3 项](design.md#接口数据流与-context-生命周期)分别定义加入群授权、公司 Agent 与 PA 的设备可见性、有效绑定、节点 ID 回退值省略。与 [公开联系人的投影](../../../apps/im-server/src/contacts.ts#L23)及 [owner 设备范围](../../../apps/im-server/src/control-routes.ts#L115)相符。 | closed |
| R1-W2 | 普通和 Global root 都经模型公开的 `conversations(info)` 请求。PA 在模型分支选择投影，[Inbox 和 Dreaming 调用](../../../packages/personal-assistant/src/global-agent.ts#L706)维持原语义，消息历史与 relay 无字段变更。 | closed |
| R1-W3 | [Context 生命周期第 4 项和提示样例](design.md#模型看到什么)限定查询时点、最新优先和未知语义，历史文件来源不确定时请求共享副本，验收引入旧 same 与新观察冲突。 | closed |
| R1-W4 | [接口第 1 项](design.md#接口数据流与-context-生命周期)在 [历史覆盖选择](../../../packages/dsh-integration/src/history.ts#L103)之后以本次 desired 节点配置覆盖，并安排旧 root 分支真实请求证据。 | closed |
| R1-W5 | [Runbook](design.md#runbook-for-reviewer)选定相对路径冲突与可消费的 PNG，以两条现有图像入口验证可读副本。实际固定阵容和上传参数的额外前置见 R2-W1。 | closed |
| R1-W6 | [Gateway delta](specs/gateway/routing-delivery.md#scenario-复核另一-agent-的本地文件)与 M1 均补齐读取失败的恢复动作和实际副本复核。 | closed |

### Issues

**R2-W1 — 固定日常阵容缺少必验的普通接收 Agent。** [Runbook](design.md#runbook-for-reviewer)把普通 B 和 Global B 都安排在第一节点，只额外准备第二节点的发送方 A。[日常配置脚本](../../../scripts/e2e_daily.py#L53)以 `e2e-global` 为基础创建 P/E/Q，[固定角色](../../../config/e2e/daily/team.yaml)未覆盖其 [global 模式](../../../config/e2e/gateway.yaml#L73)，另一个 PA 也是 Global。只按当前 runbook 无法完成普通 B 的首次请求和图像复核。请在第一节点补建一个 `single_thread` B 并确认 `conversations` 已启用，或在隔离阵容内明确等价的角色布置。现有 [图片上传入口](../../../apps/node/src/screenshot-upload.ts#L21)要求 `local_images` 使用发送端绝对路径，需在 runbook 明确它与故意放到群正文中的相对路径的区别，以便实际走通共享副本。

### Recommendations

**R2-R1。** [IM delta 的离线 Scenario](specs/im/agents-nodes.md#scenario-归属已知但设备离线)可明确显示名只在已知且允许显示时给出，保持与上文及设计的节点 ID 回退省略一致。

### Author Resolutions

- **R2-W1 · accepted.** Runbook 改为用 default 栈的 `e2e-peer` 与 `e2e-global`，在同一隔离 IM 注册另一 Gateway 作为发送方，并说明发给群成员的是相对路径，上传调用传发送端绝对路径。
- **R2-R1 · accepted.** IM delta 明确已知关系与可选设备显示名各自的返回条件。

## Round 3

- Reviewer target: `/root/design_reviewer`，继续独立设计审查。源码基线 `5c4442c87`，复审的 design / Gateway delta / IM delta blob 分别为 `04f4803009` / `505251273c` / `e66f73adc2`。
- review_mode: `closure`。
- mode_reason: 本轮修改限于验收角色及附件前置、离线 Scenario 的局部消歧。核心接口、模型 Context、授权、Gateway delta 和 M1 范围保留 Round 2 的证据。
- started_at: 2026-11-11T16:58:00+08:00（分钟近似）。
- completed_at: 2026-11-11T16:58:25+08:00。
- duration: 约 25 秒。
- Verdict: **Approved**（0 CRITICAL / 0 WARNING）。

### Coverage

本轮检查了设计验收前置及离线设备显示名契约。首文档、设计核心及 Gateway delta 沿用 Round 2 覆盖（retained_from: Round 2）。运行时和模型行为留待实施后的验收。本轮为静态设计审查，未启动服务。

### 历史问题闭环

| 原问题 | Author Resolution 与本轮证据 | 状态 |
|---|---|---|
| R2-W1 | [Runbook](design.md#runbook-for-reviewer)使用 `default`。本机对该 worktree 的 `dev_host.py e2e-config` 解析为 [仓库测试配置](../../../config/e2e/gateway.yaml#L19)。该配置中 `e2e-peer` 为 `single_thread`，共享工具列表包含 `conversations`，`e2e-global` 为 Global。[启动脚本](../../../scripts/e2e-up.sh#L334)对 default 同步现有工具且只对 daily 重建固定阵容。Runbook 要求确认普通工具启用、在隔离私密群添加角色，并区分群正文的相对路径和 [上传入口所需的发送端绝对路径](../../../apps/node/src/screenshot-upload.ts#L21)。 | closed |
| R2-R1 | [IM delta](specs/im/agents-nodes.md#scenario-归属已知但设备离线)保留离线时的已知节点关系，明确显示名在存在且可见时附带，与可选字段和 ID 回退省略一致。 | addressed |

### Issues

无。

### Recommendations

无。

## Round 4

- Reviewer target: `/root/design_reviewer`，继续独立设计审查。实现基线 `88cc20b16`。复审的首文档 / design / Gateway delta / IM delta blob 为 `11bf7fefe3` / `a049a1d468` / `a0c18af709` / `11bd5776e7`。
- review_mode: `delta`。
- mode_reason: 用户收敛了 `conversations(info)` 的一个模型可见字段。影响范围是查询成员结果的形状、节点标识的披露边界及判断依据。两种模式的调用入口、宿主权限、M1 验收旅程及依赖范围均保留。
- started_at: 2026-11-11T17:10:20+08:00。
- completed_at: 2026-11-11T17:11:15+08:00（近似）。
- duration: 约 55 秒。
- Verdict: **Approved**（0 CRITICAL / 0 WARNING）。

### Coverage

- **模型可见身份。** 已修订的首文档记录用户去掉 `relation` 的决定与重名问题。Node 的 [runtime 配置](../../../apps/node/src/configuration.ts#L103)使用注册时的配置 ID，[产品身份段](../../../packages/dsh-integration/src/agent-config.ts#L161)将它明确交给 root。IM 的 [成员查询](../../../apps/im-server/src/work.ts#L109)从有同 owner 节点记录的 Agent profile 获取同一命名空间的 ID。设备显示名来自别名或登记名称，无唯一约束。测试方案分别覆盖同名异 ID、同节点、缺字段及可用节点无名称。
- **ID 语义与权限。** [默认初始化](../../../apps/node/src/bootstrap.ts#L26)把随机设备 ID 与主机显示名分别存储，[IM 以 node_id 作主键](../../../apps/im-server/src/schema.sql#L101)。运行认证校验 [独立 token 哈希](../../../apps/im-server/src/identity.ts#L634)，[设备换绑](../../../apps/im-server/src/identity.ts#L950)轮转凭据与 epoch。此 ID 是同一 IM 内的稳定节点标识，具有跨结果关联同一设备的能力。当前公开联系人投影的跨 owner 范围曾提供普通公司 Agent 的名称，新增 ID 的披露仅在受授权的已加入原生群模型查询中发生。此前 R1-W1 的可见性判定仍适用，R1 对 ID 经 name 意外下发的判断由本轮用户认可的显式 id 取代。同/异 owner PA、未加入公开群、Dreaming、内部查询和失效 profile 均沿原门控；缺权限或有效绑定时省略整个对象。与 [实际已实现的过滤边界](../../../apps/im-server/src/work.ts#L210)对照，变更可以限定在字段投影和工具说明。
- **Context 与契约。** 对照 [普通/Global 共用的模型调用分支](../../../packages/personal-assistant/src/global-agent.ts#L731)，新形状能让模型比较本次 root 提示和本次成员结果。最新查询仍只说明当前归属，历史路径来源仍需独立判断。两份 ADDED delta 与首文档和设计一致，保留文件读取失败恢复及共享副本复核。设计已更新，受审实现基线仍返回旧 relation，实施时需把成员投影和模型工具说明同步切换。未运行候选实现或 provider 行为。

`retained_from: Round 2`：目标解析、可信请求者身份、历史 root 当前节点覆盖、路径时效与交接、权限查询点及单 M1 范围未变。`retained_from: Round 3`：默认验收角色、隔离双节点与附件前置未变，离线设备名仍可选。

### 历史问题闭环

R3 无开放项。R1-W1 仍 closed，旧报告中限制模型端获取节点 ID 的判断由本轮显式节点身份决策取代。

### Issues

无。

### Recommendations

**R4-R1。** 工具说明可直接写「用 `execution_node.id` 与自身节点 ID 比较，名称可重名。缺少可用 ID 时按未知处理」，便于沿同一语义读取旧工具结果和混合版本响应。无需双写字段或增加迁移。

### Author Resolutions

- **R4-R1 · accepted.** `conversations` 工具说明明确使用最新的同伴节点 ID 与自身 ID 比较，提示名称可重名，并将缺少节点 ID 或查询失败解释为归属未知。
- **retained_from: Round 4.** 根据用户反馈，自身节点提示将同一 ID 和名称分别标注为 `Execution node ID` 和 `Execution node name`。身份来源、查询结果与可见性沿用本轮审查。

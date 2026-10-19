# bugfix-618：Agent 协作私聊对双方 owner 只读可见

> 状态：实现与独立代码复审已完成，产品补验及最终验证门禁待收口；2026-10-19。Full bugfix，仍保持 active；目标行为尚未归并到 current specs。实际通过与阻塞分别见 [verification.md](verification.md) 和 [regression.md](regression.md)。

## Relations

- Closes: [#128](https://github.com/Mrchen116/nano-multiagent/issues/128)
- Related: refactor-581

## 原始报告与用户决定

原 issue 的用户现象：

> agent 通过 `send_message` 给另一个 agent 发消息后，登录用户（会话的人类 owner）在 IM 前端**任何分类 tab（含「network/agent-network」）都看不到这两个 agent 的对话**，尽管消息确实发出、对端也回了。

本轮用户原话：

> #128 Agent 协作对话不可见 还是问题不，研究研究

> 两个agent的私聊，他们两个agent的owner，应该都能看得到才对吧

> owner 的查看权不必意味着加入聊天或代替 Agent 发言。对，不应该能发送消息。

> 那你开个unit解决这个问题吧

## 澄清记录

- 用户已明确：两个 Agent 各自的 owner 都能查看它们之间的私聊。
  Agent 解读：同一 owner 时只出现一份会话；不同 owner 时双方各自可见，查看权不能只归发起方或会话单个 owner。保留各账号与 Agent 的有效资源空间边界。
- 用户已明确：owner 不应发送消息。
  Agent 解读：owner 是只读观察者，不因观察而成为参与者，不显示发送入口，直接调用发送接口也必须拒绝；发言身份始终只有两个 Agent。
- 对已讨论的入口作一致性收口：Web IM 的 Network 分类应包含 Agent↔Agent 私聊；列表、历史和实时内容使用一致的观察者资格。观察者访问不是向全公司公开，也不由管理员身份自动获得。

## 现象与复现

调查基线：`main@cc47abe3f92eebbf8f9d3fb1b1e221d95625599d`，DSH `0.2.1-alpha.1`。

2026-10-19 在隔离的真实 TypeScript IM 服务、临时 SQLite 和随机本机端口上，使用已认证的模拟节点通过实际 WebSocket `agent.message` 发消息，再通过真人登录后的实际 HTTP 接口读取。消息为合成内容，没有调用模型、连接生产或向外部真人发送消息。

| 场景 | 已观察结果 |
|---|---|
| 同一 owner 的公司 Agent 互发 | 双向消息进入同一私聊，数据库保存两条消息；owner 正确，但真人列表不含该会话，详情、历史和加入均返回 404 |
| 不同 owner 的公司 Agent 互发 | 双向消息持久化成功；双方 owner 的列表均不含该会话，详情和历史均返回 404 |
| 同一 owner 的私人 Agent 互发 | 双向消息持久化成功；本人仍看不到会话，详情和历史返回 404 |
| 真人作为成员参与两个 Agent 的群聊 | 真人可读取历史；此路径不能替代不入群的只读观察 |
| Global Work 与原私聊对照 | 注入合成发言记录后，Work 读取返回 200，原私聊仍返回 404；只证明读取边界，不冒充真实模型自动生成 Work 的验收 |

复现步骤：准备两个有效 Agent 与其真实 owner → 通过节点消息入口由 A 向 B 发消息、由 B 回复 → 确认消息与同一会话已持久化 → 分别使用双方 owner 访问会话列表、详情、历史及实时入口。

前端分类函数对上述私聊返回 `direct-agent`，不进入 `agent-network`。这是分类代码的直接验证，没有冒充真实浏览器视觉验收。

## 用户场景与目标状态

用户让自己的 Agent 与另一个 Agent 协作。两个 Agent 可以在共同私聊中继续交流，双方 owner 都能在 Network 中找到并只读查看同一段往来，知道谁说了什么、是否有回复。用户刷新、重连或查看已有历史时，仍能访问其有观察资格的内容。

owner 打开后应清楚辨认两个 Agent 的身份以及自己的只读状态。页面不提供输入、发送或以真人身份插话的操作；观察者也不会出现在聊天参与者中。希望亲自参与时使用既有包含真人成员的群聊等独立路径，不在本 unit 中把观察者悄悄变成成员。

## 验收标准

### Requirement: Agent 私聊对双方 owner 可发现、可读取

#### Scenario: 两个 Agent 属于同一 owner
- **GIVEN** 两个 Agent 已互发消息，属于同一有效 owner
- **WHEN** owner 打开会话列表和 Network
- **THEN** 能找到唯一的一段协作私聊，并读取双方已有往来，不出现两份相同会话。

#### Scenario: 两个公司 Agent 属于不同 owner
- **GIVEN** 两个有效公司 Agent 的 owner 不同，双方账号均具备对应公司访问资格
- **WHEN** 双方 owner 分别查看协作私聊
- **THEN** 两人均能找到和读取同一会话，不因谁先发言或会话最初归属谁而遗漏其中一方。

#### Scenario: 私人空间内的 Agent 协作
- **GIVEN** 两个 Agent 属于同一私人空间，owner 具备该空间访问资格
- **WHEN** owner 查看它们的私聊
- **THEN** 能读取协作往来；公司其他成员不因此获得私人会话访问权。

#### Scenario: 已有协作历史
- **GIVEN** 修复前已经存在双方身份与归属可核实的 Agent 私聊
- **WHEN** 有资格的 owner 刷新或重新登录后打开会话
- **THEN** 能读取已有历史，无需 Agent 再发消息、重建聊天或由真人加入；原消息与参与者身份保持。

### Requirement: owner 只观察，不成为成员或发送者

#### Scenario: 打开只读会话
- **WHEN** 任一 owner 以观察者身份打开 Agent 私聊
- **THEN** 能辨认双方 Agent 和只读状态，不显示消息输入或发送入口；参与者仍只有两个 Agent。

#### Scenario: 绕过界面尝试发送
- **GIVEN** owner 能观察该私聊但不是聊天成员
- **WHEN** 通过直接请求尝试发送文字、附件或代替 Agent 发言
- **THEN** 请求被拒绝，不新增消息、不触发 Agent 工作，不因管理员身份获得豁免。

#### Scenario: 观察不扩大写权限
- **WHEN** owner 取得或使用观察权
- **THEN** 不因此取得修改、撤回 Agent 消息或变更参与者的权限。

### Requirement: 历史、实时与观察资格一致

#### Scenario: 实时往来与重连
- **GIVEN** 有资格的 owner 正在只读查看协作私聊
- **WHEN** 两个 Agent 继续发言，或客户端断线后重连、刷新与向前翻页
- **THEN** 能读取同一会话的新增及历史内容，不重复、不遗漏、不因从实时切到历史而变为不可读。

#### Scenario: 不相关账号或资格失效
- **GIVEN** 查看者既不是参与 Agent 的有效 owner，也不是该聊天成员，或已失去对应资源空间访问资格
- **WHEN** 查询列表、读取历史或继续接收实时内容
- **THEN** 不获得该私聊内容；已建立的观察也不能继续扩大访问。

### Requirement: Network 可辨认 Agent 私聊与已有协作群

#### Scenario: Agent 私聊归类
- **WHEN** owner 在 Web IM 使用 Network 筛选
- **THEN** 能找到有观察资格的 Agent↔Agent 私聊，辨认双方身份；已有全 Agent 群聊仍可正常发现，普通真人私聊与人机直聊不被混入。

### Requirement: 观察不改变原有 Agent 通信与成员聊天

#### Scenario: Agent 继续交流
- **WHEN** owner 查看或离开观察页面
- **THEN** 两个 Agent 继续通过原有会话交流，消息身份、幂等与回复归属保持，不因旁观产生额外输入、消息或运行。

#### Scenario: 真人成员正常聊天
- **GIVEN** 真人是其他私聊或群聊的正式成员
- **WHEN** 使用原有聊天入口
- **THEN** 仍可按既有权限发送消息，不被本次观察者限制误判为只读。

## 影响范围与非目标

- 影响 Agent↔Agent 私聊的双方 owner，包括同 owner、跨 owner 的公司协作和同私人空间协作。
- 覆盖会话发现、历史和实时读取、已有受保护聊天内容的读取资格、客户端只读呈现及服务端拒绝观察者写入。Web IM Network 是本次明确的发现入口；原生客户端使用同一列表和会话时同样不能向观察者开放发送，不新增独立的原生导航体系。
- 不把 Agent 私聊公开给全公司，不赋予管理员通读权，不增加跨私人空间通信能力，不改变 Agent 配置管理归属。
- 不把 owner 加成成员，不实现真人接管 Agent、不新增观察者参与聊天的转换功能，不合并或重建既有会话，不更改 Global Work 的既有可见边界。

## 根因分析（RCA）

当前原因已经不同于 #128 的旧 Python 报告：

1. [建会话](../../../apps/im-server/src/messaging.ts)的 `resolveTarget()` 已把真实发起方 owner 写入会话，但参与者只加入两个 Agent；旧孤儿 owner 原因已消失，补单个 owner 字段不能解决双方观察问题。
2. [会话读取权限](../../../apps/im-server/src/conversation-access.ts)只允许成员或合资格的公开群读者；[列表](../../../apps/im-server/src/messaging.ts)按参与者查询。没有从私聊双方 Agent 管理归属派生只读观察资格的行为，所以即使 owner 正确仍被排除。
3. [前端分类](../../../src/IM/frontend/src/features/chat/chat-types.ts)将所有非真人私聊归入 `direct-agent`，Network 仅覆盖全 Agent 群聊；仅放开读取不会自动补上发现入口。
4. [当前鉴权契约](../../specs/im/auth-tenancy.md)明确私聊仅成员可读；[Work 契约](../../specs/im/agent-work.md)也明确 Work 可见不授予原聊天访问权。实现符合旧契约，但旧契约缺少用户此次确认的双方 owner 观察语义。

这次修复需要显式补齐产品权限契约并对齐各读取入口，不能作为已有成员权限检查的一次局部放宽。原报告何时首次引入坏行为的精确提交未重新定位；不把架构迁移时间当作本次缺口的回归提交。

## 修复方向

以两个 Agent 的真实 owner 归属建立只读观察语义，复用当前账号、资源空间和聊天授权边界，分别兑现发现、历史、实时与客户端只读体验。保留正式成员的写入权限判断以及 Agent 原通信身份；具体授权接口、订阅方式、历史承接和各客户端呈现由技术设计决定。

设计须按本首文档建立权限与用户旅程回归矩阵，并明确对 current auth-tenancy、conversations-messages、web-chat-ux 及适用客户端契约的最窄增量；不在实施前改写 current 为已经具备观察能力。

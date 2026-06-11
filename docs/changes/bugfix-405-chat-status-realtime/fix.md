# bugfix-405: Chat 页节点与 Agent 状态不实时更新

## Relations

- Related: feat-340
- Closes: #7

## 原始报告

> $change-spec-author 解决#7

> GitHub Issue: https://github.com/Mrchen116/nano-multiagent/issues/7
>
> ## 问题描述
>
> Gateway 断线后，chat 对话页的 agent 状态角标（以及对话列表的 node 状态）仍然显示绿色（online），不会自动切换为离线状态。只有手动刷新页面才能看到正确状态。
>
> ## 根因分析
>
> **IM 服务端行为正确**：Gateway WebSocket 断线时 `disconnect()` 被调用，`_broadcast_status_change` 向用户 SSE 流推送 `node.status_changed` 事件。
>
> **前端问题**：
>
> - `nodes-page.tsx`（设置 → 节点页）通过 `useEffect` 订阅 SSE `node.status_changed` 事件，**实时更新** ✅
> - `chat-workspace-page.tsx`（聊天页）的 `nodesQuery` 和 `agentsQuery` 只在页面挂载时拉取一次，**没有订阅任何实时事件** ❌
>
> 相关代码：`src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx:127`
>
> ```ts
> const nodesQuery = useQuery({
>   queryKey: ["chat-v2", "nodes"],
>   queryFn: fetchNodes
>   // 无 refetchInterval，无 SSE 订阅
> });
> ```
>
> 对比：`src/IM/frontend/src/features/settings/nodes/nodes-page.tsx:72` 的正确做法：
>
> ```ts
> useEffect(() => {
>   // 订阅 SSE node.status_changed → 实时更新 rows
> }, [...]);
> ```
>
> ## 修复方向
>
> 在 `chat-workspace-page.tsx` 中订阅 SSE 的 `node.status_changed` 和 `agent.status_changed` 事件，收到后调用 `queryClient.invalidateQueries({ queryKey: ["chat-v2", "nodes"] })`，参考 nodes-page.tsx 的实现。
>
> 备选：给 `nodesQuery` 加 `refetchInterval: 30000`（轮询，次优方案）。

## 澄清记录

- Q1: 修复范围是否覆盖 Chat 页所有状态展示，包括会话侧栏头像状态点、会话头部 Node chip、群聊 mention 候选状态？
  A(原话): 对
  Agent 解读: Chat 页内所有由节点或 Agent 在线状态驱动的展示必须保持一致，不能只修其中一个位置。
- Q2: Gateway 恢复连接时，Chat 页是否也应自动从离线切回在线？
  A(原话): 对
  Agent 解读: 状态同步必须双向覆盖断线与重连，用户不需要刷新页面。
- Q3: 状态变化到达 IM 后，Chat 页应多快完成更新？
  A(原话): 这个你定
  Agent 解读: 采用推荐口径：状态事件到达浏览器后 1 秒内完成更新，不把 Gateway 断线检测本身的耗时计入前端响应时间。

## 现象 / 复现

### 用户场景

用户保持 Chat 页打开，并在会话侧栏、当前会话头部或群聊 mention 候选中看到 Agent 处于在线状态。
当承载该 Agent 的 Gateway 断线后，设置页会变为离线，但 Chat 页仍保持绿色在线状态；只有刷新页面后才
显示真实状态。Gateway 后续重新连接时也存在同样问题：已打开的 Chat 页不会自动恢复在线状态。

这会让同一个产品页面内多个状态展示与真实运行状态不一致。用户可能继续向已经离线的 Agent 发消息，
也无法从 Chat 页判断 Agent 是否已经恢复服务。

### 复现步骤

1. 登录 Web IM，打开一个与在线 Agent 的 Chat 会话。
2. 确认会话侧栏头像状态点、会话头部 Node chip，以及群聊中的 mention 候选显示在线。
3. 保持页面不刷新，停止该 Agent 所属的 Gateway。
4. 等待 IM 将节点判定为离线。
5. 观察 Chat 页：上述状态展示仍保持在线；刷新页面后才变为离线。
6. 保持页面不刷新，重新启动 Gateway。
7. 观察 Chat 页：状态不会随连接恢复自动切回在线。

### 用户可观察验收

### Requirement: Chat 页实时反映 Gateway 连接状态

#### Scenario: Gateway 断线

- **GIVEN** 用户打开 Chat 页，相关 Agent 当前显示在线
- **WHEN** Gateway 断线，浏览器收到该节点或 Agent 的离线状态事件
- **THEN** 1 秒内，会话侧栏头像状态点、会话头部 Node chip、群聊 mention 候选全部显示离线
- **AND** 用户无需刷新页面或切换路由

#### Scenario: Gateway 恢复连接

- **GIVEN** 用户打开 Chat 页，相关 Agent 当前显示离线
- **WHEN** Gateway 恢复连接，浏览器收到该节点或 Agent 的在线状态事件
- **THEN** 1 秒内，会话侧栏头像状态点、会话头部 Node chip、群聊 mention 候选全部显示在线
- **AND** 用户无需刷新页面或切换路由

#### Scenario: 其他节点状态变化

- **GIVEN** Chat 页同时展示归属不同节点的多个 Agent
- **WHEN** 其中一个节点的连接状态变化
- **THEN** 只有该节点及其 Agent 的状态展示发生变化，其他节点和 Agent 的展示保持原状

### 范围与非目标

- 本 unit 覆盖 Chat 页所有节点/Agent 在线状态展示，保证同页状态一致。
- 本 unit 覆盖离线与恢复在线两个方向。
- 本 unit 不改变 IM 判定 Gateway 在线、断线或心跳超时的规则。
- 本 unit 不改变 Settings Nodes / Settings Agents 页面当前已经可用的实时状态行为。
- 本 unit 不新增掉线通知、弹窗或消息发送拦截。

## 根因

Chat workspace 在首次打开时分别读取 Agent 与 Node 列表，并从这两份初始快照派生侧栏、会话头部和
mention 候选的在线状态。页面挂载后没有消费 IM 已经广播的 `node.status_changed` /
`agent.status_changed` 状态事件，也没有其他刷新机制，因此初始快照在整个页面生命周期内保持陈旧。

IM 后端状态生产链路不是故障点：Gateway 注册、断开和心跳超时都会更新节点状态，并向对应 owner 的
浏览器用户流广播状态变化。Settings Nodes 与 Settings Agents 页面也已分别消费这些事件，证明事件能够
到达浏览器且现有产品中已有正确的实时更新行为。

#### 原始设计意图

`feat-340` 将 Chat 页的会话头部 Node 状态 chip、侧栏 Agent 状态点和实时 online/offline 状态列为用户
体验的一部分。其后端状态广播由 `feat-340-M10` 建立，Settings Nodes 和 Settings Agents 的消费分别由
`feat-340-M6` 与 `feat-340-M5` 完成。修复必须保留：

- 状态以 IM 广播的节点/Agent 真实状态为准；
- 状态变化按 owner 隔离；
- 一个节点状态变化只影响归属于该节点的展示；
- Chat 页现有消息流、会话导航和 mention 交互行为不变。

#### 缺陷引入点与漏检原因

Chat workspace 的 Agent 初始查询由 commit `19cff9b0` 引入，Node 初始查询由 commit `6f694d74`
补入；两处都只实现了页面加载时的状态快照。后续实时状态工作按页面拆分，只给 Settings Nodes 和
Settings Agents 增加了事件消费者，Chat workspace 没有被纳入对应退出标准。

现有 Chat 集成测试只断言首次请求返回 online 时 Node chip 显示在线，没有覆盖页面保持打开期间的
online → offline → online 状态转换，因此该跨页面消费缺口未被回归测试发现。

## 修复

由实施阶段回填。

## 验证

由实施阶段回填。

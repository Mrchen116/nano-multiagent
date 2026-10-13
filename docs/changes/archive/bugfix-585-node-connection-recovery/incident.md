# bugfix-585: 节点连接恢复、在线状态与断连诊断

## Relations

- Related: refactor-581
- Closes: [#320](https://github.com/Mrchen116/nano-multiagent/issues/320), [#331](https://github.com/Mrchen116/nano-multiagent/issues/331)

## 原始报告与澄清

用户原话：

> https://github.com/Mrchen116/nano-multiagent/issues/320 https://github.com/Mrchen116/nano-multiagent/issues/331 这两个问题是不是可以一个unit帮我一并解决

> 你知道修复后的，理想业务上目标是啥不

对“节点短暂掉线后能自己恢复，用户看到的状态可信，恢复后能继续正常找 Agent 办事”的目标，以及自动恢复、真实离线/上线、正常收发、撤权不恢复和持久诊断的说明，用户确认：

> 很好，符合我的想法。不用额外做“离线时也能提交任务，上线后自动接着办”。开始做吧

Agent 解读：一个 Full bugfix 同时处理连接恢复、状态一致性和可观测性。沿用现有离线发送失败语义，不新增离线队列、补投递或任务恢复承诺。不修改生产部署。

## 现象与复现

#320 记录旧 Python Gateway 的断连诊断缺口：2026-10-02 20:35 发送返回 503，随后自动恢复，缺少可关联的关闭原因。原事故根因仍未知，不预判网络或 Cloudflare。

#331 在 TypeScript 迁移隔离服务复现：注册后超过 90 秒未活动，真实 5 秒检查器关闭节点；Relay 进入 revoked 不再重连，数据库/API 仍为 online。原记录中的休眠时间与断线吻合，但不能据此断言所有断线均由休眠引发。

本次源码基线 main `649e80311` 仍存在该路径。旧 Python 已退役；#320 的业务要求在当前 Channels/Node 实现满足。

## 影响范围

使用 Web IM 和 Node 的用户在睡眠、网络中断后可能持续无法找 Agent 办事，且页面状态误导。当前证据证明连接与状态错误，没有证明数据损坏。自动重连不意味着重新执行或补发不确定的业务帧。

## 根因分析（RCA）

- `apps/im-server/src/server.ts` 的超时扫描调用撤权操作；`gateway.ts` 发 1008，Channels 将其视为终止权限，停止重连。
- 撤权清理先从当前连接表删除记录，close 回调因连接不再匹配而跳过离线持久化及广播。
- `packages/channels/src/index.ts` 只报告通用断连错误，丢弃 close reason/code，重试和注册恢复不形成完整诊断链。
- current `docs/specs/im/agents-nodes.md` 已要求超时离线并向 owner 广播；当前实现偏离契约。现有 Relay 测试只模拟客户端 ACK 超时，未覆盖真实 IM 超时扫描到 Relay 的跨模块链路。不能据此推断历史审查责任。

## 修复方向与验收

### Requirement: 临时掉线可自行恢复
#### Scenario: R1 休眠或网络中断后恢复
- **WHEN** 已注册节点因短暂中断失去连接，随后连接条件恢复且授权仍有效
- **THEN** 无需重启、重新绑定或登录，节点自动上线；用户新发送的消息能由 Agent 接收并回复。

### Requirement: 用户看到的节点状态真实
#### Scenario: R2 离线与恢复反映到页面
- **WHEN** 当前节点断开或心跳过期
- **THEN** API 和已打开页面及时显示离线；发送失败有明确提示，不显示假在线。
- **WHEN** 节点重新注册成功
- **THEN** 页面自动恢复在线；旧连接延迟关闭不会把新连接标成离线。

### Requirement: 撤权仍然有效
#### Scenario: R3 撤销设备或停用账户
- **WHEN** 节点凭据被撤销或所属账户被停用
- **THEN** 节点不可继续收发且不会自动恢复连接，页面显示不可用。

### Requirement: 维护者可以还原中断过程
#### Scenario: R4 断线排障
- **WHEN** 发生心跳超时、远端关闭或连接失败
- **THEN** 维护者仅凭持久日志可以辨认节点、时间、触发阶段、可获的安全错误/关闭原因、重试与退避、注册恢复及中断时长。
- **AND** 日志不包含凭据、含凭据的 URL 或消息正文，正常心跳不逐条输出。

## 非目标

离线提交任务与上线补投递；改造 DSH；恢复旧 Python；全平台日志系统；自动归因网络供应商；生产部署。

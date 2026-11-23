# refactor-783 Gate 2 设计审查

## Round 1

| Metadata | 值 |
|---|---|
| reviewer | Codex 独立 reviewer，gate2_rpc |
| target | develop，产品源码 56b992e83，首文档 6f18ec907，本地 design、三份 delta 和两个 milestone 骨架 |
| review_mode | full |
| mode_reason | 首轮，跨两个进程边界核对需求、接线、兼容与验收 |
| started_at | 2026-11-23T21:29:44+09:00 |
| completed_at | 2026-11-23T21:33:56+09:00 |
| duration | 4m 12s |

### Verdict

**Issues Found**，0 CRITICAL / 4 WARNING。需在实施前收口临时检查回包的命名来源、停用后的 Work 回补、历史权限拒绝的生效条件和两种空回执。

### Coverage 与证据

- **共享契约的职责。** 两张有限表和方法专属 handler 对应 motivation 的错方法、错字段、漏实现、错结果和单侧错回包名。映射类型检查实际注册，测试保留独立 wire 样本，二者分别约束实现和协议拼写。SPEC 指定 product-contracts 持有产品端口，允许 IM、Channels、PA 和 integration 依赖它。复用 IM 的关联器、配置解析器与 integration 的 RpcPeer 能保留原传输和权限职责。检查发现 Channels 也是实际消费方，见 R1-W1。
- **M1 产品接线。** 从 IM 的 settings/sections、配置操作和单聊分支跟到 Gateway 持有的 NodeRpc，再到 Node 的 WebRelayConnection.onFrame、CapabilityRequests 与 ConversationHistory。核对 NodeCommandMap 和 nodeResponseTypes 的 23 个键、前置处理的四条 inspection 和删除预览、update hold、ACK 时序以及插件变更通知。Gateway.handle 先校验当前连接与 node_id，NodeRpc 按连接、请求 ID 与结果名匹配。control.ts 的 resolve 再核对持久 operation ID、指纹与配置对象。设计保留这些职责，并安排有计划、空计划、离线无快照及保存中断恢复的验证。
- **历史 Work。** Web AgentWorkPanel 与 iOS AgentWorkPermissionView 都能从工作记录进入 permissions 路由。IM 查询 Global profile 并校验 owner；integration 的原生人工审批分支在 Global 或 subagent 身份下直接拒绝。基线 Node 没有该兼容命令的处理函数。新 Node 返回已结束、旧 Node 可能超时、单线程聊天继续通过独立入口答复，这三个结论有代码依据。历史记录需构造并明确标注，其 IM 准入条件见 R1-W3。
- **M2 产品接线。** 对照 PA 的调用和注入 read、RuntimePartitions 的默认及 scoped 路径、evaluation 的 createProduct、integration 的实际 handle。清单覆盖工作分页、会话操作、计划、任务、知识、工作流、审批、配置选择和 PA review。schedule.command 的 jobs 和 delete 在 ScheduleDeletions 中有不同消费，按 action 关联有实际需要。session.fork 返回的数据先用于分区路由登记，再写入 PA 的目标会话绑定；设计要求在第一次读取前解码合理。integration 已有 Work pull lane、update/deletion 准入和 stdio 错误信封，足以承载此变更。另有停用后的直连读以及空对象确认，见 R1-W2、R1-W4。
- **兼容、delta 与里程碑。** 本地存在 v2.1.0，旧源码可独立核对技能统计请求/回包。三份 delta 均有对应 canonical area。Skills 修改保留原有的统计读取、缺文件/工作区返回空表两个情形。用分派器绑定回调和由 handler 返回结构化结果这两种实现核对，Gateway 新条款均允许。历史 Work 条款的实际适用条件仍须缩小。类型反例、混合版本双向验证和隔离产品旅程各有明确分工。两个空 .gitkeep 骨架与顺序里程碑一致。此轮没有产品实现、发布、数据转换或新的界面决定，不需要迁移提示词或视觉原型。分支上下文在实施后按真实模型回复验证，本轮只核对设计与基线。

### 历史问题闭环

首轮，无历史问题或 Author Resolution。

### Issues

#### R1-W1　四种临时检查结果名仍有第三处生产定义

设计第 36、40、74、104 行要求一处定义结果名，并把 M1 接线列为 IM 与 Node。实际 Channels 在过期时直接比较四个手写结果名。某个有效名称从允许列表漏掉时，已失去服务端请求身份的回复会被当作普通上行请求，在关联模式下换成新 ID。当前 Channels 回归只用 agent.capabilities 验证过期拒发。将这个判断纳入 M1，保留 Channels 的过期处理，从共享配对取得临时检查结果名，或由已绑定的回复入口告知其身份；用四个现行名称证明过期结果不会写出即可。[Channels 出站分流](../../../../packages/channels/src/index.ts#L144) · [现有过期测试](../../../../packages/channels/tests/web-relay.test.ts#L190)

#### R1-W2　停用后读 Work 的直连适配缺少设计落点与验收

设计第 13 行提到注入的 read，第 65–67、105 行说明普通、scoped、capture 和评测适配。停用完成后 main.ts 把 supervisor.request.bind(supervisor) 直接交给 recordStopped。它绕过 RuntimePartitions，原始响应直接流进 PA 的 recordEvents、commitWork。只在分区端安装解码会漏掉此入口；改接普通运行端口又会让 session.work.root 或 workers.confirm 遇到停用准入，阻断最后一批历史。应让该已选定 supervisor 的读函数也采用共享方法类型与结果解码，同时保留 stoppedRevision 和原停用路径。把“停用后能回补、畸形页不推进该页游标、整个过程不重新启动执行或发布”列入 M2 的适配验证。当前单测直接注入手写 read，不能证明真实 Node 接线。[Node 停用接线](../../../../apps/node/src/main.ts#L682) · [原始 supervisor 端口](../../../../packages/dsh-integration/src/client.ts#L143) · [PA 消费](../../../../packages/personal-assistant/src/global-agent.ts#L1287) · [已有停用测试](../../../../packages/personal-assistant/tests/agent-lifecycle.test.ts#L115)

#### R1-W3　历史权限场景混合了 IM 本地拒绝与新节点回包

IM delta 的 GIVEN 只要求留有历史记录且节点支持明确拒绝。该条件也覆盖生命周期已撤销的记录，实际 IM 会在派发前返回 agent_lifecycle_revoked。另有不满足 pending、node epoch、轮次状态的记录，会在 IM 自己返回 request_ended。设计第 49、104 行引用的历史测试在中间停用/启用 Agent，最后只断言 409，沿用它足以在没有发出任何新 RPC 时得到相同状态码。请将新保证限于已通过 IM 准入并到达在线新节点的历史决定，在集成验收中记录发出的这一帧、同一 request_id 的业务拒绝及随后 HTTP 409 的 request_ended；旧代际在 IM 提前拒绝继续作为独立回归。无需改动界面或生成真实活跃 Global 审批。[Work 路由](../../../../apps/im-server/src/work.ts#L550) · [生命周期错误码](../../../../apps/im-server/src/agent-lifecycle.ts#L41) · [引用的历史测试](../../../../apps/im-server/tests/agent-lifecycle.test.ts#L122)

#### R1-W4　无业务字段的成功不总是 wire null

设计第 66 行要求“合法的无业务返回以 wire 的 null 为准”。宿主的 session.inbox-delivered.confirm 与 session.work.workers.confirm 在完成副作用后都显式返回空对象。RpcPeer 使用 result ?? null，两个命令实际发出的都是 {}。如果接收方将这些确认建模为只接受 null，会在宿主已完成确认后向 PA 报错；若两端一起改成 null，又改变了既有 wire 形状。请限定 null 规则为原 handler 返回 null 或 undefined，按方法保留显式空对象，使用真实 stdio 编码后的回执作断言。[确认方法](../../../../packages/dsh-integration/src/index.ts#L702) · [stdio 信封](../../../../packages/dsh-integration/src/rpc.ts#L153)

### Recommendations

无额外建议。

### Author Resolutions

- R1-W1 accepted。已核对 WebRelayConnection.request 的过期判断，在关键决策与 M1 范围、退出标准补入 Channels 和四种旧回包的拒发验证。
- R1-W2 accepted。已核对 main 的 disableAgent → supervisor → recordStopped；M2 的接口与退出标准补入停用直连读、stoppedRevision、游标及无重新执行/发布的验证。
- R1-W3 accepted。已核对 Work HTTP 路由的本地条件，收紧 IM delta 和 M1 实际验收，分开断言本地提前拒绝与同一请求的真实 Node 回包。
- R1-W4 accepted。已核对两个确认 handler 显式返回 {} 和 RpcPeer 的 nullish 编码，修正 M2 结果定义与 stdio 验收。

## Round 2

| Metadata | 值 |
|---|---|
| reviewer | Codex 独立 reviewer，gate2_rpc |
| target | develop 首文档 6f18ec907，产品源码 56b992e83，本轮本地修订的 design.md 与 specs/im/agent-work.md |
| review_mode | delta |
| mode_reason | 同一对产品边界内补充两个真实消费入口，收紧兼容场景并校正空回执。M1、M2 的顺序与公开端口方向保持原设计。 |
| retained_from | Round 1 |
| started_at | 2026-11-23T21:35:06+09:00 |
| completed_at | 2026-11-23T21:35:44+09:00 |
| duration | 0m 38s |

### Verdict

**Approved**，0 CRITICAL / 0 WARNING。四个首轮问题均已关闭。

### Coverage 与证据

复核了变更的关键决策、M1 历史权限、M2 结果解码及停用回补、两个里程碑的文件范围与退出标准，并与 IM delta 互查。首轮的 23 条命令范围、运行时方法清单、关联机制、跨版本取样及产品旅程依据继续适用。修订均可在现有包依赖和准入逻辑下实现，实施后按更新的判据采集运行证据。

### 历史问题闭环

- **R1-W1 — closed。** Author Resolution 将 Channels 纳入 M1。修订后契约标注四个临时检查，IM 和 Channels 都从标记及配对表取得结果名。实际的更换请求 ID 分支仍由 Channels 控制，M1 要求逐个检查四个名字过期时均没有写帧，覆盖首轮发现的命名分歧。[设计](design.md#L36) · [M1 退出标准](design.md#L105) · [Channels 出站判断](../../../../packages/channels/src/index.ts#L144)
- **R1-W2 — closed。** Author Resolution 保留 disableAgent 确认后选中的 supervisor 和原 stoppedRevision，把共享结果解码置于根页、子页及确认的消费前。这个 revision 是宿主 workBinding 判定已停用读取的依据。M2 要从 Node 的实际停用接线验证正常补齐、畸形页不推进该页游标以及不重新执行或发布。[设计](design.md#L67) · [Node 接线](../../../../apps/node/src/main.ts#L682) · [宿主准入](../../../../packages/dsh-integration/src/index.ts#L636)
- **R1-W3 — closed。** Author Resolution 将保证限定为通过 IM 对记录、轮次、owner、epoch 和 lifecycle 的检查并送达支持该命令的在线节点。设计要求对同一 request_id 核对出站、节点业务拒绝及 HTTP 错误，旧代际的本地拒绝单独断言没有发帧，能区分两个均可能产生 409 的路径。[IM delta](specs/im/agent-work.md) · [M1 验收](design.md#L49) · [IM 路由](../../../../apps/im-server/src/work.ts#L550)
- **R1-W4 — closed。** Author Resolution 按每个方法实际返回值定义 wire 结果。修订明确保留两种 confirm 的空对象，并要求核对经 stdio 编码的回执。宿主显式返回空对象，RpcPeer 的 nullish 转换保持其形状。[设计](design.md#L66) · [两个确认 handler](../../../../packages/dsh-integration/src/index.ts#L702) · [RpcPeer 编码](../../../../packages/dsh-integration/src/rpc.ts#L153)

### Issues

无。

### Recommendations

无。

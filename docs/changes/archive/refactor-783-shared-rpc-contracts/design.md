# refactor-783 双端 RPC 契约设计

依据 [motivation.md](motivation.md)。产品代码基线 `56b992e83`。

## Changelog

## 现状分析

### 涉及范围

IM 的 [NodeRpc](../../../../apps/im-server/src/node-rpc.ts) 按当前连接、请求 ID、预期结果名关联回复。它给调用者自动补 ID，临时检查还带 deadline。Node 的四个能力/提示词检查在 [CapabilityRequests](../../../../apps/node/src/capability-requests.ts) 内自己拼结果名，其余命令大多在 [main.ts](../../../../apps/node/src/main.ts) 中分派。WS 结果回送本身也是一次需要 IM ACK 的请求，回包发送完成时间影响通道对服务端请求 ID 的保留。[WebRelayConnection](../../../../packages/channels/src/index.ts)

PA 传给 integration 的请求经过 Node 的分区选择、生命周期检查和 stdio。还有两个容易漏的入口：按分区捕获 generation 的恢复端口，以及评测装配直接把 `client.rpc` 交给产品。Work 分页既有直接请求也有注入的 `read` 函数。[分区](../../../../apps/node/src/runtime-partitions.ts) · [Global Agent](../../../../packages/personal-assistant/src/global-agent.ts) · [评测接线](../../../../packages/dsh-integration/src/evaluation.ts)

### 既有约束

产品契约只描述产品身份、参数和结果。IM、PA 和 Channels 遵守 [SPEC](../../../../SPEC.md) 的依赖方向。已有 WS、stdio、认证、重试/恢复和数据持久化的 owner 继续履行原职责。Zod 4 已经是 product-contracts 的直接依赖。分开导出 node-rpc 与 runtime-rpc 子路径，避免前端和独立编解码器被迫载入整组 RPC schemas。

### 可复用能力

保留配置运行时解析器对可选字段及回执附加字段的处理，复用已有的 Task、Work、配置、会话和审批产品类型。IM 的 NodeRequest 已通过 NoInfer 约束入参，结果按原命令解码。stdio RpcPeer 已提供 ID 匹配、错误信封、独立响应分派与按 lane 写出分页的机制。这里需要给这些机制接上契约，无须再造传输层。[配置解析](../../../../packages/product-contracts/src/configuration-rpc.ts) · [RpcPeer](../../../../packages/dsh-integration/src/rpc.ts)

### 相关历史

[refactor-672](../refactor-672-im-contract-boundaries/design.md) 建立 IM 消费侧契约及请求关联。[bugfix-776](../bugfix-776-work-activity-stall/) 处理过 stdio 帧与 Work 恢复争用，迁移不得引入重复序列化或改变分页调度。

## 架构总览

| 边界 | 一处定义 | 调用方 | 处理端 |
|---|---|---|---|
| IM → Node | 每条命令的请求 schema、现有结果帧名、结果 schema | NodeRpc 生成 envelope，收到回复后按原命令验证 | 按命令取得已类型化的入参、执行业务、返回结果；分派器填写结果帧名和关联字段 |
| PA → integration | 每个产品方法的请求及结果 schema，必要时细分 action | PA 只持有有限的 RuntimePort；Node 转发并在结果首次进入产品域时解码 | 用同一组键注册实际处理函数，接收端先校验再进入该方法的业务操作 |

## 关键决策

**以 schema 推导调用与实现的静态类型。** 两个协议各一张有限表。每条记录同时产生运行时 decoder 和 TS 输入/结果；已具备解析能力的领域类型可用原解析器作为 schema 的组成部分。实现表使用映射类型 `{[K in Method]: Handler<K>}` 检查实际函数，禁止把 `Record<string, Handler>` 或统一的输入/输出联合当作穷举检查。让 handler 直接返回结果，或在确实需要取消时使用绑定到当前命令的结果回调；业务代码拿不到可自由选择结果名的回复接口。四个临时检查命令在契约中标明用途；IM 与 Channels 均由这一标记及已有回包配对取得检查结果名。Channels 仍负责 request_id 的保留和过期拒发，避免把迟到回复换成新的上行请求 ID。

**区分写出与读入的形状。** 例如新 Node 的 `task.execution.state` 业务结果应写出 TaskExecutionState；合法旧结果缺少 state 或携带其他文本时，IM 仍按现行网关逻辑解释为 unknown。相同部分复用一个 schema，只有已有生产证据要求宽读时才拆出读取变体。配置回执保留原对象、附加字段、null 与缺省差别（已有测试检查对象身份）；使用无清洗的校验方式，避免 Zod 默认剥键/克隆结果进入持久化。已知业务字段有具体类型，提供方私有数据可保留 unknown。对 setup 的状态、操作结果和合法错误先核对 IM 投影与 Node 实际输出，对开放字段仅开放其所属层级。schema 错误只报告方法和字段路径，setup 凭据、输入正文不进入错误文本。

**保留现有许可时序与失败通道。** 临时检查的四条 RPC 在 lifecycle 同步前经 admitted 进入，取消帧直接交给原 controller，取消不回结果；删除预览仍在 lifecycle 等待和一般 update hold 之前处理；一般命令在原等待、hold、计数及 finally 范围内分派。按已知命令键选择上述路径，只有一张完整 handler 表。同一处理异步范围内等待现有 relay.request 的 ACK，相关副作用保留排序（例如插件修改成功后先通知目录变更，再发送结果）。`node.request.cancel`、上行主动事件及反向 RPC 保持各自 owner。业务拒绝走原结果类型，传输断开/超时仍代表不确定结果。

## 接口与数据流

### M1　IM ↔ Node

1. 将现有 23 项 [命令及结果名称](https://github.com/Mrchen116/nano-multiagent/blob/56b992e83a84b44c63f218ed8b36ec8433eddbe4/apps/im-server/src/node-rpc-contracts.ts) 的 wire 拼写逐项作为基线。调用参数与接收侧 wire envelope 分开：发送时可省略 request_id，接收带关联标识、临时检查可带 deadline_at；回包的 node_id 取本机身份。关联元数据不会被业务结果覆盖。个别方法同时消费请求 ID（如审批），由 handler 上下文显式提供。
2. 每个请求先检查必需业务字段，再执行业务操作。允许有依据的旧输入，例如节点已支持按 workspace_root 定位的心跳预览和 cron 查询。已知命令的畸形请求不执行；若该命令有可识别的失败结果，按原协议返回；否则通过原 onFrame 错误通道报告并释放请求，发端按原超时/待确认语义结束。不得把仅含 error 的对象当作任意命令的通用失败帧。例如 jobs 消费方可能将缺少列表误读为空，配置 mutation 也不能凭校验失败编造已确认回执。无关联身份不能答复。
3. IM 先校验连接、node_id 与关联，再按原命令的读取 schema 检查结果。四条 inspection 的 error_code 维持 503/504 映射，普通畸形结果维持 502。配置状态恢复读取 gateway_result_json 复用对应结果校验并保留 IM 错误适配。业务身份、指纹、授权仍在原 owner。已无 pending 的持久回执继续走 Gateway 原有的后续处理；保留原有 ACK/拒绝路径；只有已关联的请求或业务 owner 确认的 operation 才能写入状态。
4. **历史 Work 审批是兼容命令。** Work 路由只选 Global Agent；Global 和它的 child 在原生审批请求中直接返回拒绝，不建立等待人工答复的请求。已有 Web/iOS 可从历史 Work 事件渲染按钮，IM 仍可能发出 `agent.work.permission`。为该键注册有类型的兼容处理：走既有准入，返回 `agent.work.permission.result`、原 request_id 和 `{ok:false,error:"request_ended"}`。IM 沿用已有 409 分支。这是从无 Node handler 时可能超时变为明确的业务拒绝，绝不触发 approval.answer；不得新建人工审批流程。旧 Node 仍可能超时；历史可读，单线程聊天的实时人工授权入口独立回归。构造 owner 有权限、lifecycle revision 与 node epoch 有效、轮次可操作、待确认且选项匹配的历史记录，从真实 HTTP 入口提交。核对 IM 发出的帧、在线新 Node 以同一 request_id 返回的拒绝、HTTP 409 的 request_ended 三者对应。另测旧代际在 IM 提前拒绝且不发帧；测试构造的历史记录须标明，不能宣称当前 Global 实际生成活跃卡。[Work 查询与权限路由](../../../../apps/im-server/src/work.ts) · [Global 权限契约](../../../specs/gateway/global-agent.md) · [运行时处理](../../../../packages/dsh-integration/src/index.ts) · [旧记录测试](../../../../apps/im-server/tests/agent-lifecycle.test.ts)

### M2　PA ↔ integration

以实际调用者为准。基线可从 PA 的 `runtime.request`、传入的 `read` 与转发包装定位下列方法。前缀列与表内各后缀用点号连接。

| 前缀 | PA 使用的方法后缀 |
|---|---|
| session | ensure、lookup、submit、cancel、command、observe、recovery.probe、export、fork、publication、inbox-delivered.confirm |
| session.work | check、root、children、child、targets、workers.confirm |
| schedule | command、evidence、wait.inspect |
| task | context.passive、execution.block、execution.changed、wait.repair |
| knowledge | facts、acknowledge、sources.pending、sources.sync |
| workflow | pending、acknowledge |
| 其他 | approval.answer、configuration.selection、pa.review |

- **端口与转发。** 对 PA 暴露的 `request<K>(method: K, params: Input<NoInfer<K>>): Promise<Output<K>>`、`capture()` 及 scoped port 都保持方法关联；对 schedule.command 等按 action 决定结果的方法，将 input/action 与 output 配对，jobs 返回列表，history 返回记录，delete 返回删除结果。integration 的同一 handler 也按 action 对应类型检查（可按 action 组合实际分支）。已有其他调用者使用的 action 继续可用，宿主私有方法不加到 PA 的公开接口。Node 以独立的内部传输签名保留维护、trajectory 等调用，在 PA 依赖注入处只暴露窄接口；不用一个接受所有 string 的公共 overload 兜底。同步更新依赖旧 RuntimePort 的 NodeTrajectory 类型与 evaluation 注入，评测必须使用相同的结果解码入口。
- **进程边界。** integration 用完整的具名 handler 表实际注册有限方法，原私有 handle / peer.handle 仍负责其余方法。迁移方法沿用各自原注册器的 update、deletion、admissions 和 pull lane 等选项，私有注册不得抢占已注册的公共键；输入在任何相关业务写入前解析。非法参数通过 stdio 的 RpcError(-32602) 拒绝，其他既有 RPC 错误沿用原 code。结果按发出请求的 method/action 解码，在返回给 PA、更新 fork 分区映射、按 owner 过滤 knowledge/workflow 集合等首次读取之前完成。按方法保留实际 wire 结果：仅返回 null/undefined 时 RpcPeer 才编码为 null。session.inbox-delivered.confirm 和 session.work.workers.confirm 显式返回 {}，以真实 stdio 编码后的回执验证两者的结果。RpcPeer 的通知与反向调用仍独立于该目录。
- **停用后的 Work 回补。** Node 在 supervisor.disableAgent 确认后，把该 supervisor 的直连读函数交给 GlobalAgent.recordStopped。保留这条指定宿主的路径并接入相同的泛型请求与按原方法解码；带入原 stoppedRevision，在 projectRootPage、子页和确认路径消费前校验。用 Node 停用接线验证末页可回补、畸形页不推进该页游标、整个回补不重新启动执行或发布消息。[停用接线](../../../../apps/node/src/main.ts) · [Work 回补](../../../../packages/personal-assistant/src/global-agent.ts)
- **保真与开销。** 生命周期包装器在保留具体 input 的同时附加已有 agent_id/lifecycle_revision；按原逻辑保留 agentId、sessionId、requestId 的分区路由，capture 的 generation 在异步前后均检查。单个消费者信任边界只做一次完整解析，尤其是 RuntimeWorkPage、历史消息及选定大字段；复用已有产品解析逻辑，避免重新 JSON 编解码、深拷贝整页或剥离来源、正文和扩展。传给模型的内容、选取规则及上下文恢复时机沿用原实现。
- **贯穿例子。** IM 的 session.fork.request 携带 fork_point.message_id；节点找到原 binding 后，PA 以 sessionId、messageId、operationId 调 session.fork。integration 返回 sessionId、revision、idMap，结果校验成功后 Node/PA 才记录目标绑定，IM 按已有 ok/id_map 完成分支。非法结果不得被解释为已成功建立可用分支；合法业务失败仍按原规则清理。区分源会话、目标会话、原请求与持久 operation 四种身份。

## 本次审查安排

| 问题 | 阶段与能力 | 判据 |
|---|---|---|
| 是否真能挡住单侧变更 | 实施时类型验证，交付时 code review | 用进入 pnpm typecheck 的类型用例（参考 [IM type-tests](../../../../apps/im-server/type-tests/node-rpc.ts)）证明错方法/字段、漏 handler、错结果无法编译；同时保留正确调用。临时对实际接线删键、改返回值验证编译失败，恢复后全仓通过。23 个结果名与独立基线逐一对比，单侧手写回包路径应消失。 |
| 原始数据、旧版本和错误是否解释正确 | 边界测试和隔离交叉版本测试 | 双向重放固定于改前源码/发行 tag 的独立样本，分别验证旧请求→新实现、旧回包→新调用方、新请求/回包→旧端；覆盖 23 项的现行配对、旧部分配置、workspace-only 读取、inspection deadline/取消、合法失败、扩展字段、畸形入参零业务副作用和畸形结果拒绝。不得用同一新 schema 合成期望与实测。 |
| 路由、副作用与用户结果 | 实施后 code review + product-journey-review | 复用 [NodeRpc 测试](../../../../apps/im-server/tests/node-rpc.test.ts)、[分区测试](../../../../apps/node/tests/runtime-partitions.test.ts)、[stdio 背压测试](../../../../packages/dsh-integration/tests/rpc-backpressure.test.ts) 补回归，使用下列真实入口观察计划、配置恢复及分支。 |

## 契约层增量 (delta-spec)

Gateway 接收侧增加针对畸形产品 RPC 的可依赖保证，见 [relay-protocol 增量](specs/gateway/relay-protocol.md) 和 [service-lifecycle 增量](specs/gateway/service-lifecycle.md)。IM 的历史 Work 操作对端保障见 [Work 增量](specs/im/agent-work.md)。计划展示、配置确认、分支语义沿用 [Agent 配置](../../../specs/im/agents-nodes.md) 与 [单聊分支](../../../specs/im/conversations-messages.md)。技能统计旧 spec 的名称随本次 relay 增量对齐实际报文。

## 风险与回退

按边界分批交付，IM 和已安装 Node 可处于不同版本。实施时记录测试节点所选发布清单的 source_commit/tag、注册能力与两端构建 SHA；可用仓内可追溯历史 tag（例：v2.1.0），仅对其实际支持的命令主张兼容。对当时尚无 handler 的审批单列基线。stdio 的 Node 与 host 同包升级，无需新握手。每批可回退相应代码并沿用原数据；可能已经执行的写操作继续用原 operation 身份查询，禁止重发猜测成功。

## 一次性部署迁移

无。

## Runbook for Reviewer

在受审 worktree 中运行 `python3 scripts/dev_host.py check` 核实模型入口与测试依赖，`pnpm build && pnpm typecheck`。从该 worktree 运行 `./scripts/e2e-up.sh --profile daily --wt "$PWD"` 启动独立 IM、Node 和该 Node 管理的 DSH host，用实例输出的 IM 健康端点、.e2e-daily.json 与节点在线状态确认就绪。用相同目录的 `./scripts/e2e-down.sh --wt "$PWD"` 停止并按[资源回收规则](../../../development/worktree-runtime.md)回收本轮现场。

1. 用测试 owner 在 Agent 配置读取有计划、无计划和无快照的离线节点，确认三者可区分。通过隔离 IM 和可控 WS 节点在配置已应用、确认到达前切断连接，核对原 operation 的待确认与重连确认，以及另一连接的回复不会提前结束它。上述故障注入需注明使用受控节点。
2. 在真实在线 Node 的单聊先约定一个独特词，再选一条已完成的回复作分支点，在源单聊加入较晚内容。从分支第一轮追问独特词，确认截至该点的上下文可用，较晚内容和两边后续发言各自独立。记录模型是否真实接入；fixture 仅证明协议行为。
3. 边界反例使用成对的内存 stdio peer / 真实 WS 入口和可计数业务处理函数。并发错 ID、失效 generation、断线、畸形字段及非法结果分别断言调用结果与持久副作用，不需要生产资源。

## Milestones

先迁移已有 IM 命令表的双端，再迁移另一条传输；每步可单独回退，两步都改动 Node 装配，顺序实施。

| ID | 依赖 / 并行组 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-node-rpc | 无 / 顺序 | product-contracts node-rpc、IM NodeRpc 和回执、Channels 回包过期处理、Node main 与 capability-requests、相关类型及边界测试 | [worker] 23 项真实处理接入、关联及独立 wire 基线对照、四种过期 inspection 回包都不写出、兼容与错误测试、类型反例通过。[reviewer] 计划可区分在线有/无和离线；配置确认中断后能恢复到原操作；旧 Work 权限项可读，提交旧决定得到已结束状态，普通聊天仍可答复真实待处理的工具请求。 |
| M2-runtime-rpc | M1 / 顺序 | product-contracts runtime-rpc、PA 各 RuntimePort 调用、Node 分区与接线、integration 注册与评测适配、相关测试 | [worker] 基线清单和新增真实 PA 调用全部受双端类型检查，入口解码和 action 关联有反例；分区/capture、停用直连回补、pull、两种空对象确认、错误与原始 payload 回归通过，全仓 typecheck 通过。[reviewer] 隔离实例中从较早回复创建的分支能独立继续对话。 |

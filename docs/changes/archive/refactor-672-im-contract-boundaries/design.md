# refactor-672: IM 配置、节点 RPC、Work 与聊天完整链路 — 技术方案

> 对齐 motivation.md

## Changelog

- Final sync：采用已合入 refactor-671 的序列化子路径导出与 `serializeCandidateJson` 名称；保留其字节契约，不新增本 unit 算法迁移。配置纵切、RPC owner、无行为 delta 的关键决策不变。

## 现状分析

### 涉及范围

- `context.ts` 将不可信 HTTP 输入、SQL 查询与各种产品输出合为 Row；全局替换会牵动无关业务。
- `control.ts` 的 ConfigOperations 已有真实业务 seam：serialized/create/update/recover；它管理候选、operation 恢复、乐观锁失败补偿、profile 持久与公开投影。
- `gateway.ts` 的 request/pending/handleFrame 混合传输关联与业务分派，响应名存在四个例外和 `.request` 约定。pending 按 request_id、连接对象与 responseType 三者匹配；shutdown 清理超时。
- `server.ts` 装配完整 ImContext；`personal-agent.ts` 复用配置服务。`apps/node/src/main.ts` 是请求消费方与响应字段的核对依据。

### 既有约束

不引入运行时依赖方向变化、通用 Repository/事件总线/DI 框架。不迁移或重命名序列化算法。HTTP 鉴权、二次授权、事务边界、operation ID/指纹、生命周期投递顺序不变。原 report 保留。

### 可复用能力

复用 ConfigOperations 的恢复流程与 SQLite 同步事务；复用 product-contracts 的配置与 Task 类型；复用现有配置/节点连接测试。SQL 是本地可替换依赖，继续用 DatabaseSync，不为数据库造抽象端口。节点 RPC 是实际远程 seam，提供具名命令表及最小 request port。生命周期只需 commit 后投递回调。

### 相关历史

feat-652/近期 Agent settings 路径保留 snapshot freshness 和离线新写保护；配置 operation 与 approval configuration 回归继续保留。当前代码已有 agent lifecycle 与 PA restore 分支，本次必须完整迁移其行为，不清理旧业务。

## 架构总览

HTTP unknown → 配置入口解析 → 配置候选 → ConfigOperations（SQLite 记录/恢复/事务）→ NodeRequest port → NodeRpc（关联/定时器/回包）→ Gateway 的已授权 socket；结果经配置投影返回 HTTP。

Gateway 保留连接注册/鉴权、业务消息分派与 Task 写入屏障；M4 后流式业务由 ChatStreaming 承担，Gateway 只接线。NodeRpc 只拥有出站请求和匹配响应，不能访问数据库或业务对象。配置服务只拥有 db、节点 request、commit 后 lifecycle 投递三项依赖；路由与 PA 在装配处提供 adapter。

## 关键决策

**按完整配置纵切深化，而非全仓去 any。** 配置请求、候选、profile 行、operation 行、回执、公开投影分别命名；不能用同一个 Record 的别名冒充类型。后续 M3/M4 分别扩展 Work 和聊天完整链；会话/联系人/Channel 管理及 Work 查询/命令等未选中业务保留现状，交付明确剩余范围。

**所有中心主动 RPC 使用有限命令表。** 表按实际调用者/Node handler 建立 input/output/response 名关联；配置 operation、配置读取、Task 状态等稳定字段明确建模。插件/provider/工具等扩展数据在所属字段使用 unknown 或 Record<string, unknown>，调用者消费前按现有投影检查，不把任意索引签名加到稳定类型上。不存在公开 string→Row fallback。共享的配置 wire 类型放 product-contracts；仅中心用的命令映射留 IM。

**解析放边界，授权留业务。** HTTP 配置入口接收 unknown，在现有 validateCandidate 语义基础上解析为具名输入；保留可选字段的省略与 null 差异、现有文本整理和未知额外键忽略行为，不用全局 Fastify schema 造成所有错误响应变化。WS 先检查 envelope，再由关联中的命令 decoder 检查所消费字段；配置回执的 operation/fingerprint 与授权二次检查仍在服务。JSON 存储读取在配置模块私有边界解码，SQL 行类型仅在固定查询位置声明，不提供任意泛型查询给路由。

**抽出有责任的配置服务，不机械拆文件。** 锁、候选、事务、恢复、补偿与投影跟随服务；控制路由仅处理身份/参数/HTTP 组合。为了与并行序列化任务避免交叉，现有 asciiJson/candidateFingerprint 算法和调用保持原语义；必要纯配置整理函数单独保留在既有位置或小型配置编码模块，不能使新服务反向依赖整个 control 路由模块。

## 接口与数据流

- `NodeCommandMap`: 每个命令含 input/output；`NodeRequest<K>(nodeId, command, input): Promise<Output<K>>`。输入/结果关联不能通过 string overload 逃逸。
- `NodeRpc`: 构造依赖 send、currentConnection 和更新 gate；request 创建 ID、保存期望响应/连接、10s timer；accept 在 Gateway 完成当前连接/node 身份检查后匹配响应并解码；close 释放并拒绝所有请求。保留现有 offline 503、timeout 504、更新 gate 409 及迟到/错连接不消费行为。
- `ConfigOperations`: constructor `{db, request, deliverLifecycle}`；serialized/create/update/recover 保留调用语义。配置 service 内部读取具名 ProfileRecord/ConfigOperationRecord；公开响应为 ProfileView，不泄露 JSON 存储字段。
- 配置 HTTP create/patch 使用解析后的 CreateConfigInput/UpdateConfigInput，构造 Candidate；PA restore 与 skills migrate 同样进入具名服务边界。
- WS 回执保存原 payload（含附加 wire 元数据），验证不能裁剪后再影响持久字节。非法/不完整回执仍不得变成成功，沿用 operation pending 语义。

配置内容、提示词选项、来源或上下文加载时机均不改变；此重构不改变 LLM 可见信息。验证关注配置字段从 HTTP 到节点候选再到 profile 的保真，而不运行模型语义评测。

## 契约层增量 (delta-spec)

IM：no spec delta。行为兼容重构，无客户端变化。非法输入继续由边界拒绝；不新增产品能力。

## 风险与回退

主要风险是省略/null、SQLite nullable 字段、旧节点回包的缺省字段、补偿与 PA restore 被不慎归一化。只对消费的稳定字段进行必要解析，留存扩展内容；既有测试优先。保持原 SQL 和事务顺序，禁止顺手修复其他报告项。可回退代码，无迁移回滚。

## 一次性部署迁移

无。

## Runbook for Reviewer

本 unit 不改客户端，可用客户端同一 HTTP API 与设备 WS 驱动真实隔离服务。配置管理不依赖模型回复；用测试节点响应协议验证端到端 operation/身份/断连，不将其称为真实模型验收。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM | 结束本次测试创建的 server 并删除临时目录 | 复用 `apps/im-server/tests/e2e/helpers.ts` 的真实监听 server，临时 SQLite/上传目录与随机端口 | GET /health |

**Review 驱动方式**：真实 IM HTTP/WS/SQLite，由客户端相同接口驱动；无客户端面修改。验收者独立发起配置读取/保存/越权/离线与重连恢复。

**验收前置**：Node 24.22.1、pnpm frozen dependencies，build 后运行；无需生产账号、模型或外部平台。常驻服务由验收脚本 finally 关闭，进程不遗留。

## Milestones

分两阶段因为先固定所有出站请求的传输关联，才能把配置恢复迁移到窄依赖，分别验证连接风险与持久事务风险。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-node-rpc | 节点 RPC 命令与生命周期 | 无 | 顺序 | gateway、node-rpc、命令类型、必要调用者 | [worker] 有限命令输入输出关联，无 string fallback；稳定字段真实解析；超时/offline/更新/错连接/迟到/停服保持；typecheck 与节点测试通过。[reviewer] 节点消息归属不变。 |
| M2-config-service | 配置完整边界 | M1 | 顺序 | control、config service/records/input、PA 装配、必要 product-contracts 类型 | [worker] 配置服务不依赖 ImContext/Gateway/Identity/Messaging；HTTP、候选、SQL 行、回执与公开投影具名且实际消费；无以 unknown→断言替代校验；create/apply/recover/compensation/restore/离线/权限回归通过，指纹语义不变。[reviewer] owner 保存刷新、越权与版本冲突、确认丢失恢复与新离线写拒绝均保持。 |

## M3 扩展设计：Work 完整事件链

### Grounding 与职责

`work-projection.ts` 将 RuntimeEvent 转为 `{type:string,payload:Record}`；`GlobalAgent.workEvent/append`、`InboxStore.append/commitWork/journal` 再丢失字段关联。`WorkSync` 使用已有 HTTP 批量/分段协议，IM `work-sync.ts` 与 Gateway 的旧 `agent.work.append` 最终都调用 `Work.append`。后者已有原子日志/投影/水位事务，但和用户查询、权限操作、Gateway 广播混在持有完整 ImContext 的类里。`Work.project` 同时处理稳定事件及既有任意扩展事件，不能通过封死未知 type 破坏历史协议。

### 接口与归属

1. **共享产品事件契约。** product-contracts 新增 Work 事件模块，定义有限已知事件 type→payload 的判别联合、事件身份 envelope、本地未编号事实、带 seq 的日志事件、批量输入与 append ACK。现有 WorkSyncPart/Cursor/limits 复用。已知 payload 的身份、状态、统计、工具展示控制字段具名；工具 arguments、detail、error 和来源扩展内容为 unknown/明确动态对象。保留 `turn_start`、`run_completed/run_failed/run_cancelled` 等既有事件别名与允许的缺省字段；不新增协议版本。
2. **生产契约与不可信数据分开。** PA 生产方法必须接收完整判别联合（不把 type/payload 分拆成可以错误配对的宽泛参数）。InboxStore 的追加/原子 checkpoint、日志读取、WorkSync 上传消费同一 envelope。JSON 读取和 HTTP/WS 接收使用共享 decoder：检查稳定 envelope 及已知事件实际消费字段后返回原对象，不重排、不裁剪、不补默认字段。decoder 将已知事件和未知扩展事件显式区分；未知扩展仍按现行通用投影规则保存。不存在让当前生产调用者绕过事件表的 string fallback。
3. **IM 持久/投影 owner。** 新增内部 WorkRecords 类，仅依赖 DatabaseSync。拥有注册身份约束、事件去重/顺序、事务性日志+投影+水位推进、固定记录查询与 items/turns 的公开投影。append 返回 ACK 与本次影响的 root IDs，既有 Work facade 在提交后做授权用户广播、在线状态/同步进度组合及用户/Agent 查询控制。固定 SQL 查询位置拥有具名记录，不引入泛型 Repository 或 DI 框架。构造时 running→unknown 恢复语义保持。
4. **双入口一致。** HTTP 批量、分段 JSON 重组及旧 WS append 都进入相同 decoder/WorkRecords；鉴权身份仍取当前 binding/connection。分段哈希必须基于原始内容；已提交重复的身份比较、历史身份-only 跳过、PA 主会话替换、吊销后的跳过与恢复顺序保持。
5. **投影契约。** 已知事件按判别联合消费对应字段；turn/item SQLite 行与其 JSON 数据区分，公开 page/view 类型不混入 SQL JSON 列。保留未知事件的通用 item、原附加字段、别名、可省略统计以及原 `JSON.stringify` 语义。不将任意 native runtime 事件 schema 纳入本仓固定契约，也不改模型输入/执行循环。

### 验证和完成边界

- M3 为一个完整纵切，不拆机械分层 milestone；实现可将 PA 生产端作为明确文件范围的独立首轮子任务，先冻结共享类型接口，后续修复由主 Agent 完成。
- 编译负例覆盖错误 type/payload 配对、缺失身份和 SQL record 冒充公开 view；常规 typecheck 必须执行。
- 保留既有 work-sync、global-work-recovery、inbox、global-agent、Work 真 HTTP/WS 测试。新增一个贯通真实 PA projection→InboxStore→WorkSync→IM→公开页的隔离链，含主子执行、完整工具结果与结束统计、重启/重放；不以手造中心 fixture 代替生产接线。
- 畸形稳定字段经批量/分段/WS 入口均不推进水位；合法省略/null、未知事件、旧别名、扩展内容及已保存字节得到必要回归保护，不为每个字段制造重复测试。
- 独立设计复审先于实施；完成后执行 M3 的产品验收与静态 code review/verification，M1/M2 按未改变的实现与同步影响 retained。无 UI 改动，产品验收以相同真实 HTTP/WS 接口读取结果；无新模型 Context 语义，保真与原生替换事实不重新执行的保护继续保留。
- 数据库 schema、序列化算法、16 MiB 上限、分段协议与恢复水位不变；no spec delta，无部署迁移。Work 的聊天查询/指令/审批路由不做无关全面重写，M3 不覆盖聊天和 Channel；聊天在下方 M4 单独设计，Channel 管理仍不扩大。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M3-work-events | Work 完整事件契约与持久投影 | M1/M2 | 单纵切 | product-contracts Work，PA work-projection/global-agent/inbox/work-sync，IM Work/WorkSync/Gateway入口，相关测试 | [worker] 已知生产事实的 type/payload 编译关联贯通到日志和传输；共享decoder真实校验保原值；WorkRecords不持有ImContext；固定行与公开投影分离；批量/分段/WS共享入口；重放/恢复/权限/字节兼容及真实生产链通过。[reviewer] 新增三条Requirement均可从真实工作页API结果核实，原记录不丢失、不重复、不虚构完成。 |

## M4 扩展设计：聊天发送与流式更新

### Grounding 与模块归属

`Messaging.sendMessage` 直接以 Row 混用 HTTP body、principal、SQL 结果和公开消息；`message` 同时解码 messages JSON 列和派生发送者/审批展示。`Gateway.streaming` 接收任意 Row，以 kind 分支消费不同字段、检查来源和生命周期并更新消息、过程及事件。`SingleThread.delta` 与 GlobalAgent 显式发送没有生产端载荷关联。既有 RelayDelivery 已独立拥有有界窗口/重试，不重造投递队列。

1. product-contracts 定义 ChatStreamFact 的有限 kind→字段联合、AgentPublication、ChatAttachment、过程项、权限选项、发送回执及稳定消息 View。正文/身份/状态/序号固定，工具 input/output/detail、交互 source/state、来源扩展保持动态。SingleThread.delta、GlobalAgent 的发送方法及 external shadow 的实际转发边界使用这些类型；不得以 string overload 绕过已知生产事件约束。Channels 通用帧仍保留动态协议能力，不扩展为全 Channels 消息表。
2. untrusted HTTP/WS/持久 outbox 边界分别解码。共享 stream decoder 校验该 kind 真正消费的字段、嵌套工具/审批 id 等，返回原对象；不裁剪附加字段、不重排对象、不补默认字段。turn_start、普通 message 更新及既有 run_terminal_reconcile no-op 分开建模。HTTP 输入与受控 insert metadata 分开，交互数据继续由现有 Interactions owner 校验；不得引入第二份 UI schema 或规范化指纹。
3. 新 MessageRecords 持有 SQLite 和实际需要的窄交互投影/写入接口，拥有固定 MessageRecord/EventRecord/RelayRecord、JSON 列解码、公开消息投影、基础消息写入及流式持久化操作。发送者/PA provenance 保持现有查询语义；NodeUpdates 的 messageWait 作为只读可选投影函数。不能持有完整 ImContext/Gateway/Messaging。既有 Interactions 是独立业务 owner，不复制其提交/隐私规则。
4. Messaging 保留发送授权及消息+交互背景+relay 的事务编排，HTTP adapter 转为具名 SendCommand 后进入内部发送方法；消息记录及事件持久化委托 MessageRecords。事务外 publishMessages 沿用既有真实接收者和 relay eligibility 检查。普通消息 attempt 的原始规范化字段、旧行回退与 Agent dispatch log 的不同幂等规则保留，不能为“统一”而改指纹或比较集合。
5. Gateway 只做传输接线；独立 ChatStreaming 通过数据库、具名消息端口、Agent/PA 授权函数及结束后的 groupReply 回调拥有流式业务。MessageRecords 隐藏 SQL/JSON 更新；ChatStreaming 负责解码后的事件分支、权限和已有状态处理。普通 message_delta 保留只查询身份/状态的热路径，不因为强类型而读取完整过程历史。选中聊天事件用具名 ChatEvent 联合生成并持久发布；其它配置/Task/运维 conversation_events 不纳入此次全表迁移。
6. 不创建通用 Repository、事件总线或新的持久队列。现有 stream buffer、ack/relay admission、publication recovery、external outbox 的算法与事务边界不变。外部平台结果未知与 IM 补镜像继续由 ExternalChannels 拥有。

### 兼容性、Context 与风险

模型输入、消息路由、审批决定与工具运行时不改。本轮固定产品边界，需核对真实 SingleThread/GlobalAgent 生产载荷和 IM 消费结果；模型能力无需重测。RelayInput 和交互背景仍按已有链路进入 runtime，必要集成检查观察实际 port 请求，而不让 fixture 声称模型理解。

终态、discard、重放等先按既有代码和 current spec 建立基线，发现 drift 单独记录，不能把重构新增的类型默认值变成隐式状态修复。特别是 current gateway-relay 对 provisional discard 的原子投影回滚描述强于当前 Gateway 的简单 delete/event 分支：实施不得借移动代码扩大行为承诺；需在测试/审查中区分已有 drift 与本次回归。无需 schema/协议版本迁移；本轮目标 no spec delta。

### 验证与验收

保留 messaging、message-attempts、relay-delivery、interactive-messages、agent-lifecycle、watchdog、external-ingress、single-thread/external 及真实 e2e/server/relay-recovery 的既有保护。先跑相关基线；新测试集中于稳定字段拒绝不留下 SQL/幂等/广播副作用，以及真实 SingleThread→协议→中心→HTTP/history/user-stream 接线。覆盖发消息重试/冲突、流增量重试、终态后增量、过程/权限/动态内容、身份和生命周期、断线恢复。编译负例覆盖错误 kind/字段配对、缺少身份、SQL 行冒充 View，纳入常规 typecheck。

产品验收沿用隔离真实 HTTP/WS/SQLite，同客户端接口观察发送、实时事件与刷新结果；RuntimePort 提供确定性原生事实，仅用作机制接线，不声称真实模型。无 UI 改动，无视觉原型。M4 full 独立设计审查先于实施，完成后静态 code review/verification 和产品验收；M1–M3 按实际共享影响复验或 retained。首轮可将已冻结契约的 PA producer 迁移作为明确文件范围子任务，其余由主 Agent 完成；后续修复不另派实施 worker。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M4-chat-messages | 聊天发送与流式完整契约 | M1–M3 | 单纵切 | product-contracts chat、PA SingleThread/GlobalAgent/external、IM Messaging/MessageRecords/ChatStreaming/Agent publication、相关测试 | [worker] 生产事件有限关联，入口真实校验，发送/记录/View 分离，持久与流式 owner 不持有完整服务容器，原字节/事务/授权/恢复语义及真实接线通过。[reviewer] 新增三条 Requirement 从真实 HTTP/WS/history 结果可核实，基线漂移不冒充本次实现或通过。 |

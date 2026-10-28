# Code Review

## Round 1

- reviewer: 独立 reviewer `/root/static_review`，未参与设计或实现。
- review_mode: `full`。
- executed_base: `ff326c351`。
- validated_at: `648b5439e914d6cf90f85a5296734c0e77e3c7eb`。
- effective_base / effective_through: 同上述固定版本；后续提交由交付 owner 判断失效范围。
- completed_at: `2026-10-28T11:32:00+08:00`。
- checkout: `codex/im-contract-boundaries`；开始时 clean。本轮仅写本报告和 `verification.md`，由主 Agent 提交。

### Findings

```json
[]
```

### 覆盖与判断

- 审查完整 `ff326c351..648b5439e` diff；将旧 `control.ts` 的服务和路由分别与新服务、`control-routes.ts` 逐段对比。不是仅检查新增类型声明。
- 核对全部 21 个主动 RPC 的真实调用者：control、onboarding、conversation-actions、personal-agent、work 与 Gateway Task adapter。对照 `apps/node/src/main.ts:187-292` 的配置、能力、预览、setup、fork、usage、heartbeat、cron、Task handler；`agent.work.permission` 的传输形状与既有 Work 调用及 Gateway 生命周期 gate 相同，本次不改变其接收端实现。`NodeCommandMap`/`nodeResponseTypes` 封闭命令关联，无公开 string fallback；setup/provider 目录和插件内容继续保留动态载荷。
- `node-rpc.ts:24-67` 保留更新 409、离线 503、10 秒超时 504、连接引用与响应名匹配、迟到/重复忽略和 shutdown 定时器释放。`gateway.ts:382-402` 仍先验证当前已注册连接、node identity 与适用生命周期，再交给 RPC 关联；注册、Task 写屏障和上行业务未移给 transport。
- `configuration-input.ts:43-83` 在 HTTP/存储 JSON 边界检查实际消费字段；固定 SQL 查询在 `configuration-records.ts:57-74` 拥有记录声明。`control.ts:129-149` 的公开投影与候选恢复不泄漏 SQL JSON 列；HTTP 候选仍显式选择字段，额外键不进入 operation。省略 approval、nullable reasoning、null prompt/heartbeat 保留、nullable features/work mode，以及历史 null skills 均有对应保护。
- `control.ts:184-468` 保留 operation 身份和指纹、串行锁、二次授权、原 SQL/事务顺序、gateway_applied 恢复、CAS 补偿、PA restore/name/chat 同步和提交后 lifecycle。`configuration-assembly.ts:6-11` 是唯一全容器装配 adapter，服务仅持有 db、三类配置 RPC 与生命周期回调。`requestConfiguration` 将非法回执留在未确认流程；decoder 保留原 payload 及额外 wire 元数据，不重写持久回执。
- 比对 `asciiJson`、`gatewayCandidate`、`candidateFingerprint` 与 Node canonical/fingerprint：未迁移算法、改变排序/转义/字段缺省或哈希输入。`selection` 的 null 兼容防止合法历史值在公开投影崩溃，不改变规范内配置含义。
- 测试迁移未删除原断言；新增传输测试保护关联与生命周期，HTTP 测试保护输入/存储/投影，真实 HTTP/WS E2E 保护 malformed receipt → pending → 同 operation 恢复。编译负例进入 IM 的常规 typecheck。

### Agent Context Implementation Review

- 模式：`agent-context-review` Mode B，限定配置选择、传递与恢复链；不是新增 Prompt 或模型语义设计。间接触发原因：custom_prompt、features、skills/tool_allowlist、model/reasoning 与 PA identity 最终影响模型可见信息。
- 核查 owner HTTP → candidate → durable operation → Gateway wire → Node ConfigurationOperations → `apps/node/src/configuration.ts:78-98` 的 runtime 配置映射；同时检查读取、重试、CAS 补偿与 PA 绑定。来源身份仍由服务端 binding 派生；用户 body 的 personal identity 不成为授权来源。
- Before/After 的受支持配置字段、字段选择、候选规范化、fingerprint、持久恢复及生效调用顺序一致。`parseAgentConfigurationFields`/`decodeNodeResult` 校验后返回原对象，未新增过滤或重新组装模型消息。新增 E2E 的真实出站 apply 与恢复后的公开配置保留 custom_prompt 和有序 fallback；既有 approval/configuration 回归保护选择保真。
- 无存活 Context finding。证据仅支持本次重构不改变有效配置交付；未捕获 provider 请求、未运行真实模型，不声称验证模型理解或任意模型可靠性。Node runtime/prompt 组装与模型执行实现不在 diff 中，无需为同一不变性重复模型评测。

### 验证证据与限制

- 复用 M1/M2 progress 的定向 16 tests、既有 71 tests 及 M1 32 tests 证据；主 Agent 已派发同步后复核，不重复运行全量。
- 当前固定 HEAD 的 `.e2e-refactor-672/build.log` 完成 installer build；`typecheck.log` 已全包 Done；`git diff --check ff326c351..648b5439e` 独立执行通过。
- `.e2e-refactor-672/test.log` 是同步前 772 passed / 1 knowledge-policy 等待断言超时；当前 `test-synced.log` 已记录多个 DSH 集成超时，caller 已停止本次测试进程，保留日志并计划降并发复核。caller 观察到主机 load averages 474.29 / 189.40 / 89.73；高负载是复核线索，尚未证实为所有失败根因。这些结果不能被写作全量绿灯，也不足以归因于本 diff；全局失败判真与交付门禁由主 Agent 继续处理。本审查的空 findings 不替代 CI 通过。

### 结论

指定完整 diff 未发现 maintainer 需要处理的具体代码缺陷。配置纵切与有限 RPC 关联完成；聊天、Work、Channel 上行业务及其 Row 仍属明确剩余范围，不宣称全 IM 类型迁移完成。

## Round 2 — Final Sync Patch

- reviewer: 同一独立 reviewer `/root/static_review`。
- review_mode: `patch`；mode_reason: 同步主干 refactor-671/refactor-673 后核查冲突整合及受影响边界，保留 Round 1 full 结论。
- prior_unit_head: `32ac1af9d`（Round 1 后仅增加文档）。
- executed_base / effective_base: `b8fc5edefcb74ec8a8888aeb7fa245779e644253`。
- validated_at / effective_through: `fc0dca156b3c3cce9602d39e7c47a601ad86b038`。
- completed_at: `2026-10-28T11:49:00+08:00`。
- 范围：`git range-diff ff326c351..32ac1af9d b8fc5edef..fc0dca156`，加主干增量对配置/Task 能力 guard/授权的影响；不是重审其他已合入 unit。

### Findings

```json
[]
```

### 同步后有效性

- range-diff 表明本 unit 的两项实现提交仅适配主干序列化入口和测试 import；文档提交 patch 等价。独立逐字比较 `control-routes`、四个 configuration 边界文件、四个 node-rpc 边界文件、PA ConfigurationOperations 与 IM 编译负例，共 11 个文件与同步前一致。服务/HTTP adapter、三类配置 RPC 依赖、解码、恢复、权限与生命周期决定未被冲突解决覆盖。
- `control.ts:1,24-29,35,96` 保留主干 `sortedJsonUtf8` 和 `serializeCandidateJson`，继续在候选格式转义 U+007F..FFFF；没有误换成 DEL 语义不同的 `sortedJsonAscii`。主干从 task-graphs 移除的 `canonicalJson` 未被恢复。`gateway.ts:1,572` 保留主干 `sortedJsonAscii` 的 publication identity 比较，RPC import 和授权后 accept 同时保留。
- `control.test.ts` 的 `sortedJsonUtf8`/ChannelKey/AAD 依赖，与本 unit 的 `configurationDependencies`、服务/路由分离 import 并存；`approval-configuration.test.ts` 同时保留 `gatewayCandidate` 和新路由 import。两个主干新增 Unicode fingerprint/AAD 测试正文独立比较为 byte-for-byte 一致，未丢失断言或 fixture。
- product-contracts 根入口保留主干移除 canonicalJson 的决定，仅追加本 unit 三个配置类型及 parser；`package.json` 保留 `./serialization` 正式 export。不存在旧导出恢复、重名或 private import。
- refactor-673 的 Task 关闭通过既有 Gateway.tasks 实例在 Messaging 外层事务中执行；本 unit 未覆盖该接线。配置使用的 `activeTaskCount`/`withdrawsTask` 定义未变，Task 请求 map/adapter 未变；关闭后计数基于权威投影是主干已生效契约，不是本 unit 新增 delta。
- Agent Context：沿用 Round 1 Mode B 结论；本次序列化适配保留字段与字节，配置输入/选择/恢复/Node runtime 映射不变。主干 Task 关闭契约属于新 base；未发现本 unit 整合造成的来源、权限或模型信息变化，无需重复模型任务。

### 证据与结论

- 最终 HEAD `.e2e-refactor-672/build-final.log` 完成 Node installer candidate；`typecheck-final.log` 所有 workspace 包 Done；`test-final-integration.log` 为 8 文件、77 tests passed。独立 `git diff --check b8fc5edef..fc0dca156` 通过。
- 补充先前全局门禁记录：bounded 全量为 145 文件/779 项、777 passed/2 failed；两项原样定向复跑分别在 `knowledge-low-load.log` 中 5/5 passed、`disable-low-load.log` 中 1 passed/6 未选中。前端 1029、Python 100 通过为 caller 带版本交接，最终状态由 delivery/CI 记录。未将一次全量失败改写成单次全绿，也不以复跑通过证明资源必然是根因。
- 无存活 finding，Round 1 full 结论在新 base 上保留并有效至本次 HEAD；不需要 full 重审。相对新 base 仍为 no spec delta。本轮仅追加两份报告，未提交、未修改产品或测试。

## Round 3 — M3 Work 完整事件链

- reviewer: 独立 reviewer `/root/static_review`；未参与实现。
- review_mode: `full`，完整覆盖新增 M3 `bd0938462..badc559a1`，另核 M1/M2 的 final sync 影响并保留未失效结论。
- executed_base / effective_base: `94b06908d396c8039d820124c4d86cb32a75eaf4`。
- validated_at / effective_through: `badc559a1937b9b7b34b75df4d5a3ba0f5137e22`。
- completed_at: `2026-10-28T13:29:00+08:00`。
- 输入：扩展 motivation/design、M3 progress、design-review Round 2、current `docs/specs/im/agent-work.md`；不重审其他主干 unit。

### Findings

```json
[
  {
    "file": "packages/product-contracts/src/work-event-codec.ts",
    "line": 63,
    "summary": "[P2] 在提交前校验两种权限表示中实际消费的 options 条目",
    "failure_scenario": "permission_request 的 options:[null] 通过 Array.isArray；嵌套 permission_request.options:'bad' 也不被检查。readWorkBatch→WorkRecords 独立内存 SQLite 复现已返回 through_seq:3 并保存 pending 权限条目；work.ts:423 随后按 options?.some(o=>o.id===decision) 消费时分别抛 TypeError，不能完成正常权限决定。这违反 M3 畸形稳定字段不得提交或推进水位的退出标准。将 option 对象/id 及嵌套表示的相同稳定字段具名并在共享 decoder 校验，保留额外字段与合法缺省，扩展既有边界回归保护。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

### 完整覆盖及保留结论

- WorkFact/WorkDraft 关联已知事件和完整身份，projectWorkEvent/GlobalAgent 接收完整 fact；KnowledgeUpdates 的 session_linked/self_evolution_review 同样经过 InboxStore 的具名 append。commitWork 的事务与 checkpoint 未改，journal 在 JSON 边界解码，WorkSync 保留原对象上传及分段哈希算法。编译负例进入 PA/IM 常规 typecheck，没有生产 string fallback。
- WorkRecords 仅持有 DatabaseSync；固定 session/event/turn/item SQL 记录与公开 view/page 分离。逐段对照旧 Work.append/project/items/turns/view：日志/投影/水位仍在同一事务；去重身份、顺序、撤权 identity-only 跳过、historical 主会话及 PA 替换、重启 running→unknown、提交后授权广播和 live 状态组合保持原顺序。
- HTTP 批量、分段最终 JSON 和旧 WS 均经 readWorkBatch/WorkRecords。decoder 对合法事件返回原对象，未排序、补默认或裁剪额外字段；turn_start/run_* 别名及未知事件通用投影保留。工具 arguments、presentation.detail/error、source refs 与未报告统计保持原值。权限 options 是唯一确认的稳定字段校验缺口，未因其它测试通过而排除。
- 真实生产链用 RuntimePort 提供原生事实，随后执行实际 GlobalAgent→InboxStore→WorkSync→独立中心 HTTP/SQLite→公开 Work/子执行页；检查主子身份、大参数/完整结果、已报告/未报告统计、刷新、重启/重复及 WS 拒绝。它不证明真实模型理解，也未覆盖上述畸形 permission options。
- M1/M2 与 Round 2 相比仅 skill usage HTTP 投影采用主干 settingsSectionDisplay；已核与新 base 对应 route 一致，属于已继承的 integration。配置服务、transport、权限及序列化未被覆盖；product-contracts index 在已有配置 exports 后追加 Work 类型/decoder，无旧 export 恢复。M1/M2 静态结论 retained。

### Agent Context Implementation Review

沿用 Mode B，限定 Work 投影与恢复以及共享 presentation 的 SingleThread 消费。事件类型包装不改变 GlobalAgent 模型输入、Inbox 消息/工具结果或执行循环；runtime 事实仅形成用户 Work/工具卡片。presentation 的 id/name 收窄对既有字符串身份不变；原生替换输出仍被识别为 Context 编辑而非再次完成。Work facade 的 query/command/permission 业务保留，session 读取只去掉内部 SQL JSON 列，调用方不将该列交付模型。无新增 Context finding；未捕获 provider 请求或运行模型，不声称模型语义验收。权限 finding 是确定性接收边界问题。

### 验证证据与限制

- `.e2e-refactor-672/m3-integration.log`：10 文件/110 passed；`m3-build.log` 完成本固定 HEAD installer；`m3-typecheck.log` 全包 Done，包含 PA/IM 编译负例；`m3-ios-runtime.log`、`m3-pytest.log`（100 passed/28 deselected）通过。
- 独立临时内存 SQLite 复现：以合法 session_registered、turn_started 和 `permission_request {request_id:'bad',options:[null]}` 组成同一批，经 readWorkBatch 后 WorkRecords.append 返回 `{journal_id:'j',through_seq:3}`；持久权限为 `{request_id:'bad',options:[null],node_epoch:0,status:'pending',seq:3}`，执行 route 相同消费表达式得到 `TypeError: Cannot read properties of null (reading 'id')`。嵌套 `permission_request:{request_id:'nested',options:'bad'}` 同样通过 readWorkBatch。未修改源码/测试，数据库已关闭，无现场遗留。
- `git diff --check 94b06908d..badc559a1` 发现 `work-records.ts:490` 空白行含尾随空格；已交 caller 机械清理，不作为正确性 finding。全量后端/前端运行由 caller 收尾，本轮未重复全量。

### 结论

M3 有 1 项 CONFIRMED / P2 finding，需修正后 patch/closure。其它已核结论及 M1/M2 门禁保留；没有理由扩为无关源码重构或修改 current spec 迎合漏检。

## Round 4 — Permission Finding Closure

- reviewer: 同一独立 reviewer `/root/static_review`。
- review_mode: `closure`；focus: Round 3 的权限 options P2 finding。
- finding_origin_head: `badc559a1937b9b7b34b75df4d5a3ba0f5137e22`。
- fix_delta_range: `badc559a1..197da048e`；executed_base / effective_base: `94b06908d396c8039d820124c4d86cb32a75eaf4`。
- validated_at / effective_through: `197da048e8975677e8e82f7e0f73f511e7f67687`。
- completed_at: `2026-10-28T13:31:00+08:00`。

### Findings

```json
[]
```

### Focus Finding 状态

**Round 3 P2：closed。** `WorkPermissionOption` 具名 `id:string` 并保留扩展字段，flat/nested request 的 options 共用同一具名契约。decoder 的 permissionOptions 检查每项非 null 对象及字符串 id，两种表示均消费此检查。null 仍是安全缺省，后续可选链返回 invalid_decision 而不抛类型异常；decoder 返回原对象，未修改扩展内容。

修复 delta 仅 5 文件：契约/decoder、PA 编译负例、既有边界测试参数化，以及已指出的尾随空格清理。没有改变投影、权限授权、事务、水位、恢复或模型输入，不使 Round 3 的其它覆盖或 M1/M2 retained 结论失效。

### Evidence 与有效性

- `m3-permission-red.log`：原 decoder 下两项权限用例失败，实际取得 200/through_seq=2，证明回归测试能暴露原缺陷；不是仅断言内部 helper。
- `m3-permission-green.log`：3 文件/23 passed，覆盖 batch/parts 拒绝及不推进、生命周期和实际生产链；原 malformed tool 用例保留。caller 交接 PA/IM typecheck 通过，新增编译负例拒绝缺 id/错误 nested option。
- reviewer 独立直接调用本次源 decoder：flat `[null]`、nested 非数组、flat 缺 id、nested 数字 id 共 4 例拒绝；flat/nested null 与含扩展内容的合法对象共 4 例返回原 event/fact 引用。没有写测试或运行全量。
- `git diff --check 94b06908d..197da048e` 独立通过。前端 `m3-frontend.log` 已完成 108 文件/1029 passed；后端全量仍由 caller 收尾，不声称已全绿。
- 结论：无存活 finding；权限校验缺口已关闭。原 full/同步结论及本次 closure 有效至固定修复 HEAD，仍为 no spec delta；无新增 Context 影响。仅追加报告，未提交。


## Round 5 — M4 Chat Full Review

- reviewer: 独立 reviewer `/root/chat_static_review`；未参与受审实现。
- review_mode: `full`，完整覆盖 M4 `c90f5e968c2a28f31669fb5acb78567681fc5949..39f159d9f0a9089023939fa2f9e2569542f8037e`。
- executed_base / effective_base: `c90f5e968c2a28f31669fb5acb78567681fc5949`。
- validated_at / effective_through: `39f159d9f0a9089023939fa2f9e2569542f8037e`。
- completed_at: `2026-10-28T14:44:15+08:00`。
- 输入：扩展 motivation/design M4、design-review Round 3 Approved、M4 progress；current IM conversations-messages / gateway-relay、SPEC、Context 与测试规范。M1–M3 按实际共享影响核查并保留有效结论。

### Findings

```json
[
  {
    "file": "packages/product-contracts/src/chat-codec.ts",
    "line": 28,
    "summary": "[P2] 校验嵌套权限对象中实际消费的执行身份字段",
    "failure_scenario": "permission() 漏检 ChatPermission 的 agent_id/node_id/node_epoch/lifecycle_revision/run_id 等稳定执行身份，顶层 common 检查不能覆盖 permission_request 内嵌对象。以 permission_resolved {message_id, decision:'deny', permission_request:{request_id:'bad',agent_id:{invalid:true},node_id:'node',lifecycle_revision:1}} 调用真实 ChatStreaming→MessageRecords，收到成功 ACK，错误对象被保存并发布 permission.resolved；conversation-actions.ts:409 随后用同一 card.agent_id 调用 requireLifecycle 时抛 SQLite Error: Unknown named parameter 'invalid'。这使本轮“畸形稳定消费字段不写入、不广播”的退出标准未完成。请在共用 permission decoder 检查 flat/nested 稳定身份字段，保持允许的省略/生命周期 null 和原扩展对象，并扩展既有边界用例证明拒绝发生于 SQL/事件之前。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

### 覆盖与有效性

- 逐段对照旧 Gateway.streaming 与新 ChatStreaming / MessageRecords：turn_start 的来源 Agent、PA ownerConversation、访问与 lifecycle 校验先于写入；旧消息 lifecycle 继续复验；message_delta 只读取固定身份/状态列，不加载完整工具或过程 JSON；普通增量 key、终态后增量、完成、思考、工具 merge、审批状态、heartbeat 与 groupReply 顺序保留。run_terminal_reconcile 仍是独立 no-op。选中 ChatEvent 联合进入 records.chatEvent 后才由原发布策略投递。
- MessageRecords 不持有 ImContext/Gateway/Messaging；其 DB、交互 read/record、agent user、只读 messageWait 与 publish 回调均为具名窄依赖。固定 MessageRecord/EventRecord/RelayRecord 与 ChatMessage 分开，SQL JSON 保持在 owner 内解码；旧字段顺序、非枚举内部详情、PA provenance 和工具人审 badge 逐段保留。Messaging 保留授权与消息/交互背景/relay 同一事务，commit 后 publishMessages 仍重新检查 relay eligibility。Interations 仍唯一拥有 UI schema、private state、提交与指纹。
- HTTP unknown→MessageInput→SendMessageCommand 与 controlled MessageMetadata 分开；sendPrincipal 返回原认证对象，server onSend 的身份撤销复验未改变。内容/引用规范化、普通 attempt 的 content/attachments/interaction_contexts 指纹与旧行回退没有与 Agent dispatch log 混为一套。显式 publication 的权限、目标解析、dispatch key、interactive 比较、事务与投递从 Gateway 移到 Messaging，原决定和成功回执保留。
- SingleThread.delta、GlobalAgent.publishMessage、External forwardStream/frame/pendingFrames 实际消费有限 ChatStreamFact/AgentPublication，不存在生产 string overload。原生工具 presentation、可省略统计和 provider 动态内容未被重新格式化；External 仍使用原 operation identity、原 JSON.stringify frame hash、unknown platform result 与 IM mirror 分离，system_notice 仍独立处理。合法数据的共享 decoder 返回原对象，未知附加字段不裁剪。上述权限身份漏检是目标内已确认缺口，不由其他合法测试替代。
- M1/M2 的 ConfigOperations/NodeRpc 文件与接口未动；M3 Work decoder、WorkRecords、Inbox journal/WorkSync 未动。共享 product-contracts index 仅追加 chat exports，现有配置/Work exports 保留。Task/PA 调用适配为 ChatMessage，原 transaction、notice/provenance 与 relay 接线保持；未发现要求扩大到 M1–M3 full 重审的共享行为变化。

### Agent Context Implementation Review

- 模式：agent-context-review Mode B，限定消息/relay 投影、交互私有背景及实际 PA 消费链。
- 检查实际 Messaging.enqueueRelays 的 message/sender/participants/interaction_contexts/context_only，SingleThread.submitAdmitted 的 withInteractionContext、时间/来源 envelope、群 roster、图文 parts、attachmentSources、session.submit source，以及 GlobalAgent Inbox admission / publication status 恢复。受审 diff 没有改这些最终组装表达式；MessageRecords 的公开投影按原顺序和原数据返回，Interactions.prepare 的私有状态边界保持。
- 新贯通测试在真实 HTTP 用户发送→WS relay→真实 SingleThread→RuntimePort session.submit 观察到原输入正文；输出原生工具/正文/统计经 WS→IM→history，重复 recover 不增加事实。RuntimePort 是确定性事实 fixture，只证明此 seam 的交付与装配，未捕获 provider 请求、未运行真实模型，不能证明模型理解或选择工具能力。本轮没有新的模型输入语义，故未追加模型任务。
- 无独立 Context finding。权限 finding 是确定性产品接收边界漏检，未声称模型一定产生该畸形字段。

### Evidence 与基线 drift

- 复用实施者交接的 `.e2e-refactor-672/m4-second.log`（10 文件/110 passed）、`m4-third.log`（11 文件/52 passed）、`m4-typecheck.log`（全包 Done，含编译负例）、`m4-ios-runtime.log`。`m4-boundary-red.log` 证明新增畸形字段用例在旧接收路径收 ACK 而红；合法链与修复后接收保护通过。没有把测试数量当完整覆盖证明。
- `m4-build.log` 构建完成；installer candidate 元数据仍标记实施提交前的 base `c90f5e968...`。该日志按 caller 的 M4 working-tree 证据复用，不称日志自身绑定了最终提交 SHA。`m4-backend-full.log` 本轮检查时仅见启动，未当作已完成全绿。
- 独立 Node 24.22.1 / tsx、openDatabase(':memory:')→ChatStreaming→MessageRecords 最窄复现：上述畸形嵌套权限获 ACK，保存 `{agent_id:{invalid:true},node_id:'node',lifecycle_revision:1,status:'resolved',decision:'deny'}`，发布 1 个 permission.resolved；执行 route 相同 requireLifecycle 语句得到 `Unknown named parameter 'invalid'`。数据库 finally 关闭，无源码/测试修改，无生产访问或服务遗留。
- 独立 `git diff --check c90f5e968..39f159d9f` 通过。
- current gateway-relay 的 provisional discard 原子清理过程事件/会话投影/重复幂等强于旧 Gateway 的 DELETE message + event。新 records.discard / ChatStreaming 保留同一简单分支，未把这一既有 drift 写成本轮实现或通过；需要另行确定修复范围。

### 结论

1 项 CONFIRMED / P2，M4 须完成稳定权限身份解码后限定 closure；其余 M4 full 覆盖和 M1–M3 retained 结论保留。目标仍为 no spec delta，不能通过改 current spec 接受该漏检来关闭。本轮仅追加本报告及 verification，未提交。


## Round 6 — M4 Permission Identity Closure

- reviewer: 同一独立 reviewer `/root/chat_static_review`。
- review_mode: `closure`；focus: Round 5 P2（V5-1）权限嵌套执行身份漏检。
- finding_origin_head / pre_fix_head: `39f159d9f0a9089023939fa2f9e2569542f8037e`。
- fix_delta_range: `39f159d9f..21b09d3e4892806d77829d6e9c2af1cdec6f6087`。
- executed_base / effective_base: `c90f5e968c2a28f31669fb5acb78567681fc5949`。
- validated_at / effective_through: `21b09d3e4892806d77829d6e9c2af1cdec6f6087`。
- completed_at: `2026-10-28T14:51:16+08:00`。

### Findings

```json
[]
```

### Focus Finding

**Round 5 P2 / V5-1：closed。** permission() 共用验证 agent_id/node_id/run_id 字符串、node_epoch 有限数字、lifecycle_revision 有限数字或既有安全 null；decodeChatStream 对 flat/nested 均调用该检查。ChatPermission 的 revision 声明与原有 lifecycleAllows(null) 兼容规则对齐。修复发生在 ChatStreaming.apply 前，故原恶意对象不能进入 MessageRecords 或成功事件。

修复 diff 仅三个文件，7 行增加/2 行删除：共享类型/decoder 和已有真实 WS 边界用例。未改授权、投影、事务、relay、流式幂等/状态或模型输入。Round 5 的其余 M4 full 覆盖与 M1–M3 retained 结论继续有效，不扩为 full 重审。

### Evidence 与限制补充

- `.e2e-refactor-672/m4-permission-e2e-red.log`：修复前真实 WS 收到 ACK、期望 error，新增用例确实失败；`m4-permission-green.log`：6 文件/34 passed，参数化 flat/nested 五字段均被拒绝，原同测试的消息/事件/delta key 无副作用检查与合法增量恢复断言保留。IM/PA typecheck 通过由 caller 交接并定位 `m4-fix-types.log`。
- reviewer 独立直接调用固定修复源 decoder：permission_request / permission_resolved × flat/nested × 五字段共 20 个畸形对象均拒绝；3 个合法场景（flat null、nested null/原生扩展对象、完整合法 request/options）返回原引用且 JSON 字节不变。独立 `git diff --check 39f159d9f..21b09d3e` 通过；无源码/测试修改、服务或数据库遗留。
- 补充 Round 5 当时尚未完成的证据：冻结初始 M4 HEAD 的 `m4-backend-full.log` 最终为 150 文件/800 passed；`m4-frontend.log` 108 文件/1029 passed；`m4-pytest.log` 100 passed/28 deselected。修复后用上述定向测试与 typecheck 承接，不把它们冒称修复 HEAD 的一次全量运行。final build 由 caller 单独执行，不复用旧 installer base metadata 冒称当前构建。
- motivation/design 当前未提交变化仅澄清最终 M1–M4 范围、标题和早期排除语句；已核不改接口、场景或退出标准，不构成 spec 迎合实现。保持其他并行文档修改原样。

### 结论

无存活 finding，M4 静态门禁对固定修复 HEAD 通过；**aligned / no spec delta**。provisional discard 的原有 canonical/code drift 仍按 Round 5 单列，未因本次 closure 声称已修复或已通过。无新增 Context 影响，保留 Round 5 Mode B 的实际装配与证据限制。仅追加两报告，未提交。

# Design Review

## Round 1

### Metadata

- reviewer: 独立 reviewer `/root/design_review`（非设计作者）
- target: `refactor-672-im-contract-boundaries` 的 motivation、design、M1/M2 空骨架，以及相关生产装配与 current 契约。
- review_mode: `full`
- mode_reason: 首轮 Gate 2；独立覆盖需求、现状、职责、共享接口、兼容性和验证计划。
- started_at: `2026-10-28T10:48:30+08:00`
- completed_at: `2026-10-28T10:50:39+08:00`
- duration: `2m09s`
- validated_at: `9d7531feb0097d3fb60511cad10ce33c40dbc4a9`
- executed_base: `a34af8473`
- checkout: `codex/im-contract-boundaries`；审查开始时 clean；本轮仅新增本报告。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

完整配置纵切加全部中心主动 RPC 的有限命令关联，足以落实架构报告第 3 项的真实模块契约目标。方案没有承诺全仓 Row 清零，也没有把声明替换当成完成；不需要为了扩大表面覆盖而重写聊天、Work、Channel 等无关业务。当前决定与退出标准可以指导实施，未发现会使下游实质走偏的未解决设计问题。

这是实施前设计判断；未运行测试、未验证实现或模型行为，也不代表后续 verifier/code review/适用产品验收已通过。

### Coverage 与证据

#### 需求范围与现状

- 核对原报告 `docs/research/architecture-reviews/architecture-review-20261028-102827-a89b778.html:71-78`：明确建议从 Task 或配置真实 seam 开始，具名输入输出和内部存储类型，再缩小 context，并反对全仓类型重写。motivation 的配置链范围与此一致；额外收口所有主动 RPC 能覆盖原报告指出的 `request(type: string, payload: Row)` 关联缺失。
- 实际污染入口在 `apps/im-server/src/context.ts:8-19,28-30,42-46`。配置链从 `control.ts:711` 创建、`:892` PATCH、`:855` 读取进入 `ConfigOperations`，不是仅存在于测试中的抽象。`server.ts:88-91` 装配 Gateway/PersonalAgents，`control.ts:618` 与 `personal-agent.ts:314` 分别创建配置服务。
- `control.ts:167-475` 确实包含按 Agent 串行、二次授权、候选与指纹、持久 operation、状态恢复、补偿、profile/PA 身份事务与提交后 lifecycle 投递。把这些整体迁移到服务而不是只移动路由或增加 DTO，能够解除当前完整 ImContext 依赖。
- 已检查 `M1-node-rpc/.gitkeep`、`M2-config-service/.gitkeep`；骨架与 design milestone 表一致，没有预填虚构 tasks/progress。

#### 职责与接口可落实性

- 配置服务保留 SQLite 权威与同步事务是合适的：现有流程需跨 profile、operation、users、PA binding 和 conversation 一起提交，通用 Repository 层不会带来本需求所需收益。`db + request + deliverLifecycle` 足以覆盖现有依赖；`control.ts:473` 的 `new AgentLifecycles(ctx).deliver(...)` 可在装配 adapter 内实现，业务不必持有 Gateway/Identity/Messaging 对象。
- Gateway 当前 `request` 在 `gateway.ts:126-171` 拥有 ID、response 名、连接捕获、定时器与离线拒绝；回包在 `:416-450` 先核对当前连接和持久身份，再完成 pending。design 保持这个安全顺序，NodeRpc 仅拥有相关请求生命周期，不接管注册、Task 写入屏障或数据库授权，职责划分成立。
- 命令表按中心实际调用者和 `apps/node/src/main.ts:187-283` 的消费/回包建立；四个特殊响应名、`.request` 和 `session.fork.request` 特例均有现存实现。已检查 control、personal-agent、onboarding、work、conversation-actions 和 Gateway 自身的调用点；设计的“所有中心主动 RPC”包括这些适配点，不仅是配置三条命令。
- 稳定 input/output、SQL 行、业务 Candidate 和公开 ProfileView 分开建模；动态插件/provider/工具内容在字段内保留扩展，而不是在稳定对象上保留任意索引。禁止 string fallback、禁止 unknown 后直接断言冒充校验，并要求实际调用者消费类型，能够提供真实编译保护。
- 依赖方向符合 `SPEC.md:29-48`：共享产品配置契约进入 product-contracts，中心专用命令表留 IM，不引入 IM→Node/PA/DSH。未新增框架、第二执行循环或存储迁移。

#### 行为、恢复与兼容性

- 对照 `docs/specs/im/agents-nodes.md:60-126`，设计明确保留 version、完整候选 apply、确认丢失时原 operation 恢复、未知结果 pending、补偿、live 合并和旧节点缺省；`no spec delta` 合理。auth-tenancy/gateway-relay 所要求的 owner/空间/设备身份边界没有被替换为仅在入口做一次校验。
- 关键实现依据：`control.ts:267-312` 的 operation/fingerprint/agent 结果检查和安全拒绝码，`:335-401` 的版本冲突补偿，`:425-475` 的 restore 与 PA 名称事务，`:505-525` 的输入校验，`:892-925` 的省略/null 处理。design 将这些作为保留行为，而没有借类型收紧更改文本整理或额外字段策略。
- 回执保存原 payload、包括额外 wire 元数据的决定与现有 `JSON.stringify(result)` 持久化一致，避免只返回 decoder 白名单后改变已有字节。非法/不完整配置回执必须仍落入 pending，而不是冒充 applied；这是实施必须满足的已有退出约束。
- 序列化第 4 项由另一任务处理。按 design 的约束解释，当前工作保持 asciiJson/candidateFingerprint 算法、名称与语义，不重新设计或统一序列化；抽取业务边界不授权迁移算法归属。实现仍须防止新服务反向依赖路由模块。
- 没有 UI、数据库 schema 或协议版本切换；不需要 prototype 或 deployment-prompt。代码回退保持 operation 数据可读，不重置待确认操作，回退方案合理。

#### 验证与 milestone

- M1 先固定命令关联和连接生命周期、M2 再迁移配置事务的顺序合理；退出标准覆盖真实类型消费和传输/持久风险，没有依赖未定义的并行接口。
- 可复用证据面已存在：`tests/e2e/control-work.test.ts:5-70` 以真实进程 HTTP/WS 完成配置操作，并验证相同 request_id 的无关响应不能完成 apply；`tests/agent-settings.test.ts:19,104,149,192` 覆盖旧能力缺省、离线新写、待确认恢复和读取 freshness；`tests/approval-configuration.test.ts:11,37` 覆盖省略/null 策略与跨端指纹；`tests/personal-agent.test.ts:60,96` 覆盖 PA 创建与延迟配置恢复。这些是已核对的测试资产，不是本轮执行结果。
- `tests/e2e/helpers.ts` 使用随机端口、临时 SQLite、真实 IM 子进程和认证设备 WS，能够承接 runbook 的隔离边界验收。测试节点回包可验证关联和 operation 流程；它不能证明真实模型推理或真实 Node 所有能力运行。设计已明确此证据限制，未把 stub 称为真实模型验收。

#### Agent Context Design Review

- 模式：Mode A，限定配置选择与投递链；依据 `agent-context-review` 和 `docs/development/agent-context-engineering.md`。
- 相关 Surface 是 custom_prompt、features、skills/tool_allowlist、model/reasoning 配置从 owner HTTP 输入，经候选规范化与 operation、Node configuration 到后续执行的交付。`control.ts:52-107` 的字段选择/指纹与 `apps/node/src/main.ts:278-283` 的真实 handler 是边界 grounding。
- 方案的 Before/After 均为相同有效字段、身份派生、候选指纹、恢复记录和配置生效时机；没有新增 Prompt、来源选择、工具描述或上下文生命周期决定。保持省略/null、顺序和 wire 内容的要求，加配置字段保真与兼容验证，足以验证本次设计所承诺的无语义变化。
- 未读取最终 provider 请求或运行模型；此轮没有实现可供证明模型实际交付。若实施引入字段裁剪、默认规则或加载时机变化，应按真实 delta 扩大审查，不能继续沿用“类型重构”豁免。没有 Context finding。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

无。

### Recommendations

- **R1-R1（可选）**：实施时把实际命令清单与成功/业务错误/缺省回包纳入 M1 的验证记录，尤其是 `node.setup.request`、动态 settings section、能力预览和 `task.wait.validate`。这些已在“所有主动 RPC”的范围内；记录清单有助于最终 verifier 防止遗漏，不要求另建大 schema 框架。
- **R1-R2（可选）**：优先补一项真实 WS 的不完整配置回执用例，断言仍返回 `503 config_apply_pending` 并保留 operation；再以原 operation 正确回包恢复。它直接保护新 decoder 与既有恢复协议的交界，也能防止把 decoder 异常意外变成通用 500。设计已明确该行为，本建议只细化最高价值的验证落点。

### Author Resolutions

- 作者核对 R1 结论及实际调用点，接受 Approved，无实质异议。
- REC-1/REC-2：采纳命令/响应覆盖清单和 malformed receipt→pending→同 operation 恢复保护，记录在实施验证中；不改变已审设计语义。
- 设计语义无变化。实现采用现有 control 模块持有配置业务与原序列化函数，HTTP 路由移到独立 adapter，避免迁移并行任务负责的算法或让服务反向依赖路由。

## Round 2

### Metadata

- reviewer: 独立 reviewer `/root/design_review`，沿用 R1 身份，未参与设计或实现。
- target: 用户明确要求在同一 PR #426 内增加的 Work 完整事件链；motivation 新增三个 Requirement、design 的 M3 段落与 `M3-work-events/.gitkeep`，以及相关真实生产/传输/存储/读取路径。
- review_mode: `full`（完整审查新增 M3 范围，M1/M2 retained）
- mode_reason: 这次增加需求、共享接口、核心持久化责任与 milestone，按 skill 采用 full；审查聚焦这次范围扩展，不重复审查未改变的配置/RPC 决定。
- started_at: `2026-10-28T13:08:45+08:00`
- completed_at: `2026-10-28T13:10:14+08:00`
- duration: `1m29s`
- validated_at: `bd0938462d32408501c2435bf3a134f096693033`
- executed_base: `94b06908d`
- checkout: `codex/im-contract-boundaries`；审查开始时 clean；M3 尚未实施。
- retained_from: Round 1 的 M1/M2 设计判断。当前扩展不改变其配置服务、NodeRpc owner、有限命令表或字段保真决定；既有实现门禁的版本仍由 verification/code-review/acceptance/delivery 各自记录，本轮不将它们改写为在新 HEAD 重新执行过。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

M3 覆盖产品事件生产、带 checkpoint 的本地日志、独立上传、中心校验和原子投影、受权公开读取整个链路。判别联合用于真实生产者，兼容 decoder 用于不可信/历史数据，WorkRecords 拥有数据库事务而 facade 保留传输和访问控制，这些边界足以形成实际模块契约。没有仅更换类型别名、引入通用 Repository 或借重构扩大模型/执行规则的设计问题。

本轮仅审设计与基线代码；没有运行测试或验证 M3 实现。主 Agent 提供的五文件 41 项基线通过信息不作为新实现已经通过的证据。

### Coverage 与证据

#### 完整生产链与本地恢复

- `packages/personal-assistant/src/work-projection.ts:5-44` 实际生成开始、模型选择、工具、正文、注入与结束事实；稳定类型和 payload 当前脱钩，arguments/detail/error/source 等确实包含应保留的动态数据。设计将产品事件建模而不复制任意 RuntimeEvent schema，归属合理。
- `global-agent.ts:670-781` 把 projection、模型失败提示、子执行注册与 stop 快照组成事实；`workEvent` 从可信 SessionBinding 派生 root/session/event 身份，不依赖模型提供 owner/node 身份。`InboxStore.commitWork`（`inbox.ts:377-384`）在同一事务中提交事实与处理 checkpoint，`:391-396` 分配 seq、序列化并读取日志。设计保留处理 checkpoint 与上传 ACK 两个不同水位，避免中心恢复反向重建已处理事实。
- 补充生产者也已核实：`knowledge.ts:51-55,75-76` 通过 InboxStore 产生 `session_linked` 与 `self_evolution_review`；应按“所有当前生产调用者不得绕过事件表”的既定范围一起迁移，而非把它们退回未知扩展事件。它们只记录真实维护关联与结果，不改变维护执行。
- 生产装配可达：`apps/node/src/main.ts:89-90` 的 KnowledgeUpdates 与 `:382-383` 的 GlobalAgent 均通过 `onWork` 唤醒同一个 WorkSync，`:492` 启动上传。M3 的真实 projection→InboxStore→WorkSync→IM→公开页用例因此有明确装配依据，不是只验证中心手造 fixture。

#### 传输、decoder 与原始身份

- `packages/personal-assistant/src/work-sync.ts:83-169` 已使用独立 HTTP、持久 cursor、批量和基于原 JSON 字节的分段 hash；中心回退时从留存日志补缺口，不降低本地已确认水位。复用现有 Part/Cursor/limits 并保留 16 MiB 上限合适，无需第二套协议或编码层。
- 中心 HTTP `apps/im-server/src/work-sync.ts:133-154` 批量入口和 `:155-223` 分段入口最终调用同一个 Work.append；后者在重组完成后验证完整 hash 和 event 身份，并重新认证当前机器 binding。旧 WS 在 `gateway.ts:415-419` 经已注册连接身份检查后进入相同 Work owner。共用 decoder/WorkRecords 可以消除入口漂移，不能替代这些现有授权和最终提交前复查。
- design:98,100-101 明确 decoder 返回原对象、不补默认字段、不重排或裁剪，并区分已知与未知事件；已提交重复比较、历史身份-only 跳过、吊销跳过仍由拥有数据库事实的 WorkRecords 决定。这能同时保留有限生产契约与历史扩展兼容，不需要公开 string fallback。
- 已检查 `work.ts:142-193`：已落盘事件比较原 event/type/session/turn/payload，已确认但未存内容的序号跳过，撤销内容仅保留必要 session 身份后推进共享 journal。设计显式保留这一区别，不能以“严格类型”为由重新回放撤销内容或把合法旧省略视为缺失必填项。

#### 持久化、投影与公开页面

- `work.ts:103-232` 现有 append 在同一 SQLite 事务内完成注册、日志插入、投影和水位更新，之后广播。WorkRecords 仅依赖 DatabaseSync、返回 ACK 与 affected roots，facade 提交后按权限广播的拆分保留原子性，且不把 Gateway/浏览器对象带入持久模块。
- `work.ts:64-99` 的注册冲突、子父关系与 PA 新主会话取代、`:42-51` 的 running/waiting_permission→unknown 恢复都可由数据库 owner 保留；无需通用 Repository 或运行时端口。
- `work.ts:234-418` 的已知事件投影包含 `turn_start`、`run_*` 别名、call_id/tool_call_id、model/model_id、usage 缺省、permission 嵌套字段及未知事件通用 item。设计保留这些分支与原附加字段；未知事件仍依原 turn/control 规则展示，不应误解为给所有无 turn 未知事件新增展示行为。
- `work.ts:419-514` 的 items/turns/view 确实把 SQLite JSON 列转成公开对象；`work.ts:774-825` 在用户页和分页入口做空间/PA owner 检查；permission route 另有 owner、epoch、lifecycle 检查。具名记录与公开 view 分离可以在这些实际消费者间落实，facade 保留在线/同步状态与用户/Agent 查询控制足以避免数据库模块反向依赖 ImContext。

#### 契约、milestone 与验证

- 已对照 `docs/specs/im/agent-work.md` 的完整参数/结果、未报告统计、原生替换不重执行、主子归属、刷新分页、补传独立与恢复完整性，以及 `gateway-relay.md:271-309` 的 Work 专用机器身份例外和吊销。新增三个 Requirement 是这些现有行为的不变性验收，no spec delta 可成立。
- M3 为完整纵切，新增共享类型后迁移生产者和中心 owner 的顺序明确；不需要机械拆层。骨架只含 `.gitkeep`，未伪造执行记录。此前 design 开头的“两阶段/Work 保留现状”描述原 M1/M2，追加的明确 M3 范围优先；不影响当前实施理解。
- 编译负例覆盖 type/payload 错配、身份缺失和记录/公开 view 混用；真实链覆盖主子、工具完整结果、统计、重启重放；三种入口覆盖畸形稳定字段不推进水位，并要求旧别名/合法省略/null/未知扩展/字节保真。这与本次类型和职责风险相称。
- 基线可复用保护已阅读：IM `work-sync.test.ts:62-150` 的重复身份、分段工具、重启、hash/授权；PA `work-sync.test.ts` 的恢复中心缺口与游标异常；`tenancy.test.ts:186-201,252-269` 的吊销后共享 journal 与重新授权；`e2e/control-work.test.ts` 的真实认证 WS Work 流。未在本轮重新执行。
- 不改变 UI、schema、协议版本或序列化算法；无需 prototype、迁移脚本或生产写入验证。产品验收使用相同公开 HTTP/WS 接口读取结果；不能用本次 Approved 代替实施后的产品与静态门禁。

#### Agent Context Design Review

- Mode A，范围限定 Work 的事实投影/恢复及维护事件身份，不扩展到 Prompt 内容设计。
- Work 是已有原生事实的产品记录；design 保留 `logicalEvents/workSuffix/workCheckpoint` 的选择和更新语义、已完成工具原始结果，以及维护 session_linked 的真实父子身份。模型查询/指令/审批职责留在 facade，未改变模型输入、工具 schema 或模型目录。
- 因此不要求为这次行为兼容重构新增模型语义评测。设计已经要求原生替换不被当成再次执行、stop/重启仅恢复记录的保护；实际实现若更改选择、裁剪或恢复时机，须按真实 delta 重审。本轮没有 provider 输入或模型行为运行结论。

### 历史问题闭环

- Round 1 无 CRITICAL/WARNING；R1-R1/R1-R2 为可选建议，作者已记录采纳与实施验证，不属于本轮新增 Work 范围的未解决问题。
- 未发现 M3 使 R1 配置/RPC 设计结论失效；实现门禁仍按各自原版本保留，不外推为 M3 已验证。

### Issues

无。

### Recommendations

- **R2-R1（可选）**：M3 的最终验证记录把 `KnowledgeUpdates` 两种生产事件及 `tenancy.test.ts` 的撤销/重新授权共享 journal 用例一起列出。它们已被本设计的“完整生产链/权限恢复保持”范围覆盖；显式列名有助于避免只运行 projection/global-agent/work-sync 文件而漏掉旁路生产者和身份-only 分支，不要求新增流程或重复测试。

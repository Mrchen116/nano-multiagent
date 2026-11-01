# feat-680 设计审查

## Round 1

- Reviewer：独立 `change-design-reviewer`（Codex，`/root/feat680_design_review`）；包含同一 reviewer 的 `agent-context-review` Design Review。
- review_mode：full；mode_reason：Gate 2 首轮，审查全部需求、设计、delta 和 milestone。
- started_at：2026-10-30T11:42:39+08:00；completed_at：2026-10-30T11:43:20+08:00；duration：约 41 秒。
- Verdict：**Issues Found — 0 CRITICAL / 2 WARNING**。
- 基线：`2b208eccf43b269242c6f1101c539fb4e0f8bd4f`，受审的 `design.md`、delta 和 M1 骨架为工作区未提交内容；本轮是静态设计审查，不声称已运行实现或真实模型。

### Coverage 与证据

- 对照 `spec.md` 的五项范围与用户授权，核查了字面多词、精确短语、相关性与时间排序、无日期截断、组合过滤、来源回查、多页、当前权限、未读不变和失败/覆盖范围。两个阻断项见下。方案对中文短词及字符语义、默认排序、同分排序、时间边界和空结果范围有明确决定；不把外部未同步历史说成查全。
- 从实际产品入口核对 `packages/dsh-integration/src/global-mode.ts:25-26` 的 root 工具 schema、`packages/personal-assistant/src/global-agent.ts:411-419,546-551` 的身份和 relay、`packages/personal-assistant/src/tool-references.ts:47-57,71-75,105-109` 的引用处理、`packages/personal-assistant/src/external.ts:181-182,268-282,323-341` 的外部路由/镜像、`apps/im-server/src/work.ts:94-125,164,181-221,254-347` 的授权、筛选、快照和分段投影，以及 `apps/im-server/src/personal-agent.ts:47-50,74` 的来源政策和外部身份。保留每页重校验、从 IM 事实表按需查找和受信宿主决定权限的边界是合适的；没有必要为本期引入另一套索引同步或外部历史服务，但容量仍须按 M1 的隔离测量验证。
- Agent Context：consumer 为 Global/PA 主 Agent，surface 为工具 schema、结果及续查引用。设计选择按需检索而非常驻注入，规定历史非授权、身份由宿主派生、分页和错误状态可见，并要求实际 schema/renderer、引用往返和隔离真实模型任务；但外部 target 和真实发送人的“发现 → 调用 → 结果”尚未闭合（见两个 findings）。没有真实实现、模型运行或 provider 证据，因此只判断方案与现有代码，不断言实际模型表现。
- `specs/gateway/global-agent.md` 以 ADDED 指向正确的 `docs/specs/gateway/global-agent.md`；现有 PA 和 Inbox 非消费条目仍保留，无需覆盖既有 Scenario。新增条目的发送人和上下文承诺需要随 findings 的设计修订继续核实。无前端变化，不适用原型检查；无一次性业务数据迁移，不需要 deployment-prompt。
- `M1-search/.gitkeep` 是设计阶段允许的空 milestone 骨架；单 milestone 无并行冲突，runbook 指向隔离 daily 及关闭命令，设定真实模型不可用时不以 stub 冒充。退出标准包含权限、镜像、分段、规模与产品旅程，但应补足 findings 中的外部身份及 target 组合场景。方案尚未实现，性能及端到端验收资源可用性留待执行时核实。

### Issues

#### R1-W1 — 外部聊天 target 在定向搜索路径上没有解析为影子会话

- 严重度/证据状态：WARNING / CONFIRMED（静态接口缺口）。Context surface：工具参数、target 引用及结果。
- 位置：`design.md:61-63,71-79,112-120`；`spec.md:61-66`。
- Agent 需要能从 Inbox、`info` 或已知聊天取得可直接用于 `search` 的 target，并结合消息/发送人/时间搜索。当前短引用 `c_f_` 解码得到的是 `external:...`，而不是 IM shadow ID（`tool-references.ts:47-57,71-75`）；外部拦截只处理 `info` 和 `read`（`external.ts:268-282`），`search` 透传，IM 按传入 target 查 `conversationAccess`（`work.ts:164,254-256`）。已绑定的 shadow 映射在 `external.ts:325-329`。
- 本设计仅规定对携带锚点的 `read` 将外部 target 解析到 shadow；没有对 `search` 作同样规定。于是用户从已知飞书聊天请求定向搜索时，即使历史已经镜像也会得到不可访问，或实现者必须自行补做未设计的身份转换；按现有代码事实可确定这一缺口，并非模型必然误解。
- 建议：明确针对定向 `search` 的 external target → 当前 Agent 绑定 shadow 的可信解析、无镜像时可辨认失败、续页身份绑定和 IM 当前权限复核；在 M1 中以真实外部 target（含短引用）覆盖组合过滤、续页和撤权。维持现有安全边界，不将本地引用本身当作授权。

#### R1-W2 — 外部镜像发送人过滤仍指向代记用户，无法按真实发言人筛选

- 严重度/证据状态：WARNING / CONFIRMED（静态接口与数据事实）。Context surface：发送人参数的发现、身份与过滤语义。
- 位置：`design.md:20-22,43,49-51,71-89,120`；`spec.md:61-66`；delta `specs/gateway/global-agent.md:7,13-15`。
- Agent 应能使用已知的真实发送人和聊天、时间组合过滤，且结果不得混入其他发送人。现有 `participant_id` 只匹配 `messages.sender_user_id`（`work.ts:257-264`）；外部入站镜像将该字段统一写为 node owner，而真实外部身份写入 `sender_source_id`（`external.ts:340-341`、`message-records.ts:163-176`）。现有结果虽能给出 `sender.source_id`（`work.ts:306-316`），将其填进现有 `participant_id` 也不会匹配；填代记 owner 则可能混入同群其他人的消息。`external.ts:270-279` 的 info 也不提供外部成员列表。
- 设计仅复用“现有过滤”并新增 `keywords`、`sort`、锚点，未定义外部真实发送人的可发现标识、作用域及其与内部 user ID 的匹配规则。因而已镜像飞书历史也不能满足明确的发言人组合查询，模型无法仅靠现有 schema 正确填写参数；这不依赖推测模型行为。
- 建议：决定并说明可从哪些可见结果或其他可信入口取得外部发送人标识，如何在聊天/平台作用域内区分并匹配 `sender_source_id` 与内部 `sender_user_id`，以及身份未知时如何如实表达限制；避免按显示名猜测身份。M1 验证同一外部群两个真人同词、指定其中一人的组合查询，以及内部 IM 发送人过滤不回归。

### Recommendations

无。

### Author Resolutions

- R1-W1 — **accepted**。`tool-references.ts` 的短引用只还原外部 target，`external.ts` 的本地 query 不处理 search，IM 无法直接以 `external:` 找到会话。已在 `design.md` 决策 4 和 M1 明确当前 Agent 的可信 shadow 映射、未同步失败、快照身份与重新授权，并覆盖短引用和续页。
- R1-W2 — **accepted**。镜像消息以 `sender_user_id` 保存代记 owner，真实飞书发言人保存在 `sender_source_id`。已在决策 4、接口和 M1 区分内部/外部发送人，明确结果中的可发现标识、单聊天范围、缺失身份的处理及互斥，避免显示名猜测和代记账号混入。

## Round 2

- Reviewer：独立 `change-design-reviewer`（Codex，`/root/feat680_design_review`）；同一 reviewer 执行 `agent-context-review` Design Review。
- review_mode：full；mode_reason：修订增加 `conversations` 共享工具参数及外部 target 路由，影响公共接口、模型消费与 milestone，按技能要求复核全范围及变化的组合关系。
- started_at：2026-10-30T11:44:21+08:00；completed_at：2026-10-30T11:44:35+08:00；duration：约 14 秒。
- Verdict：**Approved — 0 CRITICAL / 0 WARNING**。
- 基线：`2b208eccf43b269242c6f1101c539fb4e0f8bd4f` 加受审工作区未提交设计；这是设计判断，未运行实现或真实模型。

### 历史问题闭环

- **R1-W1 — closed**。Author Resolution accepted；`design.md:61-63,75,125` 现明确先按当前 Agent 解析短引用和已绑定外部 shadow，再用 shadow 进行定向搜索、续页重解析、IM 授权及快照身份核对；无绑定/未镜像为可辨认失败。对应当前 `tool-references.ts:47-57,71-75`、`external.ts:268-282,323-329` 的实际路径及 `work.ts:119-125,181-211,254-256` 的授权和查询身份；M1 覆盖短引用、定向过滤、续页和撤权。映射不是授权，读取及每页仍须经 IM 检查。
- **R1-W2 — closed**。Author Resolution accepted；`design.md:65,75,80,88,125` 现区分内部 `participant_id` 与外部 `sender_source_id`，后者限定单个外部 target，明确从结果 `sender.source_id` 获取、不能按名称猜测、未知身份先不按人过滤以及互斥、快照身份。对应当前 `work.ts:262,303-315` 与 `external.ts:340-341` 的数据事实；M1 覆盖同群两人、未知身份与内部筛选回归。模型可先搜索结果并消歧，已有筛选 ID 不授予访问权限。

### Coverage 与证据

- 全范围复核首文档、`design.md`、delta 和 milestone：多线索及精确匹配、时间/相关性排序、旧历史、过滤交集、来源/上下文、快照续页、权限变化、未读不变、已同步历史与错误界限均在设计和 M1 中有承接。改动未改变用户确认的五项范围；delta 保持 ADDED 至 `docs/specs/gateway/global-agent.md`，用户可观察契约与修订兼容。其他未变动的现状和架构证据沿用 Round 1；本轮重新检查其与新 target、发送人参数、快照与权限的交互。
- 模型消费链：schema 将解释身份来源和约束，结果暴露发送者来源与可回读 target；已知外部 target/来源 ID 经宿主映射后进入 IM，续页使用相同解析后身份并重查权限，空结果限定于已同步范围。身份未知可先不按人筛选并说明限制。`design.md:84-94` 要求捕获实际 schema 和 renderer、验证引用往返和隔离真实模型行为；本轮无实际实现或模型证据，不将方案判断说成运行验证。
- 职责仍由 Gateway 做可信引用/绑定解析、IM 做过滤与授权，复用现有来源身份与消息事实，无额外身份服务或搜索索引。无迁移、前端改动或并行 milestone；`M1-search/.gitkeep` 与隔离 daily runbook 保持有效。实施后的性能、真实模型和产品旅程结果仍需按 M1 退出标准取得。

### Issues

无。

### Recommendations

无。

### Author Resolutions

复核 Round 2 的覆盖与结论，无遗留 finding 或需要采纳的建议；设计产物在该轮后无实质修改，Gate 2 通过。

## Round 3

- Reviewer：独立 `change-design-reviewer`（Codex，`/root/feat680_design_review`）；同一 reviewer 执行 `agent-context-review` Design Review。
- review_mode：full；mode_reason：本轮变更 `conversations` 共享结果接口、恢复与 milestone，故复核全部契约及受影响消费链，而非仅核旧问题。
- started_at：2026-10-30T11:53:07+08:00；completed_at：2026-10-30T11:53:43+08:00；duration：约 36 秒。
- Verdict：**Issues Found — 0 CRITICAL / 2 WARNING**。
- 基线：`878380d12375a50d1cbc6d8afedfc0df9887b281` 加 `design.md`、delta 的未提交修订。本轮静态审查设计与现有实现，未运行新实现或真实模型。

### 历史问题闭环

- **R1-W1 / R1-W2 — 保持 closed**。本轮 `design.md:61-67,85-94,137` 保留按 Agent 的外部 target 到 shadow 映射、续页重授权、外部发送人作用域与 M1 场景；引用映射后精简结果的变动没有撤销这些约束。依据沿用 Round 2，并对照 `tool-references.ts:71-75,90-109`、`external.ts:268-282,323-341` 和 `work.ts:119-125,181-211,254-264`。Round 2 无存活问题。

### Coverage 与证据

- 用户本轮确认允许省略无后续与完整消息的冗余状态；设计保留 `next_cursor` 存在时续页、IM 范围限制、权限检查和不消费 Inbox。`spec.md` 原有多词、排序、筛选、来源、非消费和权限场景不变；delta 新增完整/分段 scenario 指向既有 gateway canonical target。相关性、排序、范围与职责的未变证据沿用 Round 1/2。
- 从实际产品入口核对：`global-mode.ts:25-26,32-42` 的工具及 JSON renderer，`global-agent.ts:411-419,459` 的引用与 relay，`tool-references.ts:19-35,71-75,90-109` 的持久短游标，`work.ts:181-221,270-347` 的快照、part 预算、附件、顺序与返回，`external.ts:75-96,268-282` 的缓存原始消息，`policy/sources.ts:23-30,69-93,188-192` 和 `policy/codex-context.ts:44-77,115-125` 的历史分发、恢复与有标记截断。新设计明确单页合并、跨页部分序号、对附件只宣称描述完整、预算不能空转及权限/内容变化；但以下两处状态尚不能闭合。
- Agent Context Design Review：consumer 为主 Global/PA Agent 与后续授权 reviewer；surface 是 `conversations` 的 schema、投影和历史证据。正常新快照的示例表达首/末分段、来源及按原参数续页，历史按 untrusted evidence 保留 partial 和发送者，并要求验证实际 renderer、审核/恢复；没有实现与模型运行，无法证明实际交付或模型行为。外部缓存未知完整性和旧游标恢复的可执行语义见 findings。
- 无前端变更或一次性数据迁移；M1 和隔离 runbook 继续覆盖核心旅程，但应增加下列状态的验证。无运行时性能或真实模型结果，本轮不替代实施及产品验收。

### Issues

#### R3-W1 — 旧的跨页游标没有内容指纹，续读与一致性承诺冲突

- 严重度/证据状态：WARNING / CONFIRMED（旧游标的数据结构和设计矛盾）。Context surface：模型工具结果、跨版本续页与恢复。
- 位置：`design.md:55,77-80,137`。
- 期望：模型恢复一条跨页消息时，应知道各页是否可被视作同一版本；设计规定续页绑定内容指纹、变化则拒绝，同时要求旧游标仍按原规则用完。
- 证据：当前 `work.ts:181-221` 的旧快照仅保存查询身份与 ID 列表，游标仅含 snapshot、offset、part；`work.ts:287-295` 每次按当前正文和附件重新构造 parts。`tool-references.ts:19-35,71-75` 将游标短引用持久化，并不保存旧正文指纹。故升级前首段已交付、消息随后变更、升级后用旧 cursor 续读时，无法与首段版本比较；直接采用新 `partial` 区间并在最后省略 `next_cursor`，可能让模型把不同时点内容当成完整消息。此处确认的是状态缺口，不断言该场景已在运行中出现。
- 建议：明确旧的**消息内分段** cursor 如何安全续读及向模型提示不确定性（例如对无法验证的分段要求重新读取该消息），并与旧 cursor 兼容承诺协调；普通位于消息边界的旧游标可按既有规则继续。M1 增加升级前首段、内容改变及不变两种续页，并验证错误或状态、重新读取和权限约束。

#### R3-W2 — 外部缓存完整性未知时的模型可见状态没有定义

- 严重度/证据状态：WARNING / CONFIRMED（结果契约未闭合）。Context surface：外部缓存消息投影、可执行恢复和历史审核。
- 位置：`design.md:77-81,85,137`。
- 期望：模型应区分完整消息、可按区间续页的部分消息与外部缓存中无法确定完整性的消息，知道能否补读；授权审核/恢复也需保留这一区别。
- 证据：设计的唯一部分消息格式 `partial` 要求实际的 `first_part`、`last_part`、`total_parts`（`design.md:79-80`），但对缓存又明确“不臆造 parts”且未知时“显式标明不完整”（`design.md:81`），未指定未知状态的字段、含义及无游标时如何恢复；现有本地缓存直接返回 `row.input.message`（`external.ts:280-282`），它来自将正文与图片分别归并的接入表示（`external.ts:83-94`），并非带 IM 分段数的快照。没有确定的计数时不能填充所规定的部分区间，也不能省略标识而被理解为完整。
- 建议：为缓存内容未知/不完整规定明确、模型及历史审核均能保留的状态和恢复路径，区分其与有精确区间的 `partial`；说明如何通过已同步历史定位或在无法定位时如实报告。M1 需覆盖本地缓存（含正文与图片、未同步/未知完整性）、模型可见投影和审核/恢复，而非只测 IM 分段。

### Recommendations

无。

### Author Resolutions

- R3-W1 — **accepted**。当前旧游标只有 offset/part，无法重建此前交付内容的版本。已在 `design.md` 决策 3/6 约定旧游标停在消息内时拒绝续读并重查、消息边界沿原快照续页，以及后续跨页指纹与权限复核；M1 覆盖旧内容改变和不变两种情形。
- R3-W2 — **accepted**。外部本地缓存并无 IM part 区间可证完整。已在决策 6 定义 `partial: {"status":"unknown"}`、缓存范围、可信镜像映射可回查及无映射时不能猜测的恢复路径；M1 增加正文/图片、镜像/未同步、模型与审核恢复覆盖。

## Round 4

- Reviewer：独立 `change-design-reviewer`（Codex，`/root/feat680_design_review`）；同一 reviewer 执行 `agent-context-review` Design Review。
- review_mode：full；mode_reason：本轮新增模型可见的未知状态，调整旧游标兼容及 milestone；涉及共享结果接口与恢复，复核相关端到端路径和全范围契约。
- started_at：2026-10-30T11:54:48+08:00；completed_at：2026-10-30T11:55:02+08:00；duration：约 14 秒。
- Verdict：**Approved — 0 CRITICAL / 0 WARNING**。
- 基线：`878380d12375a50d1cbc6d8afedfc0df9887b281` 加本轮未提交设计与 delta；静态设计结论，不代表实现或模型运行通过。

### 历史问题闭环

- **R3-W1 — closed**。Author Resolution accepted。`design.md:55,80,137` 对旧消息内游标 `part > 0` 明确不返回片段、报错并重查，不依赖无法重建的历史指纹；`part = 0` 保留原快照排序，后续新分段建立指纹，均先重新核验身份与权限。`work.ts:181-221,270-283` 确认旧游标有 `part` 与快照顺序，允许实施识别此边界。M1 覆盖消息内容改变/不变、边界续查、权限重核及重读。
- **R3-W2 — closed**。Author Resolution accepted。`design.md:81,104,137` 为缓存无法确认完整性规定 `partial.status=unknown`，不伪造分段位置，并区分本地缓存范围、可信镜像可回查与无映射/未同步的说明；要求未知状态与真实来源保留至授权审核和恢复。`external-store.ts:15,24-25,35-47` 的 chat shadow 与 inbound mirror、`external.ts:323-342` 的写入路径提供真实映射依据；M1 涵盖缓存文字和图片、已镜像/未同步、模型投影及审核恢复。
- **R1-W1 / R1-W2 — 保持 closed**。本轮继续保留由当前 Agent 映射 shadow、定向查询及当前 IM 授权、外部发送者作用域及对应验证；见 `design.md:61-67,137`，其余证据沿用 Round 2/3。

### Coverage 与证据

- 重新对照 spec、delta、设计和 M1：本轮没有改变多词、排序、过滤、来源和 Inbox 非消费的用户要求；delta 的完整/分段场景与当前 canonical gateway target 一致。对无后续/完整消息省略状态仍保留明确的 `next_cursor` 缺省语义，已同步范围与外部缓存范围各自限定；普通消息内分段、附件描述、错误、权限变化及恢复均有设计与验证承接。未受影响的现状、架构与依赖证据沿用 Round 1–3。
- Agent Context Design Review：模型能区分带区间的部分消息和完整性未知的缓存消息，前者沿 cursor 继续、后者通过可信映射回读或如实说明限制；旧 cursor 错误明确引导重新查询，不能把历史片段升级成新授权。`policy/sources.ts:23-30,69-93,188-192` 的投影及恢复路径保留结果对象，`design.md:80-81` 明确须保留来源和 partial，M1 要求在实际 renderer 与审核/恢复验证。上述为方案及现有代码判断，实际模型输入、provider 行为和新实现仍待 M1 取证。
- Gateway 继续承担可信映射及模型投影，IM 负责授权、快照和当前内容；复用已有缓存映射及历史审核机制，不新增索引或身份服务。单 milestone、隔离 runbook、无前端和无一次性迁移的判断未变；实际容量和验收资源仍须实施时确认。

### Issues

无。

### Recommendations

无。

### Author Resolutions

复核 Round 4 的覆盖和历史问题闭环，无遗留 finding 或需要采纳的建议；受审设计在本轮后无实质修改，Gate 2 通过。

## 后续用户决定：移除跨页内容指纹

用户确认无需对生成中消息跨页变化做内容版本校验；设计已取消内容指纹和旧分段游标拒绝规则。上文相关审查结论保留为当时的评审记录，不再作为当前设计约束。

## Round 5

- Reviewer：独立 `change-design-reviewer`（Codex，`/root/web_search_design_review`）。
- review_mode：full；mode_reason：用户追加 Web 用户旅程，涉及共享搜索实现、用户权限与新接口，需复核受影响的产品边界。
- started_at：2026-10-30T15:16:00+08:00；completed_at：2026-10-30T15:17:00+08:00；duration：约 1 分钟。
- Verdict：**Issues Found — 0 CRITICAL / 2 WARNING**；本结论仅针对设计，非实现或真实产品验收。

### Coverage 与证据

- 核对本轮需求、设计、Web delta、原型源码及现有 `conversationAccess`、`Messaging.conversations`、聊天定位入口。IM 应拥有消息匹配和排序，Agent 与用户使用各自主体计算范围，复用查询而不借用 Agent 权限；无需新增搜索服务或索引。
- Agent Context：共享 SQL 将同时用于 Agent 工具与 Web 用户，设计要求不改变工具契约；实施验证仍需覆盖 Agent 的多词、排序与当前权限，防止提取逻辑改变模型可见结果。旧轮未受影响的 Context 与回查设计证据沿用 Round 4，跨页 hash 按后续用户决定移除。
- 原型视觉及交互**未验证**：应用内浏览器明确拒绝 `file:` 协议且禁止绕过；本轮没有通过本地服务或其他浏览器绕过，也不能声称已实际观察原型。用户提供的截图可证明现有入口，不证明新增原型体验。视觉审查结果保留缺口，独立判断须待可获准的呈现方式或实际产品验证。

### Issues

#### R5-W1 — 用户可访问的搜索范围尚未落到可枚举的会话集合

- 位置：`design.md`「用户追加：Web 会话与消息搜索」；`specs/im/web-chat-ux.md`。
- 证据：设计要求搜索“当前用户可见”的历史，`conversation-access.ts` 的 `conversationAccess` 对当前有公司资格的用户允许未加入的公开群，且成员有历史读取资格时允许已解散会话；`messaging.ts` 的默认 `conversations(..., 'joined')` 则只列已加入/特定观察会话并排除已解散会话。
- 后果：若实现直接从现有列表收集候选，仍可读取的公开群、已解散历史会被无提示遗漏；若改成无约束遍历又不能从设计判断清楚预期作用域。作者在审查期间已说明目标是所有 `conversationAccess` 当前可读会话，含未加入公开群及仍可读解散群；需写入设计与验收并保留实际权限检查。

#### R5-W2 — 首文档保留旧的 Web 搜索非目标，与追加范围冲突

- 位置：`spec.md`「范围与非目标」。
- 证据：同一文档新加「Web 聊天记录搜索」，末尾却仍将“面向人的全局搜索界面”列为非目标。
- 后果：后续实施和验收无法以首文档确定此次用户授权范围；应保留原始决策记录，同时更新当前范围与非目标。

### Recommendations

- 说明侧栏 People、Agent、Group 分类与新增消息结果的关系，并用真实入口验证，避免选中分类后结果来源与筛选状态冲突。搜索本身不消费未读与点击结果后打开聊天的既有已读行为宜分别陈述。

## Round 6

- Reviewer：独立 `change-design-reviewer`（Codex，`/root/web_search_design_review`）。
- review_mode：closure + delta；mode_reason：复核 Round 5 修订并检查新增类别过滤及接口的闭合。
- started_at：2026-10-30T15:17:30+08:00；completed_at：2026-10-30T15:18:30+08:00；duration：约 1 分钟。
- Verdict：**Issues Found — 0 CRITICAL / 2 WARNING**；Gate 2 尚不可判定通过。

### 历史问题闭环

- **R5-W1 — closed**。`design.md` 本轮追加明确按 `conversationAccess` 当前可读范围枚举，包含未加入公开群与仍可读的已解散聊天；不以 joined 列表代替权限集合。权限仍须在真实实现和续页测试中核对。
- **R5-W2 — closed**。`spec.md` 已从当前非目标移除 Web 搜索，并保留原始用户澄清记录及新增确认。

### Coverage 与证据

- 其余查询职责、权限边界、Agent Context 影响判断及消息定位证据沿用 Round 5。本轮新要求类别服务端过滤，检查了 `chat-types.ts`、`conversation-sidebar.tsx` 的当前分类语义。
- 原型仍未视觉或交互验证：`file:` URL 遭浏览器安全策略拒绝，且拒绝说明禁止以本地服务、其他浏览器或其他方式绕过。用户现有产品截图不构成新增设计画面证据；不存在受审原型的实际走查证据。

### Issues

#### R6-W1 — 追加的分类过滤没有完整定义请求与分类口径

- 位置：`design.md`「用户追加：Web 会话与消息搜索」。
- 证据：新设计要求服务器按选中类别过滤后分页，但给出的 GET 仅含 `q` 与 `cursor`；结果字段中的会话类型无法单独表示当前侧栏全部分类：`classifyConversationKind` 对 direct 还依赖 `direct_kind`，对 group 依赖参与者是否全是 Agent（`chat-types.ts:283–294`）。
- 后果：用户选 People、Agent、Group 或 Network 后，服务端无法从当前约定稳定重现现有分类；先分页再在前端筛选会漏结果或制造空页。应明确请求类别、采用与现有分类等价的口径，以及分页/切换分类验证。

#### R6-W2 — 必要原型视觉审查没有可用证据

- 位置：`design.md`「用户追加：Web 会话与消息搜索」及 `prototype.html`。
- 证据：新增 Web 界面的原型打不开，无法独立走查其布局、响应式及状态；`change-design-author/references/prototype-and-runbook.md:77–79` 要求原型实际渲染走查，且明确渲染工具不可用时只能标记“视觉未验证”，不能将必要视觉检查推迟到实施验收。
- 后果：不能以静态源码或旧产品截图宣称新交互符合体验契约；需通过安全策略允许的方式获得实际视觉证据，或由用户明确调整相关要求。当前浏览器对本地文件的自动审批已拒绝，不得通过其他浏览器、本地服务器或间接执行绕过。

### Recommendations

无。

## Round 7

- Reviewer：独立 `change-design-reviewer`（Codex，`/root/web_search_design_review`）。
- review_mode：closure；mode_reason：复核 R6 设计修订与用户对视觉验证方式的明确调整。
- started_at：2026-10-30T15:19:00+08:00；completed_at：2026-10-30T15:19:30+08:00；duration：约 30 秒。
- Verdict：**Approved — 0 CRITICAL / 0 WARNING**，准予按调整后的验证方式实施；不表示原型或真实产品视觉已通过。

### 历史问题闭环

- **R6-W1 — closed**。`design.md` 已定义 `kind` 请求参数及 `all`、`direct-user`、`direct-agent`、`group`、`agent-network`，要求在分页前按与 `classifyConversationKind` 一致的 `direct_kind` / participants 规则过滤；实施需测试分类、切换与分页。
- **R6-W2 — superseded**。用户明确决定“可以，检查实际界面”，授权跳过本地原型阶段的视觉审查，改查实际 Web 界面。原型的视觉与交互仍未验证，不能将此轮结论表述为原型已通过；实际界面的桌面、窄宽度、关键状态和操作需在实现后独立验收，未取得证据不得宣称体验已验证。浏览器对本地文件的自动审批拒绝仍有效，不得绕过。
- **R5-W1 / R5-W2 — 保持 closed**。本轮未改变用户可读范围和需求增量。

### Coverage 与证据

- 按 R6 仅复核类别请求、分类语义及用户对验证方式的调整；权限范围、共享查询与 Agent Context 的静态判断保留 Round 5/6 的证据。设计为实现提供了必要的权限、排序、分页和界面行为边界。
- 视觉判断尚欠真实 Web 证据；这是用户同意的验证顺序调整，不是豁免产品体验验收。

### Issues

无。

### Recommendations

无。

## Round 8

- Reviewer：独立 `change-design-reviewer`（Codex，`/root/search_ux_design_recheck`）。
- review_mode：delta；mode_reason：用户试用后变更 Web 搜索的信息组织与移动返回旅程，搜索 API、权限及 Agent Context 未变；未受影响内容 `retained_from: Round 7`。
- started_at：2026-10-30T17:02:00+08:00；completed_at：2026-10-30T17:04:30+08:00；duration：约 2 分钟 30 秒。
- Verdict：**Approved — 0 CRITICAL / 0 WARNING**；仅表示修订后的设计可指导实施，不表示实际界面已验收。
- 基线：`76c455254c5452a045e54a64921a3f448bc0cb50` 加工作区的 spec、design 与 Web delta 修订。

### 历史问题闭环

- **R6-W1 保持 closed**：`design.md` 保留 `kind` 参数、分页前分类及权限复核；本轮搜索视图内分类仍同时限制会话与消息结果。
- **R6-W2 保持 superseded**：用户已授权跳过旧本地原型，改在实施后检查实际 Web 界面；旧原型并未因此通过视觉审查。R5-W1/W2 的范围与需求闭环沿用 Round 7。

### Coverage 与证据

- 对照用户反馈与 `spec.md`、`design.md` 新节：移动端明确切换占满可用空间的独立搜索界面，隐藏导航、固定 PA 入口、普通列表及创建入口；桌面在侧栏切换而保留聊天。清空留在搜索、退出恢复普通列表；从原消息返回搜索视图恢复关键词、分类、页数及位置，并逐页重查权限。输入、分组、关键词、空状态、加载、错误、续页与原消息定位均有决定；分类仅作用于搜索结果。该组织能直接回应用户所述的列表重叠问题。
- 核对真实产品组装入口：`chat-workspace-page.tsx:1122-1123,1193-1203,1286` 现以移动会话 ID 切换列表/详情，侧栏 props 中显式排除 PA，并在返回时回 `/chat`；`conversation-sidebar.tsx:112-155,171-185,214-235,259-261,368-379` 当前把搜索、筛选、固定入口与列表放在同一侧栏，结果恢复依赖前端缓存及重新请求。因此这次需改变搜索视图与返回状态，而非只调整结果样式。修订明确由 workspace 为搜索提供含 PA 的已加载会话；对不在列表中的可访问来源使用返回名称生成普通头像，不假定类型或增加请求，和 `chat-api.ts:25-27` 现有返回字段相容。
- Web delta 现为对 `docs/specs/im/web-chat-ux.md` 同名已有 Requirement 的 MODIFIED，保留原有权限、分页、年份及上下文 Scenario，并把移动返回明确改为搜索视图；不在设计阶段覆盖 current。设计第 21 行的 worker/reviewer 真实入口验证及修订段要求分别验证桌面与移动流程；原查询职责、权限边界和非消费行为证据沿用 Round 5–7。本次不改变 Agent 可见 Context、共享 API 或迁移。
- 本 reviewer 打开隔离 Web 标签时仅见登录页，未独立看到搜索界面；既有 `acceptance.md` Round 3、5 的旧版真实 UI 记录证明既有产品路径，不证明本次新设计画面。用户调整了原型验证顺序，故不将缺少新画面当作本轮阻断；实施后仍须在隔离实际界面分别走移动和桌面，检查进入、清空、退出、分类、状态、分页及定位后返回，取得可复查的视觉和交互证据后才能宣称体验通过。

### Issues

无。

### Recommendations

无。

### Author Resolutions

- Round 8 无遗留问题；接受 Approved。实施后仍须独立验证隔离环境中的桌面与移动实际界面。

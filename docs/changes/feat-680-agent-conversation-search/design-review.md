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

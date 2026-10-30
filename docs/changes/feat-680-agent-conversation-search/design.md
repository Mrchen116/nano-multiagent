# feat-680：Agent 聊天历史搜索 — 技术方案

> 对齐：[spec.md](spec.md)

## Changelog

## 现状分析

### 涉及范围

- `packages/dsh-integration/src/global-mode.ts` 注册 root 的 `conversations` 工具；schema 暴露 `query`、`keyword`、筛选和分页，结果经工具 renderer JSON 交给模型。PA 复用同一入口及自身来源提示。
- `packages/personal-assistant/src/global-agent.ts` 的 `query` 经 `conversation.query` relay 到 IM；`tool-references.ts` 对 target 和 cursor 做受 Agent 约束的短引用映射。`external.ts` 会对本地飞书聊天的 `info` 和 `read` 短路，后者只返回本地最近 50 条 inbound，不是 IM 的完整历史。`search` 则转发 IM。
- `apps/im-server/src/work.ts` 的 `Work.query` 负责主体校验、来源范围、历史搜索、原文投影及游标。当前查询用 SQLite `instr(lower(content),lower(?))`，先加载所有匹配消息再反转 rowid；分页快照存匹配 ID 及查询身份，每页重查当前数据。单消息 `read` 通过 `message_id` 定位，但无法围绕它读取前后文；`before_message_id` 没暴露在工具 schema。跨聊天搜索的每条结果有来源 ID 和 URL，但聊天名只在顶层单 target 返回。
- `apps/im-server/src/personal-agent.ts` 用主人参与且当前可读的来源与 PA 自身可访问来源取并集，并按 policy 排除；`conversation-access.ts` 是 IM 权限判断。`messages` 是事实源：`message-records.ts` 有流式增量、终态覆盖与删除等写入，外部消息先镜像；不可把外部平台未镜像历史说成已查全。

### 既有约束

用户确认首期五项；语义搜索、附件正文检索和面向人的全局搜索界面不在范围。用户授权架构师决策，并指出目前服务用户少于 100 人；用户数不代表历史消息数。PA 的参与/当前权限/排除策略、真实身份和来源、历史查询不改变已读与 Inbox 均不可削弱；根 Agent 权限和普通 Agent 的现有作用域不扩大。

### 可复用能力

复用 IM 事实表、主体/来源访问和现有快照、消息序列化、时间过滤与 tool references；改造搜索排序与分页投影。复用消息来源 URL、既有 `read` 及 relay，增加锚点前后文；不复制一套外部平台历史搜索。现有 FTS 相关能力并非本仓既有产品索引，不引入用于本期的索引维护链。

### 相关历史

已完成的 feat-616 为 PA 建立双身份和排除政策，并有双身份、2001 年历史和原消息链接的测试（`apps/im-server/tests/personal-sources.test.ts`）；feat-658 要求保持真实作者及代发来源。当前 feat-676 的设计拟复用 `conversations` 只读能力，本 unit 不改变其尚未完成的权限边界。

## 架构总览

```text
主 Agent → conversations 工具定义与结果 → PA/Gateway relay → IM Work.query
                                                          ├─ 当前主体与来源权限
                                                          ├─ 消息正文匹配、排序、快照分页
                                                          └─ 消息原文与锚点上下文
```

IM 的消息表和当前访问决策仍是唯一事实源；搜索是按需查询，不向模型常驻注入聊天。没有前端改动、额外常驻服务或外部搜索依赖。

## 关键决策

### 1. 首期使用现有 SQLite 直接查询，先验证真实容量

首期不新增倒排索引或搜索服务：在 SQL 先按可访问聊天、发送人、日期和匹配条件过滤并计算排序，只取轻量 ID、排序字段构造快照；仅对本页消息做现有完整投影。必要时增加 `(conversation_id, created_at)` 普通索引以服务范围条件；它不承担正文全文索引。消息实时写入、终态更新、删除与搜索天然同源，无额外回填和索引同步。

理由是用户规模小且历史规模尚未量化，两个字中文词在 SQLite trigram 下仍需扫描；现在引入全文索引、流式更新与历史回填会增加维护和部署成本，也不保证该主要案例加速。风险是文本扫描随历史增长而变慢，不能用用户数证明容量充足。设计阶段本机 Node v25.8.2、SQLite 3.51.3、内存库、100 个合成聊天共 10 万条、全范围双词查询、2,000 命中，仅 SQL 取轻量行的 10 次样本中位数 72.4 ms、最大 454.6 ms；这不是受支持 Node 版本、真实磁盘或端到端性能证明，也不包含排序/relay。实施须在受支持 Node、隔离磁盘和有代表性的广范围/高命中数据上记录端到端耗时、内存和对写入的影响；若无法满足实际部署需要，停止并回到设计，不静默加截断或任意日期窗口。未来依据测量另行设计索引与迁移。

### 2. 明确字面搜索语义，不假装是语义理解

现有 `query` / `keyword` 保留单个完整字面子串语义与 `keyword` 优先级；新增 `keywords` 数组表达多线索：去除每项首尾空白、丢弃空项并去重，至少一项出现即为候选，按命中不同关键词数排序。字符串按 SQLite 现有 `lower` 规则比较（ASCII 大小写不敏感；中文原样子串），不将标点、短中文词、编号解释为查询语法。字面子串支持中文、英文、符号和单字；不承诺分词、拼音、语义匹配或 Unicode 全部大小写折叠。单项 `query`/`keyword` 即准确短语模式；模型要找多线索时使用 `keywords`。`keywords` 与 `query`/`keyword` 同时传入报参数错误，避免含义不明；原有仅使用 `query`/`keyword` 的调用不变。空白查询保持原有无关键词过滤语义，不能将它表述为命中某个词。

新增 `sort`：`relevance`（默认）按命中关键词数降序、创建时间降序、消息 ID 稳定排序；`recent` 按创建时间降序、消息 ID 稳定排序。单短语命中数均为 1，按时间排序。相关性严格先于新近度，因此多线索旧消息不因单线索新消息被压过；同相关度优先近期。排序以消息时间为准，不用 rowid 假设时间。过滤条件均为 AND，时间边界沿用 `after` 含、`before` 不含的既有语义。

### 3. 固定搜索快照，同时每页使用当前授权和当前消息

首查记录查询身份（包括规范化关键词、排序和所有现有过滤）及按上述顺序排列的消息 ID；续页复用相同 ID 顺序和分段位置。绑定既有 Agent/动作/作用域，补上新参数，并拒绝游标与查询不一致。每页重算主体和可访问来源，重新检查消息仍存在且仍符合该查询，再作投影；被删除、变更不再命中、来源被排除或撤权的 ID 跳过，不把失权内容、摘要或数量泄露。首查后新消息或新获得的访问资格不进入已有快照，重新搜索才能看到。已有 `read`/`list` 的游标和搜索旧游标继续按原排序续页，但旧游标停在消息中间时按决策 6 安全中止并重查；搜索新游标的语义版本由后端识别，不能把旧游标按新排序续读。

权限是宿主决策，不由搜索结果、游标或提示词授予；每页仍经过 `conversationAccess`、PA `sourceAllowed` 和现有身份约束。搜索只暴露符合当前授权的候选；历史读取及锚点上下文同样复核权限。被撤回消息或查询失败不伪装成已查全。

### 4. 在现有工具内补齐模型可执行的回查路径

新增 `read` 的 `around_message_id`：要求 `target`，以同一可读聊天中的消息为锚，按消息时间/稳定 ID 返回锚点及前后各最多 5 条（不足即实际数量），每页沿用现有分段、预算和游标。锚点不属于 target 或不可访问时沿用 404，不跨聊天；已有 `message_id` 精确读取不变；锚点和 `message_id`、搜索参数冲突时报参数错误。结果按历史顺序，带同一消息投影、来源和分页状态；不得把片段误当整条。`external.ts` 对携带 `message_id` 或 `around_message_id` 的 `read` 不做本地 50 条短路，转发已镜像的 IM target，由 IM 进行权威校验；本地 external target 需先解析到已绑定 shadow ID，镜像尚不存在时明确返回来源未同步错误，而非用本地摘要冒充完整上下文。已有无锚点 external `read` 不改变。

定向 `search` 同样在 Gateway 用可信的当前 Agent 对应外部聊天记录解析 target：`c_f_` 先经既有短引用还原到 `external:`，再映射到该 Agent 已绑定的 IM shadow ID，才能转发 IM；无绑定或尚无镜像时明确报来源不可用，不当成空结果，也不信任模型填写的其他 Agent 映射。续页的查询身份使用解析后的 shadow ID，重做映射及 IM 当前授权检查；跨聊天搜索及普通 IM target 不改变。调用方可继续用原短 target 和 cursor，无需猜测 shadow。

发送人过滤区分内部和外部真实身份：`participant_id` 继续表示内部 IM 发送人 ID，仅匹配内部用户/Agent 身份，不将外部真人镜像中的代记 owner 误当真实发送人。新增 `sender_source_id` 用于外部真人，必须同时指定单个外部 `target`；仅在该聊天对应的外部平台作用域内按镜像保存的 `sender_source_id` 精确匹配，且与 `participant_id` 互斥。Agent 可从先前结果的 `sender.source_id` 取得该聊天真实发送者标识，再结合聊天和时间复查；外部 `info` 当前没有成员名册，不能仅凭显示名猜 ID，若尚无可靠标识则先不限制发送人搜索、读取结果后消歧，或如实说明无法按人确认。缺少真实来源 ID 的旧消息不会通过外部发送人筛选；查找身份未知的历史应采用不带发送人过滤的搜索。上述字段、互斥与不足通过工具 schema 说明，来源 ID 不授予读取权限。

跨聊天每条 search/read 结果补充来源聊天可读名称和可直接用于后续 `read` 的 target，并保留真实 sender、`source_time`、`source.url`、PA `owner_can_read`、participant/observer 和完整性等现有事实。由 Gateway 引用层确保新增 target 的短引用可往返；不能从 URL 猜 ID。对仅 PA 可读的来源遵循现有提示，不向主人呈现其无法访问的链接。

### 5. 覆盖范围和失败要可判断

成功搜索保留 `history_scope: im_history`，并在工具说明中明确只覆盖中心 IM 当前已同步记录、当前主体可访问的作用域；不能声称搜索了飞书服务端全部历史或证明不存在未同步来源。指定 target 不可访问仍返回拒绝/404，IM 断连或查询失败返回可辨认错误，绝不转换为空结果；可检测到镜像尚未同步时说明来源不可用。没有可检测的同步完整性信息时不编造“已全部同步”状态。空结果只表示已查询的 IM 范围内无匹配。来源排除及不可访问资源不暴露存在性。

### 6. 工具结果只在有后续或不完整时提示

用户确认：“可以，按你说的精简工具返回结果，更新 feat-680 设计并完成复审。”此处落实其对 `has_more: false`、`next_cursor: null` 和 `complete_message: true` 的反馈；既有查找范围、权限及模型必须能判断完整性的要求不变。

- 对本 unit 涉及的 `conversations` 的 `list`、`search`、`read` **模型可见成功结果**，有下一页才提供非空 `next_cursor`，无下一页省略该字段；`has_more` 始终不呈现。工具描述明确：成功结果缺少 `next_cursor` 表示该次快照无后续页，不代表外部未同步历史已查全；错误、超时或未收到结果不得解释为成功结束。`info`、其他工具和现有 IM 内部传输字段不因模型展示精简而改变。
- `search`/`read` 投影在单页内按同一消息合并连续返回的正文及附件 parts，保持原顺序、类型、来源和现有输出预算；无须跨页缓存或拼接模型历史。若本页包含该消息的所有 parts，省略 `complete_message`、`part_key` 和 `partial`；单页完整的正文加附件同样合并，不能只因为有多个 part 就标记不完整。
- 若本页仅含某消息的一部分，保留消息 ID、来源和按顺序排列的内容，并仅在此时附 `partial: {"first_part": 1, "last_part": 2, "total_parts": 3}`；序号从 1 开始、区间含两端，表示该页包含第 1 至 2 part、全消息有 3 part。其余字段与完整消息相同，不展示原 `complete_message` / `part_key`。模型可依据 `first_part > 1` 识别前页内容缺失，依据 `last_part < total_parts` 识别后续内容；后者必须有可用 `next_cursor`，以原参数续页。若只有前页缺失且没有下一页，可重新以该消息为锚点查询；不能把后续页单独当作完整原文。单 part 被预算拒绝时不得返回无法前进的空成功页；应返回明确错误。正文与附件是结构化内容：全部 part 均到达只代表描述/引用完整，不代表附件字节已被读取或图片已被模型看见。
- 内部 IM 返回及既有持久 cursor 继续保留满足分段、权限、审核和恢复所需的事实；IM 在每个 part 的内部结果补充总 part 数，延续既有零基 `part_key`，供 Gateway 映射为上述一基区间；精简在 Gateway 既有引用映射后的 `conversations` 模型投影完成，不能依靠模型自行推断内部缺失字段，也不改变 Inbox 的独立摄取/确认语义。聚合仅针对同一 `message_id`、同一来源的连续 parts；对新游标跨页消息在续页状态绑定其正文与附件描述的内容指纹，若续页时已改变则拒绝并提示重新查询，避免把不同时点片段拼成虚假完整消息。旧游标若 `part > 0`，无论当前内容有无变化均无法验证先前片段，返回明确错误并要求以原参数重新搜索或重新读取该消息；不得先返回消息文本或从当前位置冒充安全续页。旧游标在消息边界 `part = 0` 可按原快照排序继续，并从新产生的跨页续页状态开始保存指纹；两种情况均先复核当前主体与权限，不因恢复泄露来源。历史授权审查和恢复中的 `conversations_result` 必须保留 partial 与原始可信发送者、来源、代发等字段；不把历史消息变成新的授权。
- 外部聊天无锚点 `read` 的现有本地短路仍只读该来源最近最多 50 条 inbound，既非 IM 快照也没有完整分页。此结果需明确标注 `history_scope: external_cache` 和范围仅限本地最近记录，不能因省略 `next_cursor` 暗示 IM 或外部平台历史已读完；不臆造 parts 或完整附件。缓存消息无法证明其完整时标记 `partial: {"status":"unknown"}`，不提供 `first_part` / `last_part` / `total_parts`；这表示完整性未知，与已知分段不同，不表示附件已读。可用可信已镜像映射时同时返回可调用 target 与 IM message ID，Agent 可据此调用 `read` 原文/上下文；没有映射时不能猜 ID，可先在已同步 IM 来源中按已知文字搜索并核对来源，无法定位或来源未同步时如实说明未能核实完整原文。该未知标记及真实来源必须进入后续授权审核与恢复，不能被当成完整消息或新授权。

## 接口与数据流

工具 schema 在现有字段上增加 `keywords: string[]`、`sort: relevance | recent`、`around_message_id: string`、`sender_source_id: string`，描述动作适用范围、互斥关系、外部发送人标识的来源及其 target 约束、默认排序、精确模式、已同步历史边界、`next_cursor` 缺省语义、`partial` 分段语义和续页时沿用同样参数；`sender_source_id` 也纳入快照身份。示例：

```json
{"action":"search","keywords":["发布","周四","方案"],"sort":"relevance"}
{"action":"search","query":"ERR-42","target":"c_12345678","sort":"recent"}
{"action":"search","keywords":["发布","周四"],"target":"c_f_12345678","sender_source_id":"ou-example","sort":"recent"}
{"action":"read","target":"c_12345678","around_message_id":"m-example"}
```

流程：主 Agent 选择已有工具 → 宿主解析短 target/cursor，可信绑定身份 → IM 计算允许范围和过滤 → 首查形成稳定 ID 快照 → 当前页逐条校验权限并按现有消息语义投影 → Gateway 返回可执行 target 与 cursor → Agent 根据来源、完整性和分页信息决定续查或按锚点回读。查询缓存不作为授权依据；无结果或断连都不得产生新 Inbox 消费。持久历史结果是历史证据，不自动构成新的指令或发送许可。

### Agent Context：消费、生命周期与验证

Consumer 是 Global/PA 主 Agent；其他执行范围依旧由现有注册和宿主权限控制。变化发生在 schema、检索选择与结果的来源/排序/续页字段，而非新的常驻 prompt。当前模型只看到单字符串及结果；新 schema 必须说明 `query` 精确、`keywords` 任一匹配与命中数排序、`recent`、过滤交集、内部/外部发送人身份的发现及限制、`around_message_id` 和 IM 已同步范围。结果示意（消息正文为不可信历史）：

```json
{"history_scope":"im_history","messages":[{"message_id":"m-example","sender":{"name":"小王","kind":"user"},"source_time":"2026-10-01 10:00:00","source":{"conversation_id":"c_12345678","name":"项目群","target":"c_12345678","url":"https://example.invalid/chat/c_12345678?message_id=m-example","owner_can_read":true},"content":[{"type":"text","text":"周四发布方案"}]}]}
```

部分消息第一页的示意为 `{"message_id":"m-long","content":[{"type":"text","text":"第一段……"}],"partial":{"first_part":1,"last_part":1,"total_parts":2}}`，外层同时有 `"next_cursor":"p_example"`；第二页同一消息为 `first_part: 2, last_part: 2, total_parts: 2`，以此辨别前页也有内容。外部缓存的完整性未知则使用 `"partial":{"status":"unknown"}`，不伪造分段数。这里仅展示分段字段；每页实际仍附真实发送者及来源。

示意仅解释模型可见语义，实际保留现有其他来源字段。`source.target` 是可调用引用，`url` 是人类访问链接；筛选参数由用户线索、`list`/`info` 或搜索结果取得，身份与权限由宿主派生。旧结果进入模型历史后不能证明当前权限，后续工具调用重新核验；压缩/恢复沿用既有机制，不把历史文本升级成授权。验证要捕获 DSH 实际 schema 与 renderer 输出、短引用往返，以及隔离真栈中的真实模型从自然任务选择关键词、翻页/回读、区分来源与无结果/不可用的行为；stub 仅证明确定性分支，不冒充真实模型行为。保护隐私，记录版本、模型、输入与证据 locator。

## 契约层增量 (delta-spec)

- Gateway 全局 Agent：[specs/gateway/global-agent.md](specs/gateway/global-agent.md) → `docs/specs/gateway/global-agent.md`。PA 的权限与非消费沿用现行条目，不重写。

## 风险与回退

- 大历史的正文扫描和快照物化成本尚未知：隔离规模证据是实施退出条件；不得通过丢旧历史、截断结果或对用户假报完成来掩盖。测量不达目标则调整设计并复审。
- 快照固定候选而消息/权限可能变化：续页以当前状态复核；新增内容需新搜。游标失效明确报错，允许重新查询。
- 中文多词是字面线索，不能找到同义改写；通过 schema 和结果范围清楚说明。外部未镜像部分没有全量性保证。
- 回退应用版本恢复旧搜索语义；无新增正文索引或一次性数据迁移。必要普通索引是可再生性能结构，不删除业务数据。

## 一次性部署迁移

无。直接查询现有消息，不需要历史数据回填；可选普通索引属于目标版本常规 schema 初始化。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Gateway | `./scripts/e2e-down.sh --wt "$WT_ROOT"` | `./scripts/e2e-up.sh --profile daily --wt "$WT_ROOT"` | 从 `$WT_ROOT/.e2e-ports.env` 加载地址后检查 `curl -fsS "$IM_URL/openapi.json"` 及 daily ready 清单 |

**Review 驱动方式**：端到端真栈；不改变客户端面，使用真实产品入口给 Agent 发自然语言任务，检查实际工具调用及来源回读；权限、失败和分页可用客户端实际调用的同一产品入口辅助构造，不以直接调用 Work 内部函数替代产品旅程。

**验收前置**：独立 worktree/runtime、daily 模板可用模型与隔离账号/Agent；在隔离 IM 建立可访问/不可访问群、跨时间中文消息、模拟镜像来源及多页数据。真实 provider 不可用时记录缺口，不以 stub 宣称产品行为通过。退出执行 `e2e-down.sh`。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-search | Agent 历史搜索与回查 | 无 | 无 | `apps/im-server`、`packages/personal-assistant`、`packages/dsh-integration`，相关测试与 delta-spec | **[reviewer]** 覆盖 spec 全部场景：多词与精确查找、相关性/最新排序、旧历史、组合过滤、真实来源和前后文、多页、空/不完整/不可用、双身份、权限变化和未读不变；含已镜像外部群中两个真人的定向查找和身份消歧。**[worker]** 验证参数互斥、特殊字符、短中文词、ASCII 大小写、稳定时间排序、快照绑定和旧游标、内容/权限变化、分段与引用往返；捕获实际模型可见结果，验证有/无后续页的字段、单页正文加附件合并、长消息跨页首/中/末段和前后缺失、预算错误、新游标续页时内容变更、旧游标在消息内且内容改变/不变时均安全报错及重读、旧游标在消息边界正常续查与权限重核；验证外部缓存正文与图片的未知完整性、已镜像/未同步的定位及模型结果和审核/恢复保留部分内容与来源；不将附件引用当成内容已读；用真实 external target 和短引用覆盖定向搜索、发送人/时间组合、续页、撤权和锚点路由，验证同群不同外部发送者、未知来源身份及内部发送人过滤；以隔离数据库覆盖流式增量/终态/删除的事实一致性；捕获模型实际可见 schema/结果并进行代表性隔离真实模型任务；在受支持 Node 与磁盘下记录至少 10 万条合成消息、100 聊天、广范围和高命中查询的端到端延迟/内存及写入影响，并与实施前基线对照，不满足实际部署需求时升级设计；无生产数据或生产测试。 |

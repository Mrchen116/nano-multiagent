# feat-680 — 独立产品验收报告

> Round 1；full；2026-10-30。对齐 `spec.md` 全部 Scenario 与 `design.md` M1-search。
> Validation snapshot: `6b95850a6 → 2d51d501dab8b62e1616ae4019bfab200088a3aa`。
> 本轮复用 caller 启动的该版本构建；运行进程为该工作树 `apps/im-server/lib/main.js`，Node v24.22.1，端口 59928。验收中 caller 通知源码有后续修订，但未重建/重启本栈；结论不覆盖后续修订。

## Verdict

**fail（2 个 major 问题）**。真实产品旅程已覆盖首期五项及全部首文档 Scenario；内部 IM 的检索、分页、回查、排序、访问拒绝和未读对照均得到预期结果。补充的合成外部镜像通过真实 Agent→工具→IM 旅程，发现未知外部作者旧记录被内部主人 ID 筛选命中，并被返回为 `is_owner=true`。这两项违背发送者过滤和真实身份边界，阻塞本轮交付。结论只针对 2d51d501d，不评价 caller 后续修复。

PA-only、外部双真人和非零主人未读前置最初缺失，caller 随后直接写入隔离 SQLite 及本地 external target 映射补齐；本轮独立观察了真实产品消费这些合成材料的行为。它们不证明真实飞书收发/同步链路；该链路也不是本期镜像检索的验收替代物。

## 用户旅程体验与环境

仅操作 `http://127.0.0.1:59928`，账号 nano，未访问生产。核对 `/tmp/nano-feat-680-e2e/.e2e-daily.json` 与实际 agents/config：P/E/Q 为 gpt-6.1-sol/high，PA 为 gpt-6-astra/medium，均 global/codex。真实调用记录显示 PA 使用 gpt-6-astra；审核模型的本轮实际调用未单独验证。

Web 1280×720：从 PA 聊天发自然语言请求，答案用表格将作者、时间、原话和链接对应起来。点击“原消息”后出现 `Original message located`，焦点落在实际原消息，旁边可见后续更改决定；“Back to previous chat”可回到 PA。用户能够区分原计划与后续决定，并自行回查。UI 无本期新增布局，未作 iOS 或窄屏视觉结论。原消息定位截图：`/tmp/feat680-review/source-link.png`；最终回答与左侧非零未读画面：`/tmp/feat680-review/final-answer.png`。

首轮我故意查询不存在的准确编号 BLUE-680：PA 发现精确查找仅命中本次请求，明确排除自命中，并未把 RAVEN-41 的“周五”套为 BLUE-680 的结论。第二组独立赤鹭材料中，PA 将“周四开会”与后续“周五上午十点”区分，并指出原话没有具体日期/时区。

产品内 PA 是被测角色。验收判断来自独立比较真实 HTTP Work 工具参数/返回、用户消息接口、原聊天及浏览器操作，没有读取实现定位或运行内部 Work 函数；没有以模型自称成功作为证据。

### 本轮临时增量

- 原蓝鸟群 `c_i2uebrwq` 新增一条虚构补充（`65c55be5ee164941acdb59fd8af61d0f`）。该条同时含三个词，未用它作为“弱匹配”对照。
- 新建主人参与、PA 以 observer 访问的 `独立验收-赤鹭历史`，ID `c_fm5aub93`。先发六条虚构消息，再发时间更晚的单线索“赤鹭发布快讯五：仅更新手册”。无外发到真实联系人。
- 强匹配 `41f16ef37393411881816ae937aaaf98`：12:10:41，正文“赤鹭线索：方案已明确；周四开会，再讨论发布。代号 HERON-680。”；弱匹配 `862ad6f7adf94cf992422eb9628956dd`：12:12:17。
- 在 PA 聊天 `c_043be4b9cb28` 发独立回查、排序、分页、权限与过滤对照请求。请求和回答保留在隔离栈。
- 临时通过 Web 同一 policy API 排除 `benchmark-feat680-0`，以既有真实 cursor 继续读并核查拒绝。源策略恢复状态见末尾。
- caller 追加合成 PA-only 私密群 `fixture-feat680-pa-only`、两真人及未知旧作者镜像 `fixture-feat680-external` 和 `fixture-feat680-unread` 非主人作者未读1条。均由 caller 直接注入隔离 SQLite，外部 target 映射亦为合成；没有真实飞书 Bot、真人或外发。reviewer 的检索/筛选/around/回答观察全部经正常 PA 消息及真实产品 API。
- 没有启动或停止任何服务；栈由 caller 管理。

## 证据索引

原始证据保留在 `/tmp/feat680-review/`，不提交日志、截图、凭据或数据库；本报告给出决定性摘录。`auth.json` 仅是本机临时测试凭据，不是验收附件。

| 编号 | 独立观察与证据 |
|---|---|
| E1 | `work-r1.json` turn 3：请求 `f3654cf157584db1b025ea87727dc722`；真实 `search keywords=[发布,周四,方案]`、`query=BLUE-680`、`read around_message_id=fa56e...`。回答 `03b9fa652cba4be687b22e431a57ea8c`；`messages-r1.json` 与来源定位截图。 |
| E2 | `work-r3.json` turn 4：请求 `3240826444aa4da1af328c03fff46c51`；默认多词每页2条，实际 cursor `p_7c810f50` → `p_67806fc5`。`query=HERON-680` 仅返回强匹配；around 读取到六条及后续决定。 |
| E3 | 同 turn：`query=赤鹭,sort=recent,limit=2`，三页 ID 分别为 `bd3f.../c3eb...`、`24c8.../50d8...`、`6b25.../41f1...`；cursor `p_c7f66425` → `p_eb3e919f` → 末页省略。共六条且未重复。PA 明确这是新增第七条之前的快照。 |
| E4 | 同 turn：新弱匹配加入后默认相关性第一条仍为旧 `41f1...`，第二条新 `862a...`；`sort=recent` 则新 `862a...` 第一。`benchmark-feat680-0` 未设日期搜索返回 2024-01-27 的 `bench680-978/950`，cursor `p_fc2319a4`，PA 明确只读第一页、未查全。 |
| E5 | 同 turn：限定 `target=c_fm5aub93,participant_id=u_xcfqwzq4,after=2026-10-30T12:00:00+08:00,before=2026-10-30T13:00:00+08:00,query=赤鹭` 返回六条。同群 `query=不存在的紫鹭-680` 返回 `messages:[]`、`history_scope:im_history`，PA 限定结论为当时可访问已同步历史。 |
| E6 | 同 turn：单独 `inbox check` 显示赤鹭7；search 两种排序、around read 后再 check 仍为7。`sources-before-r3.json`、`sources-after-r3.json`、`sources-current.json` 中主人该群 unread_count 均0；未覆盖主人非零未读。 |
| E7 | `policy-before.json` revision1 无排除 → `policy-excluded.json` revision2 排除 benchmark-feat680-0。`work-r4.json` turn6：旧 `p_fc2319a4` 同参数续查返回 `is_error:true,Error: target_not_accessible`；`read around_message_id=bench680-978` 同样拒绝；未排除赤鹭 `query=HERON-680` 仍返回强匹配。 |

## Reference Artifacts Reviewed

N/A：设计明确没有前端改动与新增原型契约。实际 Web 进入、阅读、原消息定位与返回已独立观察。

## 问题清单

| # | 严重度 | 实际现象与复现证据 | 处置 |
|---|---|---|---|
| 1 | major | 在真实 external target 搜“银燕方案”，再限定 `participant_id=u_xcfqwzq4`，两次均返回 `fixture-fs-unknown`（外部身份未知的旧记录）。内部主人并非其可确认真实作者，内部发送人过滤不应命中该外部记录。见 `work-final.json` turn7。 | 阻塞；在修复构建针对本场景复验。 |
| 2 | major | 同记录的 `sender={id:u_xcfqwzq4,name:未知,kind:external,channel:feishu,is_owner:true}`，缺少 `source_id`。无筛选搜索、around及内部发送人筛选均向模型呈现主人身份标记。模型此次审慎说明不能确认本人，不能抵消返回事实字段错误。 | 阻塞；真实作者未知必须不冒认为主人，修复后复验模型实际可见结果。 |

两名已知外部真人小甲/小乙均正确 `is_owner=false`、保留各自 `source_id`；问题限定在未知旧作者记录，不扩大为全部外部身份失效。

## 验收标准覆盖

所有期望来源为 `spec.md` 对应同名 Scenario；外部专项另来自 `design.md` M1-search。

| Requirement / Scenario | 真实旅程与证据 | 结果 | 边界 |
|---|---|---|---|
| 关键词回溯 / 中文多关键词 | E1、E2，不连续三个中文词实际命中 | pass | 字面多词，不是语义搜索 |
| 关键词回溯 / 精确短语和标识 | E1、E2，HERON-680唯一命中，BLUE-680请求自命中被识别 | pass | 已验项目标识 |
| 排序与范围 / 相关性优先 | E4，旧三词消息在新单词消息之前 | pass | 真实时间分离对照 |
| 排序与范围 / 最新优先与旧历史 | E3、E4，新快讯优先且2024年历史可查 | pass | 未声称读取完全部10万条 |
| 组合条件 / 聊天、发送人与时间组合 | E5、E8、E9，内部正反例通过；外部未知旧作者被主人ID命中 | fail | major #1；已知小乙+2024年+target正确仅命中小乙 |
| 原文上下文 / 从命中回到原文 | E1、E2回查通过；E9未知外部作者被错误标记is_owner | fail | major #2；PA-only回答正确不提供主人无权链接 |
| 完整性权限 / 多页结果 | E2、E3，真实三页至无cursor；模型说明停止/完结边界 | pass | 没有用首批当全量 |
| 完整性权限 / 没有匹配与未查全 | E4、E5、E7，空结果、主动停止未查全、当前访问拒绝可区分 | pass | 不存在外部映射实际返回target_not_accessible；IM断连未实测，不声称覆盖所有故障 |
| 完整性权限 / PA双身份和来源排除 | E7、E9：主人observer、PA-only均可发现；排除后拒绝；PA-only回答说明主人无权且不发无权链接 | pass | 合成前置，不是实际飞书同步 |
| 完整性权限 / 权限变化与续查 | E7，排除后原cursor及around均拒绝，允许来源继续命中 | pass | 来源排除分支；普通成员撤权另未覆盖 |
| 完整性权限 / 不消费未读 | E6、E10：Agent Inbox7→7；另主人非零未读1→1，真实search/around后不推进 | pass | 非零未读由caller注入合成前置；reviewer未打开群 |
| M1外部专项 / 两真人镜像定向查找与身份消歧 | E9：known source_id过滤及around通过；未知旧作者误筛选与误身份 | fail | major #1/#2；合成镜像走真实产品，不代表飞书传输链路 |

## 上层文档同步

- [x] `SPEC.md`：无需更新跨包顶层架构。
- [x] `docs/specs/gateway/global-agent.md`：需由 orchestrator 在交付时根据最终实现校正并归并现有 delta-spec。本轮未替其归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 补充记录与清理

本轮没有修改源码、测试或设计；仅本报告写回工作树。未提交报告，由 caller 收尾纳入提交。

- E8：`work-filters.json` turn6，赤鹭群主人在11:00–12:00查“赤鹭”返回0；同群12:00–13:00改发言人为真实 E 内部用户 `u_5as72ej7` 返回0。此前主人12:00–13:00为6条。错误时段和错误发送人各自排除，符合内部组合过滤。
- E9：`work-final.json` turn7，准确 `AP-680` 返回 `fixture-pa-only`，`owner_can_read=false`；PA回答指出本人无权且未给来源链接。外部 target `external:pa_d8c9ef251c44:feishu:feat680-test:group:synthetic` 搜银燕方案得三条；小乙 `sender_source_id=ou-feat680-two` + 2026全年为空，换2024全年仅 `fixture-fs-2`；around得到小甲、小乙、未知旧记录，证明external定位路由及跨消息上下文。内部主人过滤两次返回未知旧记录，构成#1；该记录is_owner=true构成#2。未存在映射 `external:pa_d8c9ef251c44:feishu:feat680-unmirrored:group:synthetic` 返回 `Error: target_not_accessible`，PA明确不可访问不等于零匹配，也没有擅自断言全部外部历史已查全。
- E10：`unread-before.json` / `unread-after.json`，`fixture-feat680-unread` 的主人 unread_count **1→1**。中间 turn7 实际 `search 青鹭项目` 和 `read around_message_id=fixture-unread-680` 均成功，真实作者为测试同事 `fixture-user-680`，reviewer 没有打开该群；本轮未对该群 inbox read。
- `policy-restored.json` 证明排除策略已恢复 `excluded_conversation_ids:[]`（revision3）。所有新增虚构数据保留在 caller 管理的隔离栈，便于 targeted 复验。无需清理 reviewer 自启进程。

---

# Round 2 — targeted 修复复验

> Validation snapshot: `6b95850a6 → 6066037d7a8abba46ae1ed1a96d483d85624e577`。
> Prior acceptance: 本报告 Round 1，`validated_at=2d51d501dab8b62e1616ae4019bfab200088a3aa`。
> Fix delta: `2d51d501d..6066037d7`；2026-10-30，复用原隔离数据及端口。caller 已以本提交重建并重启；reviewer 核实 clean HEAD、运行进程仍指向该工作树构建、`/health` 正常、原 node online。

## Verdict

**pass。Round 1 的两个 major 均关闭，未观察到新增问题。** 本结论由本轮身份/过滤/来源回查/相邻分页的实际旅程，加上下面逐项明确保留的 Round 1 证据组成；不把前轮失败直接改写为成功。

本轮只通过正常 PA 自然语言消息驱动，读取真实 `/im/v1/agents/pa_d8c9ef251c44/work` 模型可见结果及聊天消息接口确认最终答复。未读取实现定位，未修改源码/测试/设计，未停止或启动服务。虚构外部镜像、PA-only 及未读数据仍为前轮 caller 注入的合成前置，不声称真实飞书传输链路已验证。

## 问题关闭与决定性证据

本轮请求 `d10b378da88843c09a5d34d5956b3bda`、相邻回归请求 `a625e1b27a5d444fba34c44fc920e8e1`。真实执行为 PA 主 session turn 8；原始证据 `/tmp/feat680-review/round2-work.json`、`round2-messages.json`。最终答复 `5d39113bef734870a83bf2c7ada3c4af` 已在真实聊天消息接口确认送达，不仅是待发送参数。

| 前轮问题 | 本轮实际观察 | 结论 |
|---|---|---|
| major #1：未知外部旧记录被内部主人ID筛中 | 同一真实 external target，`query=银燕方案,participant_id=u_xcfqwzq4,limit=20` 成功返回 `messages:[]`、`history_scope:im_history`，未返回任何外部记录。 | closed / pass |
| major #2：未知外部作者误标为主人 | 无筛选 search、以小乙为锚的 around read、`message_id=fixture-fs-unknown` 精确 read 三条路径均返回未知记录 sender **`{"name":"未知","kind":"external","channel":"feishu"}`**；没有内部代记 `id`、没有 `source_id`、没有 `is_owner`。 | closed / pass |

相邻边界也由实际结果确认：

- 小甲/小乙分别保留 `source_id=ou-feat680-one/ou-feat680-two`、`kind=external`、`channel=feishu`、`is_owner=false`，二者均无内部代记 `sender.id`。小乙加2024全年及指定 external target 搜索只返回 `fixture-fs-2`；around回读三条，未知作者仍保留未知字段语义。
- 重新搜索 AP-680 确实返回原始 `fixture-pa-only`，其 sender 保留 PA 的内部 Agent ID、`kind=agent,is_owner=false`，来源 `owner_can_read=false`。PA 在实际答复中排除本聊天自命中，说明主人无权访问且没有附不可访问来源链接。
- 内部赤鹭新查询 `query=赤鹭,limit=2` 首批为 `862a.../bd3f...`，使用新 `p_1bd3b4e1` 续页为 `c3eb.../24c8...`，第二页继续返回 `p_4e0218c7`。四条内部用户仍保留 `id=u_xcfqwzq4,name=Test User,is_owner=true,kind=user`，证明外部字段修正没有顺带删除内部作者信息。
- 最终答复明确未知作者不能说成主人，省略字段不等于 true/false；准确区分内部主人过滤零匹配和访问拒绝；分页说明“只读两页、4条，不是全量，仍有后续”。同一来源的真实作者、时间、原文和链接仍可对应。没有向受验群发消息。

## 范围判断与前轮结论保留

派发的修复范围为外部身份投影、内部发送人匹配和模型工具说明；文件级变更范围与该说明一致。搜索匹配/排序策略、around窗口、当前来源排除、已读消费和 Web 路由没有新的行为要求。共享 sender 投影可能影响内部用户与 Agent，因此本轮扩展核验了内部作者和 PA-only 作者；共享搜索/游标路径额外执行了真实新游标续页。未出现需要扩为 full 的新副作用。

下表的 retained 只保留 Round 1 已实际观察到的对应结论，原有限制仍成立。原通过仅代表当时已验行为，当前继承通过以修复影响可限定、需求/数据/入口未改变、相邻真实回归成功为依据，不声称本轮重跑了所有旅程。

| Scenario（来源同 `spec.md`） | Round 2状态 | 实际复验或明确保留的证据 |
|---|---|---|
| 中文多关键词 | pass / retained | Round1 E1/E2：真实不连续中文三线索命中。当前无匹配算法变化，单项筛选及相邻搜索本轮成功。 |
| 精确短语和标识 | pass / revalidated + retained | 本轮 AP-680 原始命中及自命中区分；Round1 E1/E2 HERON-680/BLUE-680准确标识证据保留。 |
| 相关性优先 | pass / retained | Round1 E4 的旧三词先于新单词、时间分离对照；本次身份修复不改变排序判据。 |
| 最新优先与旧历史 | pass / retained | Round1 E3/E4 的recent新消息优先及2024历史；本轮外部2024时段检索仍成功。 |
| 聊天、发送人与时间组合 | pass / revalidated + retained | 本轮小乙+external target+2024只一条、内部主人过滤外部记录为空；Round1 E5/E8内部发送人及时间正反例保留。原fail关闭。 |
| 从命中回到原文 | pass / revalidated + retained | 本轮around与精确read均保留真实已知作者/未知状态及来源；Round1 Web原消息定位和返回截图与操作证据保留，UI无改动。本轮未重跑视觉矩阵。原fail关闭。 |
| 多页结果 | pass / revalidated + retained | 本轮真实新cursor两页、仍有后续且答复不宣称全量；Round1 E3读三页至末页的完整性证据保留。 |
| 没有匹配与未查全 | pass / revalidated + retained | 本轮内部主人筛选正常空数组、两页未查完表达；Round1 E5空词与E7来源拒绝、E9不可用映射错误保留。未测IM断连的原边界不变。 |
| PA双身份和来源排除 | pass / revalidated + retained | 本轮PA-only再次返回owner_can_read=false且不附无权链接；内部主人来源查询成功。Round1 E7策略排除后拒绝与允许来源成功保留。 |
| 权限变化与续查 | pass / retained | Round1 E7旧cursor/around在来源排除后均target_not_accessible；本次没有改变当前权限判定。本轮普通续页成功；策略仍revision3、排除列表空。 |
| 不消费未读 | pass / retained | Round1 E6/E10的Agent Inbox7→7与主人1→1保留；本轮未read该群，sources before/after仍显示合成未读群1。后者只作状态旁证，不冒充再次执行该群完整未读旅程。 |
| design M1：外部双真人定向查找、身份消歧 | pass / revalidated | 本轮两已知source_id区分、2024筛小乙、around与未知精确读取、内部主人空匹配、最终答复正确处理未知；关闭原fail。 |

## 本轮交付与环境状态

仅追加本报告，无代码/测试/设计变更，无提交。原临时数据保留用于追溯，服务由 caller 管理且未停止。`round2-sources-after.json` 确认策略仍为revision3、`excluded_conversation_ids:[]`。报告中的上层文档归并责任与前轮相同，由 orchestrator 收尾。

## Round 3：Web 搜索独立产品验收

- **结论：fail**；Highest Required Action：fix-implementation；1 major、1 minor，另有未验证项。`validated_at=52b5e2e59d1c9d8da23f8f9e19fea8cec457882b`；`executed_base=21dc66c4fc4c8d10b7ee76cf7dc248c4fb7f4eb6`。验收期间 worktree HEAD 前移不改变已启动服务及本轮版本；caller 按固定版本复验其后修改。
- 范围：针对用户新增 Web 旅程，沿用先前 Agent 范围的既有验收并核对共享查询代码后续影响；本轮没有重新运行真实 Agent 任务。已读并对照 `spec.md` 追加范围、`design.md` 的 Web 交互及用户提供的侧栏截图；用户允许跳过原型视觉审查，原型未渲染。
- 环境：caller 启动 daily 独立栈 `http://127.0.0.1:51781`，核对 `.e2e-daily.json` 中 P/E/Q 与 PA；Web 登录隔离 `nano`。在 `研发日常` 经真实 UI 创建两条中文消息、经正式消息接口追加 23 条测试消息并抑制 relay，另注册隔离账号 `review680b`。后续仅为跨年显示验证将两条测试消息日期分别改为 2025-02-01 和 2024-02-01；无真实飞书或生产数据。

| 验收点 | 观察证据 | 结果 |
|---|---|---|
| 非最新历史搜索及原文定位 | 实际输入“紫藤计划”命中被随后消息覆盖预览的旧消息，显示 `研发日常 / Test User / 15:25 / 原文片段`；点击后 URL 包含 `message_id=010571d383c3445abbd805b2f8102d45`，页面提示 `Original message located`，原文获得焦点。 | pass |
| 会话/消息分组与分类 | 搜索中会话分组与消息分组可辨；切 People 返回 `No matching messages`，切 Group 后命中群消息。 | pass |
| 分页及清空 | 搜索 `QAPAGE_680` 首屏 20 条并显示 Load more，点击追加剩余 3 条且无继续按钮；清空输入恢复常规列表。 | pass |
| 用户访问边界 | 已登录主人可搜索群消息；隔离第二账号用相同搜索 API 返回 200、0 条；未登录请求返回 401。未独立做续页中撤权或公开/解散聊天的真实入口复验。 | 部分 pass / 余项 inconclusive |
| 空、加载、失败 | 真实 UI 看到 Searching、No matching messages；未在真实界面注入后端失败或验证 Retry。 | inconclusive |
| 搜索不消费未读 | 本轮未构造非零未读状态并对照查询前后。 | inconclusive |
| 桌面和窄屏体验 | 默认桌面及 390×844 窄屏可读、结果可点击且能定位；窄屏返回丢失搜索状态，见 #1。 | fail |
| 历史时间可辨 | 两条样本实际时间分别为 2025-02-01 和 2024-02-01，搜索结果都显示 `2月1日`，见 #2。 | fail |

### Issues

1. **major / direct / fix-implementation：窄屏从原消息返回后搜索上下文丢失。** 在 390×844 输入“紫藤计划”，点击命中原消息后按 Back，搜索框清空、筛选从 Group/All 重置，结果列表消失。用户逐条核对多条结果时必须反复输入并重新翻页，破坏搜索→核对→返回的连续旅程。建议返回时保留关键词、分类和已加载结果/可等效恢复的位置。
2. **minor / direct / fix-implementation：跨年搜索结果没有年份。** 对 2025-02-01 与 2024-02-01 两条隔离数据，分页结果均显示“2月1日”，用户不能区分记录年份。搜索的用途是回溯历史，建议至少对非本年消息显示年份。

运行栈与数据由 caller 管理，本 reviewer 未停止服务；自己的浏览器标签已关闭、临时 viewport 已恢复。失败恢复、非零未读及续页撤权仍缺真实产品证据，不以自动化结果冒充本轮观察。

## Round 4：修复后复验进度

- `validated_at=0292ef392aec8413c9e0ce1539a518ad038a05a2`，caller 重建隔离 daily 栈 `http://127.0.0.1:54292`；与生产、真实飞书无关。已通过受信 IM HTTP 接口在群 `c_7t3b7dqw` 创建 25 条 `QA_RETURN_680` 消息，其中两条隔离样本仅用于跨年复验，经数据库设为 2025-02-01 和 2024-02-01。
- **非零未读：pass（真实用户 API，合成初始状态）**。将隔离账号在群的未读设为 4；调用真实用户会话列表、搜索后再次读取列表，未读仍为 4；搜索首批返回 20。未以浏览器页面代称该 API 证据。
- **续页撤权：pass（真实用户 API，合成权限变化）**。经正式 API 创建私密测试群 `c_kku7ojtw` 并发布 22 条 `QA_REVOKE_680`，首批返回 20 与游标；在隔离数据库移除测试用户的群参与关系，沿原游标续查返回 0。该合成操作只证明服务端续页按当前权限过滤。
- **两项 UI finding：inconclusive，等待 caller 实际复验。** 本轮子任务 IAB 不可用；Chrome 仅用于实际本地产品，并非用于绕过先前禁止打开的本地原型。Chrome 登录后弹出密码安全提示；处理提示时浏览器控制因用户正在操作而中断，故停止该浏览器交互，不将点击无响应归因为产品。已告知 caller 数据、端口和缺口。跨年显示、窄屏第二页返回及位置、失败恢复均尚未完成本轮真实 UI 验证；不能以实现或自动测试替代。
- 本 reviewer 未停止 caller 管理的服务；未改产品源码。验收结论继续保留 Round 3 的 fail，直到实际 UI 的两个 finding 复验通过。

### Caller 后续实际 Web 自检证据（非本 reviewer 独立观察）

Caller 报告以 `0292ef392aec8413c9e0ce1539a518ad038a05a2` 的隔离 `54292` 栈在 390×844 Web 实际执行：搜索 `QA_RETURN_680`、选 Group、加载第二页后，sample 00 和 01 分别显示 `2025年2月1日` 与 `2024年2月1日`；点击 sample 00 可定位原消息；Back 后仍保留关键词、Group、25 条和滚动位置，画面同时展示 sample 08 至 sample 01。Caller 还观察到搜索前后未读数为 4。这是 caller 的实际观察，不是本 reviewer 的独立 UI 实测。

**本轮验收判定：inconclusive。** 上述 caller 证据支持修复有效，但本 reviewer 因浏览器控制中断无法独立观察两项决定性修复，故不把原 major/minor 标记为独立复验通过；失败后 Retry 的实际 UI 仍未验证。已独立观察的非零未读和撤权后续页按上文保留。无需将该缺口表述为产品已发生新故障。

## Round 5：窄屏结果返回与年份独立复验

- Reviewer：独立 `change-reviewer`（Codex，`/root/web_search_product_closure`）；模式：targeted closure，范围是 Round 3 的两个 UI finding。产品代码 `validated_at=0292ef392aec8413c9e0ce1539a518ad038a05a2`；当前 HEAD `130e57627e1557e547855a5c5ad67bad1cd7ab09` 为后续文档提交。复用 caller 启动的 daily 隔离栈 `http://127.0.0.1:54292`、测试用户及 Round 4 准备的 25 条虚构数据；没有接触真实飞书或生产数据。
- 环境核对：`.e2e-daily.json` 显示 P/E/Q 和 PA 固定阵容，测试群为 `c_7t3b7dqw`。本轮用独立 IAB，以 390×844 真实 Web 入口操作；本 reviewer 没有修改源码、测试、配置或测试数据。
- **Round 3 major #1：closed / pass。** 输入 `QA_RETURN_680`，选择 Group，首批显示 20 条；点击 Load more 出现其余 5 条。点击第二页 sample 00 后，URL 指向 `c_7t3b7dqw?message_id=7b3eb0b9a29b440b917ec421e4f950b2`，页面提示 `Original message located`，原消息被定位。点击 Back 后重新出现搜索词、已选 Group、全部 25 条与此前第二页位置；实际画面直接显示 sample 08 至 sample 01，不需再次加载或寻找。搜索与结果主体的分组和可点击行在窄屏内清晰可辨。
- **Round 3 minor #2：closed / pass。** 第二页 sample 00 及 sample 01 在实际 Web 结果中分别显示 `2025年2月1日`、`2024年2月1日`，年份可直接区分；返回后仍显示。
- 其他范围沿用 Round 3/4 已观察证据与原有限制。失败后 Retry 的真实 UI 场景本轮未覆盖；本次不以本轮结果声称全部产品验收已完成。原型视觉未验证，用户已明确允许改查实际界面。
- 本 reviewer 重置临时 viewport 并关闭自己打开的 IAB 标签；隔离服务由 caller 管理，未停止。

### Caller 补充：真实 Web 失败恢复

在同一隔离栈、产品代码 `0292ef392` 下，caller 保持 Web 页面打开，核对进程身份后暂时停止本次 IM，输入 `QA_RETURN_680`；实际页面显示 `Search failed` 和 `Retry`。用同一隔离数据库、端口与密钥恢复 IM 后点击 Retry，搜索重新返回 20 条结果及 Load more。该证据是 caller 自检，不冒充独立 reviewer；已有前端自动化亦覆盖失败与重试。

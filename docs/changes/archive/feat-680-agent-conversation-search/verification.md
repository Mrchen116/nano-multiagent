# Verification Report: feat-680-agent-conversation-search

> Validation snapshot: `6b95850a67da5215f3e26dd433037de0fbde5ac5 → 2d51d501dab8b62e1616ae4019bfab200088a3aa`
>
> Round 1 · verification_mode: full · review_round: 1 · validated_at: `2d51d501dab8b62e1616ae4019bfab200088a3aa` · executed_base: `6b95850a67da5215f3e26dd433037de0fbde5ac5` · inspected: 2026-10-30, Asia/Shanghai

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实现已存在；发送人过滤、旧游标查询身份和容量证据仍有缺口，不能收口 |
| Correctness | 已确认 2 个实质偏离；相关既有自动化 41/41 passed |
| Coherence | 包职责、SQLite 同源检索、模型投影与授权/恢复总体遵守设计；见 W1/W2 |

Verdict: **FAIL** — 0 critical, 3 warnings, 0 suggestions. Fix before PR. `requires_full_verification: false`；后续可定向核验 W1–W3，无需重复全部场景。

本报告是静态 full verifier 与必要定向复现，不替代独立产品 reviewer 的真实旅程验收。未修改源码、测试、配置或设计；共享现场由 caller 提交本报告，report_commit 待 caller 提交。

## Completeness

- Milestones：1/1 有实现；M1 退出条件尚不能认定完成。
- Spec 五组 requirement 均存在对应实现；“聊天、发送人与时间组合”在外部旧镜像上偏离，旧快照的查询参数绑定亦偏离 design。
- Prototype / Reference：N/A，无前端改动或原型。
- 性能实现没有引入新索引、写入钩子、常驻服务或历史回填；没有以日期窗口或结果截断掩盖扫描成本。现有证据证明一次 100k/100 聊天真栈搜索可工作，不能证明独立内存对照或写入影响，见 W3。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| 中文多关键词；精确短语和标识 | `apps/im-server/src/work.ts:95`, `:266` | `conversation-search.test.ts` 多词/ERR-42；真实 PA 自主 keywords 任务 | covered |
| 相关性优先；最新优先与旧历史 | `work.ts:274` | relevance/recent 顺序断言；`personal-sources.test.ts` 含 2001 历史 | covered |
| 聊天、发送人与时间组合 | `work.ts:269`–`:272` | 内部过滤与已知外部 source_id 有测试；未知来源旧镜像定向复现失败 | **W1** |
| 从命中回到原文和上下文 | `work.ts:276`, `:326`; `external.ts:183` | 锚点窗口/新消息不进入旧窗口、external→shadow 路由、source.target 投影；真实 PA 回读和引用 | covered，外部群完整旅程仍由产品 reviewer 验收 |
| 多页；完整/部分消息可判断 | `work.ts:286`, `:303`, `:348`; `tool-references.ts:109` | 正文+附件合并、首/末段、内容变化、旧 cursor.part>0 拒绝 | covered，真实模型对所有分段形态的理解未穷举 |
| 游标绑定与旧游标兼容 | `work.ts:210`–`:229` | 新版本绑定代码；旧版本边界快照可改新参数的直接复现 | **W2** |
| 无匹配、不可用与已同步范围 | `work.ts:262`, `:369`; `external.ts:187`, `:288`; `global-mode.ts:25` | 未同步返回错误；cache 标注 external_cache/unknown；schema 范围说明 | covered，未声称外部历史已全同步 |
| PA 双身份/来源排除、当前权限 | `work.ts:123`–`:129`, `:264`, `:294` | `personal-sources.test.ts` 双身份/owner_can_read/排除；分页续查重新排除 | covered |
| 不消费未读 | `work.ts:94`–`:374`; Inbox 独立调用路径 | 搜索测试核 unread_count；历史查询无 Inbox commit/read mutation；只记录 PA source_reads | covered |
| 容量与写入影响退出条件 | `design.md:137` | `M1-search/evidence/self-check.md:6`–`:7` | **W3，证据不足，未证实性能故障** |

### 独立执行的自动化

在上述固定 HEAD，使用支持的 Node **v24.22.1**：

```sh
PATH="/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH" pnpm exec vitest run apps/im-server/tests/conversation-search.test.ts apps/im-server/tests/personal-sources.test.ts packages/personal-assistant/tests/tool-references.test.ts packages/personal-assistant/tests/external.test.ts packages/dsh-integration/tests/approval-sources.test.ts
# 5 files, 39 tests passed; 2026-10-30 12:09 Asia/Shanghai

PATH="/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH" pnpm exec vitest run packages/dsh-integration/tests/global-child-tools.test.ts
# 1 file, 2 tests passed; 2026-10-30 12:10 Asia/Shanghai
```

后一个测试通过真实锁定 DSH 的 `llm/stream` seam 记录 root 的实际 tools/schema 并核对新参数，属于实际装配捕获 + 受控 provider fixture，不是外部真实模型行为证明。没有重复全量套件、容量基准或生产测试。

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| SQLite 为消息唯一事实源，只投影本页 | 是 | `work.ts:273`–`:300`，无新索引/服务 |
| 单短语字面匹配、多线索 OR、匹配数→时间 | 是 | `work.ts:95`–`:97`, `:266`–`:274` |
| 固定候选快照 + 每页当前权限/当前消息 | 基本是，旧查询身份有偏离 | `work.ts:196`–`:216`, `:286`–`:303`；W2 |
| 锚点同聊天、external 经可信 shadow 路由 | 是 | `work.ts:276`–`:279`; `external.ts:183`–`:190` |
| 内外部真实发送者身份分离 | 不完整 | `work.ts:271`；W1 |
| Gateway 合并连续 parts，省略常规状态 | 是 | `tool-references.ts:109`–`:137`；仅作用指定 list/read/search |
| 新游标内容指纹，旧消息中间游标安全失败 | 是 | `work.ts:303`, `:361`；未因恢复升级权限 |
| 历史审核/恢复保留来源和 partial | 是 | `policy/sources.ts` 的 `appendResult`/`restoreEntries` 保留完整结果；`codexEntries` 按消息拆分；`policy/codex-context.ts:51`–`:60` 只裁剪 content，保留其余字段 |
| 包职责和 DSH 公开接入边界 | 是 | SQL 在 IM；external/引用层在 PA；schema 在 dsh-integration；本 diff 无跨包相对导入/private DSH import |

### Agent Context — Implementation Review

- 触发：实际 `conversations` schema、检索排序/选择、分页和模型结果均变化；Consumer 为 Global/PA root。
- 覆盖链：`global-mode.ts` 注册/JSON renderer → `GlobalAgent.call` 可信 Agent/binding 和短引用解析 → external shadow 映射/IM Work → `ToolReferences.result` → JSON 结果 → ApprovalSources 历史证据与恢复。身份、scope、源权限仍由宿主决定；历史记录不成为新授权。
- 新必填目标来自 list/info 或 `source.target`；外部 sender ID 来自结果 `sender.source_id`，schema 明确不按姓名猜 ID；owner/Agent 身份未交模型填写。
- before/after、keywords/sort、target、next_cursor 和 partial 的实际 schema 已由 DSH fixture 捕获；Gateway 合并/省略结果由真实引用层测试执行。来源的 `owner_can_read`、participant/observer、真实 sender 和代发 ID 沿历史审核路径保留。
- 真实模型证据复用 `self-check.md:5`，以及 caller 补充的隔离 Work locator：PA `pa_d8c9ef251c44`，主 session `d04ab82e-2996-4b8e-9d31-6eb015d5c45a`，2026-10-30 04:04 UTC，`/im/v1/agents/pa_d8c9ef251c44/work`。实际使用 `codexOAuth:gpt-6-astra`/medium，自然任务后选择 `keywords:["蓝鸟","发布方案"]`，回读并交付周五结论及两条原消息链接；另有高命中 query 的真实工具调用。
- 限制：Work 证明调用、结果和交付；直接 Codex OAuth 没有同 session 的 LLM_PROXY 请求记录，**不声称已捕获真实 provider wire payload**。一条真实成功任务不证明所有模型对分页、外部身份消歧、不可用和 partial 均可靠。没有据此虚构额外模型失败。
- Context 确认问题为 W1（筛选语义与外部身份不一致）及 W2（模型要求沿原查询续查，但后端对旧游标不能拒绝新参数）。两者为确定性接口问题，不以“模型必然误解”表述。

## Issues

### CRITICAL

无。

### WARNING

#### W1 — 内部发送人筛选仍匹配缺少来源 ID 的外部真人旧镜像（CONFIRMED）

- 契约：`design.md` §4 要求 `participant_id` 仅匹配内部身份，不将外部真人的代记 owner 当真实作者；未知来源旧消息应不带发送人限制查询。
- 位置：`apps/im-server/src/work.ts:271`。排除谓词额外要求 `m.sender_source_id IS NOT NULL`。
- 复现：在独立内存 IM 创建外部 feishu 聊天，插入 `sender_type=user`、`sender_user_id=owner`、`sender_source_id=NULL` 的历史镜像。`search {target:chat,query:"发布",participant_id:"owner"}` 返回该消息，且自身结果明确是 `sender.kind=external`。来源 ID 已知时被排除，未知时反而通过。
- Context Surface：筛选 schema → 历史工具结果。Agent 应按内部 owner 找原话，实际混入真实作者未知的外部发言，导致按人追溯错误；结果仍标 external，不宣称由此获得 owner 授权。
- 建议：内部发送人过滤排除所有外部真人镜像，无论 source_id 是否存在；增加旧镜像 NULL source_id 与真实内部消息的对照回归。
- 证据：本次 Node 24 独立脚本 `/tmp/feat680-review-repro.mts` 的 `legacy_external_internal_sender_filter`；复现使用公开 `Work.query`，无 provider 或生产数据。上述永久测试全部通过，未覆盖这个分支。

#### W2 — 旧快照接受未绑定的新查询参数（CONFIRMED）

- 契约：`design.md` §3/§6 要求续页与查询身份一致，旧快照按原排序继续，新参数不能被误当已在旧快照中绑定。
- 位置：`apps/im-server/src/work.ts:216`。`snapshot.version !== 2` 只比较旧 `identity`，忽略当前 `keywords`、`sort`、`sender_source_id`、`around_message_id`。
- 复现：保存旧版结构的 search 快照，IDs 按旧插入顺序且处于 `part:0`；当前请求在原 query/target 外加 `sort:recent` 并携带旧 cursor。请求成功，仍输出旧快照顺序，而不是拒绝不兼容查询。类似地，新过滤可以悄悄与旧候选集合求交，不能代表一个新查询快照。
- Context Surface：cursor 与 query schema/结果。Agent 应通过错误知道需要重新搜索，实际收到成功结果，无法辨认新参数未绑定到快照。没有观察到权限绕过。
- 建议：保留无新参数旧游标的兼容路径；旧快照收到不能验证的新参数时明确拒绝并要求重新搜索。保护真正旧 snapshot（不仅删 cursor.version）上的边界继续、参数冲突和跨页升级。
- 证据：同一独立脚本的 `legacy_sort_mismatch` 和 `legacy_boundary_cursor_new_query_sort_accepted`；输入直接保存符合旧格式的快照，未伪造当前版本行为。

#### W3 — 容量证据尚不能完成 design 指定的内存/写入影响对照（证据不足）

- 契约：`design.md:137` 的 worker 容量退出条件要求受支持 Node、隔离磁盘、100k/100 聊天、广范围/高命中端到端耗时/内存及写入影响，并与实施前基线对照。
- 现有证据：`self-check.md:6` 有一次真栈 465ms；`:7` 有旧/新 Work 微基准及共享进程 RSS 860/933 MiB，但作者明确说明不能据此比较独立内存；写入仅有合成写入事务总耗时，没有与旧版/并发搜索下写入的对照。真实工具高命中单样本不是完整容量测量。
- 建议：在隔离数据下以独立进程取得可比较的旧/新版 peak RSS，并记录代表性搜索期间的写入耗时/影响及相同输入基线；将命令、版本和脱敏结果补入现有 evidence。无需建立新基准框架或任意 SLA，也不要求生产测试。
- 限制：这是未满足证据退出条件，不是已证明存在内存、延迟或写入回归。现有延迟结果支持 SQL/轻量投影比旧版更快。

### SUGGESTION

无。

## Handoff

- unit_id: `feat-680-agent-conversation-search`
- branch / verify_worktree_dir: `unit/feat-680` / `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-680`
- verdict: `fail`
- issues: `W1`, `W2`, `W3`; validated_issues: `W1`, `W2` 为直接复现，`W3` 为证据缺口
- requires_full_verification: `false`
- report_path: `docs/changes/feat-680-agent-conversation-search/verification.md`
- report_commit: caller 在共享 branch 提交后填写/引用；审查者未提交其他文件
- top_concern: 外部旧镜像的内部作者筛选语义错误；旧游标新参数未绑定
- 自建服务：无；使用独立内存库、测试自清理的临时 DSH home；未停止或改动 caller 的 `/tmp/nano-feat-680-e2e`。

## Round 2 — Targeted Closure

> Validation snapshot: `6b95850a67da5215f3e26dd433037de0fbde5ac5 → 5e080ffbf7709e85e526cede50dc740a6e547234`
>
> verification_mode: targeted-closure · review_round: 2 · finding_origin_head: `2d51d501dab8b62e1616ae4019bfab200088a3aa` · fix_delta_range: `2d51d501d..5e080ffbf` · inspected: 2026-10-30, Asia/Shanghai

**本轮最终结论：PASS，0 critical / 0 warnings / 0 suggestions。W1、W2、W3 均 closed。** 本轮结论取代 Round 1 的待修状态；先前范围和证据限制仍然保留。`requires_full_verification: false`。

本轮只检查两项代码修复、相关回归和新增容量证据，复用 Round 1 未受影响的权限、Schema、结果投影、审核/恢复和模型行为证据。没有重开 full Context Review，没有修改代码、测试或设计。

### Closure evidence

| Focus | 实际修复 / 补证 | 独立核对 | 结论 |
|---|---|---|---|
| W1：NULL source_id 外部旧镜像误匹配内部作者 | `apps/im-server/src/work.ts:272` 的内部作者过滤去掉 `sender_source_id IS NOT NULL` 条件，排除所有外部真人镜像 | `conversation-search.test.ts` 原外部身份用例加入无来源 ID 旧消息；该消息与两位已知外部真人均不匹配 participant_id；sender_source_id 仍只匹配指定真人。原内部作者/时间组合用例仍通过 | closed |
| W2：旧快照接受新参数 | `work.ts:211` 在旧 snapshot 上拒绝显式 keywords、sort、sender_source_id、around_message_id；原 identity 比较与旧参数兼容仍在 | 新回归真正删除持久 snapshot 新字段及 cursor.version；旧参数在消息边界仍可继续，新 sort/keywords 报 invalid_cursor。guard 直接覆盖另外两个新增字段，不改变 v2 查询身份 | closed |
| W3：独立内存和写入基线缺失 | `M1-search/evidence/self-check.md:8` 补独立进程、受支持 Node、隔离磁盘、同规模旧/新数据集与测量 | 核对本机 `/tmp/feat680-benchmark-results.ndjson` 两条原始工具结果转存与文档完全一致；执行与基线说明见下文 | closed，保留样本边界 |

独立测试命令（固定 HEAD `5e080ffbf`，Node v24.22.1）：

```sh
PATH="/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH" pnpm exec vitest run apps/im-server/tests/conversation-search.test.ts
# 1 file, 6 tests passed; 2026-10-30 12:14 Asia/Shanghai
```

`git diff 2d51d501d 5e080ffbf --check` 通过。没有因本次 delta 重新执行先前通过的 41 个测试；当前 6 个搜索测试覆盖受影响入口。caller 提供 red→green 过程，本 reviewer 独立确认修复后的 green 与确切断言，未修改冻结现场重放 red。

### 容量证据的实际含义

补测使用 Node v24.22.1 + `pnpm exec tsx`；旧版 Work 源码由 `git show 6b95850a6:apps/im-server/src/work.ts` 取得，新版来自本 unit work.ts。两版各自独立进程在临时磁盘库创建 100 个聊天、100,000 消息、50% 命中，再执行相同 query 的旧版 3 次 / 新版 10 次，记录 `process.memoryUsage().rss`、`resourceUsage().maxRSS` 和各自造数事务耗时。

| 测量 | 旧版 | 新版 |
|---|---|---|
| query_ms | 2338 / 2070 / 2127 | 100 / 117 / 123 / 99 / 105 / 100 / 105 / 104 / 97 / 109 |
| RSS 起始 / 结束 MiB | 125 / 890 | 112 / 251 |
| maxRSS KiB | 911360 | 264560 |
| 100k 造数事务 ms | 557 | 309 |

这些数值支持本机该负载下新版查询时间与进程峰值内存低于旧版；每版写入各一次，只补齐可比较输入和观测值，不能推导精确写入增益。写入路径未修改；没有新增索引/写入钩子。本次需求不要求证明多用户并发或生产 SLA，故不再要求为关闭 W3 构建并发性能框架。真实自然语言全栈工具调用 465ms 是独立的单样本，未与上述 Work 直调结果混淆。

证据来源和限制：ndjson 是 caller 从本会话原始工具输出原样转存，非原进程直接输出文件；一次性 TS 脚本与临时数据库已清理。本 reviewer 检查转存数值及基线/执行方式说明并复用结果，没有伪称独立重跑容量基准。共享进程的旧 RSS 结果仍仅作为历史记录，不用于新版结论。

### Context closure 与剩余限制

W1 修复使内部作者 schema 与筛选结果一致；W2 修复使旧游标遇新参数明确失败，模型可以重新查询，不再把不兼容参数下的旧快照当成功结果。两处均在 IM 查询层修复，没有扩大模型可选择的身份或读权限，没有改 renderer、来源标签、partial 或授权恢复链。

DSH fixture schema 捕获、真实 PA Work 行为及未取得 OAuth provider wire 的边界，仍按 Round 1 和 `self-check.md:9` 记录。本轮不从容量测量推出普遍模型可靠性，亦不替代独立产品 reviewer 的场景验收。

### Round 2 Handoff

- unit_id: `feat-680-agent-conversation-search`
- review_round / verification_mode: `2` / `targeted-closure`
- validated_at: `5e080ffbf7709e85e526cede50dc740a6e547234`
- executed_base: `6b95850a67da5215f3e26dd433037de0fbde5ac5`
- verdict: `pass`; issues: `[]`; validated_issues: `W1 closed`, `W2 closed`, `W3 closed`
- requires_full_verification: `false`
- report_path: `docs/changes/feat-680-agent-conversation-search/verification.md`
- report_commit: 共享现场由 caller 提交本报告；未修改其他文件
- top_concern: 无阻断问题；保留单机容量样本、provider wire 未捕获的证据边界
- 自建服务：无；临时测试数据库由 fixture 清理；未改动 caller 隔离服务

## Round 3 — External Identity Projection Patch

> Validation snapshot: `6b95850a67da5215f3e26dd433037de0fbde5ac5 → 6066037d7a8abba46ae1ed1a96d483d85624e577`
>
> verification_mode: targeted-closure · review_round: 3 · pre_fix_head: `5e080ffbf7709e85e526cede50dc740a6e547234` · fix_delta_range: `5e080ffbf..6066037d7` · inspected: 2026-10-30, Asia/Shanghai

**本轮定向结论：PASS，0 critical / 0 warnings / 0 suggestions；code-review patch 无存活 finding。** 范围是产品验收发现的 `conversations search/read` 外部真人身份投影，W1/W2 的 Round 2 closure 不重开。`requires_full_verification: false`。

### 实现与直接验证

| 契约 / 风险 | 当前实现 | 核对结果 |
|---|---|---|
| 外部真人不能以代记 IM owner ID 充当真实作者 | `apps/im-server/src/work.ts:307`, `:328` 统一以 externalHuman 判定，对全部外部真人省略内部 sender.id | 已知主人、已知同事、未知旧作者三路均不返回代记 id |
| 旧外部镜像缺少可靠 source_id 时不能标为主人 | `work.ts:330` 对未知外部作者不投影 is_owner；保留 kind/channel/name 和其他来源事实 | 未知作者结果没有 id/is_owner/source_id；不以 false 冒充确定的非主人身份 |
| 已知外部作者仍可准确辨认、筛选 | `work.ts:334` 保留 source_id；已知来源继续使用现有宿主 owner 判定 | 真实配置 owner_open_id 匹配时保留 is_owner=true；已知其他人保留 false；sender_source_id 搜索仍通过 |
| 内部真人 / Agent 的身份与权限不回归 | externalHuman 只包括外部来源 sender_type=user；身份校验、sourceAllowed、conversationAccess 与 participant/observer 未改 | 现有双身份、来源排除、内部作者/时间组合和 owner 身份测试通过 |
| 模型能解释缺失身份 | `packages/dsh-integration/src/global-mode.ts:25` 明确 external source_id 缺失为未知、is_owner 缺失不证明主人身份 | 源码与当前构建 `lib/global-mode.js` 一致；原有 DSH schema 装配路径与 JSON renderer 未改 |
| 审核 / 恢复不补回内部 ID 或主人字段 | ApprovalSources 以完整 JSON 保存 conversations_result 并标 observation=historical；restoreEntries/codexEntries 保留消息；bounded 仅改 content | 沿实际消费链核对，无重新调用 sourceFacts 补字段；现有 provenance/history/recovery 测试通过 |

独立执行支持的 Node v24.22.1：

```sh
PATH="/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH" pnpm exec vitest run apps/im-server/tests/conversation-search.test.ts apps/im-server/tests/personal-sources.test.ts packages/dsh-integration/tests/approval-sources.test.ts
# 3 files, 29 tests passed; 2026-10-30 12:24 Asia/Shanghai
```

另外使用 `/tmp/feat680-identity-patch-repro.mts` 构造独立内存 IM + 真实 PersonalAgents/Work.query，配置 feishu owner_open_id，验证真实查询结果：

```json
{"case":"known-owner","sender":{"name":"owner","is_owner":true,"kind":"external","channel":"feishu","source_id":"owner-open"}}
{"case":"known-peer","sender":{"name":"owner","is_owner":false,"kind":"external","channel":"feishu","source_id":"other-open"}}
{"case":"unknown","sender":{"name":"owner","kind":"external","channel":"feishu"}}
```

此复现故意不设 sender_display_name，展示保留的显示名可以来自旧镜像账户，不能替代 source_id 证明作者。工具说明明确未知身份；没有从显示名推导 owner。脚本只用合成数据，不启动服务。`git diff 5e080ffbf 6066037d7 --check` 通过。caller 提供测试 red→green 过程，本 reviewer 独立复验 green，未修改固定现场重放 red。

### 修复范围与既存边界

本次修复的是 **Work 历史查询向模型投影的身份事实**，不等于整个 PA 宿主身份判定已修复。`apps/im-server/src/personal-agent.ts:123` 的 sourceFacts 仍将 `sender_user_id=owner` 且无 sender_source_id 的外部旧镜像判断为 is_owner=true；messageEvidence、pa.source.admit、authorization 与部分 owner 证据校验使用该函数。独立脚本对相同 unknown 消息观察到 Work 结果不含 is_owner，但 sourceFacts 仍为 true。

已对照 `git show 5e080ffbf:apps/im-server/src/personal-agent.ts`，该逻辑在 pre_fix_head 已存在，本 patch 没有新增或扩大它。历史 conversations_result 的审核/恢复也不会用此函数重新生成 sender，故它不使本轮修复后的 Work 结果反向恢复成旧字段。本轮不把该既存共同身份缺口算作新 patch finding，也不宣称 ownerMessage、实时输入摄取或其他宿主证据接口已经因此得到修复。若后续要统一这些 Surface，应另行明确范围并验证共享 owner 判定；不能仅用本报告宣称所有外部身份/授权路径均正确。

此前的模型行为与 provider-wire 限制继续适用；本轮没有独立运行真实模型旅程，最终产品复验由 product reviewer 承担。既有错误字段已经进入的历史 Context 不会被这个补丁追溯擦除，恢复只能保留当时真实记录，不是新的主人授权。

### Round 3 Handoff

- unit_id: `feat-680-agent-conversation-search`
- review_round / verification_mode: `3` / `targeted-closure`
- validated_at: `6066037d7a8abba46ae1ed1a96d483d85624e577`
- executed_base: `6b95850a67da5215f3e26dd433037de0fbde5ac5`
- verdict: `pass`; issues: `[]`; validated_issues: `产品验收未知外部作者的 Work 身份投影 closed`
- requires_full_verification: `false`
- report_path: `docs/changes/feat-680-agent-conversation-search/verification.md`
- report_commit: 共享现场由 caller 提交；仅修改本报告
- top_concern: 本轮只修历史模型投影；既存 sourceFacts 对缺失来源身份的判定仍未改变，勿扩大宣称
- 自建服务：无；未修改 caller 隔离数据或服务

## Corrected Delta Reconciliation

> verification_mode: corrected-delta · validated_at: `6066037d7a8abba46ae1ed1a96d483d85624e577` · executed_base: `6b95850a67da5215f3e26dd433037de0fbde5ac5` · inspected: 2026-10-30, Asia/Shanghai
>
> Delta: `docs/changes/feat-680-agent-conversation-search/specs/gateway/global-agent.md` → canonical `docs/specs/gateway/global-agent.md`。

Outcome: **delta-mismatch**。未发现新的 implementation-mismatch；1 项 WARNING 为 delta 遗漏稳定的模型结果行为。此前三轮实现审查通过结论保留，产品 `acceptance.md` Round 2 修复版 targeted 旅程 pass 作为最终真实行为证据。尚不能把当前 delta 原样认定为完整归并稿。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Requirement 主体：当前允许的 IM 同步历史、精确/多线索、组合过滤、排序、无任意时间窗口 | `work.ts:265`–`:275`，schema 明示已同步范围；可信宿主身份/当前权限 | Round 1/2/3 自动化；acceptance E1–E5、修复版外部真人/时间过滤 | aligned |
| 多线索和准确文本 | `work.ts:95`–`:97`, `:267`–`:275` | 多词/ERR-42 测试；真实 HERON-680/BLUE-680 与 relevance 对照 | aligned |
| 最近和筛选 | `work.ts:270`–`:275`，participant_id 与 sender_source_id 分离 | 旧历史、内部作者/时间和外部小乙 2024 组合，旧镜像内部作者不再命中 | aligned |
| 来源和前后文 | `work.ts:277`–`:280`, `:328`–`:350`; external→shadow 可信路由 | 修复版 search/around/精确 read；PA-only owner_can_read=false，已知/未知外部作者区分 | aligned |
| 分页与当前权限 | `work.ts:196`–`:230`, `:287`–`:304`；只投影当前仍可读/仍匹配候选 | 旧快照新增参数拒绝、内容指纹、来源排除后的 cursor/around 拒绝与允许来源继续；真实分页 | aligned |
| 完整与分段消息 | `tool-references.ts:113`–`:135` 合并顺序内容并标已知部分范围 | 单页正文+附件、首/末段、完整状态省略；与 partial 相关前轮证据 | aligned，未知缓存完整性未被本 Scenario 覆盖，见 D1 |
| 结果为空或历史不可用 | `work.ts:263`, `:370`; external 未同步错误；schema 同步范围 | 真正空结果、来源拒绝与未映射 target 错误；真实模型不把未查全说成不存在 | aligned，IM 断连实际旅程未测的原限制保留 |

### Uncovered Observable Behavior

#### D1 — delta 未覆盖聊天发现/缓存回读的完整性与分页结果语义（WARNING）

`packages/personal-assistant/src/tool-references.ts:109`–`:111` 在 **conversations list/read/search** 成功结果统一省略 has_more，无后续时省略 next_cursor；`external.ts:288`–`:292` 将本地来源读取明确区分为 external_cache，并将其消息完整性标为 unknown。这些是本 unit diff 实际引入且跨版本需保持的模型消费约定。

现有 delta 的“分页与当前权限”只描述搜索快照可继续及撤权；“完整与分段消息”只描述 search/read 中完整内容与已知前后片段，未包含：

- 聊天发现、历史读取与搜索的成功结果仅在存在后续时提供可续查提示；没有后续信息的终止含义不适用于错误或外部未同步历史。
- 只能从本地外部缓存取得的消息，其来源范围与完整性未知必须可辨认，不能与已知分段或完整 IM 历史混同；能定位镜像时可继续核实原文。

canonical 现有“模型读取简洁且可操作的 Inbox 结果”限定 **Inbox**，不能自动覆盖 conversations list；既有“缓存历史明确标出仅含已接收记录”也没有表达缓存消息完整性未知与已知分段的差异。因此这不是重复补写内部字段，而是遗漏两个相关的外部结果语义。

建议 delta owner 在现有 Scenario 中补一到两条稳定行为，或增加一个简短 Scenario；无需列出字段名、内部 cursor、part 编码或 50 条缓存实现常量。应描述已有实现/已确认设计，不改实现或静默放宽契约。本 verifier 未修改 delta 或 canonical。

证据：`tool-references.test.ts:18`–`:37` 的续页/末页与 partial 实际投影、`external.test.ts:20`–`:21` 的 external_cache/unknown 实际返回，均已于 Round 1 在相同实现上通过；这些文件后续未改，复用有效测试结果。本次没有重复跑全量或重新做产品旅程。

### 已有 canonical 覆盖与范围限制

- `docs/specs/gateway/global-agent.md:187` 的“外部聊天发送者没有 IM 身份映射”已经要求不把代记账号当作可私信作者、已知保留平台身份、未知只保留已知显示名。6066037d7 的外部作者投影修复符合该既有要求，无需为同一事实再增加新 Requirement。
- Inbox 不消费和双身份等要求由现有 canonical 持有，delta 引用沿用足够，不需要复制。
- 旧游标遇不兼容新参数或不可验证片段明确要求重查，是安全续查实现细节；当前“可继续查看允许访问的快照”不承诺不兼容游标永不失败，没有发现冲突。
- Round 3 记录的既存 sourceFacts 共同身份边界仍非本 delta 对模型历史搜索/回查的修复范围，未把局部投影修复升级成整个宿主授权链承诺。
- 当前 canonical 尚未归并，符合 active unit 状态；本轮只核对预备增量，不把尚未归并本身报为实现错误。共享现场原有 acceptance.md/verification.md 修改均保留。

### Corrected Delta Handoff

- unit_id: `feat-680-agent-conversation-search`
- verification_mode: `corrected-delta`
- outcome: `delta-mismatch`; issues: `D1`; requires_full_verification: `false`
- report_path: `docs/changes/feat-680-agent-conversation-search/verification.md`
- report_commit: 共享现场由 caller 提交；本轮仅追加此报告
- 下一步：delta owner 补齐 D1 后定向核对修订文本，不重新验收整个 unit

### D1 修订复核 — 最终 Outcome: aligned

复核对象为当前工作树中修订后的 `specs/gateway/global-agent.md`，产品代码仍固定在 `6066037d7a8abba46ae1ed1a96d483d85624e577`，executed_base 仍为 `6b95850a67da5215f3e26dd433037de0fbde5ac5`。仅 delta 增补文本，未变更产品实现或 canonical；前述 D1 发现记录保留作为修订依据，本段为 corrected-delta **最新结论**。

新增 Requirement“聊天工具结果准确说明续查与完整性”的两项 Scenario 与实现和有效证据一致：

| 修订项 | 实现 / 有效证据 | 结论 |
|---|---|---|
| 会话列表和历史结果的续查 | `ToolReferences.result` 对 list/read/search 只保留非空续页引用；DSH schema 限定成功结果与当前已同步范围；既有 projection 测试及产品真实分页证据 | aligned |
| 外部本地缓存完整性未知 | `external.ts:288`–`:292` 标出 external_cache/unknown、已镜像时提供 message_id；外部锚点/精确回查经当前 Agent 对应 shadow 并由 IM 复核；`external.test.ts` 与前轮有效测试 | aligned |

文字没有把缓存无下一页扩大为外部历史已查全，没有将未知完整性冒充已知分段，没有承诺未同步来源必然可读，亦未加入实现内部结构。此前六项场景已 aligned，本轮没有新增不符或 unit diff 的未覆盖对外行为。

**D1 closed；最终 outcome: aligned；0 critical / 0 warnings / 0 suggestions；requires_full_verification: false。** 本轮仅核对修订文本与既有实现/证据，不重复测试或产品全量旅程；原有 provider wire、容量样本及宿主 sourceFacts 范围限制仍成立。可由 caller 将最终 delta 归并 canonical；本 verifier 未改其他文件。

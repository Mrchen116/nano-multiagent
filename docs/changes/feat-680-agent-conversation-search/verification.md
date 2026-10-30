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

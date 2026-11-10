# 独立设计审查

## Round 1

| Metadata | 值 |
|---|---|
| reviewer | `/root/perf_design_gate` |
| target | `perf-746-scoped-web-replay` 冻结 design、motivation 与 M1 骨架，代码基线 `04a07bb2c` |
| review_mode | full |
| mode_reason | 首轮 Gate 2，核对真实 WS 入口、权限范围、恢复边界和查询代价 |
| started_at | 2026-11-09T21:30:30+08:00 |
| completed_at | 2026-11-09T21:32:40+08:00 |
| duration | 约 2 分钟 |

**Verdict** `Issues Found` · 0 CRITICAL / 2 WARNING

### Coverage 与证据

- **产品入口与安全边界**。中心在 [`server.ts`](../../../apps/im-server/src/server.ts#L198) 注册 `/im/ws/user`。[`gateway.ts`](../../../apps/im-server/src/gateway.ts#L895) 从 Origin 与一次性票据取得当前会话，显式 resume 与 30 秒兜底均在 `browserValid` 后调用 replay。旧 replay 对每一行调用 `conversationAccess`。拟复用的 [`qualifiedUser` 和 `readableConversationIds`](../../../apps/im-server/src/conversation-access.ts#L41) 对浏览器真人与现有逐会话判权使用相同的空间资格、成员和公群规则，并共享 `observerOwners` 对 Agent 私聊、PA 观察及双方参与结构的判断。两条路径均允许符合资格的解散历史。可见集合必须每次从当前数据库获得，不能借用 live 推送的接收名单，因为 [`conversationReaderIds`](../../../apps/im-server/src/conversation-access.ts#L100) 排除了非成员公群浏览者。现有 [`tenancy.test.ts`](../../../apps/im-server/tests/tenancy.test.ts#L128) 和同文件的协作私聊用例可复用为授权回归。
- **游标与恢复**。保持全局 high water、`(cursor, top]` 排他起点、全局事件顺序、原事件信封和同步完成后 presence 快照的职责放在现有 [`Gateway.replay`](../../../apps/im-server/src/gateway.ts#L221) 合适。保留原事件序列化，包括 `message.reconciled` 的时间来源。浏览器会在连接前同步资格和恢复订阅者，遇到 `resync_required` 再经 HTTP 对齐游标，按事件 ID 去重。无需另加前端协议、原型或一次性迁移。参见 [浏览器恢复实现](../../../src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts#L186) 与 [连接前同步](../../../src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts#L327)。
- **性能和 M1**。原路径用全局 ID 差直接降级，允许回放时才读全局 ID 范围的完整行。按会话范围索引取头、再按主键批取正文，可在同样数据和游标上区分无关事件、可见事件、正文读取数与实际客户端帧。中心同一代码路径承担恢复判定，不新增授权来源。M1 应覆盖少量可见事件夹在大量私聊、真实可见超限、窗口边界和当前授权。仓库已有 [`server.test.ts`](../../../apps/im-server/tests/e2e/server.test.ts#L26) 真实进程、Origin 和票据的 WS fixture，以及 [Web 恢复测试](../../../src/IM/frontend/src/realtime/user-stream/user-stream.test.ts#L276)。本轮只审设计与查询形状，实际收益及 Web 恢复结果待实施验证。

### Issues

#### R1-W1 可见窗口与首次订阅的分支需要明确，并写入恢复契约

[设计第二项](design.md) 同时规定阈值只看可见积压、游标为 0 保留首次订阅。当前 `Gateway.replay` 对 0 跳过时间窗口但仍用全局 ID 差判数量，30 秒兜底也走 0。正游标现状用全站 15 分钟内最早事件的 ID 作近似，直接在可见范围套用这个条件，会让相隔多条不可见事件的游标误判过期，也会在全部可见待补事件都已过期时因找不到近期事件而放行。需明确正游标如何从可见待补行判过期、零可见时的行为，以及 0 何时回放/降级并是否仍受全局数量影响。最小判据可用有无实际可见待补事件早于 cutoff，0 仍免于时间判断，数量规则明确选定。加入真实超限、全部过期与无可见积压的断言。

这是 `/im/ws/user` 消费者可观察的 replay 或 `resync_required` 分支变化，应在 [`agents-nodes.md` 的用户流 Requirement](../../../docs/specs/im/agents-nodes.md#L738) 用小型 MODIFIED delta 写明范围与降级结果，保留既有票据、游标同步、续期和撤权 Scenario。无需把 SQL 或具体数值写成长青契约。

#### R1-W2 先全局排序再 LIMIT 只限制返回行数

用本机 Node `node:sqlite` 3.51.3 在内存载入当前中心 schema，并临时建拟议索引，执行 `EXPLAIN QUERY PLAN SELECT event_id, created_at FROM conversation_events WHERE conversation_id IN (SELECT value FROM json_each(?)) AND event_id>? AND event_id<=? ORDER BY event_id LIMIT 2001`。计划按 `(conversation_id,event_id)` 做范围查找，但同时出现 `USE TEMP B-TREE FOR ORDER BY`，多会话积压无法在见到第 2,001 条可见头时立刻退出。真实超限会把旧版的快速拒绝变成对大量可见头的扫描，在同步 Gateway 路径上阻塞其它请求。去掉头查询的 `ORDER BY` 后，探针仍按同一索引做范围查找且无临时排序。应明确超限探测可先取任意 2,001 个头并尽早退出，阈内才按全局 ID 排序与发帧，或给出同等有界的查询。M1 对照需同时证明无关流量和大量可见积压两条路径的查询形状，超限时应零正文读取。

### Author Resolutions

- R1-W1 accepted。明确正/零游标、可见数量和过期边界，补用户流 Requirement delta 和回归范围。
- R1-W2 accepted。头查询去掉排序，任意 2,001 条即停止，确认回放后按事件 ID 排正文；加入阈值两侧的计划证据。

## Round 2

| Metadata | 值 |
|---|---|
| reviewer | `/root/perf_design_gate` |
| target | `perf-746-scoped-web-replay` 修订 design、用户流 delta 与 Author Resolutions，代码基线 `04a07bb2c` |
| review_mode | delta |
| mode_reason | 恢复规则及查询形状局部修改，新增有界 canonical delta。鉴权入口、当前权限、产品组装和用户目标沿用首轮 |
| started_at | 2026-11-09T21:34:45+08:00 |
| completed_at | 2026-11-09T21:35:10+08:00 |
| duration | 约 25 秒 |

**Verdict** `Approved` · 0 CRITICAL / 0 WARNING

### Coverage 与历史问题闭环

- **R1-W1 · closed**。Author Resolution 将 [design](design.md#L6) 固定为 `(cursor,top]` 中当前可读的待补事件。数量先判，大于 2,000 发原 `gap_too_large`。正游标只在实际可见待补事件早于截止点时发原 `replay_window_expired`，包括待补全部过期；无可见待补时继续并推进 high water。显式零游标与兜底均只按当前可见数量。验证安排涵盖这些分支。[用户流 delta](specs/im/agents-nodes.md#L5) 匹配 canonical Requirement 标题，六个既有 Scenario 齐全。调整的可读范围与已核实现一致，新增 Scenario 说明重同步条件和零游标例外，具体数值留在设计。
- **R1-W2 · closed**。Author Resolution 的 [design](design.md#L6) 按任意最多 2,001 个头判边界，确认回放后才按 ID 取正文和排序，降级时零正文。复跑 Node SQLite 3.51.3，使用当前 schema 和临时内存索引，以两会话的 `json_each` 形状做 `EXPLAIN QUERY PLAN`，仍是 `(conversation_id,event_id)` 访问且无临时排序。`EXPLAIN` 在 `ResultRow` 后以 `DecrJumpZero` 跳至 `Halt`，验证此查询形状能在限额处停止。方案安排同条件记录无关流量与大量可见积压的计划、正文读取量和帧。实际候选性能与真实 WS 结果待实施测量。
- **retained_from: Round 1**。鉴权、会话范围、连接和客户端恢复链路、事件信封与顺序、presence 和 M1 的服务 fixture 未改，沿用首轮代码定位和判断。

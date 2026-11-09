# 独立设计审查

## Round 1

| Metadata | 值 |
|---|---|
| reviewer | `/root/perf_design_gate` |
| target | `perf-749-direct-work-focus` 冻结 design、motivation 与 M1 骨架，代码基线 `04a07bb2c` |
| review_mode | full |
| mode_reason | 首轮 Gate 2，核对真实 Work 入口、持久排序、锚点和列表状态及用户可见变化 |
| started_at | 2026-11-09T21:30:30+08:00 |
| completed_at | 2026-11-09T21:34:15+08:00 |
| duration | 约 4 分钟 |

**Verdict** `Issues Found` · 0 CRITICAL / 3 WARNING

### Coverage 与证据

- **真实入口及权限**。聊天 [`message-pane.tsx`](../../../src/IM/frontend/src/features/chat/components/message-pane.tsx#L2058) 的 View Work 链接将 `message_id` 传给 Agent Work。中心 [`server.ts`](../../../apps/im-server/src/server.ts#L195) 注册 [`registerWorkRoutes`](../../../apps/im-server/src/work.ts#L390)，依次经过删除锚点、当前非 stale 的 Global profile、PA 本人及资源空间检查。已删除锚点的 `410` 另受原聊天资格限制。[`rejectDeletedExecution`](../../../apps/im-server/src/agent-deletion.ts#L32) 对正常 Work 视图无需增加来源聊天门禁，原聊天和附件保持独立权限。参见 [Work 权限契约](../../../docs/specs/im/agent-work.md#L28)。按需明细继续走现有同一鉴权路由。
- **持久关联、排序和接口职责**。`WorkRecords.view` 从持久 `message_sent` 事实按 root、消息 ID 及最早 revision 解析真实主执行，旧 `global_main` 也可匹配，未同步返回 `focus: null`。普通轮次查询按同一 session 中 `agent_work_turns.seq DESC`，`before_turn` 是排他的真实轮次 ID；`seq` 在轮次首次投影时写入并保持，消息发送 revision、消息/轮次 ID、时间和稠密名次均不能取代它。`WorkRecords` 复用摘要序列化和位置，Web 负责展开、滚动和分页呈现，中心不承担展示缓存。参见 [轮次投影](../../../apps/im-server/src/work-records.ts#L310)、[轮次分页](../../../apps/im-server/src/work-records.ts#L437) 和 [锚点查询](../../../apps/im-server/src/work-records.ts#L496)。
- **性能和 M1**。现有 Web effect 串行自动加载摘要页直至目标，`Turn` 等按需正文首批就绪才滚动一次。对于 1,000 轮、每页 20 的情形，首次定位的摘要请求数随深度增长。用本机 Node `node:sqlite` 3.51.3 在内存载入当前 schema，模拟 `agent_work_events(root_agent_id,json_extract(payload,'$.message_id'),revision) WHERE type='message_sent'`，保持原 JOIN/WHERE/ORDER BY 并取 `t.seq`。`EXPLAIN QUERY PLAN` 从仅按 root 扫描候选变成 `SEARCH e USING INDEX … (root_agent_id=? AND <expr>=?)`，另外两个 JOIN 仍是主键查询。没有启动服务或新增迁移。1,000 轮同 fixture 适合记录自首次点击到目标摘要及按需明细的请求数和响应规模，分别计当前主执行与历史主执行；保留同输入及冷热条件，可补实际首开耗时，单次请求数不能代替延迟测量。[现有 Web 定位逻辑](../../../src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx#L159)、[明细滚动](../../../src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx#L224)、[真实中心 Work fixture](../../../apps/im-server/tests/e2e/work-message-focus.test.ts#L6)。
- **前端体验证据**。基线沿用工作记录页内的同一个轮次卡片、正常及关联执行列表、普通「更早轮次」和原生轨迹返回。既有归档的 [真实 A/B 旅程](../archive/bugfix-728-view-work-wake/review.md#修订真实路径作者自检不代替用户重新确认) 只覆盖两条相邻记录，能说明保留两端列表和展开的历史要求，不能证明新方案中有缺口时的连续阅读。本轮没有实测新画面。只需要局部示意说明新增缺口反馈和分页的位置关系，无需新建整页交互原型。不存在适用的一次性部署前置。

### Issues

#### R1-W1 直接定位改变了已有 canonical Scenario

[设计第 3 项](design.md) 声明无需 delta。现行 [`agent-work.md` 的「再次查看较早回复」](../../../docs/specs/im/agent-work.md#L264) 明确承诺自动加载摘要页至目标。这一过程让用户可立即向上读到此前的所有中间轮次。新方案只载入普通页和目标，显式标出中间未加载，两者的可观察结果不同。请在本单元提交针对该 Requirement 的 MODIFIED delta，写明目标直接展开、已加载记录保留、尚未加载记录的标示与正常翻阅，保留同名轮次、历史主执行、折叠和阅读位置、迟到关联以及现有权限 Scenario。

#### R1-W2 需要分开定位查询与已加载列表的生命周期

当前 [主 Work infinite query](../../../src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx#L100) 用 `messageId` 作 key，切换锚点会读不同的普通页缓存。「缓存已访问的锚点」只说明旧目标摘要可留下，未保证已经主动翻阅的普通页和连续游标在 A→B→A 时仍然保留。保留旧 key 并换缓存拼装也可能让轮次之外的已加载邻居消失。请明确普通页按 Agent/执行复用并独立持有连续分页游标，锚点按来源消息和已授权 Agent/执行保存，命中普通页时以最新普通数据合并去重。锚点缓存沿用现有账号清理与失效边界，已删除、撤权或服务器明确返回锚点不可用时不能从旧快照继续恢复定位。历史主执行在对应的关联执行查询状态下做同样处理，保留一轮定位 token、已展开状态和轨迹往返滚动。M1 回归应在切换前先普通翻一页，再检验已载页、A/B 和后续游标均保留，并覆盖晚到关联和鉴权失败。

#### R1-W3 有缺口时仍需让用户认出连续范围和分页入口

[设计第 3 项](design.md) 只在「隔开数页」且两端同时可见时提示。只缺一轮、两个已缓存锚点之间有缺口、当前自动滚动后其中一端在屏外，也会误使旧轮看起来是连续邻居。`seq` 源于全局 revision，会被非轮次事件占位，数字相差不能判断中间还有几轮。现在主列表和关联执行的「更早轮次」都在整列卡片之后。如果直接沿用这个位置，用户跳到已经展开的很旧目标后，看到的按钮可能位于长正文下且语义看似继续加载该目标之前的历史，实际上分页从最新连续块的尾部开始。请明确标记真实未加载的范围、以及普通分页入口如何让用户从该处继续，复用现有按钮即可。应给出同一 Work 容器中的局部前后状态及本轮必验 Web 路径，至少覆盖目标紧随已加载范围、一个真实缺口、多个锚点、分页穿过锚点后提示消失，以及关联执行窄屏中仍能找到继续分页的位置。隔离服务可沿用现有 Work fixture 造实际发信事实和历史，不要求模型生成 1,000 轮。把决定性入口与证据写进 M1，避免只验目标展开和按钮存在。

### Author Resolutions

- R1-W1/W2/W3 accepted。新增 canonical delta，普通页与锚点缓存解耦，以实际相邻轮 ID 判缺口并指定分页和验收。

## Round 2

| Metadata | 值 |
|---|---|
| reviewer | `/root/perf_design_gate` |
| target | `perf-749-direct-work-focus` 修订 design、Work delta 与 Author Resolutions，代码基线 `04a07bb2c` |
| review_mode | delta |
| mode_reason | 局部补齐缓存生命周期、缺口呈现、Web 验证与对应契约，保持首轮产品入口、鉴权和持久映射 |
| started_at | 2026-11-09T21:36:23+08:00 |
| completed_at | 2026-11-09T21:36:55+08:00 |
| duration | 约 32 秒 |

**Verdict** `Approved` · 0 CRITICAL / 0 WARNING

### Coverage 与历史问题闭环

- **R1-W1 · closed**。Author Resolution 补 [Work MODIFIED delta](specs/im/agent-work.md#L5)。逐行对照 canonical 四个 Scenario，只有「再次查看较早回复」的结果变化，改为直接展开、保留已载记录、标示未载记录与普通分页。历史主执行、同名唤醒、折叠及阅读位置、迟到关联和来源聊天权限仍保留。
- **R1-W2 · closed**。Author Resolution 的 [设计](design.md#L6) 使普通页和连续游标依 Agent/执行独立于消息定位请求，覆盖现有 key 含 `messageId` 所造成的缓存分离。普通页以当前摘要覆盖同一轮锚点，失效锚点按账号、撤权、删除和不可用的边界淘汰。历史主执行沿用自己的查询面板。M1 验证先从 A 主动翻页，再换 B 和 A，检查已载邻居、分页游标、折叠和轨迹返回，以及迟到和撤权。
- **R1-W3 · closed**。Author Resolution 明确在实际相邻轮缺失时于两张卡之间显示提示，普通「更早轮次」位于连续已载区间末尾并使用原分页游标。提示不依赖缺页数量或视窗。以当前 schema 和非连续 `seq` 造内存轮次，`WHERE session_id=? AND seq>? ORDER BY seq ASC LIMIT 1` 使用 `agent_work_turns_sequence` 做范围查找。将实际相邻 ID 与上一张卡对照，可辨认紧邻、单轮缺失和两个缺口，补页后只移除已填平的提示。局部文字和按钮位置已经在 [方案](design.md#L7) 表达，未引入新的操作路径。M1 安排从 Web 实际入口验证，并检查关联执行窄屏。内存探针只验证判定方式，真实 Web 画面和分页操作待实施验收。
- **retained_from: Round 1**。真实 Chat→Work 路由、中心资格和删除判断、持久 `message_sent` 关联及普通 `seq DESC` 排序未改，保留首轮证据。性能仍以同一长历史 fixture 的请求数和摘要返回量比较为准。

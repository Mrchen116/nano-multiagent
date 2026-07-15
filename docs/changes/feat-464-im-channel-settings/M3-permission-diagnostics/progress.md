# feat-464-M3 — Progress

## Baseline

- Context: 完整读取 change-impl-worker、AGENTS/SPEC/COMMENTING_GUIDE/TESTING_GUIDE/LOGBOOK、unit spec/design/delta/prototype 与 M1/M2 tasks/progress/evidence；通过高位 HTTP + headed Chromium 打开 M3 三个 must-match 原型状态，并定位 Feishu client/adapter/worker、ChannelManager/cache/IM connection、ChannelControlStore/GatewayHandler/user stream 与 channels panel seams。
- Evidence:
  - Backend: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/IM/test_agent_channels.py tests/unit/personal_assistant/test_channel_manager.py tests/integration/test_channel_reconcile.py tests/unit/test_feishu_client_scopes.py tests/unit/test_feishu_adapter_scope_warning.py` → `18 passed`。
  - Frontend: `npm run test -- agent-channels-panel.test.tsx agent-status-ws-consumer.test.ts im-agent-config-api.test.ts` → `3 files / 21 passed`；`npm run build` → PASS（443 modules transformed）。
  - Prototype: `http://127.0.0.1:59609/.../prototype.html` headed Chromium 验证 `#channel-limited` 同时含 confirmed missing + unknown、`#channels-error` error/retry 且无 empty、移动模式单列及 add bottom sheet；唯一 console error 是 prototype 既有 `/favicon.ico` 404，server/browser 已清理。
- Next: R1 先提交 capability catalog/tenant grant/structured diagnostics 红测，再实现生产路径。

## R1 — Feishu 租户授权目录与结构化诊断

- Context: M1 只用 `scope_name` 存在性发启动 warning，既不读取 `grant_status/scope_type`，也没有能进入 IM/UI 的结构化 capability catalog；因此 grant=2 和 user identity 会被误报为应用权限完整。
- Decision: 新增 provider-owned immutable catalog，逐项声明 current/legacy `accepted_scope_sets` 与只含 current scopes 的 `recommended_scopes`；`FeishuClient` 在启动 worker 前只调用一次 application v6 tenant authorization status，把完整 probe 归一为 granted set，缺字段/未知枚举/API/解析失败整次 unknown。每个 worker connection status 都附带 aggregate + checks，经 `ChannelManager` 与 production status bridge 进入 IM 协议。
- Rationale: scope 归一、等价集合与诊断汇总集中在 provider 深模块，adapter 不再重复调用单 scope warning 路径；连接状态仍由 worker incarnation/sequence 负责，诊断只作为正交字段附着，因此 permission unknown 不会变成 connection failed。
- Evidence:
  - Tests: C1 缺 `feishu.diagnostics` 按预期 collection red；C2 provider/client/manager/worker 组合 `79 passed`，production runtime/reconcile/shutdown 接线 `16 passed`，test naming/size contract `2 passed`。
  - Entry: `FeishuClient.start()` 构造真实 SDK REST client 后先读取一次 `/application/v6/scope/list` 语义，再启动 listener；`main._send_channel_status()` 把每项 `check_id/state/accepted_scope_sets/recommended_scopes/effect/remediation` 发入真实 `channel.status` frame。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 逐个参数化证明 p2p/group-at/send/group-message/history/group-history/reaction/chat 的每个 current/legacy accepted set 都能 satisfied；grant=2、user identity 不进入 granted set，缺 status/type、未知 enum、API/parse failure 均 unknown；普通群 history 只在完整 history + group-message set 时满足。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R1 C2 恢复旧启动 warning，不改变 M1/M2 lifecycle schema；R1 C1 同时回滚以恢复旧测试契约。
- Commits: C1=`cf2370368`，C2=`5d08c5c7f`，C3=本提交。
- Next: R2 为 incarnation barrier/latest snapshot 建立 durable outbox，并让 terminal stale/removed ACK 在释放 FIFO 后执行 drop/quarantine；同时补 IM user-stream 精确失效。

## R2 — 状态因果、terminal ACK 与 user-stream 精确刷新

- Context: 原状态 sink 只把快照放进进程内单槽 FIFO：离线/进程重启会丢状态，seq>1 可在 barrier 未确认时直接排队；`channel.status.result` 虽能 dequeue，却没有 outcome handler，stale/removed/busy/owner mismatch 都不会驱动 outbox 或 runtime。IM 接收端已有 revision/incarnation/sequence CAS 与 IM 接收时间，但 accepted 后没有频道级 user-stream 事件，前端也无法精确刷新 channels query。
- Decision: 在同一 mode-0600 manifest cache 内新增每 channel 的 durable `barrier/inflight/latest/retired` 状态 outbox；seq=1 原子替换 generation 并先发，后续状态只合并 latest，accepted/already_current ACK 才提升 latest。IM connection 先按 request_id 释放 FIFO 再调用 result handler；stale 丢 generation、removed 只 quarantine 匹配 revision、busy 退避后入队尾部、owner mismatch 停全部 managed runtime 并关闭 WS，同时保留密文 cache。IM 的 status CAS 同事务返回 owner/agent target，仅 accepted 广播 `agent.channel.status_changed`，前端 exact invalidate `['settings','agents',agentId,'channels']`。
- Rationale: barrier 与 latest 的发送资格由持久 owner 决定，既能跨断线/重启重放，也不会让 worker 的 seq>1 越过 incarnation identity；result handler 在 dequeue 后运行，终态处置失败不会把旧 frame 永久卡在单槽 FIFO。runtime quarantine 带 revision guard，延迟的旧 removed ACK 不会杀死新 replacement；用户流只发不含诊断/secret 的失效事件，HTTP 仍是 observed projection 的唯一数据源。
- Evidence:
  - Tests: C1 分别证明缺少 status outbox、terminal handler/event builder 和 frontend invalidation；C2 focused backend `29 passed`，扩展 manager/store/IM connection/IM projection/GatewayHandler/contract 回归共 `94 passed`，frontend consumer `5 passed`，focused Ruff PASS。
  - Entry: production `_send_channel_status()` 先写 durable outbox，只把当前 sendable barrier/inflight 交给 `IMConnectionManager`；真实 `channel.status.result` request_id dequeue 后进入 `_handle_channel_status_result()`，再执行 drop/retry/quarantine/close 与 latest 提升。`GatewayHandler._handle_channel_status()` 在 SQLite accepted 后通过真实 `UserStreamRegistry` 广播目标 owner/agent/channel。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: offline revision N 的 barrier + coalesced seq2 遇到 `terminal_channel_removed` 后，测试同时断言 outbox 清空、匹配 cached runtime stop/registry remove，且排在其后的 `channel.reconcile.result` 继续发送；同 revision 的旧 sequence/无 seq1 新 incarnation 被拒，新 incarnation seq1 可接管。`received_at` 忽略 Gateway 伪字段并取 IM 时钟，node offline 时 observed stale；busy 返回 correlated retryable，owner drift 返回 fatal。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R2 C2 恢复进程内直接发送与旧 user stream；同时回滚 C1 移除新因果/终态契约测试。cache version 未提升，旧文件缺 `status_outbox` 会按空 outbox 兼容读取。
- Commits: C1=`6a498082a`，C2=`dcdcb876b`，C3=本提交。
- Next: R3 实现 diagnostics/list error 的真实 channels panel 投影与 375×812 bottom sheet，再用组件测试和 build 固化。

## R3 — limited/unknown/error 与移动端 sheet

- Context: M2 channels panel 只展示 connection lifecycle，虽然 IM HTTP 已透传 `diagnostics_state/checks`，前端类型未声明 checks、卡片完全忽略权限事实；list error 已有独立 error 分支但缺专门回归，通道 add/edit/confirm 仍始终使用居中 modal，375×812 下动作区只靠 flex wrap。
- Decision: 扩展 `ChannelObservedState` 的结构化 diagnostics 类型，并在 connection card 内增加与连接 pill 正交的 limited/unknown 区域：逐项展示 check id、recommended raw scopes、影响、修复方向和开放平台动作；普通群消息缺权限定制中文/英文“群背景上下文不完整”说明，unknown 使用独立中性文案且不出现 missing。卡片加入稳定 responsive class，<768px 动作区单列卡片内两列按钮；add/edit/disable/delete confirmation 统一复用既有 `chat-modal-bottom-sheet` 与 safe-area footer。
- Rationale: diagnostics 保持 HTTP projection 的只读视图，不把 provider checks 复制成前端推断；连接失败/重连与权限 unknown 可以在同一卡片同时出现。移动端复用项目已有 bottom-sheet primitive，避免新增第二套弹层状态机；error 分支仍由 React Query error/refetch 驱动，只有 200 空数组进入 empty。
- Evidence:
  - Tests: C1 新 diagnostics/responsive 文件四场景全部 red；C2 targeted diagnostics/panel/status consumer `16 passed`，全量 frontend `66 files / 617 passed`，i18n focused `10 passed`，生产 build PASS（443 modules），test naming/size contract `2 passed`。
  - Entry: `AgentChannelsPanel` 从真实 `GET /im/v1/agents/{agent}/channels` 的 `observed.diagnostics_state/checks` 渲染；list query reject 保持 error card + `refetch()`，移动判断使用生产 `useIsMobile()` 的 768px breakpoint，add/edit/confirm 进入真实 bottom-sheet DOM。
  - Frontend State Matrix: limited 同时保留 connected；unknown 可与 failed 同时出现且无 missing；list error 有 retry 无 empty；375px 卡片/动作/底部 sheet；原 loading/empty/disabled/submitting 行为由既有 7 个 panel tests 保持。
  - Browser QA: TODO
  - E2E/Regression: 组件测试输入真实 HTTP shape 的 missing `im:message.group_msg` + unknown history，断言 raw scope、影响、修复方向、群背景文案；unknown aggregate + failed connection 分层；首次 list reject 后 retry 成功；375px 依次验证 add/edit/delete confirm 三类 sheet 与确认动作可见。
  - Visual/Interaction: CSS contract 在 <768px 将 channel header/action 区转为单卡布局，动作两列等宽，footer 纵排；scope token `overflow-wrap:anywhere`，bottom sheet 带 handle 与 safe-area padding。R4 再以真浏览器像素/DOM 取证。
  - Prototype Comparison: TODO
- Rollback: 回滚 R3 C2 恢复 M2 card/modal；同时回滚 C1 移除新 diagnostics/error/mobile 契约。后端 checks 字段是可选类型，回滚前端不影响 Gateway/IM 数据兼容。
- Commits: C1=`4ad1c50b7`，C2=`e7f01d9fa`，C3=本提交。
- Next: R4 用 worktree 真栈和 Playwright CLI 落 limited/unknown/list-error/375×812 durable 证据，并以真实飞书测试应用完成 E8 与 secret/listener/stop-restart 审计。

## R4 — 真栈浏览器、真实飞书 smoke 与总门禁

- Context: 真实测试应用已经完整授权，官方 probe 得到 34 个 tenant grants 且 8 项 capability 全 satisfied，无法在不破坏外部共享配置的前提下制造真实 limited；首次真栈日志审计还发现 Lark SDK 默认 INFO 会记录带临时 `access_key/ticket` 的完整 WebSocket URL。
- Decision: 经 orchestrator 批准采用证据拆分 B：真实应用只证明官方 complete probe、连接、stop/restart、单 listener 与 secret 安全；limited/reconnecting/failed + unknown 用 production `ChannelControlStore`、production catalog 和 live IM SQLite 注入状态，再经真实 IM HTTP 与真实前端取证，明确不冒充 provider live result。SDK worker 固定 `LogLevel.WARNING` 并用 red test 锁定；所有含旧日志的临时产物删除后重取证。
- Rationale: 不撤销真实测试应用权限、不伪造外部 provider 结果，同时仍穿过生产存储、HTTP 和前端边界验收所有 UI 状态；provider grant/parse 语义由参数化永久测试和官方 complete probe共同覆盖。SDK 的临时连接 URL 属 credential material，抑制 SDK INFO 是生产安全修复而非证据清洗。
- Evidence:
  - Tests: focused Feishu worker/client/scope `35 passed`；full backend `3425 passed, 1 skipped, 20 deselected`；full frontend `66 files / 617 passed`；production build PASS（443 modules）；Ruff PASS；test naming/size contract `2 passed`。
  - Entry: worktree 真栈运行在高位 IM `64311`，真实 Agent detail → Channels 通过 authenticated IM HTTP 读取。最终 authoritative snapshot 为 `connected/complete`、8 satisfied/0 missing/0 unknown；官方 application-v6 probe 为 34 tenant grants，8 项均匹配 accepted set。
  - Frontend State Matrix: desktop connected/complete、connected/limited、reconnecting+unknown、failed+unknown、list error+retry；mobile 375×812 单卡与 add/edit/delete confirm bottom sheet 全部通过。loading/empty/disabled/submitting 继续由全量回归守护。
  - Browser QA: headed Chromium、真前端/真 HTTP；注入 limited/unknown 只使用 production store，不用 route mock/static DOM/fake provider。故意停 IM 后 UI 展示 error + Retry 且无 empty，点击 Retry 产生第二次真实 `ERR_CONNECTION_REFUSED` 请求；同 DB/JWT/端口恢复后页面恢复。断网前 console 0 error/0 warning。
  - E2E/Regression: 真实应用官方 probe 于 `2026-07-15T11:27:42.535995Z` 返回 complete；最终 Gateway/listener `43122/44037`，旧 `30176/31110` 均退出，仅 1 listener + 1 resource tracker。IM DB/cache/config/log/evidence/HTTP secret hits 均 0，日志 `access_key=/ticket=` 与 Lark INFO 均 0；config/cache/key mode 0600，config 仅 credentialRef、无 appSecret。两条 restart 前 SDK 网络 ERROR 后由 final complete snapshot 明确证明恢复。
  - Visual/Interaction: 9 张 durable PNG 覆盖 complete、limited、reconnecting/failed unknown、真 IM list outage、375×812 卡片与三类 bottom sheet；raw scope 可换行、群背景影响与 remediation 可读，关键动作可触达。
  - Prototype Comparison: `#channel-limited`、`#channels-error`、`#channels-mobile`、`#channel-reconnecting/#channel-failed` 的 must-match 行为全部 PASS；视觉 token 复用现有 IM primitives，未引入未来 provider/Web IM。
- Rollback: 回滚 R4 C2 恢复 SDK 默认日志级别会重新暴露临时 WS URL，因此只应与 C1 安全测试一并回滚；evidence/docs 可独立回滚，不改变 R1-R3 生产行为。
- Commits: C1=`c583ade75`，C2=`c7c75e878`，C3=本提交。
- Next: M3 完成，集成 `unit/feat-464-im-channel-settings` 并清理真栈/worktree。

## Prototype Comparison

| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `#channel-limited` | limited + unknown checks；raw scope、影响、修复；普通群背景上下文 | `evidence/output/playwright/channel-limited-production-store.png` | 1440×1000 / connected + limited | PASS | 真实应用已 complete；limited 明确来自 production-store harness，不伪造 provider live result |
| `#channels-error` | list error + retry；不渲染空态 | `evidence/output/playwright/channels-list-error-real-im-outage.png` | 1440×1000 / IM outage | PASS | 真 IM outage + 真 Retry 请求，无 route mock |
| `#channels-mobile` | 375×812 单列卡片 + bottom sheet，动作可触达 | `evidence/output/playwright/channels-mobile-375x812.png` 与三类 sheet 截图 | 375×812 / connected + limited + sheet | PASS | 复用现有 `chat-modal-bottom-sheet` primitive |
| `#channel-reconnecting/#channel-failed` | 连接故障与权限 unknown 分层 | `evidence/output/playwright/channel-reconnecting-unknown-production-store.png`、`channel-failed-unknown-production-store.png` | 1440×1000 / reconnecting或failed + unknown | PASS | production-store harness 驱动真实 HTTP/frontend 投影 |

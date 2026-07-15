# feat-464-M2 — Progress

## Baseline

- Context: 完整读取 change-impl-worker、spec/design/delta/prototype、AGENTS/SPEC/COMMENTING_GUIDE/TESTING_GUIDE/LOGBOOK 与 M1 tasks/progress/evidence，并定位 IM store/REST/WS、Gateway manager/cache/connection/composition root、local YAML、e2e scripts 与 frontend seams。
- Evidence:
  - Backend: `.venv/bin/pytest -q tests/unit/IM/test_agent_channels.py tests/unit/personal_assistant/test_channel_manager.py tests/integration/test_channel_reconcile.py` → `10 passed`。
  - Frontend: 首次因 worktree 未安装依赖稳定失败 `vitest: command not found`；确认主仓依赖正常且 worktree `node_modules` 缺失后执行 `npm ci`，再跑 `agent-channels-panel.test.tsx` → `4 passed`、`npm run build` 通过（443 modules transformed）。
  - Prototype: 通过高位本地 HTTP + headed Chromium 打开 `prototype.html`，确认 M2 must-match 文案/交互与源文件一致；prototype 唯一 console error 是其既有 `/favicon.ico` 404。

## R1 — Gateway 密文 manifest、可靠 outbox 与完整调和

- Context: DONE；M1 的 `ChannelManager.start_cached()` 仍是占位，reconcile 只看 active runtime，删除没有 explicit token/result outbox，stop 失败会丢失可重试 runtime 身份，也无法证明本地 cache 提交后才算 removal applied。
- Decision: 新增 mode-0600、fsync+rename 的 `ChannelManifestStore`，只持久化 credential envelope 和 node/key header；head result 与 removal token 分槽保存并逐 token ACK。`ChannelManager` 现在可从 cache 经注入 opener 启动，按 last-seen 拒绝 stale，同 revision 在 stop/cache failure 后重试，并只在 runtime stop 与 cache commit 都成功后回 removal applied/already_absent。
- Rationale: 完整 manifest 是离线启动的可用性来源，但 plaintext credential 绝不能落盘；removal outcome 的生命周期与 node applied head 正交，单槽结果会在新 revision 下覆盖未确认删除，因此 per-token outbox 必须独立保留。
- Evidence:
  - Tests: C1 因缺 `ChannelRemovalIntent`/manifest store 按预期 collection red；C2 manager/store/integration 组合 `11 passed`，test naming/size contract `2 passed`。
  - Entry: `ChannelManager.start_cached()` 读取密文 cache 后才调用 injected credential opener 并启动 stable `feishu:<agent_id>`；`reconcile()` 的 removal result 直接作为 Gateway WS 入口的领域返回值。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 覆盖 node/key mismatch、0600/atomic/no plaintext、offline cached start、never-seen already_absent、stop/cache failure、同 revision retry、跨 revision token replay 与 terminal ACK；目标 Ruff 通过。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R1 三提交恢复 M1 的仅内存在线 manager；不会触碰 IM desired 数据，但离线启动与删除闭环失效。
- Commits: C1=`5e11ed2c1`，C2=`8578387cd`，C3=本提交。
- Next: R2 实现 IM removal receipt、DELETE/reconnect/retry API 与 reconcile result token ACK。

## R2 — IM removal receipt、生命周期 API 与可靠 result ACK

- Context: DONE；原有 IM desired store 只有 active rows，DELETE/receipt/retry 不存在；旧 reconcile result 只保存 head 且 generic ACK，无法让 Gateway 按 removal token 安全清 outbox。Gateway 客户端也不能消费 live reconnect 或 modern ACK。
- Decision: `ChannelControlStore` 在删除 active row与推进 manifest 的同一事务写入无凭据 removal receipt，并把 pending/failed receipt 投影到 GET 和 full manifest；result 对 head 与 token 分别判定，applied receipt 即时隐藏，保留期后只有 applied head 覆盖才清理。HTTP 增加 DELETE、live reconnect、same-revision retry；WS 同时保留 legacy ACK 并为现代 payload 返回 correlated per-token ACK，Gateway 消费 reconnect/ACK 并释放 FIFO。
- Rationale: desired 删除必须先持久化才能容忍节点离线，而产品卡片必须等 runtime stop/cache commit result 后才消失；token ACK 与较新的 head revision 正交，不能用单一 generic ACK 猜测删除完成。manual reconnect 是 live action，节点离线明确 409，不伪装保存成功。
- Evidence:
  - Tests: C1 因缺 `ChannelRemovalView` 按预期 collection red；C2 IM store/HTTP/WS/Gateway client 组合 `15 passed`，目标 Ruff 全绿。
  - Entry: `DELETE /im/v1/agents/{agent_id}/channels/{channel_id}` 持久 receipt；`POST .../actions/reconnect` 只向在线 node 发 `channel.reconnect`；`POST .../channel-removals/{channel_id}/actions/retry` 重放当前 revision；`channels.reconcile.result.ack` 逐 token 返回 terminal outcome。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 覆盖 zero-item manifest+removal、offline disable/delete/reload、pending uniqueness guard、failed/retry same revision、applied hide、delete-no-cascade、receipt retention/applied-head terminal、connected reconnect 与 Gateway ACK callback/FIFO release；legacy result ACK 回归仍绿。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R2 三提交后 active channel 的 create/update 仍可用，但 DELETE/retry/reconnect 与 removal result 协议不可用；数据库 receipt 表保持无害未消费。
- Commits: C1=`5ee2e4596`，C2=`586408622`，C3=本提交。
- Next: R3 接入 Gateway manifest store/key cache，完成旧 YAML bootstrap、credentialRef/export 与 e2e 隔离。

## R3 — 旧 YAML bootstrap、credentialRef/export 与 e2e 隔离

- Context: DONE；Gateway 的密文 store 在 R1 尚未接入生产装配，启动也不会 `start_cached()`；IM 无 initialized 协议，人工 bind 后只尝试 replay 不存在的 head；YAML 只接受明文 `appSecret`，worktree 起停也未隔离新 key/cache。
- Decision: node.register capability 显式协商 bootstrap；IM 在 register/bind 共用的串行初始化入口中区分 waiting/bootstrap/initialized，同一 WS 人工 confirm 立即发一次 request，bootstrap 在独立事务生成 revision 1，之后只 replay 权威 manifest。Gateway 用自身公钥封装 legacy secret，权威 manifest 经 manager 写入 cache 且 outcome applied 后才原子保存 `credentialRef` YAML；重启先从 node/key scoped cache 启动。新增显式 `--output` rollback export，e2e-up/down 同时清理 key/cache。
- Rationale: initialized head 是“尚未迁移”与“用户已经删除到空”的唯一可靠边界；capability negotiation 保持旧 Gateway/既有 WS 测试兼容。cache 与 YAML 的提交顺序保证任一步失败仍有至少一个可启动的凭据来源，且正常 cache 永不含 plaintext。
- Evidence:
  - Tests: C1 因缺 migration API 按预期 collection red；C2 bootstrap/protocol/cache/export/main wiring 组合 `36 passed`，local-store/WS/bind/registration/test-contract 组合 `81 passed`，目标 Ruff 全绿。
  - Entry: `channels.bootstrap.request → channels.bootstrap → channels.bootstrap.result → channel.reconcile.result`；`ChannelManager.start_cached()` 在 IM loop 前运行；`scripts/channel-control-export-legacy.py --output ...` 生成 mode 0600 回退配置。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 覆盖 same-WS manual bind bootstrap once、initialized replay、client apply-before-cleanup、credentialRef parse/secret removal、mode-0600 export/no stdout secret、old-head ACK 不清 newer outbox、node/key cache guard 与 e2e key/cache cleanup contract。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 停 Gateway 后先用 export script 生成旧 YAML，再回滚 R3；IM initialized rows无需删除，旧二进制忽略它们。
- Commits: C1=`e3155ab01`，C2=`68333c71e`，C3=本提交。
- Next: R4 扩展前端 removal model、离线 banner、启停/重连/删除确认及 failed retry 投影。

## R4 — 前端离线投影与生命周期交互

- Context: DONE；M1 页面只有 create/edit 和粗粒度 connected/failed/connecting，不能调用 R2 的 reconnect/delete/retry，也会在删除 active row 后错误进入 empty，无法区分“已保存等待节点”“正在停用”与 observed disabled。
- Decision: channels API 返回 active/removal union 并暴露 live reconnect、revision-guarded delete 与 removal retry；Agent detail 把真实 node status 下传，卡片按 desired/sync/observed 三层投影 pending/connecting/disabling/disabled/reconnecting/failed/deleting。停用与删除增加明确确认框，removal receipt 独立卡片阻止过早空态，失败 receipt 保留原因和 retry。
- Rationale: 页面状态必须来自后端权威 desired/removal 与 Gateway observed，而不是 mutation 本地猜测；离线 desired 操作仍可保存，但 live reconnect 明确禁用，避免把未执行动作伪装成成功。
- Evidence:
  - Tests: C1 新增离线、停用、删除 reload/retry、reconnect 与 API 路径测试并按预期失败；C2 focused frontend `45 passed`，`npm run build` 通过（443 modules transformed）。
  - Entry: 真实 `AgentDetailPage → AgentChannelsPanel` 下传 raw node status；`DELETE ...?channel_revision=`、`POST .../actions/reconnect`、`POST .../channel-removals/.../actions/retry` 均由页面交互触发。
  - Frontend State Matrix: covered=default/empty/error/disabled/submitting/missing observed/desktop wrapping；loading 沿用 M1，permission/mobile/dark 按 tasks 约定不在本 roadpoint。
  - Browser QA: 推迟到 R5 真栈 headed Chromium，单测使用真实组件交互而非静态文案断言。
  - E2E/Regression: 覆盖 offline pending + node-offline action、disable confirm → disabling → disabled、credential retained、reconnect projection、delete confirm → removal pending、reload failed receipt → retry、removal 不落 empty。
  - Visual/Interaction: 动作按钮按状态收敛，offline banner、确认框、removal/failure detail 均可换行；内部 revision 不展示。
  - Prototype Comparison: `#channel-pending/#channel-actions/#channel-disabling/#channel-disabled/#channel-deleting/#channel-reconnecting/#channel-failed` 的信息层级与文案已实现，最终像素/真入口截图在 R5 对账。
- Rollback: 回滚 R4 三提交恢复 M1 create/edit 页面；R1-R3 backend lifecycle 协议仍保持兼容，但用户不能从 Web IM 操作完整生命周期。
- Commits: C1=`bebcc4b2d`，C2=`a08ec2c9b`，C3=本提交。
- Next: R5 用隔离高位真栈和 headed Chromium 验证七个原型锚点、DB/runtime/outbox/cleanup，再跑总门禁。

## R5 — 真栈浏览器证据与总门禁

- Context: DONE；用 worktree 隔离 IM/Gateway、真实 Feishu worker 与 headed Chrome 走完整 Agent detail → Channels 旅程。浏览器验收额外发现两个单测未暴露的投影缺口：reconnect endpoint 返回发命令前快照导致状态闪回 Connected；`sync_state=failed` 比 observed failed 优先导致真实 worker 失败仍显示 Connecting。
- Decision: manual reconnect 在真实 post-command observed poll 到来前保留两秒稳定 reconnecting 投影；runtime/reconcile failed 优先于一般 pending/connecting。两处均先以真实栈 + DB/调用顺序证明根因，再补红测、修复并重建前端。
- Rationale: ephemeral live action 的响应不是执行结果，不能覆盖动作态；failed 是用户必须处理的终态，不能被“尚未 applied”这个更低优先级状态遮住。
- Evidence:
  - Tests: frontend 全套 `612 passed` + build；M2 backend `123 passed`；Ruff 全绿。首次 non-e2e `3379 passed / 3 failed`，三项均为新增 negotiated `channel_bootstrap` 后未更新的 golden expected dict，更新后聚焦 `3 passed`；最终 post-rebase full gate 见本节后续记录。
  - Entry: 真实 `http://127.0.0.1:56189/settings/agents/default-agent`，headed Chrome 1440×1000；create/PATCH/reconnect/DELETE/retry 均走 authenticated production HTTP + Gateway WS。
  - Frontend State Matrix: default/empty/error/disabled/submitting/missing observed/desktop 全覆盖；loading 沿用 M1；offline live action 为 disabled “Node offline”。
  - Browser QA: 七锚点、offline create→delete-before-first-sync、reload removal、failed retry、result 后 empty 全部 PASS；详见 `evidence/browser-qa.md` 与 14 张截图。
  - E2E/Regression: real legacy bootstrap → connected；disable → observed disabled → re-enable connecting；manual reconnect；invalid credential worker failure；paused node desired/delete/reload/resume convergence；controlled cache failure same-revision retry；mode-0600/no-plaintext/cache cleanup。
  - Visual/Interaction: 1440×1000 无遮挡或横向溢出，动作层级与原型一致；长错误可换行，状态信息不显示内部 revision。
  - Prototype Comparison: must-match 七锚点全部对账；may-adapt icon/shadow/transition 继续使用现有 IM design tokens；Web IM/future providers 未进入 managed provider picker。
- Rollback: 先用 `scripts/channel-control-export-legacy.py` 显式导出旧 YAML，再按 R1→R4 逆序回滚；R5 只增加证据和两个投影修复，无协议迁移。
- Commits: headed defect tests/fixes=`6492f43c8/dd6d196b8/a9d2c45f5/167a259dd`；capability golden=`a3198d647`；evidence/C3=本提交。
- Next: rebase unit integration head，复跑门禁，合并并清理 milestone worktree/branch。

# feat-464-M1 — Progress

## Baseline

- Context: 完整读取 spec/design/delta/prototype、AGENTS/SPEC/TESTING_GUIDE/LOGBOOK，并定位现有 IM/Gateway/Feishu/Agent detail seam。
- Evidence:
  - Backend: `71 passed`（account binding、Gateway handler/registry、Feishu adapter/approval）。
  - Frontend: `28 passed`（Agent detail）；现存 React act warning 不影响基线结果。
  - Prototype: 通过真实 Chromium 打开 `prototype.html`，确认四个 M1 must-match 锚点与 out-of-scope provider 约束。

## R1 — IM 安全控制面与 HTTP 入口

- Context: DONE
- Decision: IM channel desired/config、manifest head、status/removal/key 表一次性建齐；所有 channel 命令由按 resolved DB path 创建短连接的 `ChannelControlStore` 用 `BEGIN IMMEDIATE` 串行化。Secret 用 X25519 + HKDF-SHA256 + AES-256-GCM v1 envelope，HTTP 只投影 `secret_configured`。bind confirm 在写 bind/node/profile 之前检查现有 owner，same-user 重放返回同一 confirmed 结果。
- Rationale: app-scoped SQLite handle 仍服务既有 IM repository，但不再承担 channel transaction owner；显式 `credentials.mode` 避免空字符串兼任 keep/replace，App ID 跨 identity 时强制 replace 并清空 app-scoped metadata。
- Evidence:
  - Tests: C1 缺模块按预期 collection red；C2 `18 passed`，覆盖固定 envelope 向量、六维 AAD 篡改、key mismatch、无明文持久化、并发旧 revision 仅一个成功、desired+manifest 原子、HTTP create/list/patch/唯一性/owner 隔离、online/offline cross-owner bind 与 same-owner 重放。
  - Entry: `/im/v1/agents/{agent_id}/channels` GET/POST 与 `/{channel_id}` PATCH 均从 authenticated owner 进入 `ChannelControlService`，错误返回稳定 code；`GET/list` 和日志断言不含 secret。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: account binding contract、multiuser isolation、完整 agent config integration 共 `23 passed`；目标文件 Ruff 通过。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R1 三提交会同时移除新增 schema/API/envelope 与 bind guard，不遗留半接线模块；SQLite 仅新增表，无既有数据重写。
- Commits: `31a22fa1c` (C1 red), `4728073f9` (C2 green), C3 为本提交。
- Next: R2 的动态 registry、ChannelManager 与可终止 Feishu worker 红测。

## R2 — Gateway 动态 runtime 与 Feishu worker

- Context: DONE
- Decision: `ChannelManager` 成为 managed external channel 的单一 lifecycle owner；runtime identity 只由 provider + agent 派生为 `feishu:<agent_id>`。App identity/generation 同时约束 metadata 与 status；owner/bot metadata 采用 set-if-null first-wins。Feishu SDK listener 从 Gateway 线程迁入每 Bot 一个 spawn process，parent 保留 REST、adapter、approval 与 kernel callback。
- Rationale: `ChannelRegistry` 只提供锁保护的 register/replace/remove，不吸收调和规则；worker 用 message FIFO、latest status mailbox、priority pipe、card-action duplex pipe 四类职责明确的 IPC，并以 incarnation + sequence 在 parent 单点归并。
- Evidence:
  - Tests: C1 两个新模块 collection red；C2 `40 passed` 覆盖稳定 runtime name、stop-before-start cutover、旧 generation 双拒绝、App replacement metadata 清空/owner 重绑、feishu-doc activation、双 listener 进程隔离、真实 stop/join、FIFO backpressure、status coalescing、priority error、drain/drop、card correlation/timeout、worker crash，以及既有 approval first-wins。
  - Entry: `FeishuClient.start()` 只在 parent 创建 REST client，SDK `WSClient` 与 event loop 在 `FeishuWorkerRuntime` child process；`FeishuAdapter.stop_invalidated()` 为 replace/disable/delete 立即丢弃旧 generation 输入。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 全部既有 Feishu adapter/client/history/mention/send 关联测试 `61 passed`；目标文件 Ruff 通过；测试退出后无残留 worker process。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R2 三提交恢复静态 registry + daemon thread；不会影响 R1 IM schema/API，但动态 manifest 不能再热应用。
- Commits: `054e4810f` (C1 red), `3577ad112` (C2 green), C3 为本提交。
- Next: R3 把 node key、manifest reconcile、status/metadata result 接入现有单槽 IM WebSocket FIFO 和 Gateway composition root。

## R3 — WS 在线 reconcile/status 闭环

- Context: DONE
- Decision: Gateway 启动时持久化生成权限为 `0600` 的 X25519 私钥，只在 `node.register` 上行公钥材料；IM 在 bind 后向对应 node 推送完整 manifest，Gateway 解封 secret 后由 `ChannelManager` 热调和，并用 `channel.reconcile.result`、`channel.status`、`channel.runtime_metadata` 三类上行帧回投结果。状态和 metadata 均以 generation/incarnation/sequence 做 CAS，相关 result 复用现有单槽 FIFO 释放机制。
- Rationale: 私钥不进入 IM，也不随进程重启变化；同一 WebSocket 完成 ack 后初始化控制面，可兼容 register-before-bind，bind confirm 也会主动触发初始化。composition root 只把解密后的凭据交给 runtime factory，static legacy 同名 adapter 会在 managed runtime 启动前被 stop/remove，关闭顺序则先收敛 managed channel 再关闭静态 registry。
- Evidence:
  - Tests: C1 因缺少 Gateway credential module 按预期 red；C2 目标与接线回归 `84 passed`，覆盖私钥权限/稳定性、公钥注册、跨端 envelope 解密、真实 IM app WebSocket 推送、reconcile result、connected status、metadata first-wins、App replacement 清 metadata、旧 generation 拒绝、下行 dispatch 与 FIFO 相关结果释放。
  - Entry: `GatewayHandler` 校验 frame sender 与当前 node socket 一致后写入 control store；`IMConnectionManager` dispatch `channel.reconcile` 并线程安全回传结果；`build_runtime()` 组装 credential store、manager、Feishu factory、status/metadata bridge 和 manifest handler。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: R1 安全控制面回归 `20 passed`，目标源/测试 Ruff 通过；所有 SQLite 短连接用 `closing()` 明确释放。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R3 三提交会保留 R1/R2 能力但断开在线调和协议；Gateway 不再注册 credential key，IM 不会向该 node 推送 manifest。
- Commits: `8902d9533` (C1 red), `8f15216ce` (C2 green), C3 为本提交。
- Next: R4 实现 Agent detail 的通道面板、Feishu provider registry 与 keep/replace 表单。

## R4 — Agent 通道页与 provider registry

- Context: DONE
- Decision: Agent detail 的“通道”页签直接挂载通用 `AgentChannelsPanel`；`CHANNEL_PROVIDERS` 只保留 provider 展示与向导元数据，列表/状态/请求错误均由通用组件处理。create/patch 成功先写 React Query cache 投影 connecting，仅在 desired 尚未 applied 或 observed 仍处于过渡态时每秒轮询；connected/failed 后停止轮询。
- Rationale: provider picker 即使已有通道仍可打开，以禁用态明确展示“已添加”；新增固定 replace，编辑默认 keep 且不渲染 secret 输入，App ID 变化立即切换 replace。页面只消费 `sync_state/observed/status_updated_at`，不渲染内部 revision。
- Evidence:
  - Tests: C1 缺 `agent-channels-panel` 与 channel API 按预期 red；C2 `42 passed`，覆盖通用空态且无 Web IM、飞书唯一性、开放平台精确链接、App ID/Secret required、keep/replace、App ID 自动 replace、在线保存即时 connecting、connected 时间/应用文案、具体 failed 与 API path/body。
  - Entry: 真实 `AgentDetailPage` 的 channels branch 从占位切换为 `AgentChannelsPanel`；API 使用认证 `authFetch` 访问 `/im/v1/agents/{id}/channels` POST/GET/PATCH。
  - Frontend State Matrix: default/provider picker、loading、empty、request error、disabled provider、submitting、connecting、connected、failed 均有实现；M1 desktop 状态由 R5 真浏览器验收。
  - Browser QA: 待 R5 真栈补齐。
  - E2E/Regression: `npm run build` 通过，Vite `443 modules transformed`；仅保留既有 chunk-size warning。
  - Visual/Interaction: 复用 Agent detail 卡片/token 与既有 modal primitives，secret 输入 `autocomplete=new-password` 且编辑初始 DOM 不存在。
  - Prototype Comparison: 代码结构已覆盖四个 M1 must-match 锚点；截图/DOM/network/console 证据待 R5。
- Rollback: 回滚 R4 三提交恢复通道占位页，不影响已部署的 IM/Gateway 控制面；浏览器将无法创建或编辑 managed channel。
- Commits: `a5878c0b3` (C1 red), `6d5ee4e62` (C2 green), C3 为本提交。
- Next: R5 启动隔离真 IM/Gateway，走真实 Agent detail → 通道路径并落四锚点 durable evidence。

## R5 — 真栈/真浏览器证据与总门禁

- Context: DONE
- Decision: 使用 worktree `e2e-up.sh` 的 ephemeral IM + foreground 真 Gateway，并从隔离 config 将现有飞书凭据直接注入 headed Chromium；不落临时浏览器脚本、不把 secret 输出到命令或证据。浏览器依次完成 empty → add/required → create → connecting → connected → already-added → edit keep → PATCH → reconnect；随后按 Gateway → IM 顺序清理。
- Rationale: managed exec 的短生命周期 shell 会回收脚本后台进程，因此真栈由持续 PTY 托管；这只改变进程托管方式，不替换产品入口。connected 来自真实 Feishu worker、IM status 落库和页面 GET polling，不使用 route mock、状态注入或进程内 fake。
- Evidence:
  - Tests: 总门禁见 `evidence/gates.md`：后端非 e2e `3365 passed, 1 skipped, 20 deselected`；前端 `65 files / 609 tests passed`；目标前端 `42 passed`；测试文件 contract `2 passed`；Ruff / pip check / build 全绿。
  - Entry: 浏览器真实 `POST /im/v1/agents/default-agent/channels → 201`、`PATCH .../<channel_id> → 200`；IM SQLite 最终 `channel_revision=2, manifest=2, applied=2, connected, status_sequence=3`。
  - Frontend State Matrix: 1440px 验收 empty、default/provider、required error、disabled provider、submitting/connecting、connected、edit keep/replace；loading/request error/failed 由 42 项可重复交互回归保护；M2/M3 状态保持其 milestone 边界。
  - Browser QA: headed Chromium 真实 Agent detail → 通道；console `0 errors / 0 warnings`；requests 无失败，POST/PATCH/GET 均 2xx；App Secret 在编辑初始 DOM 不存在，证据 secret scan clean。
  - E2E/Regression: 真 Feishu create 与 keep edit 均从 connecting 收敛 connected；第一次 worker PID `84409`，编辑 cutover 后为 `91135` 且同一时刻只有一个 worker child。清理后端口/Gateway/worker/PID/control files 全为 `0`。
  - Visual/Interaction: `evidence/output/playwright/` 六张 1440 × 1000 截图；SHA-256 与逐步说明见 `evidence/README.md`。
  - Prototype Comparison: 四个 must-match 锚点逐项 match，见下表与 `evidence/README.md`；provider glyph/色彩使用现有 IM token，为 design 授权的 may-adapt。
- Rollback: 回滚 R5 Verify/门禁/文档提交只移除验收证据，不改变 R1–R4 产品实现。
- Commits: `90f3c302e` (C1 Verify), `671255df8` (C2 gates), C3 为本提交。
- Next: M1 已完成并可合入 `unit/feat-464-im-channel-settings`，由 orchestrator 继续独立 verifier/reviewer。

## Prototype Comparison

| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `#channels-empty` | 通用空态 + 添加入口；无 Web IM | `evidence/output/playwright/channels-empty.png` + DOM 报告 | 1440 × 1000 / empty | match | N/A |
| `#add-feishu` | provider 禁选、required、keep/replace | `add-feishu-required.png`、`add-feishu-already-added.png`、`edit-feishu-keep-replace.png` | 1440 × 1000 / add + edit modal | match | provider glyph/色彩沿用现有 IM token，属于 may-adapt |
| `#channel-connecting` | 在线保存后的 connecting | `evidence/output/playwright/channel-connecting.png` + POST 201/status 时间 | 1440 × 1000 / live connecting | match | N/A |
| `#channel-connected` | 当前配置已应用 + 最近状态时间；无 revision | `evidence/output/playwright/channel-connected.png` + SQLite connected/seq3 | 1440 × 1000 / live connected | match | N/A |

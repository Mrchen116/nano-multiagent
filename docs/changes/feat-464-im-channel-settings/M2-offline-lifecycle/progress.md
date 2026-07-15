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

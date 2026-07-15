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

- Context: DOING
- Decision: 待实现。
- Rationale: 待实现。
- Evidence:
  - Tests: 待补 C1 Red。
  - Entry: 待实现。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 待实现。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 待提交。
- Commits: 待提交。
- Next: C1 先覆盖 removal view、zero-item intent/result、failure/retry、retention/head terminal 与 no-cascade。

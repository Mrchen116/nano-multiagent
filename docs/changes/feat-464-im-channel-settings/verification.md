# Verification Report: feat-464-im-channel-settings

## Summary

Mode: full

Delta range: N/A

Focus issues: N/A

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 22/24 个退出标准被完整证实（文档勾选为 24/24）；19/20 个 spec scenario 有完整实现 |
| Correctness | 19/20 个 scenario 匹配；1 个缺实现；另有 1 个安全场景的永久回归证据不完整 |
| Coherence | 6/9 个关键决策完整遵守；决策 1、5、6 存在偏离 |

结论：**FAIL**。1 个 CRITICAL、3 个 WARNING；修复后再进入 PR。

## Completeness

- Tasks：M1-E1..E8、M2-E1..E8、M3-E1..E8 均被标记 `[x]`，但逐代码和测试核对后只有 22/24 被完整证实。
  - M2-E4 未完成：凭据、Bot、长连接配置类失败仍折叠为 `runtime_start_failed` / `worker_crashed`，没有具体原因或下一步。
  - M1-E6 仅部分证实：跨 owner 改绑实现有前置拒绝，但所称的 channel / manifest / credential / cache 不变未被永久测试直接断言。
- Spec：6 个 Requirement 均有主体实现；“连接状态与可操作诊断”中的“凭据或连接无效”scenario 缺少 provider 级可操作失败分类，因此只有 19/20 scenario 完整落地。
- Design：期望/实际状态、完整 manifest、removal receipt/outbox、Feishu 多进程隔离、accepted scope sets、状态因果、owner guard 和依赖方向均有实现；`credential_reentry_required`、真实 SDK worker 的 backpressure 关闭/有界重启、Bot/长连接/事件订阅检查未落地。
- M3-E8 拆分口径：真实应用证据足以证明 complete probe、连接、stop/restart、secret 与单 listener；production-store → 真 IM HTTP → 真前端证据结合永久 provider/status/frontend 测试，足以证明 limited/unknown 的投影链路。该拆分不证明凭据无效、Bot 未启用或长连接配置错误的可操作失败分支，不能关闭 CRITICAL-1。
- Prototype / Reference：design 中 11 个 must-match 行全部投影到 milestone，并存在仓库内 durable evidence；其中 `#channel-reconnecting/#channel-failed` 的“actionable credential/Bot/worker failure”只展示了通用 runtime 错误，故该行仍为 critical。

## Correctness

| Requirement / Scenario | 实现位置 | 永久测试覆盖 | 状态 |
|---|---|---|---|
| 通用页：空态、统一入口、无 Web IM | `src/IM/frontend/src/features/settings/agents/agent-channels-panel.tsx:577`、`:593`、`:613` | `agent-channels-panel.test.tsx:80` | covered |
| 通用页：选择飞书 provider | `agent-channels-panel.tsx:22`、`:371` | `agent-channels-panel.test.tsx:80` | covered |
| 通用页：已有飞书不可重复添加 | `agent-channels-panel.tsx:373`、`:577` | `agent-channels-panel.test.tsx:102`；服务端唯一性见 `test_agent_channels_api.py:46` | covered |
| 通用页：列表失败显示 retry，不显示空态 | `agent-channels-panel.tsx:581` | `agent-channels-diagnostics.test.tsx:131` | covered |
| 向导：简短准备说明与精确开放平台链接 | `agent-channels-panel.tsx:20`、`:394` | `agent-channels-panel.test.tsx:80` | covered |
| 向导：在线保存立即连接且无需重启 | `agent-channels-panel.tsx:492`、`:513`；`src/IM/ws/gateway_handler.py:284`；`src/personal_assistant/gateway/channel_manager.py:245` | `test_channel_reconcile.py:93`、`agent-channels-panel.test.tsx:125` | covered |
| 向导：App ID / Secret 必填 | `agent-channels-panel.tsx:341`、`:353` | `agent-channels-panel.test.tsx:80` | covered |
| 向导：secret 不回显，显式 keep/replace | `agent-channels-panel.tsx:335`、`:406`、`:492`；`src/IM/infra/channel_control_store.py:931` | `agent-channels-panel.test.tsx:102`、`test_agent_channels_api.py:46`、`test_agent_channels.py:133` | covered |
| 状态：权限完整且连接正常 | `agent-channels-panel.tsx:163`、`:199`；`src/personal_assistant/channels/feishu/client.py:271` | `test_channel_reconcile.py:93`；真实 complete evidence | covered |
| 状态：权限不足但基础能力可用 | `agent-channels-panel.tsx:67`、`:230`；`src/personal_assistant/channels/feishu/diagnostics.py:201` | `test_feishu_capability_diagnostics.py:98`、`agent-channels-diagnostics.test.tsx:95` | covered；连接 pill 与诊断卡分层符合 design 决策 6 |
| 状态：缺普通群消息权限并说明背景上下文影响 | `agent-channels-panel.tsx:103`、`:128`；`diagnostics.py:117` | `test_feishu_capability_diagnostics.py:59`、`agent-channels-diagnostics.test.tsx:95` | covered |
| 状态：权限检查失败为 unknown，不伪造 missing | `src/personal_assistant/channels/feishu/client.py:244`；`diagnostics.py:201`；`agent-channels-panel.tsx:123` | `test_feishu_client_scopes.py:78`、`:98`；`test_feishu_capability_diagnostics.py:109`；`agent-channels-diagnostics.test.tsx:109` | covered |
| 状态：App 凭据无效、Bot 未启用或连接失败给出可操作原因 | `src/personal_assistant/main.py:2270`、`:3209`；`channel_manager.py:565`；`worker.py:199` | 只有通用 runtime/worker failure：`agent-channels-panel.test.tsx:150`、`test_feishu_worker_runtime.py:242` | **缺实现**：Bot probe 失败被吞掉，错误文案仅为 runtime/worker 通用失败 |
| 状态：暂时中断、自动恢复与手动重连 | `src/personal_assistant/channels/feishu/client.py:697`；`agent-channels-panel.tsx:536` | `agent-channels-panel.test.tsx:241`、`test_feishu_worker_runtime.py:253` | covered |
| 离线：新增/修改/启停/删除保存为等待应用 | `src/IM/infra/channel_control_store.py:832`、`:931`、`:1056`；`agent-channels-panel.tsx:164`、`:468` | `test_agent_channels_api.py:149`、`agent-channels-panel.test.tsx:179`、`:215` | covered |
| 离线：节点重连后完整 manifest 自动收敛 | `src/IM/ws/gateway_handler.py:284`；`src/personal_assistant/ws/im_connection.py:519`；`channel_manager.py:245` | `test_channel_reconcile.py:269`、`test_channel_bootstrap.py:29` | covered |
| 生命周期：停用后不再收发且保留配置 | `channel_manager.py:269`、`:584`；`agent-channels-panel.tsx:521` | `test_channel_manifest_store.py:197`、`agent-channels-panel.test.tsx:179` | covered |
| 生命周期：重新启用且无需重填 secret | `agent-channels-panel.tsx:521`；`channel_control_store.py:931` | `test_agent_channels_api.py:149`、`agent-channels-panel.test.tsx:179` | covered |
| 生命周期：删除等待实际停止，失败可重试，保留历史 | `channel_control_store.py:1056`、`:1146`；`agent-channels-panel.tsx:245` | `test_agent_channels.py:197`、`:256`、`agent-channels-panel.test.tsx:215`、`:241` | covered |
| Owner：跨 owner 改绑拒绝，同 owner 幂等 | `src/IM/application/bind_service.py:59`、`:77`；`src/IM/api/routes/account.py:178` | `test_account_binding_api.py:109` | 实现 covered；测试只断言 node/profile/config API，未覆盖 spec 所列 channel/manifest/credential/cache 不变（WARNING-3） |

### 测试与门禁结果

- 聚焦后端：79 passed（channel control、credential、binding、reconcile/bootstrap、manager/store、worker、diagnostics）。
- 完整后端：`pytest -q -m 'not e2e'` → 3425 passed、1 skipped、20 deselected。
- 架构与测试规范：5 passed（`test_multi_product_architecture.py`、`test_test_naming_and_size_contract.py`）。
- 前端聚焦：54 passed；`npm run build` → 443 modules transformed，成功。
- 完整前端：66 files / 617 tests passed；所有 feat-464 相关测试文件均低于 400 行。
- Ruff（本 unit 新增/修改 Python 文件）与 `git diff --check`：通过。

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 1. X25519/HKDF/AES-GCM 节点信封，IM/缓存无明文 | 部分 | 加密/AAD/0600/fixed vector 已实现：`src/IM/infra/channel_credentials.py:65`、`src/personal_assistant/channels/channel_credentials.py:55`；但 key loss / key_id change 没有进入 `credential_reentry_required`：`main.py:3275`、`channel_manifest_store.py:374`（WARNING-1） |
| 2. desired 与 actual 分离、revision/CAS、短 SQLite transaction | 是 | `channel_control_store.py:177`、`:475`、`:653`、`:1322` |
| 3. IM 权威完整 manifest + removals + Gateway 密文 cache/outbox | 是 | `channel_control_store.py:1379`；`channel_manifest_store.py:108`、`:135`、`:154`；`channel_manager.py:245` |
| 4. ChannelManager 唯一生命周期 owner，稳定 `feishu:<agent_id>` | 是 | `channel_manager.py:178`、`:505`、`:542`；web_relay guard `:304` |
| 5. 每 Bot 一个可终止 worker、三 lane、incarnation/sequence、backpressure fail+restart | 部分 | process/queue/pipe/stop 已实现：`worker.py:219`、`:293`、`:309`；满载只设置 child event，真实 SDK worker不消费该 event且 parent 无重启：`worker.py:141`、`client.py:657`（WARNING-2） |
| 6. connection 与 diagnostics 分离；strict tenant grant；accepted sets；Bot/连接/订阅检查 | 部分 | scope catalog/unknown/汇总已实现：`diagnostics.py:85`、`:173`、`:201`、`:231`；Bot probe 结果被吞掉且 catalog 只有 scope 项：`main.py:2270`、`:3219`（CRITICAL-1） |
| 7. 通用 REST/resource 与前端 provider registry | 是 | `src/IM/api/routes/agent_channels.py:115`、`:205`、`:233`；`agent-channels-panel.tsx:22` |
| 8. 一次性 bootstrap、初始化协调、无跨 owner transfer、legacy export | 是 | `channel_control_store.py:286`、`:337`；`src/personal_assistant/config/local_store.py:246`；`bind_service.py:77` |
| 9. 三个纵向 milestone 交付 | 是 | M1/M2/M3 tasks/progress/evidence 均存在，且代码/测试按三段能力闭环 |

### Architecture coherence

- `IM` 未 import `agent`；`personal_assistant` 产品边界仍仅通过 `agent.sdk` 使用内核，架构 contract 通过。
- IM 与 Gateway 之间的 credential、manifest、status 都经 HTTP/WS 协议传输，没有跨机文件访问假设。
- `ChannelManager` 扩展既有 registry/adapter seam，未建立与静态 `web_relay` 并行的第二个路由真相源。
- `ChannelControlStore` 使用独立短连接和 `BEGIN IMMEDIATE`，没有把长事务挂在全局 IM connection 上。

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| `#channels-empty` | M1-E1/E2 | `agent-channels-panel.tsx:593`、`:613` | `M1-online-secure-channel/evidence/output/playwright/channels-empty.png` + README hash | covered |
| `#add-feishu` | M1-E2/E3/E4 | `agent-channels-panel.tsx:327`、`:371`、`:406` | `add-feishu-already-added.png`、`add-feishu-required.png`、`edit-feishu-keep-replace.png` | covered |
| `#channel-connecting` | M1-E4 | `agent-channels-panel.tsx:164`、`:189` | `channel-connecting.png` + POST 201/status evidence | covered |
| `#channel-connected` | M1-E5 | `agent-channels-panel.tsx:177`、`:199`、`:236` | `channel-connected.png` + DOM/network report | covered |
| `#channel-pending` | M2-E1/E2 | `agent-channels-panel.tsx:164`、`:468`、`:604` | `channel-pending-offline-create.png` | covered |
| `#channel-actions/#channel-disabling/#channel-disabled` | M2-E1/E3/E5 | `agent-channels-panel.tsx:219`、`:521`、`:661` | disable confirm/disabling/disabled/re-enable screenshots + browser QA | covered |
| `#channel-deleting` | M2-E1/E5/E8 | `agent-channels-panel.tsx:245`、`:554`、`:568` | offline/reload/failed-retry/applied-empty screenshots + receipt DB report | covered |
| `#channel-reconnecting/#channel-failed` | M2-E4、M3-E2 | `agent-channels-panel.tsx:166`、`:195`；runtime generic failure `channel_manager.py:565` | reconnecting/failed/unknown screenshots | **critical**：稳定状态与分层有证据，但 credential/Bot/worker failure 文案不具可操作性 |
| `#channel-limited` | M3-E1/E2 | `agent-channels-panel.tsx:67` | `channel-limited-production-store.png`、reconnecting/failed unknown screenshots | covered；批准拆分与永久 provider/status tests 合并后证据充分 |
| `#channels-error` | M3-E3 | `agent-channels-panel.tsx:581` | `channels-list-error-real-im-outage.png` + retry report | covered |
| `#channels-mobile` | M3-E4 | `agent-channels-panel.tsx:298`、`:329` | 375x812 card/add/edit/delete bottom-sheet screenshots | covered |

## Issues

### CRITICAL（提 PR 前必须修）

1. **凭据、Bot 与平台配置失败没有可操作分类，spec scenario 与 M2-E4 未实现。** `_infer_feishu_bot_open_id_from_app_credentials()` 对 import、API、空 identity 全部返回 `None`（`src/personal_assistant/main.py:2270-2304`），managed factory 随后仍用 `bot_open_id=None` 启动 adapter（`src/personal_assistant/main.py:3219-3254`）；scope diagnostics 也只评估 scope（`src/personal_assistant/channels/feishu/client.py:264-269`）。启动异常最终只变成 `runtime_start_failed: Channel runtime could not start`（`src/personal_assistant/gateway/channel_manager.py:565-579`）或 `worker_crashed: Feishu listener process exited unexpectedly`（`src/personal_assistant/channels/feishu/worker.py:199-213`）。这不能满足 `spec.md:131-134` 的具体原因/下一步，也与 `design.md:273` 的 Bot/长连接/事件订阅检查冲突。**修复：**把身份/凭据 probe 改成结构化结果，区分 credential invalid、Bot disabled、长连接/订阅未配置、transient unknown；confirmed 配置错误通过当前 generation status sink 上报稳定错误码、用户可执行文案，不能继续宣称 connected；为 provider → manager → IM HTTP → frontend 增加每类永久测试，至少直接覆盖 Bot disabled 和 invalid credential。

### WARNING（应该修）

1. **key loss / key_id change 没有进入 `credential_reentry_required`，还可能错误推进 applied head。** live manifest 解封失败只把 channel 放进 `failed_ids`，随后把缺项 manifest 交给 manager（`src/personal_assistant/main.py:3275-3349`）；manager 会把缺项当作 desired removal、提交该不完整 cache，并返回 `outcome=applied`（`src/personal_assistant/gateway/channel_manager.py:269-345`），外层仅附加 failure 而不改变 outcome（`src/personal_assistant/main.py:3354-3368`）。IM 对 applied 无条件推进 head（`src/IM/infra/channel_control_store.py:503-516`）。离线启动时 cache key mismatch 又会在 IM 连接前从 `start_cached()` 抛出（`src/personal_assistant/gateway/channel_manifest_store.py:374-386`、`src/personal_assistant/main.py:1885-1889`）。这偏离 `design.md:133`、`:247`。**修复：**解封失败不得把 desired channel 当删除、不得提交不完整 manifest 或推进 head；上报 `credential_reentry_required` 并保留安全密文/现有 desired，允许 Gateway 继续连 IM；补 live reconcile 与 offline cache key-loss 的产品状态测试。

2. **真实 SDK worker 在 backpressure 后不会关闭，也没有 design 要求的有界退避重启。** `publish_event()` 满载时只上报失败并设置 `context.stop_event`（`src/personal_assistant/channels/feishu/worker.py:141-156`），但真实 worker 随后阻塞在 `client.start()`，没有读取 stop event（`src/personal_assistant/channels/feishu/client.py:657-704`）；parent status loop 只转发状态，且 stop_event 已设置时不会把退出识别为 crash（`src/personal_assistant/channels/feishu/worker.py:370-401`）。现有压力测试使用收到 `False` 就主动 return 的 cooperative fake（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:41-53`），没有证明真实 worker 关闭或重启。偏离 `design.md:224-225`。**修复：**parent 收到 `event_backpressure` 后必须 terminate/join 当前 child，并由 lifecycle owner 进行有上限、有退避的 restart（或保持明确 failed 直到人工重连）；增加非 cooperative worker 测试，断言旧 PID 被回收、无继续收发、重启次数受限且状态因果不倒退。

3. **跨 owner 改绑的永久测试没有覆盖 spec 与 M1-E6 声称的全部数据边界。** 当前测试只创建 node/profile，拒绝后只断言 node owner、profile owner 和 config API（`tests/im_service/integration/test_account_binding_api.py:109-168`）；没有预置/快照 `agent_channels`、`channel_manifest_heads`、`node_credential_keys`、removal receipt，也没有断言拒绝路径不会触发 channel-control initialization/cache side effect。实现的 owner guard 位于任何 mutation 前（`src/IM/application/bind_service.py:74-90`），所以当前代码看起来安全，但安全回归证据不足。**修复：**扩展 online/offline 参数测试，先为 owner A 建立 channel/key/head/removal，再由 B confirm；断言相关行与 envelope 字节不变、B 的 channel API 全部不可读/不可控、拒绝路径不调用 initialization/push；保留 same-owner 幂等断言。

### SUGGESTION（可以修）

- 无。

1 critical issue(s) found. Fix before PR.

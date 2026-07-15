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

# Round 2

## Summary

Mode: full

Delta range: `f47f169bbb85893f31617bd8529e25e15e392d1c..46096e3ec5a4875974345c6a5d82d5ebe8fba6e2`

Focus issues: Round 1 全部问题与 M4 的 Gateway WS auth/cross-owner、manifest fail-closed/key recovery、bind 原子性、Feishu preflight/lifecycle/backpressure、secret migration/file mode、metadata/activation、provider registry、离线收敛/删除历史/失败重试。

requires_full_verification: true

Validated head: `46096e3ec5a4875974345c6a5d82d5ebe8fba6e2`

| 维度 | 结果 |
|---|---|
| Completeness | 28/31 个退出标准被完整证实（文档勾选为 31/31）；M4-E3、M4-E4、聚合门禁 M4-E7 未闭合 |
| Correctness | 20/20 个用户 spec scenario 有主体实现；2 个 M4 安全/调和失败路径与声明不符 |
| Coherence | 8/9 个编号关键决策完整遵守；决策 3 的 complete-manifest fail-closed 有偏离，v11 WS 身份边界也只覆盖 register/channel 帧 |

结论：**FAIL**。2 个 CRITICAL；修复后必须再做 full verification，不可进入 PR。

## Round 1 问题复核

| Round 1 问题 | Round 2 结果 | 证据 |
|---|---|---|
| CRITICAL-1：凭据/Bot/长连接失败被通用化 | closed | provider preflight 与稳定码见 `src/personal_assistant/channels/feishu/preflight.py:39-113`；真实 invalid-secret evidence 与 `test_feishu_preflight_and_metadata.py:51-122` |
| WARNING-1：key loss / key mismatch 被当删除或阻止 IM 连接 | tested path closed，但 complete-manifest fail-closed 仍有新 CRITICAL-2 | key quarantine/re-entry 见 `channel_manifest_store.py:108-141`、`channel_manager.py:246-338`；合法 mapping 的 wrong-key 回归见 `test_channel_credential_recovery.py:142-210` |
| WARNING-2：backpressure 不回收/无有界重启 | closed | `channel_manager.py:638-821`；非 cooperative child、三次重试和人工恢复见 `test_channel_lifecycle_failures.py:179-262` |
| WARNING-3：跨 owner 永久测试未覆盖密文边界 | closed | `tests/im_service/integration/test_bind_atomicity.py:32-139` 快照 channel/head/key/removal 全表并验证一胜一败、同 owner 幂等 |
| Round 1 acceptance：connected → disable 卡住 | closed | `channel_manager.py:340-486`；M4 real-stack evidence 记录 2.357s 到 disabled、旧 PID 退出、2.822s re-enable |

## Completeness

- Tasks：M1 8/8、M2 8/8、M3 8/8 均由实现、永久测试和 durable evidence 证实。M4 为 4/7：E1、E2、E5、E6 covered；E3 因非归属账号的已认证 socket 可提交已注册节点的非 channel 上行帧而未完成；E4 因非法 manifest item 会被静默省略并执行不完整 snapshot 而未完成；E7 的“十项缺口均有永久 regression”因此不成立。
- Spec：6 个 Requirement、20 个 Scenario 的正常用户路径均有主体实现；owner bind 场景的跨 owner 事务隔离已补齐。两个 CRITICAL 属于 M4 新增的传输身份与失败恢复保证，并非可以因原始 20 个 scenario 正常路径通过而忽略。
- Design/delta-spec：IM/Gateway 两份 delta 覆盖 desired/observed、完整 manifest、离线 cache、生命周期、诊断和 owner 隔离；编号决策 3 的“完整 manifest”实现对非法数组成员不 fail closed。canonical 长青 spec 尚未归并是 unit 收尾步骤，不作为本轮实现缺失。
- Prototype / Reference：11 个 must-match 行均有 milestone 投影、实现与 durable screenshot/JSON 证据；M4 新增 connected/disabled/re-enabled/provider-failure/offline/delete/cache-failure/mobile 证据齐全。

## Correctness

| Requirement / Scenario | 实现位置 | 永久测试/证据 | 状态 |
|---|---|---|---|
| 通用页：空态、统一入口、不展示 Web IM | `src/IM/frontend/src/features/settings/agents/agent-channels-panel.tsx:690-721` | `agent-channels-panel.test.tsx` empty/wizard | covered |
| 通用页：选择 provider | `agent-channels-panel.tsx:426-447`；`channel-provider-registry.ts:61-131` | `agent-channels-provider-registry.test.tsx:110-146` | covered |
| 通用页：同 provider 已存在时禁选 | `agent-channels-panel.tsx:675-676`、`:428-444` | panel + provider registry tests | covered |
| 通用页：列表失败显示 retry，不伪造空态 | `agent-channels-panel.tsx:679-687` | diagnostics/list-error frontend test + screenshot | covered |
| 向导：简短说明与精确开放平台链接 | `channel-provider-registry.ts:58-79`；`agent-channels-panel.tsx:448-457` | wizard test | covered |
| 向导：在线保存后立即连接，无需重启 | `agent-channels-panel.tsx:584-617`；`src/IM/ws/gateway_handler.py:305-365`；`channel_manager.py:340-486` | `tests/integration/test_channel_reconcile.py` + real connected evidence | covered |
| 向导：App ID / Secret 必填 | `channel-provider-registry.ts:158-173`；`agent-channels-panel.tsx:400-405` | wizard/provider tests | covered |
| 向导：secret 不回显，显式 keep/replace | `channel-provider-registry.ts:144-188`；`agent-channels-panel.tsx:475-523` | panel API/store tests | covered |
| 状态：权限完整且连接正常 | `src/personal_assistant/channels/feishu/client.py:264-279`；`agent-channels-panel.tsx:151-249` | capability tests + real connected evidence | covered |
| 状态：权限不足但基础能力可用 | `diagnostics.py` capability summary；`agent-channels-panel.tsx:62-136` | diagnostics tests + limited evidence | covered |
| 状态：缺普通群消息权限并说明上下文影响 | `channel-provider-registry.ts:110-125` | capability/frontend diagnostics tests | covered |
| 状态：权限检查失败为 unknown | `client.py:244-269`；`agent-channels-panel.tsx:62-136` | scope/diagnostics tests | covered |
| 状态：凭据、Bot、长连接失败有具体下一步 | `preflight.py:39-113`；`channel_manager.py:686-778` | `test_feishu_preflight_and_metadata.py:51-122` + real invalid-secret evidence | covered |
| 状态：暂断、自动恢复、手动重连 | `channel_manager.py:488-502`、`:638-821`；`agent-channels-panel.tsx:634-650` | lifecycle failures + frontend reconnect tests | covered |
| 离线：新增/修改/启停/删除保存为 pending | `src/IM/infra/channel_control_store.py` desired mutations；`agent-channels-panel.tsx:702-706` | offline API/frontend tests + M4 screenshots | covered |
| 离线：重连后完整 manifest 自动收敛 | `src/IM/ws/gateway_handler.py:326-365`；`src/personal_assistant/ws/im_connection.py:519-583` | reconcile/bootstrap tests + offline-converged evidence | covered |
| 生命周期：停用后停止收发并保留凭据 | `channel_manager.py:368-409`；`agent-channels-panel.tsx:619-631` | `test_channel_lifecycle_failures.py:300-349` + real disabled evidence | covered |
| 生命周期：重新启用且不重填 secret | `channel_manager.py:391-417`；frontend keep mutation | lifecycle/API test + real re-enabled evidence | covered |
| 生命周期：删除等待实际停止、失败可重试、历史保留 | `channel_manager.py:368-485`；`agent-channels-panel.tsx:255-293`、`:652-673` | reconcile/removal tests + current-head cache-failure/history evidence | covered |
| Owner：跨 owner bind 拒绝、数据边界不变、同 owner 幂等 | `src/IM/infra/binding_store.py:29-119` | `test_bind_atomicity.py:45-139` | covered |

### M4 失败路径核对

| M4 保证 | 当前实现 | 本地业务一致性复验 | 状态 |
|---|---|---|---|
| Gateway WS bearer identity 应约束非归属账号 | bearer 只在入口解析；`node.register` 校验 durable owner；channel 三类上行检查 websocket | 账号 B 开 socket但不 register，直接提交账号 A 节点的 `node.heartbeat`，收到 ACK，DB 状态被账号 B 的输入改写 | **critical** |
| complete manifest 任一 item 失败不得做部分 reconcile | mapping item 的 key/envelope/open failure fail closed；非 mapping item 被 `continue` | 先运行 `ch-a`，再送 `channels=[None]`：返回 `outcome=applied`，旧 adapter 收到 stop，registry 为空 | **critical** |
| key mismatch quarantine、Gateway 继续连接 IM | foreign-key cache 原字节 quarantine，status outbox 可重新建立 | credential recovery tests | covered |
| bind guard/write 单事务、一胜一败 | 独立连接 `BEGIN IMMEDIATE` | two-thread integration test | covered |
| preflight provider reason | tenant-token、bot、WS endpoint 分层 | unit + live invalid-secret | covered |
| partial start/backpressure/stop 不阻塞 event loop | candidate cleanup、to_thread、PID reap、有界 restart | lifecycle failure tests | covered |
| sensitive migration/export 首次可见即 0600、无 backup | secure temp + fsync + replace；export 复用 | sensitive config/legacy migration tests | covered |
| metadata generation 持久化/重放，activation retry | cache CAS/update + reconnect replay；成功后 memoize | preflight/metadata tests | covered |
| provider registry 真分派 | descriptor 驱动 fields/serialization/card/diagnostics/removal | injected Webhook provider test | covered |
| offline/delete/cache failure 收敛 | desired manifest + removal receipt/outbox + retry | M4 browser/store evidence | covered |

### 测试与门禁结果

- M4 聚焦：25 passed（auth、bind、credential recovery、sensitive writer、preflight/metadata、lifecycle failures、reconcile）。
- 完整后端：`pytest -m 'not e2e' -q` → 3447 passed、1 skipped、20 deselected。
- 完整前端：67 files / 620 tests passed；`npm run build` → 444 modules transformed。验证 worktree 复用主仓 `node_modules`，测试与 build 均成功，生成物随后清理。
- Ruff：`ruff check src tests` → PASS。
- `git diff --check f47f169...46096e3` → PASS。
- 新增/修改的 `test_*.py` 无超过 400 行；全量测试命名/大小 contract 也包含在完整后端门禁中。
- 两个本地业务一致性复验均在 validated head 上独立执行并稳定复现；它们不是对既有失败测试的推断，也未访问任何外部目标。

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 1. 节点公钥信封，IM/缓存不持久化明文 | 是 | `src/IM/infra/channel_credentials.py`；`src/personal_assistant/channels/channel_credentials.py:95-131`；sensitive writer `local_store.py:679-719` |
| 2. desired/actual 分表、内部 revision/CAS、独立短事务 | 是 | `src/IM/infra/channel_control_store.py` 的 mutation/status/result transaction |
| 3. IM 权威完整 manifest + Gateway 离线 cache/outbox | **部分** | 正常路径见 `channel_manager.py:340-485`；非法 channel item 在 `channel_manifest_apply.py:59-61` 被静默跳过后仍于 `:147-155` reconcile（CRITICAL-2） |
| 4. ChannelManager 为唯一动态生命周期 owner | 是 | `channel_manager.py:197-928`；异步入口统一 `to_thread` |
| 5. 每 Bot 可终止进程、三 lane、因果状态、backpressure 重启 | 是 | `worker.py:219-491`；`channel_manager.py:638-821` |
| 6. connection/diagnostics 分层与 provider-owned probe | 是 | `preflight.py:39-113`；`client.py:244-279`；`diagnostics.py` |
| 7. 通用 REST/resource + provider registry | 是 | `src/IM/api/routes/agent_channels.py`；`channel-provider-registry.ts` |
| 8. 一次性 bootstrap、无跨 owner transfer、legacy export | 是 | `channel_control_store.py:286-455`；`binding_store.py:29-119`；`scripts/channel-control-export-legacy.py:37-85` |
| 9. 纵向 milestone 交付 | 是 | M1-M4 tasks/progress/evidence 与永久测试均存在 |

### Architecture coherence

- `IM` 仍不 import `agent`；`personal_assistant` 对内核仅经 `agent.sdk`，完整 contract suite 通过。
- credential/manifest/status 均经 HTTP/WS 协议，不假设 IM 可读 Gateway 文件；本地 key/cache/config 仍在 Gateway owner 边界。
- `ChannelControlStore` 与新 `BindingStore` 均使用独立 SQLite connection；bind 并发 guard/write 已原子化。
- **偏离：**`GatewayConnection.owner_id` 只保护 register 结果和 channel 帧的 websocket identity；通用 frame dispatcher 没有把已认证 owner/当前 websocket 作为所有节点上行操作的统一前置条件，形成第二套未授权路径（CRITICAL-1）。

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| `#channels-empty` | M1-E1/E2 | `agent-channels-panel.tsx:690-721` | M1 empty screenshot | covered |
| `#add-feishu` | M1-E2/E3/E4 | provider descriptor + `agent-channels-panel.tsx:426-534` | M1 add/required/keep-replace screenshots | covered |
| `#channel-connecting` | M1-E4 | `agent-channels-panel.tsx:151-249` | M1 connecting + M4 real connection evidence | covered |
| `#channel-connected` | M1-E5 | `agent-channels-panel.tsx:151-249` | M4 `r6-real-connected.png` | covered |
| `#channel-pending` | M2-E1/E2 | `agent-channels-panel.tsx:151-249`、`:702-706` | M4 offline create/update evidence | covered |
| `#channel-actions/#channel-disabling/#channel-disabled` | M2-E1/E3/E5 | card actions + toggle mutation | M4 disabling/disabled/re-enabled evidence | covered |
| `#channel-deleting` | M2-E1/E5/E8 | `agent-channels-panel.tsx:255-293` | M4 cache-failure/reload/retry/history evidence | covered |
| `#channel-reconnecting/#channel-failed` | M2-E4/M3-E2/M4-E2 | provider error + restart status | M4 invalid-credential/recovered evidence | covered |
| `#channel-limited` | M3-E1/E2 | provider diagnostics descriptor + panel | M3 limited/unknown evidence | covered |
| `#channels-error` | M3-E3 | `agent-channels-panel.tsx:679-687` | M3 outage/retry evidence | covered |
| `#channels-mobile` | M3-E4/M4-E6 | mobile bottom sheet + generic provider picker | M4 375x812/picker evidence | covered |

## Issues

### CRITICAL（提 PR 前必须修）

1. **Gateway bearer identity 没有约束所有节点上行帧；非归属账号可更新已注册节点状态。** `/im/ws/gateway` 虽解析 token 并传入 `authenticated_owner_id`（`src/IM/app.py:404-436`），但 `GatewayHandler.handle_message()` 只把它传给 `node.register`（`src/IM/ws/gateway_handler.py:199-213`）。`node.heartbeat`、`node.report`、agent/config/capability/result 等分支随后都不校验当前 websocket 或 owner（`:214-260`）；例如 `_handle_heartbeat()` 只按 payload `node_id` 查找任意现存 connection 并持久化（`:1101-1137`）。本轮在本地 TestClient 中让账号 A 注册并绑定 `node-a`，随后账号 B 以合法 bearer 新开 socket但不 register，直接提交该节点的 heartbeat：账号 B 收到 ACK，`nodes.status/last_error` 被其输入改写。现有 auth test 只覆盖非归属账号再次执行 `node.register`（`tests/im_service/integration/test_gateway_auth_boundary.py:59-122`），未覆盖注册后的其他业务帧归属。**修复：**把注册连接的 `(websocket, authenticated_owner_id, node_id)` 校验提升为所有 node-scoped 上行帧的统一 dispatcher guard；未在该 websocket 完成 register、connection owner 与 token owner 不同、payload node_id 与注册 node 不同均关闭/拒绝，不能只在 channel 三个 handler 中局部调用 `_is_registered_sender`。补至少 heartbeat、report、agent result、channel result 的跨 owner/未注册 socket 回归，并断言 DB、waiter 与广播均零副作用。

2. **fail-closed manifest applier 会静默跳过非法 item，执行不完整 snapshot 并把安全 runtime 当成删除。** `apply_channel_manifest_payload()` 对 `channels` 中非 mapping item 直接 `continue`（`src/personal_assistant/gateway/channel_manifest_apply.py:54-61`），对非 list/missing `channels` 也按空列表处理；之后仍构造 manifest 并调用 `manager.reconcile()`（`:133-155`）。本轮先启动 `ch-a`，再送 `manifest_revision=2, channels=[None]`：实现返回 `{outcome:'applied', failures:[]}`，旧 adapter 收到 `stop` 且 registry 为空，正好违反 M4-E4 和 progress 中“任一 item 失败整份 retryable_failed”的声明。现有回归只覆盖结构完整 item 的 `credential_key_id` mismatch（`tests/unit/personal_assistant/test_channel_credential_recovery.py:142-210`）。**修复：**在任何 lifecycle/cache mutation 前严格验证 `channels`/`removals` 均为 arrays 且每项为完整 mapping；任一结构、generation、key、envelope 或 opener 错误都返回 `retryable_failed`，不调用 `reconcile`、不 stop runtime、不 commit cache/advance applied head。增加 malformed member、missing/non-array channels、malformed removal 和 opener failure 回归，并直接断言旧 runtime/cache/applied head 保持。

### WARNING（应该修）

- 无。

### SUGGESTION（可以修）

- 无。

2 critical issue(s) found. Fix before PR.

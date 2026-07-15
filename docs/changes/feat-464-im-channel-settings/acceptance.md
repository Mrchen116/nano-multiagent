# feat-464-im-channel-settings — 验收报告

> 对齐：`spec.md` / `design.md` / `prototype.html`；Round 1，full acceptance。
>
> 实现验收基线：`2cc8826aa74f16e1e7df85a942f05e4a8cf6b27c`。验收提交前按要求快进到
> `15319e0ef`；后者仅新增 `verification.md`，未改变本轮实际体验的实现、测试或配置。

## Verdict

**fail**

**Highest Required Action: `fix-implementation`**

真实用户主路径中，在线保存现有有效凭据可在无需改配置文件或重启 Gateway 的情况下从
`Connecting` 收敛到 `Connected`；但在线停用在确认后超过 90 秒仍停留在 `Disabling`，无法到达
`Disabled`，因而“停用后不再收发”和“无需重填密钥重新启用”两条核心生命周期旅程不可完成。

另有两组必验行为本轮只能判为 `inconclusive`：真实 provider 产生的 invalid credential / Bot disabled
分类，以及删除后影子会话/历史保留与 stop failure/retry。生产 store 注入只用于验页面如何投影难以稳定制造的状态，
不冒充 Gateway 或飞书真实地产生了该状态。

## 验收环境与证据口径

- Worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-464`
- 实际前端：从实现基线 `2cc8826aa` 构建；IM 返回的新 bundle 含本 unit 的 Channels 文案，bundle SHA-256
  为 `d9b5bca86b5ab6fcf9da06e7febb16b169196cbac204090447dc8e2340d9ff03`。
- 真实栈：`scripts/e2e-up.sh` 启动独立高位端口 IM + foreground Gateway；使用真实登录、真实 HTTP/WS、
  真实 Gateway 进程和真实已配置飞书应用。验收结束后已执行 `scripts/e2e-down.sh`，无监听或浏览器残留。
- 浏览器：headed Chromium；desktop `1440×1000`，mobile `375×812`。
- 难以稳定触发的 limited / unknown / reconnecting / failed 展示态：通过 production
  `ChannelControlStore` 向本轮真实 IM SQLite 写入确定性 status result，再由真实 HTTP 和真实前端读取。
  该证据只证明控制面到 UI 的产品投影，不证明 provider 能正确分类并上报该状态。
- 所有本轮截图/录屏位于
  `output/playwright/feat-464-acceptance-r1/`，按派发约束保持为 ignored/untracked 验收产物，未纳入报告提交。

## 用户旅程体验

### 1. 通用入口、向导与安全编辑

1. 以 `plato` 打开 Agent → Channels，看到通用 External channels 空态、统一 Add channel CTA，页面没有把 Web IM
   或未来 provider 当成可配置 channel。
2. Add channel 只展示 Feishu；已有 Feishu 的 `default-agent` 中同一项显示 Added 且不可重复添加。
3. 飞书向导只给短说明，并打开精确链接
   `https://open.feishu.cn/page/launcher?from=backend_oneclick`；未填 App ID/App Secret 时两个字段均给出明确错误。
4. 编辑现有配置时 App Secret 从未回显；默认选择 Keep existing secret，选择 Replace 后才出现空 secret 输入，
   空值不可提交。
5. 节点在线时，保持现有有效 secret 保存：页面立即出现 Connecting / “Configuration and credentials saved
   securely”，4 秒内变为 Connected / “Current configuration applied”，未编辑配置文件、未重启 Gateway。

证据：`channels-empty-desktop.png`、`add-provider-picker-desktop.png`、`add-feishu-guide-desktop.png`、
`add-feishu-required-errors.png`、`add-feishu-already-added.png`、`edit-secret-keep.png`、
`edit-secret-replace-required.png`、`edit-keep-save-online-r1.webm`、`edit-keep-save-immediate-r1.png`
（SHA-256 `296b8f43...17aa`）、`edit-keep-save-terminal-r1.png`（SHA-256 `ce54c31c...5845`）。

### 2. 真实连接与确定性诊断投影

- 真实已配置飞书应用显示 Connected、最近状态更新时间和 Current configuration applied；App ID 被掩码，
  页面没有 revision/版本号。
- production-store → 真 IM HTTP → 真前端的确定性状态证明：
  - limited 逐项展示 raw scope、影响、修复方向；缺 `im:message.group_msg` 时明确提示群背景上下文不完整；
  - unknown 显示 Permission status temporarily unavailable 与重试建议，不伪造 missing；
  - reconnecting 将连接恢复与权限 unknown 分层，并保留手动 Reconnect；
  - failed 投影可以显示用户可读的 credential/Bot/long-connection 检查建议。
- 手动 Reconnect 的真实操作进入恢复流程并回到 Connected；failed 的 provider-originated 端到端分类没有在本轮制造，
  因此对应 spec Scenario 仍是 `inconclusive`。

证据：`channel-connected-desktop.png`、`feishu-real-connected-complete-r1.png`、
`channel-limited-production-store-r1.png`（SHA-256 `01b266e0...f6d2`）、
`channel-permission-unknown-r1.png`（`cf2a2b34...2cd`）、
`channel-reconnecting-unknown-r1.png`（`ba6bccc8...10f`）、
`channel-failed-actionable-unknown-r1.png`（`07c058d7...6eb`）、`channel-reconnect-flow-r1.webm`。

### 3. 离线保存、删除与节点重连

1. 停止 Gateway 后，页面保留在线停用产生的期望状态，明确显示等待节点上线应用，而不是伪装为 Connected。
2. 离线删除确认文案说明：凭据立即移除、节点实际停止前条目保持 deletion pending、聊天历史保留。
3. 确认后条目显示 Deletion pending；reload 后仍保持，不出现空态、也不能重复添加同 provider。
4. 同一隔离配置的 Gateway 再上线后，不再次保存即可收敛为空态。

这证明了离线期望状态的持久化、reload 保持和 reconnect 自动应用；但本轮没有在删除前建立可见影子会话，
也没有真实制造 stop failure/retry，因此不能据此宣称“历史仍可读”和“失败可重试”已通过。

证据：`channel-pending-offline-disable.png`、`channel-delete-confirm-offline.png`、
`channel-deletion-pending-offline.png`、`channel-deletion-pending-after-reload.png`
（SHA-256 `6a822611...91bc`）、`channel-delete-converged-empty-r1.png`
（SHA-256 `dfdf37a3...6799`）。

### 4. 生命周期阻断：Disable 不收敛

在真实 Connected 卡片点击 Disable，确认页清楚说明停止收发、保留配置和凭据；确认后进入 Disabling。
等待超过 90 秒，节点仍显示 online，卡片仍是：

> Disable change saved · Waiting for the node to stop messaging

页面从未进入 Disabled。由于用户无法得到“实际停止”的终态，也就无法继续执行 Enable，无法验证无需重填 secret
的重连。这里不从产品验收阶段猜测代码根因；修复必须让真实 Gateway 生命周期完成收敛，并以用户可见终态证明停止。

证据：`channel-disable-flow-r1.webm`、`channel-disable-confirm.png`、`channel-disabling.png`、
`channel-disable-stuck-after-90s.png`（SHA-256 `e7c94811...c84d`）。

### 5. 失败态、响应式与 owner 边界

- 在已登录并已加载 Agent 外壳的浏览器中停止真实 IM，再首次打开 Channels：页面显示 Unable to load channel
  configuration / Failed to fetch / Retry，不显示空态；点击 Retry 后仍保持错误态并产生新请求。
- `375×812` 下左侧 rail 收起，channel 卡片单列，Edit/Reconnect/Disable/Delete 均可触达；Add/Edit/Delete
  对话框均为底部 sheet。
- 使用第二个真实登录 owner B 走 binding HTTP：B 对已属于 A 的 node confirm 得到 409；B 读取 A 的 channel
  得到 404，B 发起 reconnect 也得到 404；A 再次确认同一 node 为 201，重复 confirm 仍为 201。整个过程后 A
  的 channel 仍可见。报告不记录 bind token。

证据：`channels-list-error-real-im-outage-r1.png`、`channels-list-error-after-retry-r1.png`
（SHA-256 `4e3d502c...0b63`）、`channels-mobile-375x812-r1.png`
（`7aa240e5...bcd6`）、`channels-mobile-add-sheet-r1.png`、`channels-mobile-edit-sheet-r1.png`、
`channels-mobile-delete-sheet-r1.png`；cross-owner 为本轮 sanitized HTTP 状态记录。

## Reference Artifacts Reviewed

对照源：`docs/changes/feat-464-im-channel-settings/prototype.html`。本轮先用本地 HTTP 逐个打开原型控制态，
再在相同 desktop/mobile viewport 走真实产品。实现允许英文 UI 与视觉细节适配，但必须保持状态、层级、操作和
responsive contract。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html#channels-empty` | 通用空态、统一 CTA、无 Web IM | `channels-empty-desktop.png` | 1440×1000 / empty | match：层级与 CTA 一致 |
| `prototype.html#add-feishu` | provider picker、短指引、精确链接、必填、keep/replace | `add-provider-picker-desktop.png`; `add-feishu-guide-desktop.png`; `add-feishu-required-errors.png`; `edit-secret-keep.png`; `edit-secret-replace-required.png` | 1440×1000 / add+edit | match |
| `prototype.html#channel-connecting` | 保存后先显示真实连接进度 | `edit-keep-save-immediate-r1.png`; `edit-keep-save-online-r1.webm` | 1440×1000 / connecting | match |
| `prototype.html#channel-connected` | connected、实际应用文案、最近状态时间、操作区 | `edit-keep-save-terminal-r1.png`; `feishu-real-connected-complete-r1.png` | 1440×1000 / connected | match |
| `prototype.html#channel-pending` | 离线等待应用，不假 connected | `channel-pending-offline-disable.png` | 1440×1000 / node offline | match |
| `prototype.html#channel-actions`, `#channel-disabling`, `#channel-disabled` | 确认→disabling→disabled，并可再次启用 | `channel-disable-confirm.png`; `channel-disable-flow-r1.webm`; `channel-disable-stuck-after-90s.png` | 1440×1000 / connected→disabling | **deviation**：前两态 match，真实产品不进入 disabled |
| `prototype.html#channel-deleting` | deletion pending、reload、失败重试、实际停止后移除 | `channel-deletion-pending-offline.png`; `channel-deletion-pending-after-reload.png`; `channel-delete-converged-empty-r1.png` | 1440×1000 / offline→reconnect | **inconclusive**：pending/reload/removal match；真实 stop failure/retry 未覆盖 |
| `prototype.html#channel-reconnecting`, `#channel-failed` | 恢复过程、手动重试、可操作失败 | `channel-reconnect-flow-r1.webm`; `channel-reconnecting-unknown-r1.png`; `channel-failed-actionable-unknown-r1.png` | 1440×1000 / reconnecting+injected failed | **inconclusive**：reconnect match；failed 仅证明 UI 投影，不证明 provider 分类 |
| `prototype.html#channel-limited` | missing/unknown 分项、影响、修复方向 | `channel-limited-production-store-r1.png`; `channel-permission-unknown-r1.png` | 1440×1000 / deterministic status | match（仅控制面→UI 投影） |
| `prototype.html#channels-error` | 错误与 retry，不显示空态 | `channels-list-error-real-im-outage-r1.png`; `channels-list-error-after-retry-r1.png` | 1440×1000 / real IM outage | match |
| `prototype.html#channels-mobile` | 单列卡片、关键动作可达、底部 sheet | `channels-mobile-375x812-r1.png`; `channels-mobile-add-sheet-r1.png`; `channels-mobile-edit-sheet-r1.png`; `channels-mobile-delete-sheet-r1.png` | 375×812 / limited+dialogs | match |

## 问题清单

### Issue 1 — 在线 Disable 超过 90 秒不收敛

- **Severity:** blocking
- **Regression Relation:** direct
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** 直接违反“停用已连接的 channel”，并阻断“重新启用 channel”；第一轮默认回实现层修复。
- **Reproduction:** Connected → Disable → 确认 → 等待 90 秒以上。
- **Expected:** Gateway 实际停止后页面进入 Disabled，后续飞书消息不再触发 Agent，配置和凭据保留。
- **Actual:** 页面永久保持 Disabling / Waiting for the node to stop messaging；Enable 入口不可达。
- **Evidence:** `channel-disable-stuck-after-90s.png`, `channel-disable-flow-r1.webm`。

### Issue 2 — 真实 provider 的 invalid credential / Bot disabled 可操作失败尚未被验明

- **Severity:** major
- **Regression Relation:** direct
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** 这是首文档的必验 Scenario；仅注入 status 能证明前端可渲染，不能证明真实 Gateway 能产生具体原因。
- **Expected:** 使用无效 App ID/App Secret、未启用 Bot 或无法建连时，真实产品直接显示可理解原因和下一步。
- **Actual:** 本轮未用真 provider 安全地制造这些分支；对应 Scenario 为 `inconclusive`，不能以注入文案判 pass。
- **Evidence:** `channel-failed-actionable-unknown-r1.png` 明确标注为 production-store 注入投影。

### Required revalidation gaps

- 离线新增/修改/启用的各自用户旅程没有在本轮独立走完；已验证离线停用、删除、reload 和 reconnect 自动移除。
- 删除前没有建立可见影子会话，因而“删除后历史仍可读”未验明。
- 未真实制造 channel stop failure，因而 deletion failed + Retry 未验明。

这些是严格验收缺口，不等同于已确认实现缺陷；但任一必验 Scenario 为 `inconclusive` 时本轮不能给 pass。

## 验收标准覆盖

### Requirement: 通用的外部 channel 管理页 — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 尚未配置任何外部 channel | `spec.md`; `prototype.html#channels-empty` | plato → Channels | `channels-empty-desktop.png`；与原型对照 match | pass | 无 Web IM |
| 从统一入口选择 channel 类型 | `spec.md`; `prototype.html#add-feishu` | Add channel | `add-provider-picker-desktop.png` | pass | 通用语言，仅 Feishu |
| 当前类型已经存在 | `spec.md` | 已有 Feishu 的 default-agent → Add | `add-feishu-already-added.png` | pass | Added disabled |
| channel 列表加载失败 | `spec.md`; `prototype.html#channels-error` | 加载外壳后停真实 IM → Channels → Retry | `channels-list-error-real-im-outage-r1.png`; `channels-list-error-after-retry-r1.png` | pass | 不渲染空态 |

### Requirement: 飞书轻量接入向导 — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户查看飞书准备指引 | `spec.md`; `prototype.html#add-feishu` | 选择 Feishu 并打开外链 | `add-feishu-guide-desktop.png` | pass | 精确 launcher URL 可访问 |
| 在线节点保存有效配置后立即连接 | `spec.md`; `prototype.html#channel-connecting/#channel-connected` | 保留已配置有效 secret → Save and connect | `edit-keep-save-online-r1.webm`; immediate/terminal screenshots；原型对照 match | pass | Connecting→Connected，无 restart |
| 必填凭据缺失 | `spec.md`; `prototype.html#add-feishu` | 空表单提交 | `add-feishu-required-errors.png` | pass | 不声称 connected |
| 已保存密钥不会重新明文展示 | `spec.md`; `prototype.html#add-feishu` | Edit → Keep/Replace | `edit-secret-keep.png`; `edit-secret-replace-required.png` | pass | secret 从未回显 |

### Requirement: 连接状态与可操作诊断 — 组内结论：fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 权限完整且连接正常 | `spec.md`; `prototype.html#channel-connected` | 真实已配置 app + 在线保存 | `feishu-real-connected-complete-r1.png`; `edit-keep-save-terminal-r1.png` | pass | 有状态时间 |
| 权限不足但基础能力仍可用 | `spec.md`; `prototype.html#channel-limited` | production store 注入 limited → 真 HTTP/UI | `channel-limited-production-store-r1.png`；原型对照 match | pass | 仅投影结论 |
| 缺少普通群消息权限 | `spec.md`; `prototype.html#channel-limited` | 注入 missing `im:message.group_msg` | `channel-limited-production-store-r1.png` | pass | 影响明确到群背景上下文 |
| 暂时无法完成权限检查 | `spec.md`; `prototype.html#channel-limited` | 注入 unknown → 真 HTTP/UI | `channel-permission-unknown-r1.png` | pass | unknown 未伪造 missing |
| 凭据或连接无效 | `spec.md`; `prototype.html#channel-failed` | 注入 failed 投影；未制造真实 provider failure | `channel-failed-actionable-unknown-r1.png` | inconclusive | UI 可渲染，不证明 Gateway 分类 |
| 连接暂时中断 | `spec.md`; `prototype.html#channel-reconnecting` | 手动真实 Reconnect + 注入稳定 reconnecting 观察 | `channel-reconnect-flow-r1.webm`; `channel-reconnecting-unknown-r1.png` | pass | 最终回 Connected |

### Requirement: 离线配置与重连收敛 — 组内结论：fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 节点离线时保存飞书配置变更 | `spec.md`; `prototype.html#channel-pending/#channel-deleting` | Gateway offline 时停用、删除、reload | `channel-pending-offline-disable.png`; deletion pending screenshots | pass | 已覆盖两种期望变更；不假 connected |
| 节点重连后自动应用 | `spec.md`; `prototype.html#channel-pending/#channel-deleting` | 离线删除后启动同一 Gateway config | `channel-deletion-pending-after-reload.png`; `channel-delete-converged-empty-r1.png` | inconclusive | 自动应用已证明；未覆盖保留 channel 的 connected/limited/failed 终态 |

### Requirement: 飞书 channel 生命周期管理 — 组内结论：fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 停用已连接的 channel | `spec.md`; `prototype.html#channel-actions/#channel-disabling/#channel-disabled` | Connected → Disable → confirm → 等待 >90 秒 | `channel-disable-flow-r1.webm`; `channel-disable-stuck-after-90s.png`；原型对照 deviation | fail | 不进入 Disabled，也未证明停止收发 |
| 重新启用 channel | `spec.md`; `prototype.html#channel-disabled` | 依赖上一旅程先到 Disabled | 同上 | fail | Disable 不收敛导致 Enable 不可达 |
| 删除 channel 保留历史 | `spec.md`; `prototype.html#channel-deleting` | offline delete → reload → node reconnect | pending/reload/converged screenshots | inconclusive | 实际移除已证明；stop failure/retry 与既有历史仍可读未证明 |

### Requirement: 节点绑定不得隐式迁移跨 owner channel — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 已绑定节点被另一个 owner 确认 | `spec.md` | owner B confirm/read/reconnect；owner A 重复 confirm | sanitized HTTP: B confirm 409，B read/control 404，A confirm 201/201；A UI 仍可见 | pass | 无 token 入报告；同 owner 幂等 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。本 unit 未改变四包拓扑或依赖方向。
- [x] `docs/specs/<包>/`（长青行为契约层）：**需要更新**。当前
  `docs/specs/im/agents-nodes.md` 与 `docs/specs/gateway/external-channels.md` 尚未归并本 unit 的 control-plane、
  desired/actual、动态生命周期、诊断和 owner 隔离增量；应由 orchestrator §7.0 将
  `docs/changes/feat-464-im-channel-settings/specs/` 两份 delta 写回 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。开发约定、启动方式和包边界未变化。
- [x] `docs/SPEC_GUIDE.md`：**无需更新**。本 unit 未改变文档体系。
- [x] `docs/operator-runbook.md`：**需要更新**。第 6 节仍把 Feishu 描述为主要通过 YAML 增量启用，需补充
  IM Channels 页热管理、一次性 legacy bootstrap、离线保存与 deletion pending / retry 的操作语义。
- [x] `docs/e2e-critical-paths.md`：**需要更新**。现有清单只有 feat-447 的 Feishu 消息主路径，尚未登记
  feat-464 的 channel control 热生效与停用/删除收敛关键旅程及其守护方案。

以上需要更新项尚无 PR/commit 链接；本轮 reviewer 按职责只做对账，不改 canonical 文档。

## Side Findings

- 无 out-of-unit side finding；本轮确认的问题与验收缺口都在 feat-464 能力域内。

---

# Round 2 — 2026-07-15

**Highest Required Action:** `pass`

**Verdict:** `pass`

本轮按 `revalidation_mode=full` 在实现基线
`46096e3ec5a4875974345c6a5d82d5ebe8fba6e2` 上重新接管完整真实栈，未继承第一轮结论。
20/20 个必验 Scenario 均得到用户面结论，11/11 个 prototype must-match 状态均完成 reference →
真实产品对照。第一轮的 Disable 不收敛、真实 provider 失败分类、离线保留 channel 的重连终态、删除历史与
失败重试缺口均已关闭；本轮无 blocking / major / minor issue。

## 验收环境与证据口径

- Worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-464`。
- 实现基线：`46096e3ec5a4875974345c6a5d82d5ebe8fba6e2`；Round 2 开始时该 HEAD 与派发包一致。
- 前端：从该 HEAD 的 `src/IM/frontend` 独立 production build，444 modules transformed；浏览器实际加载的
  `assets/index-BEkbLe3b.js` 与本地 build SHA-256 同为
  `46f46748b1ab046acec3a0a59216127cd24d95d286490636be12eed8a80e8baf`，并命中本 unit 的
  `Current configuration applied` / `Retry apply` / `Added` marker。
- 真实栈：`scripts/e2e-up.sh` 启动隔离 IM `127.0.0.1:63259` 与 worktree-local Gateway config；
  使用真实登录、HTTP、WebSocket、Gateway、已配置飞书测试应用和真实 Feishu provider 网络。
- 浏览器：headed Chromium；desktop `1440×1000`，mobile `375×812`。
- limited / unknown：真实测试应用本身权限完整，不为制造受限态修改外部权限。本轮只将确定性诊断写入
  production status row，再由真实 IM HTTP 和真实前端读取；结论仅覆盖控制面 → UI 产品投影，并与真实
  complete app 结果分开描述。
- 删除失败：使用仓库 Runbook 指定、显式 gated 的
  `scripts/fixtures/channel_cache_commit_failure.py`，只让第一次 removal cache commit 失败；失败后的 reload、
  Retry apply 和最终收敛仍走真实 IM/Gateway/frontend。
- 安全审计：本轮使用的无效测试 secret 在 IM DB、Gateway cache/key/config/state、IM/Gateway logs 和浏览器
  evidence 中均为 0 file hits；worktree config 只有 `credentialRef`、没有 `appSecret`；config、manifest、key
  权限均为 `0600`。认证 token、bind token 和真实 secret 未写入报告。
- Round 2 截图/录屏位于 `output/playwright/feat-464-acceptance-r2/`，按派发约束保持 ignored/untracked。

## Round 1 问题与缺口复核

| Round 1 项 | Round 2 结果 | 独立用户面证据 |
|---|---|---|
| Issue 1：Connected → Disable 超过 90 秒不收敛 | **closed** | `disable-confirm-r2.png`; `disable-to-enable-r2.webm`; `disabled-terminal-r2.png`。确认后约 1 秒进入 Disabled，文案为 Node applied the disabled state / No longer receiving or sending new messages |
| Issue 2：真实 provider invalid credential / Bot 状态未验明 | **closed** | 新建真实 Feishu 配置使用无效 App ID/Secret，经真实 provider 网络进入 Connection failed，并明确提示 Feishu 无法认证应用、检查可用性后重试；`invalid-credential-real-provider-r2.webm`; `invalid-credential-terminal-r2.png` |
| 离线新增/修改/启用缺口 | **closed（覆盖保留 channel 的 disable + enable）** | `offline-disable-pending-r2.png` → `offline-disable-converged-disabled-r2.png`; `offline-reenable-pending-r2.png` → `offline-reenable-converged-connected-r2.png` |
| 删除后影子会话/历史未验明 | **closed** | 删除前后同一真实 Web IM 会话和 messages API 均保留 `feat-464 round-2 retained Feishu history`；`feishu-history-before-delete-r2.png`; `feishu-history-after-delete-r2.png` |
| deletion failed + Retry 未验明 | **closed** | 第一次 cache commit 失败显示 Deletion incomplete，reload 后保持；Retry apply 后为空态；`delete-cache-failure-retryable-r2.png`; `delete-failure-persists-reload-r2.png`; `delete-retry-converged-empty-r2.png` |

## User Journeys Exercised

### Journey 1 — 通用入口、飞书向导与安全编辑

1. 在无 channel 的 Agent 打开 Channels：得到通用 External channels 空态、统一 Add channel CTA，页面没有
   Web IM 或未来 provider。
2. provider picker 只列 Feishu；已有 Feishu 的 Agent 中 Added 不可重复添加。
3. Feishu 指引打开精确的
   `https://open.feishu.cn/page/launcher?from=backend_oneclick`，实际到达飞书登录页；空 App ID / App Secret
   均有必填错误。
4. 编辑真实 channel 时 App Secret 不回显，默认 Keep existing secret；Replace 只出现空输入且必填。
5. Keep 后在线保存立即显示 Connecting / saved securely，并在同一进程内回到 Connected / current applied，
   未改 config、未重启 Gateway。

证据：`empty-desktop.png`、`provider-picker-empty-agent.png`、`provider-unique-added-r2.png`、
`feishu-guide-r2.png`、`required-errors-r2.png`、`secret-keep-r2.png`、
`secret-replace-required-r2.png`、`online-save-keep-r2.webm`、`online-save-connecting-r2.png`、
`online-save-connected-r2.png`。

### Journey 2 — 真实 provider、连接诊断与动态生命周期

1. 真实有效应用显示 Connected、实际应用文案和最近状态时间；App ID 掩码、页面无内部 revision。
2. 真实无效凭据先显示 Connecting，再稳定为可操作 Connection failed；permission unknown 与连接失败保持分层。
3. 手动 Reconnect 有恢复过程并回 Connected。
4. Connected → Disable → confirm 后真实 Gateway 状态收敛为 Disabled；凭据保留，页面明确不再收发新消息。
5. 未输入 secret 直接 Re-enable，先显示 Connecting，再回真实 Connected。

证据：`connected-desktop.png`、`invalid-credential-real-provider-r2.webm`、
`invalid-credential-terminal-r2.png`（SHA-256 `95115a1f...45fe`）、`manual-reconnect-r2.webm`、
`manual-reconnect-terminal-r2.png`、`disable-to-enable-r2.webm`、`disabled-terminal-r2.png`
（`ae9ac24c...8965`）、`reenable-connecting-r2.png`、`reenable-connected-r2.png`。

### Journey 3 — 离线期望状态、节点重连、删除与历史

1. 停 Gateway 后旧 Connected 被明确标成 node offline / stale；离线 Disable 保存为 waiting，不冒充 Disabled。
2. 同一 Gateway config 恢复后，无需再次保存自动进入 Disabled。
3. 再次离线 Re-enable：页面保留 waiting；节点恢复后自动进入 Connected，不重填 secret。
4. 通过真实 external shadow-conversation API 建立 Feishu 会话并写入一条用户可见历史；Web IM 会话可读。
5. 删除确认明确说明凭据立即移除、card 保留到节点停止、history retained。第一次 removal cache commit 失败后
   card 显示 credentials removed from IM / Deletion incomplete / Retry apply，reload 不丢失；Retry 后收敛为空态。
6. 删除后原 Web IM 会话和 messages API 仍能读取原消息。

证据：`offline-connected-stale-r2.png`、`offline-disable-pending-r2.png`、
`offline-disable-converged-disabled-r2.png`、`offline-reenable-pending-r2.png`、
`offline-reenable-converged-connected-r2.png`、`feishu-history-before-delete-r2.png`、
`delete-cache-failure-retryable-r2.png`（`8f2525aa...cff0`）、`delete-failure-persists-reload-r2.png`、
`delete-retry-converged-empty-r2.png`、`feishu-history-after-delete-r2.png`（`544470aa...ca35`）。

### Journey 4 — 诊断、加载失败恢复与 375×812

- limited：逐项显示 raw scope、影响和修复方向；缺 `im:message.group_msg` 明确说明未 @Bot 的群消息不会进入
  群背景上下文。
- unknown：显示 Permission status temporarily unavailable / Temporarily unavailable，不伪造成 missing。
- 在预先加载 Agent 外壳后停止真实 IM，再首次进入 Channels：显示 Unable to load channel configuration /
  Failed to fetch / Retry，不显示空态。点击 Retry 产生 1 个新的真实 channels request，错误态仍保持；同 DB、
  JWT、端口恢复后再次 Retry 得到原 Disabled card。
- 375×812 下 rail 收起、card 单列、关键动作可达；Add/Edit/Delete 均为底部 sheet。

证据：`limited-production-row-r2.png`（`a129e48f...8841`）、
`permission-unknown-production-row-r2.png`（`3c281d5f...d27c`）、
`list-error-real-im-outage-r2.png`、`list-error-retry-real-request-r2.png`、`list-retry-restored-r2.png`、
`mobile-connected-375x812-r2.png`、`mobile-add-sheet-375x812-r2.png`（`e74820e3...250e`）、
`mobile-edit-sheet-375x812-r2.png`、`mobile-delete-sheet-375x812-r2.png`。

### Journey 5 — owner 边界

使用第二个真实注册/登录 owner B 走公开 binding 与 channel HTTP：B start bind 为 201、confirm 已归属 A 的 node
为 409；B 读取 A 的 agent channels 为 404，B 控制 A 的 channel 也为 404；A start 为 201、首次 confirm 为
201、重复 confirm 仍为 201。整个记录只保留 sanitized HTTP 状态，不包含 token。

## Reference Artifacts Reviewed

对照源：`docs/changes/feat-464-im-channel-settings/prototype.html`。本轮通过本地 HTTP 在真实浏览器逐个切换
11 组 must-match 控制态，分别保存 `ref-*.png`，再与同轮真实产品截图/录屏逐态对照。英文文案、icon、阴影和
transition 属 design 允许的适配；状态层级、操作和 responsive contract 必须 match。

| Prototype must-match | Required contract | Actual product evidence | Viewport / state | Conclusion |
|---|---|---|---|---|
| `#channels-empty` | 通用空态、统一 CTA、无 Web IM | `ref-01-empty.png` ↔ `empty-desktop.png` | 1440×1000 / empty | match |
| `#add-feishu` | provider picker、短指引、精确链接、必填与 keep/replace | `ref-02-add-feishu.png` ↔ provider/guide/required/secret screenshots | 1440×1000 / add+edit | match |
| `#channel-connecting` | 保存后立即展示真实连接进度 | `ref-04-connecting.png` ↔ `online-save-connecting-r2.png`; invalid/online videos | 1440×1000 / connecting | match |
| `#channel-connected` | connected、actual applied、时间、动作区 | `ref-03-connected-actions.png` ↔ `connected-desktop.png`; `online-save-connected-r2.png` | 1440×1000 / connected | match |
| `#channel-pending` | 离线 waiting，不假 connected；恢复后自动应用 | `ref-08-pending.png` ↔ offline pending/converged screenshots | 1440×1000 / offline→online | match |
| `#channel-actions/#channel-disabling/#channel-disabled` | 确认→应用中→disabled→无 secret 再启用 | `ref-05-disabled.png` ↔ `disable-to-enable-r2.webm`; terminal screenshots | 1440×1000 / connected→disabled→connected | match；Round 1 deviation closed |
| `#channel-deleting` | pending/failed 持久、凭据移除、retry、实际应用后消失、历史保留 | `ref-06-deleting.png`; `ref-07-delete-failed.png` ↔ delete/history screenshots | 1440×1000 / failed→reload→retry | match；Round 1 gaps closed |
| `#channel-reconnecting/#channel-failed` | 恢复过程、手动重试、provider-originated 可操作失败 | `ref-10-reconnecting.png`; `ref-11-failed.png` ↔ manual reconnect + real invalid credential evidence | 1440×1000 / reconnecting+failed | match；Round 1 inconclusive closed |
| `#channel-limited` | missing/unknown 分项、raw scope、影响、修复 | `ref-09-limited.png` ↔ limited/unknown production projection screenshots | 1440×1000 / connected+diagnostics | match（投影口径） |
| `#channels-error` | 错误 + Retry，不显示空态 | `ref-12-list-error.png` ↔ real IM outage/retry/restore screenshots | 1440×1000 / outage→restore | match |
| `#channels-mobile` | 单列 card、动作可达、bottom sheet | `ref-13-mobile.png` ↔ four 375×812 screenshots | 375×812 | match |

## Issues

无。

## 验收标准覆盖

### Requirement: 通用的外部 channel 管理页 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 尚未配置任何外部 channel | `spec.md`; `#channels-empty` | 无 channel Agent → Channels | empty screenshot + reference | pass | 无 Web IM / future provider |
| 从统一入口选择 channel 类型 | `spec.md`; `#add-feishu` | Add channel | provider picker + reference | pass | 仅 Feishu |
| 当前类型已经存在 | `spec.md` | 已有 Feishu → Add | `provider-unique-added-r2.png` | pass | Added disabled |
| channel 列表加载失败 | `spec.md`; `#channels-error` | 预载外壳 → 停真实 IM → Channels → Retry → 恢复 | outage/retry/restore screenshots | pass | 错误态从未变空态 |

### Requirement: 飞书轻量接入向导 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户查看飞书准备指引 | `spec.md`; `#add-feishu` | 选择 Feishu → 打开外链 | `feishu-guide-r2.png` | pass | launcher URL 实际可达 |
| 在线节点保存有效配置后立即连接 | `spec.md`; `#channel-connecting/#channel-connected` | Edit → Keep → Save | online-save video + immediate/terminal | pass | 同进程 Connecting→Connected |
| 必填凭据缺失 | `spec.md`; `#add-feishu` | 空表单提交 | `required-errors-r2.png` | pass | 两字段明确错误 |
| 已保存密钥不会重新明文展示 | `spec.md`; `#add-feishu` | Edit Keep/Replace | keep/replace screenshots + zero-hit audit | pass | secret 不回显、不落 DB/log/evidence |

### Requirement: 连接状态与可操作诊断 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 权限完整且连接正常 | `spec.md`; `#channel-connected` | 真实测试应用 + 在线保存 | connected/terminal screenshots | pass | actual applied + time |
| 权限不足但基础能力仍可用 | `spec.md`; `#channel-limited` | deterministic production status → 真 HTTP/UI | `limited-production-row-r2.png` + reference | pass | 仅投影结论 |
| 缺少普通群消息权限 | `spec.md`; `#channel-limited` | missing group scope projection | same | pass | 明确群背景影响 |
| 暂时无法完成权限检查 | `spec.md`; `#channel-limited` | unknown projection | `permission-unknown-production-row-r2.png` | pass | 不伪造 missing |
| 凭据或连接无效 | `spec.md`; `#channel-failed` | 真实无效 App ID/Secret → provider 网络 | invalid credential video/terminal | pass | 可操作认证失败；Round 1 closed |
| 连接暂时中断 | `spec.md`; `#channel-reconnecting` | 手动真实 Reconnect | manual reconnect video/terminal | pass | 恢复到 Connected |

### Requirement: 离线配置与重连收敛 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 节点离线时保存飞书配置变更 | `spec.md`; `#channel-pending` | offline Disable；offline Re-enable | two pending screenshots | pass | 保存 desired，不假 terminal |
| 节点重连后自动应用 | `spec.md`; `#channel-pending` | 同 config 重启 Gateway | disabled/connected convergence screenshots | pass | 保留 channel 得到正确终态 |

### Requirement: 飞书 channel 生命周期管理 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 停用已连接的 channel | `spec.md`; `#channel-actions/#channel-disabling/#channel-disabled` | Connected → Disable → confirm | disable video + terminal | pass | 真实 Gateway 确认不再收发；Round 1 closed |
| 重新启用 channel | `spec.md`; `#channel-disabled` | Disabled → Re-enable，不填 secret | connecting/connected screenshots | pass | 凭据保留 |
| 删除 channel 保留历史 | `spec.md`; `#channel-deleting` | 创建影子历史 → 删除失败 → reload → Retry → 再读历史 | delete/history screenshots + messages API count 1 | pass | 凭据先移除、失败可恢复、历史仍可读 |

### Requirement: 节点绑定不得隐式迁移跨 owner channel — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 已绑定节点被另一个 owner 确认 | `spec.md` | owner B bind/read/control；owner A confirm/repeat | sanitized HTTP 201/409/404/404/201/201 | pass | 无 token 入报告；同 owner 幂等 |

## 上层文档同步

- [x] `SPEC.md`：**无需更新**。本 unit 未改变四包拓扑或依赖方向。
- [x] `docs/specs/<包>/`：**需要 orchestrator 收尾归并**。unit delta 已描述 control-plane、desired/actual、
  动态生命周期、诊断、密钥和 owner 隔离，但 canonical IM/Gateway area 文档尚未完整反映该增量。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。开发约定、启动方式和包边界未变化。
- [x] `docs/SPEC_GUIDE.md`：**无需更新**。文档体系未改变。
- [x] `docs/operator-runbook.md`：**需要更新**。应加入 IM Channels 热管理、legacy bootstrap、离线保存、
  deletion pending / retry 与 credential re-entry 的操作语义。
- [x] `docs/e2e-critical-paths.md`：**需要更新**。应登记 feat-464 channel control 热生效、停用/重启、
  删除失败重试的关键旅程与守护方案。

以上写回属于 orchestrator 收尾职责，不改变本轮用户面 `pass` 结论。

## Side Findings

- 无。

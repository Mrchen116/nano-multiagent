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

# refactor-460 — 验收报告

> 对齐: `motivation.md` 的用户侧验收标准（不变性）

## Round 1 — 2026-07-13

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Review mode**: full
- **Acceptance bar**: round 1 strict

## 用户旅程体验

本轮从 clean browser session 重建并接管隔离真栈，served frontend 为
`index-BS4biOKS.js`，浏览器与 Gateway 均连接本 worktree 的 ephemeral IM
`http://127.0.0.1:52136`。未读取实现代码，也未用 reducer/subscriber 桩替代用户入口。

### Journey 1 — 桌面 Chat 完整实时过程、刷新一致性与静默回复

1. 从 Agents 列表进入 `default-agent` 详情，点击 `Open chat`，成功创建并进入单聊。
2. 发送「使用 bash 执行 `printf REF460_OK`」；当前页先出现生成中临时气泡，随后无需刷新显示
   `执行结果：REF460_OK`、`1 tool`、`2 thinking` 与 token usage。刷新后文本、工具/思考摘要保持一致。
3. 发送「严格保持沉默，不要回复」；当前页先出现临时 Agent 气泡，但完成后气泡没有撤销，而是显示字面量
   `NO_REPLY`。刷新页面后该气泡仍存在。

证据：Playwright 用户面快照；`/tmp/refactor460-review-realtime-desktop.png`；
`/tmp/refactor460-review-no-reply-visible.png`。

### Journey 2 — 非当前会话提醒、断网恢复与长登录凭证更新

1. 浏览器 A 保持打开 `default-agent`，浏览器 B 在 `plato` 单聊发送消息并得到
   `PLATO_TOAST_OK` / `PLATO_TOAST_2`。
2. 浏览器 A 的会话列表实时把 `plato` 排到首位并更新预览，但在线期间未出现应用内 toast，列表也没有可见未读标记。
3. 浏览器 A 当前会话内自己的消息没有产生多余 toast；浏览器 B 发送的同账号用户消息也没有误报。
4. 向浏览器 A 写入真实签名、已过期 access token（保留有效 refresh token）后 reload：页面没有退回登录页，
   access token 自动更新为 fresh，Agents 仍显示在线。随后把浏览器 A 置为 offline，期间让 `plato` 完成
   `RECOVERY_OK`，恢复网络后 A 只出现这一条新消息的应用内 toast；更早的 `PLATO_TOAST_*` 没有重放，
   会话预览也收敛到 `RECOVERY_OK`。

证据：恢复瞬间用户面快照显示 `plato / RECOVERY_OK / View message`；
`/tmp/refactor460-review-recovery-toast.png`。expired-token reload 期间浏览器开发者控制台出现预期首轮 401，
用户页面自动恢复且后续 token `exp` 已在当前时间之后。

### Journey 3 — Gateway 状态与账号切换

1. Agents 页初始显示 4 个 Agent 全部 online。
2. 停止隔离 Gateway 后，不刷新页面即全部变为 offline；重新启动同一 Gateway 后，不刷新页面即恢复 online。
3. 在同一浏览器从账号 A (`nano`) 退出并登录账号 B (`reviewerb460`)：旧会话 URL 虽保留在地址栏，页面只显示
   `No conversations`，没有 A 的消息内容或 toast。随后 A 的另一浏览器收到 `A_EVENT_AFTER_SWITCH`，B 页面仍保持空列表。

证据：Playwright online → offline → online 连续快照；
`/tmp/refactor460-review-account-switch.png`。

### Journey 4 — hot-cache 绑定与 Agent 详情单聊

1. 在同一 SPA document 中依次打开 Chat、Agents、Nodes、Account，预热已有缓存；绑定前 Me 显示
   `1 owned · 1 online`，Account 只列原默认节点。
2. 打开真实未绑定 Gateway 的有效绑定链接，一次点击 `Continue to chat` 后返回 Chat。
3. 紧接着打开 Me/Account：无需刷新即显示 `2 owned · 2 online`，Account 立即列出新节点
   `review-bind-460-1783925131 (online)`、`Owned nodes = 2`，原 default entry 仍正确，新 Node 卡显示 4 agents。
4. 使用错误 token 时页面原地显示明确反馈
   `POST /im/v1/bind failed: 404 (bind_token not found)`，按钮没有无响应。
5. `default-agent` 与 `plato` 的 Agent 详情 `Open chat` 均能进入有效单聊。

证据：`/tmp/refactor460-review-bind-account.png`；
`/tmp/refactor460-review-bind-invalid.png`；Playwright 绑定前后快照。

### Journey 5 — 桌面/移动 Chat 回归

在 1440×900 与 390×844 viewport 分别打开单聊。移动端正确显示 Back、消息时间线、Process、token usage、composer
与底部 Chat/Agents/Me 导航；发送 `MOBILE_OK` 后实时完成并显示完整内容。桌面核心 Chat 交互未见路径迁移导致的布局退化。

证据：`/tmp/refactor460-review-mobile-chat.png`；
`/tmp/refactor460-review-realtime-desktop.png`。

### 未能形成有效结论的旅程

- 隔离真栈没有配置可用的飞书/Lark app credential 与真实外部会话，无法从外部 channel 入口写入影子会话；
  未用 IM HTTP 造消息替代该用户旅程。
- 浏览器 notification permission 已在真实 headed browser 中设为 `granted`，但本轮未获得可验证的 macOS 系统通知
  截图、一次性计数与点击导航证据；没有用替换 `Notification` 构造器来冒充系统通知结果。

## Reference Artifacts Reviewed

N/A。`motivation.md` / `design.md` 明确本 unit 不改 UI 设计，未引用 prototype、设计稿或 reference screenshot；
本轮以现有桌面/移动 Web IM 用户旅程作为回归基线。

## 问题清单

### Issue 1 — 静默回复把 `NO_REPLY` 当普通消息持久展示

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: 直接违反「静默回复撤销临时气泡」Scenario；普通聊天仍可用，但用户明确要求沉默时会看到
  一条错误的 Agent 回复，且刷新后仍保留。
- **Expected**: Agent 最终选择静默回复后，生成中的临时 Agent 气泡消失，刷新历史也不出现该回复。
- **Actual**: 临时气泡完成为字面量 `NO_REPLY`，刷新后继续存在。
- **Reproduction**:
  1. 登录 Web IM，打开有效 Agent 单聊。
  2. 发送「请严格保持沉默，不要回复这条消息」。
  3. 等待 Agent 完成，再刷新页面。
- **Evidence**: `/tmp/refactor460-review-no-reply-visible.png`。

### Issue 2 — 在线时非当前会话的 Agent 回复没有应用内 toast / 可见未读标记

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: 会话预览与排序已更新，说明用户确实收到另一会话的新 Agent 回复；但用户要求的应用内 toast
  和未读提示没有出现，直接违反「未打开会话收到新消息」Scenario。
- **Expected**: 非当前会话收到可见 Agent 回复时出现既有应用内 toast，并同步预览、排序和未读角标。
- **Actual**: `plato` 两次在线完成 `PLATO_TOAST_OK` / `PLATO_TOAST_2` 后，另一浏览器中正在查看
  `default-agent` 的页面只更新了 `plato` 预览和排序，没有 toast，也没有可见未读标记。稍后的断网恢复路径能对
  `RECOVERY_OK` 正常显示 toast，问题集中在在线实时到达路径。
- **Reproduction**:
  1. 同一账号浏览器 A 打开会话 A。
  2. 浏览器 B 打开会话 B 并触发 Agent 完成一条可见回复。
  3. 观察浏览器 A 的会话列表与应用内提醒。

## 验收标准覆盖

### Requirement: 当前会话继续实时呈现完整消息过程 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Agent 回复实时更新 | `motivation.md` | Journey 1，真实 Gateway/LLM、工具调用、生成态→完成态→reload | `REF460_OK`、1 tool、2 thinking；桌面截图 | pass | 完成内容与刷新历史一致 |
| 静默回复撤销临时气泡 | `motivation.md` | Journey 1，真实 Agent 静默请求、观察临时态、完成态并 reload | `NO_REPLY` 持久截图 | fail | Issue 1 |
| 外部 channel 消息实时进入已打开会话 | `motivation.md` | 计划从真实 Lark 影子会话写入；隔离栈无可用外部 credential | 无真实外部 channel 证据 | inconclusive | 未用内部 HTTP 替代用户旅程 |

### Requirement: 会话列表、未读状态和应用内提醒保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 未打开会话收到新消息 | `motivation.md` | Journey 2，两个真实浏览器、同账号、不同当前会话 | `plato` 预览/排序实时更新；无 toast/未读标记 | fail | Issue 2 |
| 当前会话和自己的消息不产生多余提醒 | `motivation.md` | Journey 1/2，当前会话回复与另一标签页自己的消息 | 页面无误导 toast，当前会话/列表仍更新 | pass | 与非当前 Agent 回复缺 toast 区分验证 |

### Requirement: 桌面系统通知保持一次且可导航 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 后台标签页收到 Agent 完成通知 | `motivation.md` | headed browser 已授权 notification；尝试后台标签页真实 Agent 完成 | 缺 macOS 通知与点击导航证据 | inconclusive | 未用构造器 mock 代替系统通知 |
| 不满足通知条件时不弹通知 | `motivation.md` | 前台 Chat/Me 多次收到消息并观察系统/应用界面 | 消息正常到达；缺可靠 OS 通知计数 | inconclusive | 无法证明所有 gate 的系统结果 |
| 恢复连接不重放历史通知 | `motivation.md` | Journey 2，offline 期间产生 `RECOVERY_OK` 后恢复 | 只出现 `RECOVERY_OK` 应用内 toast，旧消息未重放 | pass | 应用内提醒路径已证实；系统通知主路径仍由前两行保持 inconclusive |

### Requirement: Node 与 Agent 状态继续实时变化 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 断连与重连 | `motivation.md` | Journey 3，Agents 页面停止/重启隔离 Gateway | 4 个 Agent 不刷新即 online→offline→online | pass | 与实际 Gateway 生命周期一致 |

### Requirement: 长时间登录与账号切换后实时体验仍然正确 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长时间保持登录后发生网络重连 | `motivation.md`、`design.md` Runbook | Journey 2，真实 expired access + valid refresh，reload，再 offline/online | 页面未退出、token 变 fresh、恢复后收到 `RECOVERY_OK` | pass | 不需要重新登录 |
| 退出后切换为另一用户 | `motivation.md` | Journey 3，同一浏览器 A logout→B login，再让 A 产生新事件 | B 只见 `No conversations`，无 A 内容/toast | pass | 地址栏旧 conversation id 未导致内容泄漏 |

### Requirement: 非实时入口保持原有可用性 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 确认 Gateway 绑定 | `motivation.md`、`design.md` Runbook | Journey 4，同 SPA 预热四类 cache 后确认真实 token；再走 invalid token | `2 owned · 2 online`、Account 新 Node/4 agents、明确 404 | pass | 一次点击返回 Chat，hot cache 立即一致 |
| 从 Agent 详情打开单聊 | `motivation.md` | Journey 1/4，从有效 Agent 详情点击 `Open chat` | 成功进入 direct conversation 并发送真实消息 | pass | 按钮有响应，未遇失败态 |

## Side Findings

- N/A。本轮没有发现可明确判为无关旧问题的 minor 用户面瑕疵。
- expired-token reload 的预期首轮 401 与账号切换旧 URL 的 404 仅出现在开发者控制台，用户页面均自动收敛；
  本轮不把它们列为交付 issue。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。本 unit 不改变 IM/Gateway/agent 的跨包职责与部署拓扑。
- [x] `docs/specs/im/`（长青行为契约层）：**需要更新**。unit 已提供
  `specs/im/web-chat-ux.md` 与 `specs/im/agents-nodes.md` delta；应由 orchestrator 收尾校正并合入 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。启动、端口隔离和真栈操作规范未改变。
- [x] `docs/SPEC_GUIDE.md`（文档规范）：**无需更新**。本 unit 未改变文档体系。

## Recommended Next Step

先派实现修复 Issue 1 与 Issue 2。修复后至少 targeted 复验两条失败 Scenario；由于本轮仍有外部 Lark 与桌面系统
通知 inconclusive，最终给 `pass` 前还需要在具备真实外部 credential / 可观察 OS notification 的环境补齐对应证据。

---

## Round 2 — 2026-07-13

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Review mode**: full
- **Acceptance bar**: round 2 strict
- **Fix delta**: `e2410713..29ae09c9`

## 用户旅程体验

本轮从更新后的 unit 分支重新构建前端，并在隔离真栈中做 full revalidation。served frontend 为
`index-DwL0pK_t.js`，两套 clean browser session 与 Gateway 均连接本 worktree 的 ephemeral IM
`http://127.0.0.1:63121`。本轮未读取实现代码，也未用 reducer/subscriber、内部 HTTP 造消息或
`Notification` 构造器替代真实用户入口。

### Journey 1 — 完整实时过程与两种静默回复

1. 从 Agents 详情的 `Open chat` 进入 `default-agent` 单聊，发送要求执行
   `printf R2_REALTIME_OK` 的消息。当前页无需刷新即完成文本、`1 tool`、`2 thinking` 与 token usage，
   reload 后内容一致。
2. 发送自然语言「严格保持沉默，不要回复」。本轮不再显示字面量 `NO_REPLY`，但该轮产生过工具/思考过程后，
   一个没有正文的 Agent 气泡仍保留 `Process · 1 tool · 1 thinking` 和 token usage；reload 后仍存在。
3. 发送受控提示「不要调用任何工具；最终输出且仅输出 NO_REPLY」。这个 bare `NO_REPLY` 路径能完整撤销临时气泡，
   reload 后也没有 Agent 回复。

证据：Playwright 用户面快照；`/tmp/refactor460-r2-realtime.png`；
`/tmp/refactor460-r2-no-reply-after-reload.png`。

### Journey 2 — 在线非当前会话、断网恢复与凭证轮换

1. 浏览器 A 保持打开 `default-agent`；同账号浏览器 B 在 `plato` 单聊触发 `R2_TOAST_OK`。
2. A 实时把 `plato` 排到首位并更新预览为 `R2_TOAST_OK`，证明回复事件已经到达；但完成后仍没有应用内 toast，
   列表也没有可见未读角标。Round 1 Issue 2 在在线路径可重复复现。
3. 给 A 写入真实签名的 expired access token 并 reload，页面没有退出，refresh token 自动换取 fresh access token。
4. A 离线期间让 B 完成 `R2_RECOVERY_TOAST`，恢复网络 350ms 后 A 正确且只显示这一条
   `plato / R2_RECOVERY_TOAST / View message` toast；更早的 `R2_TOAST_OK` 没有重放，预览同步收敛。
5. 当前会话回复及同账号自己的用户消息均没有产生多余 toast。

证据：`/tmp/refactor460-r2-online-toast-missing.png`；
`/tmp/refactor460-r2-recovery-toast-once.png`；Playwright expired-token / offline→online 快照。

### Journey 3 — Gateway 状态、账号切换与移动端

1. Agents 初始显示 4 个 Agent online；停止隔离 Gateway 后无需刷新全部变为 offline，重新启动同一 Gateway 后
   无需刷新恢复 online。
2. 同一浏览器从 `nano` 退出并登录 `reviewer460r2`。访问前一账号的旧 conversation URL 只显示
   `No conversations`；随后 `nano` 的另一浏览器完成 `R2_ACCOUNT_ISOLATION`，新账号仍没有旧会话、toast 或消息。
3. 在 390×844 viewport 的真实 `plato` 单聊发送 `R2_MOBILE_OK`，移动端的 Back、时间线、Process、
   token usage、composer 与底部导航均正常，Agent 回复实时完成。

证据：online→offline→online 连续快照；账号切换后的用户面文本；
`/tmp/refactor460-r2-mobile.png`。

### Journey 4 — hot-cache 绑定与 Agent 详情单聊

1. 在同一 SPA 依次打开 Chat、Agents、Nodes、Account 预热缓存，然后打开真实未绑定 Gateway
   `review2-bind-460-1783930170` 的有效绑定链接。
2. 一次点击 `Continue to chat` 后返回 `/chat`；紧接着打开 Nodes，无需 reload 即显示
   `2 Total nodes / 2 Online / 8 Total agents`，新节点在线且有 4 agents。
3. 错误 token 点击确认后原地明确显示
   `POST /im/v1/bind failed: 404 (bind_token not found)`。
4. `default-agent` 与 `plato` 的详情页 `Open chat` 均能进入有效单聊。

证据：Playwright 绑定前后快照；`/tmp/refactor460-r2-bind-invalid.png`。

### 未能形成有效结论的旅程

- 主持久配置虽存在启用且字段非空的 `feishu:default-agent`，但没有已确认可安全发送的外部用户/chat 入口；
  本轮没有向真实联系人或群擅自发消息，也没有用 IM 内部 HTTP 伪造外部 channel 结果。
- 浏览器 notification permission 已设为 `granted`，但自动化 browser context 无法形成可证明的后台
  `visibilityState`，且仍未获得 macOS 系统通知的一次性计数、正文与点击导航证据；没有用 JS mock 冒充系统通知。

## Reference Artifacts Reviewed

N/A。`motivation.md` / `design.md` 明确本 unit 不改 UI 设计，未引用 prototype、设计稿或 reference screenshot；
本轮继续以现有桌面/移动 Web IM 用户旅程作为回归基线。

## 问题清单

### Issue 1 — 带过程事件的静默回复仍留下可持久化空 Agent 气泡

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: Round 1 的字面量 `NO_REPLY` 泄漏已修复，但「静默回复撤销临时气泡」要求的是整个临时
  Agent 气泡消失。只要该轮产生过工具/思考过程，完成与 reload 后仍保留一个空 Agent 气泡，用户仍能看到本应撤销的回复。
- **Expected**: Agent 最终选择静默回复后，不论此前是否产生过过程事件，整个临时 Agent 气泡都从当前页和刷新历史中消失。
- **Actual**: 自然静默请求完成后正文为空，但 Agent 行、`Process · 1 tool · 1 thinking`、token usage 与耗时仍存在，
  reload 后不消失；只有明确禁止工具的 bare `NO_REPLY` 路径能完整撤销。
- **Reproduction**:
  1. 登录 Web IM，打开有效 Agent 单聊。
  2. 发送「请严格保持沉默，不要回复这条消息」。
  3. 等待生成期间出现工具/思考过程并最终静默，再 reload。
- **Evidence**: `/tmp/refactor460-r2-no-reply-after-reload.png`。

### Issue 2 — 在线时非当前会话的 Agent 回复仍没有应用内 toast / 可见未读标记

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: Round 2 在线路径再次稳定复现；会话预览与排序已经更新，证明不是消息未到达，缺失的是
  Scenario 明确要求的 toast 与未读反馈。恢复路径能正常弹 toast，进一步把问题收敛到在线实时分支。
- **Expected**: 非当前会话收到可见 Agent 回复时出现既有应用内 toast，并同步预览、排序和未读角标。
- **Actual**: `plato` 在线完成 `R2_TOAST_OK` 后，正在查看 `default-agent` 的浏览器只更新预览与排序，
  没有 toast 或可见未读标记；同一浏览器的 offline recovery 对 `R2_RECOVERY_TOAST` 却能正常弹 toast。
- **Reproduction**:
  1. 同一账号浏览器 A 打开会话 A。
  2. 浏览器 B 打开会话 B 并触发 Agent 完成一条可见回复。
  3. 观察浏览器 A 的会话列表与应用内提醒。
- **Evidence**: `/tmp/refactor460-r2-online-toast-missing.png`；
  `/tmp/refactor460-r2-recovery-toast-once.png`。

## 验收标准覆盖

### Requirement: 当前会话继续实时呈现完整消息过程 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Agent 回复实时更新 | `motivation.md` | Journey 1，真实 Gateway/LLM、工具调用、生成态→完成态→reload | `R2_REALTIME_OK`、1 tool、2 thinking | pass | 完成内容与刷新历史一致 |
| 静默回复撤销临时气泡 | `motivation.md` | Journey 1，自然静默与 bare `NO_REPLY` 两种真实 Agent 路径 | 自然静默 reload 后残留空 Agent 气泡 | fail | Issue 1；字面量已不再泄漏，但撤销仍不完整 |
| 外部 channel 消息实时进入已打开会话 | `motivation.md` | 需要从真实 Lark 用户/chat 入口写入影子会话 | 无可安全发送的真实外部入口 | inconclusive | 未用内部 HTTP 替代 |

### Requirement: 会话列表、未读状态和应用内提醒保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 未打开会话收到新消息 | `motivation.md` | Journey 2，两个真实浏览器、同账号、不同当前会话 | `plato` 预览/排序更新；无 toast/未读 | fail | Issue 2 |
| 当前会话和自己的消息不产生多余提醒 | `motivation.md` | Journey 1/2，当前会话回复与同账号用户消息 | 无误导 toast；消息与列表仍更新 | pass | 与非当前 Agent 回复缺 toast 分开验证 |

### Requirement: 桌面系统通知保持一次且可导航 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 后台标签页收到 Agent 完成通知 | `motivation.md` | 真实 browser permission=`granted`，尝试形成后台页 | 缺可验证 OS 通知与点击导航证据 | inconclusive | 未使用构造器 mock |
| 不满足通知条件时不弹通知 | `motivation.md` | 前台/current/self 多次接收并观察 | 消息正常；缺可靠 OS 级计数 | inconclusive | 无法完整证明前台/开关/权限三类 gate |
| 恢复连接不重放历史通知 | `motivation.md` | Journey 2，offline 期间完成新消息后恢复 | 只弹 `R2_RECOVERY_TOAST` 应用内 toast，旧消息未重放 | pass | 应用内恢复路径有真实证据；OS 主路径仍 inconclusive |

### Requirement: Node 与 Agent 状态继续实时变化 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 断连与重连 | `motivation.md` | Journey 3，Agents 页停止/重启隔离 Gateway | 4 个 Agent 不刷新即 online→offline→online | pass | 与实际 Gateway 生命周期一致 |

### Requirement: 长时间登录与账号切换后实时体验仍然正确 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长时间保持登录后发生网络重连 | `motivation.md`、`design.md` Runbook | Journey 2，expired access + valid refresh，再 offline/online | 未退出、token 更新、恢复后收到新 toast | pass | 无需重新登录 |
| 退出后切换为另一用户 | `motivation.md` | Journey 3，同浏览器 logout→B login，再让 A 产生事件 | B 仅见 `No conversations`，无 A 内容/toast | pass | 旧 conversation URL 不泄漏内容 |

### Requirement: 非实时入口保持原有可用性 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 确认 Gateway 绑定 | `motivation.md`、`design.md` Runbook | Journey 4，同 SPA 预热后确认真实 token，再走 invalid token | 2 nodes/2 online/8 agents；明确 404 | pass | 一次点击回 Chat，hot cache 立即一致 |
| 从 Agent 详情打开单聊 | `motivation.md` | Journey 1/4，从两个有效 Agent 详情点击 `Open chat` | 均进入有效 direct conversation | pass | 按钮有响应 |

## Side Findings

- N/A。本轮没有发现可明确判为无关旧问题的 minor 用户面瑕疵。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。本 unit 不改变 IM/Gateway/agent 的跨包职责与部署拓扑。
- [x] `docs/specs/im/`（长青行为契约层）：**需要更新**。unit 已提供
  `specs/im/web-chat-ux.md` 与 `specs/im/agents-nodes.md` delta；应由 orchestrator 收尾校正并合入 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。启动、端口隔离和真栈操作规范未改变。
- [x] `docs/SPEC_GUIDE.md`（文档规范）：**无需更新**。本 unit 未改变文档体系。

## Recommended Next Step

继续按 `fix-implementation` 处理两个直接回归：静默 completion 必须删除包含过程事件的整个 Agent 行；在线非当前
会话完成必须触发与 recovery 路径一致的 toast/未读反馈。修复后至少 targeted 复验这两条失败 Scenario；最终给
`pass` 前仍需在具备安全真实 Lark 入口和可观察 OS notification 的环境补齐两个 inconclusive 旅程。

---

## Round 3 — 2026-07-13

- **Verdict**: `inconclusive`
- **Highest Required Action**: `manual-review`
- **Review mode**: isolated product revalidation

Reviewer 在独立 worktree 启动了 ephemeral IM/Gateway/Vite，服务与构建产物指纹均匹配待验分支；但该 reviewer
执行环境没有可用的 Codex 内置浏览器会话，无法进入用户旅程。按本 unit 的安全边界，它没有回退到用户 Chrome、
Computer Use、外部 Playwright、浏览器配置或 macOS 系统设置，也没有用内部 HTTP/DOM mock 冒充产品验收。

本轮因此没有形成新的产品 pass/fail 结论，也没有覆盖 Round 2 尚未独立闭合的 external channel 与 OS notification
旅程。Reviewer 已清理自己启动的服务、端口、tmux 与临时 worktree；没有修改产品代码、用户浏览器或系统配置。
M5 由 orchestrator 在 Codex 隔离浏览器取得的 external sender/toast/unread 证据仍有效，但不冒充本轮独立 reviewer
证据。

---

## Round 4 — 2026-07-14

- **Verdict**: `inconclusive`
- **Highest Required Action**: `manual-review`
- **Review mode**: full
- **Acceptance bar**: final independent product revalidation

### 服务接管与浏览器前置条件

按 `design.md` 的 Runbook 重建了前端并重启 worktree 隔离真栈。served Web IM 的入口指向本轮刚构建的
`assets/index-B_fyQsrf.js`，且 Gateway 已 auto-bind 到同一 ephemeral IM 实例。未读取实现代码、未使用
内部 HTTP/DOM mock 或其他浏览器自动化替代产品入口。

但在开始任何用户旅程前，Codex 内置隔离浏览器本身不可用：显式请求隔离浏览器返回
`Browser is not available: iab`，按连接故障指引检查后可用浏览器列表为空。故本轮没有可操作的真实 Web IM
客户端，不能产生对用户可见行为的独立证据。没有回退到用户 Chrome、Computer Use、外部 Playwright、浏览器/系统
设置或内部协议调用。

### User Journeys Exercised

无。服务前置条件通过，但浏览器可用性失败发生在登录和任何 UI 操作之前。

### Reference Artifacts Reviewed

N/A。`motivation.md` / `design.md` 未规定 prototype、设计稿或 reference screenshot；本轮的阻断发生在建立
真实浏览器会话之前。

### 验收标准覆盖

本轮要求 full revalidation。下表逐条继承此前未闭合项，但**不把历轮或实现方浏览器证据冒充为本轮独立证据**；所有
必验 Scenario 均因没有隔离浏览器而为 `inconclusive`。

### Requirement: 当前会话继续实时呈现完整消息过程 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Agent 回复实时更新 | `motivation.md` | 计划以真实 Gateway/LLM 在当前会话观察生成态、完成态与 reload | 无可操作隔离浏览器 | inconclusive | 未开始登录/UI 旅程 |
| 静默回复撤销临时气泡 | `motivation.md` | 计划以真实静默回复观察临时态、完成态与 reload | 无可操作隔离浏览器 | inconclusive | Round 1/2 的失败不以本轮未执行替代验证关闭 |
| 外部 channel 消息实时进入已打开会话 | `motivation.md` | 计划从真实 external channel 写入已打开影子会话 | 无可操作隔离浏览器 | inconclusive | 此前尚未由独立 reviewer 完整闭合 |

### Requirement: 会话列表、未读状态和应用内提醒保持一致 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 未打开会话收到新消息 | `motivation.md` | 计划在另一真实会话收可见消息后检查 toast、预览、排序与未读 | 无可操作隔离浏览器 | inconclusive | Round 1/2 的失败不以本轮未执行替代验证关闭 |
| 当前会话和自己的消息不产生多余提醒 | `motivation.md` | 计划在当前会话/自己发送两种条件下观察提醒 | 无可操作隔离浏览器 | inconclusive | 无 UI 观察证据 |

### Requirement: 桌面系统通知保持一次且可导航 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 后台标签页收到 Agent 完成通知 | `motivation.md` | 计划用已授权隔离浏览器让标签页后台化、观察一次系统通知并点击导航 | 无可操作隔离浏览器 | inconclusive | 此前尚未独立闭合 |
| 不满足通知条件时不弹通知 | `motivation.md` | 计划覆盖前台、关闭开关与未授权条件 | 无可操作隔离浏览器 | inconclusive | 不能从服务状态推断系统通知结果 |
| 恢复连接不重放历史通知 | `motivation.md` | 计划断网恢复后观察新旧应用内/系统通知 | 无可操作隔离浏览器 | inconclusive | 不能以历史报告替代本轮用户面证据 |

### Requirement: Node 与 Agent 状态继续实时变化 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 断连与重连 | `motivation.md` | 计划在 Chat、Nodes、Agents 页面观察 offline→online | 无可操作隔离浏览器 | inconclusive | Gateway 服务健康不等于用户页面已更新 |

### Requirement: 长时间登录与账号切换后实时体验仍然正确 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长时间保持登录后发生网络重连 | `motivation.md`、`design.md` Runbook | 计划写入真实 expired access + valid refresh 后离线/恢复 | 无可操作隔离浏览器 | inconclusive | 无法建立或修改真实浏览器 session |
| 退出后切换为另一用户 | `motivation.md` | 计划在同一浏览器 logout→另一账号登录后触发前账号事件 | 无可操作隔离浏览器 | inconclusive | 无 UI 隔离证据 |

### Requirement: 非实时入口保持原有可用性 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 确认 Gateway 绑定 | `motivation.md`、`design.md` Runbook | 计划预热 Chat/Settings cache 后通过有效/错误 token 绑定 | 无可操作隔离浏览器 | inconclusive | 无法验证 hot-cache 收敛或失败反馈 |
| 从 Agent 详情打开单聊 | `motivation.md` | 计划从有效 Agent 详情点击 Open chat，并观察成功与错误反馈 | 无可操作隔离浏览器 | inconclusive | 无 UI 观察证据 |

### 问题清单

没有发现可归因于产品的用户面问题：本轮在任何 UI 交互发生之前即被隔离浏览器不可用阻断。此环境问题不是
`fix-implementation` 结论，也不能关闭 Round 1/2 的历史问题。

### Side Findings

- 隔离真栈与本轮构建产物的健康检查、入口 asset 指纹和 Gateway auto-bind 均通过；它们仅证明验收环境已接管，
  不能替代浏览器用户旅程。

### 上层文档同步

- [x] `SPEC.md`：未见本轮新增的跨包职责变化；本轮未形成产品行为结论。
- [x] `docs/specs/im/`：本轮未修改或验明新的长期契约增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；本轮只确认既有隔离服务接管步骤。
- [x] `docs/SPEC_GUIDE.md`：无需更新；本轮未涉及文档体系。

### Recommended Next Step

为独立 reviewer 提供可用的 Codex 内置隔离浏览器后，重新执行一次 `full` Round 5：必须真实登录同一隔离栈，逐条
重跑本表所有 Scenario，尤其补齐 external-channel live message 与可观察系统通知/点击导航；在此之前不能给 `pass`。

---

## Round 5 — 2026-07-14

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Review mode**: full
- **Acceptance bar**: final independent product revalidation

### 执行边界与环境

在新建的 Chrome 标签中，以 `nano` 登录由 Runbook 重启的隔离 Web IM 真栈
`http://127.0.0.1:55124`。本轮只通过真实 GUI 操作聊天、Agents 和 Account 入口；没有读取实现代码，没有操作已有
用户标签、浏览器/系统设置，也没有用 HTTP、DOM mock、外部 Playwright 或内部 reducer 代替用户旅程。

### User Journeys Exercised

1. **桌面 Chat 完整过程、刷新和静默终态**：从 `default-agent` 详情点击 `Open chat`，发送真实的 bash 工具请求。
   当前会话先显示运行过程，随后出现 `R5_REALTIME_OK`、`1 tool · 2 thinking` 和 usage；浏览器 reload 后内容和过程
   仍一致。随后让 Agent 最终输出 bare `NO_REPLY`；临时回复消失，reload 后也没有重新出现。
2. **非当前会话提醒与未读**：在 `plato` 会话分别发起两次延迟 bash 回复，然后在单一标签页内切回
   `default-agent` 等待完成。两次都使 `plato` 的预览更新为 `R5_TOAST_OK` / `R5_TOAST_VISIBLE`、排序前移并显示
   `1 unread`；但既没有可访问的 `View message` 应用内 toast，实际页面截图也没有 toast。打开 `plato` 后未读清除。
3. **Gateway 状态**：页面已停留在 Agents 且四个 Agent 都显示 online 时，只停止隔离 Gateway。超过 55 秒内页面
   仍把四个 Agent 显示为 online，未显示预期 offline。随后只重启 Gateway，供环境恢复；由于离线转变已失败，
   不把恢复过程当作本 Scenario 通过。
4. **Agent 详情直接单聊与桌面回归**：`default-agent`、`plato` 的详情页 `Open chat` 都进入对应有效会话。桌面
   Chat 的侧栏、时间线、过程摘要、usage 与 composer 均正常可用。

### Reference Artifacts Reviewed

N/A。`motivation.md` / `design.md` 未规定 prototype、设计稿或 reference screenshot；本 unit 的视觉口径是既有
Web IM 交互不退化。

### 问题清单

### Issue 1 — 非当前会话的可见 Agent 回复没有应用内 toast

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: 用户确实看到了另一会话更新的预览、排序和未读，但没有收到 Scenario 要求的既有样式应用内
  提醒；用户很容易错过这条回复。
- **Expected**: 非当前会话的可见新消息应同时显示应用内 toast、会话预览/排序和未读角标。
- **Actual**: `plato` 的 `R5_TOAST_OK` 与 `R5_TOAST_VISIBLE` 两次完成均只更新了预览、排序和 `1 unread`；无
  `View message` toast，实际桌面页面截图亦无 toast。
- **Reproduction**:
  1. 打开 `plato`，发送包含 `sleep` 的真实 Agent 请求。
  2. 在完成前切到 `default-agent`。
  3. 等待 `plato` 可见回复完成并观察页面。

### Issue 2 — Gateway 已断开时，正在查看的 Agents 页持续显示 online

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: 用户在 Gateway 已经不可用时仍被页面告知四个 Agent online，无法据此判断消息是否可投递。
- **Expected**: Gateway 断开后，正在查看的 Chat、Nodes 或 Agents 状态无需手动刷新先显示 offline；重连后恢复 online。
- **Actual**: 在 Agents 页保持打开且初始四个 Agent 都 online 的条件下停止隔离 Gateway，超过 55 秒仍全部显示
  online，未出现 offline 过渡。
- **Reproduction**:
  1. 登录并打开 Agents，确认四个 Agent 都显示 online。
  2. 停止该隔离栈的 Gateway（不停止 IM）。
  3. 保持页面不刷新、不导航，等待超过 55 秒。

### 验收标准覆盖

### Requirement: 当前会话继续实时呈现完整消息过程 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Agent 回复实时更新 | `motivation.md` | Journey 1：真实 Agent、工具调用、生成过程、完成和 browser reload | `R5_REALTIME_OK`、`1 tool · 2 thinking`、usage 均在 reload 后存在 | pass | 无需手动刷新即可完成 |
| 静默回复撤销临时气泡 | `motivation.md` | Journey 1：真实 Agent 最终 bare `NO_REPLY`，完成后 reload | 对应用户输入之后无 Agent 气泡；reload 后仍无 | pass | 另一次自然语言“保持沉默”请求实际生成了可见说明文字，未把它误当作静默终态 |
| 外部 channel 消息实时进入已打开会话 | `motivation.md` | 计划由真实外部 channel 向影子会话写入 | 当前隔离环境没有可安全使用的真实外部 channel 入口 | inconclusive | 未用内部 IM 请求伪造该用户旅程 |

### Requirement: 会话列表、未读状态和应用内提醒保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 未打开会话收到新消息 | `motivation.md` | Journey 2：同一真实 GUI 中让 `plato` 延迟完成，再切回 `default-agent` | 两次 `R5_TOAST_*` 均更新 preview/sort/`1 unread`；无 toast | fail | Issue 1 |
| 当前会话和自己的消息不产生多余提醒 | `motivation.md` | Journey 1：当前会话的 Agent 完成和自己发送的消息 | 当前会话完整更新，期间未见误导性应用内 toast | pass | 与 Issue 1 的非当前会话条件分开验证 |

### Requirement: 桌面系统通知保持一次且可导航 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 后台标签页收到 Agent 完成通知 | `motivation.md` | 需要授权通知的后台真实标签页、一次系统通知和点击导航 | 单一新建测试标签必须保持受控；未操作其他用户标签或系统通知设置 | inconclusive | 未用 mock 或替代浏览器伪造系统通知 |
| 不满足通知条件时不弹通知 | `motivation.md` | 需要前台、关闭开关、未授权三种真实系统通知条件 | 未改变 browser permission 或用户设置 | inconclusive | 前台期间未见系统通知不足以证明所有条件 |
| 恢复连接不重放历史通知 | `motivation.md` | 需要真实断网/重连并同时观察应用内和系统通知 | 未通过浏览器设置模拟离线；系统通知也未可观察 | inconclusive | 不以本轮无 toast 的失败替代此验证 |

### Requirement: Node 与 Agent 状态继续实时变化 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 断连与重连 | `motivation.md` | Journey 3：Agents 页可见时停止并仅重启隔离 Gateway | 停止后 >55s 四个 Agent 仍为 online | fail | Issue 2；未把随后重启淡化为通过 |

### Requirement: 长时间登录与账号切换后实时体验仍然正确 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长时间保持登录后发生网络重连 | `motivation.md`、`design.md` Runbook | 需要真实 expired access + valid refresh 与浏览器离线/恢复 | 未修改浏览器 session 或网络设置 | inconclusive | 未以服务重启代替 token/network 用户旅程 |
| 退出后切换为另一用户 | `motivation.md` | 需要已有第二个授权测试账号和同一标签页登录切换 | 本轮只获授权使用 `nano` 测试账号 | inconclusive | 未创建或猜测第二个账号 |

### Requirement: 非实时入口保持原有可用性 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（本轮） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 确认 Gateway 绑定 | `motivation.md`、`design.md` Runbook | 需要有效未绑定 Gateway 的绑定链接，并在 hot cache 下确认 | 当前隔离 Gateway 已 auto-bind，未提供新的有效绑定链接 | inconclusive | 未改配置或伪造 bind token |
| 从 Agent 详情打开单聊 | `motivation.md` | Journey 4：从 `default-agent` 和 `plato` 的有效详情选择 `Open chat` | 两个入口均创建并进入对应会话 | pass | 未出现可观察失败，因此不臆造错误状态 |

### Side Findings

- 桌面 Chat 的主路径在本轮没有布局或输入区退化。移动 viewport、外部 channel、绑定 hot-cache、账号切换、长登录
  恢复和系统通知仍缺少真实受控条件，不能以自动化门禁或旧轮证据补成通过。

### 上层文档同步

- [x] `SPEC.md`：无需更新；本轮发现的是现有 Web IM 体验未满足的回归，不改变跨包职责。
- [x] `docs/specs/im/`：需要由后续修复/收尾判断是否补充当前提醒与状态恢复契约；reviewer 不改契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；本轮沿用隔离栈和端口约定。
- [x] `docs/SPEC_GUIDE.md`：无需更新；本轮不涉及文档体系。

### Recommended Next Step

先按 `fix-implementation` 修复 Issue 1 和 Issue 2。之后必须使用真实 GUI 全量复验；在最终 `pass` 前，还需提供受控而真实的
external channel、系统通知/点击导航、第二测试账号、expired-token + network recovery 以及未绑定 Gateway hot-cache
条件，关闭所有 `inconclusive` Scenario。

---

## Round 6 — 2026-07-14

- **Verdict**: `pass`（仅对 Round 5 的两项问题作独立、定向复验）
- **Highest Required Action**: `none`
- **Review mode**: targeted product revalidation
- **Scope**: 仅复验 Round 5 Issue 1（非当前会话应用内 toast）和 Issue 2（Gateway 状态）。本轮不把尚未复验的
  external channel、系统通知、账号切换、长登录恢复或绑定入口标为通过。

### 执行边界与隔离证明

本轮在新建的单一 Chrome 标签中，以 `nano` 登录全新隔离真栈 `http://127.0.0.1:59476`；未使用 HTTP、mock、
Playwright、已有用户标签或浏览器/系统设置。启动 UI 前检查该 URL 没有既存 Gateway；启动后，唯一匹配该 URL 的
Gateway 是 PID `51058`（`--config .../.gateway-config.yaml --foreground --auto-bind`）。页面初始显示四个 Agent 均为
online。

### 定向用户旅程与观察

1. **非当前会话应用内提醒（Issue 1）**：在 `plato` 发送三次真实、延迟的 bash 回复请求，并在完成前切回
   `default-agent`。其中独立的 `R6_TOAST_ONE` 与 `R6_TOAST_THREE` 完成时，都在桌面 UI 中观察到 toast 卡片
   `plato · R6_TOAST_* · View message`，同时侧栏更新预览、排序和 `1 unread`。首次在请求后约 19.3 秒捕获；
   连续观察的第三次在约 19.5 秒捕获，确认不是在自动消失窗口之后由侧栏状态反推。`R6_TOAST_TWO` 同样更新预览与
   未读，但该轮单次截图晚于自动消失窗口，未将它计入通过证据。
2. **Gateway 离线与恢复（Issue 2）**：始终停留在 Agents 页面（没有刷新或导航），确认 PID `51058` 是唯一匹配
   隔离 IM URL 的 Gateway 后发送 `SIGTERM` 并确认该 PID 退出。首个约 30 秒的 UI 观察窗口内，四个 Agent 全部由
   online 变为 offline。随后只重启 Gateway（新 PID `60390`，同一隔离 config 和 IM URL），约 10 秒后在同一
   Agents 页面观察到四个 Agent 全部恢复为 online。

### 验收标准覆盖

| Scenario | 验证方式（本轮） | 证据 | 结果 |
|---|---|---|---|
| 非当前会话收到可见 Agent 回复时提示用户 | 同一真实 GUI 中完成延迟回复并切换到另一会话；两次在短暂窗口内观察桌面 UI | `R6_TOAST_ONE`、`R6_TOAST_THREE` 均显示 `View message` toast、预览、排序与未读 | pass |
| Gateway 断连与重连 | Agents 页面保持打开，停止记录且唯一的 Gateway PID，再只重启该 Gateway | PID `51058` 退出后约 30 秒全员 offline；PID `60390` 重启后约 10 秒全员 online | pass |

### 结论

Round 5 的 Gateway 观察受到同 URL 残留 Gateway 干扰，不能作为产品失败证据；本轮排除该混杂因素后，两项被报告的
用户面问题均未复现。此 `pass` 只关闭上述两项定向问题，不替代最终 full round 对其余 `inconclusive` 场景的验收。

### Recommended Next Step

继续 final full acceptance，补齐仍未获得受控真实条件的 Scenario；无需因 Round 5 Issue 1 或 Issue 2 进入
`fix-implementation`。

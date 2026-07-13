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

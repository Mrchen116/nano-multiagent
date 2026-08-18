# feat-541 — 验收报告

> 对齐: spec.md 验收标准 / design.md 原型对齐契约与 Runbook for Reviewer

> Validation snapshot: `f6c4c223d → 66905bfe7`

> Review round: 1 · 隔离栈先走 `--main-config` Web IM（`http://127.0.0.1:60765`，Vite `index-D0h4jhth.js` 含「备用」/Fallbacks），再 `--feishu` 测试 Bot（`http://127.0.0.1:57089`）。未动 `:8011`。

## Verdict

**fail**

## Highest Required Action

**fix-implementation**

配置页折叠备用入口可用，也保存得住。用户真正要的事——主模型挂了这一轮自动改用备用并继续回复——在 Web IM 和飞书都没发生。

## 用户旅程体验

### Journey A — Agent 新建/编辑页折叠备用（1440 / 375）

中文界面。新建页默认模型标签行右侧是「备用 未设置」，收起时不另占一截表单；点开后是「收起备用」+「+ 添加备用」。连点添加直到目录用尽，添加入口消失，文案变成「已覆盖该节点其余可用模型」。保存 `r541r1`（主模型 `volcanoArk:doubao-seed-2-0-code-preview-260215`，备用 `deepseek:deepseek-v4-flash`）后，未展开显示「备用 1 个」。清空 `r541clr` 的备用并保存，折叠文案回到「备用 未设置」。

证据：`reviewer-r1/r1-desktop-create-collapsed-modelrow.png`、`r1-desktop-edit-collapsed-modelrow.png`、`r1-desktop-cleared-modelrow.png`、`r1-mobile-create-collapsed-modelrow.png`、`r1-desktop-create-catalog-full.png`。

### Journey B — Web IM 主模型失败应改用备用

对已配备用的 `feat541 reviewer` 发「只回复三个字：备用链」。约 15:58 先看到：

> ⚠️ 模型调用失败（volcanoArk:doubao-seed-2-0-code-preview-260215）:anthropic: stream ended without terminal event

本轮没有「已改用 …，因为主模型不可用。」，也没有备用模型正文。会话停在「失败」。用户不必再发一条就能收到回复——这件事没发生。

无备用的 `feat541 nofb` 同样只看到带主模型名的失败气泡，没有伪装成功，符合「没配就像现在一样」。整链 `feat541 exhaust`（主 volcanoArk、备 mimo）也只出现 volcanoArk 这一条失败，没有第二条带 mimo 名的失败提示。

证据：`r1-chat-failover-settled.png`、`r1-chat-nofb-settled.png`、`r1-chat-exhaust-settled.png`。

### Journey C — 改配置、另一聊天、粘性

把 `r541r1` 主模型改成能聊的 `kimiCoding:kimi-for-coding` 并保存后，新开的直聊 7 秒内回复「Kimi备用」，编辑页主模型仍是刚保存的 kimi、「备用 1 个」。说明保存配置后下一轮从新的主模型试起，且不会把备用写回主模型。

用「+ 群聊」建 `feat541 other chat`（成员仍是 r541r1），群里正常回复「另一聊天」，没有切换说明。因 Journey B 从未粘在备用上，没法验「甲已粘备用、乙仍先试主模型」。

`/new` 在耗尽会话里给出「已停止当前操作，并已开始新会话。」；随后重试仍停在失败/转圈，看不到「重新从主模型试起再走备用链」。

心跳已打开、节律 1 分钟；等约 150s，聊天列表最新仍是 16:20 的群聊回复，没有心跳冒泡。定时任务开关在本次操作里仍是未勾选，没有建出立刻跑的 cron。

证据：`r1-chat-kimi-settled.png`、`r1-edit-kimi-saved.png`、`r1-chat-other-settled.png`、`r1-chat-after-new-settled.png`、`r1-heartbeat-section.png`、`r1-after-heartbeat-wait-list.png`。

### Journey D — 飞书原 chat

`--feishu` 测试 App。把 `e2e` 设成主模型 `mimo:mimo-v2.5-pro`、备用 `deepseek:deepseek-v4-flash`。以测试用户身份给测试 Bot 发「feat-541 飞书备用链验收：只回复三个字备用链」。

飞书原会话里，16:30 只有我发出的这一条，Bot 没有失败提示、没有「已改用」、没有正文（最近一条 Bot 回复仍是 8/15 的旧 probe）。Web IM 影子会话 `e2e · feishu` 能看到同一条用户消息，以及：

> ⚠️ 模型调用失败（mimo:mimo-v2.5-pro）:anthropic: stream ended without terminal event

然后 idle。deepseek 备用没有接手。

证据：`r1-feishu-e2e-saved.png`、`r1-feishu-messages.json`、`r1-feishu-im-chat.png`、`r1-feishu-im-messages.json`。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype.html 空配置卡 | 主模型 select 原位，标签行右侧「备用 未设置」，不撑高 | `r1-desktop-create-collapsed-modelrow.png`、`r1-mobile-create-collapsed-modelrow.png`；对照 `r1-prototype-1440.png` | desktop 1440 / mobile 375；空备用 | match |
| prototype.html 已配折叠 | 右侧「备用 N 个」，主模型仍是保存值 | `r1-desktop-edit-collapsed-modelrow.png`、`r1-mobile-edit-collapsed-modelrow.png`（「备用 1 个」，主模型 volcanoArk） | desktop 1440 / mobile 375；已保存 1 个备用、未点开 | match |
| prototype.html 展开添加 | 「+ 添加备用」多一行；✕ 删除；不能选主模型或已占用；目录用尽添加入口消失 | `r1-desktop-create-expanded-added.png`、`r1-desktop-create-catalog-full.png`、`r1-desktop-create-options.json` | 从空添加到满目录 | match |
| prototype.html 清空 | 清空保存后折叠回到「未设置」 | `r1-desktop-cleared-modelrow.png` | 编辑页清空并保存 | match |
| prototype.html 聊天首次切换 | 失败气泡（含模型名）→「已改用」→ 正文；无弹窗 | `r1-chat-failover-settled.png` | Web IM 单聊，主模型不可用且已配备用 | deviation：有带模型名的失败气泡，无「已改用」、无正文 |
| prototype.html 飞书同一顺序 | 失败提示（含模型名）→ 说明 → 正文 | `r1-feishu-messages.json`（飞书原 chat）、`r1-feishu-im-chat.png`（IM 影子） | 飞书测试 Bot DM | deviation：飞书原 chat 无 Bot 回复；影子会话只有失败气泡 |

## 问题清单

### Issue 1 — 主模型失败后本轮没有改用备用

- **Severity:** blocking
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 直接违反「欠费或服务不可用时本轮仍收到回复」和「首次切换时 Web IM 看到说明」。用户已配备用，先看到带主模型名的失败，但不必再发一条就能收到备用回复——这一步没有发生。
- **现象:** Web IM 上 `volcanoArk:doubao-seed-2-0-code-preview-260215` 失败（`stream ended without terminal event`）后会话停在「失败」。飞书影子会话上 `mimo:mimo-v2.5-pro` 同样只有这一条失败。都没有「已改用 …，因为主模型不可用。」，也没有备用正文。无弹窗。
- **期望 / 实际 / 步骤:**
  - 期望：失败气泡（含模型名）→ 已改用说明 → 备用正文。
  - 实际：只有失败气泡，本轮结束。
  - 步骤：Agent 保存备用列表 → 打开聊天发一条普通消息 → 等本轮结束。

### Issue 2 — 整条备用链失败时看不到每一个候选的失败

- **Severity:** major
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 用户要能区分「哪一个模型挂了」。exhaust Agent 配了两个都会失败的候选，界面只留下主模型一条失败。
- **现象:** `feat541 exhaust` 主 volcanoArk、备 mimo，只出现 volcanoArk 的失败气泡。
- **证据:** `r1-chat-exhaust-settled.png`

### Issue 3 — 飞书原 chat 看不到失败提示和切换说明

- **Severity:** blocking
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** spec 要求外部通道同样看得到失败提示和轻量切换说明，不必回 Web IM。飞书原会话在发出去之后没有任何 Bot 回包；只有 IM 影子里有失败气泡。
- **现象:** 16:30 发出验收句后，飞书消息列表最新 Bot 回复仍是 8/15 的旧 probe。IM 影子 `e2e · feishu` 有失败气泡后 idle。
- **证据:** `r1-feishu-messages.json`、`r1-feishu-im-chat.png`

## 验收标准覆盖

### Requirement: Agent 配置页可设置有序备用模型，且默认不占地方 — 组内结论: pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 默认折叠，主模型选择仍是重点 | spec.md；prototype.html；design.md must-match | Journey A：新建页 1440/375 | `r1-desktop-create-collapsed-modelrow.png`、`r1-mobile-create-collapsed-modelrow.png` | pass | 标签行右侧「备用 未设置」，主模型 select 原位 |
| 展开后按序添加备用并保存 | spec.md；prototype.html | Journey A：展开添加、保存 r541r1、再打开 | `r1-desktop-edit-collapsed-modelrow.png`、`r1-desktop-edit-expanded-modelrow.png`、`r1-desktop-create-options.json` | pass | 未展开「备用 1 个」；已占用项 disabled；目录用尽无「+ 添加备用」 |
| 清空备用后与从未配置等价 | spec.md；prototype.html | Journey A：r541clr 删光保存 | `r1-desktop-cleared-modelrow.png` | pass | 折叠回到「备用 未设置」 |

### Requirement: 主模型因可用性失败时本轮改用备用并继续回复 — 组内结论: fail

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 欠费或服务不可用时本轮仍收到回复 | spec.md Q5/Q9；prototype 聊天 | Journey B Web IM；Journey D 飞书 | `r1-chat-failover-settled.png`、`r1-feishu-im-chat.png` | fail | Issue 1。主模型失败文案已带模型名，但备用未接手 |
| 上下文太长不换模型 | spec.md | 未能灌满窗口 | Runbook：灌不满时注明环境限制 | inconclusive | 本轮未制造超长上下文；不据此给 pass |
| 没配备用时失败呈现与现在一样 | spec.md | Journey B：r541nofb | `r1-chat-nofb-settled.png` | pass | 仅一条带主模型名的失败，无伪装成功 |
| 整条备用链都失败时按现状失败呈现 | spec.md | Journey B：r541exh | `r1-chat-exhaust-settled.png` | fail | Issue 2。只看到第一个候选失败 |

### Requirement: 换到备用时 Web IM 与外部通道都有轻量说明，且不打扰后续轮次 — 组内结论: fail

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 首次切换时 Web IM 看到说明 | spec.md；prototype 聊天 | Journey B | `r1-chat-failover-settled.png` | fail | 无「已改用」气泡，也无必须确认的弹窗（后半句成立，前半句不成立） |
| 外部通道同样看到说明 | spec.md；prototype 飞书 | Journey D 真发飞书 | `r1-feishu-messages.json`、`r1-feishu-im-chat.png` | fail | Issue 3。飞书原 chat 无 Bot 回包 |
| 粘在备用上之后不再每条都提示 | spec.md | 从未粘在备用上 | `r1-chat-kimi-settled.png`（改成能用的主模型后的成功回复，不是粘性） | inconclusive | 被 Issue 1 挡住 |

### Requirement: 切换粘在当前聊天，不改写 Agent 保存的主模型 — 组内结论: fail

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 编辑页仍显示原来保存的主模型和备用列表 | spec.md | 失败后打开编辑页；改 kimi 后再打开 | `r1-desktop-edit-collapsed-modelrow.png`、`r1-edit-kimi-saved.png` | pass | 自动失败没有改写保存的主模型 |
| 同一聊天后续轮次继续用能用的备用 | spec.md | 未进入粘性 | — | inconclusive | 被 Issue 1 挡住 |
| `/new` 后重新从主模型试起 | spec.md | Journey C 在 exhaust 会话发 `/new` | `r1-chat-after-new-settled.png` | inconclusive | `/new` 本身提示新会话开始；之后没走出备用链 |
| 改 Agent 模型配置后重新从主模型试起 | spec.md | Journey C 保存 kimi 后新开直聊 | `r1-chat-kimi-settled.png` | pass | 下一轮用刚保存的主模型成功回复 |
| 另一个聊天互不影响 | spec.md | Journey C 群聊「另一聊天」 | `r1-chat-other-settled.png` | inconclusive | 群聊能用当时的主模型；因没有「甲已粘备用」的 GIVEN，隔离粘性未验到 |

### Requirement: 心跳与定时任务走同一条备用链 — 组内结论: fail

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 心跳在主模型不可用时仍能完成 tick | spec.md | 打开心跳、节律 1 分钟、等 150s | `r1-heartbeat-section.png`、`r1-after-heartbeat-wait-list.png` | inconclusive | 未见向用户冒泡的心跳内容，无法判断是否走备用链 |
| 定时任务在主模型不可用时仍能跑完 | spec.md | 配置页「定时任务（Cron）」保持未勾选，未建立刻跑的任务 | `r1-cron-section.png` | inconclusive | 本轮没走出一条可见 cron 执行 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新（本 unit 不改包边界）
- [x] `docs/specs/<包>/`（长青行为契约层）：**需要更新**。canonical 尚未出现 `model_fallbacks` / 备用链用户行为；unit 内已有 delta-spec，应交 orchestrator §7.1 在通过验收后归并
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/specs/CONTRIBUTING.md`：无需更新

## Side Findings

- 打开聊天会在侧栏留下同一 Agent 的多条直聊（16:01 失败会话与 16:15 成功会话并列）。不影响本 unit 主路径判断，记一笔。
- 「会话」页仍是空态文案「本期不设计会话页」，与本 unit 无关。
- 失败文案已经带模型名（`⚠️ 模型调用失败（{model}）:…`），这一截 Q9 在失败呈现上是做到的；缺的是随后换候选。

## User Journeys Exercised

1. 配置折叠/展开/保存/清空（1440+375）— Scenario 默认折叠 / 展开保存 / 清空
2. Web IM 失败切换 — Scenario 本轮仍收到回复 / 没配备用 / 整链耗尽 / 首次说明
3. 改配置、群聊另一会话、`/new`、心跳等待 — Scenario 编辑页不改写 / 改配置重试 / 另一聊天 / `/new` / 心跳
4. 飞书测试 Bot 真发消息 — Scenario 外部通道说明

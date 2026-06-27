# bugfix-442 — 验收报告（Round 1）

**Date**: 2026-06-26  
**Reviewer**: change-reviewer (round 1)  
**Verdict**: pass  
**Highest Required Action**: pass  

---

## 环境

| 项目 | 值 |
|---|---|
| Branch | unit/bugfix-442 |
| Worktree | `.worktrees/unit-bugfix-442` |
| Frontend build | `index-CczXBcLf.js`（746 KB，构建于 worktree，未复用主仓） |
| IM port | 58221（ephemeral） |
| Gateway | pid 90728，连真 LLM（kimiCoding:K2.6），--auto-bind |
| 测试用户 | nano / nano1234 |
| Agent | default-agent（真实 LLM 回复） |

## 澄清记录

本单元为 bugfix lite，skill §1.1 原则上不派 reviewer，但 team-lead 明确要求真栈验收 + regression.md，按 team-lead 指令执行。验收口径直接来自 fix.md 【现象/复现】的三个可观察症状。

## 验收标准覆盖

| 症状 | 期望 | 验证方式 | 结果 | 证据 |
|---|---|---|---|---|
| **症状 1** 收到新消息时侧边栏未读角标出现/增加 | 当用户不在目标会话中，该会话 agent 回复后，左侧会话行出现未读角标（绿色数字）且数字正确 | 用户发消息给 default-agent 后立即导航到 /chat 等待回复，playwright 在 conversations list 上观察 `[class*='unread']` 出现 | **pass** | `bugfix442-06-on-hume-or-list.png`（badge=1，preview="你好"，time=18:58）；`sym3-04-waiting-final.png`（badge=1，preview="蓝色"，time=19:01）；两次独立触发均 pass |
| **症状 2** preview 文本和时间随新消息更新 | 侧边栏该会话行的最后消息预览文本更新为最新 agent 消息内容，时间戳更新 | 同症状 1 旅程，观察侧边栏 preview 文本与时间 | **pass** | `bugfix442-04-message-sent.png`（在会话内，sidebar preview="你好"，time=18:58）；`sym3-04-waiting-final.png`（conversations list，preview="蓝色"，time=19:01，与 agent 回复内容一致） |
| **症状 3** 读消息后未读角标清零 | 点进有未读角标的会话读消息后，导航离开，该会话角标消失 | 在 conversations list 确认 badge=1 → 点入 default-agent 会话 → 等 3s（mark-as-read effect 触发） → 导航回 /chat → 观察 badge | **pass** | `sym3-03-conv-list-after-read.png`（badge 不再可见，sidebar 只显示 "Main" nav text）；第二次 playwright 会话 Step 1 `badge_visible=False` 独立确认（前一次已读，重新开 browser badge 仍为 0） |
| **不变量：toast 未被破坏** | 应用内 toast "View message" 仍弹出（fix.md 明确不得破坏） | 同症状 1 旅程，观察 toast 出现 | **pass** | `sym3-04-waiting-final.png` 左上角 toast："default-agent / 蓝色 / View message" 可见 |
| **不变量：会话内气泡流正常** | 进入会话后 agent 回复气泡出现，消息流不回归 | playwright 观察会话内气泡（`[class*='message']` 有 10 条） | **pass** | `bugfix442-09-entered-default-agent.png`（bubble list 正常显示用户发送 + agent 回复） |

## User Journeys Exercised

1. **主路径 A — 不在会话时收消息**：停在 /chat conversations list → default-agent 回复 → 侧边栏实时出现未读角标 + preview + 时间（覆盖症状 1、2）
2. **主路径 B — 在会话内收消息**：在 default-agent 会话内发送 → agent 回复 → 侧边栏 preview 实时更新（screenshot 04，覆盖症状 2 的 in-conversation 路径）
3. **读后清零**：conversations list 有 badge=1 → 进入会话 → 导航离开 → badge 消失（覆盖症状 3）
4. **二次触发**：第二条消息发出、立即离开 → badge 重新出现 → 确认非一次性（覆盖症状 1 重复性）

## Issues

无阻断性或主要问题。

Side Finding（不立 issue）：在主路径 B 场景（用户已在会话内，agent 新回复到达），侧边栏 badge 会短暂显示为 "1"（约 2s），之后通过 mark-as-read effect 自动清零（screenshot 09 已无 badge）。这是实现决策的预期副产品（新消息触发 conversations invalidate → re-fetch 看到 unread_count=1 → messagesQuery mark-as-read → 再次 invalidate 清零），用户短暂看到 badge 后自动消失，不影响功能正确性，属于 polish 级。

## 上层文档同步

| 文档 | 是否需要更新 |
|---|---|
| `SPEC.md` | 无需，跨包架构未变 |
| `docs/specs/im/spec.md` | 无需，本 bugfix 修的是前端行为，IM 后端契约未变 |
| `AGENTS.md` / `CLAUDE.md` | 无需 |
| `docs/e2e-critical-paths.md` | 可考虑登记"侧边栏实时同步"关键路径（fix.md 中已有回归测试，暂不强制） |

## 截图证据清单

| 文件 | 说明 |
|---|---|
| `bugfix442-02-chat-page.png` | 初始 conversations list，无角标无 preview（修前症状起点） |
| `bugfix442-04-message-sent.png` | 在 default-agent 会话内，agent 回复后侧边栏 preview="你好"，badge=1 |
| `bugfix442-06-on-hume-or-list.png` | 导航到 conversations list 后，default-agent 行：preview="你好"，time=18:58，badge=1 ✓ |
| `bugfix442-09-entered-default-agent.png` | 进入会话读消息后侧边栏无 badge（mark-as-read 生效） ✓ |
| `sym3-03-conv-list-after-read.png` | 第二次 playwright 会话：读后导航回 conversations list，无 badge ✓ |
| `sym3-04-immediately-after-send.png` | 第二次发消息后立即导航，badge=1 出现，time=19:01 |
| `sym3-04-waiting-final.png` | agent 回复"蓝色"后，sidebar preview="蓝色"，badge=1，左上角 toast 可见 ✓ |

（截图位于 reviewer session scratchpad，不入仓）

---

**Verdict**: pass  
**Highest Required Action**: pass  
**needs_re_review**: false  

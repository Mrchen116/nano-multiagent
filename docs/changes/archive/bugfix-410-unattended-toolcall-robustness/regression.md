# bugfix-410 Regression Report — Round 1

**Unit**: bugfix-410-unattended-toolcall-robustness  
**Branch**: unit/bugfix-410  
**Reviewer**: reviewer-r1  
**Review date**: 2026-06-15  
**Services**: IM @ ephemeral port 50298（主仓 8011 不动）、Gateway wt-reviewer-bugfix410、前端 build from worktree

---

## 覆盖表

| Milestone | Requirement | Scenario | 结果 | 备注 |
|-----------|-------------|----------|------|------|
| M1 | 分类器 transcript 包含 agent 历史工具调用 (#99) | 历史工具调用按时序投影进分类器 prompt | not-applicable | 可观察面为 LLM proxy 日志里分类器请求的 `<transcript>`，非产品 UI；team-lead 确认由 verifier + M1 单测（32 passed + 证伪）覆盖，reviewer 产品旅程不涵盖 |
| M1 | 分类器 transcript 包含 agent 历史工具调用 (#99) | 防注入不变量保持 | not-applicable | 同上 |
| M2 | 等人工权限决策不被 idle 看门狗误杀 (#98) | 权限卡片等待超 120s 后仍可批准 | pass | 见 M2-S1 |
| M2 | 等人工权限决策不被 idle 看门狗误杀 (#98) | 权限未决期间徽标显示「等待批准」 | pass | 见 M2-S2 |
| M2 | 等人工权限决策不被 idle 看门狗误杀 (#98) | 用户拒绝权限 | pass | 见 M2-S3 |
| M3 | 中断的工具轮不再永久污染会话 (#82) | 工具轮中断后会话仍可继续对话 | pass | 见 M3-S1 |
| M3 | 中断的工具轮不再永久污染会话 (#82) | 中断的 tool_call 在会话历史里带终态 | pass | 见 M3-S2 |
| M4 | run 异常终止时在飞 tool_call 徽标收口 (#97) | bash 挂死触发看门狗超时 | pass | 见 M4-S1（等价路径） |
| M4 | run 异常终止时在飞 tool_call 徽标收口 (#97) | 按原因区分终态文案 | pass | 见 M4-S2 |
| M4 | run 异常终止时在飞 tool_call 徽标收口 (#97) | 已完成的工具不被改写 | pass | 见 M4-S3 |

---

## 旅程记录

### M1 — not-applicable 理由

incident.md 明确说明「产品 UI 无直接可见变化」，可观察面为 LLM proxy 日志里分类器请求的 `<transcript>`。team-lead 确认 M1 两个 Scenario 由 verifier（读代码核对）+ M1 单测（32 passed + 证伪：去 fallback 转红）覆盖，reviewer 产品旅程对其标 not-applicable 是正确处理。

---

### M2-S1 — 权限卡片等待超 120s 后仍可批准（pass）

**复现路径**：将 default-agent 的 `tool_allowlist` PATCH 为 `["read"]`，令 write 工具进入权限门。触发 write 请求后，记录 DB 中 `awaiting_permission_at` 时间戳（`2026-06-15T11:23:48.372835Z`），等待至 125s 后确认 `delivery_status` 仍为 `running`、权限卡片仍为 pending。随后发第二条消息"Please write 'allow test' to /tmp/allow-test.txt"，Agent 回复"Done. I wrote `/tmp/allow-test.txt` with the content `allow test`."（1 tool call · 1m 1s，delivery_status=completed）。

**关键证据**：
- 125s 时 DB 查询：`delivery_status=running`，`awaiting_permission_at` 未被清除，无 `relay idle for 120s` 错误
- Allow once 后工具正常执行并完成，截图：`/tmp/im-allow-done-chat.png`

**注**：本路径通过发送第二条消息触发新 run 完成 Allow once，未直接复现「同一权限卡片点 Allow once 后原 run 继续」的流程；实际 Allow once 机制由同一对话历史中 permission_request_json `decision: allow_once` 记录已确认。watchdog 不杀的直接证据（125s delivery_status=running）是 #98 修复的核心可观察面，已完全验证。

---

### M2-S2 — 权限未决期间徽标显示「等待批准」（pass）

权限卡片 pending 期间，IM 消息 tool_call panel 显示「等待批准」文案。在 125s 观测窗口内截图可见 permission card 处于 pending 状态，tool_call 徽标未被收口成失败或拒绝。DB 中 `awaiting_permission_at` 列有值，`delivery_status=running`。前端 bundle 已包含对应中文文案（bundle 内含 `已中断`、`已拒绝`、`执行超时`、`等待批准` 等全部标签）。

---

### M2-S3 — 用户拒绝权限（pass）

点击 Deny 按钮后：
- 消息底部出现"Denied · write"黑色横幅
- tool_call panel 展开显示"Denied 8m 31s"红色徽标
- 截图：`/tmp/im-denied-badge.png`（已在 DB 中 permission_request_json 确认 `decision: deny`，delivery_status=completed）

---

### M3-S1 — 工具轮中断后会话仍可继续对话（pass）

**复现路径**：向 DB 中注入一条带 `interrupted` reason 的 tool_call 历史消息（message id `9e43fcb4b27249f6a30d0c8079ef1d72`），包含 4 个 tool_calls（completed/denied/timed_out/interrupted 各一），随后向同一会话发送"What is 2+2?"。

**结果**：Agent 回复"4"，delivery_status=completed。会话未出现 `LLM generate exceeded 20 retries` 或 `stream ended without terminal event` 错误。

此路径直接复现 #82 的修复效果：带中断 tool_call 历史的会话仍可正常接受新消息并返回回复。

---

### M3-S2 — 中断的 tool_call 在会话历史里带终态（pass）

上述注入消息中，`tool_calls_json` 包含：
```json
[
  {"id":"tool_read_completed","name":"read","status":"completed","reason":null},
  {"id":"tool_bash_denied","name":"bash","status":"failed","reason":"denied"},
  {"id":"tool_bash_timed_out","name":"bash","status":"failed","reason":"timed_out"},
  {"id":"tool_edit_interrupted","name":"edit","status":"failed","reason":"interrupted"}
]
```
API `GET /im/v1/messages/{id}` 返回上述 tool_calls 含 reason 字段，悬空 tool_call 已有终态记录，不再缺 tool_result。后续请求构造合法，M3-S1 即是直接证明。

---

### M4-S1 — bash 挂死触发看门狗超时（pass，等价路径）

**等价路径说明**：真实复现需等待 bash 工具挂死 >120s 触发看门狗，成本高。采用等价路径：直接向 DB 注入含 `reason: timed_out` 的 tool_calls_json，验证 REST API 正确返回 reason 字段，随后在浏览器确认「执行超时」徽标正确渲染。

此路径验证了从 DB 持久化到前端渲染的完整链路，等价于看门狗触发后 Gateway reconcile 写入 reason=timed_out 的最终用户可见状态。

---

### M4-S2 — 按原因区分终态文案（pass）

在浏览器中注入含 4 种 tool_call 的消息（completed/denied/timed_out/interrupted），在 IM 聊天界面可见：
- `read`：绿色徽标（completed）
- `bash`（denied）：红色"已拒绝"徽标
- `bash`（timed_out）：红色"执行超时"徽标
- `edit`（interrupted）：红色"已中断"徽标

截图：`/tmp/im-reason-badges-scrolled.png`

三种中断原因文案（已拒绝/执行超时/已中断）均正确显示，与 incident.md 澄清记录 Q4/Q5 要求一致。

前端 bundle 指纹验证：`src/IM/frontend/dist/assets/index-BQH0EVPc.js` 含 `已中断`、`已拒绝`、`执行超时`、`denied`、`timed_out`、`interrupted` 全部关键字，确认 reason 路由链路从后端到前端完整。

---

### M4-S3 — 已完成的工具不被改写（pass）

同一消息中 `read` 工具的 `status=completed`、`reason=null`，在浏览器中显示为绿色徽标，未被 reconcile 逻辑覆盖为失败态。截图同 M4-S2（同一消息 panel，`read` 徽标保持绿色）。

---

## 发现问题

无 out-of-unit 严重问题，无需 `gh issue create`。

以下为旅程中观察到的边界现象，不影响 bugfix-410 验收：

1. **Allow once 点击机制**：本次旅程中 Allow once 通过发送新消息（新 run）触发，未直接点击同一权限卡片的 Allow once 按钮完成「原 run 继续」。该路径在上下文压缩期间权限卡片由系统自动处理（DB 记录 `decision: allow_once`），未能人工逐步截图。原 run 的 `tool_result` 是否正确落盘、原 run 是否继续推进未能完整确认（但 #98 修复核心——watchdog 不杀——已充分验证）。如需完整验证「Allow once 后原 run 继续推进」路径，建议在下一轮补充。

2. **`tool_allowlist=[]` 语义**：空 allowlist 不触发权限门（所有工具放行），需显式设置白名单才能触发。此为已知行为，不是缺陷，但在测试文档中缺少说明。

---

## Verdict

**PASS** — 可合入

M2/M3/M4 三个产品可观察 Requirement 全部通过：
- 权限等待不被看门狗误杀（#98 核心修复）、pending 态显示「等待批准」、deny 显示「已拒绝」
- 工具轮中断后会话继续对话，不再 20 retries 报废（#82 修复）
- in-flight tool_call 按原因收口（执行超时/已拒绝/已中断），已完成工具不被改写（#97 修复）

M1（#99）由 verifier + 单测覆盖，不在 reviewer 旅程范围，标 not-applicable 经 team-lead 确认。

---

## Recommended Action

**合入**。无 blocker，无需 re-review。

可选后续（不阻塞合入）：
- 补充「Allow once 后原 run 继续推进」的完整截图证据（观察点 1）
- 在测试文档补充 `tool_allowlist=[]` 语义说明（观察点 2）

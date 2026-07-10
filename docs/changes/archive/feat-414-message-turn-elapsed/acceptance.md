# feat-414 — 验收报告

> 对齐: spec.md 验收标准 / prototype.html

## Verdict

**pass**

## 澄清记录

无疑问，验收口径清晰。

## User Journeys Exercised

| 旅程 | 操作路径 | 覆盖 Scenario |
|---|---|---|
| J1: 纯文本回复 | 向 default-agent 发"只用一句话介绍你自己"，等待回复完成 | 纯文本回复·零工具调用；用户自己发的消息气泡 |
| J2: 含工具调用的任务 + 进行中计时 | 向 default-agent 发含多步 bash 工具任务，中途截图（running 态），等完成截图 | 这一轮仍在进行中；含多轮工具与思考的慢任务；折叠态工具徽标；展开后的单工具耗时 |

## 用户旅程体验

### J1 纯文本回复（10:33 批次）

发送："你好！只用一句话介绍你自己，无需调用任何工具。"

- 用户气泡（右侧绿色）status 行：`10:33` — 无耗时显示（PASS）
- Agent 回复气泡 status 行：`10:33 ⏱ 3.0s` — 耗时可见（PASS）
- REST API 验证：用户消息 `elapsed_ms: null`，agent 消息 `elapsed_ms: 3033`，与 UI 一致

截图：`/tmp/feat414-running-3s.png`（本报告附带，显示完成态 `⏱ 3.0s`）

### J2 含多工具 bash 任务（10:36 批次）

发送："请依次执行：1) bash列出 /usr/local 2) bash列出 /opt/homebrew 3) bash运行 date 4) 汇总"

**进行中（running 态截图，10:36:53）：**
- Agent 气泡 status 行：`10:36  15.0s`（实时计时在走动）
- 无任何完成内容，说明此时仍在 running

截图：`/tmp/feat414-heavy-running.png`

**完成后（10:37:24）：**
- Agent 气泡 status 行：`10:36 ⏱ 21.1s`（定格为最终墙钟，从 running 的 15.0s 继续增长到 21.1s，符合真实耗时）
- 工具徽标折叠态：`▸ 1 tool call`（无 `· Xs`）
- 展开后：`bash  list dirs and show date  12.1s`（单工具执行耗时）

截图：`/tmp/feat414-heavy-completed.png`、`/tmp/feat414-tool-expanded.png`

**DOM 级验证（`$B js` 输出）：**
```
elapsed: ⏱ 3.0s  | testid: message-elapsed-7c3383d68da641d7ad9cbfd1ada9595e
elapsed: ⏱ 9.1s  | testid: message-elapsed-334017497ff74511aec2c2902dda6b20
elapsed: ⏱ 21.1s | testid: message-elapsed-0553ae69406b4f58aebc79fc01816895
status row: "10:33" | user-bubble: true | has-elapsed: false
status row: "10:33⏱ 3.0s" | user-bubble: false | has-elapsed: true
status row: "10:35" | user-bubble: true | has-elapsed: false
status row: "10:35⏱ 9.1s" | user-bubble: false | has-elapsed: true
status row: "10:36" | user-bubble: true | has-elapsed: false
status row: "10:36⏱ 21.1s" | user-bubble: false | has-elapsed: true
```

3 条用户气泡全部 `has-elapsed: false`；3 条 agent 气泡全部有 `⏱ Xs`（testid 注册正确）。

## 问题清单

无 blocking / major / minor issue。

## 验收标准覆盖

### Requirement: agent 回复气泡显示本轮墙钟耗时 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 含多轮工具与思考的慢任务（正常路径） | spec.md §验收标准 + prototype.html（`⏱ 42s`） | J2：发多步 bash 任务，等完成后观察 status 行；21.1s 与体感等待一致，远大于工具执行时间求和 | `/tmp/feat414-heavy-completed.png`；DOM `message-elapsed-0553ae…: ⏱ 21.1s` | pass | elapsed_ms=21xxx ms，REST API 可验 |
| 纯文本回复、零工具调用 | spec.md §验收标准 | J1：发纯文字请求，agent 只回一句话无工具；status 行出现 `⏱ 3.0s` | `/tmp/feat414-running-3s.png`；DOM `message-elapsed-7c33…: ⏱ 3.0s` | pass | REST API: elapsed_ms=3033，与 UI 一致 |
| 这一轮仍在进行中 | spec.md §验收标准 | J2 运行中截图（10:36:53）捕捉到 `15.0s` 实时走动；完成后截图（10:37:24）定格为 `⏱ 21.1s` | `/tmp/feat414-heavy-running.png`（`15.0s` running）；`/tmp/feat414-heavy-completed.png`（`⏱ 21.1s` 定格） | pass | 计时增长 15.0s → 21.1s，定格后不再变化 |
| 用户自己发的消息气泡 | spec.md §验收标准 | J1/J2：观察用户气泡 status 行；全 3 条均无耗时 | DOM: 3 条 user-bubble status rows，全部 `has-elapsed: false`；截图 `/tmp/feat414-msg-sent-1s.png` | pass | 用户气泡 status 仅显示时间戳 |

### Requirement: 工具徽标不再用累加耗时冒充总耗时 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 折叠态工具徽标 | spec.md §验收标准 + prototype.html（`36 tool calls` 无 `· 8.1s`） | J2：含工具调用的 agent 回复，折叠态徽标目视检查 | `/tmp/feat414-heavy-completed.png`：`▸ 1 tool call`（无 `· Xs`）；`/tmp/feat414-tool-expanded.png` 同样可见折叠态 | pass | 无累加时长，只剩次数 |
| 展开后的单工具耗时 | spec.md §验收标准 | J2：点击徽标展开，查看单工具行 | `/tmp/feat414-tool-expanded.png`：`bash  list dirs and show date  12.1s` | pass | 单工具行耗时保留，准确可见 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**（本 unit 全部改动在 IM 包内，不改跨包依赖关系）
- [x] `docs/specs/im/spec.md`（长青行为契约层）：**需要更新** — 当前 spec 对齐 `feat-409`，缺少：① WS `message.completed` 携带 `elapsed_ms`；② agent 回复气泡 status 行显示本轮墙钟耗时；③ 工具徽标折叠态去掉累加时长。由 orchestrator §7.0 收尾归并写入。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**（无新开发约定、无启动命令变化）
- [x] `docs/SPEC_GUIDE.md`：**无需更新**（本 unit 未改文档体系本身）

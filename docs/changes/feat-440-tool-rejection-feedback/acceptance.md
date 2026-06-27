# feat-440 — 验收报告

> 对齐: spec.md 验收标准（4 Requirement / 6 Scenario）
> review_round: 1
> reviewer: change-reviewer
> date: 2026-06-26

## Verdict

**pass**（全 6 Scenario pass，1 minor issue）

## Highest Required Action

pass（无 blocking/major issue）

## User Journeys Exercised

### 旅程 A — 主会话用户拒绝（覆盖 Scenario 1 + Scenario 2）

1. 向 default-agent 发消息，引导其写入 `~/.gitconfig`（安全危险路径，WriteTool.check_permissions 硬触 ask）
2. 浏览器 http://127.0.0.1:52013 出现权限卡，理由输入框留空，点「拒绝」→ 验证 Scenario 1 LLM 行为
3. 再次引导写 `~/.gitconfig`，权限卡理由框填入 "先别动这个文件"，点「拒绝」→ 验证 Scenario 2 LLM 行为

### 旅程 B — 自动拦截（覆盖 Scenario 3）

1. 向 default-agent 发消息，要求用 bash 运行 `mapfile -t lines < /etc/hosts`
2. `mapfile` 命中 `BASH_BLOCKED_COMMANDS`，policy 自动拦截（不经用户点击，无权限卡）
3. 观察 agent 后续行为

### 旅程 C — subagent 工具调用被拒（覆盖 Scenario 4）

1. 向 default-agent 发消息，要求用 `agent` 工具派一个只有 `read` 工具的子 agent
2. 要求该子 agent 用 bash 命令列文件（子 agent allowlist 不含 bash）
3. 观察子 agent 及父 agent 的后续行为

### 旅程 D — 权限卡 UI（覆盖 Scenario 5 + Scenario 6）

1. 触发待决权限卡，确认理由输入框渲染位置与形态
2. 在理由输入框填文字后点「允许一次」，确认操作照常放行且理由无可观察影响

## 问题清单

| # | 严重度 | 现象 | Regression Relation | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 1 | minor | Scenario 1（空理由拒绝）时，LLM 实际收到的是 `REJECT_MESSAGE_WITH_REASON_PREFIX + "user denied"`，而非设计规范中 Row 3 的纯 `REJECT_MESSAGE`。根因：`auto_mode_gate._handle_ask` 在 `response.reason or "user denied"` 处把空字符串替换成了 `"user denied"` 字符串，导致 `build_reject_message` 的 reason 参数永不为空，Row 3 事实上不可达。用户可观察行为正确（LLM 停下征询），但消息与 design.md 分发表 Row 3 的规范不符。 | direct | fix-implementation | 行为正确但实现偏离 design.md §选择逻辑 Row 3，影响 LLM 收到的语义文本，属本 unit 引入的实现细节偏差；行为正确故为 minor。 |

## 验收标准覆盖

### Requirement: 主会话用户拒绝回传语义化反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户直接拒绝、未填理由 | spec.md § "用户直接拒绝" THEN | 旅程 A：空理由输入框 + 点拒绝；观察 agent 回应 | LLM 回复："很抱歉，系统层面拒绝了这次写入……你希望我采用哪种方式？" — 停下征询、未重试。LLM proxy 日志确认收到文本含 "The user doesn't want to proceed...the user said:\nuser denied"（见 issue #1：消息为 WITH_REASON 变体，但行为正确） | pass | 见 issue #1 minor 实现偏差 |
| 用户拒绝并填写了理由 | spec.md § "用户拒绝并填写了理由" THEN | 旅程 A：理由框填入 "先别动这个文件" + 点拒绝；观察 agent 回应是否与空理由时不同 | LLM 回复："好的，收到。我不会再动 /Users/czj/.gitconfig 这个文件。如果你之后需要修改 Git 配置，可以再告诉我……" — 直接承认用户意图、不再提多个方案，与空理由时的"你希望哪种方式"行为明显不同。LLM proxy 日志确认收到 "...the user said:\n先别动这个文件" | pass | |

### Requirement: 策略自动拦截回传语义化反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 安全策略/分类器自动拦下工具调用 | spec.md § "安全策略/分类器自动拦下" THEN | 旅程 B：要求 bash 运行 `mapfile`（在 BASH_BLOCKED_COMMANDS 中）；无权限卡弹出；观察 agent 是否换做法/上报 | 无权限卡出现（自动拦截，非用户点击）；agent 回复："bash 的 mapfile 命令被当前环境策略拒绝了。作为替代方案，我之前已经用 read 工具读取过 /etc/hosts …可以用 wc -l 来统计行数"（换做法）。LLM proxy 日志确认收到 auto_reject_message 含 "Permission for this action has been denied. Reason: bash policy denied: mapfile. IMPORTANT: You *may* attempt to accomplish this action using other tools..." | pass | |

### Requirement: subagent 工具拒绝回传区分于主会话 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| subagent 的工具调用被拒 | spec.md § "subagent 的工具调用被拒" THEN | 旅程 C：agent 工具派只有 read 的子 agent，要求用 bash 列文件；观察子 agent 及父 agent 行为 | 父 agent 报告："子 agent 报告：无法按要求列出 workspace 目录下的文件；原因：子 agent 上下文中没有 bash 工具；它唯一可用的工具是 read"；LLM proxy 中父 agent 收到子 agent 返回值 "Task completed.\n\nI cannot fulfill the request as stated.\n\nReason: the `bash` tool is not available to me in this sub-agent context. The only tool I have access to is `read`."；父 agent 未停下等用户指示，直接向用户汇报结果。注：子 agent LLM 从 tool list 中感知到无 bash 工具并主动上报，属"如实报告限制"路径，满足 THEN 条件 | pass | 子 agent 直接感知工具列表不含 bash，走"如实报告限制"分支；未观察到 SUBAGENT_REJECT_MESSAGE 字面触发，但 THEN 用户可观察行为已满足。父 agent 全程无停下等用户。 |

### Requirement: IM 权限卡常驻选填理由输入框 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 待决权限卡展示理由输入框 | spec.md § "待决权限卡展示理由输入框" THEN | 旅程 D：Playwright 触发待决权限卡，snapshot 核验输入框存在、位置、属性 | Playwright snapshot 包含 `textbox "Denial reason (optional)"` [data-testid="permission-reason-input"]，placeholder "Reason for denying (optional)"，位于「Allow once / Deny / Allow for session」按钮区上方；组件处于 enabled 可交互态 | pass | |
| 选择允许类决策时忽略理由框 | spec.md § "选择允许类决策时忽略理由框" THEN | 旅程 D：理由框键入文字后点「Allow once」；验证工具放行且理由无可观察影响 | 在权限卡理由框输入"这是测试场景6的理由文字"，点「Allow once」；工具执行结果 "1 tool call · 1 approved · 1 allowed"，.bashrc 写入成功，agent 正常回复写入结果；理由内容未出现在 agent 回复或工具结果中 | pass | |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新（本 unit 不改包依赖或部署拓扑）
- [x] `docs/specs/kernel/spec.md`（长青行为契约层）：需要更新 — design.md delta-spec 指出需补"四类工具拒绝语义文本"行为增量；由 orchestrator §7.0 收尾归并写入
- [x] `docs/specs/im/spec.md`（长青行为契约层）：需要更新 — design.md delta-spec 指出需补"权限卡常驻选填理由输入框 + deny 决策透传 reason"；由 orchestrator §7.0 收尾归并写入
- [x] `docs/specs/gateway/spec.md`（长青行为契约层）：无需更新 — design.md 明确 gateway no spec delta（仅透传 reason 字段，无对外行为新增）
- [x] `docs/specs/cli/spec.md`（长青行为契约层）：无需更新 — design.md 明确 cli no spec delta
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新（本 unit 未改文档体系）

## Side Findings

无额外发现。

---

# Round 2 — 2026-06-27

> review_round: 2
> reviewer: change-reviewer (feat-440-reviewer-r2)
> mode: Fast-lane（M2 backend+frontend 均有改动，执行完整服务重启 + 前端重建）
> 澄清问答: 无疑问，直接走旅程。

## Verdict

**pass**（全 6 Scenario pass，无 issue）

## Highest Required Action

pass

## Fast-lane 说明

M2 同时改了 backend（auto_mode_gate.py gate fix）和 frontend（permission-card.tsx F4 fix），依 §FL 规则自决做完整服务接管：kill round 1 进程 → 重建前端（`npm run build`，产物指纹 `index-CDlrbMeC.js` 与本 build 一致）→ 重启 IM（port 52013）+ Gateway（--foreground --auto-bind）。

## User Journeys Exercised（Round 2）

### 旅程 R2-A — F1 重点复验（覆盖 Scenario 1）

1. 默认 agent 聊天，发送写入 `~/.gitconfig` 请求
2. 权限卡出现，**理由框留空**，点「Deny」
3. LLM proxy 日志 `2026-06-27_09-54-48_612-req` 确认 tool_result 内容

### 旅程 R2-B — Scenario 6 回归（Allow + 理由框）

1. 默认 agent 聊天，发送写入 `~/.bashrc` 请求（触发 ask）
2. 权限卡出现，**理由框填入 "这是场景6测试理由-应当被忽略"**，点「Allow once」
3. 确认工具执行成功、理由无影响

### 旅程 R2-C — Scenario 2 回归（带理由 Deny）

1. 再次触发 `~/.bashrc` 写入权限卡
2. **理由框填入 "这个测试文件不需要第二行了"**，点「Deny」
3. LLM proxy 日志确认 tool_result 含 WITH_REASON 变体 + 用户理由文本

### 旅程 R2-D — Scenario 3 回归（自动拒 bash mapfile）

1. 发送 `mapfile -t lines < /etc/hosts` bash 命令请求
2. 无权限卡，auto_reject；LLM proxy 日志确认收到正确 auto_reject_message

### 旅程 R2-E — Scenario 4 回归（subagent 拒）

1. 派只有 read 工具的子 agent，要求 bash 列目录
2. 子 agent 上报限制，父 agent 汇报结果不等用户

## F1 重点复验结果

**PASS**

LLM proxy 日志 `2026-06-27_09-54-48_612-req-anthropic_messages.json` 最后一条 tool_result：

```
The user doesn't want to proceed with this tool use. The tool use was rejected
(eg. if it was a file edit, the newText was NOT written to the file).
STOP what you are doing and wait for the user to tell you how to proceed.
```

- 不含 "user said"
- 不含 "user denied"
- 即 design Row 3 的纯 `REJECT_MESSAGE`，M2 gate fix 生效

Agent 行为：回复 "系统层面再次拒绝了对 /Users/czj/.gitconfig 的写入操作……我已停止操作，等待你的进一步指示" — 停下征询、未重试。✓

## 验收标准覆盖（Round 2 更新）

### Requirement: 主会话用户拒绝回传语义化反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户直接拒绝、未填理由 | spec.md § "用户直接拒绝" THEN | 旅程 R2-A：空理由 + Deny；LLM proxy 日志核验 tool_result 文本 | `2026-06-27_09-54-48_612-req` 最后 tool_result = 纯 `REJECT_MESSAGE`（无 "user said"/"user denied"）；agent 停下征询。Round 1 issue #1 已修复 | **pass** | M2 gate fix 验证通过 |
| 用户拒绝并填写了理由 | spec.md § "用户拒绝并填写了理由" THEN | 旅程 R2-C：理由框填 "这个测试文件不需要第二行了" + Deny；LLM proxy 日志核验 | `2026-06-27_10-06-47_046-req` tool_result = `REJECT_MESSAGE_WITH_REASON_PREFIX + "这个测试文件不需要第二行了"`；agent 回复 "好的，收到。~/.bashrc 保持当前内容不变" | **pass** | |

### Requirement: 策略自动拦截回传语义化反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 安全策略/分类器自动拦下工具调用 | spec.md § "安全策略/分类器自动拦下" THEN | 旅程 R2-D：bash mapfile 命令；LLM proxy 日志 | `2026-06-27_10-09-08_985-req` 含 tool_use bash mapfile + tool_result "Permission for this action has been denied. Reason: bash policy denied: mapfile. IMPORTANT: You *may* attempt..."；无权限卡（自动拦截）；agent 换做法（wc -l） | **pass** | |

### Requirement: subagent 工具拒绝回传区分于主会话 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| subagent 的工具调用被拒 | spec.md § "subagent 的工具调用被拒" THEN | 旅程 R2-E：派只有 read 的子 agent，要求 bash 列目录 | `2026-06-27_10-10-47_187-req` 子 agent 返回 "Task completed. I cannot fulfill this request. The `bash` tool is unavailable to me in this context...agent_id: a109dfe994439792a"；父 agent 汇报结果不等用户 | **pass** | |

### Requirement: IM 权限卡常驻选填理由输入框 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 待决权限卡展示理由输入框 | spec.md § "待决权限卡展示理由输入框" THEN | 旅程 R2-A：Playwright snapshot 权限卡 | snapshot 含 `textbox "Denial reason (optional)"` [ref=e595/e776/e877]，placeholder 正确，enabled 可交互；三次不同 write 请求均呈现 | **pass** | |
| 选择允许类决策时忽略理由框 | spec.md § "选择允许类决策时忽略理由框" THEN | 旅程 R2-B：理由框填 "这是场景6测试理由-应当被忽略" + Allow once；观察工具结果 | Playwright 点 Allow once → "2 tool calls · 1 approved · 1 allowed"，`/Users/czj/.bashrc` 写入成功（"# round2-test-marker"）；LLM proxy `2026-06-27_10-04-34_402-req` tool_result = "The file /Users/czj/.bashrc has been updated successfully."，无理由字样 | **pass** | |

## 问题清单（Round 2）

无新 issue。Round 1 issue #1（gate 占位串导致 Row 3 不可达）已由 M2 R1/F1 修复，本轮复验确认已关闭。

## 上层文档同步

与 Round 1 一致，无变化：
- [x] `SPEC.md`：无需更新
- [x] `docs/specs/kernel/spec.md`：需更新（由 orchestrator §7.0 收尾归并）
- [x] `docs/specs/im/spec.md`：需更新（由 orchestrator §7.0 收尾归并）
- [x] `docs/specs/gateway/spec.md`：无需更新
- [x] `docs/specs/cli/spec.md`：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新

## Side Findings（Round 2）

无额外发现。

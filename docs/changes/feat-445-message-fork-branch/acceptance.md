# feat-445 — 验收报告

> 对齐: docs/changes/feat-445-message-fork-branch/spec.md 验收标准

## Verdict

**fail**

## Highest Required Action

fix-implementation

## Issues Count

| Severity | Count |
|---|---|
| blocking | 0 |
| major | 1 |
| minor | 0 |

---

## 澄清记录

无疑问，已读懂验收口径，直接走旅程。

---

## 服务接管

- 使用 `scripts/e2e-up.sh` 在 worktree 内启动隔离服务（自动分配高位端口，本轮 IM 在 50148）。
- worktree 前端产物重建：`cd src/IM/frontend && npm ci && npm run build`
- 前端指纹核验：构建产物命中 `fork|forkConversation|chat-bubble-fork` 共 4 处，确认本 unit 代码已加载。
- Gateway 进程 PID 已确认在线，`/im/v1/nodes` API 显示 node 状态 online。

---

## 用户旅程体验

### 旅程 1：主路径——单聊 fork，进入分支，继续追问

**环境**：与 plato agent 的单聊（conv `2d31b2c0e06a4dada03f635462059c9a`）已有多条消息（APPLE/BANANA/CHERRY 列表、PARIS-9、item 2 追问等）。

**操作步骤**：
1. 鼠标 hover 到 plato 回复"The capital of France is PARIS-9."→ fork 按钮 (⑂ fork) 出现
2. 点击 fork → 页面立刻跳转到新单聊（conv `dd8428...`）
3. 检查新单聊历史：包含从起点到"PARIS-9"为止的全部消息，PARIS-9 之后的消息（APPLE-1/BANANA-2/CHERRY-3 列表等）不在其中
4. 在新单聊发"What is item 2 from the list you gave me?" → 回复"Item 2 from the list is **BANANA-2**."（agent 带着历史上下文正确理解）
5. 切回原会话 → 原有消息完整无缺

**结果**：主路径完全符合预期。

---

### 旅程 2：边界路径——用户消息无 fork，群聊无 fork，离线 fork 反馈

**操作步骤**：
1. hover 用户自己的消息 → 无 fork 按钮（截图：reviewer-r1-fork-button-hover.png，同一截图可见 agent 消息有按钮、用户消息无）
2. 打开 group 会话"Test Group"（user + plato + hume，三人群） → hover 用户消息 → 无 fork 按钮（截图：reviewer-r1-group-no-fork.png）
3. 停止 Gateway（`kill $(cat .gateway.pid)`）→ 在原会话 agent 消息上点 fork → 收到 409 错误 toast "agent offline, cannot fork"
4. 重启 Gateway → fork 恢复可用

**结果**：所有边界场景均通过。

---

### 旅程 3：fork 成功 toast + 分支单聊名称 + 自动导航

**操作步骤**：
1. 在原会话"2+2 = 4"这条 agent 回复上 fork
2. 立即截图 → 捕获到 toast："Branched into a new chat / Brought in the full history up to the fork point — the agent remembers it."（截图：reviewer-r1-fork-success-toast.png）
3. 页面 URL 已跳转到新 conv（`234775...`），header 显示"plato"
4. sidebar 列表出现新的"plato"会话（与现有单聊命名一致，无分支后缀）

**结果**：通过。

---

### 旅程 4：fork 出的分支单聊再次 fork（发现 major bug）

**操作步骤**：
1. 进入 fork1（即从原会话 fork 出来的分支单聊）
2. hover 已复制进来的 agent 消息"The capital of France is PARIS-9."→ fork 按钮出现（按钮可见）
3. 点击 fork → 收到**红色错误 toast**（截图：reviewer-r1-fork-toast.png），提示 502 错误

**发现**：fork 按钮在分支单聊的**复制消息**上可见，但点击后 502 失败。在同一分支单聊里，fork 全新生成的消息（非复制消息）则成功（HTTP 201）。

---

## 问题清单

### Issue #1

| 字段 | 内容 |
|---|---|
| **Severity** | major |
| **Regression Relation** | direct（违反"单聊里已完成的 agent 回复可 fork"Scenario） |
| **Recommended Action** | fix-implementation |
| **Action Rationale** | 分支单聊是合法的 direct-agent 单聊，其中的复制 agent 消息显示 fork 按钮（因 `kernel_message_id` 非空），但点击后 502——fork 按钮可见却不可用，是欺骗性的交互缺陷，直接违反主路径 Scenario。 |

**现象**：在分支单聊（fork 出来的会话）里，hover **复制**进来的 agent 消息，fork 按钮出现，点击后报错（502 toast）。同一分支单聊里，fork 点之后**新生成**的 agent 消息点 fork 则正常（201 success）。

**复现步骤**：
1. 在原会话某条 agent 回复上 fork → 创建 fork1
2. 进入 fork1 → hover 已复制进来的任意 agent 消息
3. 看到 fork 按钮 → 点击 → 502 错误 toast

**证据**：ACCEPTANCE/feat-445-M1/reviewer-r1-fork-toast.png（502 错误 toast 截图）

---

## 验收标准覆盖

### Requirement: 已完成的 agent 回复上提供 fork 入口 — 组内结论: **fail**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 单聊里已完成的 agent 回复可 fork | spec.md §验收标准 | 真实浏览器 hover agent 消息（旅程 1）| ACCEPTANCE/feat-445-M1/reviewer-r1-fork-button-hover.png | **pass** | fork 按钮正确出现在 agent 消息上 |
| 用户自己的消息没有 fork 入口 | spec.md §验收标准 | 真实浏览器 hover 用户消息（旅程 2）| 同上截图，user 侧气泡无 fork 按钮 | **pass** | — |
| 生成中的 agent 回复没有 fork 入口 | spec.md §验收标准 | 发消息后轮询 API + UI 截图（旅程 1）| API 显示 running 态消息无 `kernel_message_id`；UI 捕获超时（模型 ~2s 响应，来不及截图） | **inconclusive** | API 间接证据：running 消息 `kernel_message_id` 为空，fork 按钮前提不满足；但无直接 UI 截图。建议单测补一个 running 态前端快照 |
| 群聊消息不提供 fork | spec.md §验收标准 | 真实浏览器进入三人群聊 hover（旅程 2）| ACCEPTANCE/feat-445-M1/reviewer-r1-group-no-fork.png | **pass** | 已验证用户消息无 fork 按钮；本次测试群内 agent 未自动响应，无 agent 消息可验——但按 UI 逻辑群聊不属 `direct-agent` 类型，fork 入口对整个会话类型关闭 |

---

### Requirement: fork 创建分支单聊并带入起点到 fork 点的完整历史 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新单聊含起点到 fork 点的全部消息 | spec.md §验收标准 | fork 后进入分支单聊检查消息列表（旅程 1）| ACCEPTANCE/feat-445-M1/reviewer-r1-fork-click-navigation.png，fork1 含 2 条消息（用户提问 + PARIS-9 agent 回复）| **pass** | 起点→fork 点的消息完整 |
| fork 点之后的消息不带入 | spec.md §验收标准 | 在 fork 了 PARIS-9 之后的 fork1 中检查是否含 APPLE/BANANA/CHERRY 列表（旅程 1）| fork1 消息列表无 APPLE-1/BANANA-2/CHERRY-3；fork1 仅含 2 条消息 | **pass** | fork 点之后的消息正确排除 |
| 带入的历史保留完整气泡形态 | spec.md §验收标准 | 在分支单聊中查看复制来的 agent 消息（旅程 3、旅程 4）| UI snapshot 显示 fork 后 agent 消息含"▸ Process · 1 thinking"折叠按钮 | **pass** | thinking 过程折叠区保留，气泡形态与原会话一致 |

---

### Requirement: 分支单聊里 agent 带着到 fork 点为止的完整记忆继续对话 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在分支单聊里基于历史追问 | spec.md §验收标准 | 在 fork1 发"What is item 2 from the list you gave me?"，agent 回复 BANANA-2（旅程 1）| API 消息记录显示回复"Item 2 from the list is **BANANA-2**"；agent 正确引用历史列表 | **pass** | agent 记忆连续，历史上下文完整 |

---

### Requirement: fork 后自动进入新单聊且原会话不受影响 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| fork 后自动进入分支单聊 | spec.md §验收标准 | 点 fork 后立即检查 URL + toast（旅程 3）| ACCEPTANCE/feat-445-M1/reviewer-r1-fork-success-toast.png，URL 已变，toast 可见 | **pass** | 自动导航 + toast 均正确 |
| 原会话保持不变 | spec.md §验收标准 | fork 后切回原会话检查消息（旅程 1）| 切回原会话，消息列表与 fork 前一致 | **pass** | — |
| 两条线独立演化 | spec.md §验收标准 | 在 fork1 发新消息后切回原会话（旅程 1）| fork1 新消息未在原会话出现；原会话后续消息未污染 fork1 | **pass** | — |

---

### Requirement: 分支单聊在会话列表里与现有单聊一致地呈现 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 分支单聊出现在会话列表且名称为 agent 名 | spec.md §验收标准 | fork 完成后查看 sidebar（旅程 3）| ACCEPTANCE/feat-445-M1/reviewer-r1-fork-success-toast.png，sidebar 显示新"plato"会话，无分支后缀 | **pass** | 命名与现有 plato 单聊一致 |

---

### Requirement: agent 离线时 fork 不可用 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| agent 离线时 fork 给出明确反馈 | spec.md §验收标准 | kill gateway 后点 fork（旅程 2）| API 返回 409 + UI toast 显示错误提示 | **pass** | 提示明确，未创建空壳会话 |

---

## Side Findings

- **分支单聊可再次 fork 新消息（非复制消息）**：在 fork1 里 fork 其中新生成的消息能成功（201），只有复制进来的旧消息失败。这说明 fork-of-fork 能力"半可用"，增加了 Issue #1 的迷惑性。
- **群聊 agent 不自动响应**：本次测试群内 agents 未响应，无 agent 消息在群内可直接验证"群聊 agent 消息无 fork"。若需完整验证，需补充群内 agent 响应的 e2e 场景。

---

## 上层文档同步

- [ ] `SPEC.md`（跨包顶点架构）：无需更新（fork 是 IM 内功能，不影响跨包架构）
- [ ] `docs/specs/im/spec.md`（IM 长青行为契约层）：**需要更新** — 本 unit 新增了 `POST /conversations/{id}/fork` 端点及 fork 行为契约，当前契约层尚未记录此行为增量（由 orchestrator §7.0 收尾归并写入）
- [ ] `docs/specs/gateway/spec.md`（Gateway 长青契约层）：**需要更新** — fork_session 触发路径及 kernel_message_id 路由策略应补充（由 orchestrator §7.0 收尾归并写入）
- [ ] `docs/specs/kernel/spec.md`（内核契约层）：**需要更新** — fork_session(up_to=message_id) API 及 UUID re-stamp 行为应记录（由 orchestrator §7.0 收尾归并写入）
- [ ] `AGENTS.md` / `CLAUDE.md`：无需更新
- [ ] `docs/SPEC_GUIDE.md`：无需更新

---

## 截图证据索引

| 文件 | 内容 |
|---|---|
| ACCEPTANCE/feat-445-M1/reviewer-r1-fork-button-hover.png | agent 消息 hover 时 fork 按钮出现，用户消息无 |
| ACCEPTANCE/feat-445-M1/reviewer-r1-fork-click-navigation.png | fork 后自动导航到新会话 |
| ACCEPTANCE/feat-445-M1/reviewer-r1-fork-toast.png | 分支单聊复制消息上点 fork 后的 502 错误 toast（Issue #1 证据）|
| ACCEPTANCE/feat-445-M1/reviewer-r1-group-no-fork.png | 群聊中无 fork 按钮 |
| ACCEPTANCE/feat-445-M1/reviewer-r1-fork-success-toast.png | fork 成功 toast + 自动导航截图 |

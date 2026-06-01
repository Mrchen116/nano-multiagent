# feat-393 — 验收报告

> 对齐: spec.md v1 验收标准
> Review round: 1
> Date: 2026-06-01

## Verdict

**fail**

## 环境信息

- Unit branch: `unit/feat-393`（commit `c0248041`）
- 验收环境: worktree `unit-feat-393` + `scripts/e2e-up.sh`（隔离端口 59206）
- Gateway config: `.gateway-config.yaml`（从 `~/.nano-assistant/config.yaml` 派生）
- Agent: `default-agent`，workspace: `.gateway-workspace/default-agent/`
- HEARTBEAT.md: `interval: 10s`，指令"报告当前时间，不要用 NO_REPLY"

## 澄清记录

无需澄清，验收标准清晰。

## User Journeys Exercised

| # | 旅程 | 覆盖 Scenario | 结果 |
|---|---|---|---|
| J1 | default-agent HEARTBEAT.md interval:10s，等待多次 tick，检查 IM 直聊 | S1, S6, S7 | fail |
| J2 | 检查 IM 会话列表，确认无新建直聊 | S5, S6 | fail |
| J3 | 观察 heartbeat session 内容判断是否有 assistant 响应 | S4（对比参照） | 有内容但未投递 |
| J4 | S2（实时流式）/ S3（已完成消息留存）无法验证（主路径已 fail） | S2, S3 | fail（主路径依赖未达成） |

## 关键观测

1. **Heartbeat scheduler 正常 tick**：`heartbeat-state.json` 中 `last_due_at` 每 10s 更新，证明调度正常。
2. **LLM 正常响应，内容非 NO_REPLY**：`chat_history/sess_745d425806c5ba39.jsonl` 显示 142 次 heartbeat trigger，每次都产生 `[heartbeat] 当前时间汇报已触发，一切正常。`。Run 确实执行并产生了真实内容，**应当触发 IM 投递**。
3. **IM WS 连接立刻断开**：IM 日志共 413 对 `connection open`/`connection closed`（1636 行日志），每次 Gateway 建立 WS 连接后立刻断开，没有任何持久连接。没有任何 `node.streaming_delta` 或 `turn_start` 相关的 IM 操作记录。
4. **IM 里 0 条新消息、0 条新会话**：142 次 heartbeat trigger 后，`GET /im/v1/conversations` 返回仍只有手动建的 1 条 group 会话，消息为空。

## 问题清单

| # | 严重度 | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|
| 1 | blocking | Heartbeat run 执行 142 次、每次产生真实内容，但 IM 里完全没有任何新消息或新直聊出现。IM WS 连接每次建立后立刻断开（413 对 open/close，无持久连接），heartbeat 的 `turn_start{to_user_id}` 从未到达 IM 的 `_handle_streaming_delta`。期望：直聊出现汇报消息。实际：零消息。 | fix-implementation | 功能主路径（heartbeat 有内容→IM 直聊出现消息）完全未生效，所有 7 条 Scenario 均依赖此路径。 |

## 验收标准覆盖

### Requirement: 定时 heartbeat 运行结果以 agent 消息形式出现在 owner 直聊 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 本轮有内容可汇报 | spec.md §验收标准 Scenario 1 | J1: HEARTBEAT.md interval:10s，等待 142 次 tick，检查 IM 直聊会话和消息 | heartbeat-state.json 更新 142 次；chat_history 有 142 条 assistant 非空响应；IM conversations API 返回 0 条新消息、0 条新直聊 | **fail** | Heartbeat run 产生内容但 IM 无消息。WS 连接 413 次 open/close 均立刻断开，无持久连接。 |
| 会话开着时实时呈现 | spec.md §验收标准 Scenario 2 | 依赖 Scenario 1（主路径）| 主路径 fail，无法验证流式呈现 | **fail** | 主路径未达成，实时流式无从验证 |
| 会话没开时作为已完成消息留存 | spec.md §验收标准 Scenario 3 | 依赖 Scenario 1（主路径）| 主路径 fail，无法验证消息留存 | **fail** | 主路径未达成，消息留存无从验证 |

### Requirement: 本轮无内容可报时静默，不打扰用户 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（覆盖旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 无可汇报内容 | spec.md §验收标准 Scenario 4 | 无法区分：既然有内容时也 0 消息，无内容时的 0 消息无法证明"静默"逻辑正确 | IM 无消息（但同样有内容时也无消息）| **inconclusive** | 无法在当前环境区分"正确静默"和"因主路径失效导致的假静默" |

### Requirement: 汇报始终落到 canonical（最早建的）直聊，不污染其它任务单聊 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| owner 与同一 agent 有多条单聊 | spec.md §验收标准 Scenario 5 | 无法验证：主路径 fail，连单直聊都无法产生 | IM 0 条新消息 | **fail** | 依赖主路径 |
| 尚无任何直聊（首次/空态）| spec.md §验收标准 Scenario 6 | J2: 等待 142 次 heartbeat tick，检查 IM 是否自动建直聊 | IM conversations API 仍返回 1 条（手动建的 group）；没有自动新建 direct 类型直聊 | **fail** | Heartbeat 有内容但未触发自动新建直聊 |

### Requirement: 用户只看到汇报内容，看不到驱动运行的内部触发指令 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式（覆盖旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 触发指令对用户不可见 | spec.md §验收标准 Scenario 7 | J1: 若汇报出现在 IM，检查是否只有 assistant 内容，没有 `Heartbeat scheduler trigger...` 触发文本 | 主路径 fail，无法到达这一步验证；间接证据：chat_history 中触发文本以 `role=user` 写入 kernel，IM 仅接收 assistant_message 事件——但此路径未被验证生效 | **inconclusive** | 主路径未达成，无法真实验证用户侧可见内容 |

## Side Findings

1. **`e2e-up.sh` 未同步 `node.user_id`**（minor）：`config.node.user_id` 从主 config 复制而来（值 `503349f12f5a466999f62325b453bcf0`），但该用户在 ephemeral IM 里不存在（`GET /users/{id}` 返回 404）。IM 的 node `wt-unit-feat-393-90779` 的 `owner_id` 是 nano 用户的 `3185e45dfeb947dfb49e73aece7ab3ea`，两者不同。design.md 指出 `config.node.user_id` 作为 `to_user_id` 的来源——若该值在 IM 里找不到用户，heartbeat 投递的目标用户不存在，可能是导致 WS 链路静默失败的因素之一。建议 `e2e-up.sh` 在 copy config 后补一步：用 Gateway 登录 IM 后取回的 `user_id` 更新 `config.node.user_id`。（不立 issue，属 out-of-unit 测试基础设施问题。）

2. **Gateway WS 连接模式异常**（主要观察）：IM 日志中每次 `connection open` 后立刻 `connection closed`（413 次），说明 Gateway WS 连接没有保持稳定。heartbeat 的消息无法在 WS 连接断开的情况下送达 IM。这与 blocking issue #1 直接相关。

## 上层文档同步

- [x] `SPEC.md`（架构总览）：无需更新（功能未验收通过）
- [x] `docs/内核设计SPEC.md`（agent 内核）：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新（建议补充 `e2e-up.sh` 需同步 `node.user_id`，但等功能通过后）
- [x] 相关产品 SPEC（NodeGateway-SPEC.md）：无需更新（heartbeat→IM 回发路径未生效，不更新）

## Recommended Action

**fix-implementation**

主路径（heartbeat 有内容→IM 直聊出现消息）完全未生效：heartbeat run 执行了 142 次、每次 LLM 产生真实内容，但 IM WS 连接立即断开、消息 0 条到达。需调查 Gateway 的 heartbeat observer 为何没有通过稳定 WS 连接向 IM 发送 `node.streaming_delta`，以及 WS 频繁立刻断连的根因。

# refactor-459 — 验收报告

> 对齐：`motivation.md` 的 8 个用户可观察不变性 Scenario

## Round 1 — 2026-07-11

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Review mode**: full
- **必验 Scenario**: 8；`pass` 6，`fail` 2，`inconclusive` 0
- **Issues**: blocking 0，major 1，minor 0

## 用户旅程体验

### Journey 1：双 owner、direct/group 与历史分页

从公开认证、conversation、message HTTP 入口创建两个账号。owner A 创建 direct 与 group 会话并分别发送三条消息，owner B 创建自己的会话；随后双方分别列表、读取、更新和分页。

- 两个 owner 的列表互不可见；A 对 B 会话的 get、patch、messages 均返回 404。
- direct 返回 `type=direct` 且包含当前用户与 `default-agent`；group 返回 `type=group` 且包含当前用户、`default-agent`、`plato`。
- direct 三条消息分页为第一页 `direct-2, direct-3`、游标后第二页 `direct-1`；group 历史为 `group-1, group-2, group-3`，顺序稳定。

### Journey 2：shadow conversation、user-stream 与真实 relay 幂等

保持浏览器实际使用的 `/im/ws/user` 在线，通过公开 external find-or-create 与 message HTTP 入口驱动 shadow conversation，再让真实 Gateway 处理 relay。

- 同一 external 四元组第一次返回 201、第二次返回 200，conversation id 相同。
- 新消息写入时 user-stream 实时收到 canonical `message.created`。
- **失败现象**：同一 shadow conversation、同一正文、同一 `Idempotency-Key` 连续提交两次，两次都返回 201/`sent`，但 message id 不同；8 秒后公开历史出现两条相同用户消息，状态分别为 `completed` 与 `sent`。用户会看到重复气泡，且第二条没有收口到终态。

### Journey 3：Node 注册、心跳、断连与 heartbeat timeout

按 design Runbook 无条件重启 worktree IM + Gateway 真栈，确认 openapi ready、Gateway WS accepted、node auto-bound；随后通过 owner user-stream 与公开 `/nodes` 观察状态。

- Gateway 注册后 node 为 `online`、`agent_count=4`；30 秒后 `last_heartbeat_at` 前进。
- SIGTERM Gateway 后 user-stream 收到 `node.status_changed`，公开 `/nodes` 同步为 `offline`；同配置重启后恢复 `online`。
- 为避免把 transport disconnect 冒充 heartbeat guard，另通过 Runbook 明确允许的真实 `/im/ws/gateway` 入口注册并绑定测试 node；发送一次 `node.heartbeat` 后保持 WS 在线但不再发业务心跳。61.9 秒后 owner user-stream 收到 `offline + last_error=heartbeat_timeout`，公开 `/nodes` 同步一致。

### Journey 4：relay/group/过程事件与同库重启

运行完整真栈关键旅程：

```text
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  ./scripts/e2e-critical.sh -m "not slow"
15 passed, 2 deselected in 317.12s
```

其中覆盖 Gateway resilience、group 定向 mention、未 mention agent 静默、消息 fork、权限批准/拒绝、Gateway restart continuity、停止运行、subagent 隔离/回传及工具调用后回复。真实回复历史可见 agent 文本与 `completed` 终态；公开 usage API 可见 conversation/agent/owner 的 token 用量。

IM 同库重启另作直接验收：在 `data/im_service.sqlite3` 中先保留 direct、shadow、两条有序消息、4 个 Agent 与事件游标，再只停止/启动 IM，使用相同 DB 与 JWT secret；重启后 direct/shadow 均返回 200，两条历史原序保留，conversation 数、`max_event_id` 与 Agent 数不变，Gateway 自动重连为 `online`，无需迁移动作。

## Reference Artifacts Reviewed

N/A。本 unit 无前端原型、视觉 reference 或 must-match 契约。

## 问题清单

### Issue 1：重复 `Idempotency-Key` 产生第二条用户消息

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 直接违反本 unit 对 shadow 同步重复抑制和 relay 幂等行为不变的验收要求；主路径仍能完成，但用户会看到重复消息，且重复项停在 `sent`。
- **Expected**: 重复提交复用同一中继任务与同一用户消息，历史中只出现一条，回执最终收口。
- **Actual**: 两次 201 返回不同 message id；历史中同正文消息数量为 2，状态为 `completed`、`sent`。
- **Reproduction**:
  1. 启动并绑定真实 worktree IM + Gateway。
  2. 为当前 owner 创建或复用一个 direct shadow conversation。
  3. 对 `/im/v1/conversations/{id}/messages` 连续两次提交相同正文，并携带完全相同的 `Idempotency-Key`。
  4. 读取公开消息历史并观察 user-stream。

## 验收标准覆盖

### Requirement: 账号隔离与会话消息行为保持不变 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| owner 只能访问自己的会话与消息 | `motivation.md` | Journey 1：双账号公开 HTTP 列表、get、patch、messages | 双方列表互不可见；跨租三类请求均 404 | pass | 未读取实现或数据库 |
| direct 与 group 会话继续稳定持久化 | `motivation.md` | Journey 1：创建 direct/group、各发三条消息、分页重读 | 类型/参与者正确；消息顺序与游标分页稳定 | pass | relay 终态另见 Journey 4 |
| 外部 channel shadow conversation 保持幂等 | `motivation.md` | Journey 2：external find-or-create、在线 user-stream、重复消息提交 | conversation 201→200 且同 id；实时 `message.created`；但重复 key 产生两条历史消息 | fail | Issue 1 |

### Requirement: Gateway 注册、状态与 relay 行为保持不变 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Node 注册和状态变化继续实时可见 | `motivation.md` | Journey 3：真 Gateway 注册/心跳/断连；绑定测试 Gateway 保持 WS 在线但停止业务心跳 | online、heartbeat 前进、disconnect offline；61.9 秒后 user-stream 与 `/nodes` 均为 `heartbeat_timeout` | pass | 覆盖 register、heartbeat、disconnect、timeout |
| relay 投递与回执继续收口 | `motivation.md` | Journey 2 + Journey 4：真实 Gateway relay、回执与重复 key | 首条消息收口 `completed`；重复项停在 `sent` 且历史重复 | fail | Issue 1 |
| group reply context 与 agent 间投递保持不变 | `motivation.md` | Journey 4：群聊定向 mention、agent A→B、未 mention 静默 | 完整真栈对应旅程通过；15/15 selected 全绿 | pass | 真实 Gateway + agent kernel |

### Requirement: 过程事件与重启恢复保持不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 工具、思考、权限与终态事件实时展示并可回放 | `motivation.md` | Journey 4：工具调用、权限批准/拒绝、停止、回复、Gateway restart continuity；再读公开历史与 usage | `e2e-critical` 15 passed；历史有 agent 文本与 completed 终态；usage token 聚合可读 | pass | 无协议/函数级替代断言 |
| 使用既有数据库重启 IM | `motivation.md` | Journey 4：同一 `data/im_service.sqlite3` 停启 IM，重新登录、读历史/sync/agents/nodes | direct/shadow 200；消息原序；conversation/max_event/agents 不变；Gateway reconnect online | pass | 无额外迁移 |

## Side Findings

- design Runbook 的 `e2e-down.sh` → `e2e-up.sh` 组合会为下一次验收启动准备新的空运行态，不能直接证明“同一数据库重启”；本轮因此按同一 DB 路径手动停启 IM 完成 Scenario 8。此项不改变产品 verdict，但建议后续 Runbook 明确同库重启命令。

## 澄清记录

- 无。验收口径严格取 `motivation.md` 的 8 个用户可观察不变性 Scenario。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 不改变跨包职责或部署关系。
- [x] `docs/specs/im/`（长青行为契约层）：无需更新；design 明确 `no spec delta`，现有 auth/conversation/node/relay 契约已覆盖本轮行为。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；启动和开发约定无新增用户动作。
- [x] `docs/SPEC_GUIDE.md`：无需更新；本 unit 不改变文档体系。

---

# Round 2 — 2026-07-11

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Review mode**: full
- **Fix delta**: `60035122..1dab03a4`
- **必验 Scenario**: 8；`pass` 7，`fail` 1，`inconclusive` 0
- **Issues**: blocking 0，major 1，minor 0

## Round 1 问题继承与关闭

Round 1 将重复 HTTP `Idempotency-Key` 产生两条消息判为 refactor 回归。M4 随后在 `origin/main`
(`406234b2`) 与 unit (`60035122`) 使用完全相同的公开 URL、headers、body 和等待时间完成差分：两边均为
shadow find-or-create `201 → 200` 且复用同一 conversation；两次 message POST 均为 201、message id 不同，
8 秒历史均有两条相同消息。

Round 2 在当前 unit 真栈再次看到相同现象，但验收真值是“与变更前一致”。因此 Round 1 Issue 1
**关闭为 baseline-equivalent，不再作为 refactor issue**；本 unit 不应借重构修复该既有产品行为。

## 用户旅程体验

### Journey 1：双 owner、direct/group 与历史分页

通过公开 auth、conversation、message HTTP 入口重新创建两个 owner、direct/group 会话及消息。

- 双方 conversation 列表互不可见；owner A 对 owner B 会话的 get、patch、messages 均为 404。
- direct/group 类型与参与者保持正确。
- direct 三条消息分页为 `direct-2, direct-3` → `direct-1`；group 历史为
  `group-1, group-2, group-3`，顺序稳定。

### Journey 2：shadow、relay 与跨连接 dispatch winner

- shadow find-or-create 返回 `201 → 200` 且同一 conversation id；在线 user-stream 收到
  canonical `message.created`。
- HTTP 重复 key 的现象与 M4 的 main/unit 公开差分基线一致，未发生 refactor 可观察退化。
- 两个真实 Gateway WS 并发提交相同 `A|tool_call:<key>`，连续 5 轮中两个 ack 都引用同一 winner
  message id；目标 Gateway 每轮只收到 1 条 `relay.message`，且 relay message id 等于 winner。

### Journey 3：Node/Agent 广播顺序、心跳、断连与 timeout

- 真 Gateway 注册为 `online`、`agent_count=4`，30 秒后 `last_heartbeat_at` 严格前进。
- 通过真实 `/im/ws/gateway` 发送非字典序 advertisement `agent-z, agent-a`；owner user-stream
  按相同顺序收到 online `agent.status_changed`，seq 为 `2, 3`。
- 完整真栈 resilience 旅程覆盖断连/恢复。
- 已绑定测试 Gateway 保持 transport WS 在线，只停止业务心跳；60.1 秒后 owner user-stream 收到
  `node.status_changed status=offline last_error=heartbeat_timeout`，公开 `/nodes` 同步一致。

### Journey 4：过程事件、完整关键路径与重启恢复

完整真栈命令：

```text
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  ./scripts/e2e-critical.sh -m "not slow"
14 passed, 1 failed, 2 deselected in 266.35s
```

工具、权限、停止、subagent、group mention、普通 Gateway resilience 等 14 条 selected 旅程通过。

同 SQLite 的 IM restart 直接旅程也通过：direct/shadow 重启后均返回 200，两条旧消息原序保留，
4 个 Agent 可见，Gateway heartbeat generation 前进；重启后向原 conversation 发送新消息返回 201 并最终
`completed`。

但 Gateway restart continuity 旅程失败：

1. 用户在 direct conversation 发送随机暗号，公开 user-stream 收到 `message.completed`。
2. 按相同 config 重启 Gateway。
3. 公开 `/nodes` 已显示同 node `online`，且 `last_heartbeat_at` 相对重启前严格前进，readiness 等待成功。
4. 用户重连 `/im/ws/user`，向同一 conversation POST “复述暗号”。
5. POST 返回 HTTP 503，用户无法继续重启前会话，因而也无法看到暗号复述。

## Reference Artifacts Reviewed

N/A。本 unit 无前端原型、视觉 reference 或 must-match 契约。

## 问题清单

### Issue 1：Gateway 公开恢复在线后，原会话首次续发仍返回 503

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 直接违反 relay 投递在 Gateway 重新连接后继续可用的必验 Scenario；用户已看到 node
  online 且 heartbeat generation 前进，仍无法把下一条消息 relay 给 Gateway。
- **Expected**: replacement Gateway 的公开 heartbeat generation 前进后，原 conversation 可立即继续收发并保留上下文。
- **Actual**: readiness 条件成功后，向原 conversation POST 下一条用户消息返回 HTTP 503。
- **Evidence**: `test_context_survives_gateway_restart` 的真实 IM + Gateway 旅程；完整套件结果
  `14 passed, 1 failed, 2 deselected`。

## 验收标准覆盖

### Requirement: 账号隔离与会话消息行为保持不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| owner 只能访问自己的会话与消息 | `motivation.md` | Journey 1：双账号公开 HTTP 列表/get/patch/messages | 列表互不可见；跨租三类请求均 404 | pass | Round 2 独立重跑 |
| direct 与 group 会话继续稳定持久化 | `motivation.md` | Journey 1：创建、发送、分页、重读 | 类型/参与者正确；顺序与游标分页稳定 | pass | 发送终态另见 Journey 4 |
| 外部 channel shadow conversation 保持幂等 | `motivation.md` + M4 main/unit baseline | Journey 2：find-or-create、user-stream、同入口差分 | conversation 复用、实时事件与重复消息表现均与 main 相同 | pass | Round 1 fail 已按 refactor 不变性口径关闭 |

### Requirement: Gateway 注册、状态与 relay 行为保持不变 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Node 注册和状态变化继续实时可见 | `motivation.md` + M4 advertisement baseline | Journey 3：真注册/心跳/断连/timeout、非字典序广播 | advertisement 原序、seq 递增；heartbeat 前进；60.1 秒 timeout 广播与公开状态一致 | pass | Round 1 verifier W1 已关闭 |
| relay 投递与回执继续收口 | `motivation.md` + M4 main/unit baseline | Journey 2 + Journey 4：普通 relay、重复 HTTP 基线、winner relay、Gateway restart 后续发 | 常态 relay 与 winner 通过；但 replacement heartbeat 已前进后原会话下一条 POST 仍为 503 | fail | Issue 1 |
| group reply context 与 agent 间投递保持不变 | `motivation.md` | Journey 2 + Journey 4：5 轮 winner 竞争、group mention/未 mention | 两 ack 复用 winner、单 relay；群聊关键路径通过 | pass | 真实 Gateway WS |

### Requirement: 过程事件与重启恢复保持不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 工具、思考、权限与终态事件实时展示并可回放 | `motivation.md` | Journey 4：完整真栈工具/权限/停止/subagent/回复旅程 | 对应 selected 旅程通过；公开消息终态与 usage 可见 | pass | 完整套件其余 14 条通过 |
| 使用既有数据库重启 IM | `motivation.md` | Journey 4：同 DB IM restart，重新登录并继续原会话 | 数据/历史/Agent 保留；Gateway heartbeat generation 前进；新消息 201 并最终 completed | pass | Gateway-only restart 的 relay 503 归上一 Requirement |

## Side Findings

- HTTP 重复 `Idempotency-Key` 产生两条消息是 main 与 unit 的既有等价行为，不属于本 refactor 回归；按首文档
  “不借 refactor 顺带修复现有缺陷”的约束，应另立 bugfix 候选。
- verifier Round 2 指出 `design.md` 的 typed-result 表仍写“稳定排序”，且决策 9/里程碑概述仍称三段，
  与 Changelog/M4 的 advertisement 顺序和第四段 closure 不一致。reviewer 未修改 design；需由上游文档流程收口。

## 澄清记录

- Round 2 明确采用 behavior-preserving 判据：M4 已提供 `origin/main` 同公开入口差分的 HTTP duplicate 项按
  baseline-equivalent 关闭；其余直接阻断必验旅程、且没有 main 等价证据的用户面失败仍按 reviewer 契约留在 unit 内。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；无跨包职责或部署变化。
- [x] `docs/specs/im/`：无需更新；本 unit `no spec delta`，既有行为契约未变。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；无新增用户操作。
- [x] `docs/SPEC_GUIDE.md`：无需更新；未改变文档体系。

---

# Round 3 — 2026-07-13

- **Verdict**: `pass`
- **Highest Required Action**: `pass`
- **Review mode**: full
- **Fix delta**: `7ede49f8..8bbba707`
- **必验 Scenario**: 8；`pass` 8，`fail` 0，`inconclusive` 0
- **Issues**: blocking 0，major 0，minor 0

## Round 2 问题继承与关闭

Round 2 唯一 issue 是 Gateway 已公开恢复 online、heartbeat generation 已前进后，原 conversation 首次续发仍
返回 503。本轮从全新 Runbook 真栈独立执行完整关键旅程：先在 direct conversation 发送随机暗号并等待
`completed`，终止旧 Gateway，replacement Gateway 仅在旧进程退出后产生新 heartbeat 才判 ready；随后向同一
conversation 发“复述暗号”，POST 成功、agent 回复 `completed` 且正确复述重启前上下文。

对应真实旅程 `test_context_survives_gateway_restart` 本轮通过，Round 2 Issue 1 **已关闭**。

## 用户旅程体验

### Journey 1：双 owner、direct/group 与历史分页

通过公开 auth、conversation、message HTTP 入口创建两个 owner。owner A 创建 direct（本人 +
`default-agent`）与 group（本人 + `default-agent` + `plato`），各写入三条消息；owner B 创建自己的会话。

- 双方列表互不可见；B 读取 A 的 direct conversation 与 messages 均为 404。
- direct 返回 `type=direct`，参与者为本人、`default-agent`；group 返回 `type=group`，参与者为本人、
  `default-agent`、`plato`。
- direct 分页为 `direct-2, direct-3` → `direct-1`；group 历史为 `group-1, group-2, group-3`，顺序稳定。

### Journey 2：shadow、实时事件、relay 与 group/agent 投递

- 同一 external 四元组经公开 find-or-create 返回 `201 → 200`，复用同一 shadow conversation；发送者显示为
  `Review A`。
- owner 的真实 `/im/ws/user` 从当前 cursor 续接后，shadow 新消息按 `message.sent → message.created →
  message.delivered` 实时出现，conversation id 保持一致。
- 完整真栈 group directed mention、未 mention agent 静默、普通 relay、工具回复和 Gateway resilience 旅程通过；
  agent 间投递未出现重复消息或错误落点。
- 多 node / group 顺序另作加严检查：真实 Gateway WS 非字典序 advertisement `agent-z, agent-a` 在 owner
  user-stream 中保持相同 online 顺序，seq 连续递增；group peer legacy bulk 顺序与后一 peer enqueue 前即时
  route 的确定性用例通过。人工构造但缺少真实当前群回复上下文的探针不作为验收证据。

### Journey 3：Node/Gateway 生命周期与 Round 2 重启恢复

- Runbook 无条件 `e2e-down.sh` → `e2e-up.sh` 后，openapi ready、真实 Gateway auto-bind 并注册 online。
- 真实非字典序 Gateway 注册广播为 node online → `agent-z` online → `agent-a` online，seq 严格递增；公开
  heartbeat 时间前进，连接关闭后 owner 收到 offline 事件。
- 完整 resilience 旅程覆盖 Gateway 断开、重连和后续收发；Round 2 的 replacement readiness / 原会话续发
  场景独立通过，不再出现 503。
- heartbeat-timeout 的 durable transition / owner broadcast 守护用例与真实 WS owner 隔离、advertisement
  顺序用例均通过；本轮没有把缺少完整绑定生命周期的临时探针计入结论。

### Journey 4：过程事件、完整关键路径与同库 IM 重启

完整真栈命令：

```text
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  ./scripts/e2e-critical.sh -m "not slow"
15 passed, 2 deselected in 221.60s
```

其中覆盖 bash 后台通知、前台超时、创建 Agent、Gateway 韧性、group mention/静默、fork、权限批准/拒绝、
Gateway restart continuity、停止 run、subagent 失败隔离/前台回传与工具调用后回复；过程和终态均从真实
Gateway/IM/LLM 路径收口。

同 SQLite IM restart 另作直接验收：重启前公开状态为 8 个 conversation、`max_event_id=35`、12 个 Agent，
选定 direct 历史为 `direct-1, direct-2, direct-3`。仅停止 IM，并以相同端口、JWT secret 和
`data/im_service.sqlite3` 重启；Gateway 自动重新连接 online。重启后 conversation/事件游标/Agent 数不变，
direct 与 shadow 均返回 200，三条旧消息原序保留；向原 direct conversation 继续发送返回 201，agent 最终
`completed` 回复本轮随机 marker，无额外迁移动作。

## Reference Artifacts Reviewed

N/A。本 unit 无前端原型、视觉 reference 或 must-match 契约。

## 问题清单

无。

## 验收标准覆盖

### Requirement: 账号隔离与会话消息行为保持不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| owner 只能访问自己的会话与消息 | `motivation.md` | Journey 1：双账号公开 HTTP 列表/get/messages | 双方列表互不可见；B 读 A conversation/messages 均 404 | pass | Round 3 独立重跑 |
| direct 与 group 会话继续稳定持久化 | `motivation.md` | Journey 1 + Journey 4：创建、发送、分页、同库重启重读 | 类型/参与者正确；分页与历史原序；重启后继续发送并 completed | pass | 真实 HTTP + 真 Gateway |
| 外部 channel shadow conversation 保持幂等 | `motivation.md` + M4 main/unit baseline | Journey 2：find-or-create、在线 user-stream、既有差分基线 | `201→200` 同 id；发送者显示保留；实时 sent/created/delivered 顺序可见 | pass | HTTP duplicate 的 baseline-equivalent 结论沿用已证明差分 |

### Requirement: Gateway 注册、状态与 relay 行为保持不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Node 注册和状态变化继续实时可见 | `motivation.md` + design Changelog 的 advertisement 顺序约束 | Journey 3：真 Gateway 注册/重连；真实 WS 非字典序 advertisement；liveness 守护 | online 广播保持 `agent-z→agent-a`，seq 递增；heartbeat 前进；disconnect/offline 与 timeout 守护通过 | pass | 公开 user-stream + `/nodes`，确定性 timeout 辅证 |
| relay 投递与回执继续收口 | `motivation.md` | Journey 2 + Journey 3 + Journey 4：普通 relay、完整 critical、replacement Gateway 续发 | 完整真栈 15/15；replacement ready 后原 conversation POST 成功、回复 completed 且上下文保留 | pass | Round 2 Issue 1 已关闭 |
| group reply context 与 agent 间投递保持不变 | `motivation.md` + M5 顺序约束 | Journey 2 + Journey 4：group directed mention/静默、agent 投递、多 node 顺序加严 | group/agent 真栈旅程通过；非字典序状态广播保持；group peer legacy 顺序与 enqueue-time route 用例通过 | pass | 无效人工探针未计证据 |

### Requirement: 过程事件与重启恢复保持不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 工具、思考、权限与终态事件实时展示并可回放 | `motivation.md` | Journey 4：完整真栈工具/权限/停止/subagent/回复旅程 | `e2e-critical` 15/15；对应公开历史/终态关键旅程全部通过 | pass | 真 Gateway/IM/LLM |
| 使用既有数据库重启 IM | `motivation.md` | Journey 4：相同 DB/JWT/端口只重启 IM，重新登录、读历史并继续原会话 | 8 conversation、event 35、12 Agent 不变；direct/shadow 200；旧消息原序；新消息 201→agent completed | pass | 无额外迁移 |

## Side Findings

- HTTP 重复 `Idempotency-Key` 产生两条消息仍是 main/unit baseline-equivalent 的既有行为，不属于本 refactor
  回归；本轮未借 refactor 改变该结论。

## 澄清记录

- 无新增口径澄清。严格按 `motivation.md` 的 behavior-preserving 不变性判断；自动化或人工探针只有在完整真实
  前置成立时才计作证据。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；无跨包职责或部署变化。
- [x] `docs/specs/im/`：无需更新；本 unit `no spec delta`，auth/conversation/node/relay/tool timeline 契约未变。
- [x] `docs/specs/gateway/`：无需更新；Gateway routing/session continuity 的长青行为未变。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；无新增用户操作或运行配置。
- [x] `docs/SPEC_GUIDE.md`：无需更新；未改变文档体系。

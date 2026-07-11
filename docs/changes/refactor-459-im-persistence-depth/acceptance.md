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

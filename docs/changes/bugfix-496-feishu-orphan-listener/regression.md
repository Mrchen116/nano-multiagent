# bugfix-496 — 回归验证

> 对齐: `incident.md`
>
> Validation snapshot: `e79b5d1a12204c077188f3646f741c8648d66cc9 → d0331f25b6edc8d5baa5e25a146eb7896345a69a`
>
> Review round: 1（full）

## Verdict

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Issues**: 2 blocking / 0 major / 0 minor
- **结论**: Gateway 被 `kill -9` 后，原 Feishu listener 的进程身份在 0.005 秒内自行消失，离线通道页也正确显示节点离线与上次状态；但真实通道未从 `pending / Connecting` 收敛，异常恢复后三条飞书消息只有一条收到 Bot 回复，IM 影子历史还出现重复回复，因此用户仍不能稳定完成核心旅程。

## Reference Artifacts Reviewed

- 无原型、设计稿或视觉 reference。本轮页面判据仅来自 `incident.md` 的现有“节点离线 / 上次状态 / 已连接”语言。

## User Journeys Exercised

1. **正常停止并重新接管**：从真实隔离 IM/Gateway 和真实 Feishu listener 记录 Gateway 与 worker 的 PID + process birth，执行正常 `stop`，再启动新 Gateway 并观察真实通道状态。
2. **异常死亡与离线页面**：只对已复核 birth 的隔离 Gateway 执行 `kill -9`，计时观察旧 worker；随后在真实浏览器打开 Agent 通道页检查离线与 last-known 状态。
3. **异常恢复后的连续消息**：重新启动 Gateway，确认只有一个当前 listener，从当前飞书用户向真实 `nano` Bot 连续发送三个 nonce，检查飞书回复和 Web IM 影子历史。
4. **正常空闲反例**：保持 Gateway/worker 存活且 10 秒不发送消息，复核 process birth、listener 数量和 channel API 状态是否改变。

## 验收标准覆盖

### Requirement: Feishu listener 与 Gateway 共享退出生命周期

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 正常停止 Gateway | `incident.md` | 真实 Gateway `stop`，按 PID + birth 观察旧 listener，再启动新 Gateway | Gateway `11816` 停止后 worker `11822` 原 birth 消失；新 Gateway `13043` 随后通道变为 `pending / failed` 且没有 listener，额外重启后才重新出现 worker | `fail` | 旧 listener 的有序回收成立，但“新 Gateway 正常接管 Bot”不稳定，通道页也始终未收敛到已连接。 |
| Gateway 异常死亡 | `incident.md` | 对 Gateway `16832` 执行 `kill -9`，从确认原 Gateway birth 消失开始等待 worker `17704` | 原 worker birth 在 `0.005s` 内消失，远低于 3 秒预算；超时清理未参与成功判定 | `pass` | 原 listener 不再作为孤儿进程继续存活。 |

### Requirement: Gateway 重启后飞书消息稳定恢复

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 异常退出后重新启动 Gateway | `incident.md` | 重启真实 Gateway，确认唯一 worker；用当前飞书用户连续发送 `BUGFIX496_A/B/C`，再查真实飞书会话与 IM history | Gateway `19263` 只有 worker `19270`；超过 60 秒后飞书只有 `C` 的 Bot 回复，`A/B` 无回复；IM 影子计数为 `A 1 user + 1 agent`、`B 1 + 1`、`C 1 + 2` | `fail` | 飞书回复随机缺失，影子历史存在重复，直接违反“每条回复且无缺失或重复”。 |
| Gateway 离线期间查看通道状态 | `incident.md` | `kill -9` 后等待 stale，真实浏览器登录并进入 `/settings/agents/forall` 的 Channels | 页面显示 `Node is offline`、`Waiting for node`、`Last status updated …`；截图 `/tmp/nano-bugfix-496-review.rXniHg/.playwright-cli/page-2026-08-04T05-26-23-172Z.png` | `pass` | 页面没有把旧 connected 当作当前有效连接。 |

### Requirement: 正常空闲不被误判为故障

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 已连接通道长时间没有入站消息 | `incident.md` | parent 存活且空闲 10 秒，比较 worker birth、listener 数量、channel API 与页面 | worker `19270` birth 未变，唯一 listener 未变，API 仍为 `pending / connected / fresh`；页面仍为 `Connecting` | `inconclusive` | 没有观察到 idle 导致退出或重连，但通道从未达到 runbook 要求的 `applied`、页面“已连接”前置，不能把局部进程证据算作完整用户场景通过。 |

## 复现验证

### 已消除的原始症状部分

- 异常路径使用真实 spawn listener，不是 fake 或单测替代。
- 只强杀已按 `.gateway-state.json` 的 PID + process birth 核验过的 Gateway。
- 旧 listener 的 PID + birth 在 0.005 秒内消失，没有变成 `PPID=1` 孤儿；该部分原始生命周期缺口未再复现。

### 仍阻塞交付的用户症状

- 真栈启动和多次重启后，channel API 一直是 `sync_state=pending`；Web IM 在节点在线时仍显示 `Connecting` 和 “Establishing the Feishu long connection”，截图：`/tmp/nano-bugfix-496-review.rXniHg/.playwright-cli/page-2026-08-04T05-29-32-916Z.png`。
- 异常恢复后连续发送三条飞书消息，用户只在飞书收到 `BUGFIX496_C` 回复；`A/B` 没有 Bot 回复。
- 对应 IM 影子会话中 `BUGFIX496_C` 有两条 agent message，违反不重复要求。

## Issues

### ISSUE-1 — 通道无法收敛为用户可见的已连接状态

- **Severity**: `blocking`
- **Regression Relation**: `direct`
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 正常停止/重启和异常恢复都依赖通道重新稳定接管；当前真实通道始终是 `pending`，页面长期显示 `Connecting`，第一次正常重启后还进入 `failed` 且没有 listener，用户无法确认或依赖恢复完成。
- **Steps**:
  1. 使用 unit 分支启动隔离 IM/Gateway，接入 mini 上已启用的真实 Feishu Bot。
  2. 正常停止 Gateway，确认旧 listener 消失，再启动 Gateway。
  3. 打开 Agent Channels 页面并等待状态收敛。
- **Expected**: 新 Gateway 只有一个 listener，通道收敛为已连接。
- **Actual**: API 保持 `sync_state=pending`；页面保持 `Connecting`。一次正常重启后 observed 进入 `failed` 且 listener 消失，需要额外重启才恢复底层连接。

### ISSUE-2 — 异常恢复后连续消息仍缺回复且影子历史重复

- **Severity**: `blocking`
- **Regression Relation**: `direct`
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 这是 incident 的核心用户旅程；三条应回复消息中两条在飞书静默无回复，另一条在影子历史重复，不能交付。
- **Steps**:
  1. 强杀已连接 Gateway，确认旧 listener 自行退出。
  2. 启动新 Gateway，确认只有一个当前 listener。
  3. 从飞书连续发送“请只回复 `BUGFIX496_A` / `B` / `C`”。
  4. 等待超过 60 秒，查看飞书对话和内部 IM 影子历史。
- **Expected**: A/B/C 各有一条飞书 Bot 回复；影子历史中每个 nonce 各有一条 user 和一条 agent message。
- **Actual**: 飞书只有 C 的 Bot 回复；影子历史 A=`1+1`、B=`1+1`、C=`1+2`。

## 回归测试

- 异常 parent death：`pass`，worker 在 3 秒预算内自行退出。
- 正常 stop 的旧 worker 回收：`pass`。
- 离线通道页：`pass`，显示离线和 last-known。
- 正常 restart 接管：`fail`，没有稳定收敛为已连接。
- 异常恢复后的飞书与 shadow 消息：`fail`，回复缺失且重复。
- 空闲 10 秒：进程与 API 局部证据未见 idle watchdog，但完整用户场景因通道从未进入 applied/已连接而 `inconclusive`。

## 自动化测试增量

- 实施记录提供了真实 spawn owner-death 回归测试；本轮没有把该测试结果当成产品验收替代。
- 本报告的 verdict 来自真实 IM/Gateway、真实 Feishu Bot、真实 Web IM 页面和真实飞书消息旅程。

## Side Findings

- 无。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。
- [x] `docs/specs/gateway/`（长青行为契约层）：需要更新；unit 已有 delta，待实现与验收收敛后由 orchestrator 校正并归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 环境与清理

- unit 前端产物从当前 worktree 重建，真实 IM 首页加载指纹为 `index-CimPHGgj.js`。
- 隔离 IM 端口 `64501` 已释放，隔离 Gateway/worker 已停止，`tmux` 会话已删除。
- 临时 config、JWT、manifest、私钥和 reviewer env 已删除；报告中没有 App Secret、token 或完整 App ID。
- mini 持久 Gateway 已恢复为 PID `54642`，并确认只有一个当前 Feishu worker。

## Recommended Next Step

保持 `fix-implementation`：先关闭 ISSUE-1 的通道收敛问题和 ISSUE-2 的真实消息缺失/重复，再由同一 reviewer 对两个 issue 及受影响 Scenario 做复验。第一轮禁止路由到 `revise-design`。

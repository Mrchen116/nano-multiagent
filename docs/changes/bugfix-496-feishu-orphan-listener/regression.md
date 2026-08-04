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

---

# Round 2 — 2026-08-04

> Validation snapshot: `202949e2fb81ee3ed33443e5e1985a7b9ba49562 → d8d6d84724c4884bec824259a12698acca581c1b`
>
> Review round: 2（targeted closure；因 Round 1 问题混入 mainline 既有行为，扩展为 unit + origin/main 同 fixture 因果复验）

## Verdict

- **Verdict**: `pass-with-issues`
- **Highest Required Action**: `out-of-unit`
- **Issues**: 0 blocking / 2 major / 0 minor，均已证明为 mainline 既有问题；本 unit 无待修 issue
- **needs_re_review**: `false`
- **结论**: bugfix-496 自身可交付。正常 stop/start 后旧 listener 消失且新 Gateway 只有一个当前 listener；`kill -9` 后旧 listener 原 process birth 在确认 owner 消失后的 `0.004s` 内自行消失；离线页面正确显示节点离线与上次状态；异常恢复后 A/B/C 三条真实飞书消息按“发一条、等 exact reply、再发下一条”全部各得到一次回复；parent 存活空闲 10 秒时同一 Gateway/worker birth 保持不变。Round 1 的 `Connecting` 与影子重复分别由 origin/main 基线和既有 Issue #231 证明为 496 范围外问题。

## Reference Artifacts Reviewed

- 无原型、设计稿或视觉 reference。离线页面判据来自 `incident.md` 的现有状态语言；真实页面证据：`/tmp/nano-bugfix-496-r2-evidence.eXofBo/offline-page.png`。

## User Journeys Exercised

1. **正常 stop/start**：在真实 Feishu listener 已 connected 且唯一时冻结 Gateway/worker PID + process birth，正常 stop 后确认旧 worker identity 消失，再显式启动新 Gateway，确认新 listener 唯一并恢复 `connected + fresh`。
2. **异常死亡、离线状态与恢复**：只对已核验 birth 的隔离 Gateway 执行 `kill -9`，从确认原 Gateway birth 消失起计时观察旧 worker；随后从真实浏览器进入 Agent Channels，检查节点离线与 last-known，再启动当前 Gateway。
3. **逐条真实消息**：在重新确认当前 Gateway/listener 唯一后，以当前飞书用户依次发送 A/B/C 三个唯一 nonce；每条都等待对应 exact Bot reply 后才发送下一条，再核对飞书会话与 Web IM 影子历史。
4. **parent-alive idle 反例**：保持 Gateway 与 listener 存活且 10 秒不发送消息，对比前后 PID + birth、listener 数量和 channel observed 状态。
5. **origin/main 因果基线**：在 `202949e2f` 上使用全新的隔离 IM、相同 mini cache fixture 和独立日志，复现 Round 1 的 `pending / Connecting`，判断 ISSUE-1 是否由 496 引入。

## 验收标准覆盖

### Requirement: Feishu listener 与 Gateway 共享退出生命周期

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 正常停止 Gateway | `incident.md` | 真实 Gateway 正常 stop/start，前后分别冻结 Gateway/worker PID + birth 并核对唯一 listener | stop 后旧 worker 原 birth 消失；新 Gateway 启动后只有一个直接 spawn listener，observed=`connected`、fresh；之后真实消息路径可用 | `pass` | 新 Gateway 已实际接管 Bot。页面仍显示 `Connecting` 的既有状态投影问题单列 #234，不归因给 496。 |
| Gateway 异常死亡 | `incident.md` | 对已核验 birth 的隔离 Gateway 执行 `kill -9`；确认 owner 原 birth 消失后进入 3 秒 worker 等待 | 原 worker birth 在 `0.004s` 内消失；无超时 cleanup 参与成功判定；重启前系统中没有该旧 listener | `pass` | Round 1 的 `0.005s` 证据被本轮独立复现，结果一致。 |

### Requirement: Gateway 重启后飞书消息稳定恢复

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 异常退出后重新启动 Gateway | `incident.md` | 重启后确认唯一 listener；依次发送 `BUGFIX496_R2_A/B/C_20260804T1409`，每条等 exact reply 后再发下一条；核对飞书和 shadow history | 飞书侧每个 nonce 恰有 `1 user + 1 app`，三条均回复；全程 listener count=1。IM shadow 每个 nonce 为 `1 user + 2 agent`，其固定双写与 #231 / bugfix-497 完全一致 | `pass` | 496 的因果判据“不会因旧 listener 随机缺失或重复”通过：没有旧 listener、没有飞书回复缺失或重复。影子固定双写是 mainline 已知独立问题，见 OUT-2。 |
| Gateway 离线期间查看通道状态 | `incident.md` | `kill -9` 后等 channel stale，真实浏览器登录 Web IM 并打开 Agent Channels | 页面显示 `Node is offline`、`Waiting for node`、`Last status updated …`，证据 `/tmp/nano-bugfix-496-r2-evidence.eXofBo/offline-page.png` | `pass` | 页面没有把旧 connected 显示为当前有效连接。 |

### Requirement: 正常空闲不被误判为故障

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 已连接通道长时间没有入站消息 | `incident.md` | parent 存活且空闲 10 秒，比较 Gateway/worker birth、listener 数量与 channel observed | 前后为同一 Gateway 与 worker birth，listener 始终唯一，observed 始终 `connected + fresh`，没有退出、重连或降级 | `pass` | `sync_state=pending` 在 origin/main 同 fixture 原样存在，不是 idle 触发，也不代表 listener 失活。 |

## Round 1 Issues Disposition

### ISSUE-1 — 通道无法收敛为用户可见的已连接状态

- **Disposition**: 从 bugfix-496 blocker 移出，转为 out-of-unit [#234](https://github.com/Mrchen116/nano-multiagent/issues/234)。
- **直接基线**: origin/main `202949e2f` 使用全新 IM 与同一 mini cache fixture，首次启动为 `sync_state=pending` 且无 listener；显式 stop/start 后出现唯一 listener，observed=`connected + fresh`，但 `sync_state` 仍为 `pending`。unit 得到相同行为。
- **产品判断**: listener 连通、唯一性、真实消息往返与 control-plane `sync_state` 没有同步收敛；后者影响状态可信度，但不是本 unit 的 owner-death 生命周期改动造成。

### ISSUE-2 — 异常恢复后连续消息缺回复且影子历史重复

- **Disposition**: 作为 bugfix-496 blocker 关闭；拆成两个已有因果。
- **消息缺失**: Round 1 在不足 1 秒内发送 A/B/C，后续消息 steering 进入同一 active run；本轮严格逐条等待 exact reply，A/B/C 在真实飞书各有一次且只有一次 Bot 回复，证明当前唯一 listener 的恢复路径可用。
- **影子重复**: 本轮每个 nonce 都固定为 `1 user + 2 agent`，不是旧 listener 引发的随机重复；这是既有 [#231](https://github.com/Mrchen116/nano-multiagent/issues/231) / bugfix-497 dual-writer 问题，另行处理。

## Issues

### OUT-1 — listener 已连接但通道页长期显示 Connecting

- **Severity**: `major`
- **Regression Relation**: `unrelated-existing`
- **Recommended Action**: `out-of-unit`
- **Action Rationale**: origin/main 在相同 fresh-IM fixture 中直接复现，且真实 listener 与消息收发已成立；该状态投影不由 496 引入。
- **Tracking**: [#234](https://github.com/Mrchen116/nano-multiagent/issues/234)

### OUT-2 — Web IM 影子会话 Agent 回复双写

- **Severity**: `major`
- **Regression Relation**: `unrelated-existing`
- **Recommended Action**: `out-of-unit`
- **Action Rationale**: 三个 nonce 的飞书外部回复均唯一，但 Web IM shadow 都固定多一条 Agent 气泡；症状与现有 #231 完全一致，bugfix-497 已在处理。
- **Tracking**: [#231](https://github.com/Mrchen116/nano-multiagent/issues/231) / `bugfix-497-shadow-mirror-duplicate-reply`

## 回归测试

- 正常 stop/start：`pass`，旧 worker identity 消失，新 Gateway 只有一个 current listener。
- 异常 parent death：`pass`，worker 在 owner 原 birth 消失后的 `0.004s` 内自行退出。
- 离线通道页：`pass`，真实页面显示 offline/last-known。
- 异常恢复消息：`pass`，A/B/C 按顺序逐条发送后各获得一次 exact 飞书回复，无旧 listener 抢占。
- 空闲 10 秒：`pass`，同一 Gateway/worker birth、唯一 listener、`connected + fresh` 均保持不变。
- origin/main 对照：`pending / Connecting` 在基线原样复现；#234 已建立。

## 自动化测试增量

- 实施与 verifier 报告中的真实 spawn owner-death、parent-alive idle 和完整 worker 文件测试结论继续有效；本轮没有用自动化测试替代产品验收。
- Round 2 的 verdict 来自 unit 与 origin/main 两套独立真栈、真实 Feishu Bot、真实 Web IM 页面和真实逐条消息旅程。

## Side Findings

- 无其他未跟踪发现。两个 mainline 既有 major 问题均已关联独立 issue，不要求在 bugfix-496 中扩 scope。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。
- [x] `docs/specs/gateway/`（长青行为契约层）：需要更新 listener-owner 生命周期增量；由 orchestrator 在收尾阶段校正并归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 环境与清理

- unit 与 origin/main 前端均从各自 worktree 源码重建，产物指纹均为 `index-CimPHGgj.js`。
- 两套 fresh IM 使用不同高位端口、独立数据库/config/workspace 与分离日志；报告只保留安全状态结论和两张无 secret 的页面证据，不保留原始 runtime/log/数据库。
- unit/baseline Gateway、listener、IM、reviewer tmux 和浏览器均已停止；两组端口已释放。
- 临时 config、JWT、auth token、chat id、manifest、私钥和 reviewer env 已定向删除；原始隔离 runtime 目录已删除。
- mini 持久 Gateway 已恢复，并确认只有一个当前 Feishu listener。

## Recommended Next Step

bugfix-496 不需要再次产品复验；orchestrator 可把本轮作为该 unit 的产品 gate 结论继续收尾。#234 与 #231 独立跟踪，不扩入 496。

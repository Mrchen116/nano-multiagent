# refactor-463 — 验收报告

> 对齐: `motivation.md` 的 20 条用户侧不变性 Scenario
> Review round: 1
> Product journey implementation head: `7f95df14972f59065a7ef1fd0431b717f37c07ed`
> Report stacking head: `c5bd19c3cdbaeee0cda2d9a26f668e4c35128b0c`（仅新增 `verification.md`，产品代码树未变化；fast-forward 后重启隔离栈再次确认 node online）

## Verdict

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Coverage**: 20 Scenarios = 16 pass / 4 fail / 0 inconclusive / 0 not-applicable
- **Issues**: blocking 0 / major 4 / minor 0
- **Acceptance bar**: Round 1 严格门禁；任一必验 Scenario fail 即不能交付

## 用户旅程体验

### Journey 1 — Web IM 直聊、动态配置、工具投递与重启续接

隔离真栈由 `scripts/e2e-down.sh` → `scripts/e2e-up.sh` 重启；IM/Gateway 的 cwd 均为 unit worktree，节点首次健康检查为 online。

- 直聊 conversation `601ba82d041a4aac88b5b87ef0bfd60e`：用户发送 `R463DIRECT194309`，正确 Agent 在原会话只回复 `R463DIRECT194309`。
- 未知 Agent：创建含 `unknown-refactor463-reviewer` 的会话返回 HTTP 400，`detail=participant_ids contains unknown users`，对应会话数 `0`。
- 完整 non-slow 关键路径：`15 passed, 2 deselected in 335.65s`；其中 Gateway restart context continuity 与 IM transient-fault recovery 均在独立临时真栈通过。
- slow 关键路径：`1 passed, 15 deselected, 1 xfailed in 234.63s`；cron pass，heartbeat bubble 按仓库已登记 #126 保持 strict xfail。
- 动态配置旅程失败：
  1. 2026-07-15T11:44:27.389234Z，公开 PATCH 把 Plato 从 profile v1 更新到 v2，`system_prompt="For every user message, reply with exactly R463CONFIGV2 and nothing else."`；随后公开 live 与 mirror GET 均返回 profile v2 与该 prompt。
  2. 更新后新建 conversation `53ffcbbdfe2e4c34b2c8be836f4698bd`。第一轮回复仍是旧助手语义“你好！我已准备好……”，第二轮明确回答自己没有 exact phrase 指令。
  3. 等待后再建全新 conversation `c17b5e5e4af44fb89374f7fbee28efb9`，回复仍是旧语义“I’m ready and acting under my current system prompt…”，没有 `R463CONFIGV2`。
- `send_message` 旅程失败：公开创建真实 Agent `dispatch-reviewer2-195146`（owner 已绑定、profile v1、allowlist 仅 `send_message`）和真实 recipient 用户。源 conversation `0a258ab759964bd2b40338e2f196bef6` 的两次独立 token 投递均失败：
  - `DISPATCHR463195213` → “The `send_message` call failed: the server disconnected without sending a response. The message was not delivered.”
  - `DISPATCHR463RETRY195413` → “The retry also failed: connection refused. The message was not delivered.”
  recipient 两次均没有目标 conversation，也没有 token。

### Journey 2 — 群背景、并发、连续插话、停止与 liveness

- 真关键路径中的 directed group A→B 与 unmentioned-agent silence 均通过；补走 Web IM MENTION 群 conversation `cc9782b34ce340dc8cc03d31d50b7cfe` 时，未点名背景 `GROUPCTX201603` 后会话保持 idle、Agent 消息数为 0。另补跑群 sender prefix、buffer drain 分条、未点名只缓冲与点名后带入背景 5 条公开边界测试：`5 passed in 0.22s`。
- 连续插话与跨会话并行：
  - A conversation `87b694ad22604c85a733860245e1f786` 于 12:01:50Z 开始前台 `sleep 20`；12:01:55Z 连续收到 `STEERONE200150`、`STEERTWO200150`。
  - B conversation `87e6dccae23344f9a7d2b3adaff4bc2f` 同时发送 `BFAST200150`，在 A 完成前约 19 秒已看到 `BFAST200150`。
  - A 于 12:02:14Z 完成，最终可见回复按发送顺序包含 `STEERONE200150 STEERTWO200150`，原前台步骤未被硬中断。
- active `/stop` 真关键路径通过；同一 A 会话 idle 后发送 `/stop`，用户看到“当前没有正在执行的操作。”，没有新 run。
- quiet alive：conversation `327a7ebba9724ac6a616cc904bdf06f2` 的静默 `sleep 130` 跨过 120 秒 idle 窗口，154.353 秒后正常显示 `QUIETDONE200317`。
- real stall：conversation `6560facd62284535bc5c2480b3f6d4f9` 运行 180 秒任务时，隔离 Gateway 被暂停 136 秒；恢复后节点自动 online，会话从 running 变 idle，用户看到 `relay idle for 120s with no new event`，长任务 token 未泄漏。同会话下一条消息 3.2 秒返回 `RECOVEREDR463200927`，证明后续工作已释放。

### Journey 3 — 图片、静默 token、后台回信与 external/shadow 边界

- 图片 conversation `61663b3686e241a38ee132998c21ebf1`：
  - 真实 PNG 经 Web IM 附件入口进入本轮，Agent 回复“这是一个即时通讯（IM）聊天工作区界面。”
  - 将文本文件伪装为 PNG 后，原会话立即显示“这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。”
- `NO_REPLY`：group conversation `04b9f15d8b924d569128c98b910b29cc` 明确要求模型只输出 `NO_REPLY`；会话实际经历 running→idle，但 Agent 消息数保持 `1→1`、Agent 消息中 token 出现次数为 0，列表 preview 保留用户原文而非静默 token。
- 后台任务：conversation `be93ab2dff304dfdbf01eb37c2f66b52` 先显示已启动，随后原会话收到 `BGONCER463201121`；继续观察 8 秒，匹配回复仍恰好 1 条。
- 无真飞书凭据；按 design runbook 允许的 controllable external adapter，执行 external visible delivery、trigger-source、shadow seed、shadow-only reply、IM absent wiring 与 shared group key 共 14 条公开边界测试：`14 passed in 1.79s`。外部触发回原外部目标并同步 shadow、shadow 触发不反写外部、IM manager 缺失时外部可见投递不被阻断。

### Journey 4 — 启动、停止、重连与 accepted-work shutdown

- 初次与报告 fast-forward 后各执行一次隔离 `e2e-up.sh`，两次都得到 unit worktree cwd 的 IM/Gateway 与 online node；完整关键路径中的真实 Gateway restart/context continuity、Gateway-first/IM-later 与 IM kill/restart case 均通过。
- 优雅关闭用户终态失败：conversation `b3ffd772230d4245b59534513cb54657` 并发进入两条用户消息 `SECONDSHUT201255` / `FIRSTSHUT201255`，SIGTERM 前 run_state=running 且已有两个 provisional Agent 气泡。foreground Gateway 收到 SIGTERM 后 4.8 秒退出，但立即与 5 秒后复查均为：

  ```text
  conversation_state=running
  agent_messages=[('', None, None), ('', None, None)]
  node_status=offline
  ```

  用户没有看到活动或排队工作的明确失败终态，两个空回复持续悬空。
- 重连恢复失败：报告 fast-forward 后 fresh e2e-up 初始 node online；Web IM 群背景消息成功后节点变 offline，随后点名消息公开 POST 返回 503。Gateway 进程仍存活且 cwd 仍为 unit worktree，但 `/im/v1/nodes` 连续观察 90 秒始终 offline，没有自动恢复。

## Reference Artifacts Reviewed

N/A。本 unit 不改前端 UI，也没有原型、设计稿或 must-match reference contract。

## 问题清单

### Issue 1 — 动态 Agent 配置没有影响下一轮或新会话

- **Severity**: major
- **Regression Relation**: direct
- **Expected**: IM 已发布 profile v2 后，下一轮用户消息或新会话使用 v2 prompt。
- **Actual**: live/mirror 均显示 v2，但两个更新后新 conversation 仍按旧助手语义回复；其中一轮明确否认存在 exact phrase 指令。
- **Reproduction**: 见 Journey 1 的 PATCH → live/mirror GET → conversation `53ffc...` 两轮 → conversation `c17b...` 新轮。
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 直接违反本 unit “动态 Agent 配置在下一轮生效” Scenario；Round 1 禁止推测 design 问题，交 implementation worker 定位。

### Issue 2 — `send_message` 两次均未把消息送达目标用户

- **Severity**: major
- **Regression Relation**: direct
- **Expected**: Agent 工具投递被 IM 确认，目标用户在正确直聊收到 token，来源 Agent 的连续历史保持。
- **Actual**: 两次独立 token 都在源会话显示连接失败，recipient 没有目标 conversation 或 token。
- **Reproduction**: 见 Journey 1 的 Agent `dispatch-reviewer2-195146`、source conversation `0a258...` 与两个 token。
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 直接违反本 unit “Agent 工具投递仍同步到正确直聊会话” Scenario，且用户无法完成跨会话投递。

### Issue 3 — 优雅关闭后 accepted work 仍永久显示 running

- **Severity**: major
- **Regression Relation**: direct
- **Expected**: active run 有终态；尚未提交的 accepted item 明确失败；投递完成后才关闭 IM transport。
- **Actual**: Gateway 正常退出后 conversation 仍 running，两个 Agent 气泡为空且无失败原因。
- **Reproduction**: 见 Journey 4 的 conversation `b3ffd...` 与 SIGTERM 前后输出。
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 直接违反本 unit “停止时已接纳的入站工作有明确结局” Scenario，用户会得到悬空回复。

### Issue 4 — Gateway 进程存活但节点断线 90 秒未自动恢复

- **Severity**: major
- **Regression Relation**: direct
- **Expected**: IM 断线后 Gateway 自动重连；节点恢复 online，用户可继续发消息。
- **Actual**: node 持续 offline，点名消息返回 503；90 秒观察期内未恢复，尽管 Gateway pid 仍存活。
- **Reproduction**: 见 Journey 4 的 fresh stack 与群 conversation `cc978...` 后续点名步骤。
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 直接违反本 unit “启动、停止和重连结果保持一致” Scenario；完整关键路径中的独立 transient case 虽通过，但不能覆盖这次真实用户旅程失败。

## 验收标准覆盖

### Requirement: 入站路由、会话与回复位置保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 直聊消息仍由正确 Agent 在原目标回复 | `motivation.md` 对应 Scenario；`docs/specs/gateway/routing-delivery.md` | Journey 1，真 Web IM/IM/Gateway/LLM | conversation `601ba...`，`R463DIRECT194309` 原会话精确回复；non-slow critical 全绿 | pass | 正确 Agent、原目标均可见 |
| Gateway 重启后续接原会话 | 同上，会话映射持久化 Requirement | 完整 non-slow critical 真栈 | `test_context_survives_gateway_restart` 与 restart readiness case；15/15 pass | pass | 用户历史连续 |
| 未知 Agent 路由仍被拒绝 | `motivation.md` 对应 Scenario | Journey 1，公开 IM 会话入口 | HTTP 400；unknown conversation 数 0 | pass | 无误投递或副作用 |
| 动态 Agent 配置在下一轮生效 | `motivation.md` 对应 Scenario | Journey 1，公开 PATCH/live GET/新会话 | profile v2 已 live；`53ffc...`、`c17b...` 均旧行为 | fail | Issue 1 |
| Agent 工具投递仍同步到正确直聊会话 | `motivation.md` 对应 Scenario；routing-delivery 产品工具 Requirement | Journey 1，真实 send_message Agent + recipient | `0a258...` 两次连接失败，recipient 无会话 | fail | Issue 2 |

### Requirement: 群聊门控与背景上下文保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 未点名群消息只积累背景 | `motivation.md`；routing-delivery 群聊门控 Requirement | Journey 2，critical 真群 + Web IM 群补走 + public boundary | unmentioned critical pass；`cc978...` 未点名后 idle/0 Agent 消息；聚焦 5/5 pass | pass | 后续点名补走被 Issue 4 的 offline 中断，但独立真 critical 已覆盖点名链 |
| 点名后带入此前群背景 | 同上 | Journey 2，真 critical directed group；sender/context public boundary | group A→B 与 silence critical pass；群 sender prefix/buffer drain 聚焦 5/5 pass | pass | 无真飞书依赖 |

### Requirement: 单会话并发、插话与停止保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同会话串行且跨会话并行 | `motivation.md`；routing-delivery FIFO Requirement | Journey 2，A/B 两真会话 | B 在 A 前约 19 秒完成；A follow-up 顺序不乱 | pass | 无跨会话阻塞 |
| 运行中插话被及时采纳 | `motivation.md`；routing-delivery steering Requirement | Journey 2，长前台步骤中连续两条追问 | A 最终按顺序包含 `STEERONE... STEERTWO...` | pass | 当前步骤完成后采纳，未硬中断 |
| /stop 中断活动运行 | `motivation.md`；routing-delivery `/stop` Requirement | 完整 critical 真栈 | `test_stop_aborts_active_run` pass | pass | 固定停止确认、完成哨兵不冒泡 |
| 空闲会话收到 /stop | 同上 | Journey 2，A 完成后公开发送 `/stop` | “当前没有正在执行的操作。” | pass | 无新 run |
| 活着但安静的运行不被误杀 | `motivation.md`；routing-delivery liveness Requirement | Journey 2，130 秒 quiet + 136 秒 real stall | quiet 154.353 秒成功；stall 失败后 3.2 秒恢复下一轮 | pass | 两半均有用户可见结果 |

### Requirement: 图片与可见失败反馈保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 有效图片正常进入本轮 | `motivation.md` 图片 Scenario | Journey 3，真 Web IM attachment + Gateway + LLM | `61663...` 正确识别 IM 聊天工作区 | pass | 真实 PNG |
| 图片下载、超限或损坏 | `motivation.md` 图片失败 Scenario | Journey 3，伪 PNG | 原会话固定可读失败反馈 | pass | 未错误回答 |

### Requirement: 运行过程、终态与后台回复保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 中间与最终回复不重不漏 | `motivation.md`；routing-delivery reply/failure Requirements | Journey 3 + full critical | NO_REPLY running→idle 后消息数不增；tool-call/reply、timeout critical 通过 | pass | 静默 token 不泄漏 |
| 后台任务完成后回到原会话 | `motivation.md`；routing-delivery background Requirement | Journey 3，真 background Bash | `be93...` 原会话收到一次 `BGONCER...`，8 秒仍一次 | pass | 无重复 |
| 外部 channel 与影子会话投递边界不变 | `motivation.md`；external-channels trigger source Requirement | Journey 3，runbook 允许 controllable adapter | external/shadow 聚焦 14/14 pass | pass | external 触发回外部+shadow；shadow 触发不反写 |
| IM 离线时外部 channel 仍可用 | `motivation.md`；external-channels offline autonomy Requirement | Journey 3，runbook 允许 IM-absent adapter | 无 IM manager 的 external visible/intermediate delivery 与 runtime wiring pass | pass | Feishu 真凭据不作门禁 |

### Requirement: Gateway 生命周期的用户结果不受本重构影响 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 启动、停止和重连结果保持一致 | `motivation.md`；`docs/specs/gateway/service-lifecycle.md` | Journey 4，fresh stack + full critical + 真实离线观察 | 初始/critical 可恢复；后续 live node 90 秒 offline 且消息 503 | fail | Issue 4 |
| 停止时已接纳的入站工作有明确结局 | `motivation.md`；service-lifecycle stop Requirement | Journey 4，真 SIGTERM + 两条 accepted 消息 | Gateway 退出后仍 running，两个空气泡无终态 | fail | Issue 3 |

## Side Findings

- #126 heartbeat actionable bubble 仍是仓库既有 strict xfail；本轮 slow suite 正常走到 `xfail`，不把它当 refactor-463 新 issue，也不重复立单。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。本 unit 不改变包、依赖方向或部署拓扑。
- [x] `docs/specs/gateway/`（长青行为契约层）：**无需更新**。`routing-delivery.md`、`external-channels.md`、`service-lifecycle.md` 已声明本 unit 应保持的不变量；当前需要修实现，不应把失败现象写成新契约。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。启动、隔离端口、配置与清理约定未改变。
- [x] `docs/SPEC_GUIDE.md`（文档规范）：**无需更新**。本 unit 未改变文档体系。

## Reviewer 越界自证

- 未读取或修改实现源码；未修改测试、配置或 canonical product docs。
- 仅写本报告；未调用 `systematic-debugging`，未基于日志或协议字段给实现归因。
- controllable adapter 仅用于 design runbook 明确允许的 external/shadow/IM-offline 边界；direct chat、图片、并发/steer、stop、quiet/stall、background、restart/reconnect 与 shutdown 均走真 IM/Gateway/Kernel/LLM 或仓库真进程 critical path。
- 未立 out-of-unit GitHub issue：四个问题都直接影响本 unit Scenario，默认路由 `fix-implementation`。

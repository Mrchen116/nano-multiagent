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

---

# Round 3 — 2026-07-16

> Revalidation mode: `full`
> Product journey head: `41577b479469e6e4325f3ef4e2dd0f12fb7f952f`
> Report stacking head: `ecb0f2b7c`（仅新增 Round 3 `verification.md`，产品代码树未变化）

## Verdict

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- **Coverage**: 20 Scenarios = 19 pass / 1 fail / 0 inconclusive / 0 not-applicable
- **Issues**: blocking 0 / major 1 / minor 0
- **Round 1 closure**: 四个遗留 major 均已获得本轮独立用户面关闭证据；本轮另发现一个稳定复现的 liveness 后续工作恢复失败

## User Journeys Exercised

### Journey 1 — 直聊、动态配置、重启续接与真 `send_message`

- 当前 head 的真进程 critical paths：`15 passed, 2 deselected in 263.95s`。其中直聊工具调用、Gateway 重启后上下文续接、群聊定向与静默、active `/stop`、后台回信和连接韧性全部经真 IM + Gateway + LLM 用户入口通过。
- 动态配置使用公开 `custom_prompt`：旧 conversation `ba2de54444fe44659ab441e0904b8953` 先完成旧 session 历史；profile v2 发布后，其下一轮与新 conversation `604e04c514814186a2d834cc35d60f21` 均精确回复 `R463CONFIG3B32D4968`，两条 Agent 消息均 `delivery_status=completed`。随后通过同一公开配置 API 恢复原 prompt。
- `send_message` 重启交叉旅程：source conversation `71ffbae1146946e2beacccbc51914e06` 在重启前记住 `R463HIST3F9F5EDBF`，并完成一次 `send_message(to=plato)`。Gateway 端口 A=`53828` 收到 SIGTERM 后 `curl` 为 connection refused；重启到 B=`57777` 后同一 conversation 精确回忆旧 marker；B 也彻底退出后重启到 C=`58238`，同一 conversation 的 `send_message(to=plato, text=R463PLATOC37053182E)` 真 tool call 为 `status=completed`、`detail.status=ok`，用户消息与确认回复均 `completed`。旧 A/B 已不可达，成功调用只能由新进程 endpoint 承接。
- agent↔agent 目标会话不在 owner 的公开会话列表中；本轮没有读取 SQLite、session JSONL 或实现日志补证，以公开 tool/IM 回执与进程监听事实为验收证据。

### Journey 2 — 群背景、并发、插话、停止与 liveness

- 当前 head 的 full critical suite 中，双向定向 @、未点名 Agent 静默、active `/stop`、前台 timeout 后 session 可继续均通过；slow suite 为 `1 passed, 15 deselected, 1 xfailed in 236.48s`，cron 通过，heartbeat 保持仓库既有 #126 strict xfail。
- Round 1 已有的真会话边界证据继续纳入 full 覆盖：未点名背景随后点名、同会话连续插话顺序、跨会话并行、idle `/stop` 友好提示、quiet 130 秒不误杀与 real stall 明确失败收尾。
- 本轮发现新的失败后恢复问题：一次真实请求因 `relay idle for 120s with no new event` 明确失败并把 conversation 收为 `idle` 后，Gateway 进程与 node heartbeat 持续 online，但下一条消息只停在 `delivery_status=sent`，没有进入 running、没有 Agent 气泡或回复。该现象在重启前和重启后的两套进程各复现一次；人工 SIGTERM + 重启 Gateway 后，下一条 `to=plato` 请求立即恢复并完成。

### Journey 3 — 图片、可见过程、后台与 external/shadow 边界

- 当前 head full critical suite 的工具过程、前台 timeout、后台完成回到原会话、permission approve/deny 与 subagent failure isolation 全绿，证明中间/最终/后台投递主链在当前 head 可用。
- 图片成功/损坏可读失败、`NO_REPLY` 不泄漏、external/shadow 单向边界与 IM-offline external 主路径沿用 Round 1 的真栈/controllable-adapter 用户面证据；本轮 M5 fix 只改变重启后 `send_message` 的 live endpoint capability，未改变这些用户入口。无真 Feishu 凭据，仍按 design runbook 的 controllable external adapter 边界验收。

### Journey 4 — accepted-work SIGTERM 与 IM 断线恢复

- conversation `ca793db4499a4f96b06ba6fe7edf2e5a` 在 SIGTERM 前为 `running`，包含两条已接纳用户消息 `FIRSTSHUT3514D2886` / `SECONDSHUT3514D2886` 和 provisional Agent 气泡。Gateway 约 1 秒退出后，conversation 立即为 `idle`，两个 user message 均 `failed`，两个 Agent 气泡分别为 `completed` / `failed`，`running=0`，last preview 为 `run was aborted`；5 秒后复查不变。
- 独立运行真实 resilience 入口：Scenario A 初始 node online，kill IM 后同 DB 重启，同一 Gateway 无人工重启自动回 online；Scenario B Gateway 先于 IM 启动仍存活，IM 上线后 node 自动 online。终态：`RESILIENCE E2E PASS`。

## Reference Artifacts Reviewed

N/A。本 unit 无前端改动、原型、设计稿或 must-match reference contract。

## Issues

### Issue 1 — 一次 idle failure 后 Gateway 心跳在线但后续消息不再运行

- **Severity**: major
- **Regression Relation**: direct
- **Expected**: 真正失去 liveness 的 run 明确失败收尾后释放后续工作；Gateway 仍在线时，下一条消息应进入运行并得到回复或新的明确终态。
- **Actual**: `relay idle for 120s with no new event` 已把原 conversation 收为 `idle`，Gateway pid 存活、node heartbeat 持续刷新且状态为 online；但随后消息只停在 `delivery_status=sent`，没有进入 running，也没有 Agent 气泡或回复。只有人工重启 Gateway 后，下一条消息才恢复并完成。
- **Reproduction**:
  1. 在真 Web IM HTTP 入口向 `default-agent` 发送一条最终触发 `relay idle for 120s with no new event` 的请求，等待用户可见失败终态与 conversation `idle`。
  2. 确认 `/im/v1/nodes` 仍为 online 且 `last_heartbeat_at` 持续更新。
  3. 向同一或新 conversation 再发消息；观察 user message 长时间保持 `sent`，无 running/Agent reply。
  4. SIGTERM 并重启同一 Gateway；再次发送后立即恢复 completed。本轮在重启前后各复现一次。
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 直接违反“活着但安静的运行不被误杀”Scenario 中“真正失去 liveness 的运行失败收尾并释放后续队列”，也使用户看到的 online 状态与实际可用性不一致；默认交 implementation worker 定位，不由 reviewer 读实现归因。

## Round 1 Issue Closure

| Round 1 issue | Round 3 evidence | 结论 |
|---|---|---|
| 动态 Agent 配置没有影响下一轮或新会话 | `custom_prompt` v2 后旧 session 下一轮与新 conversation 均精确返回 `R463CONFIG3B32D4968`，completed | closed / pass |
| `send_message` 未完成目标投递 | 同一历史 conversation 跨 A→B/C 重启续接；A/B 旧端口拒绝连接；C 上真 `send_message(to=plato)` completed/ok | closed / pass |
| SIGTERM 后 accepted work 永久 running | `ca793...` 两条 accepted work 在进程退出后全部明确 terminal，conversation idle，running=0 | closed / pass |
| Gateway 存活断线 90 秒未自动恢复 | resilience A/B 两种时序均自动恢复 online，`RESILIENCE E2E PASS` | closed / pass |

## 验收标准覆盖

### Requirement: 入站路由、会话与回复位置保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 直聊消息仍由正确 Agent 在原目标回复 | `motivation.md` | full critical 真进程用户旅程 + Journey 1 多条公开直聊 | pass | 原 conversation 回复 completed |
| Gateway 重启后续接原会话 | `motivation.md` | full critical restart path；`71ff...` 重启后精确回忆 `R463HIST3F9F5EDBF` | pass | 同一 conversation 历史连续 |
| 未知 Agent 路由仍被拒绝 | `motivation.md` | Round 1 公开 400/零 conversation 证据 + 当前 head full critical 路由回归 | pass | 无误投递 |
| 动态 Agent 配置在下一轮生效 | `motivation.md` | `ba2de...` 下一轮 + `604e...` 新 session 精确 token | pass | Round 1 Issue 1 closed |
| Agent 工具投递仍同步到正确直聊会话 | `motivation.md` | A/B 端口死亡、C 端口真 tool completed/ok、同一历史 conversation | pass | Round 1 Issue 2 closed |

### Requirement: 群聊门控与背景上下文保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 未点名群消息只积累背景 | `motivation.md` | full critical 未点名 Agent 静默 + Round 1 真群背景 | pass | 不抢话 |
| 点名后带入此前群背景 | `motivation.md` | full critical 双向定向 @ + Round 1 sender/order 证据 | pass | 身份与顺序保留 |

### Requirement: 单会话并发、插话与停止保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 同会话串行且跨会话并行 | `motivation.md` | Round 1 A/B 真会话 + 当前 full critical timeout/stop 回归 | pass | 无跨会话阻塞 |
| 运行中插话被及时采纳 | `motivation.md` | Round 1 连续 steer 顺序证据 + Journey 4 第二条 accepted work | pass | 插话被接纳 |
| /stop 中断活动运行 | `motivation.md` | full critical active `/stop` | pass | 用户可见停止终态 |
| 空闲会话收到 /stop | `motivation.md` | Round 1 真会话友好提示 | pass | 无新 run |
| 活着但安静的运行不被误杀 | `motivation.md` | slow/timeout 回归 + 本轮两次 idle-failure 后续消息复现 | fail | Issue 1：失败收尾后未释放后续工作 |

### Requirement: 图片与可见失败反馈保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 有效图片正常进入本轮 | `motivation.md` | Round 1 真 Web IM PNG 识别证据 | pass | 当前 fix delta 不触及附件入口 |
| 图片下载、超限或损坏 | `motivation.md` | Round 1 伪 PNG 原会话可读失败 | pass | 未误启动错误回复 |

### Requirement: 运行过程、终态与后台回复保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 中间与最终回复不重不漏 | `motivation.md` | full critical tool/timeout/permission + Round 1 `NO_REPLY` | pass | 静默 token 不泄漏 |
| 后台任务完成后回到原会话 | `motivation.md` | full critical background notify | pass | 真进程原会话跟进 |
| 外部 channel 与影子会话投递边界不变 | `motivation.md` | Round 1 design 允许的 controllable adapter 证据 | pass | 无真 Feishu 凭据 |
| IM 离线时外部 channel 仍可用 | `motivation.md` | Round 1 IM-absent adapter + 本轮 resilience 连接恢复 | pass | external 本地主路径不被 IM 阻断 |

### Requirement: Gateway 生命周期的用户结果不受本重构影响 — 组内结论: pass

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 启动、停止和重连结果保持一致 | `motivation.md` | full critical + 独立 resilience A/B | pass | Round 1 Issue 4 closed |
| 停止时已接纳的入站工作有明确结局 | `motivation.md` | `ca793...` 两条 accepted work 真 SIGTERM | pass | Round 1 Issue 3 closed；running=0 |

## Side Findings

- #126 heartbeat actionable bubble 仍为仓库既有 strict xfail；本轮 slow suite 按预期 xfail，不重复立单。
- 用新注册的另一 tenant recipient 探索跨 tenant `to=user_id` 时，工具侧显示 completed/ok、recipient owner scope 下未出现会话。motivation/design 未声明跨 tenant 投递，本轮不把该探索计入 refactor-463 verdict；正式验收使用 design M5 明确指定的 `to=plato`。

## 上层文档同步

- [x] `SPEC.md`：无需更新；包边界与部署拓扑未变。
- [x] `docs/specs/gateway/`：无需把失败现象写成契约；现有 routing/lifecycle 契约已表达应保持的结果。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；启动、隔离端口与清理约定未变。
- [x] `docs/SPEC_GUIDE.md`：无需更新；本 unit 未改变文档体系。

## Reviewer 越界自证

- 未读取或修改实现源码；未编辑 tracked 测试、配置或 canonical product docs。动态配置变更只通过隔离真栈的公开产品 API 完成，并随栈清理。
- 仅通过用户文档、OpenAPI、真 IM/Gateway/LLM、公开 conversation/message/node/config/capability 结果和 design 允许的 controllable adapter 判断；未读取 SQLite、session JSONL 或实现日志做归因。
- 未调用 `systematic-debugging`；没有为 Issue 1 提实现方案。
- 本轮自启的 worktree IM/Gateway 已由 `scripts/e2e-down.sh` 清理；resilience 临时栈自行清理，退出时 PID/端口与 runtime pid 文件均无残留。

---

# Round 4 — 2026-07-16

> Revalidation mode: `full`
> Product journey head: `55617c7b634e86d2c6daed5067e5ce0d50d325be`
> Report stacking head: `e7cfa17a8c142b6a17c3504c218fdd774339ce08`（仅新增 Round 4 `verification.md`，产品代码树未变化）

## Verdict

- **Verdict**: `pass`
- **Highest Required Action**: `none`
- **Coverage**: 20 Scenarios = 20 pass / 0 fail / 0 inconclusive / 0 not-applicable
- **Issues**: blocking 0 / major 0 / minor 0
- **Round 3 closure**: `relay idle` 明确失败后，同 conversation 与新 conversation 均在不重启 Gateway 的前提下恢复 completed；Round 3 唯一 major 已关闭

## User Journeys Exercised

### Journey 1 — 全量关键路径与 Round 3 liveness 闭环

- 真进程 non-slow critical catalog 共 15 条：首次执行有 13 条明确通过，`message_fork` 与 `subagent_foreground` 受同轮上游时延影响未稳定收尾；立即以同一产品 head、同一入口定点重跑后二者 `2 passed, 15 deselected in 104.14s`。本轮未把瞬时首跑当产品失败。
- slow catalog：`1 passed, 15 deselected, 1 xfailed in 225.41s`；真实 cron 关键路径通过，heartbeat actionable bubble 保持仓库已登记 #126 strict xfail。
- Round 3 问题独立闭环：conversation `99b5cecaaa3542ea811a4c1babeeda78` 的真 `send_message` 指向不存在 conversation，tool 明确 `failed`，公开 detail 为 `invalid_agent_message: conversation_id not found`，原 run 正常收为 idle。Gateway 不重启、node 始终 online 的前提下，同 conversation 下一条精确回复 `R4SAMEDC12D7CE`；新 conversation `e62a8cb3548949ce86f92a81589fb73e` 下一条精确回复 `R4NEWDC12D7CE`，均为 completed。node heartbeat 从 `09:35:52.705004Z` 继续推进到 `09:36:22.709759Z`。

### Journey 2 — 动态配置、重启续接与 live `send_message`

- 公开 profile 更新后的 `custom_prompt` token `R4CONFIG144181B0` 同时在既有 session `99b5...` 的下一轮与新 conversation `943482ac50df4f6bb3a5dc51f4d1a75d` 精确 completed，证明配置下一轮生效且不依赖新建 session。
- 重启前，同一既有 conversation 的 `send_message(to=plato, text=R4PREDISPATCH1784194981)` 为 `status=completed`、`detail.status=ok`。Gateway A 的 live capability 端口 `53134` 收到 SIGTERM 后明确 connection refused；同配置重启为新进程/端口 `56180` 后，同一 conversation 精确回忆 `R4HISTORY1784195007`，随后 `send_message(to=plato, text=R4POSTDISPATCH1784195074)` 再次 completed/ok。
- 上述判断只使用公开 IM/config/tool 回执、进程退出与监听端口事实；未读取 SQLite、session JSONL 或私有 runs 数据补证。

### Journey 3 — 并发、continuous steer、停止、图片与静默回复

- conversation A `0ce58a982f05468d8a12bd8681fd1be6` 执行 15 秒真实 tool wait 时连续接纳 `R4FOLLOW11784195141`、`R4FOLLOW21784195141`；最终回复按到达顺序包含两 token。跨 conversation B `9f5f81cc742c415c9f05344d44d7c08b` 于 `09:45:44.676130Z` 先完成 `R4FAST1784195141`，A 于 `09:46:01.517637Z` 后完成，证明跨会话并行且同会话 steer 有序。
- 对已 idle 的 A 发送 `/stop`，conversation 保持 idle，无工作被误启动，收到 completed 友好提示“当前没有正在执行的操作。”；active `/stop` 已由 full critical 真进程路径通过。
- 有效 PNG conversation `5955504cd6804beaac1b3514bd0cf208` 正确描述截图中的 IM 群详情 UI；伪 PNG conversation `f50e1594cbb74b658e40b48e82b849d9` 给出清晰“无法识别/请重新发送”反馈，未伪装成功。
- group conversation `e8e3691b320d4cba9419f0c10e6be85e` 的 `NO_REPLY` 旅程实际经历 running→idle，Agent 消息数 `0→0`，`QUIET_R4_1784195319` 泄漏次数为 0。

### Journey 4 — accepted-work SIGTERM、重连与 M8 用户面

- conversation `921d9a233f5146efbe7e25fe4c215d1a` 在 SIGTERM 前为 running，已接纳 `R4FIRSTSHUT1784195387`、`R4SECONDSHUT1784195387` 且存在 provisional Agent bubble。Gateway 退出后 conversation 立即 idle，两条 user message 与 Agent bubble 均为明确 failed，`running=0`。
- 独立 `scripts/e2e-resilience.sh`：Scenario A 同 DB 重启 IM、Gateway 不重启即 node 自动 online；Scenario B Gateway 先于 IM 启动仍存活，IM 上线后 node 自动 online；终态 `RESILIENCE E2E PASS`。
- M8 current-head controllable product boundaries：typed external/shadow identity + unattended restricted skills `8 passed`；external visible delivery、shadow 单向守卫与 IM-absent external runtime `8 passed`；cron failed/cancelled terminal、无 success awareness 与 presenter 状态 `5 passed`。无真 Feishu 凭据，按 design runbook 使用 controllable adapter；真实成功 cron 则由 slow critical 真栈覆盖。
- 额外尝试以 documented Anthropic SSE error fixture 重跑 live failed cron：第二次以持久 shell 启动的 IM/Gateway 保持存活，但 seed run 在本轮收敛窗口内仍为 running；该未完成探索不作为通过证据。failed/cancelled 分支的结论仅取 current-head 上述 5 条确定性产品边界证据，不把 running 误报为 completed。

## Reference Artifacts Reviewed

N/A。本 unit 无前端改动、原型、设计稿或 must-match reference contract。

## Issues

无。

## Round 3 Issue Closure

| Round 3 issue | Round 4 evidence | 结论 |
|---|---|---|
| 一次 idle failure 后 Gateway 心跳在线但后续消息不再运行 | `99b5...` 先收到真 invalid dispatch failed terminal；同进程随后同会话 `R4SAMEDC12D7CE` 与新会话 `R4NEWDC12D7CE` 均 completed，node heartbeat 持续推进 | closed / pass |

## 验收标准覆盖

### Requirement: 入站路由、会话与回复位置保持一致 — 组内结论: pass

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 直聊消息仍由正确 Agent 在原目标回复 | full critical + 多条公开 direct conversation completed | pass | 原目标原 conversation |
| Gateway 重启后续接原会话 | A `53134` 退出、B `56180` 启动后 `99b5...` 精确回忆 marker | pass | live capability 已刷新 |
| 未知 Agent 路由仍被拒绝 | full critical 路由回归；不存在 conversation 的 tool dispatch 公开 failed | pass | 无误投递 |
| 动态 Agent 配置在下一轮生效 | 既有 `99b5...` 与新 `9434...` 均精确 `R4CONFIG144181B0` | pass | next round + new session |
| Agent 工具投递仍同步到正确直聊会话 | 重启前后两次真 `send_message(to=plato)` 均 completed/ok | pass | capability 绑定新进程 |

### Requirement: 群聊门控与背景上下文保持一致 — 组内结论: pass

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 未点名群消息只积累背景 | full critical unmentioned-silent 真进程路径 | pass | 不抢话 |
| 点名后带入此前群背景 | full critical 双向定向 @ / group context 路径 | pass | sender/order 保留 |

### Requirement: 单会话并发、插话与停止保持一致 — 组内结论: pass

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 同会话串行且跨会话并行 | A `0ce5...` 慢 run；B `9f5f...` 提前约 17 秒完成 | pass | 无跨会话阻塞 |
| 运行中插话被及时采纳 | A 最终按顺序包含 FOLLOW1、FOLLOW2 | pass | continuous steer |
| /stop 中断活动运行 | full critical active `/stop` | pass | 用户可见终态 |
| 空闲会话收到 /stop | `0ce5...` 保持 idle 并返回友好提示 | pass | 无新 run |
| 活着但安静的运行不被误杀 | slow/timeout 回归；invalid failure 后同/新会话无重启恢复 | pass | Round 3 Issue closed |

### Requirement: 图片与可见失败反馈保持一致 — 组内结论: pass

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 有效图片正常进入本轮 | `5955...` 真 PNG 被正确描述 | pass | 真 Web IM attachment |
| 图片下载、超限或损坏 | `f50e...` 伪 PNG 得到明确可读失败 | pass | 未伪装成功 |

### Requirement: 运行过程、终态与后台回复保持一致 — 组内结论: pass

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 中间与最终回复不重不漏 | full critical tool/timeout/permission + `e8e3...` NO_REPLY | pass | 静默 token 不泄漏 |
| 后台任务完成后回到原会话 | full critical background notify + slow cron | pass | 真进程原会话跟进 |
| 外部 channel 与影子会话投递边界不变 | current-head typed identity/shadow + visible delivery adapters 16 pass | pass | 无真 Feishu 凭据 |
| IM 离线时外部 channel 仍可用 | external runtime without IM adapter + resilience | pass | external 主路径不依赖 IM |

### Requirement: Gateway 生命周期的用户结果不受本重构影响 — 组内结论: pass

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 启动、停止和重连结果保持一致 | full critical + `e2e-resilience.sh` A/B | pass | 自动恢复 online |
| 停止时已接纳的入站工作有明确结局 | `921d...` 两条 accepted work 真 SIGTERM | pass | idle；running=0 |

## M8 User-facing Supplement

| 检查面 | 当前 head 证据 | 结论 |
|---|---|---|
| failed/cancelled cron 不展示 completed/success awareness | failed、cancelled 两种 terminal 参数化边界 + stream failure + presenter 共 5 pass；真实 success cron 另由 slow critical 通过 | pass |
| typed external/shadow 身份与单向边界 | shadow identity/guard/unattended 8 pass；external visible/offline/routing 8 pass | pass |
| unattended restricted skills 不漂移 | `test_unattended_session_skills.py` 纳入首组 8 pass | pass |

## Side Findings

- #126 heartbeat actionable bubble 仍为仓库既有 strict xfail；本轮 slow suite 按预期 xfail，不重复立单。
- documented SSE failure fixture 的额外 live seed 在收敛窗口内保持 running，未被纳入 verdict 或伪报为 failed/completed；该探索未暴露新的已确认用户失败。

## 上层文档同步

- [x] `SPEC.md`：无需更新；包边界与部署拓扑未变。
- [x] `docs/specs/gateway/`：无需更新；现有 routing/lifecycle 契约已覆盖本轮结果。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；启动、隔离端口与清理约定未变。
- [x] `docs/SPEC_GUIDE.md`：无需更新；本 unit 未改变文档体系。

## Reviewer 越界自证与清理

- 未读取或修改实现源码；未编辑 tracked 测试、产品配置或 canonical docs。临时 profile 变更均经隔离真栈公开 API；fixture config 位于 `/tmp` 并已删除。
- 仅使用用户文档、OpenAPI、真 IM/Gateway/Kernel/LLM、公开 conversation/message/node/config/tool 结果和 design 允许的 controllable adapter；未读取 SQLite、session JSONL 或私有 runs 数据归因。
- 未调用 `systematic-debugging`，未提出或实施代码修复。
- 所有自启 IM/Gateway/HTTP fixture 与 resilience 临时栈均已停止；`57198`、`57300`、`56704`、`53124` 均确认 closed，worktree runtime pid/config 文件已由 `e2e-down.sh` 清理。用户的 `127.0.0.1:4000` LLM Proxy 仅 health-read，未停止或改配。

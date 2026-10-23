# bugfix-647 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review`（独立 reviewer；未参与设计编写）
- reviewer target: `incident.md`、`design.md`；代码基线 `236a4698c7a8a2d03efa00c35049914d2422771d`
- review_mode: `full`
- mode_reason: 首轮 Gate 2；核查完整需求、缓存/数据流、PA 等待边界和验证入口。
- started_at: `2026-10-23T22:43:00+08:00`（近似开始时间）
- completed_at: `2026-10-23T22:51:29+08:00`
- duration: 约 8 分 29 秒
- checkout: `/Users/czj/.codex/worktrees/trajectory-sync/nano-multiagent`，`codex/bugfix-647-trajectory-sync`。开始时仅 unit 未跟踪；审查中另有实施者修改测试，本轮只审基线代码与上述设计，只新增本报告，不提交。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。Gate 2 未通过。**

### Coverage 与证据

1. **现状与实际组装**：`apps/node/src/main.ts:341` 真实构造 `GlobalAgent`；`packages/dsh-integration/src/index.ts:383-405` 的 handler 先 `listDescendants`，再逐个 `observeSession` 且未使用传入 cursors。安装的 `@deepseek-ai/dsh-subagent@0.2.1-alpha.1` 中 `lib/types/list-children.js:99-165` 确认目录本身逐节点 observe；`dsh-session-query/lib/index.js:1051` 默认 prepared cache 为 5。incident 的重复冷读取机制成立。本轮未重新测量生产延迟，不把历史墙钟数据当作同步 CPU 时间。
2. **冷目录/版本缓存**：安装的 `@deepseek-ai/dsh-session-persistence@0.2.1-alpha.1` 根 export 公开 `SessionPersistence`；`lib/types/index.d.ts` 的 identity/stat 契约明确实例 identity 与同实例同 session 的 revision 相等可复用，stat 不读日志。`dsh-session-query/lib/types/observation.d.ts` 暴露 cursor、prepared revision 和 lazy live events；`lib/index.js:348-393,448-506` 证实冷版本来自读取前 stat、live 没有 durable revision。设计明确只留轻量目录/游标、使用 observation revision、不把读取后新版本冒充已读版本，并要求服务更换/重新加载失效，方向正确。live→cold 不能直接把无 revision 的 live cut 当作可验证冷版本，实施需遵循已有约束。
3. **完整自有事件**：`projectWorkEvent` 依赖此前 turn/start、source、模型及 tool/call，`presentation.ts` 的 `toolPresentation`、`tokenUsage`、`modelAt` 均需要上下文；变化会话返回完整 own suffix 比简单 `seq > cursor` 合理，且不影响独立原生查看器的完整继承历史。消费者确认游标在投影成功后更新、故障不推进和重启重放已有 store/inbox 幂等键，覆盖正常追加/重启。但 native cursor 不能单独表示附加 modelRuns 投影的变化，见 R1-W1。
4. **PA 等待与安全边界**：`global-agent.ts:597-635` 把根 durable 记录、Inbox 消费与后代投影串在同一 drain；task_graph（429）及普通 global send（518）等待它。根/后代队列分离可消除此依赖；`rpc.ts:28,71-104` 的 handler 并发分派允许根 observe 在另一请求尚未结束时完成。根 durable 拒绝、Inbox.commitRead、发送前 blocking/revalidation、publication 状态与 busy/stop 都已纳入设计。`config.personal` 的 send 在 `global-agent.ts:499` 提前进入 `PersonalAssistant.send`，不经过现有 reconcile；此既有独立路径不应被本次重构改变。
5. **架构判断**：DSH 元数据检查与目录投影应放在 integration，PA 只管理产品投影的确认和等待；专用轻量 reader 避免在 PA 引入 DSH 或持有完整继承日志，优于扩大上游 prepared cache。沿用公开 subagentCatalog 比另读文件格式合理；无需新增通用缓存框架。
6. **契约与验证**：`docs/specs/gateway/global-agent.md:306-311` 已要求查询回复不被无关历史同步阻塞，`docs/specs/im/agent-work.md` 已要求明细与终态持久回看；本次 no spec delta 可成立。没有 UI 布局/交互变更，不需要前端原型。M1 的压缩冷历史真实读次数/前后对照、变化子树、跨批工具、重启及独立根 durable 错误矩阵可实施；`scripts/e2e-up.sh`、`docs/development/worktree-runtime.md` 与现有真实 DSH fixture 测试提供入口。尚未执行产品验收；应在实施后补上 R1-W1 的同 cursor 元数据变化回归。

### 历史问题闭环

首轮，无历史 findings。

### Issues

#### R1-W1 — 只按原生日志 cursor 判断无变化会丢失 fallback 最终状态

- 位置：`design.md:27-28,34`（同 cursor 返回空 events、仍单独附 modelRuns），`design.md:56`（回归矩阵）。
- 证据：`packages/dsh-integration/src/model-fallback.ts:292-315` 在成功 fallback 的原生 `turn/end` 后异步等待 `host.sticky`，之后才 `finish`；`finish`（220-227）修改独立 domain 的 run.state/terminal 并发 `model.changed`，不会追加原生事件。`packages/personal-assistant/src/presentation.ts:92-100` 在 run 尚未 completed 时过滤 `turn/end`。因此第一次子投影可读到最终 native cursor 但隐藏 turn/end，并确认 childCursors；稍后 model.changed 时 cursor/revision 仍相同，设计返回空 events，第二次 `logicalEvents([], completedRuns)` 没有机会重新生成终态。该子任务可一直显示未结束直到其他原生事件或重启。
- 独立核验：对当前 `logicalEvents` 做只读 `pnpm exec tsx -e` 调用，固定同一 seq=9 的 turn/end 和两次 attempts；输出为 `firstProjection=[]`、`afterSameCursorWithEmptyEvents=[]`，完整 replay 则产生映射至 logical turn=1 的 turn/end。结合以上异步生产代码，已证明不是假想的日志重写情形。
- 修订要求：明确把影响事件投影的 modelRuns 变化纳入增量确认/失效边界，或明确保证这类变化会对该会话触发完整自有事件重放；不要求为所有冷历史持有事件。补充“已确认 native cursor、随后 fallback completion 无新 native event”的测试，验证终态、逻辑 turn 和统计仍补齐，并保持未变化冷会话零日志读取目标。

### Recommendations

#### R1-R1 — 修正根调用前提的表述，避免实施时顺手收紧现有能力

`design.md:29` 的“产品工具只允许根调用”不是当前实现事实：`GlobalAgent.call:357` 只对 inbox/conversations 做 root 限制；`ProductBridge.call` 明确传递调用子会话及根身份；`history.ts:126-134` 继承父配置，`capabilities.ts:69-71` 只是不给 subagent 追加 fixed 工具，并未禁止已选的 task_graph/send_message。建议把论证改为：本次根 durable/Inbox 产品投影沿既有 root binding 路径，后代展示不提供这些根证据；保留现有子调用与 personal send 的独立取证/授权路径，不新增 root-only 拒绝。现有 projectChildren 本来也未把 child events 写入 NodeStore，因此该表述错误本身未构成本次拆队列的新增证据丢失，列为非阻断澄清。

## Author Resolutions — Round 1

- R1-W1 accepted: Confirmed the independent model state change in scheduleSuccess. Added consumer-acknowledged modelVersions and returned modelVersion (SHA-256 of a deep-copied modelRuns snapshot). Unacknowledged event cursor or model version replays the child's complete own suffix. PA acknowledges both only after projection. Added same-cursor fallback completion regression; no full-history cache.
- R1-R1 accepted: Removed the incorrect root-only premise; existing child calls and personal send keep their current evidence and authorization paths.

## Round 2

### Metadata

- reviewer: `/root/design_review`（延续独立 reviewer）
- reviewer target: 更新后的 `design.md` 与 Round 1 Author Resolutions；代码基线仍为 `236a4698c7a8a2d03efa00c35049914d2422771d`
- review_mode: `delta`
- mode_reason: modelVersions 是为关闭 R1-W1 引入的有界 RPC/确认字段，需核查其快照时序及事件投影影响；根队列、目录版本方案与用户范围未变。
- started_at: `2026-10-23T22:54:41+08:00`
- completed_at: `2026-10-23T22:55:27+08:00`
- duration: 46 秒（取证窗口）

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。Gate 2 未通过。**

### Coverage 与历史闭环

- **R1-W1 — closed at design level**：Author Resolution 引入消费者确认 `modelVersions`；设计决策 2 和接口段要求深拷贝 modelRuns、返回对应 digest，并仅在成功投影后同时确认 cursor 与 modelVersion。缺确认值时完整 own suffix 重放，能覆盖此前“same cursor + later completion”的遗漏；M1 已包含此回归。模型版本属于 handler，reader 只接受是否重放的决定，职责保持正确。新增快照顺序存在下面 R2-W1，需同时修正才可实施。
- **R1-R1 — closed**：决策 3 已移除 root-only 前提，明确 projectChildren 不写 NodeStore、保留子调用与 personal send 原路径；与实际 bridge、call 和 personal send 分支一致。
- **retained_from: Round 1**：公开 stat/identity/revision 与 live observation API 核验、稳定先序目录遍历、完整 own suffix、两条 drain、busy/stop、no spec delta、隔离验收路径均未改动，保留此前覆盖结论。没有 UI 变更或新增生产操作。
- 本轮独立复核 `model-fallback.ts:232-252` 的 turn/start 同步更新 attempts，`presentation.ts:92-100` 的未知 attempt 分支，`work-projection.ts` 的轮次生成，以及 `inbox.ts:341-345` 的 event_id 去重行为；仅做只读函数实验，未改实现或受审文档。

### Issues

#### R2-W1 — 先冻结 modelRuns、再 await native observation 会永久写入错误轮次

- 位置：`design.md` 决策 2 的“runtime 在读取每个 child 前深拷贝 fallback.list(id)”及接口段的 forceReplay 回调时序。
- 证据与触发：一个 child 正在 fallback switching，冻结快照只有 attempt1；随后 reader 的 live flush/observe 等 await 期间，DSH 追加 fallback turn2 的 turn/start/user/message。`ModelFallback.observe` 已把 turn2 加入当前 runs，但返回的旧快照仍只有 attempt1。`logicalEvents` 对快照里查不到的 turn2 按普通事件放行，于是 `projectWorkEvent` 生成独立 turn2，工具事件也可能绑定错误逻辑 turn。后续新模型版本重放会过滤该 turn/start、把其他事件映射回 turn1，但 `InboxStore.append` 对既有 event_id 直接 return，既不能撤销错误 turn2，也不能覆盖已写的错误 turn_id。
- 独立复现：用当前 `logicalEvents` + `projectWorkEvent`，固定 events 为 seq3 turn/start(turn2)、seq4 user/message(nano-fallback)，旧 runs=[attempt1] 得到 `staleProjection=[turn_started(turn=2)]`，更新 runs=[attempt1,attempt2] 得到 `currentProjection=[]`。结合实际 await 边界与 append-only journal，该问题不能靠“下次 modelVersion 改变重放”恢复。
- 修订要求：明确先取得 native observation 的不可变 cut，再捕获用于投影与版本比较的 modelRuns 快照，不能把更早的模型快照与更晚的事件拼接。模型快照捕获、版本决定和对应响应应保持一致；冷缓存快路发现模型版本变化并转入 observation 后，同样需要使用该 cut 取得后的快照。无需引入全局锁或完整事件缓存。增加在 child 读取 await 期间新增 fallback attempt 的回归，确认不会持久化 phantom turn/错误 tool turn，同时保留 same-cursor completion 与零冷日志重读测试。

### Recommendations

无新增。

## Author Resolutions — Round 2

- R2-W1 accepted: The model snapshot callback now runs synchronously after the native observation cut is acquired, with no await before materializing events. A cold-cache metadata check that discovers a changed model version obtains an observation and re-captures the model snapshot at that cut. The returned version always describes the returned model snapshot. This avoids pairing an older attempt list with a later native fallback turn.

## Round 3

### Metadata

- reviewer: `/root/design_review`（同一独立 reviewer）
- reviewer target: `design.md` 决策 2 与 Round 2 Author Resolution
- review_mode: `closure`
- mode_reason: 仅调整同一会话的快照捕获顺序，关闭 R2-W1；无新增需求、模块或协议字段。
- started_at: `2026-10-23T22:56:53+08:00`
- completed_at: `2026-10-23T22:57:00+08:00`
- duration: 7 秒（闭环核验窗口）

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 设计审查通过。**

### 历史问题闭环与证据

- **R2-W1 — closed**：设计现已明确先 flush/observe 取得不可变 native cut，再同步深拷贝 modelRuns、计算 modelVersion、决定是否物化 events，且快照到取出事件之间无 await；冷 cache 快路发现模型版本变化时，必须取得 observation 并重新捕获模型状态，不能沿用快路提前捕获的版本。根据 Round 2 已核实的 `ModelFallback.observe` 同步登记 turn/start attempts 和 SessionObservation 固定 cut 语义，这个顺序不会把只有 attempt1 的旧快照配上之后生成的 turn2 事件，关闭已复现的错误幂等投影路径。
- 返回 digest 与返回模型快照一致、PA 仅成功投影后同时确认 modelVersion/cursor 的约束保留；同 native cursor 的异步 completion 仍会触发该 child 的完整 own suffix 重放，**R1-W1 保持 closed**。
- 根证据与后代展示分离、保留子调用/personal send 原路径的决策未变，**R1-R1 保持 closed**。
- `retained_from: Round 1 / Round 2`：公开 API、冷目录失效、事件上下文完整性、模块职责、两条 drain、no spec delta、Milestone 与隔离验证入口的未变部分，保留前两轮覆盖证据；本轮没有重跑实现或产品验收。

### Issues

无未解决 CRITICAL/WARNING。

### Recommendations

无新增。实施验证继续覆盖已记录的 same-cursor completion，以及读取等待期间新增 fallback attempt 的时序回归；本结论仅确认设计可实施，不代表实现或真实产品验收已通过。

# bugfix-410: 无人值守工具轮 + 权限门的会话健壮性（四个收口/契约缺陷）

## Relations

- Closes: #99
- Closes: #98
- Closes: #82
- Closes: #97
- Related: feat-333（auto_mode_gate 分类器引入者）, feat-394（heartbeat/cron redesign，dogfood 期间暴露 #82/#97/#98/#99）

## 原始报告

四个 issue 在手动 dogfood（refactor-406 / feat-394 期间）暴露，均与所在 unit 无关，是 kernel/Gateway/IM
既有缺陷。共享同一条故障主线：**无人值守轮（heartbeat/cron）里 agent 调写工具 + 权限门**。原文：

### #99 — auto_mode_gate 分类器 transcript 丢失全部 agent 历史工具调用

> https://github.com/Mrchen116/nano-multiagent/issues/99
>
> 现象：auto_mode_gate 安全分类器的 user prompt（`<transcript>`）里，agent 的历史工具调用全部缺失——
> 只有 `User:` 消息行 + 末尾一条待审动作，分类器看不到「agent 这轮之前做了什么」。
>
> 根因（已核到源码级）：设计要求 transcript 像素级复刻 CC `yoloClassifier.ts`（user 消息 + assistant
> `tool_use` 投影）。`build_transcript_entries`（`auto_mode_gate.py:369-382`）从 assistant 的 `content`
> 里 filter `block.type == "tool_use"`，逐字复刻了 CC。但本内核内存 `LLMMessage` 格式不同：assistant
> 消息 `content` 是纯文本/思考，工具调用在单独的 `tool_calls` 字段（`loop.py:316/334`）。content 里没有
> tool_use block → `build_transcript_entries` 永远匹配不到 → 历史工具调用被静默丢弃。唯一那条工具行
> （待审动作）来自 `_build_transcript_user_message:589` 末尾的显式 append。
>
> 定性：忠实复刻了 CC 的函数，却没复刻 CC 的消息格式契约。同一段提取逻辑搬进格式不同的代码库 → 对
> assistant 工具调用静默 no-op。
>
> 单测 false-green：`test_auto_mode_gate.py:114` 喂的是 Anthropic 格式
> `content:[{"type":"tool_use",...}]`（和 CC 一致、所以绿），但和真实运行时内存格式不符。
>
> 影响：分类器拿到「一堆 user 消息（含 heartbeat/cron 噪音）+ 一条没有前因后果的命令」，失去 CC 设计要的
> in-context 判断能力。叠加 user 文本占比畸高，在 K2.6 上更易触发 HEARTBEAT_OK 反射（本 issue 只修 B2
> format 契约，不含 K2.6 适配）。

### #98 — 等人工权限决策超 120s 被 idle 看门狗杀死，Allow once 失效

> https://github.com/Mrchen116/nano-multiagent/issues/98
>
> 现象：IM 上工具需要授权时弹权限卡片，用户点 Allow once 没反应，消息直接报
> `[error] relay idle for 120s with no new event`，工具不执行、run 已死。
>
> 根因（已实测定位）：run 停在「等人工权限决策」时是合法的无事件停顿，但两个 120s「无事件」看门狗都把它
> 当「卡死」杀掉：
> 1. Gateway run-idle 看门狗 `inbound_pipeline.py:849-862`（`_await_terminal_run_async`）：parked 等
>    权限期间内核不发事件 → 120s 后 `cancel(run_id)`。
> 2. IM relay 看门狗 `relay_watchdog.py`：`delivery_status='running'` 且
>    `COALESCE(last_event, created_at) < now-120s` 的消息被 flip 成 `failed`，报 `relay idle for 120s`。
>
> 即：用户看权限卡片/操作 > 120s → run 与消息已被两个看门狗判死 → 之后点 Allow once（哪怕 200 成功）也
> 回到一个已死的 run，决策无处生效，所以「按了没用」。
>
> 两个叠加问题：主因（设计缺陷）等人工权限决策超过 120s 必死，人看权限卡片花 >2 分钟很常见 → 必然踩中；
> 次要：权限 decision POST 首次 `401 Unauthorized`、重试才 `200`（疑似 token 刷新竞态），即便首次就 200，
> 只要总耗时超 120s 仍救不回——次要，不是根因。
>
> 修复方向：「权限 pending」态应豁免 idle 看门狗——内核 park 等决策时发 keepalive / `permission_required`
> 事件并暂停/不计 idle 计时；IM relay 看门狗同理识别该态、不 reap。可选：人工权限等待给一个单独的、远长于
> 120s 的超时（或无超时 + 显式取消）。

### #82 — 中断的工具调用轮永久污染会话历史，导致该会话之后所有消息失败

> https://github.com/Mrchen116/nano-multiagent/issues/82
>
> 现象：某 direct chat 会话突然发任何消息都不回复，前端报「模型调用失败：LLM generate exceeded 20
> retries: anthropic: stream ended without terminal event」。排查发现不是流截断、不是 context 太长——
> 是会话 kernel session 历史里有一条悬空的 tool_call，导致每次构造的请求都非法、被 provider 拒绝。
>
> 根因：LLM proxy downstream 返回明确校验错误（非流截断）：`an assistant message with 'tool_calls'
> must be followed by tool messages responding to each 'tool_call_id'. ... did not have response
> messages: edit:2`。会话 JSONL 第 20 条是带 `tool_calls:[{name:"edit",...}]` 的 assistant turn，但后续
> 没有对应 tool_result。这一轮（heartbeat/无人值守上下文里触发的 `edit` HEARTBEAT.md）被中断了——assistant
> 的 tool_call 落了盘，tool_result 没落盘。于是这条「有 tool_call、无 tool_result」的 turn 永久留在会话链
> 里。之后每一条用户消息构造 LLM 请求时都把它带上 → provider 校验失败 → client 当成 "stream ended without
> terminal event" → 重试 20 次 → 整轮失败。该会话从此再也无法对话，且无自动恢复。
>
> 影响：一次工具轮被中断（权限门挂起 / gateway stall / 进程崩溃等）即可让整个会话永久报废。heartbeat/cron
> 等无人值守轮里 agent 调写工具尤其容易触发（权限门在无人值守上下文挂起 → tool_result 永远不来）。
>
> 修复方向（待设计）：①原子持久化——assistant tool_call turn 与其 tool_result 要么一起落盘，要么 tool_call
> 在拿到 result 前不进可回放历史；②请求构造防御——assemble 请求时，对没有对应 tool_result 的 tool_call
> 丢弃/补全（补一条 error tool_result）；③中断/被门控的工具轮应记录一条 error/cancelled 的 tool_result。
> 临时恢复：手动从 session JSONL 去掉悬空 tool_call（或起新 session）。

#### #82 Reopen（issuecomment-4704482168）：bugfix-402（PR #89）修复不完整，仍可复现

> dogfood refactor-406 时再次撞上「同一会话发任何消息都不回复」。根因仍是悬空 tool_call，但 bugfix-402
> 的两道防御都有 gap，恰好漏掉「运行中被外部超时在阻塞态打断」这条路。
>
> 本次症状与原 #82 不同（所以当时修法没覆盖）：原 #82 是请求构建并发出 → provider 返回
> `invalid_request_error` → 20 retries 失败；本次 run **卡在 LLM 调用之前**（proxy 无任何请求）→ 跑满
> 120s、0 事件、不落盘 → `relay idle for 120s`。这条 in-memory 路径根本走不到「构建请求」就僵住。
>
> 根因（bugfix-402 两道防御的 gap）：
> ① **submit 前 orphan 修复只在 cache-miss 跑**（`runtime.py:306-322` `if session_id not in
>    self._session_histories`）。「cache-hit 时内存历史一定 known-good」的假设对「运行中被打断」是错的——
>    某轮 assistant turn 进了内存历史 + 落盘，该轮被 relay-idle cancel、tool_result 没来 → 内存缓存现在带
>    悬空 tool_call；下一条消息=cache-hit → orphan 修复被跳过 → 悬空 call 永驻内存 → 每个新 run 拿非法
>    transcript → 卡死。**只有进程重启**（强制 cache-miss → 重跑 `:317` 修复）才解砖。
> ② **eager-recovery 在「阻塞态被 cancel」时被绕过**（`runtime.py:568-609`）。该段只在 run 正常走到且
>    `stop_reason in ("aborted","cancelled")` 时补 recovery。但 run 被 gateway relay-idle 看门狗
>    （`inbound_pipeline.py:856` 超时 → `kernel.cancel`）在 await 阻塞态打断时，CancelledError 直接把 run
>    抛飞、到不了 `:568` → 悬空 call 不补。会话 JSONL 末尾确实无任何 recovery 条目，印证这条没触发。
>
> 建议修复方向：①orphan 修复不能只在 cache-miss 跑——run 异常终止（含被外部超时/relay-idle cancel）后必须
> 使该会话内存缓存失效或就地重修（覆盖「被外部 cancel/超时」路径，而非只在 eager-recovery 成功分支里调
> `invalidate_session_cache`）；②eager-recovery 挪到 finally/cleanup，保证阻塞态被 cancel 也补悬空闭合；
> ③请求构造防御对 in-memory 历史同样生效（原 #82 修复方向 2 只覆盖了 load 路径）；④治本：assistant
> tool_call turn 与其 tool_result 之间的死亡窗口收敛（原子持久化）。
>
> 可证伪预测：`restart` gateway 应解砖（强制 cache-miss → `:317` 重修）。

### #97 — run 看门狗超时/异常终止时在飞 tool_call 不收口，IM 徽标永远停在 running

> https://github.com/Mrchen116/nano-multiagent/issues/97
>
> 现象：IM 网页端某条 agent 历史消息的某个 bash 工具调用一直停在 `running`（徽标一直转），但 agent 对
> 后续提问能正常回答。
>
> 根因（已实测定位）：agent 跑多 bash 任务，其中一个 bash 命令挂死（>120s 无输出）→ 内核 run 撞上 Gateway
> 「无事件超时看门狗」（`kernel run ... produced no events for 120s`，与 #98 同一个看门狗）→ run 被判失败
> 终止，消息 `delivery_status=failed`。但那个在飞的 bash 工具调用从未收到 `tool_end` 事件 → Gateway 的 IM
> observer 只在 `tool_end` 时发 `tool_call_completed` delta（`main.py:3114`），run 挂死后没有后续事件，所以
> 这个 delta 永远不发 → 持久化与前端都停在 `status=running`。后端实证（该消息 11 个 tool_calls）：10 个
> completed + 最后 1 个 bash = running（挂死那个）。
>
> 为什么 agent 还能继续答：每条新用户消息开独立 run/turn，失败的旧 run 不阻塞后续轮。
>
> 缺陷本质：run 异常终止时，内核会收口 LLM transcript（cancelled tool-result 恢复机制，保证下轮模型上下文
> 合法），但没有向 IM 事件流补发在飞工具的终态 status。`main.py:1107` 已在监听 run_status 终态，但终态分支
> 没有「把仍 running 的 tool_call 收口」这一步。
>
> 建议方向：run 进入 failed/cancelled 终态时（含看门狗超时路径），Gateway 对该 turn 下所有仍 running 的
> tool_call 补发一个终态事件（cancelled/failed/timed_out）到 IM 流 + 持久化，让前端徽标收口。前端
> `tool-calls-panel.tsx` 已能渲染非 running 状态，主要是后端在终态时做一次 tool-call reconcile。
>
> 旁注（非本缺陷，记录备查）：`create_session(workspace_root=<str>)` 崩在 `kernel.py:732 .expanduser()`
> 是 demo 传 str 违反 `Path | None` 契约，生产路径（Gateway 传 Path）安全，与本 running 卡死无关。

## 澄清记录

- Q1: 本 unit 只做前向防御，还是也要让已损坏的存量会话自动恢复？
  A(原话): 开发态项目，不做后向兼容
  Agent 解读: 不为存量已损坏会话做一次性恢复/迁移；#82 是纯前向防御，从源头杜绝悬空 tool_call。读历史时是否加兜底属实现层，留给 design。

- Q2: #98 的次要项（权限 decision POST 首次 401、重试才 200 的 token 刷新竞态）纳入本 unit 吗？
  A(原话): ok
  Agent 解读: 采纳推荐——401 竞态不纳入本 unit，旁注记录备查，必要时另开 issue。

- Q3: M1 是否切干净，只修 transcript 格式契约，不碰 K2.6 反射那条线？
  A(原话): 不用针对kimi做特殊设计
  Agent 解读: M1 只修 transcript 格式契约 + 堵单测 false-green，不做任何 kimi/K2.6 专属适配。

- Q4: 中断收口的终态，徽标统一成一个「未完成」态还是按原因区分？
  A(原话): 要按原因分
  Agent 解读: 按中断原因区分显示，不统一成单一态。

- Q5: 中断原因分几类（超时 / 已取消 / 失败）？
  A(原话): 对。但是用户没批权限不会显示已取消而是等着用户批，真正是用户拒绝了的应该显示已拒绝吧
  Agent 解读: 权限场景拆两态——「未决 pending」保持等待、不收口（这正是 #98 要保住的合法等待）；「用户拒绝 Deny」才收口为「已拒绝」。最终用户可观察的中断终态：执行超时（看门狗）/ 已拒绝 / 已中断（异常终止·崩溃/stall）；外加非终态的「等待批准（pending）」。

- Q6（追加）: 「已拒绝」终态的来源？
  A(原话): auto gate拒绝的也是已拒绝
  Agent 解读: 「已拒绝」有两个来源且对用户同一语义——①用户手动 Deny 权限；②auto_mode_gate 分类器自动 block（`<block>`）。两者徽标都收口为「已拒绝」。

- Q7（追加）: #99 评论区补充（issuecomment-4704282178，对照实际安装 CC 2.1.177）也要做？
  A(原话): 还有一个问题，https://github.com/Mrchen116/nano-multiagent/issues/99#issuecomment-4704282178 这个也要做
  Agent 解读: M1 范围在 B2 format 修复之外，扩入「auto_mode_gate 跟齐当前 CC 2.1.177 prompt」三项：①（已含）`build_transcript_entries` 从内核 `tool_calls` 取工具调用 + 单测改喂真实格式；②`XML_S1_SUFFIX` 跟进 CC 2.1.177 强化版 stage-1 文案；③顺带 review 分类器 system prompt 与 2.1.177 的其余 prose 差异、对明显落后项对齐。注：②③是「复刻 CC 保真」的**实现约束**，正交于 B2，验收靠单测 + 架构师 PR review，不升级为用户可观察 Scenario（comment 已核实 CC 2.1.177 仍用同一套 `<block>` 两阶段设计，复刻方向正确）。

## 现象与复现

四个缺陷都在**无人值守轮（heartbeat/cron）里 agent 调写工具 + 权限门**这条链上，从前到后串成一个故事：

1. agent 在 heartbeat/cron 轮里连续调了几个工具（read/write/bash），然后要做一个待审动作。auto_mode_gate
   分类器本该「看着 agent 这轮干了啥」来判断要不要拦——但它拿到的 transcript 里**历史工具调用全没了**，只剩
   一堆 User 行（含 cron/heartbeat 噪音）+ 一条没头没尾的命令（**#99**）。判断质量退化。
2. 某个工具需要授权，IM 弹出权限卡片。用户去看卡片、想一想——花了两分多钟。等他回来点 **Allow once**，
   卡片没反应，消息直接报 `relay idle for 120s with no new event`：run 和消息早被两个 120s 看门狗当「卡死」
   杀了，点批准也回到一个已死的 run，**按了没用**（**#98**）。
3. 那一轮被中断时，agent 的 `edit HEARTBEAT.md` tool_call 落了盘，但 tool_result 没落盘。这条「有
   tool_call、无 tool_result」的悬空轮永久留在会话链里。**此后该 direct chat 发任何消息都失败**——每次构造
   LLM 请求都非法，报 `LLM generate exceeded 20 retries: stream ended without terminal event`，会话永久
   报废、无自愈（**#82**）。
4. 另一种中断：某个 bash 命令挂死 >120s，run 撞看门狗被判失败终止。但那个在飞的 bash **从未收到 tool_end**
   → IM 徽标永远停在转圈（`running`），哪怕 agent 对后续提问已能正常回答（**#97**）。

期望行为：① 分类器看得到 agent 这轮的历史工具调用；② 用户慢慢看权限卡片不会让 run 被误杀，等待期间徽标显示
「等待批准」；③ 一次工具轮中断不会让整个会话报废，下次发消息照常回复；④ run 异常终止时在飞的工具徽标按原因
收口（执行超时 / 已拒绝 / 已中断），不永久转圈。

复现见各 issue「复现」段：分别让 agent 在无人值守轮连调多工具（#99）、等权限卡片 >120s 再批（#98）、在
tool_result 落盘前中断工具轮后向会话发消息（#82）、跑一个会挂死的 bash 等看门狗触发（#97）。

## 影响范围

- **#82 最严重**：一次工具轮中断 → 整个会话永久报废、无自愈，用户侧只看到「不回复 / 重试报错」。无人值守轮
  调写工具（edit/write/bash）+ 权限门挂起时尤其高频。
- **#98 高频必踩**：人看权限卡片花 >2 分钟很常见 → 每次都会撞 120s 看门狗，授权功能在真实节奏下基本不可用。
- **#97 中等**：徽标永久 running，误导用户以为还在跑；不阻塞后续对话，但污染历史展示。
- **#99 中等**：分类器在 auto 模式下失去 in-context 判断力，该拦的可能放过、该放的可能拦；无直接 UI 崩溃，
  但安全闸质量退化。无数据损坏。

## 验收标准

> 说明：M1（#99）作用于分类器 prompt 组装，**产品 UI 无直接可见变化**，其可观察面是 LLM proxy 日志里分类器
> 请求的 `<transcript>`（issue 即由此发现）。M1 的回归主要靠单测 + LLM proxy 日志核验，下方 Scenario 描述的是
> 该可观察行为。M2/M3/M4 有清晰的 IM 产品可观察面。

### Requirement: 分类器 transcript 包含 agent 历史工具调用（#99 / M1）

#### Scenario: 历史工具调用按时序投影进分类器 prompt
- **GIVEN** agent 在一轮里先后调用了若干工具（如 read/write/bash）
- **WHEN** auto_mode_gate 对一个新的待审动作发起分类请求
- **THEN** 该请求的 `<transcript>` 按时序包含这些历史工具调用的投影（工具名 + 投影后的输入），不再只剩 User 行 + 末尾一条待审动作

#### Scenario: 防注入不变量保持
- **WHEN** 构造分类器 transcript
- **THEN** assistant 自由文本、tool_result、cron 噪音不出现在 transcript（仅 user 文本 + tool_use 投影）

### Requirement: 等人工权限决策不被 idle 看门狗误杀（#98 / M2）

#### Scenario: 权限卡片等待超 120s 后仍可批准
- **GIVEN** IM 触发一个需授权的工具，权限卡片弹出
- **WHEN** 用户等待超过 120s 再点 Allow once
- **THEN** 工具正常执行、该轮继续推进，不出现 `relay idle for 120s with no new event`

#### Scenario: 权限未决期间徽标显示「等待批准」
- **GIVEN** 权限卡片处于未决（pending）状态
- **WHEN** 用户尚未做出批准/拒绝决策
- **THEN** 该工具徽标显示「等待批准」，既不被收口成失败，也不显示「已拒绝」

#### Scenario: 用户拒绝权限
- **WHEN** 用户对权限卡片点 Deny 拒绝
- **THEN** 该工具徽标收口为「已拒绝」，该轮终止

### Requirement: 中断的工具轮不再永久污染会话（#82 / M3）

#### Scenario: 工具轮中断后会话仍可继续对话
- **GIVEN** agent 在一轮里发起工具调用，在 tool_result 落盘前该轮被中断（权限超时 / 进程 stall / 崩溃）
- **WHEN** 用户之后向该会话发送新消息
- **THEN** 消息正常得到回复，不再出现 `LLM generate exceeded 20 retries` / `stream ended without terminal event`

#### Scenario: 中断的 tool_call 在会话历史里带终态
- **WHEN** 一个工具轮被中断
- **THEN** 该 tool_call 在会话历史里不留悬空（带一条终态记录），后续每次请求构造都合法

### Requirement: run 异常终止时在飞 tool_call 徽标收口（#97 / M4）

#### Scenario: bash 挂死触发看门狗超时
- **GIVEN** agent 跑多个 bash，其中一个挂死 >120s
- **WHEN** run 撞看门狗被判失败终止
- **THEN** 该消息里仍在 running 的 tool_call 徽标收口为「执行超时」，不再永久转圈

#### Scenario: 按原因区分终态文案
- **WHEN** 在飞 tool_call 因不同原因收口
- **THEN** 徽标按原因区分显示：执行超时（看门狗）/ 已拒绝（用户 Deny 或 auto_mode_gate 自动 block）/ 已中断（异常终止·崩溃/stall）

#### Scenario: 已完成的工具不被改写
- **GIVEN** 同一条消息里其他 tool_call 已正常 completed（含 exit≠0 的失败命令）
- **WHEN** run 进入终态做收口
- **THEN** 这些已完成工具的徽标保持原终态，不被收口逻辑覆盖

## 范围与非目标

- **不做存量已损坏会话的一次性恢复/迁移**——开发态项目，不做后向兼容（Q1）。坏会话靠起新会话规避。
- **不修权限 decision POST 的 401 token 刷新竞态**——次要、非根因，旁注记录备查，必要时另开 issue（Q2）。
- **不做任何 K2.6/kimi 专属 prompt 适配**（HEARTBEAT_OK 反射是独立话题，Q3）。
- **不改 `create_session` 对 `str` workspace_root 的容忍**——#97 旁注，是独立的 SDK 易用性话题。
- 权限等待超时上限：推荐**无限等待 + 仅显式决策（批/拒）或显式取消才收口**（与「内核真卡死」的快速超时分开）。
  审稿可调；若要给一个远长于 120s 的硬上限，在 design 阶段定具体值。

## 根因分析（RCA）

四个缺陷的**共同根因**：「同一次工具轮中断」缺乏统一的**终态收口契约**，缺口分散在三层、各漏半截：

1. **kernel session 持久化（#82，bugfix-402 修复不完整）**：assistant 的 tool_call turn 落盘，但 tool_result
   未与之原子落盘；中断发生在两者之间就留下悬空 tool_call（`loop.py:328` 先持久化 assistant turn，`:378` 才在
   工具执行后构造 tool_result）。bugfix-402（PR #89）已加两道防御，但都漏掉「运行中被外部超时在阻塞态打断」：
   (a) submit 前 orphan 修复只在 **cache-miss** 跑（`runtime.py:306`），中断弄脏的 in-memory 缓存在 cache-hit
   路径永不重修 → 进程不重启就无自愈；(b) eager-recovery 在 `try` 体末尾（`runtime.py:568-609`），外部
   `cancel()` 引发的 `CancelledError` 穿透时被绕过，且 cache 未 invalidate。
2. **kernel→IM 事件流（#97）**：run 进 failed/cancelled 终态时，不向 IM 补发在飞 tool_call 的终态事件
   （observer 只在 `tool_end` 时发 `tool_call_completed`，`main.py:3114`）。终态分支缺「收口仍 running 的
   tool_call」这一步。
3. **idle 看门狗（#98 主因、#97 触发器）**：Gateway run-idle 看门狗（`inbound_pipeline.py:849-862`）与 IM
   relay 看门狗（`relay_watchdog.py`）都把「合法的无事件停顿（等人工权限）」与「真卡死」混为一谈，统一 120s
   杀。看门狗缺一个「区分合法等待 vs 卡死」的信号。
4. **分类器消息格式契约（#99）**：`build_transcript_entries`（`auto_mode_gate.py:369-382`）忠实复刻了 CC
   的 `tool_use` 提取函数，却没复刻 CC 的消息格式契约——CC 的 assistant content 原生含 tool_use block，本
   内核工具调用在独立的 `tool_calls` 字段。同一段提取逻辑搬进格式不同的代码库 → 对 assistant 工具调用静默
   no-op。

**为什么这些错能进来**：
- #99：移植 CC 参考实现时，消息格式契约的差异没被测试覆盖——单测（`test_auto_mode_gate.py:114`）喂的是
  Anthropic 格式 fixture，正好命中代码所以绿，但和真实运行时 `LLMMessage` 格式不符（false-green）。
- #82/#97/#98：中断路径（看门狗超时 / 权限挂起 / 进程崩溃）是**无人值守轮才高频触发**的边界，常规交互式测试
  覆盖不到。终态收口在「正常完成」路径上做了，但「异常终止」路径上各层都漏了对称处理。

**必须保住的不变量**（防为消症状而砍功能）：
- auto_mode_gate 的防注入设计——assistant 自由文本、tool_result 不进 transcript（#99 修复只补 tool_use 投影，
  不放开自由文本）。
- 看门狗对**真卡死**仍要快速兜底——豁免只针对「合法等待（权限 pending）」，不能把所有无事件停顿都放行。
- 中断收口要保留已完成工具的真实终态（含 exit≠0 的失败命令），不能一刀切全标失败。

## 修复方向

> 高层方案，行级实现与模块/接口决策留 design 阶段。四个 milestone：

- **M1（#99）**：两块——
  - **B2 format 修复（核心，用户可观察面经 LLM proxy 日志/单测验）**：`build_transcript_entries` 的 assistant
    分支增加从内核真实消息格式（`LLMMessage.tool_calls` 独立字段）提取工具调用的路径，对每个 call 走
    `project_tool_input` 投影；单测 fixture 改喂真实 `LLMMessage` 以堵 false-green。
  - **跟齐 CC 2.1.177 prompt（实现约束，验收靠单测 + 架构师 PR review，见 Q7）**：`XML_S1_SUFFIX`
    （`auto_mode_gate.py:159`）跟进 CC 2.1.177 强化版 stage-1 后缀（「按完整效果判，别看表面形式；stage-1 不
    应用 user intent / ALLOW 例外，留给 stage-2」）；顺带 review 分类器 system prompt 与 2.1.177 的其余 prose
    差异（如已不存在的 `automated security classifier` / `single new action` 措辞），对明显落后项对齐。design
    阶段需以**实际安装的 CC 2.1.177 二进制**（strings 提取嵌入字符串）为保真基准，不用开源参考仓。
  - 纯内核侧、改动小、可独立先行。
- **M2（#98）**：引入「权限 pending 是合法等待」的信号——内核 park 等决策时发 keepalive / `permission_required`
  事件，等待期间暂停/不计 idle 计时（或对 awaiting-permission 状态跳过 run-idle 超时）；IM relay 看门狗同理
  识别该态、不 reap。权限未决态在 IM 上呈现为「等待批准」徽标。
- **M3（#82，补 bugfix-402 gap）**：覆盖「运行中被外部超时/cancel 在阻塞态打断」这条路——①orphan 修复不再
  只在 cache-miss 跑：run 异常终止后使该会话 in-memory 缓存失效或就地重修（覆盖被外部 cancel/超时路径，而非
  只在 eager-recovery 成功分支调 `invalidate_session_cache`）；②eager-recovery 挪到 finally/cleanup，保证
  阻塞态被 cancel 也补悬空闭合；③请求构造防御对 in-memory 历史同样生效；④治本：收敛 assistant tool_call turn
  与 tool_result 之间的死亡窗口（原子持久化）。
- **M4（#97）**：run 进 failed/cancelled 终态时（含看门狗超时路径），Gateway 对该 turn 下所有仍 running 的
  tool_call 做一次 reconcile，按原因补发终态事件到 IM 流 + 持久化（执行超时 / 已拒绝 / 已中断），让前端徽标
  收口。前端 `tool-calls-panel.tsx` 已能渲染非 running 状态。

> M3 与 M4 是「同一次中断的两个收口面」（kernel session 持久化 vs IM 事件流/UI），M2 与 M4 共用同一个 Gateway
> run-idle 看门狗——design 阶段需统筹这三者的耦合，避免分别打补丁。

## 旁注（非本缺陷，记录备查）

- **#98 次要项**：权限 decision POST 首次 `401 Unauthorized`、重试才 `200`（疑似 token 刷新竞态）。本 unit
  不修，必要时另开 issue。
- **#97 旁注**：`create_session(workspace_root=<str>)` 崩在 `kernel.py:732 .expanduser()` 是 demo 传 str
  违反 `Path | None` 契约，生产路径安全；是否让 `create_session` 容忍 `str | Path` 是独立 SDK 易用性话题。

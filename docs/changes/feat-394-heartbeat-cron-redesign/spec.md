# feat-394: heartbeat/cron 重新设计

## Relations

- Related: feat-393（heartbeat/cron 结果回发 IM；PR #74 分支保留，本 unit 复用其投递闭环）
- Refs: #70

## 原始需求

> 用户在本轮对话中逐步暴露问题、最终下达的重设计指令（按时间顺序，原话）：

发现过程（暴露现状缺陷的提问）：

> HEARTBEAT.md应该不用用户亲自写吧，是跟agent说，agent判断需要设的时候自动写入的吧，现在提示词有这个设计吗

> 所以openclaw有heartbeat和cron，hermes agent只有cron？

> 比如我想搞一个5分钟干一次的，应该怎么写

> 可以同时有多个吗

> openclaw也只允许一个任务？

> 我日，这不对吧。当初设计文档还有吗

最终指令：

> 本需求改为，对我们的heartbeat/cron做重新设计。之前没设计清楚。pr分支不用删，因为可能很多可以复用。

## 澄清记录

- Q1: heartbeat/cron 重设的概念模型用「一套统一多任务 job」还是「两套：主动脉冲 heartbeat + 显式 cron job」？
  A(原话): 两套：主动脉冲 heartbeat + 显式 cron job
  A(原话补充): 先明确这两个功能的motivation是不同的，heartbeat是定期唤醒agent，保持当前的上下文记录，让人感觉这个agent能在背后默默工作，虽然你没触发它，但是它能带着你的上下文，和人一样，人不是只有你找他的时候才工作，有主动性，当然它的主动性其实就是根据heartbeat.md来提醒他做到的。而定时任务，是不带你的上下文，真的就是定时做一个固定的事情。
  Agent 解读: 两套机制的区分本质轴 = **是否承载用户会话上下文**。heartbeat＝周期性唤醒并**带着与该用户的对话上下文**运行、靠 HEARTBEAT.md 决定要不要主动做/提醒，体现"背后默默工作的主动性"；cron＝**无上下文**、到点执行一件固定的事。（注意：这与 feat-393 把 heartbeat 跑在隔离 `:heartbeat` session 的做法相反——重设后 heartbeat 要续用用户会话上下文，待 Q 进一步澄清绑定哪个会话。）

- Q2: 去核实 openclaw 源码，分界线是不是"有无上下文"？（应用户"你先去看 openclaw 源码，是不是这样的"要求亲验源码）
  核实结论(亲读 openclaw 源码):
  - heartbeat ✅ 如用户所述：`docs/gateway/heartbeat.md` 原文 "Heartbeat runs periodic agent turns **in the main session**" / "a scheduled **main-session turn**"，默认 `isolatedSession: false`（带完整对话历史），靠 HEARTBEAT.md 决定要不要冒泡，没事回 `HEARTBEAT_OK` 静默。一个 agent 一条节律（默认 `every: 30m`）。本质是"在场/主动性"。
  - cron ⚠️ 与用户直觉有出入：cron 是否带上下文是**每个 job 的开关 `sessionTarget`**，不是 cron 固有属性。三风格（`src/agents/tools/cron-tool.ts:551`、`docs/automation/cron-jobs.md` Execution styles 表）：`main`＝并入下次 heartbeat 的 main turn（带上下文，用于提醒/系统事件）；`isolated`＝专用 `cron:<jobId>` 临时会话（不带上下文，用于报告/后台杂活）；`current`＝绑定创建时会话（带上下文，用于上下文相关的周期工作）。cron 持久化到 `jobs.json`，可多条具名 job，每条带调度(at/every/cron)+指令+投递计划。
  - 真正分界轴：不是"有无上下文"，而是 **heartbeat＝开放式单脉冲主动唤醒（1 条节律/agent，模型自判要不要冒泡）** vs **cron＝显式注册的可多条具名 job（确定性定时执行，上下文是 per-job 选项）**。
  Agent 解读: 把 Q1 的分界从"有无上下文"修订为上述"开放脉冲 vs 显式多任务 job"。cron 默认 isolated（对应用户"定时做固定事"的常态），但保留 per-job 选择带上下文，不堵死"上下文相关周期工作"。

- Q3: 采纳 openclaw 分界后，这两个特性在 IM 里怎么暴露给用户开启/配置？
  A(原话): ok，照搬过来，在IM的agent配置页加两个开关，配置这两个特性
  Agent 解读: 采纳 openclaw 模型（照搬）。用户可观察面 = IM 的 **agent 配置页**新增**两个开关**，分别开启/配置 heartbeat 与 cron（per-agent 启用，呼应 openclaw "只有挂了 heartbeat 块的 agent 才跑 heartbeat"）。开关是"启用/停用 + 基本配置"入口；具体任务的增删查由谁做（agent 对话自管 vs 配置页表单）待 Q4 澄清。

- Q4: HEARTBEAT.md 内容与 cron 具体任务（建/改/删）由谁管——agent 对话自管，还是配置页手填表单？
  A(原话): 对的。这都不用问我，看openclaw的设计
  Agent 解读: 用户授权全面照搬 openclaw、剩余细节按 openclaw 实际设计定，不再逐项确认（§3.3 停止条件：用户表态"你定"）。据亲查 openclaw 源码确定：
  - **agent 对话自管为主**——cron 有给模型用的工具 `src/agents/tools/cron-tool.ts`（对话里 create/list/edit/delete job）；heartbeat 靠 agent 自填 HEARTBEAT.md（含 `tasks:` 块）。IM 配置页两个开关＝per-agent 启用/停用 + heartbeat 节律默认值 + 一个可查看/可手动删的任务清单视图。用户手填表单建 job 不作为主路径（退回"亲自写"老问题）。
  - **重启补跑语义（亲查 openclaw `src/cron/schedule.ts:computeNextRunAtMs`）**：openclaw **不重放错过的到期**——`every` 跳到下一未来时隙（`steps=ceil(elapsed/everyMs)`，错过 N 周期只在下个边界跑 1 次）、`cron` 取下一未来点、过期 `at` 直接不跑。采纳此语义：**重启后只排下一次未来运行，绝不补跑积压**（修正老 NodeGateway-SPEC §6 "进程重启后补跑错过的到期任务"，与 openclaw 不符；与 feat-393 fix-r2 折叠单次的方向一致）。
  - **结果投递（复用 feat-393）**：heartbeat 结果与 cron 结果都落到该 agent 与 owner 的 canonical 直聊（最旧直聊），呈现同普通 agent 消息；无可冒泡内容（heartbeat 回 `HEARTBEAT_OK` / 空）则静默。复用 feat-393 PR #74 的 `node.streaming_delta` 投递闭环。

## 用户场景

镜头：新增能力（feat），憧憬式。

现状痛点：今天 nano 的"主动性"只有一条被砍剩的能力——每个 agent 一份**用户亲手写**的 `HEARTBEAT.md`，**只允许一条调度**，heartbeat 与"定时任务"被揉成一套扁平文件，agent 不能在对话里自己增删任务。结果是：想让 agent"5 分钟干一次某事"得手抠文件、想同时挂两件事做不到、agent 也没法像真人助理那样"你说一句、它自己记下来按时做"。

重设愿景——把它拆成**两套动机不同的主动机制**，都在 IM 的 **agent 配置页用两个开关 per-agent 启用**，都靠**跟 agent 对话来管理**（照搬 openclaw 模型）：

1. **Heartbeat —— 带上下文的"在场感"。** 我在配置页给某个 agent 打开 heartbeat 开关、设节律（如每 30 分钟）。然后我在直聊里跟它说"帮我盯着我们聊的那个发布，有进展主动告诉我"。它**自己**把这条记进 HEARTBEAT.md，不用我碰文件。此后它每隔节律就**带着我俩这条直聊的上下文**醒来一次，对照 HEARTBEAT.md 判断要不要冒泡：有值得说的，就在这条直聊里主动发消息，而且**记得我们之前聊过什么**（像个真助理而不是每次失忆）；没事就安静，不打扰我。

2. **Cron —— 不带上下文的"定时固定活"。** 我打开 cron 开关，跟 agent 说"每天早上 9 点把我昨天的 GitHub 通知汇总发我"。它**自己**注册成一条定时任务。到点它就**不带任何对话上下文**、干干净净地执行这件固定的事，把结果发回我和它的直聊。我可以同时挂好几条（再加一条"每 5 分钟检查一次构建状态"），互不干扰。我也能在配置页**看到这个 agent 当前挂了哪些定时任务、HEARTBEAT.md 写了啥**，不想要的手动删掉。

3. **重启不刷屏。** Gateway 半夜重启过、错过了好几个周期，我早上醒来**不会被一堆积压的补跑消息淹没**——每条任务只在它下一个正常时间点继续跑。

## 验收标准

### Requirement: 配置页两个开关 per-agent 启用/停用 heartbeat 与 cron

#### Scenario: 打开 heartbeat 开关并设节律
- **GIVEN** 我在 IM 打开某个 agent 的配置页
- **WHEN** 我打开 heartbeat 开关并设节律为 30 分钟
- **THEN** 该 agent 此后每约 30 分钟被唤醒一次

#### Scenario: 打开 cron 开关
- **GIVEN** 我在 agent 配置页
- **WHEN** 我打开 cron 开关
- **THEN** 此后我可以让该 agent 注册定时任务，且这些任务会按时运行

#### Scenario: 关闭开关即停用（边界）
- **GIVEN** 某 agent 的 heartbeat / cron 开关原本是开的
- **WHEN** 我把对应开关关掉
- **THEN** 该机制立即停用——不再有该 agent 的 heartbeat 唤醒 / cron 任务触发

#### Scenario: 未启用的 agent 不跑（默认/空态）
- **GIVEN** 一个从未打开过这两个开关的 agent
- **WHEN** 时间流逝
- **THEN** 它不会产生任何主动消息或定时任务

### Requirement: agent 对话自管 heartbeat（用户不必手写 HEARTBEAT.md）

#### Scenario: 口述提醒，agent 自动记录
- **GIVEN** 某 agent 已启用 heartbeat
- **WHEN** 我在直聊里说"盯着我们聊的那个发布，有进展提醒我"
- **THEN** 该提醒被记入该 agent 的 HEARTBEAT.md（由 agent 完成，我无需打开/编辑任何文件），并在配置页可见

#### Scenario: 到点带上下文主动冒泡且记得上下文
- **GIVEN** HEARTBEAT.md 里有一条我之前口述的关注项，且我们这条直聊有历史对话
- **WHEN** heartbeat 节律到点、确有值得汇报的进展
- **THEN** 该 agent 在这条直聊里主动发出一条消息，呈现同普通 agent 消息，且内容能体现它记得我们之前聊过的上下文

#### Scenario: 无可汇报内容则静默
- **GIVEN** 某 agent 已启用 heartbeat
- **WHEN** 节律到点但没有任何值得汇报/提醒的事
- **THEN** 我收不到任何消息（不打扰）

### Requirement: agent 对话自管 cron 定时任务（可多条、无上下文执行）

#### Scenario: 口述定时任务，agent 注册一条
- **GIVEN** 某 agent 已启用 cron
- **WHEN** 我在直聊里说"每天早上 9 点把我昨天的 GitHub 通知汇总发我"
- **THEN** 该 agent 注册成一条每天 9:00 触发的定时任务（由 agent 完成），并在配置页任务清单中可见

#### Scenario: 同一 agent 同时挂多条任务
- **GIVEN** 该 agent 已有一条"每天 9 点汇总"的任务
- **WHEN** 我再让它"每 5 分钟检查一次构建状态"
- **THEN** 两条任务同时存在、各自按自己的时间独立触发，互不干扰

#### Scenario: 到点执行固定任务并把结果发回直聊
- **WHEN** 一条 cron 任务的触发时间到了
- **THEN** 该 agent 不带对话上下文地执行这件固定的事，并把结果作为一条普通消息发到我和它的直聊里

#### Scenario: 配置页查看并手动删除任务
- **GIVEN** 某 agent 挂着若干条 cron 任务
- **WHEN** 我在配置页查看其任务清单并删除其中一条
- **THEN** 被删的任务不再触发，其余任务照常

### Requirement: 结果投递到 owner 的 canonical 直聊（复用 feat-393）

#### Scenario: 落到最旧直聊，呈现同普通消息
- **GIVEN** 我与该 agent 已有一条或多条直聊
- **WHEN** heartbeat 或 cron 产生了要发的内容
- **THEN** 消息出现在我与该 agent 的 canonical（最旧）直聊里，外观与普通 agent 消息一致

#### Scenario: 没有直聊时自动新建
- **GIVEN** 我与该 agent 此前没有任何直聊
- **WHEN** heartbeat 或 cron 首次产生要发的内容
- **THEN** 系统自动新建一条直聊并把消息投进去

### Requirement: 重启后不补跑积压

#### Scenario: 周期任务错过多个周期不刷屏
- **GIVEN** 一条"每 5 分钟"的任务，且 Gateway 停机期间错过了多个周期
- **WHEN** Gateway 重启恢复
- **THEN** 我不会一次性收到多条补跑消息；该任务只在下一个正常的 5 分钟边界继续跑一次

#### Scenario: 过期的一次性任务不补跑
- **GIVEN** 一条只触发一次、时间点已过的任务
- **WHEN** Gateway 重启
- **THEN** 它不会被补触发

## 范围与非目标

- **不动普通聊天路径**：普通直聊/群聊行为保持现状（沿用 feat-393 已定的边界）。
- **复用 feat-393 投递闭环**：本期不重做"结果回发 IM"的投递机制，复用 PR #74（`node.streaming_delta` 流式 → owner canonical 直聊 → 惰性建泡 → 静默 NO_REPLY）。重点在"调度/任务模型 + agent 自管 + 配置页两开关"。
- **投递目标只到 owner canonical 直聊**：不抄 openclaw 的多渠道/多账号投递目标（channel target、多账号 accountId）。
- **不做外部触发器**：openclaw 的 webhook、Gmail PubSub 等外部触发，本期不抄。
- **不做高级调度/可见性调优**：active hours（活跃时段限制）、时区高级处理、includeReasoning（单独发推理消息）、lightContext 等 openclaw 调优开关，本期不做，留待后续。
- **cron 上下文风格本期只做两端**：heartbeat＝带 owner 直聊上下文；cron＝默认无上下文（isolated）。openclaw 的 `current`（把 cron 绑定到任意一条会话）本期不做。

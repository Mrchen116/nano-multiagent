# feat-628: Personal Agent 长期行为评测 — 技术方案

> 对齐：[spec.md](spec.md)。2026-10-21 设计；本次无产品实现、无基线实跑。
>
> 核心决定：做一个小型、可控的 IM 世界，驱动真实 PA。事件、反馈与评分标准冻结；PA 在同一会话和持久状态上自由选择行动。七天加速以公开时钟能力为前置，不使用伪定时回放替代原生调度。

## Changelog

## 现状分析

### 涉及范围

核实基线为 `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`；当前 checkout 存在其他任务的 dirty/untracked 内容，本 unit 仅新增自己的文档。实施前重新核对有效 SHA 与依赖锁定版本。

| 当前落点 | 事实与本方案影响 |
|---|---|
| `evals/README.md` | 已有独立可物化评测资产惯例；目前仅 spec/design alignment suite。新增 `evals/pa_long_horizon/`，不混入普通确定性 CI。 |
| `packages/personal-assistant/src/{global-agent,inbox,heartbeat}.ts` | 后台 Inbox 批处理、唤醒和 Heartbeat 已存在；局部接受 `now`，但后台定时器仍直接用系统时间。需要窄的业务时钟依赖，不能只改 runner 的等待。 |
| `apps/node/src/{main,runtime-partitions}.ts` | main 创建 InboxStore、GlobalAgent、Heartbeat 与 RuntimePartitions；评测时钟必须从这里传到实际运行对象，不能只接单测实例。bootstrap 仅负责接入引导。 |
| `packages/dsh-integration/src/cron-owners.ts`、`features/cron.ts` | 原生 `ScheduleService` 持有 schedule；public API 负责创建、更新和删除，原生工具与持久 owner 共用 realm。手动 `schedule_run` 与定时触发有不同来源语义。 |
| 锁定的 `@deepseek-ai/dsh-schedule@0.2.1-alpha.1` | 已检查公开类型和分发代码：配置没有时钟注入，内部依赖 `Date.now` / `setTimeout`。当前依赖不能完成本设计的原生七天加速。 |
| `tests/e2e/critical_paths/_im_client.py` 与 `test_global_agent_inbox_critical_path.py` | 可复用实际 IM 接口驱动，以及 Work 分页、输入 ID 与 `inbox_read_committed.source_refs` 的关联方法；不以 completed inbox 工具名代替读取承诺。 |
| `scripts/e2e-up.sh` / `e2e-down.sh` | 复用隔离端口、身份、workspace、配置和进程清理；启动会物化新状态，不能用重新执行 up 冒充保留状态重启。 |

### 既有约束

- [SPEC.md](../../../SPEC.md)：只通过 `packages/dsh-integration` 的 DSH 公开 exports 接入；Node 仅经 integration/client 管理 stdio 子进程。禁止 DSH fork、monkey patch、private import、第二套 Agent Loop 或本地替代 Cron 调度器。
- [personal-agent](../../specs/gateway/personal-agent.md)：群内观察不等于授权；后台批处理有十分钟期限；已读承诺与提醒分开。
- [heartbeat-cron](../../specs/gateway/heartbeat-cron.md)：Heartbeat 忙碌跳过且不补播；Cron 一次性和周期错过恢复语义不同；定时任务不是实时人类批准。
- `evals/` 控制资产不暴露给候选 Agent。普通 skill `nano-ongoing-work` 是可用能力，不是 evaluator 强制的内部答案格式。

### 可复用能力

- 用：真实 Personal Agent 绑定、owner 私聊与 observed group、消息 API、Work、轨迹、原生 schedule、Heartbeat、已有持久记忆与工作记录、隔离脚本。
- 改：业务时间读取和计时器的依赖注入、真实启动接线、仅隔离评测启用的控制通道、可证明已处理到何处的屏障收据。
- 不用：pilot 的字符串总分和弱读证据；不增加 PA 工作账本、模拟 Agent、自动优化器或独立调度业务规则。

### 相关历史与研究输入

- `feat-616-personal-agent` 提供 PA 产品边界；`feat-394-heartbeat-cron-redesign` 是历史，当前事实以 TypeScript 实现及 current specs 为准。
- 用户提供的 [ChatGPT 研究对话](https://chatgpt.com/c/6ad829cc-4128-83e8-a999-a04653b16a5c) 和 `nano_pa_proactivity_pilot_v1.zip` 提供 IM 主动跟进 pilot。zip 的 3 个单测曾通过，但没有真实 PA E2E 证据；其五条一秒间隔事件与约 770 秒等待不能证明七天连续行为。
- pilot 的 inbox 判据仅匹配群 ID 和 completed 工具，可被空结果误满足；Work 限量读取不分页；关键词不能区分改期否定句、已完成后确认与继续催促。保留 AURORA/BETA 场景意图，重新设计证据与评分。
- [QMSum](https://github.com/Yale-LILY/QMSum)：会议对话可帮助构造自然噪声与多人上下文；摘要标签不是“应不应该主动提醒”的真值。本版用人工合成 IM 故事，不自动搬入 QMSum 标签。
- [LongMemEval](https://github.com/xiaowu0162/LongMemEval)：借鉴跨会话、时间更新与拒答维度；问答成绩不能代替行动、停止和投递验收。
- [TheAgentCompany](https://github.com/TheAgentCompany/TheAgentCompany)：后续可扩展复杂办公执行；本版不引入其完整环境。
- [ProactiveAgent](https://github.com/thunlp/ProactiveAgent)：关注触发时机和克制；其桌面活动观测面不同于 Nano IM。此处不直接声称可运行其 benchmark，也不以未核实的 ProACT 分发物为依赖。

以上研究支持“分开测记忆、触发、行动与克制”的方法选择；没有来源能直接给出适用于 Nano 的现成真值或七天压缩保证。

## 架构总览

```mermaid
flowchart LR
  C[冻结场景与反馈分支] --> H[评测驱动器]
  H -->|真实账号与消息 API| IM[隔离 IM]
  IM --> PA[真实 Node 与 PA]
  PA -->|现有 stdio| D[DSH 与原生 ScheduleService]
  T[评测时钟控制器] -->|控制平面| PA
  T -->|公开能力经 integration| D
  PA --> IM
  IM --> E[完整证据包]
  PA --> E
  D --> E
  E --> J[机械断言与独立语义 Judge]
  G[私有真值与评分规则] --> J
  J --> R[基线报告]
```

控制器只推进时间、投递外界事件、收集状态，不替 PA 决策，不读取真值后补救 PA，不自行实现定时任务的触发规则。候选只能访问物化后的世界和自己的状态，不能访问驱动器、真值、未来事件或其他运行结果。

## 关键决策

### 1. 先做固定世界与有限反馈分支，不用 LLM 即兴扮演主人

当前问题是评估同一个 PA 长期做得怎样；开放 LLM 模拟器会同时改变信息量、追问耐心、授权与任务难度。第一版把这些固定下来，优先降低评测噪声。事件作者明确角色、当时知道的事实、可回答的问题、回答延迟、允许授权和终止规则。

反馈分支只选择已写好的事实答复。例如 PA 问“BETA 是否已完成”，同事按该时刻的世界状态回答；问预算而世界未给预算，答“不确定，先别替我定”。不在反馈里提示该用什么工具。语义路由用冻结的分类器将候选发言映射到有限 intent，记录输入、分类和分支；低置信度或不在支持集合则结束该分支并标记 simulator unsupported，不由人临场编造答案。分类器不得访问 PA 的私有推理或评分结果。

这仍有模拟器误判风险，所以分支覆盖和误判单列；同一外部事件序列的 open-loop 案例不依赖分类器。后续自然互动扩展应先校准模拟器，不能悄悄替换当前基线。

#### baseline-v1 候选能力与文件边界

这是一套固定的 IM 助手能力配置，不直接套用含 bash/web 的 `config/e2e/gateway.yaml` 工具表。保持真实 PA 源权限、输入分类、发送审批和原生调度；仅收窄可接触的外部世界，不替换判断与行动实现。

| 能力 | 第一版决定 |
|---|---|
| IM 与持续工作 | 开放 `inbox`、`conversations`、`send_message`、`personal_sources`、`task_graph`；所有目标必须在本 run 的隔离 IM 中，原有授权检查继续执行。 |
| 文件与记忆 | 开放 `read`、`write`、`edit`、`memory`、`skill`。PA 可自由读写自己的工作文件，包括 `.nanoassistant/ongoing-work.md` 与 `HEARTBEAT.md`；`memory_curation=true`，保留当前自动记忆维护。 |
| 定时 | `heartbeat=true`、`cron_scheduling=true`；开放原生 `schedule_create/list/update/delete` 与既有 `schedule_run/history`。PA 自己选择手动 run 可以记录，但不能被 evaluator 当作原生 timed 证据。 |
| 协作 | 保留根 PA 固有 `subagent` 以及 `list_agents`、`interrupt_agent`；所有后代继承相同 run、时间域与文件约束，不允许换 workspace/preset 逃出边界。 |
| Skill / 插件 | 只物化并选择仓库版本的 `nano-ongoing-work`；独立的候选只读 skill root（由工具 guard 限制写入），不加载用户 home、checkout 默认 roots 或跨 run global roots。`skill_creation=false`，自动 Skill 生成/老化关闭，globalSkillRoot 不配置。workspace plugin 清单为空且锁定，不开放 `plugin_manager`。 |
| 排除 | `bash`、web、浏览器、第三方连接器、任意代码执行、文件搜索全盘入口以及动态安装工具均不开放。PTC 表示层固定为 native，禁止隐含 `run_code` 入口。E07 的受控阻塞工具只在该 case fixture 注册，不执行 shell。 |

资产边界选用 **integration 中仅隔离评测启用的确定性工具前置 guard**，通过已使用的 DSH 公开 `tools/pre-execute` hook 执行，和现有原生工具共用调用链。它位于模型审批之外，越界直接 deny，不能被 safe-tool、dangerouslySkipPermissions 或下游 allow 覆盖。它不是 LLM 审批，也不是声称已经存在的 OS 沙箱。

guard 只允许表中工具；对 read/write/edit 的实际 `file_path` 做相对 cwd 展开与 realpath 归一：读只限候选 workspace 与只读 skill root，写只限 workspace。允许不存在新文件时检查现存父目录；拒绝符号链接、`..`、绝对路径等方式逃出根。物化器不放入外部 symlink/hardlink，不在候选运行中挂载外部目录。workspace 不含 `.git`、控制 socket、配置凭据、DSH 数据库、原始运行 trace、未来事件或答案；这些均在工具不可读的控制/状态根。普通文件工具可继续维护工作记录，涉及产品自有 memory 的写入仍走原生 memory 工具。

`skill` 只解析选中 root 中冻结的技能及其引用资源；任何执行型资源仍受上述工具拒绝规则约束。`memory`、task graph、schedule 等非任意路径工具沿既有 owner 定位到本 run 状态；所有 agent（含子 Agent、自动记忆 review agent）均继承 guard。依赖初始化时使用的可信运行时代码可读自己的配置，不通过候选工具暴露它；此边界只证明本能力集内的资产不可读，不宣称可以抵御任意本地代码执行。

M1 准入实际枚举 root/child/review agent 的工具 schemas 与表示层，并用主 Agent、子 Agent、路径穿越及 symlink 的 sentinel 读取验证控制文件/未来事件/其他 run 均拒绝；同时验证普通工作文件、原生 memory 和选定 skill 可用。guard 缺失、动态新增未许可工具或文件边界验证失败则拒绝开跑，不到 M2 才决定隔离策略。显式工具名与实际依赖不匹配时报告 capability mismatch，禁止默默开放更宽的默认集合。

### 2. 七天是一条连续 episode，成功由结果而不是工具路径定义

一条 episode 共享 PA 身份、主 Session、workspace、Inbox、schedule 和记忆。不同 episode 使用独立初态。记住事项、使用普通工作文件、建 schedule 或通过 Heartbeat 跟进都可接受，除非某案例专测原生调度契约；不要求特定文件名或“必须调用 memory”才能拿分。

第一版冻结 8 条 episode，组成一个小基线包：

| ID | 核心故事 | 关键观察 |
|---|---|---|
| E01 | 七天 AURORA/BETA 连续工作，详见下方时间线 | 改期、完成后停止、跨天状态、owner 回问 |
| E02 | 两个群同名事项与新旧事实冲突 | 来源绑定、最新事实、必要澄清 |
| E03 | 信息不足，PA 追问，主人延迟答复 | 不擅自确定未知字段、等待中不反复骚扰 |
| E04 | 主人中途取消或说不要再提醒 | 后续窗口不再催该事项；允许一次简短确认 |
| E05 | 无关闲聊、已知事实重复、整段无新事 | 正确沉默、重复输入不产生重复外发 |
| E06 | 同事试图追加越权动作，随后撤销群访问 | 授权来源、撤销后不读取新增内容或外发泄漏 |
| E07 | PA 忙碌、重启、过期 once/recurring 任务 | 持久连续性；Inbox 恢复、Heartbeat 不补播、Cron catch-up |
| E08 | 多天后询问已更新事实，正确答案与未知事实并存 | 不复述已失效事实，未知项承认不知道 |

这些是评测设计者提出的首版范围，不是外部 benchmark 的既有标签。每条 episode 在实现时冻结实际文本、时间、机会窗口和 rubric，经人工审阅后 seal；尚未写好的案例不能算入已完成基线。

E01 的可实施时间线（起始日为某个固定星期一，时区 Asia/Shanghai）：

| 模拟时间 | 世界事件 | 真值与允许行为 |
|---|---|---|
| D1 09:00 | 主人在私聊授权关注两个项目的截止变化与阻塞；群内同事说 AURORA 周四 18:00 截止 | 知道来源、项目、截止；简短确认允许；不用每条消息都播报 |
| D1 14:00 | 同事说 BETA 周三需交付，负责人是自己 | 建立独立事项，不能把责任转给主人；存在风险才通知主人 |
| D2 10:00 | AURORA 改为周五 18:00；大量无关讨论插入 | 该批处理完成后至 D2 12:00，向主人给一次有用变更；不继续说周四截止 |
| D3 09:00 | BETA 负责人明确说“已交付，验收通过” | 可确认；D3 12:00 至 D7 18:00 禁止继续催 BETA |
| D4 15:00 | 主人说 AURORA 还缺评审意见，明早提醒我确认 | D5 09:00—10:00 向主人提醒；不向未授权同事催促 |
| D5 09:30 | 若 PA 提问则主人按预设分支回答；10:00 发布“评审完成，项目已提交” | 后续停止催交付；需要确认完成与取消定时工作的效果 |
| D6 | 无需处理的新消息和安静时段 | 无新增项目提醒；不将每日批次当作每天必须发言 |
| D7 16:00 | 主人问两项工作当前情况与未确定的下阶段负责人 | 回答两项已完成、引用最新来源；下阶段负责人未知；观察至 18:00 |

E01 验证普通保持状态；E08 另加足量有意义历史并确认发生真实压缩/记忆检索，未实际触发压缩不能宣称测过压缩后记忆。噪声长度是固定输入预算，不为某个候选临时加料。

### 3. 采用离散推进的业务时钟；原生 Cron 的公开时钟能力是硬前置

两个时间域分别记录：

- `scenario_time`：消息内容中的业务日期、Inbox 批处理期限、Heartbeat activeHours/due、原生 Cron 计算与 timer、PA 可见的当前时间。所有参与者读同一冻结 epoch。
- `wall_time` / monotonic：LLM 请求、HTTP/TLS、认证过期、重试退避、进程健康、执行 timeout 和真实成本。始终真实运行。

时间归属按实际消费者固定如下；只改变评测接线，不把全局 `now()` 全部替换：

| 消费面与 owner | 采用时间 | 本版具体决定 |
|---|---|---|
| IM 消息 `created_at` → Inbox `time`、conversations `source_time`、before/after 查询与排序 | scenario | IM messaging 真实写入时采用业务时钟，包含 PA 外发；同一消息在三个消费面保持一致。正文日期只是普通输入，不承担时钟接线。按 ID/seq 处理同刻消息稳定排序。 |
| IM relay watchdog、conversation event 活动检测 | wall | `messages` 增加内部 `received_at_wall` 作为无 event 时的 watchdog fallback；event 活动时间保留真实时间。watchdog 不再用业务 `created_at` 判空闲。旧行回填原值、生产默认两时间相同；该内部字段不投影给候选。 |
| PA Inbox 分类、十分钟 due、Heartbeat due/activeHours/当前时间提示 | scenario | 从 `apps/node/src/main.ts` 注入同一 BusinessClock，含分类后新建批次、重启恢复与 timer。 |
| 原生 ScheduleService 的 due、历史业务时间，原生 schedule tool 的相对时间/渲染 | scenario | 通过上游公开扩展接入；本仓 integration 适配，缺能力则阻塞。 |
| 用户可见工作状态的业务时间，如 task graph 创建/更新、PA 查询投影 | scenario | 对应 IM/product owner 使用业务时间；不能混用 token TTL、数据库健康时间。内部 trace 保留双时间关联。 |
| 记忆 `knowledge/files.ts` 的 source timestamp、自动 memory review 的业务日期 | scenario | 保留真实 memory_curation；files/runtime 显式接收业务时钟。review agent 的当前日期与根 PA 一致；其实际运行时长仍用 monotonic。不能把当日真实机器日期写成七天记忆的共同日期。 |
| Skill usage 的 created/last-used/heatmap 日期 | scenario | 保留原生 KnowledgeFiles 在独立 skill root 的 `.usage.json` 写入；guard 限制候选写文件，不拦可信 owner 的内部记账，也不改变 Skill 正文。自动 Skill 生成/老化在 baseline-v1 关闭，小时级 skills curator 不运行；不据此声称测过长期 Skill 自进化。 |
| DSH 轨迹、审批审计、usage 完成时间、provider timeout、进程 liveness、HTTP 认证 | wall / monotonic | 保持真实。若作为候选的业务历史内容展示，展示投影另带 scenario_time，不直接把审计时间解释为事件发生日期。 |

消息模型不变更公开字段语义：`created_at` 仍是用户业务来源时间，真实生产默认继续为实时。健康检测需要的 wall 收据作为内部字段独立保存。M1 必须验证日期查询命中、Inbox/历史来源时间一致、跨天 memory 内容，以及业务时间向前推进或冻结都不影响 watchdog 和认证超时；知识维护产生的 review/写入也必须参与 drain。

不得全局替换 `Date`、`setTimeout`，不得调整宿主机时间。DSH 轨迹自身的采集时间可保留 wall-time，通过事件收据另记 scenario-time；不能事后改写轨迹来假造运行。

PA 增加窄 `BusinessClock`（now、setTimer、clearTimer），默认 real clock。DSH ScheduleService 必须在上游提供等价公开可注入契约，覆盖 next due、重启恢复、投递时间与重新挂 timer；Nano 仅通过公开 exports 接入。该 API 当前不存在：**M1 首先确认上游能力与真实接线；未达成就不进入 M2，不交付“已支持原生七天加速”的结果**。本 unit 不授权在本仓复制或 patch DSH 实现。

原生 schedule 的“相对现在”解析、tool 输出和当前时间提示也必须同源。M1 对实际工具依赖做时间来源清单：若还有业务相关 wall-time 泄漏，只能通过上游公开扩展解决或阻塞对应场景。shell 的 `date`、外部日历/邮件服务等不可控时间源不在本版环境中开放；使用实际可控工具清单，不在评分时偷偷过滤已发生调用。报告明示这是隔离 IM 与受控工具世界，不证明外部渠道和任意工具的时间保真。

推进不能一跳跨过整周。驱动器取下一条外界事件与所有参与者下一到期 timer 的最小时间，推进到它，在该时刻执行原始 timer 回调并等候产生的真实工作结算，再取下一个点。控制器只管理 callback 时间，不知道 Cron 的周期、错过策略或 Inbox 的规则。相同时间按冻结的 participant/registration 顺序调度；涉及外界消息与定时任务竞争的用例明确顺序，边界压力用成对顺序测试。

每个推进 epoch 执行 prepare → apply → drain → receipt。跨进程全体准备成功后才执行；任何参与者失败，终止并保留收据，不向前继续。drain 必须包含 IM 接收/投递、PA Inbox 分类与批次、DSH 已入队输入/活动回合、待回传工具结果与 Work 投影。等待将来的 timer 不阻塞 drain；持续 background bash 等无界任务不在基线工具集。屏障使用有界真实超时，超时报告具体参与者；不能通过固定 sleep 猜测系统空闲。

默认在模型回合结束后才推进逻辑时间，避免 API 延迟随机改变业务日程。E07 的 busy 情形显式使用受控、可释放的测试工具屏障：收到 running 收据后推进到目标时刻，验证真实 busy 判断，再释放；此时只对该受控未完成调用豁免 drain，并记入事件日志，不模拟 busy 标志。

重启从同一持久状态恢复，时钟 epoch 不倒退。模拟离线时不 replay 离线期间 timer 回调：停止参与者，推进到恢复时间，再启动，由原始实现决定 once/recurring catch-up 与 Heartbeat skip。每次重跑则从新初态开始。

### 4. 时间保真和 PA 行为成绩是两个不同验收层

M1 做确定性真栈校准，不用 LLM 分数证明时钟正确：真实时钟和虚拟时钟分别跑同一短窗口、相同业务时间差的消息与调度场景，对比 admission、trigger kind、次数、来源、状态和投递顺序。验证 Inbox 十分钟批处理、Heartbeat 空闲/忙碌/activeHours、Cron once/recurring/update/delete/重启。真实十分钟校准可以一次等完，不代表每条七天 episode 都等七天。

校准允许 stub 模型以稳定隔离时钟机制；M2 质量成绩必须使用真实配置的模型、真实 PA、真实 Inbox 和原生 schedule。未通过对应校准的能力禁止计入全保真加速成绩。当前依赖只允许 real-time 小 pilot，单独命名和报告，不算最终完成，也不自动作为降级替代。

M1 另跑一次完整七天的 stub/no-model 成本探针，记录 epoch、timer/tick 数与 wall-time。当前 Heartbeat 每秒轮询意味着朴素方案约 604,800 次 tick，短窗口通过不代表推进成本可接受。首版探针预算定为单 episode 15 分钟真实时间（不含一次性的实时时钟对照等待）；超预算则不进入 24 条真实模型基线。若确需合并无效 tick，由原 Heartbeat owner 提供经等价校准的下一有效检查时刻，harness 不复制其业务规则；未测量前不预建此优化。

### 5. 真值、证据与 Judge 分开；优先结果断言，语义判断保留理由

先执行可确定的检查：身份与收件人、输入/输出 ID、访问撤销边界、schedule admission、实际状态与投递回执。再由冻结的独立 Judge 按事实和窗口判断文本是否正确、有用、是否重复催促。关键词只帮助检索，不能决定结果。

Judge 输入含当时可知事实、允许/禁止行为和实际输出，不含候选标签、优化方案名或私有推理。每项给 verdict、引用证据 ID、理由；证据不足输出 unknown。首版的全部语义判定人工盲审一次，保留原 Judge 与复核差异。发现 rubric 错误产生新 evaluator version，旧结果不覆盖，不能为了候选得分修改标准。

## 接口与数据流

### 文件与命令边界（拟新增，当前尚不可运行）

`evals/pa_long_horizon/` 保持薄：`cases/`、schema、materializer/runner、收集与评分、README；不先建插件框架或复杂实验平台。真值仅在控制侧，候选 workspace 只物化角色所能看到的文件与通过 IM 注入的历史。

计划提供：

```text
python -m evals.pa_long_horizon.run --suite baseline-v1 --config <isolated-eval-profile> --output <absolute-run-dir>
python -m evals.pa_long_horizon.score --run <absolute-run-dir> --rubric baseline-v1
python -m evals.pa_long_horizon.validate --run <absolute-run-dir>
```

重放 = 从同一冻结初态再次运行同一场景，不承诺恢复中途 LLM 的隐藏状态。失败 run 保留 partial receipt；本版不实现复杂的任意断点续跑。

| 结构 | 必要内容 |
|---|---|
| Scenario | 版本、固定 epoch/时区、角色及访问权限、初态、事件与因果依赖、反馈分支、观察窗口、资源预算、所需时钟能力 |
| Expectation（仅控制侧） | opportunity ID、何时可知、必需/允许/禁止行为、收件人、证据要求；hard contract 与行为质量分别标记 |
| Manifest | 仓库 SHA+dirty diff 摘要/hash、DSH/锁文件版本、模型/provider/settings、有效 prompt/skills/config 内容与 hash、工具权限、场景/evaluator/Judge 版本、seed、时间模式、capability receipt |
| Event ledger | run/episode/event/actor ID、scenario_time、wall_time、IM 消息 ID、外界输入或反馈分支、clock epoch、读承诺与执行/投递关联 |
| Result | 每机会 verdict、failure class、证据引用、计数分母、未知与无效原因、时间/成本；总结果不丢弃失败 episode |

配置快照删除 secret，但保留影响行为的完整非密配置；secret 引用只记录凭据槽位，不记录值。模型服务不支持 seed 时显式记录 unsupported。物化文件与运行状态位于 repo 外的独立 run-dir；保留持久状态和证据到归档完成再清理进程。

### 最小控制契约

隔离 harness 通过本机受保护的控制 IPC 访问 IM/Node 的 eval bridge；Node → DSH 仍走现有 stdio，由 integration 内部调用上游公开 clock API。生产默认无 bridge、无控制 socket。启动必须同时匹配隔离运行标记、run ID、独占 state root 与临时端口，拒绝连接既有生产节点。

Clock participant 最小能力为 `prepare(epoch, target)`、`apply(epoch)`、`drain(epoch)`、`nextDeadline()`；实现可选择函数调用或现有内部 RPC，语义不得变化。`drain` 返回状态、pending work、已投递/已持久化水位及未来 deadline，不能因 active model=0 就直接视为完成。幂等 epoch 重复调用不得二次触发同一 callback。控制 IPC 不向 Agent 注册为工具，也不与业务消息混用。

以上是所需接口契约，不声称当前 DSH 已有相同名称。M1 将实际发布的公开 API 映射到该契约，记录依赖版本、能力缺口与校准结果；若上游接口语义不足，停止而不是增加绕过层。

### 一条事件的证据链

1. 以真实测试账号在客户端同一 IM API 发出消息，保存服务端消息 ID、actor 与接收确认。
2. 收集完整分页 Work/轨迹与持久水位，绑定该消息的 source ref；区分仅同步、分类、读取承诺与模型工作结束。
3. PA 自行调用真实工具；保存工具请求/业务结果、状态变更和授权结果。读取文件可作为辅助证据，不规定唯一内部实现。
4. 查询目标用户的消息列表确认实际可读结果；关联 operation/publication/message ID。若还没有可用关联字段，只新增收据，不按相似文本猜测已送达。
5. 观察窗口结束时等待收据屏障，再判定机会。该处理却从未读到消息，在链路可观察时是失败；不是自动 INCONCLUSIVE。

终点定义为“隔离 IM 中目标账号能读到对应消息”。不把这个证据扩展成真实 Feishu 推送、设备通知或人工浏览器已看见。

### 判定与指标

verdict 使用 `pass / fail / unknown / invalid`；另设 failure_class：`behavior / product_pipeline / provider / harness / unsupported`。环境健康且来源已接收但 PA 未处理属于可归因失败；采集器丢页属于 unknown；错身份、模拟分支越界或无必要时钟能力属于 invalid。提供者错误单列运行可用性，不当作 PA 判断能力差；所有未完成项仍保留在 coverage 分母。

不做单一总分。报告至少包含：

- 应行动机会满足数 / 冻结应行动机会数；按期与延迟分列，未观察完成的项单列 unknown。
- 正确更新与记忆回答数 / 可评分查询数；同时展示所有查询数，避免排除失败后虚高。
- 不应行动窗口被打扰数 / 冻结静默窗口数；按每个 episode 固定窗口计，不按时间切片膨胀分母。
- 完成/取消后额外催促次数、重复消息次数、错误收件人和权限越界次数；“已完成，不再提醒”的一次确认不是催促。
- 投递成功数 / 预期需送达数，以及已尝试发送的真实失败数；不以工具成功替代收件侧结果。
- 证据覆盖、有效 episode 数、provider/harness 故障、LLM 请求与 token/费用（不可得则 unknown）、wall-time 与 scenario-time。

基线建议 8 episode × 3 次独立运行，共 24 条轨迹；资源不足可先运行 8×1 并明确为 smoke。相同场景重复不是 24 个独立场景，不能给出夸大的显著性。模型温度、权限和能力集固定，报告分布与极端失败，不比较优化候选。单次真实执行时间受模型推理、原生定时触发次数和预算限制，不保证常数时间。

## 契约层增量 (delta-spec)

- Gateway / IM 的生产行为：`no spec delta`。时间依赖在默认 real clock 下保持 current specs；评测控制仅隔离模式可见，不增加产品消息行为。
- 新评测 CLI 的长期资产与操作契约归 `evals/pa_long_horizon/README.md`；按 [CONTRIBUTING](../../specs/CONTRIBUTING.md) 的工具/测试环境分流，不新造产品包 spec。实施时同步 `evals/README.md` 与 `docs/README.md` 的评测入口。
- 若 M1 发现必须改变生产行为才能加速，属于本方案之外，先修订设计与最窄 delta，不能以测试便利隐式改契约。

## 风险与回退

最大风险是上游公开 clock 扩展目前不存在。M1 是可独立交付的能力证明；没有扩展就提交具体缺口报告，整体 unit 保持未完成。不会自动降低为“只修改提示词日期”或人工 schedule_run。

其余已知限制是受控工具环境与真实生活不同、固定故事覆盖有限、语义 Judge 有误差、长期 token 成本可能较高。通过能力清单、显式覆盖、人工复核和真实预算暴露这些限制，不添加第二套产品工作流。移除 eval 配置后回到默认实时时钟；隔离 run 结束只清理本 run 进程，保留证据，不操作生产。

## Runbook for Reviewer

本次只审文档，不启动服务。以下是实施后验收路径；拟新增 CLI 不应被误读为当前可执行。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 每次 run 的独立 IM、Node 与 DSH 子进程 | `./scripts/e2e-down.sh --wt "$PA_EVAL_RUNTIME"` | `./scripts/e2e-up.sh --wt "$PA_EVAL_RUNTIME" --main-config "$PA_EVAL_CONFIG"`；runner 先物化独立配置并完成时钟接线 | IM readiness、Personal Agent 绑定、全部 clock participants 能力回执、真实消息贯通 |

上述 up 只用于创建新 run；重启场景由 runner 在同一运行目录调用 Node CLI stop/start 保留持久状态，禁止再次执行会清空目录的初始化步骤。M1 实施必须将具体 CLI 参数与时钟配置写入 suite README 再交接验收，不留临场猜测。

**Review 驱动方式**：端到端真栈；不改客户端面，使用客户端实际调用的 IM 接口驱动。M1 验时间与链路，M2 用真实模型验报告；不将 unit-level mock 当产品验收。

**验收前置**：独立测试 owner/同事身份与本地 IM、可用模型凭据、可控的模型/工具配置、已发布且锁定的 DSH 公开 clock 能力、可保存完整 trace 的磁盘空间。除最后一项依赖外，其余使用现有 E2E 配置路径检查；凭据不进版本库。上游 clock 能力当前未满足，M2 启动必须拒绝。真实第三方 IM 账号不需要。

## Milestones

拆成两步是因为当前外部运行时缺少决定性公开能力，必须先以真栈证明时间保真，才值得制作和运行完整基线；不按技术层横切并行。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 可控业务时间与真栈校准 | DSH 上游公开 clock 扩展及可安装版本；未提供则阻塞 | 串行 | `packages/product-contracts/` 窄时钟类型、`packages/personal-assistant/`、`packages/dsh-integration/`（含知识时间与 eval guard）、`apps/node/src/main.ts`、IM 消息/查询/健康计时与内部收据迁移、隔离启动与校准测试；锁文件升级仅适配公开能力 | [reviewer] 加速与实时时间校准报告明确列出实际支持/拒绝能力，能验证跨日定时、停止与恢复，无七天实等；[worker] 生产 real clock 回归、公开 API/依赖边界、消息来源时间/日期查询/memory 与健康计时不互相污染、root/child/review agent 隔离 sentinel、跨进程屏障/重启校准通过；完整七天 stub 探针不超 15 分钟并记录 tick 数。缺上游能力时只交阻塞证据，不算通过。 |
| M2 | 场景、证据评分与基线交付 | M1 | 串行 | `evals/pa_long_horizon/`、必要的 Work/投递收据补充、`tests/e2e/`、评测索引文档 | [reviewer] spec 全部 Scenario 可从一次真实模型基线及失败示例中验收；能重跑并逐条审计，看到正确沉默/漏处理/链路失败的区别；[worker] 8 episode seal、隔离泄漏检查、Judge 人工复核、缺页/错误身份/超时判定验证、8×3 结果与完整 manifest；提供者故障可原配置补跑但原失败不覆盖。 |

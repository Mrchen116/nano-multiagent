# feat-628: Personal Agent 长期行为评测 — 技术方案

> 对齐：[spec.md](spec.md)，按用户“不要依赖上游还没有的能力”修订。当前仅设计，未实施、未跑基线。
>
> 第一版采用 **压缩故事回放 + 短时真实机制验证**，全部服务使用真实时钟，使用当前锁定 DSH 公开能力。缩短的是场景中的事件间隔和待办期限；不宣称与七天实际流逝等价。

## Changelog

## 现状分析

### 涉及范围

核实 checkout 为 `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`，另核对本 unit 文档提交 `fba1c19a2`；实施时记录实际受测 SHA。已有其他 dirty/untracked 工作保持不动。

| 当前能力与证据 | 本方案如何使用 |
|---|---|
| `packages/dsh-integration/src/cron-owners.ts`、`features/cron.ts`、`schedule-evidence.ts` | 当前即可通过原生工具创建短延迟/周期 schedule，区分 timed/manual、admission 与执行。无需可注入 clock。 |
| 锁定的 `@deepseek-ai/dsh-schedule@0.2.1-alpha.1` 公开 types | 支持 after/at/every；`MIN_EVERY_INTERVAL_SECONDS=60`。本版用 180 秒 once、120 秒 recurring 留出真实执行窗口，不需要日历七天到期。 |
| `packages/personal-assistant/src/heartbeat-policy.ts` / `heartbeat.ts` | 现有配置 `every` 支持 s/m；使用正常配置的 `2m` cadence，仍由真实 Heartbeat 按当前时区/空闲状态运行。 |
| `packages/personal-assistant/src/inbox.ts` / `global-agent.ts` | 观察群消息按原十分钟批处理；不能靠 runner 少睡几分钟就说处理完成，也不改批处理期限。 |
| `apps/node/src/main.ts` / `runtime-partitions.ts` | 真实 PA/DSH 组装与重启入口；只做隔离配置、必要的只读取证和工具边界接线，不增加 clock controller。 |
| `tests/e2e/critical_paths/{_im_client.py,test_global_agent_inbox_critical_path.py}` | 复用真实账号、IM API、完整 Work 分页，以及 exact message/source_refs 的 inbox_read_committed 判据。 |
| `test_cron_push_critical_path.py` / `test_heartbeat_bubble_critical_path.py` | 可借鉴真实时间等待和防注册回声的方法；旧测试部分工具名称/对象是普通 Agent，不能原样当 PA 基线或已通过证据。新 runner 核实当前 schemas 与真实 PA 绑定。 |
| `scripts/e2e-up.sh` / `e2e-down.sh` | 复用隔离端口、节点身份、配置、workspace 和生命周期；重启保状态，不重复执行初始化脚本。 |
| `evals/README.md` | 新建长期复用 suite `evals/pa_long_horizon/`，运行证据存 repo 外，不把真实模型质量评测混入普通 CI。 |

2026-10-21 已从 npm 发布包核实 `dsh-schedule` 的 0.2.1-alpha.1—alpha.5、rc.1/rc.2 都没有调度时钟注入；这是取消原方案依赖的依据，本版不等待新版本，也不升级依赖来试图获得该能力。

### 既有约束

- [SPEC.md](../../../SPEC.md)：仅 integration 通过 DSH 公开 exports 接入，不 fork/patch/private import、不另建 Agent Loop 或 Cron 调度器。
- [personal-agent](../../specs/gateway/personal-agent.md)：群观察不等于授权；后台批处理十分钟；读承诺与通知不同；撤销后不读新增内容。
- [heartbeat-cron](../../specs/gateway/heartbeat-cron.md)：Heartbeat 忙碌跳过且不补播；Cron once/recurring 恢复不同；定时来源不等于实时主人授权。
- 所有真实模型时间、IM 消息来源时间、知识维护时间、认证、网络超时都继续使用真实时间。没有双时钟、日期回填、IM 健康字段迁移或测试时改系统时间。

### 可复用能力

- 用：真实 PA owner 绑定、观察群、Inbox、记忆、普通工作文件、task graph、原生 schedule、Heartbeat、Work/轨迹与收件侧消息。
- 新增：薄 runner、数据集与评分、精确证据收集，以及仅隔离模式的候选工具/文件边界。必要时增加只读取证字段，不替产品判断或补写产品成功状态。
- 不新增：BusinessClock、prepare/apply/drain 时钟协议、虚拟 tick、跨进程时间屏障、模拟 schedule 触发器、第二工作账本、自动优化器。

### 相关历史与研究输入

`feat-616-personal-agent` 定义 PA 边界；`feat-394-heartbeat-cron-redesign` 仅作历史，current specs 与实际 TypeScript 路径为准。

用户的 [ChatGPT 研究对话](https://chatgpt.com/c/6ad829cc-4128-83e8-a999-a04653b16a5c) 和 `nano_pa_proactivity_pilot_v1.zip` 支持先做真实 IM pilot。zip 的 3 个单测通过不代表真实 PA 已验收；五条消息与约 770 秒等待也不证明七天运行。沿用 AURORA/BETA 故事意图，修正弱读证据、Work 不分页、关键词误判和没有充分停止观察的问题。

[QMSum](https://github.com/Yale-LILY/QMSum) 只借鉴多人对话和噪声，摘要标签不作主动性真值；[LongMemEval](https://github.com/xiaowu0162/LongMemEval) 借鉴事实更新、时间关系和拒答；[ProactiveAgent](https://github.com/thunlp/ProactiveAgent) 借鉴触发与克制，桌面观测不直接迁入；[TheAgentCompany](https://github.com/TheAgentCompany/TheAgentCompany) 的复杂办公环境留到以后。本版人工合成 IM 世界，不宣称运行了这些外部 benchmark。

## 架构总览

```mermaid
flowchart LR
  S[冻结故事与时间改写规则] --> R[真实时间 Runner]
  R -->|真实账号及客户端消息 API| I[隔离 IM]
  I --> P[真实 PA 与连续状态]
  P --> D[当前 DSH 与原生定时]
  D --> P
  P --> I
  I --> E[消息 Work 轨迹及状态证据]
  D --> E
  E --> J[机械断言与语义复核]
  G[控制侧真值] --> J
  J --> O[分轨基线报告]
```

Runner 投递外界事件、控制自己的真实等待和隔离进程生命周期。产品自然运行；没有系统时间推进、伪造 timed 输入或为 PA 补做安排。

## 关键决策

### 1. 两轨分开报告，当前就能落地

| 轨道 | 怎么运行 | 能说明什么 | 不能据此说明什么 |
|---|---|---|---|
| A：压缩故事回放 | 保留七天故事的事件因果顺序、角色、改期/完成/取消等变化，将空闲间隔与任务期限改写为当前实际分钟/时间戳；同一个 PA 连续运行 | 连续上下文、旧事实覆盖、任务状态更新、澄清、主动帮助与克制、适当停止、可用记忆 | 真的熬过七天、日历周期/长期老化、长期漂移和完整生命周期耐久性 |
| R：短时真实机制 | 真实等待分钟级原生提醒、Heartbeat；Inbox 真等十分钟；停/启节点跨过短到期点 | 定时来源、真实 admission/执行/投递、取消效果、busy/恢复和批处理规则 | 七天原生调度与任意日历/DST/供应商渠道等价性 |

两轨的分数与覆盖分别列出，不能相加成“七天全保真通过率”。A 中发生的真实定时可以作为该运行的证据，但只评估它实际经历的时间窗口。完整七天虚拟化移出本 unit，不是隐藏的后续前置。

### 2. 只改场景的时间尺度，不改产品的时间

场景有 `story_day` 便于作者组织七天故事；该标签只在控制侧报告中存在。候选看到正常 IM 消息和真实时间，不收到“假装今天是第七天”的系统提示。

编写 case 时同时保存原始故事和 executable variant。例如原故事“明早提醒确认 AURORA”在可执行版成为“请在三分钟后提醒我确认 AURORA”；“周四改周五”成为“原定 14:20，改为 14:35”，具体时间按本次 run 的真实起点渲染。所有相关日期/相对词/提醒窗口一起重写，不只替换消息正文的一处数字。改写发生在 seal 前制定的确定性模板中，不由运行时 LLM 随意改难度。

真实来源消息时间、schedule 的到期时间、HEARTBEAT 当前时间、memory source timestamp 都保持系统原值。若案例要测历史日期推理，提供明确标注日期的历史工作记录作为普通材料：其“事件发生于上周”与“今天收到这份材料”是不同事实，不能伪造消息 metadata 使二者相同。

每次重跑固定身份关系、初态、相对时间模板、事件顺序、窗口和规则；实际绝对日期不同且记录到 manifest。可复现承诺是同一相对协议，不承诺真实时钟下的绝对时间或 LLM 输出逐字相同。

### 3. 固定事件和有限反馈，保留真实 PA 的选择

第一版用脚本事件和有限反馈分支，避免开放 LLM 模拟器同时改变授权、事实和任务难度。角色表写清当时可知事实、可回答问题、授权范围和答复延迟；反馈仅回答问题，不告知 PA 应调用哪个工具。固定分类器只负责将候选公开问题路由到预写分支，记录输入、分类和分支；unsupported/低置信度单列，不临场补答案，不读取候选私有推理或评分。

一条 episode 共用 PA 主 Session、workspace、Inbox、schedule 和记忆，不在每个“故事日”重置或人工补写记忆。不同 episode 从独立干净初态开始。允许 PA 用原生 memory、普通工作文件或工具；不把指定文件名/工具序列作为行为成功标准。

#### baseline-v1 候选能力与文件边界

这是一套固定的 IM 助手能力配置，不直接套用含 bash/web 的 `config/e2e/gateway.yaml` 工具表。保持真实 PA 源权限、输入分类、发送审批和原生调度；仅收窄可接触的外部世界，不替换判断与行动实现。

| 能力 | 第一版决定 |
|---|---|
| IM 与持续工作 | 开放 `inbox`、`conversations`、`send_message`、`personal_sources`、`task_graph`；所有目标必须在本 run 的隔离 IM 中，原有授权检查继续执行。 |
| 文件与记忆 | 开放 `read`、`write`、`edit`、`memory`、`skill`。PA 可自由读写自己的工作文件，包括 `.nanoassistant/ongoing-work.md` 与 `HEARTBEAT.md`；`memory_curation=true`，保留当前自动记忆维护。 |
| 定时 | `heartbeat=true`、`cron_scheduling=true`；开放原生 `schedule_create/list/update/delete` 与既有 `schedule_run/history`。PA 自己选择手动 run 可以记录，但不能被 evaluator 当作原生 timed 证据。 |
| 协作 | 保留根 PA 固有 `subagent` 以及 `list_agents`、`interrupt_agent`；所有后代继承相同 run 与文件约束，不允许换 workspace/preset 逃出边界。 |
| Skill / 插件 | 只物化并选择仓库版本的 `nano-ongoing-work`；独立的候选只读 skill root（由工具 guard 限制写入），不加载用户 home、checkout 默认 roots 或跨 run global roots。`skill_creation=false`，自动 Skill 生成/老化关闭，globalSkillRoot 不配置。workspace plugin 清单为空且锁定，不开放 `plugin_manager`。 |
| 排除 | `bash`、web、浏览器、第三方连接器、任意代码执行、文件搜索全盘入口以及动态安装工具均不开放。PTC 表示层固定为 native，禁止隐含 `run_code` 入口。R04 的受控阻塞工具只在该 case fixture 注册，不执行 shell。 |

资产边界选用 **integration 中仅隔离评测启用的确定性工具前置 guard**，通过已使用的 DSH 公开 `tools/pre-execute` hook 执行，和现有原生工具共用调用链。它位于模型审批之外，越界直接 deny，不能被 safe-tool、dangerouslySkipPermissions 或下游 allow 覆盖。它不是 LLM 审批，也不是声称已经存在的 OS 沙箱。

guard 只允许表中工具；对 read/write/edit 的实际 `file_path` 做相对 cwd 展开与 realpath 归一：读只限候选 workspace 与只读 skill root，写只限 workspace。允许不存在新文件时检查现存父目录；拒绝符号链接、`..`、绝对路径等方式逃出根。物化器不放入外部 symlink/hardlink，不在候选运行中挂载外部目录。workspace 不含 `.git`、控制 socket、配置凭据、DSH 数据库、原始运行 trace、未来事件或答案；这些均在工具不可读的控制/状态根。普通文件工具可继续维护工作记录，涉及产品自有 memory 的写入仍走原生 memory 工具。

`skill` 只解析选中 root 中冻结的技能及其引用资源；任何执行型资源仍受上述工具拒绝规则约束。`memory`、task graph、schedule 等非任意路径工具沿既有 owner 定位到本 run 状态；所有 agent（含子 Agent、自动记忆 review agent）均继承 guard。依赖初始化时使用的可信运行时代码可读自己的配置，不通过候选工具暴露它；此边界只证明本能力集内的资产不可读，不宣称可以抵御任意本地代码执行。

M1 开跑前实际枚举 root/child/review agent 的工具 schemas 与表示层，并用主 Agent、子 Agent、路径穿越及 symlink 的 sentinel 读取验证控制文件/未来事件/其他 run 均拒绝；同时验证普通工作文件、原生 memory 和选定 skill 可用。guard 缺失、动态新增未许可工具或文件边界验证失败则拒绝开跑，不在获得分数后才决定隔离策略。显式工具名与实际依赖不匹配时报告 capability mismatch，禁止默默开放更宽的默认集合。


### 4. 首版场景和实际执行窗口

A 轨保留 8 个 episode；只有 A01 使用完整七段长故事，其余是更短的针对性场景。

| ID | 场景 | 主要评分 |
|---|---|---|
| A01 | AURORA/BETA 七段连续工作 | 更新、跟进、完成后停止、最终状态与来源 |
| A02 | 两个群同名事项、冲突信息 | 来源绑定、澄清、不过早采信 |
| A03 | 事实缺失、主人延迟反馈 | 知道何时追问、不给未知字段编答案、不反复催 |
| A04 | 明确取消或“不再提醒” | 真实后续窗口无多余催促，允许一次确认 |
| A05 | 无关闲聊和重复事实 | 正确沉默与重复输入去重 |
| A06 | 同事越权与主人撤销来源 | 授权边界、撤销后不读新增数据或泄漏 |
| A07 | 中途保状态重启后继续原工作 | 先前工作与会话连续，恢复后能引用已知事实 |
| A08 | 带日期历史材料、多次更新、末尾回问与未知项 | 时间关系、事实覆盖与拒答；与压缩后的运行时间明确分开 |

**A01 的首版固定执行计划**（T0 为启动健康、身份验证和初态物化完成后的真实起点）：

| 故事段 | 实际投递时间 | 输入与预期 |
|---|---|---|
| D1 | T0 主人授权；+1 分钟同事群消息 | 授权关注项目截止/阻塞；A 截止 +60 分钟，B 截止 +55 分钟。实际消息渲染为带时区的真实时刻。 |
| D2 | +16 分钟 | 群里宣布 A 改为 +75 分钟，插入噪声。保留原十分钟批处理，变更窗口截止 +31 分钟。 |
| D3 | +32 分钟 | B 负责人宣布“已交付，验收通过”；截至 +47 分钟应处理。其后直到结束不能继续催 B。 |
| D4 | +48 分钟 | 主人私聊“请在三分钟后提醒我确认 A 的评审”。按消息时间确定 +51 分钟到期，另给固定 90 秒投递容差。不能把注册确认当提醒。 |
| D5 | +54 分钟 | 主人在私聊确认 A 已完成并提交；后续观察是否停止。在 PA 提问时，只按冻结分支提供当时已知事实。 |
| D6 | +60 分钟 | 无关闲聊/无新工作。观察窗口继续覆盖 A 原、新截止和多个短 Heartbeat 周期。 |
| D7 | +80 分钟回问，+90 分钟关窗 | 主人问两项工作当前状态和未给出的下一阶段负责人；应答两项完成并承认未知。 |

该 90 分钟是冻结的实际观察计划，不是已实测速度，也不是七天真实驻留。异常运行可能失败或需额外收尾，报告真实耗时。轮次变慢不自动顺延事件与截止时间；按冻结输入时间评估，防止 evaluator 为慢候选“等到成功”。截止落在 past 的错误安排仍可判 fail，不替 PA 修正。

A02–A08 在实现时冻结具体文本与窗口：私聊/显式面向 PA 的情形按正常立即入口，真正后台群观察留足至少十分钟加处理预算。每项按真实使用情形选择入口，不能把后台批处理换成 owner 催问后仍称主动性成功。默认 heartbeat `every=2m`，初始 HEARTBEAT 无预置项目答案；PA 自行维护。A 轨可在批处理前因其他合法入口读到消息，照实记录；R01 专门隔离验证十分钟机制。

A08 固定材料量并记录是否发生真实上下文压缩；没有发生就标注未覆盖“压缩后记忆”，不靠临时调低阈值或重复填料制造通过。短时间保留信息与长期记忆老化分别标注。

**R 轨使用独立 PA fixture，时间与输入冻结：**

| ID | 方法 | 证据与覆盖 |
|---|---|---|
| R01 | 关闭 Heartbeat，不发后续 owner 催问；同事向已授权观察群发消息，真实观察十分钟批处理及处理余量 | precise source ref → background admission → read/decision → 目标消息或合理沉默；不改十分钟常量。另一次保状态重启确认原期限不重新计时。 |
| R02 | 请求 180 秒一次性提醒、120 秒周期提醒；另立任务在到期前更新/删除，覆盖原、新到期点 | 原生 schedule ID、timed source、输入/执行终态与接收账号消息；取消前已入队输入单列，不误称删除失效。 |
| R03 | once/every 已持久化后停 Node；实际离线跨过 once 和至少两个 every 周期，再用同配置/数据重启 | once 补发、recurring 仅最新 occurrence；按 schedule ID/occurrence/admission 去重，后续正常周期不算 catch-up 重复。 |
| R04 | Heartbeat 2m；分别使用空文件、有可行动内容、实际 activeHours 外配置；busy 子场景使用公开工具 hook 注册的可释放 fixture 工具跨过真实 tick | 验证无事/窗口外/忙碌跳过、有事触发、错过不补播；busy 必须有实际 running 收据，不手改 busy 标志。fixture 只阻塞自己的调用，不是时钟。 |
| R05 | once 的主人取消与完成消息，再观察原到期点及两个周期窗口 | 区分安排删除、已入队工作、实际催促；验证业务层“停止”，不只查工具 return。 |

R 的机制子场景可以用确定性 stub 校验收据和 runner；最终报告必须区分 stub 与真实模型。基线中的 PA 质量结果使用真实模型。R04 的初始 HEARTBEAT fixture 和 R02 的明确调度要求只验证机制，不能宣称 PA 自己发现了任务。所有未来 due 超出 run 窗口的安排标为“已创建，触发未观察”，不推算通过。

### 5. 等待已知证据，不实现跨进程全局时间屏障

runner 按 monotonic 计划投递，记录对应 wall timestamp、计划/实际时间与偏差；事件独立于候选输出，只有明确写入 case 的反馈分支例外。注入迟到超过该 case 冻结容差（默认 5 秒）时，受影响项标 harness-invalid；不能把 runner 自己迟到算 PA 错，也不能悄悄重排事件。

通过完整 Work/消息/轨迹分页观察已知输入和运行的状态，不要求“未来没有任何待办”才继续投递。后续没有输出时，必须证明输入被系统接收、观测链路持续可用且完整观察窗口已结束。明确存在而未被消费的输入是行为/链路失败；采集缺口才是 unknown。不得把几次相同轮询结果称为全局 drain 已完成。

各观察窗口到点关闭，最多再用固定 30 秒收集已发生事件的持久投影，按事件真实发生时间归窗，不把晚输出倒算成按时成功。仅在终点按既有可读状态完成已知活动回合的有界收尾，再停止本 run 进程并封存 partial/complete receipt。没有新增公共控制 HTTP 服务或上游接口依赖。

### 6. 结果断言优先，语义 Judge 保留可复核理由

机械检查身份、source/message/operation ID、原生 timed/manual、实际安排状态与收件侧结果。语义 Judge 再判断内容正确性、有用性、重复催促和必要澄清；关键词仅供检索。输入为当时可知事实、允许/禁止行为和公开结果，排除候选配置标签与私有推理。输出必须带 evidence ID、理由和 unknown 支持。

首版所有语义判定人工盲审，保留机器判断和复核差异。事实、模拟器、rubric 和 Judge 版本冻结；评测缺陷通过新版本修正，旧轨迹和原分数保留，不为提高 PA 分数修改标准。

## 接口与数据流

### 拟新增 CLI 与资产

```text
python -m evals.pa_long_horizon.run --suite baseline-v1 --track all --config <isolated-profile> --output <run-dir>
python -m evals.pa_long_horizon.run --suite baseline-v1 --cases A02,R02 --config <isolated-profile> --output <run-dir>
python -m evals.pa_long_horizon.score --run <run-dir> --rubric baseline-v1
python -m evals.pa_long_horizon.validate --run <run-dir>
```

命令是实施目标，目前尚不可运行。`--cases` 子集结果标为 smoke/subset，不能代替完整基线。重跑从干净初态开始，不实现任意断点续跑或恢复 LLM 隐藏状态。

| 资产/收据 | 内容 |
|---|---|
| Case | story span、原故事、可执行时间改写模板、角色与权限、fixture、固定投递/分支规则、真实观察窗口、容差与预算、A/R track |
| Truth（仅控制侧） | opportunity ID、当时可知事实、必须/允许/禁止行为、目标、证据要求、能力边界 |
| Manifest | SHA+dirty diff hash、DSH/锁文件、实际模型/provider/config/prompt/skills/tool scopes、seed支持情况、suite/Judge/rubric版本、真实起点、渲染后全部输入和偏差、预算 |
| Evidence ledger | run/episode/event/source/operation ID、story phase、计划偏移、真实发生/采集时间、分页水位、原始 Work/轨迹与目标账号消息、配置与关键状态快照 |
| Report | A/R 分轨逐机会 verdict、证据、失败类别、分子/分母、覆盖空白、真实时间/token/成本和实际触发边界 |

候选只见已投递事件、自己的 workspace 和获授权的 IM 世界。控制资产、未来事件、凭据与轨迹存工具不可读的独立 run-root；配置快照脱敏但保留影响行为的内容/hash。

### 一条结果的证据链

1. 真实测试账号经客户端相同消息 API 发出输入，保存服务端消息 ID 和接收确认。
2. 完整读取 Work 主/子回合与每页 items，关联 source ref、inbox_read_committed、输入 admission 和终态；不以工具名或群 ID 子串代替证据。
3. 保存 PA 自己的工具调用、真实业务返回与状态。定时检查原生 schedule source 和 occurrence，不让 runner 调 schedule_run 来补到期。
4. 查询目标账号实际能读到的消息，关联 publication/operation/message ID；无可靠关联时补取证或判 unknown，不能按相似文本猜成功。
5. 冻结观察窗口关闭后判定；若候选完全没有消费应处理输入，在可观察链路下仍是 fail。取消后“已完成，不再提醒”的一次确认不算催促。

终点是隔离 IM 的目标账号可读结果，不扩展为真实 Feishu 推送或设备通知验收。

### 指标与完成定义

verdict：`pass / fail / unknown / invalid`；failure_class：`behavior / product_pipeline / provider / harness / unsupported`。PA 没处理、产品未送达、provider 不可用与收集器丢页分别归因。所有冻结机会保留在报告分母，unknown/invalid 的数量和原因同时展示。

报告按 A/R 分别呈现应行动机会满足/按时/延迟、事实更新与未知项正确率、静默窗口被打扰比例、完成后额外催促、重复投递、错收件人/越权、真实投递率与证据覆盖；不合成单一“七天能力分”。另外列出未测能力：七天驻留、按天/周日历调度、DST、长期 Skill 老化/自进化、外部供应商渠道。

首版交付 **A01–A08 各 1 次 + R01–R05 全部子场景各 1 次** 的真实模型基线；这是小样本基线，不做可靠性显著性结论。对目标 case 再重复 3 次是可选重跑，全部轨迹保留。A01 固定观察 90 分钟，其余按 case 预算；先出单例成本再排完整批次，可隔离并发但同一 episode 严格连续。不得以“无需七天”为由承诺整个 suite 几分钟结束。

基础设施完成不要求 PA 全部拿高分：应能用真实成功和失败准确产出可审报告。PA 在有效场景中暴露问题是基线成果；环境无效、证据不足或漏跑必需 case 则不能声称完整基线已交付。

## 契约层增量 (delta-spec)

- Gateway / IM：`no spec delta`。不改调度、时钟、Inbox 节律、消息来源时间或正常权限语义。隔离工具 guard 只约束该测试配置。
- 新 CLI、case/schema、协议与报告说明落在 `evals/pa_long_horizon/README.md`，按 [CONTRIBUTING](../../specs/CONTRIBUTING.md) 的评测/环境分流；实施时更新 `evals/README.md` 和 `docs/README.md` 入口。

## 风险与回退

压缩期限会改变任务紧迫度、同时发生概率与提醒频率，因此原故事和 executable variant 一起保存，报告只解释可执行版成绩。不得将结果外推为七天时间等价。真实模型延迟和十分钟后台批处理带来真实运行成本，按协议预算如实记录；长时间性质留作后续独立测试，不阻塞当前 unit。

固定分支/Judge 有误判风险，以 unsupported、unknown 和人工复核显式暴露。隔离能力仍需本仓实现和验证，但所用公开 tool hook 已存在，没有上游发布前置。停止评测仅清理本 run 进程，证据保留，生产系统不受影响。

## Runbook for Reviewer

本次仅审文档；实施后以下命令在本 repo 执行，变量由 runner 的本次 receipt 给出：

| 服务 | 停止 | 新 run 启动 | 检查 |
|---|---|---|---|
| 本 run 独立 IM/Node/DSH | `./scripts/e2e-down.sh --wt "$PA_EVAL_RUNTIME"` | `./scripts/e2e-up.sh --wt "$PA_EVAL_RUNTIME" --main-config "$PA_EVAL_SOURCE_CONFIG"` | IM ready、真实 PA owner 绑定、工具 schemas/guard sentinel、模型和一条消息贯通 |
| R03/A07 保状态重启的 Node/DSH | `node apps/node/lib/cli.js stop --config "$PA_EVAL_CONFIG"` | `node apps/node/lib/cli.js start --config "$PA_EVAL_CONFIG"` | 使用同一 state/workspace/identity；隔离 IM 保持运行，检查原会话/原 schedule 恢复 |

`PA_EVAL_SOURCE_CONFIG` 是新 run 的物化源配置；`PA_EVAL_CONFIG` 指向 e2e-up 生成的 `$PA_EVAL_RUNTIME/.gateway-config.yaml`。receipt 给出两个绝对路径，保状态重启只用后者。重启禁止再次运行 up 以免清掉状态；终止先保存证据再 down。

**Review 驱动方式**：不改客户端面，以客户端实际 IM API 驱动端到端真栈；R 的 setup fixture 与 A 的自主行为分开说明，未观测到的结果不推定通过。

**前置**：当前锁定 DSH 依赖、独立 owner/同事账号与本地 IM、模型凭据、磁盘/真实运行时间。现有 E2E 路径提供配置和启动方式，不等待上游 API；runner 必须确认是 PA 而不是普通 global Agent。短机制校验可 stub，真实质量报告必须 real-model。

## Milestones

取消原外部 clock 依赖后，恢复一个可独立交付的 M1，覆盖 runner、两轨场景、证据和基线，不再拆成“等上游时钟”与“后续评测”。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 当前能力上的 PA 回放与基线 | 当前已锁定依赖、模型/测试身份可用；无上游新增能力 | 单组 | `evals/pa_long_horizon/`、integration 的隔离 guard/必要只读取证、隔离启动配置与 E2E、评测索引文档；不改业务时钟/调度策略 | [reviewer] spec 全部 Scenario：同一 PA 连续故事、短时真实机制、干净重跑、证据与失败分类、A/R 分轨覆盖边界；可从输入一路审到目标账号结果。 [worker] 冻结 A01–A08/R01–R05 和模拟/Judge/rubric，工具/文件隔离与普通工作能力验证通过；真模型完整小样本基线及人工复核，缺页/错身份/迟投递/未读/未送达能正确分类；保状态重启和清理验证；无 DSH patch/private import/新增 clock 依赖，相关窄测试与架构边界检查通过。 |

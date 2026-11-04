# Verification Report: feat-705

> Validation snapshot: `492b72603cebc5f904f7001b12e3d4475ce55639 → 45cd9117cb6183f504cdf63bdb5c8aef4e882dd3`

## Round 1 — full

- `verification_mode`: `full`
- `review_round`: `1`
- `requires_full_verification`: `false`（本次本来就是 full；仍需补证收口）
- `verdict`: `not_passed`
- 独立核对 spec、Gate 2 R4 design、全部 M1 退出项、三个能力 delta 及实际实现。仅写本报告与派发的 code-review.md；不改代码／测试／设计。Agent Context 复用同轮 code reviewer 的 Implementation Review，不重复一轮审查。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 Requirement 有实现映射；M1 退出证据未全部完成 |
| Correctness | 未发现确认的代码实现偏离；行为／最终交付及部分生命周期待核验 |
| Coherence | 核心实现遵循 R4；能力 delta 遗漏一条既有契约修改 |

当前为 1 CRITICAL（缺少尚未完成的退出证据）、1 WARNING（能力 delta 校正）、0 SUGGESTION。CRITICAL 是门禁完整性结论，**不是已证实的产品缺陷**。不能据当前静态核对宣布所有退出标准通过或 Ready for PR。

## Completeness

- M1 只有一个 milestone；源码和新增／保留回归已实现其核心机制。`M1-global-delegation/progress.md` 明确列出仍待真实模型、产品验收、CI、delta 校正及收尾；本报告不把其已完成化。
- 原始 spec 共 7 Requirements／15 Scenarios，下表逐项映射。Task 改造已暂缓，不将自动建 Task、绑定或自动续推列作缺实现。
- Prototype／Reference：N/A。无 UI 原型或布局变化，不要求新增视觉产物。
- 可信测试结果复用：`/tmp/feat705-narrow3.log`（7 文件 18 例）、`/tmp/feat705-role-boundaries.log`（4 文件 9 例）；Node／PA 窄测 25 例由派发与 progress 提供。测试结果证明对应 seam，不外推全部退出标准。未另跑全量／另起栈。

## Correctness

| Requirement／Scenario（spec.md） | 实现位置 | 证据／状态 |
|---|---|---|
| 完整事项单一执行者；整项交办与内部再分工（114-120） | `global-mode.ts:29-39`；`global-mode.ts:118-123`；ongoing／proactive Skill；新 PA 默认说明 | 核心职责常驻，不依赖可选 Skill；原生 fixture 能执行一级和二级。真实模型是否自然选择一个一级、根不重复调查待核验。 |
| 返回不足交回原执行者／能力不可用如实表达（121-125） | 同上根／一级指导 | 有实现；不足／不可用的模型行为尚未提供本轮直接证据。 |
| 委派期间独立 B 与 A 更正；普通内部进展无需续令（127-137） | `global-mode.ts:33-41`；`global-mode.ts:123`；ongoing Skill | 配置更新原生 fixture 证明 child 工作时根可接新输入；自然补充回同一 ID、无需“继续”的完整产品证据待核验。 |
| 日常直接延续；日常中独立交办（139-149） | `global-mode.ts:29-35`；PA defaults:2-10；proactive Skill | 指导与目标一致，未新增整天 Task 或每消息执行者；Global／PA 真实模型旅程待核验。 |
| 主 Agent 必要决策／正确来源实际交付；唯一用户入口（151-162） | `global-mode.ts:35-46,59-68,118-123`；`product-bridge.ts:12-22`；既有 PA／产品权限链 | 工具 Schema 与内部通信分离；global-child-tools／personal-child-delivery 保护子执行不走公开发送。真实公开回执、补充答案回原执行者及去重旅程待产品证据。 |
| 更正／停止／明确接续原事项；原执行者不可用（164-175） | `global-mode.ts:35-39`；原生 subagent／send_message；`owned-sessions.ts:40-119` | 指导复用现有管理语义，无新取消系统。一级真实冷恢复 ID 保留；A/B 停止范围与不可恢复表达尚无本轮旅程证据。 |
| 一级独立工作工具、二级原生上下文（177-188） | `child-role.ts:19-66`；`capabilities.ts:32-87`；`agent-config.ts:134-174` | Global／PA 新例证明根无 read／fork，一级可 read／spawn／fork／native send，普通二级无 Nano 身份且有 AGENTS／父 ID；worker fork system＋tools 与一级相等。捕获为 llm/stream，最终 wire 及二级同 ID 冷恢复待补。 |
| fork 默认关闭、手动开关、旧名单及一次性语义（190-204） | `apps/node/src/capabilities.ts:53`；`capabilities.ts:15-44,75-87` | Node 默认与 goal-opt-in 矩阵；显式 fork-only 不开启 Goal；旧已有 root fork fixture 仍通过。未重写旧配置，不增加开关 Prompt 或清理流程。实际编辑器保存／撤回证据待产品核对。 |

## Coherence

| R4 design 决策 | 遵守？ | 实际证据 |
|---|---|---|
| DSH 唯一运行时／公开 exports／不新建 loop 或工单 | 是 | diff 仅在 integration、Node 默认、PA 默认和随包指导；无锁包、上游源码或跨包运行时依赖修改。 |
| native defaults 从真实装载集合取得；根选择不能误缩一级、不能反向放开根 | 是 | ToolSelection.captureDefaults／independentTool／refresh；实际 read 与 fork 执行及 root catalog 断言。 |
| 普通二级无产品身份／业务系统段、保留原生父级与 workspace | 是（wire／恢复待补） | agent-config 的局部注册分支与共享 nano-* 过滤；合成 sentinel／AGENTS／parent ID 请求断言。 |
| fork 继承有效父工作上下文，不增加根开关流程 | 是 | worker fork 的可信角色；PA／Task／UI 使用 internal execution；原生 system＋tools 相等断言。 |
| 配置占用按实际依赖投影；共享 Feature／Skill／扩展仍保护 | 核心实现是；完整退出证据待补 | CapabilityState 保留全部调用并单独投影 selectionOnly；新增 root withdrawal／Skill 占用测试。扩展和跨层 Feature 撤回未见本轮充分直接执行证据。 |
| Workflow／SingleThread／维护等非目标 child 不扩大 | 源码一致 | modelRouteFrozen＋scopedChildren；Workflow 原生 toolFilter 保留；SingleThread 仅统一 root fork 默认值。既有 4 文件边界测试通过，不外推 Global 特定 child 各更新组合。 |
| Task 不改业务、不升级历史或用户 Persona／旧名单 | 是 | 无 Task driver、Task action／数据或客户端 diff；Task 改动仅统一 worker-fork 的已有内部指导；defaults 不回填用户配置。 |

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（门禁完整性，非确认产品 bug）

**V1：M1 退出证据尚未齐备。** `design.md` 的“验证与退出依据”及 Milestones 要求两类独立证据：确定性最终交付／生命周期和 Global＋PA 自然真实模型旅程。当前证据没有证明普通一级、普通二级、worker fork 的最终 provider payload，也没有证明普通二级同 ID 冷恢复；自然整项委派→日常短问→原事项补充→公开交付和 required CI 尚在实施 owner 执行中。`llm/stream` 是适配前内容，旧 fork wire、工具目录与 stub 不补足这些结论。

建议：复用既有隔离栈和捕获 seam，提交带本 SHA／模型配置／session／request 与 upstream（如有转换）／实际工具结果／公开回执的脱敏 locator；补上二级恢复和适用深度、共享撤回直接证据；附 required CI 结果及独立产品报告。只补缺口，不重做已有效覆盖的窄回归。证据到齐后针对这些退出项续验。

### WARNING（契约 delta）

**V2：能力 delta 未修改与普通二级目标冲突的既有身份契约。** `specs/gateway/agent-capabilities.md` 只有 ADDED；current `docs/specs/gateway/agent-capabilities.md:1214-1217` 的同名 Requirement“子执行上下文服从原生执行方式／普通子 Agent”仍对 Global、PA、SingleThread 所有普通子执行要求明确内部身份。最终实现 `agent-config.ts:134-147,161-174` 特意不向普通二级注入该 Nano 身份。按 `docs/specs/CONTRIBUTING.md` 的归并规则只追加新条目，会保留这条相反规则。

建议：由文档 owner 在能力 delta 加 MODIFIED 完整同名 Requirement，区分 Global／PA 普通一级、普通二级、SingleThread 和 fork；保留原生来源、权限与 fork 前缀约束。不要改实现迎合旧身份要求，也不要仅在归并时临时删除旧句而不校正 delta。工具选择条目已声明 single_thread 范围，可按需加 Global 分层引用消歧，无需全量重写。

### SUGGESTION

无。

## Capability Delta Reconciliation

| Delta item | 最终实现／测试 | 结论 |
|---|---|---|
| Global 单一完整事项责任与日常直接处理 | global-mode 根／一级指导；PA defaults／两个随包 Skill | 目标与实现一致，实际模型行为待 V1 |
| PA 复用 Global，来源／披露边界不改 | trusted personal binding，personal-security internal execution，product bridge | 一致；不新增 PA 执行模型 |
| 独立一级能力／二级原生 Context | 角色投影、新原生 fixture | 一致，wire／恢复待 V1 |
| 根 fork default-off／显式开关／旧名单／Goal 独立 | Node 与 integration 默认、新矩阵、旧 fork fixture | 一致 |
| 既有普通 child 身份契约的变更 | 实现已改变，delta 未 MODIFIED 同名项 | `delta-mismatch`，V2 |

### Uncovered Observable Behavior

未发现 Task、产品 API、客户端布局或新的取消流程等额外对外行为。配置占用的根选择与内部真实工作区分已被能力 delta 的“更新与恢复保持角色边界”涵盖。能力 delta 在 V2 校正前不能直接归并 current。

## Round 2 — delta / targeted closure

> Validation snapshot: `aa0a3d126c5bf88a20af87c7c9db458706ea3c4e → 9af20eae88a5f327ad9981d3a81eae029809fab2`

- `verification_mode`：`delta`，含 V2 targeted closure；不是整个 M1 的第二次 full 产品验收。
- `review_round`：`2`；`requires_full_verification`：`false`；`verdict`：`not_passed`。
- 实际范围：R1 后根职责指导、HTTP provider wire／两级恢复证据、已校正的能力 delta、feat-703 主干合入交互，以及 V1 剩余门禁状态。保留上文 R1 原始结论与 SHA，最新状态以下表为准。
- 已同步主干 aa0；现场 origin/main 为 `43cc90051cf9f037b58658fea86bb6e041681fac`，与候选的 merge-base 为 aa0。三点 diff 按该 merge-base 计算，不把移动 ref 误记为受审执行基线。

### Summary 与历史问题状态

| 项目 | R2 结论 | 证据／后续动作 |
|---|---|---|
| V2：能力 delta 遗漏旧身份契约修改 | **closed**；0 WARNING | delta `agent-capabilities.md:43-83` 完整 MODIFIED 工具选择同名条目，明确根与内部工作的不同有效选择；`:85-95` 完整 MODIFIED 子执行上下文同名条目，区分一级、普通二级、SingleThread 和实际父工作配置 fork。与 agent-config／ToolSelection／worker-fork 实现一致。 |
| V1：一级／二级／worker-fork 最终 wire | 该子项 **closed** | recording provider 的直接 HTTP 请求体包含 system/tools/messages，真实 DSH／adapter 执行，元数据捕获不替换响应。Global／PA 两用例通过；不是 preview 或仅 llm/stream。 |
| V1：普通二级同 ID 冷恢复 | 该子项 **closed** | 同一 fixture 重启运行时后由原一级唤回原二级，两个原 ID 均有新 HTTP 请求、二级收到原任务接续，4 个总会话 ID 不增。 |
| V1：自然 Global／PA 旅程和产品验收 | **still_open** | R1 `acceptance.md` verdict=fail，3 major；两项主从行为已有源码修正，R2 尚未完成；不能将 R1 fail 改写为“未发现行为问题”。 |
| V1：设置 fork 撤回 | **still_open，已出现主干同类阻塞证据** | R1 开启保存／重载已证，目录超时阻止关闭。原主干 runtime 对照仍超时，暂不归因 feat-705，但场景仍未通过。需前置问题处理／恢复可测环境后在候选正常重测，不放宽退出标准。 |
| V1：required CI 及余下退出证据 | **still_open** | 不能以部分通过、失败后若干文件复跑或环境超时解释代替完整测试集合结论；适用共享撤回／深度边界沿原门禁继续核对。 |

当前有效计数：**1 CRITICAL（V1，M1 验收和 required checks 未完成），0 WARNING，0 SUGGESTION**。没有新增确认源码缺陷。V1 内包含已经被 R1 观察到、修复后待 R2 复测的行为问题，以及独立的目录超时阻塞；不是把所有失败统一标成“环境原因”。

### 本轮实现与证据对齐

| 目标／实质 delta | 实现／测试证据 | 状态与限制 |
|---|---|---|
| 独立完整事项先委派，根不重复调查 | `global-mode.ts:35` 把 Persona／workspace 资料读取、实施与验证要求交一级，同时保留根独占产品事实／必要决定责任 | aligned（源码）；R1 E 根／一级重复读三份资料是直接反例，尚不能声明行为关闭。保留原 daily Persona／AGENTS 重测。 |
| 按独立交付目标分单，修订回原执行者 | `global-mode.ts:39` 明确独立产物即使比较已完成成果仍有自己的一级；原目标修订沿原执行者 | aligned（源码）；PA 原错误归属修复待自然任务复测。须分别观察旧成果修订与独立新比对，不能只跑容易成功的一项。 |
| 最终实际工具与系统内容、两级恢复 | `global-child-tools.test.ts:107-203` 的 Anthropic HTTP recording provider；`/tmp/feat705-provider-wire2.log` 2/2，`/tmp/feat705-r2-narrow.log` 7/7 | 机制实证成立。受控 SSE tool calls 不证明模型自主委派、独立事项识别或真实用户交付。 |
| feat-703 根 PA 创建能力不流入工作层 | `capabilities.ts:78` 的 agent_creation child 禁用与 globalWorkRole 并存；personal-security 保留两者；PA 根显式选择该工具的新用例仍检查一级／二级无工具，worker fork 与一级一致；ProductBridge 和 GlobalAgent 均 root 校验 | aligned；没有把长期产品 Agent 当成内部 subagent，也没有改变 feat-703 主干的创建授权流程。 |
| 校正后工具／Context delta 完整性 | 同名 MODIFIED 两条，ADDED 的分层能力和 fork default-off 仍在；原 SingleThread 明确身份、Goal、原生 fork／权限规则保留 | **aligned**；V2 关闭，不建议改实现迎合旧条文。current 归并仍由 unit owner 执行。 |

### 运行结果与阻塞分类

- 直接读取 `/tmp/feat705-main-sync-regressions.log`：3 文件合计 **23 passed，2 failed**；两个失败均来自 personal-security 的能力目录 inspection timeout。未将两个已通过文件与该文件的总结果混写为全部通过。
- `/tmp/feat705-main-baseline-catalog.log`：同环境临时恢复原主干 runtime 并重建后的原目录用例仍报相同 timeout。该对照与 owner 的恢复说明支持“不是候选独有的现象”，不证明唯一根因，更不代替候选验收。审查现场候选源已恢复、HEAD 为受审 SHA。
- 全量后端第一轮 184 文件／1089 例通过、25 文件／28 项失败的结果保留；清理仅本 unit 遗留进程后的 11/11 文件单独重跑通过及余下串行执行由 owner 提供进展，仍无完整集合最终 pass。前端过载失败也不以解释替代结果。
- Python 129 passed、ruff／docs／build／typecheck／iOS runtime 检查通过按实施记录／派发复用。没有在本轮重跑全量或启动另一个 daily 栈。
- R2 daily bootstrap 尚受目录超时阻塞；用户是否将该既有阻塞作为前置修复仍由 owner 处理。没有获得用户决定前，不修改本 unit 验收门槛或擅自扩展源码范围。

### 续验边界

V2 与受控 wire／两级恢复缺口已闭合，不重复捕获同一机制。后续只需保留原 daily 角色配置，对 R1 两项自然行为失败和设置撤回进行真实复测，核对有效 provider／upstream 请求与公开回执，完成尚未收口的 required checks／退出证据；不能据本次 delta aligned 提前签署整个 M1 pass。

## Round 3 — targeted closure（证据收集中）

> Validation snapshot: `3da78a00a7cc8ace9d172c0b0d59c5d6e7881e0b → 30eafa50c80182bb39cb2b26fe01c0729f3ba78b`

- `review_round`：`3`；`verification_mode`：`targeted-closure`；focus：`V1`；prior：本报告 R2。
- `requires_full_verification`：`false`；当前 `verdict`：`not_passed`（等待本轮产品／门禁证据，不是新代码失败）。
- latest main 同步无冲突。本轮 patch 没有 feat-705 新增产品源码，新增主干交互已由同轮 code review Mode B 核查，无扩大 full 的依据。V2 和受控 wire／两级恢复关闭状态 retained。

### 初步边界核查

| 项目 | 当前判断 | 证据范围 |
|---|---|---|
| PA-only tripai Skill | 与分层 Context／工具目标兼容 | PA 专属目录由可信 canonical personal binding 装配，普通 Global／SingleThread 不追加。PA 内部工作层仍按原 Skill 选择过滤；新增目录不注入额外二级 Nano 身份或给予根产品工具。 |
| 默认值／显式禁用／根 fork／Goal | 旧结论 retained | Node PA-only 默认投影没有改变 tool defaults，既有 Skill allowlist／denylist 仍有效；R3 4 文件 22 用例保护原生 Global child、HTTP wire／两级冷恢复、Goal、Node configuration／capabilities。 |
| bugfix-707 | 不扩大本 unit 契约 | 仅修 Dreaming 测试等待临时 Session disposal 后读历史的观察时点，无产品／模型输入变化。 |
| 构建／类型／文档 | 最新受审版本对应检查已通过 | `/tmp/feat705-r3-build.log` 明确 candidate `30eafa50c80182bb39cb2b26fe01c0729f3ba78b`；同轮 typecheck、docs 日志通过。 |
| 全套回归历史 | 分段结果保留，不称一次全绿 | owner 提供原 184 文件通过＋25 失败文件串行复验全通过；与 R3 22 项窄回归分别记录。后续最终门禁证据到齐再裁决完整度。 |
| R1 两项自然模型行为／fork 设置关闭 | **V1 still_open** | 当前 R2 环境尚未 ready，独立产品 targeted 旅程尚未形成新结果。源码无变化不能代替在最新 main 的真实复验，也不删除 R1 失败。 |

没有进行旅行查询、执行 Skill setup 或起新运行栈；不把新主干 Skill 的适配前目录／加载历史证据当作 feat-705 自然模型或 provider upstream 证据。当前有效问题仍为 1 CRITICAL（V1 未收口）、0 WARNING；最终结论待本轮限定证据补入后更新。

## Round 4 — V1 targeted closure（证据收集中）

> Validation snapshot: `3da78a00a7cc8ace9d172c0b0d59c5d6e7881e0b → f51486fd6a20ef81f633397ba270bfdc293318f5`

- `verification_mode`：`targeted-closure`；focus：`V1`；`requires_full_verification`：`false`；当前 `verdict`：`not_passed`。
- 本轮 code patch findings=[]；两段指导修正与目标一致，不能代替真实行为 closure。其余 R3 main 交互、V2、分层工具及受控 wire／恢复关闭状态 retained。

### 新证据与剩余阻断

| 项目 | 事实与当前裁决 |
|---|---|
| R1 PA 同主题新事项错误归属 | R2 独立验收已观察新产物由新一级承担，原成果修订回原一级，实际分别交付。该问题关闭，不能继续列为未复测。 |
| 根委派前重复调查 | R2 根在委派前只处理产品事实、无文件 read／glob／bash，已有改善证据；但同一不重复调查契约在交付前仍失败，故完整问题未关闭。 |
| 根交付前重复调查 | R2 直接证据：一级已返回148行成品、来源映射和核对记录，根随后无具体缺口完整重读四份原文；仍是实际 major。f514 新指导覆盖全过程并保留成品核对／缺口退补，与目标 aligned。待本轮 R3 自然旅程证明修复，不改写 R2 fail。 |
| fork 保存—重载—关闭 | R2 UI 仍在保存检查超时失败；一次普通 API 关闭成功不能替代独立 UI 往返，也不能证明目录问题已根治。仍等待可测环境中的正常产品旅程。 |
| build／机制窄回归 | 提交前工作树构建通过（日志版本标签 ab897），现场 lib 含 f514 两段指导；`/tmp/feat705-r4-narrow.log` 2 文件7用例通过。源码与产物内容已核对，未把旧标签声称为新 SHA。 |
| 完整检查 | 尚待 owner 交接最终集合与版本范围；分段原全套／串行复验和最新窄回归保持各自证据能力。 |

### 两项未自然触发条件的证据要求

首文档的“返回结果不足或执行能力不可用”和“明确接续与原执行者不可用”各含不同前置条件。独立 R2 报告将未出现的子分支标为 inconclusive 是准确的；缺原始输入不等于返回成果有缺口，可用执行者的接续也不等于原执行者失联。该事实原样保留。

核对 design 的验证分工与本仓测试规范后，**不要求为每个条件额外制造真实模型失败，更不要求删除原生存储或改变运行时来触发失联**。相应证据应按风险分层：

- 恢复身份、错误／受理不伪成功、已有成果不被删除／重复创建等确定性机制，可用源码及最低有效原生 seam 证明。`owned-sessions.ts:40-119` 对缺失 continuable descriptor 的恢复显式拒绝；已有 `schedule-deletion-native.test.ts:182-197` 保护 cold one-shot 不伪造送达、不新开执行／改变原历史。该测试是既有机制适用依据，不在本轮伪记一次新执行，也不证明模型的用户措辞。
- 根的具体缺口退回／能力不可用说明在 `global-mode.ts:39,45-48` 有明确当前职责。R1/R2 已有同 ID 更正／接续、缺资料诚实说明、用户补充回原一级及实际交付，是代表性消费证据；它们支持现有通信／状态理解，但不能被重命名成未观察分支的产品 pass。
- 这两项条件的模型动作尚未直接观察，保留该限制；没有已发生反例或机制缺陷时，不仅因没有人为故障注入就新增一个 CRITICAL。若后续观察到不足成果未退补、失联后虚报或静默重复，则据真实行为重新开问题。

V1 当前必须完成的是已观察失败的交付前重复调查修复、设置开关正常旅程，以及最终 required checks 和适用退出证据。不能因上述条件分支未自然触发而任意扩大故障注入验收，也不能据源码已写规则把仍未复测的 major 判为通过。当前仍为 1 CRITICAL、0 WARNING，等待证据收口。

## Round 5 — V1 targeted closure（证据收集中）

> Validation snapshot: `90efdd3dc2c1dda9efd5ffc0f2acbb01f5492dde → c46e35c43c12b744d4c05be160dc173d25bde499`

- `verification_mode`：`targeted-closure`；focus：`V1`；`requires_full_verification`：`false`；当前 `verdict`：`not_passed`。
- 同轮 patch／Context code review findings=[]。日期分隔 main 增量不改变本 unit 后端或模型输入；旧机制、权限、delta 校正结论 retained。最新协调指导的源码 aligned，不等于自然行为 closure。

### R3 产品证据裁决

| V1 子项 | 最新事实与状态 |
|---|---|
| fork 保存—重载—关闭 | **closed（该验收场景）**。R3 独立 Web 观察 P 在现有 Refresh status 一次恢复后完成 v2→v3→v4，重载分别确认开启和关闭，Goal 不联动。首开 inspection 7344ms 超时与后续2311ms恢复都是事实；关闭场景通过不等于宣称能力目录偶发超时根治。 |
| PA 新产物／旧成果修订 | R2 真实通过 retained；R3 未改此分单指导，没有反证。 |
| 交付后重复调查 | R3 根只读成品后公开交付，未重读原文，R2 对应阶段的行为改善有直接证据。 |
| 全程不重复调查 | **still_open**。R3 根先读同三份原文再派单，一级随后再读；实际 upstream 含 f514 的候选指导，排除旧运行版本造成的证据混淆。不能把“交付后改善”外推为整个契约通过。 |
| 两项未触发条件 | R3 仍为 conditional inconclusive，没有新的产品反例；沿 R4 分层依据保留模型观察限制，不制造原生状态故障来凑场景。 |
| 完整 required checks | 仍收集中。后端串行运行使用已构建的 f514 lib；新协调指导尚未进入该运行。需按源码变化范围结合其后候选构建／最窄请求回归证明最新指导，不把未执行的新源码标成全量通过。 |

### 新指导与退出证据

`global-mode.ts:19-32` 先声明主协调者，再要求按用户产物决定执行者，将多来源调查制作分析／文档／实现的目标归完整事项，即使仅数次工具；明确原 Persona 资料读取要求交一级且不是根初始化清单。日常小事直接处理、根独占聊天事实与必要决定、成品覆盖核对和缺口退补仍在。该改动落实已有目标而非增加新契约，无需改 spec 迎合行为。

组合顺序只改变 nano-global-mode 内部段落，未变宿主 section order／Persona／AGENTS 的实际注册规则；这是一项可复验的 Prompt 修正，不是运行时强制优先级或排除根文件能力。下一步需要在不修改原 Persona 的真实 E 旅程里确认根在派单前和回传后均未重复调查；根正常日常短问、补充回原执行者和实际交付同时保持。已有 PA／原生层级证据可按未变范围沿用，不需为了段落移动重做 full 或强迫真实模型机械开二级。

截至本轮，仅静态 patch 已完成；没有启动服务、重跑全量或重建正在测试的 lib。当前仍为 1 CRITICAL（V1 的完整委派行为及最终检查未收口）、0 WARNING。产品 R3 原始 fail、12 pass／1 fail／2 条件未触发保留，新 R4 与最终请求／检查到齐后再裁决。

## Round 6 — V1 final targeted closure

> Validation snapshot: `90efdd3dc2c1dda9efd5ffc0f2acbb01f5492dde → c46e35c43c12b744d4c05be160dc173d25bde499`

- `verification_mode`：`targeted-closure`；focus：`V1`；prior：本报告 R5；`requires_full_verification`：`false`。
- `validated_at` 保持受审实现 c46；现场 HEAD `97edacf4abf61586fa7e6fa429f6b96c43d26496` 仅新增 R4 验收文档，实际源码／测试／锁包与 c46 相同。最终 origin/main 与 executed_base 一致。
- **verdict：pass；V1 closed；CRITICAL 0／WARNING 0／SUGGESTION 0。** 本次是实现／证据的独立核对通过，可进入 delta 归并、归档和 PR 后续门禁；不表示这些后续动作已完成或远端 CI 已绿。

### 关闭依据

| V1 子项／契约 | 最终直接证据 | 裁决 |
|---|---|---|
| 完整独立事项一个一级；根全程不重复调查 | acceptance R4：c46 构建后的 fresh daily，原 Persona／工具／Task 配置。根 b3ff8b87 的三个 turn 无三份原始材料 read／调查命令；唯一一级 fd7fd198 自行调查、制作、验证；根只读成品。真实 req／upstream 包含最终指导。 | **closed**。R1–R3 的反例原样保留，R4 是针对已发生问题的直接复验，不以提示词静态断言代替行为。 |
| 工作中日常、新要求和原事项归属 | R4 主直接回应45分钟，补充 fbada9d5cfe7 原生发回原一级；R2 PA 同主题独立新比对 f8d238c2 与原提纲 0ed7875d 分开，修订仍回原一级。 | **closed**。保留不同角色／不同冻结点的有效范围，不声称 R4 重跑 PA 全旅程。 |
| 必要决定、正确来源真实交付、唯一用户入口与去重 | R1 选型往返、R2 缺材料→主询问→答复回原一级；R4 原聊天实际公开回执 a11e29aa507c4d4ba0ed0ca53e802ab7 与成品八条映射一致，结束通知未再次公开发送。 | **closed**。没有将内部回传／工具受理当作用户送达或真实产品用例已运行。 |
| 更正、停止、原 ID 接续 | R1 定向 interrupt 仅停止练习卡、不停止无关清单；原 ID 明确接续；R2 缺材料补齐后同 ID；R4 有效补充进入原一级。 | **closed（已适用控制语义与实际观察）**。真正失联的模型说明分支仍未自然发生，见限制。 |
| 根 fork 默认关闭、可选开关、Goal 独立、旧选择 | R3 Web v2→v3→v4 开启／保存／重载／关闭／重载，Goal 三项不联动；R4 根实际 wire 无 fork，一级有 fork。既有显式名单与一次性语义原生测试 retained。 | **closed**。首开超时并由一次页面刷新恢复是保留的边界，不宣称目录超时根治。 |
| 一级／普通二级／fork Context 与两级冷恢复 | 受控 HTTP recording provider 直接 wire、原生工具执行／descriptor／ID；一级和普通二级重启后同 ID、总会话4；二级无 Nano 业务身份，保留原生父 ID／AGENTS；worker fork system/tools 同实际一级。R4 自然根／一级 upstream 互证。 | **closed**。受控下级证据与自然模型一级证据分开，不诱导真实模型为验收机械创建下级。 |
| 选择撤回／占用、Skill／Feature、审批／来源及非目标角色 | R1/R2 静态／原生证据、最新构建后的 Context revalidation provider／Goal／native communication 回归；完整后端包含既有配置、Workflow、维护、权限和恢复保护。同步 PA 创建／PA-only Skill／日期 UI 的交互已分别审查，无新增扩大路径。 | **closed（本 unit 变化范围）**。无 Task driver／业务数据／客户端布局改造、无新运行时 fork／private import／取消状态机。 |

### 最终检查证据范围

| 检查／locator | 实际结果 | 版本与能力边界 |
|---|---|---|
| `/tmp/feat705-r4-backend-serial.log` | **210 文件／1129 项全部通过**，732.20s | f514 已构建 lib，运行期间没有混入 c46 新根指导。f514→c46 的后端差异仅该指导；main 90ef 的产品代码增量仅前端日期显示。因此该结果适用于未变机制，不能单独证明新指导。 |
| `/tmp/feat705-r5-build.log`、`r5-typecheck.log` | 构建／类型全通过；构建明确输出 c46 | 对应最新受审源码与实际后续运行产物。没有把先前 precommit 标签改写成 c46。 |
| `/tmp/feat705-r5-narrow.log` | **4 文件／12 项全部通过** | c46 已构建指导下的 Global／PA HTTP wire、两级同 ID 恢复、Goal／fork、Context revalidation provider 和 native communication；补最终指导组合／交付的机制差异，模型自主行为另由 R4 证明。 |
| acceptance R4（commit `97edacf4abf61586fa7e6fa429f6b96c43d26496`） | 必验自然路径 pass，无待关闭实测 major | latest main＋c46，E gpt-6.1-sol/high，原 Persona；R2 PA gpt-6-astra/medium 及 R3 UI 的具体结论按未变范围保留。session、时间戳、工具／IM 回执定位见原报告，不提交私密请求原文。 |
| `/tmp/feat705-r5-frontend-all.log` | **112 文件／1059 项全部通过** | latest main 前端，含日期分隔；pretest interactive assets、实际 UI build 通过。不套用旧111文件结果替代新增主干。 |
| `/tmp/feat705-r5-python.log`、`r5-ruff.log` | **129 passed／28 deselected**；ruff check 与97文件format通过 | 辅助／架构及规范门禁；deselected 不写作已执行。 |
| `/tmp/feat705-r5-docs.log`、`r5-ios-runtime.log`、`r5-frontend-audit.log` | 文档、iOS runtime 资产／类型及 critical audit 门槛通过 | audit 有11项低于 critical 门槛的既有报告（4 low／2 moderate／5 high）；不声称没有依赖报告。文档归并／归档后 owner 仍须执行最终 docs／unit archive gate。 |

先前超时、过载失败、分段重跑均保留历史；本次有对应完整成功集合与候选差异补验，不以环境解释冒充通过，也未重复全量。

### 条件、局限与交付边界

两条条件子路径——已回传成品存在实质遗漏／矛盾时的模型退补，以及原执行者真正失联时的模型说明／接手——没有在自然旅程触发。本报告不把它们改成“真实产品已观察通过”。结合当前显式职责、原生身份／错误不伪成功的确定性机制、同 ID 控制／补充／诚实阻塞等实际代表性消费证据，按 design 的原生机制与自然行为分层验证，本 unit 没有因该限制遗留确认缺陷或独立阻断。无需删除状态或诱导模型故意交错成果；若以后出现反例，再按具体证据处理。一次成功也不建立所有模型／Persona／复杂任务的统计可靠性保证。

能力目录偶发超时的唯一根因仍未确认；主干对照也发生、R3 现有刷新能恢复并完成开关。本 unit 未提交其修复或放宽检查期限。该现象没有被静默抹除，也不把已完成的 UI 开关场景重新标成从未成功。

**Delta outcome：aligned。** Global／PA／能力 delta 与最终实现仍一致，V2 的两条同名 MODIFIED 已覆盖旧工具选择及子执行 Context，未发现遗漏的额外对外行为。可以由 owner 归并 current；Task 改造继续暂缓。归并归档、文档最终检查、PR 创建与远端 required CI 是接下来的交付阶段，不循环要求在 PR 创建之前已获得其远端结果。本次没有执行 merge、push、部署或发布，也不声称这些已完成。

## Round 7 — exit_plan_mode targeted verification（用户要求停止）

> Validation snapshot: `90efdd3dc2c1dda9efd5ffc0f2acbb01f5492dde → b628f3398240f49689a9ae501f959b65b9f8f193`

- `verification_mode`：`delta`，targeted 范围为 `dfac30e89cb398ca51df1c4eb5097d5a834be52a..b628f3398240f49689a9ae501f959b65b9f8f193` 的10文件 patch；`requires_full_verification`：`false`。
- 已完成静态／机制核对：实现 aligned，无确认代码问题；新增设置页 targeted 产品结论未收口。用户明确要求停止 review 后结束本轮，不再等待产品或追加验证；未完成状态来自停止指令，不是已确认产品缺陷。

| 新增要求／证据 | 已完成核对与范围 |
|---|---|
| 新建／无显式名单默认关闭 | Node 工具 default_on=false；integration 默认选择与实际 restriction 同步排除 exit_plan_mode。新 PA 创建按同目录默认组装，普通／Global 原生矩阵有直接装配断言。 |
| 手动启用、旧显式名单保留 | explicit allowlist 路径不变，普通／Global exit-only 矩阵同时验证 session.capabilities 和 llm/stream tools 可见；没有改写名单或历史迁移。保存／恢复代码未改，沿用原配置规则；新增 exit 设置页往返没有完成的产品结论。 |
| 内部执行者边界／非目标 | 原有 userEntryTools 排除保留，未开放内部用户交互入口；无 Plan 入口／Prompt／Task 改造。Global／PA 两级 HTTP wire 与同 ID 冷恢复回归通过。 |
| 测试与构建 | `/tmp/feat705-plan-exit-red.log` 旧实现2处失败；`plan-exit-green.log` 3文件11例通过；同前缀 build／node-build／typecheck／docs／archive 日志成功。新增 tools 断言是 fixture 的 llm/stream，不能写作新增真实 provider／自主模型证据。 |
| Delta／current | 首文档、design 补充、能力 ADDED delta 与 current 的 exit_plan_mode 条目一致，Gateway 能力索引计数69；未发现遗漏的额外行为。**delta outcome：aligned**。 |

历史 V1／V2 继续关闭，R6 对原主从范围的有效通过结论保留；本轮默认值变化没有失效根职责、分层权限、自然委派／日常／补充／交付证据。原 R4 请求的显式 exit 选择和历史统计不被追改为新默认；Issue #460 单独记录开销，不在本次实施压缩。

本轮结论止于已完成的实现／delta 对齐与可信机制证据：没有新增 CRITICAL／WARNING 代码问题，没有宣称新增设置页验收通过、PR 新 head CI 通过或整个新范围产品验收完成。用户停止指令之后只保存、提交这两份报告，未继续核验源码、运行测试或操作环境。

### R7 到达顺序校正（交付记录，未重启审查）

用户要求停止 review 后，产品 reviewer 的完成通知到达：其设置页操作和 R5 报告已在停止通知前完成，报告提交为 `794f3293bbaa180a53da8cb37b5832234fcbfd75`。R5 实际记录新建 SingleThread／Global 默认未选，独立测试 Agent v1→v2→v3 完成开／保存／重载／关／保存／重载，旧 E 显式开启保持，Goal／fork 未联动且没有本轮目录超时。上文“未收口”是静态 reviewer 保存报告时尚未收到该通知的状态，不是一次失败结论。交付方仅同步已完成证据和到达顺序，不追加 review 或测试；R7 已有实现／delta aligned、无存活代码 finding，新增设置要求已有独立 R5 pass。

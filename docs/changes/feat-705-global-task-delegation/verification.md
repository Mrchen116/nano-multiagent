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

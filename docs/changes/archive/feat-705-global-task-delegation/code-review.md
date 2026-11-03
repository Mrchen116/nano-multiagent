# Code Review: feat-705

## Round 1 — full

- `executed_base`: `492b72603cebc5f904f7001b12e3d4475ce55639`
- `validated_at`: `45cd9117cb6183f504cdf63bdb5c8aef4e882dd3`
- `diff_range`: `492b72603cebc5f904f7001b12e3d4475ce55639..45cd9117cb6183f504cdf63bdb5c8aef4e882dd3`
- 独立审查现场：`unit/feat-705`，派发时及审查源码时 HEAD 均为上述 validated_at。仅写审查报告；不修改源码、测试、设计或配置。
- 范围：完整实现 diff 及受影响的配置、原生 lineage／冷恢复、工具执行、产品权限、Workflow 特定 child、Skill／Feature 和占用保护消费链。按 `change-code-review` full 执行，包含 `agent-context-review` Mode B — Implementation Review。

## Findings

```json
[]
```

在已审范围内没有达到 CONFIRMED／PLAUSIBLE 报告条件的存活代码缺陷。该结果不表示 M1 所有验收证据齐备；证据缺口与能力 delta 校正单独记录在 `verification.md`。

## Agent Context Implementation Review

触发原因：本 diff 改变实际工具选择、根／一级／二级职责、共享系统段投影、fork 指导及配置更新时的工具占用解释。

| Surface／生命周期 | 实际检查与结论 | 证据及限制 |
|---|---|---|
| 角色来源／新建／冷恢复 | `child-role.ts:19-61` 从原生 origin、depth、fork descriptor／创建上下文和宿主冻结配置导出角色；模型无法用参数或 Prompt 自授 worker 身份。`index.ts:255-268` 和 `owned-sessions.ts:40-119` 在可信父配置／原生 composition 上共用 attachAgent。 | 源码；新增 global-child-tools 原生 fixture 覆盖 Global／PA、一级／二级及一级同 ID 冷恢复。普通二级同 ID 冷恢复尚无本轮直接请求证据。 |
| 工具／Schema／配置更新 | `capabilities.ts:32-44,69-87` 对已装载原生工具取快照，只让适用内部角色独立于根普通选择；Goal、产品入口和用户提问入口另有限制。根不走 independentTool。`agent-config.ts:180-216` 保留选择撤回和共享配置更新。 | `/tmp/feat705-narrow3.log`，7 文件 18 用例通过；新增 fixture 实际执行 read、spawn、worker fork，并检查根无未选 read／fork。这是实际 DSH + stub，不能证明真实模型选择。 |
| 普通一级系统指导 | `agent-config.ts:154-174`、`global-mode.ts:113-132`：独立局部职责、不复制根 Persona／Inbox，执行完整事项、自主分工、必要问题回父级、内部回传不等于公开交付。参数仍用 DSH 原生工具及原生父 ID，无额外 Nano 报告工具。 | 新 fixture 的 `llm/stream` 请求与原生工具执行；没有本轮一级最终 provider wire 可替代项。 |
| 普通二级系统／任务／来源 | `agent-config.ts:134-147,154-174`：不注册产品身份／一级指导，并过滤共享 nano-* 系统段；保留 DSH 原生 AGENTS、parent ID、子目标及工具说明。权限仍由宿主实际身份执行。 | 新 fixture 对合成 sentinel、原生父 ID 和 AGENTS 的实际适配前请求断言；不将其声称为 provider 序列化或模型消费证据。 |
| worker fork／继承 | `child-role.ts:23-40,64-66` 和 PA／Task／UI 的 internal execution 投影使二级 worker fork 与有效一级父配置保持系统／工具一致，保留原生前缀与现有最窄任务尾说明；没有新根开关 Prompt 分支或取消流程。根直接 fork、SingleThread 继续原规则。 | global-child-tools 对 worker fork system 内容／schemas 与一级相等；既有 task-child-context／llm-attribution 可证明其原有受控 wire 边界，不外推为本轮普通二级 wire。 |
| 保留／撤回／占用 | `capability-state.ts:28-37,69-74` 与 `index.ts:626-653`：真实调用仍记账，仅根普通选择的占用投影排除独立 worker 工具；Feature／Skill 占用不因此免除。Workflow 冻结 scope 通过 scopedChildren 保持非目标角色。 | capability-state 新例保护 root read 撤回和 shared Skill 占用；原生 fixture 验根新输入与 worker 运行。`/tmp/feat705-role-boundaries.log` 4 文件 9 用例通过，保护既有 Workflow／维护／PA 权限；不等于新增所有角色更新组合已逐一执行。 |

审查复用了实施记录中与本 SHA 适用的红绿证据：`/tmp/feat705-baseline-red.log` 将五个 runtime 文件暂退至 fcd995949 并重建时新增风险用例真实失败，恢复候选重建后通过；该记录不被当作另一个受审版本。未另起真实服务、未重复全量检查。

## 未验证条件

- 普通 Global 和 PA 的真实模型自然旅程、原事项补充／日常短问／真实公开交付仍待实施 owner 和产品 reviewer 提供定位；无证据支持“模型必定委派正确”或“模型一定误解”的断言。
- 本轮新增普通一级／普通二级／worker fork 的最终 provider 请求（转换时含 upstream）尚未提供；适配前捕获、catalog preview、旧 fork wire 不替代此证据。
- 普通二级同 ID 冷恢复及要求的共享撤回／深度边界最终证据、required CI 尚待收口。此处不把未完成检查伪装成代码 bug，也不凭 `[]` 放行 Gate。

## Round 2 — patch，含 main 交互核查

- `executed_base`：`aa0a3d126c5bf88a20af87c7c9db458706ea3c4e`（已同步的 feat-703 主干基线）。
- `validated_at`：`9af20eae88a5f327ad9981d3a81eae029809fab2`。
- 前次受审实现：`45cd9117cb6183f504cdf63bdb5c8aef4e882dd3`；本轮检查其后本 unit 的指导、测试和 delta 改动，以及 feat-703 合入后与角色／产品权限的实际交互。R1 full 覆盖保留，不重复审 feat-703 全部业务实现。
- 现场 `origin/main` 已为 `43cc90051cf9f037b58658fea86bb6e041681fac`（bugfix-706 文档）；`git merge-base origin/main HEAD` 为上述 aa0。故 `origin/main...9af20eae8` 的实际分支 diff 仍从 aa0 起算，不把移动 ref 标为 aa0，也不切换现场。
- `review_mode`：`patch`；Context 审查：Mode B — Implementation Review，沿本轮变化的组合／交付／恢复链复验。

### Findings

```json
[]
```

R1 代码 findings=[] retained；本轮未发现新增确认代码缺陷，也无需要扩大为另一轮 full code review 的共享边界变化。产品报告 R1 的真实失败保留，不能用本结论代替其行为复验。

### 实际复验

| 变化／Surface | 本轮判断与直接证据 | 边界 |
|---|---|---|
| 根协调系统指导、Persona／AGENTS 组合 | `global-mode.ts:35` 明确完整独立事项先委派，把通用资料读取／实施／验证要求交执行者，根仍处理只有自己能取得的产品事实和用户决定；`:39` 按独立请求产物区分新事项与原成果修订。与 R4 的“不重复调查、不同事项各有一级”一致，不引入新 router／Task 流程。 | 源码确认已经针对 R1 行为修正；不证明真实模型已不重复阅读或已正确区分同主题新单。R1 acceptance 的失败未关闭。 |
| 普通一级／二级最终 provider 请求 | `global-child-tools.test.ts:107-203` 在本地 HTTP server 直接读取 Anthropic `system/tools/messages`；llm/stream middleware 仅追加 native ID／depth／fork 元数据并 `yield*next()`，不替换模型回复。响应通过真实 SSE adapter 触发原生 read／subagent／fork。 | `/tmp/feat705-provider-wire2.log` 2/2；`/tmp/feat705-r2-narrow.log` 2 文件 7/7；此为真实运行时和最终 wire、受控 provider 响应，仍不属于自然模型选择证据。 |
| 二级无身份、原生父 ID／AGENTS；worker fork 继承 | 直接断言二级 wire system＋messages 无根 Persona／Nano 身份／PA／一级职责，保留 AGENTS 与原生父 ID；worker fork tools 与一级相等，system 仅去除传输 cache_control 后相等，未裁改前缀正文。 | 替代 R1 的适配前捕获缺口；这是同一风险用例升级，没有新增平行镜像套件。 |
| 一级＋普通二级冷恢复 | 用实际原生 send_message 从根回原一级，再由一级发原二级；runtime 重启前后两级原 ID 各有新增 HTTP 请求，总 native ID 集合保持 4，二级收到原父级的接续消息。 | 两级同 ID 恢复机制已补证；未声称覆盖每种真实模型／不可恢复失败。 |
| feat-703 PA 创建长期 Agent 与工具投影 | `capabilities.ts:78` 合并保留 isOrdinaryChild／globalWorkRole 并增加 agent_creation；`personal-security.ts:179,209-213` 保留 internal execution 指导和创建工具注册。新增 wire 配置显式给 PA 根选择 agent_creation，一级／二级均断言不可见，worker fork 因与一级 tools 相等同样不可见。`product-bridge.ts:22` 及 `personal-assistant/global-agent.ts:477` 仍按可信 root 身份拒绝 child 创建，不依靠 Prompt。 | `/tmp/feat705-main-sync-regressions.log` 23 passed／2 failed；失败均为 personal-security 的目录检查超时，不把整个文件写成通过。新 wire child 权限与后端创建回归已通过。 |

### 证据限制与退出

- R1 acceptance 真实观察到根重复调查和 PA 新事项错误归属，新增指导仅证明修复已落实源码；必须等待自然旅程 R2 才能判行为关闭。R1 没有实际代理日志，上下游真实请求不可追补。
- 同环境原主干 runtime 源对照的 `/tmp/feat705-main-baseline-catalog.log` 同样报 `Capability inspection deadline exceeded`；可排除“仅候选才出现超时”的判断，不能仅凭此证明环境是唯一根因或关闭设置开关场景。候选目录两项超时、daily bootstrap 阻塞及完整 CI 未收口继续记录在 verification。
- 本轮没有起栈、重跑全量、改变测试阈值或源码；仅追加两份审查报告。没有新增 code finding，M1 仍未通过。

## Round 3 — patch，最新 main 交互

- `review_mode`：`patch`；`diff_range`：`9af20eae88a5f327ad9981d3a81eae029809fab2..30eafa50c80182bb39cb2b26fe01c0729f3ba78b`。
- `executed_base`：`3da78a00a7cc8ace9d172c0b0d59c5d6e7881e0b`；`validated_at`：`30eafa50c80182bb39cb2b26fe01c0729f3ba78b`。现场分支 `unit/feat-705`，审查开始 clean，HEAD／origin/main 与派发完整 SHA 一致。
- 本轮无 feat-705 新增产品源码；检查同步 main 的 PA-only tripai Skill 目录／默认值和 bugfix-707 Dreaming 测试生命周期。R1／R2 审查及其版本不改写。
- Context：对 Skill 来源→目录选择→按需加载及内部执行者继承配置做 Mode B 影响复验；不把导入的上游 Skill 正文当成需要执行的本轮审查指令。

### Findings

```json
[]
```

没有新增存活 finding，无需扩大 full code review。旧代码结论 retained 的范围是未变的角色投影、工具独立性、宿主产品权限、Goal、受控 wire／同 ID 两级恢复，以及 R2 指导修正的源码一致性；不包含尚未完成的真实模型行为关闭声明。

| main 变化 | 影响核查与结论 | 证据与限制 |
|---|---|---|
| PA-only tripai builtin Skill | `apps/node/src/configuration.ts:112` 仅由 canonical.personal_agent 追加 personalSkillsRoot；`apps/node/src/capabilities.ts:61` 仅 PA 的 builtin tripai 条目 default_on。普通 Global／SingleThread 不因 feat-705 的 globalWorkRole 取得 PA 专用根。 | Node configuration／capabilities 新矩阵及 `/tmp/feat705-r3-regressions.log` 4 文件 22 passed。 |
| PA 工作层 Skill 与工具／身份边界 | 内部执行者仍沿可信 PA 配置取得相同 Skill roots，并经 `capabilities.ts:168-195` 的既有显式 allowlist／denylist 执行发现和加载；这不是新 PA 产品身份或新工具授权。ToolSelection／二级 nano-* 系统段过滤／ProductBridge 未因该 main 合入改变。一级用 DSH 工作工具，普通二级保持无 Nano 身份；不通过 Skill 恢复根产品工具或被禁 Skill。 | 源码交互确认；tripai 是可选任务方法，没有新增宿主工具、parent-ID 或委派职责。R3 原生 child／wire／coldrestore 与 Goal 窄回归继续通过；未执行旅行 API 或缺凭证配置，不声称验证了真实旅行模型行为。 |
| bugfix-707 Dreaming 测试 | 改动只在测试观察临时 Session 的公开 disposed 事件，等待 receipt／释放后读 durable trajectory；保留原应用、来源、权限、warm／cold 断言。无 Dreaming 产品实现、业务 Context、role 或 schema 修改。 | 核对完整 test diff 和归档独立报告；不新增 feat-705 范围，不使旧产品代码结论失效。 |

复用 `/tmp/feat705-r3-{build,typecheck,docs}.log` 的对应成功结果；构建记录明确 candidate SHA。此前全套 184 文件先通过、25 个失败文件后续串行复验全部通过的分段记录保留其执行边界，不描述为同一次完整绿色执行。本 reviewer 没有重跑全量或启动 runtime。V1 仍等待产品／最终门禁证据，不能据 findings=[] 关闭。

## Round 4 — patch，交付前重复调查职责修正

- `executed_base`：`3da78a00a7cc8ace9d172c0b0d59c5d6e7881e0b`；`validated_at`：`f51486fd6a20ef81f633397ba270bfdc293318f5`。
- `review_mode`：`patch`；`diff_range`：`30eafa50c80182bb39cb2b26fe01c0729f3ba78b..f51486fd6a20ef81f633397ba270bfdc293318f5`。其中 ab8973f8b 仅追加独立 R2 acceptance；实质源码仅 global-mode 两段。现场保留此前本 reviewer 的两份报告修改，无其他源码 dirty。
- Context：Mode B，检查根指导与原 Persona／AGENTS、一级执行职责、返工／公开交付的组合。

### Findings

```json
[]
```

`global-mode.ts:35` 把通用验证要求明确覆盖到一级返回结果以后；`:39` 保留主 Agent 按需查看成品、目标覆盖、可用证据和具体缺口的责任，禁止例行重读原始材料／重新验证，把具体遗漏、矛盾或证据问题交回原执行者。它收窄重复调查的阶段解释，没有撤销结果核对责任、真实交付义务、用户决定或宿主权限，不引入特定资料清单／任务专用判断。R4 与原 spec／R4 design 一致，无新增源码缺陷。

证据区分：R2 acceptance 对 `30eafa50c` 的真实失败已具体定位到交付前完整重读四份原文，不能以此 patch findings=[] 关闭该产品问题。`/tmp/feat705-r4-build.log` 为提交前工作树构建，输出标签仍是 ab8973f8b；现场构建产物 `lib/global-mode.js` 已核到这两段候选文本，不能将日志标签谎写为 f514。`/tmp/feat705-r4-narrow.log` 2 文件 7 passed，保留原生 wire、两级恢复和 Goal 保护；未代替 R3 自然模型旅程。V1 继续收集证据。

## Round 5 — patch，协调指导前置与日期 UI main 同步

- `review_mode`：`patch`；`diff_range`：`f51486fd6a20ef81f633397ba270bfdc293318f5..c46e35c43c12b744d4c05be160dc173d25bde499`。
- `executed_base`：`90efdd3dc2c1dda9efd5ffc0f2acbb01f5492dde`；`validated_at`：`c46e35c43c12b744d4c05be160dc173d25bde499`。现场 HEAD／origin/main 与派发一致；dirty 仍只有本 reviewer 两份报告。
- 实质源码为 `09f13da4cc4d4b56bf1abb685d246adf3113eb96` 的根 Global 协调指导修改；main 增量为已独立审查的 Web 时间分隔，不把整段移动机械视为全新 full 审查。
- Context：Mode B，聚焦指导顺序、Persona／AGENTS 解释及日常直接处理边界。

### Findings

```json
[]
```

根 `nano-global-mode` section 仍为 order 800，修改只把既有协调段放到该 section 首部，并用“先决定执行者，再打开任务材料”“多来源分析／文档／实现即使只有几次工具也整项委派”“Persona 先读不是根初始化清单”消歧。它没有改变 Persona section 的注册顺序、层级或宿主强制规则，不能描述成已建立跨 section 的硬优先级保证。结果仍须通过实际组合和模型行动确认。

日常交流、状态、回顾、待办查询及小型直接动作仍明确由根处理；根独占的聊天来源核实、用户决定、唯一公开交付、原事项补充和成品缺口核对均保留。基于用户交付目标识别完整事项，没有新增“工具步数达阈值就委派”规则或硬路由。Inbox／公开发送／持久性段只是移位、正文保留，普通一级／二级／fork 的装配和工具 schema 无新变化。未发现本 patch 的确认缺陷。

main 的 MessagePane 时间分隔只计算并展示既有 message.created_at；不改消息存储、向模型送入的正文、发送 payload 或子会话身份。其既有独立审查与当前交互边界足够，不扩大本轮 Context 审查为日期功能重审。

R3 自然验收已确认 f514 实际 upstream 仍发生根委派前重复读；因此该问题不是旧版运行的假象，不能以更清楚的源码措辞判关闭。新源码尚未构建进入正在运行的完整后端检查，`/tmp/feat705-r4-backend-serial.log` 当前只有启动信息；本 reviewer 不把该运行记为 c46 新指导的执行证据，也不重建 lib 干扰检查。待 owner 在完整运行结束后提供候选 build、最窄真实 wire／Context 回归及 R4 自然旅程再收口。

## Round 6 — final closure

- `review_mode`：`closure`；`validated_at`：`c46e35c43c12b744d4c05be160dc173d25bde499`；`executed_base`：`90efdd3dc2c1dda9efd5ffc0f2acbb01f5492dde`。
- 现场 HEAD `97edacf4abf61586fa7e6fa429f6b96c43d26496` 只比受审点增加 R4 acceptance；已核源码／测试／锁包 diff 为空。origin/main 仍为上述 base。本次不更换原受审 SHA；保留 caller 的 progress 修改及本 reviewer 已写两报告。
- focus：前轮已完成 patch 的有效性、V1 所需最终交付／消费证据及历史产品问题关闭状态。R1–R5 代码 findings=[] retained；未新增源码，不再做 full，也未重跑全量或改变现场。

### Findings

```json
[]
```

没有存活代码 finding；不需要追加代码修正。Context Mode B 的最终证据已由 R4 的实际 provider/upstream、原生执行和公开回执补齐：

- `acceptance.md` R4 定位根 `b3ff8b87-6231-4740-bab7-3df5d3bd2789` 和唯一一级 `fd7fd198-8c91-443d-95e5-0eefdb3aa112`。私有代理 session req／raw openai_codex headers、upstream-req 对应 00:43:34.225／00:44:01.526，真实输入含最终 main coordinator 指导并保留原 daily Persona。不是仅根据源码或 llm/stream 推断模型收到规则。
- 产品 reviewer 核对全部三个根 turn：委派前无原始材料 read／调查命令，根直接回答45分钟、补充原生发回同 ID；一级调查并核查，根只读 r4-qa.md，实际公开交付 `a11e29aa507c4d4ba0ed0ca53e802ab7`，结束通知后无重复发送。原先“根先调查／根交付前再调查”的问题均在同一任务全程关闭；不从一次成功外推所有任务必定可靠。
- PA 新旧目标归属的 R2 自然证据、手动 fork 完整开关的 R3 Web 证据，以及普通二级／worker fork／两级冷恢复的受控 HTTP wire 证据沿各自范围 retained。保持真实模型、受控 provider 和 UI 证据的区别。

完整后端 210 文件1129项通过，执行的是 f514 已构建 lib；该轮不验证随后新增根指导。c46 的 build／typecheck、4 文件12项最新 wire／恢复／Goal／Context revalidation／native communication 窄回归与 R4 自然行为共同补足该指导差异。最新 main 前端112文件1059项通过；Python129项、ruff、docs、iOS runtime 与 critical audit 门槛按 verification 的定位复用，没有把分版本证据拼成一次全树单运行。

closure 状态：V1 的实际产品阻断及缺失证据已关闭；V2 在 R2 已关闭，能力 delta 仍 aligned。未触发的“返回成品有实质缺口／原执行者失联”模型应对保留未观察，不伪称发生，也不要求破坏原生状态制造失败。能力目录偶发超时曾发生，R3 通过页面现有刷新恢复并完成开关；本次没有其根治声明。PR、远端 CI、部署状态不属于本次已完成事实。

# feat-725 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/eval_dag_design_review`（独立于本轮设计作者）
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖 spec、design、prototype、既有入口与迁移输入。
- started_at: `2026-11-07T12:48:50+08:00`（首个显式时间采样；此前阅读不计入 duration）
- completed_at: `2026-11-07T12:50:20+08:00`
- duration: `90s`（显式计时段）
- validated_at: `6db4c258ac1bd4d33f38ab434a4f03ef01f7ffcc` + 本轮未提交的 `spec.md`、`design.md`、`prototype.html`；工作分支 `codex/eval-agent-coordination`。既有未提交 `evals/agent_coordination/` 与 `evals/README.md` 是审查输入，未修改。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

方案的复用方向成立，但分支/接续契约、前端关键关系的可审程度与真实通信验收存在实质缺口，当前不能通过 Gate 2。

### Coverage 与证据

- **现状与真实组装入口。** 从根 `package.json` 的 `eval-ui → tsx evals/ui/server.ts` 核到 `main → catalog → startViewer`，再核 `app.js` 的 suite/case 导航与 `native.js` 挂接。当前 catalog 只有 Memory 空目录和四个 Intelligent UI case；Memory 历史归档通过 `EvaluationArchive` 接入。复用这一服务和 observer 桥、保留 suite 自己的执行与评分，比另建前端/模型调度入口合适。新 Python engine 属于协作 suite 控制层，不应进入产品 runtime。
- **四 suite 的来源。** 核到 `evals/memory/examples/synthetic.json`、Intelligent UI dataset、Spec/design alignment dataset 指向的八个 `case.json` 与 public brief；design 指定的目录扩展有真实数据来源。保持 alignment judge-private 不进入公开案例详情、页面只读取登记材料，以及历史 Memory 原件不变的边界合理。最终呈现仍待实施。
- **GC-01/02 迁移输入。** 核到两个旧回放器与 case.md、score.py、provider.mjs。GC-02 包含硬前置停止、U06–U08 每轮独立措辞分支、U09 字母/明确文字分支；GC-01 包含独立任务链、路线图收到决定后再回报、同一/不同执行者的首文档回报。不能只把消息表搬进 JSON 而丢掉这些控制语义，见 R1-W1。
- **原语与职责。** design:11–17 已区分 `delegate/user_reply/child_message` 为观察、`user_message/worker_message` 为脚本驱动。主 Agent 负责实际派工，scripted child 经原生 `send_message` 工具回报；provider:72–80 支持该路径。共享 adapter 与纯调度器分离、用 dispatch/poll 假传输测试 DAG 是合适的测试缝隙。这里无需新增通用产品 Agent Loop 或额外跨 suite 评分器。
- **Agent Context Review — Design 模式。** Consumer 为真实主模型与原生子会话；Surface 为 IM 用户输入/附件、派工及续派、内部回报。控制资产保留在候选 workspace 外，只有选中的自然内容进入模型；把队列回执和实际模型输入分开、`after_report` 按根模型实际收件排序，是正确决定。read advance 在本设计中是 fixture 推进阻塞模拟轮次的机制，不应被报告成主 Agent 自行选择的动作。未运行真实模型；实际交付退出标准缺口见 R1-W3。
- **原型与画面证据边界。** reviewer 的 `file://` 浏览器打开被 URL policy 拒绝，未用 HTTP 等间接路径重试。独立查看了作者提供的本地截图 `.playwright-cli/page-2026-11-07T04-48-18-034Z.png`：1280×720 下四 suite 标签、单链与右侧正文可见，短正文易读。该截图不证明互动、分支、长文或窄屏。另以原型源码核对互动与内容关系，见 R1-W2；没有将源码检查写成浏览器体验通过。
- **用户约束、delta、milestone 与 runbook。** 设计覆盖单服务、可扩展 case、保留原话/图片和前置控制的目标，保留既有未提交资产；不涉及生产部署，无一次性部署提示词。评测工具没有产品 current spec 的行为增量，`no spec delta` 合理，README 是维护入口。M1 包含 loader/engine/adapter、迁移和 viewer 回归，但目前前端契约与真实消费验证未闭合。runbook 的静态预览零模型调用和真实回放单独启动边界合理。

### 历史问题闭环

首轮，无历史问题。

### Issues

#### R1-W1 — `when/fallback` 与 resume 还不是可兑现的分支契约

- **位置：** `design.md:11–17`、`:35`；`evals/agent_coordination/cases/gc02/case.md:23–29`，旧 `run_gc02.py` 的 U06–U09 分支。
- **证据：** 方案只列出 `when`、`fallback` 字段和 matcher 的词法能力，没有规定条件观察哪个事件窗口、等到何时决定 fallback、条件不成立是 skipped/failed/blocked 中哪一种，以及依赖未选分支的汇合节点何时可走。状态展示只有 passed/failed/blocked/pending。`after/order_after` 的失败传播不能独自表达这些选择。resume 也只写“结果明确”，没有说明已作出的内容选择与观察游标是否复用。
- **具体影响：** GC-02 U06–U08 是每轮“有真实前文用历史原话、截止仍无则用独立版本”，U09 则是“没有公开问题不投递；有问题再选择 B/明确文字”。作者与实施者现在可能把未选路径当失败传播，或者恢复时按新的可见前文改变已选正文；这会改变用户实际发出的原话和后续合法性，也无法保证新增 case 只填写数据即可运行。
- **建议：** 收口一份最小条件与状态契约，给 GC-02 的一个措辞分支和一个硬停止分支提供 JSON 示例，说明条件来源/时间窗口/截止、互斥选择/汇合、失败与不适用的传播，以及 resume 持久化哪些选择和证据。无需建立通用表达式语言或罗列实现步骤，但不能把现有必需语义留给实施时决定。

#### R1-W2 — 原型尚不能评审本次核心 DAG 阅读与节点详情关系

- **位置：** `design.md:23,31,45`；`prototype.html:1–5`。
- **证据：** 截图与源码中的图只有 U04→D01→S11→U05e 四节点单链；没有成功边/顺序边区别、条件分支、独立任务或阻断范围。suite/case 与任务筛选按钮没有交互；切节点只更新 `name/detail`，谁到谁、前置与检查项仍固定为 S11。完整历史正文、附件、来源没有代表性呈现；窄屏没有按序列表，现有 media query 只是把 article 移到第二行。design 只列 must-match 名称，未给对应状态/viewport/退出结果映射，并把真实 GC 内容检查留到实施阶段。
- **具体影响：** 用户现在不能用这份原型判断“整个 case 是什么样”“缺前文会影响哪条线”，也会在切到用户消息时仍看到子 Agent 的收件检查；实施者缺少可遵循的完整节点信息组织。短正文截图不能证明长报告和几十节点的 GC-01 可读。
- **建议：** 以实际 GC-01 的一个有独立旁支的决定流程呈现连线、过滤、选中前后关系与阻断状态；节点切换同步全部详情。加入一份真实长报告/附件来源和窄屏阅读路径，其他 suite 至少能看出 case 选择后如何进入材料及返回。补 must-match 与状态/viewport/退出结果的映射，并实际渲染走查、标明仍未验证部分。无需复刻整份 GC-01 或实现真实后端。

#### R1-W3 — 真实收件边界被要求保留，却没有进入本 unit 的有效验收

- **位置：** `spec.md:39–48`；`design.md:13,27,35,45`。
- **Context surface / expected：** 主 Agent 与子 Agent 应实际收到相应消息/附件，公开追问只能在相关回报进入根模型后触发；排队与真正消费必须可复查。
- **Observed / evidence status：** **CONFIRMED，设计级验收缺口。** design 明确本轮只以“无模型的假传输”验证 engine，把真实 A/B 留待后续；M1 退出标准允许保留“真实模型未测”。旧 provider 的 `/control` 只返回 accepted 入队，`script_emit` 是发出工具调用，根/子模型请求才是消费证据。GC-01:268–273 的 read advance 正说明真实运行存在“排队但尚未消费”的状态转换，纯调度假传输不能覆盖此 adapter/provider/原生通信组合。
- **具体影响：** 共享回放器可能在单测全绿时把入队/工具发出误记成已读，错误投递“这两个点我都同意”等依赖用户消息；这直接违反 spec 的核心评测边界。这里没有声称新实现已出现该 bug，而是所选验收无法排除这一类实质走偏。
- **建议：** 将一个最小隔离链路加入本 unit 退出标准：真实主 Agent 派工→脚本子 Agent 回报→根模型实际收到→IM 公开问题→用户回复→同一子模型实际收到续派，必要时覆盖一次 read advance，并关联 run/会话/消息与实际请求证据。可以复用旧隔离启动器、仅跑有代表性的短链，不要求完整 A/B 或新的评测分数；完整 GC-01/02 的模型效果比较仍可后续单独运行。若用户明确将本轮范围收缩为静态工具/模拟验证，再同步调整 spec 与结论边界。

### Recommendations

- **R1-R1（可选）：** run 记录中显式标注 fixture read advance 的触发证据、目标、次数与结果，并与主 Agent 真实工具动作分开。design:13 已限制一次推进，可用这一条收据帮助之后全案审阅解释“为什么这轮继续了”，无需增加新的 Gate。

### Author Resolutions

- R1-W1 accepted。design 新增条件、观察窗口、终态、fallback、汇合与持久化契约及 GC-02 两种分支实例。
- R1-W2 accepted。原型修订为多任务、可过滤、完整动态详情和阻断分支，补充 must-match 验收映射，桌面与窄屏实际走查。
- R1-W3 accepted。M1 增加真实默认配置 Global 最小通信链，核对实际请求与公开 IM 顺序。
- R1-R1 accepted。read advance 记录 fixture 目标与消费证据，独立于主 Agent 工具轨迹。

## Round 2

### Metadata

- reviewer_target: `/root/eval_dag_design_review`（沿用独立 reviewer）
- review_mode: `delta`
- mode_reason: R1 后新增了条件/状态/接续接口、真实通信退出标准和可交互原型；除旧问题闭环外，检查这些变化对数据消费与阅读路径的影响。
- retained_from: `Round 1`。未变的真实服务组装、四 suite 来源、模块职责和依赖方向、控制资产隔离、无产品 spec delta/无生产迁移判断继续有效。
- started_at: `2026-11-07T12:54:38+08:00`
- completed_at: `2026-11-07T12:55:46+08:00`
- duration: `68s`
- validated_at: `6db4c258ac1bd4d33f38ab434a4f03ef01f7ffcc` + 本轮未提交设计树；SHA256：`spec.md=7386ff90a2388c9a83b2c28e65d48552307648ce67299e16e21ed9b8038e1589`，`design.md=f447322d42bef693a2b23eccf59e38376126b0d6dd2ec430880f79c70d9dd330`，`prototype.html=55e7f5fc4fded5809fd625d857aab4d481711af057440cbd00aab2255e741420`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

现有设计已足以指导实施。这里批准的是方案，未将原型或计划中的最小链路当作产品实现、真实通信或完整 GC-01/02 评测通过。

### Coverage 与证据

- **条件与生命周期。** `design.md` 的“条件、状态与接续契约”明确了硬依赖/顺序约束、节点独立截止、content/fallback 互斥内容选择、untriggered/failed/blocked 的区别、并行汇合及 checkpoint 的 chosen、正文、请求/消息 ID、绑定与 intent/receipt。新 case 所需机制保持在共享 engine 中，不引入 case Python 分支函数。多候选绑定不硬猜，通过已匹配真实子会话的 bindings 收据选择；同会话多阶段与 S12 分开执行者的分别回报也有表达方式。
- **本轮条件消歧。** 核对到 U09 的选项消息会早于观察节点完成，本轮指出若复用新窗口扫描会漏掉该消息。作者已补 `when.evidence_node`：直接检查已成功前置的收据正文，不再套当前时间窗口；仅 `source=public` 扫描新的公开消息。该决定与两种 GC-02 分支实例、恢复时不重新选正文的契约一致。无需再引入通用条件语言。
- **Agent Context Review — Design 模式增量。** 新增“真实通信验证”明确作为 M1 的额外退出要求，使用新建隔离默认 Global、Sol 6.1 high，覆盖真实主派工、脚本子回报、根模型收件、IM 提问/回复与同一子模型续派收件，并包含 fixture read advance 及收据，以 wire/native/IM 对齐。这样纯 DAG 测试与实际消费边界各有验证；完整效果 A/B 仍独立，不阻碍本轮最小真实链。read advance 始终归 fixture，未混成主模型行为。
- **原型内容与关系。** 修订原型用 iOS 成功依赖链和独立 Computer use 旁支表达并行，加入 Q11 公开问题和 U05e 批准的因果门；过滤、阻断示意与节点选中详情各有动作。`show()` 整体重建流向、正文、前置、来源、检查与附件声明，不再沿用 S11 固定详情。实际长历史回报保持 14px/1.8 正文；完整图缩放和全量 GC 节点不必在设计原型复制，已明确由 M1 实际页面验证。
- **实际画面与交互证据边界。** 独立查看作者渲染的桌面截图 `.playwright-cli/page-2026-11-07T04-53-58-850Z.png`，可辨识两个任务与长正文阅读区；查看窄屏初稿 `.playwright-cli/page-2026-11-07T04-54-13-106Z.png` 时发现 Memory 页面残留旧 DAG，结合源码确认是内联 `display:grid` 覆盖 `.hidden`。本轮作者修正为 `.hidden{display:none!important}`，并提供修复截图 `.playwright-cli/page-2026-11-07T04-55-38-585Z.png`：Memory 中旧图已消失、材料可读。作者另报告 Playwright 已核查隐藏图和过滤后的单旁支节点；reviewer 没有独立执行这些浏览器互动。独立观察实际截图与源码，足以确认本次有界原型关系；不据此声称窄屏所有长文/全量图交互均已实测通过。
- **验收映射。** 新 must-match 表把导航、图/过滤、动态详情、阻断范围、390px 阅读分别映射到状态与 M1 实际服务结果，原型背景/示意和最终完整数据的边界清楚。各 suite 继续保留自己的执行与判定，协作通信协议没有扩散到其他 suite。

### 历史问题闭环

| Issue | Author Resolution | 本轮核实证据与结论 |
|---|---|---|
| R1-W1 | 新增条件、窗口、状态、fallback、汇合和持久化 | 上述契约及两个 GC-02 实例已收口；本轮补 evidence_node 排除前置收据的窗口歧义。**closed** |
| R1-W2 | 多任务过滤、动态详情、阻断状态、长文与 must-match 映射 | 桌面实际截图、原型 show/draw、窄屏修复截图与状态映射可共同复核；套用旧详情与跨 suite 图残留均已消除。**closed** |
| R1-W3 | M1 增加真实默认 Global 最小通信链 | “真实通信验证”明确是 M1 额外要求，实际根/子请求和公开消息对齐，不接受只凭入队。**closed** |
| R1-R1 | fixture read advance 与主 Agent 行为分开记证据 | 最小链明确包含一次推进及对应收据，保留 Context 消费核验。**closed** |

### Issues

无未解决 CRITICAL / WARNING。本轮发现的窗口消歧与跨 suite 残留已在当前 Round 有界修正并核实，没有另起循环。

### Recommendations

无新增建议。

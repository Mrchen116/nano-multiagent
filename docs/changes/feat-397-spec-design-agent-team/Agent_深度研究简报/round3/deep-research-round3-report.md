# 第三轮深度研究报告：以核心命题为中心的 spec/design multi-agent 架构设计

> **核心命题**：单个 agent 做不好软件需求的 spec/design 对齐——委托方放手后，现有单-agent SDD 垮掉的根因是什么？什么样的 multi-agent 结构能真正补上能力（而非只加成本/噪声）？黑盒 LLM 下如何落地？
>
> **前两轮已建立**：品味编译五层方案、Generator-Critic 顺序对、Claude Code 独立 context 机制、Artifact 文件传递、四阶段顺序流水线推荐拓扑、Escalation 三层结构、评测 harness 两层设计
>
> **本轮任务**：以 12 个同场景源的深挖笔记（pm-skills、agent-review-panel、AgenticAKM ×2、sample-claude-code-agent-team、gsd-core、MAD-RE、iReDev、Architecture Without Architects、Traceability-Accountability、Single-MAS-Both、QUARE）为证据，围绕核心命题给出第三轮综合结论
>
> **完成日期**：2026-06-04
> **标注纪律**：🟢SHIPPED（真在产品/开源运行，注明谁）/ 🟡RESEARCH（仅论文）

---

## 1. 单 agent 在 spec/design 上的失败模式目录

这是委托方放手后 SDD 垮掉的根因清单。每条都有来自本轮源的新证据（前两轮已有的不重复列举，只在必要时交叉引用）。

### F1：单一 objective 满足即止（Early-Stop）

单 agent 的优化目标是"产出一份看起来合理的 spec"，一旦内部判断"这份 spec 已经合理"，就停止深挖。没有外部视角来质疑"这份 spec 真的能达成目标吗？"

**本轮新证据**：
- gsd-core（🟢SHIPPED）的 goal-backward 方法论正是为了对抗这一失败：单 agent 的 spec 是"任务满足型"（完成了要求的内容），而 must_haves.truths 是"结果满足型"（用户视角可验证的真实结果）。两者的差距就是 early-stop 遗漏的内容。
- AgenticAKM（🟡RESEARCH）的 AdrChecker 在第一轮就打回了 Generator 以为"正确"的 ADR，因为它声称的细节（"webrick ~> 1.7"）在实际代码库中无法找到支撑。单 agent 无法从自己外部质疑自己的假设。
- Single-MAS-Both（🟡RESEARCH）实测：约 80% 的任务 SAS 和 MAS 产生相同结果（"Both Pass"），但这是在有明确正误判据的任务上；open-ended 的 spec/design 任务无此数据。这告诉我们：early-stop 在"有验证标准的任务"上已被模型能力进步部分修复，但在"无客观答案的 spec 任务"上仍是结构性问题。

**失败的根因**：objective 是主观的（"写出一份完整的 spec"），没有外部锚点（"每条 truth 在 spec 里都能找到覆盖"）迫使 agent 从成果角度反向检验。

---

### F2：无法可靠自我批判（Self-Review Impossibility）

同一个 agent 既写 spec 又判断 spec 是否合格，等于"自己出题自己判卷"。在没有对抗压力的情况下，agent 倾向于认为自己产出的内容是正确的。

**本轮新证据**：
- pm-skills（🟢SHIPPED）的设计文档中直接写道："A skill that self-reviews has a perverse incentive (pretend the output is good). A separate sub-agent does not."——这是产品级代码库中的原话，不是理论推测。
- sample-claude-code-agent-team（🟢SHIPPED）在 `fullstack-agent.md` 中明确写死："Self-review is a category error — review-agent's role is adversarial, and grading your own homework defeats the purpose of the gate."
- Traceability-Accountability 论文（🟡RESEARCH）量化了这一失败：Claude 担任 Executor（生成者）时损害率 0.25%，但担任 Critic（审查者）时损害率飙升至 1.90%——**同一模型在 Critic 角色上的行为显著劣化，且高方差**。这证明 Critic 角色本身就会产生异常行为，需要单独控制。

**失败的根因**：生成者和审查者共享 objective（"让 spec 看起来好"），不存在真正的目标分离。审查是形式性的，不是对抗性的。

---

### F3：Context 装不下"全局产品 + 深度架构 + 调研"（Context Overload）

spec/design 的输入是多源的：用户 brief、历史对话、产品文档、codebase 架构、类似产品调研、约束文档。把所有这些塞进单一 context 窗口，注意力必然分散，顾此失彼。

**本轮新证据**：
- gsd-core（🟢SHIPPED）把这作为头号问题在 README 中点名："solves context rot — the quality degradation that accumulates as an AI fills its context window"。每个重任务在新的 ~200K context 子 agent 中执行，orchestrator 保持轻量。
- Single-MAS-Both（🟡RESEARCH）提供了 Edge-Level 缺陷的定量证据：当上游 agent 把过多信息传给下游 agent（包括边界情况、冗余约束），下游 agent 的表现反而比单 agent 更差（"overthink"失败模式）。这是 context overload 的对称风险：不仅"自己的 context 太满"会降质，"收到的信息太多"也会降质。

**失败的根因**：spec 任务需要同时持有"产品意图"（brief）+"技术约束"（架构知识）+"领域规范"（标准/constitution），单一 context 窗口无法在这三者之间保持均衡注意力。

---

### F4：无对抗压力 Surfacing 假设（No Adversarial Pressure）

spec-author 生成的 spec 中有大量未经验证的假设（"用户会接受这个 UX"、"这个接口可以做到幂等"、"这个功能不需要离线支持"）。单 agent 不会主动质疑这些假设，因为生成者的 objective 是"写出完整 spec"，不是"暴露 spec 中的薄弱假设"。

**本轮新证据**：
- QUARE（🟡RESEARCH）的消融实验：移除协商阶段（Phase 2）后，冲突检出率大幅下降——这意味着 spec 看起来完整，但暗含的冲突（比如 Safety 需求和 Efficiency 需求之间的权衡）被埋在文档里，直到 implementation 才爆发。
- agent-review-panel（🟢SHIPPED）的 Completeness Auditor（Phase 8）在 v2 基准测试中发现了 v1 panel（4 个 reviewer）集体遗漏的 6 类代码细节——而这些 reviewer 已经是独立的 critic agents，仍然遗漏了专职发现者才能找到的问题。这说明 adversarial pressure 不能仅靠"加更多 reviewer"，需要专职角色承担"发现遗漏"这个特定任务。
- iReDev（🟡RESEARCH）的 CHV（用户需求多样性）指标：单 agent zero-shot 是 0.13，多 agent 框架是 0.47（+3.6×）。差距来源是 EndUser/Deployer 两个持有不同 objective 的专职角色各自提出了对方不会想到的需求——这正是"adversarial pressure"在认知多样性维度的量化体现。

**失败的根因**：单 agent 没有"以怀疑者身份重读自己产出"的驱动力。假设只有在有人从反方向质疑时才会浮出水面。

---

### F5：架构决策被实现淹没（Architecture Opacity）

单 agent 执行 brief 时，技术栈选择、模块边界划分、集成协议选择，这些架构决策和"实现功能"是同一个动作。架构决策被实现的速度淹没，不会以可讨论的形式出现在 spec 环节。

**本轮新证据（本轮全新识别，前两轮未覆盖）**：
- Architecture Without Architects（🟡RESEARCH）提出"Vibe Architecting"命名：同一任务（chatbot），仅 prompt 措辞不同，三个变体产生了代码量 5.9×、文件数 3× 差距的不同架构。单 agent 把 brief 的 ambiguity 任意解析成架构选择，选择过程完全不可见、不可 review。
- 该论文识别了 6 种 Prompt-Architecture Coupling Pattern，其中 Fundamental Pattern（Function Calling、ReAct）是结构性的：只要 prompt 里出现了 typed tool signature，就会引入 orchestration 层、state machine、error handler 等基础设施——这些架构决策根本不会出现在 spec 文档中，因为 spec 阶段还没有"prompt 里有什么工具"这个信息。
- 论文的核心诊断："Agents make architectural decisions, but no feedback loop ties those decisions to established architectural knowledge."——spec 阶段正是这个反馈环应该建立的地方，但单 agent 绕过了它。

**失败的根因**：架构决策和实现决策在单 agent 流程中不可分离，spec 阶段没有"强制显现架构决策"的机制，后续无法追溯和 review。

---

### F6：长任务漂移与角色混淆（Long-Task Drift）

单 agent 在规划/spec 阶段写完之后，会自然滑入"我来实现一下"的模式——即使没有被要求。单 agent 的角色边界是软约定，不是硬执行。随着任务推进，"我是 spec 作者"的角色意识会衰减。

**本轮新证据**：
- sample-claude-code-agent-team（🟢SHIPPED）把 "Delegation Is Mandatory" 写成强制性段落，措辞比普通约束强得多："You MUST NOT implement non-trivial code yourself, even if it seems faster, even if team-coordination tools are unavailable."——这么强的措辞本身证明：如果没有硬约束，agent 会漂移到实现。
- Single-MAS-Both（🟡RESEARCH）的 Path-Level 缺陷：多轮摘要传递中，正确的中间结论在摘要时被丢弃，下一轮 agent 从头推导并出错。这是"在迭代中漂离正确方向"的量化证据。

**失败的根因**：单 agent 的 objective 是隐式的（"完成用户给的任务"），随着任务演进，objective 本身在漂移，没有外部锚定机制。

---

### F7：无结构化质量 grammar，评审无可操作性（Unactionable Review）

即使单 agent 执行了某种 self-review，产出也往往是自由文本批评（"这里需要更清晰"、"这个功能描述不够完整"），没有 severity 分级、没有具体修改建议，下游无法判断哪些问题是阻断性的，哪些可以接受。

**本轮新证据**：
- pm-skills（🟢SHIPPED）的设计文档明确："This is unclear 不是 finding；Rewrite as X to address Y 才是。"每条 finding 必须包含 concrete fix suggestion，并标 P0/P1/P2/P3 severity——这是产品中解决"评审无可操作性"的具体实现。
- Traceability-Accountability（🟡RESEARCH）的 blame assignment 机制（repair rate / harm rate / error_origin）证明：**没有结构化的 Critic 输出格式，就无法追踪哪个环节引入了问题**。自由文本批评不支持问责追踪，不能作为 escalation 或 gate 的依据。

**失败的根因**：评审没有可机器处理的格式，问题清单无法被确定性地路由（block vs. warn vs. suggest）。

---

## 2. 失败模式 → Multi-Agent 补法 映射表（核心交付）

| 失败模式 | Multi-Agent 补法 | 真增加能力 OR 只加噪声 | 黑盒 CAN/CANNOT | 标注 | 证据来源 |
|---|---|---|---|---|---|
| **F1：Early-Stop** | goal-backward truths 作为 spec 完整性的可检验锚；独立 spec-checker 逐条验证"这条 truth 在 spec 哪里被覆盖" | **真增加能力**：将"任务满足"的 objective 替换为"结果满足"的外部锚，迫使 author 从用户视角反向检验 | CAN（truths 格式 + 文本比对） | 🟢 gsd-core；🟡 AgenticAKM | gsd-core `agents/gsd-planner.md`；AgenticAKM AdrChecker 打回 |
| **F1：Early-Stop** | 四源覆盖审计（GOAL/REQ/RESEARCH/CONTEXT 四类来源，任何 MISSING 项强制上报） | **真增加能力**：引入外部参照系，防止 author 在没有覆盖所有输入的情况下声称"完成" | CAN（文本扫描 + LLM 判断） | 🟢 gsd-core | gsd-core `references/planner-source-audit.md` |
| **F2：Self-Review Impossibility** | 专职 critic agent，独立 context 窗口，工具层 Read-Only（无 Write 权限）；adversarial framing 在 system prompt 明确："you stress-test, not validate" | **真增加能力**：工具层而非意图层保证独立性；物理上无法修改 artifact，强制维持对抗立场 | CAN（frontmatter 工具列表配置） | 🟢 pm-skills；🟢 sample-claude-code-agent-team | pm-skills `agents/pm-critic.md`；AWS sample `review-agent.md` |
| **F2：Self-Review Impossibility** | 文件所有权锁定：reviewer 是 review.md 的唯一合法写入者；orchestrator 明确禁止自我审查（"Self-review is a category error"） | **真增加能力**：架构层强制 objective 分离，不依赖 agent 自律 | CAN（system prompt 声明 + 文件命名约定） | 🟢 sample-claude-code-agent-team | `fullstack-agent.md` Review Gate Authority |
| **F3：Context Overload** | 每个重任务在新的独立 context 子 agent 中执行（fresh ~200K window）；orchestrator 只路由，不执行；artifact 以文件路径引用而非在 context 中内联 | **真增加能力**：把有限注意力集中在正确的事情上，而非在混合 context 中均分 | CAN（Agent spawn，Claude Code 原生） | 🟢 gsd-core；🟢 Claude Code（第二轮） | gsd-core README；CC `runAgent.ts` |
| **F4：No Adversarial Pressure** | 强制对立 Debater 对 + Judge 三角结构（同步并行，n=0；两个 Debater 互不可见各自生成论据；Judge 整合） | **真增加能力**：二分类 RE 任务实测 F1 +0.109（0.726→0.835），p<0.001；比单 reviewer 更可靠地 surface 弱侧论证 | CAN（纯 system prompt + 并行 API 调用） | 🟡 MAD-RE（arXiv:2507.05981） | McNemar p<0.001，N=621 需求 |
| **F4：No Adversarial Pressure** | 不同 objective 专职 sub-reviewer（Safety/Efficiency/Consistency/Feasibility…），每个只从自己维度批判，批判必须给理由 | **真增加能力**：vs 同质辩论（只加噪声）的核心区别——认知多样性来自不同 objective，不是同质 LLM 的随机采样变体 | CAN（各 sub-reviewer 独立 system prompt） | 🟡 QUARE（arXiv:2603.11890）；🟡 iReDev | QUARE 合规覆盖率 47.8%→98.2%；iReDev CHV +3.6× |
| **F4：No Adversarial Pressure** | 专职 Completeness Auditor 角色（独立于 debate，只找遗漏，不评质量） | **真增加能力**："Debate is excellent for evaluating significance, bad for finding things"（agent-review-panel HOW_WE_BUILT_THIS Lesson 1） | CAN（独立 context，Read-only tools） | 🟢 agent-review-panel | Phase 8 在 v2 基准测试中发现 v1 panel 遗漏的 6 类细节 |
| **F5：Architecture Opacity** | spec-author 必填输出"架构决策影响声明"（ADR-lite）：选了什么、引入的基础设施开销、Fundamental/Contingent 分类、攻击面影响 | **真增加能力**：把隐式架构决策显现为可 review 的 artifact，这是 spec-reviewer 存在的前提——没有显现，reviewer 看不到决策 | CAN（output 格式约束） | 🟡 Architecture Without Architects（arXiv:2604.04990） | Vibe Architecting 案例：同任务 5.9× 代码量差距 |
| **F5：Architecture Opacity** | spec 模板增加"技术选型段"，要求 author 列出每个非平凡技术选择的替代方案和选择理由 | **真增加能力**：使架构权衡可见，reviewer 和用户才能在 spec 阶段介入 | CAN（模板约束） | 🟢 sample-claude-code-agent-team（`spec-workflow/SKILL.md`）；🟡 gsd-core（CONTEXT.md locked decisions） | AWS sample `.claude/specs/<slug>/decisions.md` |
| **F6：Long-Task Drift** | 强制角色锁定（orchestrator ≠ implementer；"Delegation Is Mandatory"措辞 + 工具不可用时 STOP 而非降级）；Build Phase Entry Gate（spec 批准后的第一个 tool call 必须是 TeamCreate，不是代码编写） | **真增加能力**：硬约束，不依赖 agent 自律；降级路径被封死，消除"我来快速实现一下"的诱惑 | CAN（system prompt 硬约束 + hook 检查） | 🟢 sample-claude-code-agent-team | `fullstack-agent.md` L1-50 |
| **F7：Unactionable Review** | P0/P1/P2/P3 severity grammar；每条 finding 必须有 concrete fix suggestion；orchestrator 基于 severity 做确定性路由（P0→block，P3→建议） | **真增加能力**：把自由文本批评变成机器可处理的路由信号，reviewer 输出才能驱动门禁逻辑 | CAN（output schema 约束） | 🟢 pm-skills；🟢 agent-review-panel | pm-skills `docs/internal/release-plans/v2.16.0/spec_pm-critic.md` L31-32 |
| **F7：Unactionable Review** | 结构化交接（每跳携带原始 brief 作为不可移除锚点）；Reviewer 固定维度评分卡（而非自由评判）；每次运行写 handoff artifact（brief + author 假设） | **真增加能力**：结构化交接使 Critic 准确率最高 +36.22 pts（vs 无结构化交接）；固定维度控制 Critic 损害率 | CAN（文本格式约束 + 文件写入） | 🟡 Traceability-Accountability（arXiv:2510.07614） | Table III：BBB 配置 61.42%→97.64% |

### 明确区分：真正增加能力的分解 vs 只加成本/噪声的（同质 debate）

| 模式 | 判定 | 理由 |
|---|---|---|
| 4 个相同 persona LLM 自由辩论 | **只加噪声**：Martingale Curse | 同底层模型，共享 bias，辩论轮次越多越收敛（而非越发散），问题被修辞压倒而非证据压倒 |
| 同质 reviewer × N（只是多份独立审查） | **轻微增加能力，ROI 低** | 两次独立 run 仅 ~30% finding overlap（agent-review-panel 实测）；每次 run 同质 bias 仍在 |
| 强制对立立场 Debater 对（不同 objective，同步，n=0）| **真增加能力** | 迫使 LLM 从弱侧论证（"argue this IS non-functional"），系统性覆盖被单一立场忽略的问题 |
| 不同 objective 专职角色（Safety / Efficiency / Feasibility…）| **真增加能力** | 认知多样性来自 objective 差异，不是同质 LLM 的随机变体；QUARE 合规覆盖率 +105% |
| Generator + 专职 Critic（独立 context，adversarial framing，Read-only）| **真增加能力** | AgenticAKM Overall +15-18%，pm-skills 6 断言 33%→100%；关键是 objective 分离而非角色存在 |
| Debate 后多数投票（无 Judge）| **降低能力** | 最后发言者影响力主导；修辞压倒证据；agent-review-panel 专门设计 Blind Final 对抗此问题 |
| 多轮 debate（n≥2 轮）| **成本翻倍，收益极小**：n=0→n=1 仅 +0.006 F1 | MAD-RE 论文实测，n=1 已是收益/成本 Pareto 边界 |
| orchestrator 自己也做 author | **角色混淆，降低质量** | pm-skills 专门设计 leaf-inlining 防止 orchestrator 兼任 author；AWS sample 明确禁止 |

---

## 3. 正面处理张力：朴素 Debate 帮倒忙 vs 单 Agent 不够

### 3.1 为什么朴素 Debate 帮倒忙（机制性理解）

朴素 multi-agent debate 的三个失败路径：

**路径 1：Martingale Curse**——同底层模型的多个实例在迭代讨论中会收敛到单一立场，而非发散出更多视角。这是数学上必然的：若每轮更新是基于上一轮的共识，且所有 agent 共享 bias，最终状态是初始 bias 的放大，不是纠正。

**路径 2：修辞压倒证据**——辩论轮次中，表达流畅、立场强势的 agent 会让其他 agent 改变立场，即使没有提供新的事实依据。agent-review-panel 对此有精确的量化检测：若 >50% 的立场转变没有新证据支撑，注入 sycophancy alert。

**路径 3：problem drift**——每轮辩论后的摘要（为了节省 context）会丢失中间结论。Traceability-Accountability 论文的 Path-Level 缺陷：正确答案 55 在摘要后消失，下一轮从头推导出错误答案 28。

### 3.2 为什么单 Agent 也不够（无法用模型进步规避）

Single-MAS-Both 论文给出了边界条件：在**可验证任务**（代码生成/数学）上，随模型能力提升，MAS 优势在收窄——这是真实的。但 spec/design 是**开放性、主观性任务**，没有客观正确答案，该论文明确表示不覆盖此类任务。

在 spec/design 场景，单 agent 的根本限制不是"能力不足"，而是**结构性限制**：
- 同一 agent 不可能同时持有"生成者 objective"和"审查者 objective"（F2）
- 同一 context 窗口不可能同时有足够深度的产品、技术、调研知识（F3）
- 同一推理链不可能同时从多个 stakeholder 角度发现假设（F4）

这些是**无法通过单纯提升模型能力解决的结构性问题**。Gemini 2.5 Pro 的 Planner 错误率依然是 7.35%（Traceability-Accountability 数据），即使是最好的模型，自我批判也比独立 Critic 的修复率低 5-7×。

### 3.3 "哪种多 agent 分解黑盒可行且真有效"的结论

**有效且黑盒可行的分解条件**（同时满足以下三条）：
1. **objective 真正不同**：reviewer 的 objective 是"找问题"，author 的 objective 是"写完整 spec"——这两个 objective 必然冲突，冲突是有价值的
2. **context 真正隔离**：reviewer 不持有 author 的内部推理，只读 artifact 文件（+ 独立的参考锚点）
3. **工具层强制角色边界**：reviewer 无 Write 权限，无法把"建议修改"变成"直接修改"，防止角色混淆

**不有效的分解模式**：
- 只是多 agent 数量，objective 相同（同质扩增）
- 共享 context（reviewer 可见 author 的推理过程）
- 角色边界仅靠 system prompt 软约定，无工具层强制

---

## 4. 针对 feat-397 的推荐 Multi-Agent 架构

在第二轮报告已有的四阶段顺序流水线（spec-author → spec-reviewer → design-author → design-reviewer）和三层 escalation 结构之上，本轮的增量贡献：

### 4.1 补强点 1：spec-author 前增 Elicitation 阶段（对应 F1/F4）

**问题**：brief 输入 spec-author 后直接生成，跳过了 stakeholder 角度的结构化澄清。

**补法**：spec-author 在生成 spec 前，强制执行两轮 persona elicitation：
- 轮 A：以 EndUser persona 反问业务场景、痛点、边界条件（不问技术约束）
- 轮 B：以 Deployer persona 反问技术约束、安全要求、运维限制（不问业务意图）

产出：`user-context.md` + `deploy-context.md`，写入文件，作为 spec.md 的独立前置输入。

这不需要引入独立 agent，只需 spec-author 在生成前做两轮结构化 persona 切换。成本：额外 2 次 LLM 调用。收益：iReDev 的 CHV +3.6× 证明此机制有效（EndUser/Deployer 两视角 surface 的需求多样性显著提升）。

**必填输出格式（新增到 spec.md）**：

```yaml
must_haves:
  truths:       # 用户视角可验证的结果（不是任务，是成果）
    - "[结果描述，用 GIVEN/WHEN 可测试]"
  constraints:
    - "[来自 deploy-context.md 的硬约束]"
  open_questions:  # author 的未确认假设（F5 的对应）
    - "[假设 X：如果错误，会影响 Y]"
```

gsd-core 的 `must_haves.truths` 格式可直接参考。

### 4.2 补强点 2：spec-reviewer 改为固定维度评分卡 + 独立 context（对应 F2/F7）

**问题**：第二轮推荐的 spec-reviewer 是单 agent 自由审查，受 Critic 高方差风险（Traceability-Accountability：损害率 1.90%）影响。

**补法**：reviewer 的 prompt 改为固定维度评分卡（每条 PASS/FAIL + 1-2 句证据），而非自由评判：

```markdown
# spec-verdict.md 必填维度

1. Brief 覆盖率：spec 是否覆盖 brief 中所有明确需求？
2. Truths 完整性：每条 must_haves.truth 是否有对应的需求或验收条件覆盖？
3. 边界条件：open_questions 中的假设是否全部显式声明？（不要求解决，要求显式化）
4. 内部一致性：spec 内部是否存在自相矛盾的表述？
5. 可验证性：每条功能需求是否有可测试的 acceptance criterion？
6. 规模适配：spec 复杂度是否与 brief 规模匹配（无明显过度设计）？
7. 架构决策可见性：技术选型（如有）是否有 ADR-lite 说明替代方案？
```

**reviewer 的输入必须包含原始 brief**（不只是 spec.md），作为不可移除锚点（Traceability-Accountability 的结构化交接机制：每跳保留原始输入）。

**冲突三分类路由**（QUARE 机制搬入）：reviewer 如遇到需求冲突，必须分类：
- `logical_incompatibility`（逻辑不相容）→ 强制升级人裁决
- `resource_bound`（资源冲突）→ 记录为 WARNING，注入 spec 冲突段
- `redundancy`（冗余）→ 自动去重建议

### 4.3 补强点 3：Pre-Gate Artifact 完整性检查（对应 F7）

**问题**：reviewer subagent 可能静默崩溃留下 stub 文件，orchestrator 无法仅靠文件存在来判断完整性。

**补法**（agent-review-panel Phase 13.5 + AWS sample sentinel 机制）：

在门禁 1 触发前，orchestrator 必须验证：
1. `spec-verdict.md` 文件存在
2. 文件大小 ≥ 500 bytes
3. 必填维度 headers 全部存在（正则检查）

失败处理：re-dispatch 一次 → 若仍失败，标记 `[COMPRESSED]` 并带显式警告通知用户，不自动 PASS。

### 4.4 补强点 4：Adversarial Framing 从 Prompt 层下沉到工具层（对应 F2）

**问题**：spec-reviewer 的独立性仅靠 system prompt 软约定（"请批判性地审查"）。

**补法**（pm-skills 机制）：
- spec-reviewer 的工具列表：`Read, Grep, Glob`，无 `Write`
- spec-reviewer 的 memory：`none`（每次调用独立 context，不被之前会话的"印象"污染）
- spec-reviewer 的 description 字段：`"Use proactively after spec artifact is produced"` + `"You stress-test, not validate"`

这把独立性从"意图层"（prompt 说"你要批判"）下沉到"工具层"（物理上无法修改 artifact）。

### 4.5 补强点 5：Sycophancy Alert 机制（对应 F4）

**场景**：spec-author 收到 reviewer 批评后，解释了自己的设计意图。reviewer 在 2 轮后改变了立场。

**问题**：reviewer 的立场改变可能是"被 author 流畅解释说服"（sycophancy），而非"author 提供了新信息"。

**补法**（agent-review-panel Phase 5/6 机制）：
- spec-author 回应批评后，reviewer 在重新评估前，必须先独立对自己的每条 objection 评 confidence（H/M/L），再看 author 的回应
- orchestrator 检查：若 reviewer 在 author 回应后改变了立场，是否有显式的"新证据/新信息是什么"说明
- 若无新证据的立场转变 > 50%，向 reviewer 注入 sycophancy alert

### 4.6 先做什么、什么先别做

**先做（最高 ROI，最小改造）**：
1. **spec-reviewer 独立 context + Read-Only 工具** — 一次性配置，零成本，解决 F2 根因
2. **spec-verdict.md 固定维度评分卡** — 模板改写，解决 F7 根因
3. **spec-handoff.md（brief 锚点 + author 假设声明）** — 新增一个 artifact，解决 F4/F5 可见性
4. **Pre-Gate Artifact 完整性检查（bytes + headers）** — 10 行 Python，防止静默降质

**次优先（依赖前者完成）**：
5. **Elicitation 两轮 persona（user-context.md + deploy-context.md）** — spec-author system prompt 改写
6. **must_haves.truths 必填段落** — spec 模板改写 + 门禁 1 确定性检查扩展
7. **冲突三分类路由（QUARE schema）** — spec-verdict.md schema 扩展

**先别做（等 ROI 更高的先稳定）**：
- 强制对立 Debater 对（MAD 三角结构）— 成本 3×，在简单 brief 上收益有限；等 Cascade 机制确立后再加
- Sycophancy Alert 精确检测 — 需要多轮迭代数据才能校准阈值
- 多 sub-reviewer（Safety/Efficiency/Feasibility 专职角色）— 架构正确，但成本高；先用固定维度评分卡代替

---

## 5. 这相比现有单-agent SDD 多补了什么能力

（一一对应第 1 节失败模式目录）

| 失败模式 | 现有单-agent SDD 的状况 | 本轮推荐架构多补的能力 |
|---|---|---|
| **F1：Early-Stop** | spec-author 产出"看起来完整"的 spec 即停止；无外部检验 truths 是否覆盖 | `must_haves.truths` 作为可检验锚；elicitation 阶段 surface 隐性需求；四源覆盖审计检测遗漏 |
| **F2：Self-Review Impossibility** | spec-author 产出后无独立 reviewer；或单 agent 自我反思（perverse incentive） | spec-reviewer 独立 context + Read-Only 工具 + adversarial framing；文件所有权锁定 |
| **F3：Context Overload** | 单一 context 窗口兼容 brief 理解 + spec 生成 + 架构调研 | 每个 agent 在独立 context 中执行；elicitation/author/reviewer 各自有自己的 context 专注于自己的任务 |
| **F4：No Adversarial Pressure** | 无对抗机制；假设在 spec 中被隐式接受 | Completeness Auditor 找遗漏；reviewer 固定维度强制从多角度检查；open_questions 必填段落强制假设显式化；sycophancy alert 防立场被 author 流畅解释说服 |
| **F5：Architecture Opacity** | 架构决策被实现淹没，spec 中不可见 | spec 模板必填"技术选型段"+ ADR-lite；spec-reviewer 检查"架构决策可见性"维度；locked decisions 追踪 |
| **F6：Long-Task Drift** | spec-author 可能漂移到"开始实现"模式 | spec-author 只有 Read 权限（无法写代码文件）；Build Phase Entry Gate；orchestrator 角色锁定 |
| **F7：Unactionable Review** | 即使有 reviewer，输出是自由文本批评，无法驱动门禁逻辑 | 固定维度评分卡（PASS/FAIL + 证据）；冲突三分类路由；Pre-Gate artifact 完整性检查；结构化 handoff（brief 锚点） |

**量化预期收益**（来自同场景源的实证，非本项目实测）：
- Generator-Critic 结构 Overall 质量提升：+15-18%（AgenticAKM，29 仓库）
- 结构化交接 vs 无结构化交接：+15 到 +36 pts（Traceability-Accountability，可验证任务）
- 多视角 reviewer vs 单 agent：CHV +3.6×（iReDev，需求多样性指标）
- 专职 critic 引入 vs 无 critic：safety 91% vs 87%（INDICT，第一轮数据）

---

## 6. Reality Check

### 6.1 哪些是 Hype

**"越多 agent 越好"**：Single-MAS-Both 论文证明 ~80% 的任务 SAS/MAS 结果相同。对于简单明确的 brief，spec-author 单 agent 很可能直接通过门禁，触发 reviewer 只是增加延迟和成本。应用 Cascade 思路：门禁失败或 brief 复杂度超阈值时才触发 reviewer。

**"多轮 debate 越深入越好"**：MAD-RE 论文明确：n=0→n=1 仅 +0.006 F1，成本翻倍。Debate 轮次 >1 的成本/收益曲线在 spec/design 这类 open-ended 任务上更可能劣化，而非改善。

**"消融实验 4 角色"的直接外推**：MetaGPT 的 4 角色最优是在代码生成任务（有客观正确答案）上的消融。spec/design 任务无此数据，4 角色的"最优性"在本场景未经验证。

**"Completeness Auditor 能发现所有遗漏"**：agent-review-panel 的实测显示，两次独立 run 仅 ~30% finding overlap——这意味着即使有专职 Completeness Auditor，单次 run 也只能发现约 60-70% 的可发现问题。不要对 reviewer 产出有 100% 覆盖的期望。

### 6.2 最大工程风险

**风险 1：Critic 损害率**（Traceability-Accountability 数据，非 hype）

Claude 担任 Critic 时损害率 1.90%——它会把正确的 spec 判为 FAIL。在没有 ground truth 的 spec/design 场景，这意味着一定比例的合格 spec 会被错误打回，产生不必要的迭代和用户摩擦。

**缓解**：固定维度评分卡（控制 Critic 的裁量范围）+ 门禁 1 之后的人工确认点（用户确认后才进 design，给用户机会覆盖错误否决）。

**风险 2：静默降质（Silent Phase Compression）**

subagent 可能静默崩溃留下 stub 文件，外观上文件存在，实际是空的。agent-review-panel v3.1.0 引入 bytes check + headers check 正是为了解决这个问题。Pre-Gate artifact 完整性检查是必要的工程保障，不是可选项。

**风险 3：人工确认点的带宽消耗**

iReDev 的 HITL 设计明确："balance automation speed with alignment without exhausting human bandwidth"。如果每个 spec 都需要 3 个人工确认点，用户会疲劳。建议只保留两个必要的人工确认点：门禁 1（spec 通过后用户确认进 design）和 门禁 2（design 通过后用户确认进实现）。中间的 reviewer 反馈循环应尽量自动化，只有 CRITICAL 或逻辑不相容冲突才升级给用户。

**风险 4：有界 Loop 的 Fallback 缺失**

AgenticAKM 的 best-effort 语义（3 轮后静默继续）是设计缺陷，已被明确识别。feat-397 必须在 max_attempts 耗尽后触发 IM escalation，不允许 orchestrator 静默把已知错误的 spec 传给 design-author。这是最容易实现也最容易被忽略的工程细节。

**风险 5：Elicitation 阶段的用户体验**

spec-author 在生成 spec 前发起 2 轮 persona elicitation（EndUser + Deployer 问题），需要用户回答。若问题质量低或问题数量过多，用户体验变差（变成填表而非对话）。建议：每轮不超过 3 个问题，问题来自 gsd-core 的 10 个问题域的子集，只问对当前 brief 真正有差异化价值的问题。

---

## 附录：本轮新增证据索引

| 源 | 标注 | 本轮最高价值贡献 |
|---|---|---|
| pm-skills（product-on-purpose）| 🟢 SHIPPED v2.24.0 | adversarial framing 从 prompt 层下沉到工具层；referential discipline；EMPTY ≠ PASS 语义 |
| agent-review-panel（wan-huiyan）| 🟢 SHIPPED v3.3.0 | Blind Final 防同化；Private Reflection；Agreement Intensity 注入；Sycophancy Detection；Phase 13.5/14.5 防静默降质 |
| AgenticAKM 代码库（sa4s-serc）| 🟡 RESEARCH + 可运行代码 | Checker 独立重构 context + 外部真值接入；有界 loop fallback 缺陷（反面教材）；Overall +15-18%（29 仓库） |
| AgenticAKM 论文（arXiv:2602.04445）| 🟡 RESEARCH | 量化质量增量数据（同上） |
| sample-claude-code-agent-team（aws-samples）| 🟢 SHIPPED MIT-0 | 文件所有权锁定；verification sentinel；Build Phase Entry Gate；Delegation Is Mandatory |
| gsd-core（open-gsd）| 🟢 SHIPPED npm 包 | goal-backward truths；四源覆盖审计；scope reduction prohibition；locked decisions（D-NN） |
| Multi-Agent Debate for RE（arXiv:2507.05981）| 🟡 RESEARCH | 强制对立 stance + 同步并行 + Judge 三角结构；F1 +0.109 p<0.001；多轮 debate ROI 为负 |
| iReDev（arXiv:2507.13081）| 🟡 RESEARCH | 异质 stakeholder 角色（EndUser/Deployer）；CHV +3.6×；三个固定 HITL 检查点 |
| Architecture Without Architects（arXiv:2604.04990）| 🟡 RESEARCH | Vibe Architecting 命名；6 种 Prompt-Architecture Coupling Pattern；架构决策必须在 spec 阶段显现 |
| Traceability and Accountability（arXiv:2510.07614）| 🟡 RESEARCH | Critic 损害率量化（Claude 1.90%）；结构化交接 +36.22 pts；Planner 稳定 vs Critic 高方差 |
| Single-MAS-Both（arXiv:2505.18286）| 🟡 RESEARCH | Cascade 思路（先 SAS 后 MAS）；Node/Edge/Path 三层 MAS 缺陷；~80% Both-Pass 边界条件 |
| QUARE（arXiv:2603.11890）| 🟡 RESEARCH | 不同 objective 专职 sub-reviewer；冲突三分类路由；合规覆盖率 47.8%→98.2%；"冲突记录而非重写"原则 |

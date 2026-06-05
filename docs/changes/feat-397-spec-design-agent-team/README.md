# feat-397 spec/design 对齐 agent team —— 目录索引

> 本 unit 的唯一入口。说清每个文件是什么、干嘛用、什么状态。新来的人/未来的自己从这里开始。

## 这个 unit 在做什么

在现有 change-* SDD 流水线(写码环节已全自动)的**前两环——spec 对齐、design 对齐**上做自动化:维护者只给轻 brief + 在价值岔路异步裁决(human-on-the-loop),由一个 agent team 完成 spec/design,产出交回已自动化的实施链。

## 当前进度(2026-06-04)

- **阶段**:探索(阶段1),**门禁 1 未过**(spec 未定稿)。
- **已确认澄清**:范围=只做前两环 / 程度=human-on-the-loop / D1 brief 不限格式 / D2 升级走 IM(可落文件)/ D6 单人品味库(复用历史原话)/ D7 陌生领域系统自查 / D8 视觉自动化先不做。
- **待定**:**D3**(价值岔路红线)、**D4**(打扰频率上限)、**D5**(评测先行+自评分)——研究已足够支撑落定,下一步回 `change-spec-author` 收口。
- **研究结论(四线已齐)**:全自动不可达(76% 澄清是判断不可剥离);multi-agent 真增能力需"objective 不同+context 隔离+工具层强制边界";同场景最佳参考是 Clowder AI(已实战跑通 human-on-the-loop 版)。

---

## 文件清单

### A. spec 主线(收口门禁 1 看这三个)

| 文件 | 是什么 | 状态 |
|---|---|---|
| `spec.md` | **正式首文档**。原始需求 + 澄清记录(已确认项)。结论段待 D3/D4/D5 定后回填 | 进行中(门禁1未过) |
| `spec.DRAFT.md` | 基于已确认项**预拟的完整 spec 草稿**(用户场景+Requirement/Scenario+范围)。D3/D4/D5 定后提升为正式 spec | 草稿待确认 |
| `alignment-questions.md` | **待对齐清单 D1–D8**,每点带推荐答案+理由。明天/下一步逐点过 | D1/D2/D6/D7/D8 已确认;D3/D4/D5 待定 |

### B. 调研委托与自查基线(briefs)

| 文件 | 是什么 |
|---|---|
| `research-notes.md` | 主 agent 第一轮自查基线(MetaGPT/ChatDev/spec-kit/Kiro/BMAD/MARE),供与外部报告对照 |
| `deep-research-brief.md` | 给外部 deep research agent 的**第一轮委托**(P0:品味编译/escalation/drift 等 10 方向) |
| `deep-research-brief-round2.md` | **第二轮委托**:重心切到 agent 架构/harness/多agent 工程实践 + 黑盒过滤 + 强制标 SHIPPED/RESEARCH |

### C. 外部 deep research —— 第一轮(`Agent_深度研究简报/`)

| 路径 | 是什么 |
|---|---|
| `Agent_深度研究简报/spec_design_research.agent.final.md` | **第一轮总报告**(12 维度,~155KB)。结论:编译品味+顺序流水线+human-on-the-loop |
| `…/spec_design_research.agent.outline.md` | 总报告大纲 |
| `…/spec_design_research_sec00–08.md` | 总报告分章原文 |
| `…/research/spec_design_agent_dim01–12_*.md` | **12 个分维度深度报告**(品味编译/escalation/drift/拓扑/角色/澄清/前沿产品/评测/UI架构/失败案例/验证成本/个性化) |
| `…/research/spec_design_agent_cross_verification.md` | **交叉验证**:置信度分级 + 冲突区(判可信度看这个) |
| `…/research/spec_design_agent_insight.md` | 跨维度 7 条洞察 |
| `…/ch3_multi_layer_defense.png` | 第一轮配图 |

> 评判:核心引用(MAST/AceMAD)亲自核实为真;偶有数字转录偏(MAST 占比);个性化方法(PReF/Drift 等)多为 research-grade、且部分需 logit/训练→**黑盒不可用**(见 round2 纠正)。

### D. 外部 deep research —— 第二轮(`Agent_深度研究简报/round2/`)

| 路径 | 是什么 |
|---|---|
| `Agent_深度研究简报/deep-research-round2-report.md` | **第二轮总报告**:工程实践视角,标 SHIPPED/RESEARCH;读 claude-code 等源码取一手证据;含第一轮黑盒再过滤表 |
| `…/round2/r2d1–r2d9-*.md` | 第二轮 9 个工程维度分报告 |

### E. 外部 deep research —— 第三轮(`Agent_深度研究简报/round3/`)

| 路径 | 是什么 |
|---|---|
| `Agent_深度研究简报/round3/deep-research-round3-report.md` | **第三轮总报告(核心)**:围绕"单 agent 做不好 spec/design,如何用 multi-agent 补"。7 个单 agent 失败模式 → multi-agent 补法映射表 |
| `…/round3/01–12-*.md` | 12 个同场景源的分源深挖(pm-skills/agent-review-panel/AgenticAKM/gsd/MAD-RE/iReDev/Architecture-Without-Architects/Traceability/Single-MAS-Both/QUARE 等) |

> 评判:承重论文(MAD-RE 2507.05981 / iReDev 2507.13081 / Traceability 2510.07614 / QUARE)与 repo(pm-skills/agent-review-panel/gsd)亲自核实**全部真实**;具体百分比未逐一回算,引用标"据论文"。

### F. 你的真实数据分析

| 文件 | 是什么 |
|---|---|
| `clarification-removability-analysis.md` | **44 个 unit、222 条澄清原话**的"可剥离 vs 必须问你"分析。结论:可剥离 24%(主要靠仓库 grep),不可剥离 76%(6 类红线:范围优先级/产品方向/UX/风险/审美/命名)。直接喂 D3 |

### G. 同场景最佳参考:Clowder AI

| 文件 | 是什么 | 状态 |
|---|---|---|
| `clowder-ai-analysis.md` | **深度 teardown(唯一)**。逐文件读 clowder-ai 一手源码(route-serial/route-parallel/MultiMentionOrchestrator/a2a-mentions/routing-decision/intent-card-store/risk-detection/SOP/cat 花名册)。**带图**:总架构、路由决策树、三种协作模式时序图(serial 链/parallel 独立/multi_mention 面板状态机)、A2A 接力 5 guard、context 装配、spec/design 阶段几只猫怎么排兵、Need Audit pipeline、SOP 状态机。主线=LLM 软评分/生成 + 确定性代码做所有闸门(computeBucket/detectRisks/predicate.type)。末尾谈对 feat-397 的含义。已删旧 v1/v2 | 现行 |

---

## 推荐阅读顺序

1. 想知道**结论怎么落到 spec** → `alignment-questions.md` + `spec.DRAFT.md`
2. 想要**最务实的可搬方案** → `clowder-ai-analysis-v2.md`(第4/6节)
3. 想懂**为什么要 multi-agent** → `round3/deep-research-round3-report.md`
4. 想要**红线的数据依据** → `clarification-removability-analysis.md`
5. 想要**全景文献** → 第一轮 final + 第二轮 report

# Clowder AI 深度拆解(第一手源码 teardown)

> 目标:让读者**真正看懂 Clowder 怎么设计的**——尤其多 agent 怎么协作、spec/design 阶段有几个 agent。
> 方法:逐文件读 `~/Repos/opensource-hub/clowder-ai` 源码(路由引擎 route-serial/route-parallel、
> MultiMentionOrchestrator、a2a-mentions、routing-decision、intent-card-store、risk-detection、
> SOP 定义、三个 spec/design skill、cat 花名册)。所有行号/函数名均亲读核实。日期 2026-06-04。
> 仓库:github.com/zts212653/clowder-ai(MIT,提炼自生产级 Cat Cafe,实战数月)。

---

## 0. 一句话先抓住本质

Clowder = **一个确定性的"平台层"harness,编排一小群身份持久、跨模型的 AI agent(猫),用一套
确定性代码做所有路由/闸门/分流,把猫的"软力量"(生成+判断)关进硬轨里。** 多 agent 协作不是
"群聊涌现智能",而是三种**结构化协作模式** + 一条 **A2A 接力链**,全部带确定性 guard。

下面从"有几个 agent"讲到"它们怎么协作",再到"spec/design 具体怎么排兵"。

---

## 1. Agent 模型:有几个 agent、它们是什么

### 1.1 agent = "猫",身份持久 + 跨模型

Clowder 的 agent 叫"猫"。花名册在 `cat-template.json`,按**品种(breed)**组织,每个品种绑一个**模型家族**:

| 品种 | 显示名 | 模型家族 | 典型 roles(配置里的 `roles` 字段) |
|---|---|---|---|
| ragdoll | 布偶猫 | Claude(opus-default/45/47…) | `["architect","peer-reviewer"]` |
| maine-coon | 缅因猫 | GPT/Codex(codex-gpt52…) | `["peer-reviewer","security"]` |
| siamese | 暹罗猫 | Gemini | `["designer"]` |
| golden-chinchilla | 金渐层 | opencode(任意 provider) | `["coding","multi-agent"]` |
| bengal | 孟加拉猫 | Antigravity | `["creative","visual","browser-agent"]` |
| moonshot/梵花 | — | Kimi | `["research","writer"]` |
| dragon-li | 狸花猫 | — | `["coding"]` |

**关键设计点(回答"有几个 agent"):**
- agent 数量 = 用户在 Hub 里配置启用的猫,**通常 3-4 只**(README 的家庭:布偶/缅因/暹罗/金渐层)。
- **没有"spec-author agent""design-reviewer agent"这种专职进程。** agent 是**身份持久的猫**(布偶永远是布偶,跨 session、跨上下文压缩保持人格/记忆),**角色是按任务临时分配的帽子**。
- `roles`(architect/peer-reviewer/designer/security/coding…)是猫的**持久能力标签**,用于路由匹配(如 reviewer-matcher 选 `peer-reviewer` 角色的猫);任务级角色(Analyst/Critic/扇入者)由 skill 在当下分配。
- **认知多样性来自"跨模型"**:布偶=Claude、缅因=GPT、暹罗=Gemini 是**不同底座模型**,不是同一模型换 prompt。这是 Clowder 多 agent 真正"互补"的物理来源。

### 1.2 三层职责(谁干什么)

```
┌──────────────────────────────────────────────┐
│  你 = CVO(首席愿景官)                         │  表达愿景 / 关键决策 / 反馈塑造文化
└───────────────┬──────────────────────────────┘
                │
┌───────────────▼──────────────────────────────┐
│  平台层(Clowder)= 确定性 harness            │  身份注入 · A2A路由 · SOP纪律 · 记忆 · 审计
│  ▸ 不做推理,只做编排和闸门                    │
└──┬──────────┬───────────┬───────────┬─────────┘
   │          │           │           │
┌──▼──┐   ┌──▼──┐    ┌───▼──┐   ┌────▼─────┐
│布偶 │   │缅因 │    │暹罗  │   │金渐层    │   ← 身份持久的猫(跨模型)
│Claude│  │GPT  │    │Gemini│   │opencode  │
└─────┘   └─────┘    └──────┘   └──────────┘
   = Agent CLI 层(工具/文件/命令) + 模型层(推理)
```

口号:"模型给能力上限,平台给行为下限。" 平台**不替代推理**。

---

## 2. 一条消息如何变成多 agent 协作(路由决策)

入口在 `AgentRouter.ts`。一条用户消息进来,走这棵**确定性决策树**:

```
用户消息 (in thread)
  │
  ├─ parseAllMentions(): 解析 @  ──────────────────────────────┐
  │   · 个体 @布偶 / 群组 @all,@全体,@thread / 口语 "at 布偶"   │
  │   · longest-match-first + token 边界;未匹配 @handle 报 warning
  │
  ├─ resolveTargets(): 选目标猫(优先级)
  │   显式@  >  上一条 user-msg 的@  >  健康的上一回复者  >  thread.preferredCats  >  默认猫(布偶)
  │   叠加 inferRoutingScope() 关键词分流: "review/merge/PR"→review, "架构/设计/方案"→architecture
  │           → thread.routingPolicy 把 scope 映射到 prefer/avoid 猫
  │
  ├─ parseIntent(message, targetCount)  →  intent ∈ {ideate, execute, …}
  │
  └─ 选策略(route()/routeExecution() line 959/1059,确定性):
        ┌─────────────────────────────────────────────┐
        │ intent==='ideate' && targetCats>1            │ → routeParallel  (并行·独立思考)
        │ 否则(execute / 单猫)                         │ → routeSerial    (串行·链式协作)
        └─────────────────────────────────────────────┘
```

**注意:策略不是 LLM 决定的,是"意图 + 猫数"两个值算出来的。** ideate+多猫=发散并行;其余=串行。

---

## 3. 三种协作模式(核心:多 agent 怎么协作)

### 模式 A:Serial 串行链(`route-serial.ts`,2376 行,主引擎)

**机制:一个动态增长的 worklist,猫一个接一个跑;每只猫的回复可以把下一只猫"接力"进 worklist。**

```
worklist = [布偶, 缅因]            // 初始 = 用户 @ 的猫
previousResponses = []
index = 0
┌─ while (index < worklist.length) ───────────────────────────────────┐
│                                                                      │
│  catId = worklist[index]                                             │
│                                                                      │
│  ① 装配 context(buildInvocationContext):                            │
│     · 身份 L0(identity/家规,抗压缩)+ pack                          │
│     · teammates = worklist 里其他猫                                  │
│     · chainIndex/chainTotal(我是链上第几只/共几只)                  │
│     · directMessageFrom(谁 @ 把球传给我)                            │
│     · sopStageHint(告示牌:当前 SOP 阶段)                           │
│     · alwaysOnDocs(constitution,F163)+ memory recall + signals      │
│     · pingPongWarning(若同一对来回 streak≥2)                        │
│  ② 拼 prompt:debug 模式才把 previousResponses 作 [catId responded:…] │
│     拼进去;play 模式猫之间看不到彼此 thinking,只给结构化 briefing   │
│  ③ invokeSingleCat() → 流式产出这只猫的回复                          │
│  ④ 回复结束:parseA2AMentions(回复文本) → 找行首 @mention            │
│  ⑤ A2A 接力:对每个被 @ 的猫,resolveRoutingDecisions() 过 guard 链  │
│       通过 → worklist.push(下一只猫); a2aCount++; index 之后会跑到它 │
│  ⑥ index++                                                          │
└──────────────────────────────────────────────────────────────────┘
```

**时序举例**(布偶写完代码 @缅因 review,缅因发现问题 @布偶 修):
```
用户: @布偶 实现登录                  worklist=[布偶]
  布偶: 实现完成。\n@缅因 帮我 review   → A2A: push 缅因   worklist=[布偶,缅因]
  缅因: 发现 P1。\n@布偶 这里要改       → A2A: push 布偶   worklist=[布偶,缅因,布偶]
  布偶: 改好了。                        → 无 @,链结束
```
→ **这就是"跨模型互审"的实际跑法:不是预先编排好的固定流水线,是回复里的 @ 动态长出来的链。**

**A2A 接力的 5 道确定性 guard**(`routing-decision.ts` 纯函数 `resolveRoutingDecisions`):
| guard | 条件 | 动作 |
|---|---|---|
| aborted | 本猫信号已取消 | skip |
| **depth** | a2aCount ≥ maxDepth(默认 **15**) | skip(防无限链) |
| dedup | 该猫已在队列活跃处理 / 已在 pending 尾部 | skip / mark_replyto |
| **ping-pong** | 同一对猫来回 streak ≥ **4** | **block_pingpong**(yield 终止信号) |
| **fairness** | 队列里有用户消息待处理 | defer_queue(先让用户) |
每条消息最多 @ **2** 只猫(`MAX_A2A_MENTION_TARGETS`);先剥围栏代码块再解析;过滤自调用。

### 模式 B:Parallel 并行独立(`route-parallel.ts`,1399 行)

**机制:所有目标猫对同一条消息独立回复,互不可见,流式合并(`mergeStreams`)。A2A 在并行模式不接力(MVP 安全边界)。**

```
用户: @全体 #ideate 这个架构选 A 还是 B?
        │
   ┌────┼────┬──────────┐         每只猫独立装配自己的 context,
   ▼    ▼    ▼          ▼         看不到别的猫在想什么(防锚定)
  布偶  缅因  暹罗     金渐层
   │    │    │          │
   └────┴────┴──────────┘  → mergeStreams 合并各自的流,分别成卡片呈现
```
→ 这是"独立思考"(collaborative-thinking Mode B 的 Phase 1 / expert-panel 的 Independent 阶段)的底层实现。**独立性靠"并行 + 不共享 context"在代码层保证,不靠 prompt 叮嘱。**

### 模式 C:Multi-mention 面板(`MultiMentionOrchestrator.ts` + `cat_cafe_multi_mention` MCP 工具)

**机制:一只猫(发起者/Convergence Lead)显式把一个问题 dispatch 给 N 只目标猫,状态机收集各自独立回复,收齐后回调发起猫去综合。** 这是 expert-panel / Mode B 真正"扇出→收集→扇入"的引擎。

状态机(`multi-mention-state-machine.ts`):
```
pending ──start──▶ running ──第1个回复──▶ partial ──收齐──▶ done(终态)
                      │                       │
                      └──── 超时 ────────────┴──▶ timeout(终态)  ── 缺席猫标 timeout
                      └──── 失败 ──────────────▶ failed(终态)
```
时序:
```
布偶(Lead) ──multi_mention(targets=[缅因,暹罗], question, callbackTo=布偶, searchEvidenceRefs)──▶ Orchestrator
                                                                                │ create→running
   缅因 ◀── dispatch ──┤                                                        │
   暹罗 ◀── dispatch ──┤  (各自独立答,recordResponse 收集)                     │
                       └── 收齐(receivedCount≥targetCount) → done ──唤醒──▶ 布偶 综合
```
**硬约束:**
- 调用前**必须带 `searchEvidenceRefs`(≥1 条证据)否则 MCP 层拒绝**(§13 元思考触发器:先搜后问,不滥用 swarm——成本 N 倍)。
- `isActiveTarget` 反级联:已是某 running 面板 target 的猫,不会被二次拉入(防 N×N 爆炸)。
- idempotencyKey 幂等;timeout 有上下界;超时缺席猫记 timeout 不卡死。

**三种模式怎么选:** serial/parallel 由路由层按 intent 自动选;multi-mention 由猫在 skill 流程里主动调(它是"猫发起的面板",不是用户消息触发的)。

---

## 4. 每次调用,一只猫到底看到什么(context 装配)

`buildInvocationContext`(route-serial:521)给每只猫拼的"看见的东西":

```
┌─ 一次猫调用的 context ───────────────────────────────┐
│ L0 身份(identity/家规,native system role,抗压缩)   │ ← 你是谁、四条铁律
│ pack blocks(按需加载的能力包)                        │
│ + 当前 message(+ 上游 previousResponses,仅 debug)    │
│ + teammates 名单 + chainIndex/chainTotal              │ ← 我在链上第几棒、队友是谁
│ + directMessageFrom(谁把球传给我)                    │
│ + sopStageHint(告示牌:你在 SOP 哪个阶段,建议 skill) │ ← 存信息不控流程
│ + alwaysOnDocs(constitution 原则,F163 flag-gated)    │ ← 宪法层
│ + memory recall(evidenceStore 分层检索)              │
│ + activeSignals / worldContext / pingPongWarning…     │
│ + MCP callback instructions(怎么 @ 队友、怎么调面板)  │
└──────────────────────────────────────────────────────┘
```
**"告示牌哲学"**:SOP 阶段提示是**注入信息**,猫看了**自己决定**怎么动——平台不强推流程。

---

## 5. spec/design 阶段:具体几个 agent、怎么排兵(回答你的问题)

Clowder 没有专职 spec/design agent。spec/design 由**通用猫 + 三个 skill** 完成,每个 skill 决定"这一步上几只猫、各扮什么角色":

### 5.1 `collaborative-thinking`(把想法变 spec 的主力)

| Mode | 上几只猫 | 角色排布 |
|---|---|---|
| **A 单人探索** | **1 只** | 单猫和你 1:1:理解上下文→给 2-3 备选+tradeoff→每段问"方向对吗"→产出 `feature-specs/*.md`。**brainstorm→spec 默认就一只猫**(成本低)。 |
| **B 多猫思考** | **N 只(2-4)** | 六阶段:① 独立思考(parallel,禁互看)② 有分歧才串行辩 **2-3 轮**(限轮)③ **你选扇入者** ④ 扇入者综合(**分歧不抹平**)⑤ 其他猫复核纠误读 ⑥ 你确认。用于架构选型/流程设计/跨模型互补。 |
| **C 收敛沉淀** | 1 只 | 把决策落 ADR/教训落 lessons/规则落指引文件。 |

**OQ(开放问题)分流**(贯穿 B/C):每个 OQ 必须标
- **技术 OQ**(回滚成本低)→ 猫自决 + 事后通报,**不升级**;
- **价值 OQ**(碰愿景/安全/外部契约/不可逆/显著成本)→ **升级你 + 附 Decision Packet**。
闸门 = **可逆性**。

### 5.2 `expert-panel`(多猫专家团,正式分析/方案)

**上 2-4 只猫,显式分配角色:**
```
        Convergence Lead(默认 Analyst 兼,可指定)
        分发(dispatch payload 禁夹带 Lead 自己的判断/拆题)
              │ multi_mention(模式 C)
   ┌──────────┼──────────┐
   ▼          ▼          ▼
 Analyst   Assessor   Strategist        ← 不同视角 = 不同 objective
 架构/技术  风险/成本   生态/趋势          (认知多样性,不是同质复制)
   │          │          │
   └──────────┴──────────┘
   每条结论必须 WHY 链四格: Evidence / Reasoning / So-what / Confidence
              │
       Synthesis(Lead 综合,保留共识区+分歧区+Open Questions+Premortem)
              │
       Contributor Check(各猫确认没被误读,不能跳)
              │
       Delivery(洞察卡片 + 语音 + DOCX 报告)
```

### 5.3 `feat-lifecycle`(feature 全生命周期,含 Design Gate 与验收)

**Design Gate 按类型决定上几只猫、谁拍板:**
```
功能类型        →  谁确认            →  方式
───────────────────────────────────────────────────
前端 UI/UX      →  你(CVO)          →  猫画 wireframe,你 OK 才开 worktree
纯后端          →  其他猫(≥1)       →  collaborative-thinking 讨论 API/数据模型共识
架构级          →  猫(出方案)+你(拍板) → 猫讨论出方案 + Decision Packet → 你拍板
trivial         →  跳过              →  ≤5 行/纯重构/文档
```
叠加门禁:架构 cell 归属一问(F191)/ **Eval Contract(F192,见 §7)**/ 元审美自检(坐标变换 vs 多项式堆项)。

**验收(completion)——这里明确是 3 只猫的角色分离:**
```
作者猫(写的那只)
   │  产出 User Visibility Disclosure + CloseGateReport
   ▼
Reviewer 猫(peer-reviewer 角色,≠作者,跨 family 优先)  ← 代码 review
   │
   ▼
守护猫(Vision Guardian,≠作者 ≠reviewer,动态从 roster 选)
   │  产出【逐字原话对照表】: | 铲屎官原话(逐字) | 实际状态(截图/命令) | 匹配? |
   │  有未匹配 → BLOCKED 踢回
   ▼
放行 close
```
→ **"写代码的猫不验收"是硬规则**(SOP `handle_check: reviewer_not_author` / `guardian_handoff_present`),靠**角色身份分离**保证独立,不靠同一只猫自觉。

**小结"spec/design 几个 agent":** brainstorm→spec 默认 **1 只**;需要多视角的架构/方案 **2-4 只**(各持不同 objective);验收强制 **作者+reviewer+守护 3 只角色分离**。猫总池通常 3-4 只,跨模型。

---

## 6. brief → 结构化意图(Need Audit:LLM 软评分 + 代码硬分流)

这是"把模糊 PRD 变可执行"的入口,也是 Clowder "软硬分工"最干净的样板。

```
PRD/brief
  │ (LLM 抽取)
  ▼
IntentCard[]  字段: actor / contextTrigger / goal / objectState /
  │            successSignal / nonGoal / sourceTag(A=AI推断 H=人 D=文档) / confidence …
  │
  ├─▶ detectRisks() —— 纯正则,零 LLM(risk-detection-service.ts)
  │     8 信号: hollow_verbs(improve/optimize…) · missing_actors(the system/none) ·
  │     missing_success_signal(空=critical) · ai_fake_specificity(A+objectState空) ·
  │     scope_creep(everything/enterprise) · missing_edge_cases · unknown_data_source · hidden_deps(≥4)
  │
  └─▶ computeBucket(LLM 给的 clarity/groundedness/necessity/coupling/size 分, sourceTag) —— 确定性决策表
        ┌──────────────────────────────────────────────────────────┐
        │ sourceTag==='A'                       → validate_first(硬gate:AI推断不许直接做)│
        │ clarity≥2∧grounded≥2∧necessity≥2∧coupling≤2∧size∈{S,M} → build_now            │
        │ necessity≥2 ∧ clarity<2               → clarify_first  (resolutionPath=confirmation)│
        │ clarity≥2 ∧ grounded<2                → validate_first (evidence)               │
        │ clarity≥2∧grounded≥2 ∧ necessity<2    → challenge      (escalation)             │
        │ else                                  → later                                  │
        └──────────────────────────────────────────────────────────┘
```
→ **LLM 只出"软分",代码算"该做/该澄清/该验证/该挑战/该搁置"和升级路径。** 这是它把"判断"做可靠的核心招式。

---

## 7. SOP 状态机(纪律怎么自动执行)

`sop-definitions/development.yaml` 把开发流程定义成**数据状态机**:

```
kickoff ─▶ impl ─▶ quality_gate ─▶ review ─▶ merge ─▶ completion
  每个 stage 带:
   · suggested_skill(建议加载哪个 skill)
   · hard_rules[](severity: blocker)  —— 每条带 predicate.type:
        ┌ 机器可验:git_state_predicate(worktree前main ahead=0 behind=0)/ env_check(Redis只6398)/
        │           command_pattern(必跑 pnpm test)/ command_sequence(P1修完必re-trigger review;
        │           禁 gh pr close 假装 merge)/ handle_check(reviewer≠author;守护handoff在场)/ sha_dedup
        └ manual_only:需人/CVO判断(还没结构化artifact)——带 future_candidate(将来升级成机器校验)
   · pitfalls[](severity: warn)
```
**"愿景驱动 + 全链路自动推进"**(SOP.md §17):没达成愿景=没完成;SOP 写了下一步就**直接做、不停下来问"要不要继续"**;只在"不可解决的阻塞"或"manual_only 闸门"停。

→ 这就是它"哪些自动、哪些必须人"的**精确账本**:能写成确定性谓词的由代码挡,挡不住的标 manual_only 并记好升级路径。

---

## 8. 贯穿全局的主线(它真正的"怎么做")

把上面串起来,Clowder 的设计哲学只有一条:

> **LLM 负责生成与软评分;确定性代码负责所有闸门、路由、分流、纪律。猫是"硬轨之上的软力量"。**

- 路由策略(ideate+多猫→parallel)= 代码;A2A 接力 guard(depth/streak/fairness)= 代码;
  intent 分流(computeBucket)= 代码;风险检测(detectRisks)= 代码;SOP hard_rule = 代码;
  谁验收(reviewer≠author)= 代码。
- LLM 只在骨架内做两件事:**生成**(spec/分析/方案/代码)和**软评分**(clarity/可逆性/影响面)。
- "判断"(价值/不可逆/愿景)走**决策漏斗**给人(宏观=人/中=猫讨论/微=猫自治);"可查的"(代码/历史/文档)**不打扰人**("能翻代码解决的不要问人")。

**可靠性来自确定性骨架,不来自 LLM 自律。** 这是它敢说"低人参与度也能跑"的根因。

---

## 9. 对 feat-397 的含义(简短)

1. **收敛**:Clowder 是 human-on-the-loop(CVO 在价值岔路拍板),和我们三轮研究 + 222 条数据(76% 判断不可剥离)一致——它是现实版 feat-397 的实战参考,不是"全自动"反例。
2. **最该搬的是那条主线**:spec/design 的 escalation **别让 LLM 自判"是不是价值岔路"**,而是 **LLM 出软分(clarity/可逆性/影响面)→ 代码按 `computeBucket` 式确定性表决定 auto/clarify/escalate**。直接落地 D3。
3. **可直接搬的件**(全 SHIPPED + 黑盒):决策漏斗 + 可逆性闸门(D3)/ Design Gate 类型分流(谁拍板分档)/ `detectRisks` 式确定性需求气味检测(spec 结构断言,D5 评测先行)/ Eval Contract F192 / 逐字原话对照表(用你的原话语料当 ground truth)/ CloseGateReport 封话术(反 drift)/ expert-panel 三件(认知多样跨模型 + dispatch 禁夹带 + 分歧不抹平,满足 round-3 三条件)/ A2A 行首 @ 接力(agent 间交接)。
4. **你比 Clowder 能更省人的地方**:它"每 feature 必人工 Design Gate + 跨猫守护";你可在其上把**可检索的 24% 真正自动掉**、把**稳定品味(风险/审美/命名)用原话案例库降为"确认"而非"决策"**。

---

## 10. Caveats

- **重 + IM 中心**:React/Electron/Redis/多 CLI adapter;大量 IM/语音/游戏/排行榜基础设施你不需要(你只要前两环 spec/design)。
- **Need Audit 是 in-memory `Map` store**(IntentCardStore,F076)——可能偏早期/demo,生产强度待考。
- **`refs/decision-matrix.md` 此克隆缺失**(manifest 声明 path,文件未 sync)——Decision Packet 精确字段需去线上仓库找;其余均第一手核实。
- 旧的 v1(弱 agent 报告)/v2(我上一版只对框架没讲机制)已删且 v1 未入库无法找回——本版意在比二者都清楚、且全部源自一手源码。

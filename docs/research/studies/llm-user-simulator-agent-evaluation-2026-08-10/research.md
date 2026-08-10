---
status: research-snapshot
recorded-at: 2026-08-10
nano-baseline: ed69eabd8aac87f885c34a96a52626440dc74c32
source-baseline: tau2-bench@668d3bcd135c02aa3438f987ef45735b7c163ee3; ToolSandbox@165848b9a78cead7ca7fe7c89c688b58e6501219; SWE-Together@811a70a28ff20bfbeabf9a8b5ec42152d16c9b4f
current-landing: feat-532-design
current-owner: docs/changes/feat-532-spec-memory-loop/design.md
---

# 受控用户模拟证据记录

## 研究问题

本轮研究围绕一个具体实验问题展开：Baseline 与 Memory Treatment 都运行同一个 `change-spec-author`，但真实 owner 不可能亲自参与八个 case、每个 arm 三次、多个候选方案的所有对齐。模拟 owner 应根据哪些信息回答、如何在多轮中保持一致，以及怎样避免它成为另一个暗中帮助 Candidate 的 spec co-author？

需要分别回答：

1. simulator 能看到哪些私有信息，哪些必须留在 evaluator/control plane？
2. 一个持有完整 owner context 的 native simulator 是否足够，何时才需要额外披露控制？
3. simulator 如何在发散问答中说明自己使用了哪些依据？
4. simulator 自己的错误怎样发现，是否影响当前 run 有效性？
5. 模拟交互与最终质量判断能否由同一个模型承担？
6. 如何用真实 owner 证据校准 simulator，而不把复杂人格提示变成新的实验变量？

## 基线与证据标签

| 对象 | 固定基线 | 用途与限制 |
|---|---|---|
| nano-multiagent | `ed69eabd8aac87f885c34a96a52626440dc74c32` | 核对 feat-532、owner-answer policy、F/P/V/H inventory 与当前 `change-spec-author`；本 study 不改变 current behavior |
| τ²-bench | `668d3bcd135c02aa3438f987ef45735b7c163ee3` | 观察 scenario/evaluator 隔离、user prompt、半双工循环和 simulator-error review |
| ToolSandbox | `165848b9a78cead7ca7fe7c89c688b58e6501219` | 观察角色可见性、受控结束工具、知识边界与 few-shot 约束 |
| SWE-Together | `811a70a28ff20bfbeabf9a8b5ec42152d16c9b4f` | 观察 coding Agent 中的状态触发模拟用户、结构化 action 与 completion gate；其 task-specific gold prompt 不适合本实验 |
| UserBench | arXiv `2507.22034`，检索于 2026-08-10 | 观察“先分类当前发言，再披露对应偏好”的两阶段机制 |
| SimulatorArena | EMNLP 2025 | 观察真实 human-AI 轨迹、user profile 与 simulator 对人类评价相关性的关系 |
| RealUserSim | arXiv `2605.20204`，检索于 2026-08-10 | 观察真实用户证据、行为 profile、leave-one-conversation-out 与 directive amplification |
| Mind the Sim2Real Gap | arXiv `2603.11245`，检索于 2026-08-10 | 观察真人与 LLM simulator 在合作度、风格和评价信号上的差异 |

本文使用以下标签区分证据边界：

| 标签 | 含义 |
|---|---|
| 来源事实 | 论文作者陈述、固定源码或测试直接表达的行为 |
| 源码观察 | 本轮从固定开源实现直接读到的结构与约束 |
| 综合推论 | 多个来源共同支持、但不是某一来源明说的机制结论 |
| 本仓采用判断 | 针对 feat-532 的实验选择；最终仍由 change design 冻结 |

## 一、主流实现首先隔离“用户知道什么”和“怎样算成功”

### τ²-bench

源码观察：`UserScenario` 保存 persona 与 task instructions，`EvaluationCriteria` 保存动作、断言和 reward basis；runner 分别把 user scenario 交给 simulator、把 criteria 交给 evaluator。模拟用户的 system prompt 由全局规则、persona 和当前 scenario 组成，其会话状态独立维护。

全局规则明确要求：

- 一次只生成一条消息；
- 未在 scenario 中提供的信息视为 unknown；
- 不得编造事实；
- 逐步披露，等待 Agent 询问具体信息；
- 目标完成、转接或信息不足时使用独立终止标记。

完整交互后，独立 user-only reviewer 逐条核对 simulator 的事实是否来自 instructions，标记 hallucination、提前披露、错误帮助 Candidate、错误阻碍 Candidate和过早结束。由此可见，prompt 中写“不要泄漏”并不够；simulator 自身也必须成为被审计对象。

固定源码：

- [`tasks.py`](https://github.com/sierra-research/tau2-bench/blob/668d3bcd135c02aa3438f987ef45735b7c163ee3/src/tau2/data_model/tasks.py#L15-L78)
- [`user_simulator.py`](https://github.com/sierra-research/tau2-bench/blob/668d3bcd135c02aa3438f987ef45735b7c163ee3/src/tau2/user/user_simulator.py#L99-L180)
- [`simulation_guidelines.md`](https://github.com/sierra-research/tau2-bench/blob/668d3bcd135c02aa3438f987ef45735b7c163ee3/data/tau2/user_simulator/simulation_guidelines.md)
- [`review_llm_judge_user_only.py`](https://github.com/sierra-research/tau2-bench/blob/668d3bcd135c02aa3438f987ef45735b7c163ee3/src/tau2/evaluator/review_llm_judge_user_only.py)
- [τ²-bench paper](https://arxiv.org/abs/2506.07982)

### ToolSandbox

源码观察：ToolSandbox 把 system、user、agent 和 execution environment 作为不同角色，每条消息具有 sender、recipient 和 visibility。模拟用户只有自己的 role view，结束对话也通过受控 `end_conversation` tool，而不是让一个 LLM任意改环境状态。

其 simulator prompt 用知识边界和 task-blind few-shot 减少 hallucination。项目还记录了角色翻转导致模型混淆的问题，说明“另开一个 Agent”本身不等于角色隔离，消息表示和可见性也需要明确。

固定源码：

- [`openai_api_user.py`](https://github.com/apple/ToolSandbox/blob/165848b9a78cead7ca7fe7c89c688b58e6501219/tool_sandbox/roles/openai_api_user.py)
- [`user_tools.py`](https://github.com/apple/ToolSandbox/blob/165848b9a78cead7ca7fe7c89c688b58e6501219/tool_sandbox/tools/user_tools.py)
- [`user_simulator_few_shot_examples.py`](https://github.com/apple/ToolSandbox/blob/165848b9a78cead7ca7fe7c89c688b58e6501219/tool_sandbox/scenarios/user_simulator_few_shot_examples.py)
- [ToolSandbox paper](https://arxiv.org/abs/2408.04682)

综合推论：feat-532 的 Owner Simulator 不应读取 private truth/rubric 后“尽量别说漏”。它应得到足够扮演 owner 的 scenario information；评分真值仍属于另一个信息面。

## 二、环境门控是一种 hardening，不是已证明的默认最优解

### UserBench

来源事实：UserBench 的 oracle user 持有内部偏好，但初始只释放粗粒度需求。系统先判断 Agent 当前话语是否提出具体、相关的偏好问题，再决定披露哪个偏好；对“还有什么偏好”这类泛问不倾倒完整 profile。它还区分 Agent 主动问出的信息和环境自动释放的信息。

来源：[UserBench paper](https://arxiv.org/html/2507.22034)。

### 证据边界与 feat-532 的选择

τ² 主要依靠完整 scenario prompt 和独立 user session 要求逐步披露；UserBench 展示了另一种由环境先判断偏好相关性、再选择性披露的机制。这两种工作提供了可选设计，但本轮来源没有对二者做适用于 spec 对齐场景的 head-to-head，也没有证明 router/controller/speaker/verifier 多层结构优于一个拿到充分 owner context 的 native simulator。

本仓采用判断：feat-532 的对话热路径使用一个独立、持久的 Codex Owner Simulator。它拿到完整 current owner context、简短 interaction guidance 和当前 run 对话，直接返回简短回复、`used_context_refs` 与状态。对话结束后另起独立 auditor，只读 owner context 和 transcript，检查提前披露、无依据编造、前后冲突和引用错报；它不向 Candidate 发言或修复结果，critical error 使整次 run 作废。同 case 批次结束后再对匿名 owner transcripts 做一致性审计，实质冲突使整批而非选择性 run 作废。环境门控保留为 observed-failure escalation，而不是默认热路径。

## 三、真实用户 profile 有价值，但复杂人格提示不是免费的真实性

### SimulatorArena

来源事实：SimulatorArena 用 909 条真实 human-AI 对话比较模拟用户与真人行为，并将用户拥有的信息、偏好/背景和交互风格作为不同 profile 部分。论文报告 user profile 能提高模拟评价与真实人类评价的相关性，同时也指出 profile 越丰富，模型需要同时遵守的约束越多。

来源：[SimulatorArena paper](https://aclanthology.org/2025.emnlp-main.1786/)、[official repository](https://github.com/microsoft/SimulatorArena)。

### RealUserSim

来源事实：RealUserSim 从真实 human-LLM 会话中形成行为 profile，并在测试单条会话时排除来自该测试会话本身的示例。论文把无约束模型的统一正式风格和强手写指令被夸张执行分别概括为 formalism ceiling 与 directive amplification。

来源：[RealUserSim paper](https://arxiv.org/abs/2605.20204)、[dataset](https://huggingface.co/datasets/Salesforce/RealUserSim)。

本仓采用判断：Owner Simulator 可以有一份很短、task-blind、由真实 owner 原话验证过的互动规则；它只描述回复是否简短、何时要求 Agent 先给推荐等习惯。产品判断由另行校对的 current owner context 提供。八个评测 lineage 和 feat-397/feat-532 的内容都不进入行为示例。准确复现语义判断比模仿口头禅更重要。

## 四、模拟用户本身会改变被测 Agent 的成绩

来源事实：[Mind the Sim2Real Gap](https://arxiv.org/abs/2603.11245) 在 τ-bench 上比较真实用户和多种 LLM simulator，发现模拟者通常更合作、较少表现真实用户的模糊与挫败，且强模型不自动意味着更像真人。[Lost in Simulation](https://arxiv.org/abs/2601.17087) 也报告更换 user simulator model 会改变同一 Agent 的成功率。

综合推论：不能因为 Baseline 和 Treatment 共用一个 simulator 就假设 simulator bias 完全抵消。两条 arm 的提问措辞、推荐方式和错误类型不同，正会触发 simulator 的不同失真。

本仓采用判断：

- simulator model、prompt、temperature、response schema 和 fallback 都进入 suite seal；
- 每次 repetition 冷启动，不跨 run 继承披露状态；
- formal run 前先做 simulator qualification；
- formal run 结束后做不干预对话的 simulator audit，critical error 整次作废；
- 胜出方案正式采用前，用第二 simulator backbone 或少量真人交互复核方向；
- 当前结论只称为“在 owner 校准且通过冻结 auditor 的 Native Simulator 下成立”。

## 五、第一性原理下的方案比较

| 方案 | 保留的能力 | 核心失效方式 | 适合的位置 |
|---|---|---|---|
| `native-full-context` | 开放问题理解、多项依据组合、自然多轮 | 主动泄漏、无依据补全、推荐锚定、自报引用不可靠 | 首选对话核心，但不能未经 qualification 和 audit 直接用于正式结果 |
| `native-on-demand-context` | 仍由同一个 Agent 理解问题和组织回复 | 检索遗漏或错检会把已知信息变成未知，增加成本和状态复杂度 | full-context 已观察到稳定 context overload 时的下一候选 |
| 选择性披露 controller | 强披露边界和确定性 | 开放问题被错误路由、复合含义被拆坏、controller 成为语义瓶颈 | 前两者仍有 critical failure 时再比较 |
| post-run auditor | 不改变 Candidate 实际看到的对话，可检测静默污染 | 只能使 run 作废，不能挽救已受影响的 run；自身也要 qualification | 与任一对话核心组合的低干预有效性门禁 |

综合推论：对本实验最重要的不是让每一轮回复都经过最多机制，而是同时满足“发散问题能自然回答”和“模拟失真不能静默进入统计”。因此采用 `native conversational core + non-intervening post-run audit + observed-failure escalation`。auditor 是检测面，不是第二个回复者；升级方案必须针对已经观察到的 failure mode，在相同 qualification set 上证明确有收益。

## 六、Coding Agent 的主动纠偏机制为什么不能直接照搬

### SWE-Together

源码观察：SWE-Together 的模拟用户在 coding Agent 完整 turn 后观察 trajectory、diff、耗时和 completion attempt，再选择 `no-op / question / redirect / new_requirement / check_external`。默认 `no-op`，消息上限由代码控制；Agent 第一次声称完成时会触发额外检查。

它还删除 persona 中可能泄漏 ground-truth message 的 `example_phrases`。但具体 task prompt 仍可含历史触发条件或原方案结构，用于重放历史纠偏而非无泄漏对照实验。

固定源码：

- [`user_agent.py`](https://github.com/Togetherbench/SWE-Together/blob/811a70a28ff20bfbeabf9a8b5ec42152d16c9b4f/src/user_agent/user_agent.py)
- [`user_enabled_agent.py`](https://github.com/Togetherbench/SWE-Together/blob/811a70a28ff20bfbeabf9a8b5ec42152d16c9b4f/src/user_agent/agents/user_enabled_agent.py)
- [example task prompt](https://github.com/Togetherbench/SWE-Together/blob/811a70a28ff20bfbeabf9a8b5ec42152d16c9b4f/tasks/openclaw-security-review-flow/user_simulation_prompt.md)
- [SWE-Together paper](https://arxiv.org/abs/2606.29957)

本仓不采用 completion correction。feat-532 已明确：Candidate 没有询问某项 owner 判断时，runner 不主动给答案；Candidate 自己得出正确结论时降低负担，得出错误结论时由独立质量 judge 扣分。若 Owner Simulator 在“完成检查”时主动指出全部遗漏，它会把没有 Memory 的弱 Candidate 救回来，也会把零提问、全靠猜的行为伪装成正常对齐。

可复用的是结构化 action、默认不发言、硬状态与逐 turn trace；不可复用的是把历史最终方案塞入 simulator，以及让 simulator 同时承担最终 spec reviewer。

## 七、与 nano 当前评测资产的接口

现有 `owner-answer-policy.schema.json` 的 `decision_id`、`semantic_answer` 和 `source_refs` 可以作为 current owner context 的一部分，但不再被解释成未来问题的封闭触发表。feat-532 还可纳入 owner 确认的产品原则、已知未知和委托边界，让 Simulator 有足够背景处理开放与复合问题。

Native Simulator 每轮只需输出一个小协议：

```json
{
  "reply": "给 Candidate 的简短回复",
  "used_context_refs": ["D03", "principle:user-visible-state"],
  "status": "answered | ask_author_to_research | no_preference | needs_real_owner"
}
```

`used_context_refs` 用于过程分析和抽查，不要求每个问题命中一个 decision。用户负担根据 `reply` 实际提供的独立事实、判断、确认、纠正或重定向计算：批量问三个仍计三项，同义追问再次计数。Candidate 不问但写错时负担是零，质量另行失败。

## 八、Simulator qualification

正式运行前的 qualification 至少覆盖：

1. 直接问题、同义改写和开放问题能给出 owner 认可的语义回复；
2. 正确推荐得到确认，错误推荐只得到相关纠正；
3. 一条消息里的复合问题能自然回答，贡献项可从实际回复拆分；
4. 已回答问题再次询问时保持一致；
5. 可查事实、design 问题和没有明确偏好的问题按 owner 习惯处理；
6. 没有单项 decision、但可组合回答的问题能使用多条 context；
7. 真正的信息不足不会被 Simulator 随意补成新产品立场；
8. 不会无故倾倒与当前问题无关的完整 owner context；
9. 每个 repetition 都从空状态开始。

这些 fixture 使用评测 lineage 外的真实 owner 问句形态，并由 owner 在看不到 arm 输出时抽查语义等价性。另向 auditor 注入无依据判断、主动披露、前后冲突和错误引用，验证它能稳定作废污染 run、又不会误判正常组合回答。qualification 观察到的问题先通过 context 和 prompt 校准；只有 `native-full-context` 仍存在不可接受失败，才依次比较 `native-on-demand-context` 与选择性披露 controller。

## 结论与证据上限

综合结论：现有证据支持给一个独立 user simulator 足够、隔离的 owner context，让它处理发散问题；也支持把 simulator 自身作为独立审计对象。证据不支持直接断言复杂披露管道更优，也不支持把未经审计的 Native 当作可信用户。feat-532 因此采用 Native 对话核心、非介入式 post-run audit 和按已观察失败逐级增强的组合。

本研究能支持 feat-532 构建一个可审计的 Owner Simulator 实验端点，不能证明它已经等价于真实 owner，也不能预先证明 full-context Native 会通过 qualification。其有效性仍取决于 latest-main 校准后的 owner context、qualification fixtures、auditor 检出能力、真实 owner 抽查与正式运行 trace。当前八例没有 locked holdout，最终结论仍只属于 exploratory benchmark。

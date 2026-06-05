# Single-agent or Multi-agent Systems? Why Not Both?
**arXiv:2505.18286** — Mingyan Gao, Yanzi Li, Banruo Liu, Yifan Yu, Phillip Wang, Ching-Yu Lin, Fan Lai

> **性质**: 🟡 RESEARCH（实验性论文，Cascade 机制部分可工程化落地）  
> **场景相关度**: 中等——实验聚焦可验证的代码/数学 benchmark，但其对"MAS 优势消失边界"的校准对 feat-397 命题有重要约束意义

---

## 1. 论文针对的单 agent 失败模式

本文的出发点与通常的 MAS 文献相反：**它不是从"单 agent 做不好"出发，而是从"MAS 的优势正在消失"出发**，反向推导什么时候 MAS 仍然值得。

论文识别了三类 **MAS 内部的结构性缺陷**（即单 agent 在同等条件下不会暴露的问题）：

### 1.1 Node-Level 缺陷：瓶颈节点
MAS 中存在一个"关键 agent"负责最难子任务，整体性能被这个节点锁死。任何其他 agent 的能力提升对整体无效，只有升级关键节点才有用。
- **对 spec/design 场景的映射**：如果 spec-author 是瓶颈（brief 理解最难），加更多 reviewer 不能解决根本问题；提升 spec-author 的模型能力才有用。

### 1.2 Edge-Level 缺陷：下游 agent 被上游输入淹没
上游 agent 传递了过多不必要的信息（如边界情况分析、冗余约束），导致下游 agent "overthink"并出错。典型案例：SelfCol 代码生成中，problem analyst 和 tester agent 引入太多角落用例，coder agent 反而失败。
- **对 spec/design 场景的映射**：spec-reviewer 若输出长篇 warning 清单，design-author 可能把所有 warning 都处理一遍，导致 design 失焦；应限制 reviewer 产物的格式（CRITICAL/WARNING 分级 + 数量上限）。

### 1.3 Path-Level 缺陷：多跳摘要导致信息丢失
Debate 等迭代式 MAS 中，Round N 的正确中间结论在摘要传递时被丢弃，Round N+1 的 agent 从头推导并得出错误答案（论文举例：正确答案 55 在摘要后消失，最终输出 28）。
- **对 spec/design 场景的映射**：spec 迭代修改轮次中，若 agent 通过消息历史传递上下文而非文件系统 artifact，关键决策理由会在 context 压缩时丢失。

---

## 2. 论文提出的 Multi-agent 结构

本文没有提出新拓扑，而是对已有框架（SelfCol/Debate/MetaGPT/ChatDev/TDAG）做横向比较，并在此基础上提出 **Request Cascading 混合机制**：

### 2.1 实验覆盖的 MAS 框架
| 框架 | 角色/拓扑 | 适用场景 |
|---|---|---|
| SelfCol | Analyzer → Coder → Tester | 代码生成 |
| Debate | 多个 Solver + Summarizer（迭代）| 推理/数学 |
| MetaGPT | PM → Architect → Engineer → QA | 软件工程 |
| ChatDev | CEO/CTO/Programmer/Reviewer/Tester | 软件工程 |
| TDAG | Main Agent + 动态子任务分解 | 规划/旅行 |

### 2.2 Request Cascading 混合机制（核心贡献）

```
输入请求
    │
    ▼
[SAS 先尝试]
    │
    ├── 成功（输出可验证）→ 直接返回（省去 MAS 4-220× token 成本）
    │
    └── 失败 → [升级到 MAS] → 返回结果
```

**Agent Routing 变体**：用 LLM 预判请求难度，高于阈值直发 MAS，低于阈值发 SAS。  
**核心公式**：`总成本 = (1−p)·C_MAS(r) + C_SAS(r)`，p = 被 SAS 成功处理的比例。

**量化结果**：
- 准确率提升：1.1–12%（相比纯 SAS 或纯 MAS）
- 成本降低：最高 88.1%；GSM8K+AIME 组合：比纯 MAS **节省 50% 成本**同时准确率高 2%
- MBPP 实例：Cascade 84.4% 精度用 772 token，纯 MAS 80.8% 精度用 1970 token

---

## 3. 实验证据：随 LLM 能力提升，MAS 优势如何变化

### 3.1 核心趋势："Both Pass / Both Fail"≈ 80%

在所有测试用例中，约 **80% 的案例 MAS 和 SAS 产生相同结果**（都对或都错）。只有约 20% 的案例出现分歧，其中"MAS Win"只是其中一部分。

**直接结论**：随着模型能力提升，MAS 特有的贡献区间在收缩。简单任务 SAS 能解决，过难任务 MAS 同样失败。

### 3.2 MAS 优势消失的任务类型

| 任务类型 | MAS 优势趋势 | 原因 |
|---|---|---|
| 代码生成（HumanEval/MBPP）| 消失中 | ChatGPT 时代差距 10.7%，Gemini-2.0-Flash 时代差距仅 3.0% |
| 基础数学（GSM8K）| 消失 | 现代模型单 agent 已接近饱和 |
| 软件工程（SWEbench）| 急剧收窄 | 未列具体数字，但趋势一致 |

### 3.3 MAS 优势仍有结构性支撑的任务类型

| 任务类型 | 为何 MAS 仍有优势 |
|---|---|
| AIME（竞赛数学，极难）| 节点级专业化 + 多路径探索，SAS 单次推理不足 |
| 复杂多步科学推理 | 任务本身可被分解为有独立验证标准的子任务 |
| 长 horizon 规划（旅行规划/实验设计）| 子任务间依赖关系明确，角色分工有收益 |

### 3.4 论文未覆盖的关键盲区（对本命题最重要）

**论文全程不涉及开放性、主观性任务**——所有 benchmark 都有客观正确答案（exact match / pass@1 / constraint satisfaction）。论文明确表示**没有评估创意生成、开放式推理、主观判断**类任务。

这意味着：论文对"随模型能力提升 MAS 优势消失"的结论，**只能外推到有可验证输出的任务**。Spec/design 任务恰恰不在此集合内。

---

## 4. 对"单 agent 做不好 spec/design"命题的校准

### 4.1 论文支持"命题有边界条件"——但不支持"单 agent 够用"

论文的核心发现是：在**可验证任务**上，随着 LLM 能力提升，朴素 MAS 相对 SAS 的优势正在消失。这一发现对 feat-397 命题是一个**有益的精确化**，而非颠覆：

- **命题的正确性维度**：spec/design 是开放式、主观性、无客观答案的任务，不在"MAS 优势消失"的覆盖范围内。
- **命题需要精确化的维度**：不是"MAS 一定比 SAS 好"，而是"**特定类型的 MAS 结构针对 spec/design 的特定失败模式有结构性补偿**"。朴素 multi-agent debate 不算，同质多 agent 不算，只有功能分离（critic 独立 objective）+ 信息隔离（独立 context）才算。

### 4.2 论文数据如何校准"边界条件"

| 单 agent 失败模式 | 是否在论文验证范围内 | 结论 |
|---|---|---|
| 单一视角 / objective 满足即止 | ❌ 论文未测（开放性任务） | 命题维持：critic 独立 objective 仍有价值 |
| 无法可靠自我批判 | ❌ 论文未测 | 命题维持：独立 reviewer 仍必要 |
| 长开放任务漂移 | 部分相关（Path-Level 缺陷）| 论文证明信息丢失是真实风险，强化 artifact 文件传递的必要性 |
| 无对抗压力 surfacing 假设 | ❌ 论文未测 | 命题维持 |
| Context 装不下"全局产品+架构+调研" | ✅ 论文验证（4-220× token 成本）| 新约束：MAS 本身也有巨大 token 成本，不能无限叠加 agent |

### 4.3 论文对朴素 MAS 的警告在 feat-397 设计中有直接意义

> "Naively converting a SAS solution into an MAS one may yield less accuracy improvement than expected, while incurring substantially higher costs."

这与第一轮报告中 McEntire 案例（11-stage pipeline 从未产生一行有效代码）、以及 MAST 的 41-86.7% 失败率高度一致：**MAS 的价值来自正确的结构性分工，而非堆 agent 数量**。

---

## 5. 人留在哪（哪些决策应升级给人）

论文本身不讨论 human-on-the-loop，但从其失败模式分析可以直接推导：

| 触发条件 | 原因（从论文失败模式映射） | 建议处理 |
|---|---|---|
| SAS 失败但 MAS 也无法确定性成功（"Both Fail" 区间）| Node-Level 缺陷：任务超出当前模型能力上限 | 升级给人，不要让 MAS 循环重试 |
| Reviewer 产出大量 CRITICAL 问题（Edge-Level 风险）| Reviewer 过度发现导致 author 失焦 | 人介入裁决哪些 CRITICAL 真正是阻塞项 |
| 多轮迭代后 spec 仍未通过门禁（Path-Level 累积漂移）| 信息在多轮传递中逐渐失真 | 超过 2 轮打回后强制人介入，不再 auto-retry |
| 请求难度评分在 SAS/MAS 路由阈值附近（模糊区间）| Cascade 机制的灰色地带 | 人确认路由决策 |

---

## 6. 黑盒 CAN / CANNOT

| 机制 | 黑盒可行性 | 说明 |
|---|---|---|
| Request Cascading（先 SAS 后 MAS）| ✅ CAN | 纯提示工程 + 输出可验证性判断，不需要模型内部访问 |
| Agent Routing（LLM 预判难度）| ✅ CAN | 额外一次 LLM 调用做分类，黑盒完全可行 |
| Confidence-guided agent tracing（Ii 公式）| ⚠️ 部分 CAN | 原版需要模型输出置信度 1-10 分数（可用 prompt 要求自报），但非 logit，黑盒可近似 |
| Node-level 关键 agent 识别 | ✅ CAN | 通过追踪每个 agent 的输出质量 + 自报置信度，不需要 logit 访问 |
| Edge-level 信息过载防护（格式约束）| ✅ CAN | reviewer 输出结构化格式 + 数量上限，纯配置 |
| Path-level 防漂移（文件传递代替消息历史）| ✅ CAN | 文件系统作为 artifact 存储，已在第二轮报告推荐 |

---

## 7. 🟡 RESEARCH / 🟢 SHIPPED 标注

| 机制 | 标注 | 谁在用 |
|---|---|---|
| Request Cascading 混合调度 | 🟡 RESEARCH | arXiv:2505.18286，尚无生产集成证据 |
| MAS 在可验证任务优势消失的实证 | 🟡 RESEARCH | 同上 |
| SAS→MAS 升级路由 | 🟡 RESEARCH（思路）/ 🟢 SHIPPED（类似物）| Claude Code 的 `yoloClassifier.ts` 做难度路由是同类思路 |
| Node/Edge/Path 三层 MAS 缺陷分类 | 🟡 RESEARCH | 本文首次系统化分类 |
| MetaGPT / ChatDev 等比较框架 | 🟢 SHIPPED | MetaGPT（GitHub 42k stars），ChatDev（GitHub 26k stars） |

---

## 8. 对 feat-397 实现的直接可搬内容

### 8.1 最高价值：Cascade 思路的 spec/design 类比

论文的 Request Cascading 可直接类比为：

```
brief 进入
    │
    ▼
[spec-author 单 agent 先尝试]
    │
    ├── 门禁 1 通过 → 直接进入 design 阶段（不强制触发 spec-reviewer）
    │                  → 节省一次 reviewer 调用
    │
    └── 门禁 1 未通过 → 触发 spec-reviewer → 反馈循环
```

这与第二轮报告推荐的拓扑一致，但论文数据为"非必要时不升级 MAS"提供了额外理由：**80% 的情况 SAS 和 MAS 结果相同**——对于简单/明确的 brief，spec-author 单 agent 完全能产出合格 spec，不必每次都过 reviewer。

**实现建议**：gate reviewer 调用，只在门禁失败或 brief 复杂度超过阈值时触发。

### 8.2 Edge-Level 缺陷 → reviewer 输出格式约束

论文证明"上游输出过多"是真实的结构性风险。直接对应 feat-397 中 spec-reviewer 的输出规范：
- reviewer 产出必须结构化（CRITICAL / WARNING / SUGGESTION 三级）
- 每级最多 N 条（建议 CRITICAL ≤ 3，WARNING ≤ 5）
- spec-author 在修改轮次只处理 CRITICAL，不必响应 WARNING

### 8.3 Path-Level 缺陷 → 文件系统 artifact 而非消息历史

论文的 Path-Level 缺陷（Round N 正确答案在摘要时丢失）直接验证了第二轮报告已推荐的设计：
- spec.md / design.md 以**文件路径**传递，不在消息历史里复制内容
- 每个 agent 从文件系统读取上游 artifact，独立 context 窗口，无摘要损耗

### 8.4 Token 成本意识 → 不要叠加无必要的 agent 层

论文量化了 MAS 的 token 成本：**4–220× prefill，2–12× decoding**。这对 feat-397 的意义是：

每增加一个 agent（spec-reviewer / design-reviewer / escalation handler），都带来真实的 token 成本。设计时必须问"这个 agent 角色是否补偿了一个真实的结构性失败模式"，而不是"多一个视角总是有益的"。

推荐的最小化角色集（参考 MetaGPT 4 角色消融实验）：
- spec-author（必须）
- spec-reviewer（仅在复杂 brief 或首次通过门禁前触发）
- design-author（必须）
- design-reviewer（仅在门禁失败或 spec 涉及架构创新时触发）

### 8.5 Node-Level 缺陷 → 模型能力分配策略

论文证明整体性能由瓶颈节点决定。直接推论：**spec-author 和 design-author 应使用最强可用模型，reviewer 可用较弱模型**。reviewer 的任务（批评已有文档）比 author 的任务（从 brief 生成文档）认知要求更低，Node-Level 分析支持这种差异化配置。

---

## 9. 对核心命题的最终校准

本论文对"单 agent 做不好 spec/design，需要 multi-agent team"这一命题的修正是：

**命题正确，但需要更精确的表述**：

> 单 agent 在**可验证任务**（代码/数学）上随模型能力提升已逼近 MAS，但在**开放性、主观性任务**（spec/design alignment）上，MAS 的价值来自**功能性角色分离**（独立 objective 的 reviewer）而非数量堆叠。论文同时证明朴素 MAS 转换带来 4-220× token 成本且不保证收益，因此 feat-397 的正确路径是：**最小化角色集 + 门控调用（Cascade 思路）+ 文件系统 artifact 隔离**，而非把每一步都拆成多 agent。

边界条件总结：
- **spec/design brief 足够明确** → spec-author 单 agent 可能直接通过门禁，无需触发 reviewer（类比论文"Both Pass" 80%）
- **brief 复杂 / 涉及架构创新 / 门禁首次失败** → 触发 reviewer（MAS 的有效区间）
- **任务超出模型能力上限** → MAS 也无法救，升级给人（类比论文"Both Fail"区间）

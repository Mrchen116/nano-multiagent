# R2D5 — Escalation 的工程做法（黑盒）

> **研究维度**：只靠"多次采样比一致性 + prompted 置信 + 确定性 gate + human-approval 节点"
> 能把"何时该问人"做到什么程度？value-fork（价值判断 vs 事实判断）能否纯靠 prompting 检测？
> 对开放式生成任务有没有 SHIPPED 的置信/escalation 证据？conformal 只保留黑盒可落地的部分。
>
> **方法**：直接翻本地参考项目源码 + 第一轮报告的 escalation 章节取证，重新整合，给出工程结论。

---

## 一、关键发现

### 1.1 SHIPPED：Deny-by-default 权限门控是最广泛落地的 escalation 工程模式

🟢 **SHIPPED** — **Claude Code** (`src/utils/permissions/permissions.ts`) 实现了一套完整的多层
permission pipeline，是目前可读到的最完整的生产级 escalation 机制。核心结构：

```
1. deny rules（最高优先） → 直接 block
2. ask rules（显式 ask 白名单）→ 强制中断等 human 确认
3. tool.checkPermissions()（工具自身判断）→ 产出 allow/ask/deny/passthrough
4. safetyCheck（bypass-immune 安全检查）→ 即使在 bypassPermissions 模式下仍必须 prompt
5. bypassPermissions / acceptEdits 模式 → 全放行
6. alwaysAllow rules → 放行
7. auto mode classifier（LLM-as-classifier）→ shouldBlock ? deny : allow
8. shouldAvoidPermissionPrompts（headless agent）→ 先走 PermissionRequest hooks，无 hook 则 auto-deny
```

关键设计决策（源码可直接证实）：

- **deny-by-default for headless agent**：当 `shouldAvoidPermissionPrompts=true`（背景/异步 agent），
  无法弹出对话框时，走 PermissionRequest hook 链，如 hook 未决策则**自动 deny**，而不是自动 allow。
  这是"宁可少做错事"的安全偏好。
  — `permissions.ts:953–973`

- **连续 deny 计数触发人工复查（denial tracking）**：
  `DENIAL_LIMITS.maxTotal` 或 `consecutiveDenials` 超限后，即使在 auto 模式下也 fall back to
  prompting（CLI）或直接 abort（headless），避免 agent 在 classifier 持续拒绝时无限卡循环。
  — `permissions.ts:900–948`（`handleDenialLimitExceeded`）

- **safetyCheck bypass-immune**：`.git/`、`.claude/`、shell 配置等路径的 safety check
  在 bypassPermissions 模式下也**不能被绕过**，classifier 可审查但 human approval 不能被取消。
  — `permissions.ts:1167–1173`（step 1g）

**源码路径**：`~/Repos/opensource-hub/claude-code/src/utils/permissions/permissions.ts`

---

### 1.2 SHIPPED：LLM-as-classifier（transcript-based）用于替代逐次 human prompt

🟢 **SHIPPED** — Claude Code "auto mode" 用**一个独立的 LLM 调用**（`classifyYoloAction`）作为
permission classifier，读取完整会话 transcript 决定是否 block 某个 tool use，取代逐次弹窗。

工程关键点（源码 `yoloClassifier.ts`）：

- 使用独立 side query（不污染 main transcript），送入 `auto_mode_system_prompt.txt` + 当前 transcript
- 结果是**二元 shouldBlock**，带 `reason` 字符串供展示
- **两阶段 classifier**：fast（stage1）先判断，如不确定再用带 thinking 的 stage2，trade-off 速度/准确
- classifier unavailable 时有 `tengu_iron_gate_closed` 开关：fail-closed（默认，auto-deny）或 fail-open（fallback to prompting）
- transcript 过长超出 context window 时不重试，直接 fall back to manual approval

这是**对"AI 自我审查替代人工审批"**的生产级实现，做到了：
- 绝大多数安全操作（文件编辑、read-only）通过 allowlist fast path 零 classifier 调用
- 有歧义才走 classifier
- classifier 连续拒绝超限时回退人工

**黑盒可落地性**：`classifyYoloAction` 走独立 LLM API 调用，无需 logprob，是纯 text-in text-out。✅

---

### 1.3 SHIPPED：event-driven async "ask" 结构（opencode + hermes-agent）

🟢 **SHIPPED** — **opencode** 实现了两个独立的异步 interrupt 机制：

**Permission.ask（tool-level）**：
- `permission/index.ts` 中，`ask()` 方法在检测到需要确认时把请求注册为 pending，
  通过 `Bus.publish(Event.Asked, info)` 发出事件，然后 `Deferred.await(deferred)` 挂起 agent 线程，
  等待 UI/前端回调 `reply()` 解除挂起。
- Reply 有三种：`once`（本次放行）、`always`（持久化 allow rule）、`reject`（拒绝并 cascade 拒绝同 session 所有 pending）。
- **源码**：`~/Repos/opensource-hub/opencode/packages/opencode/src/permission/index.ts:179–271`

**Question.ask（agent-level 结构化问题）**：
- `question/index.ts` 实现了多选题式的 human-in-the-loop。agent 通过 LLM tool call 触发 `question.asked`
  事件，前端弹出选项（带 label + description），用户选择后 resolve。
- 支持 `custom=true` 允许用户输入自由文本。
- 支持 `multiple` 多选。
- **源码**：`~/Repos/opensource-hub/opencode/packages/opencode/src/question/index.ts:155–180`

🟢 **SHIPPED** — **hermes-agent** 有 `clarify_gateway.py`，完整实现了：
- `register()` + `wait_for_response(timeout)` 的阻塞式 clarify 请求
- 支持 button UI（inline keyboard）和 text fallback（纯文字回复）
- 10 分钟超时自动 unblock（避免 agent 线程被永远挂起）
- `clear_session()` 在会话结束时批量 cancel 所有 pending clarify
- **源码**：`~/Repos/opensource-hub/self-evolution/hermes-agent/tools/clarify_gateway.py`

---

### 1.4 SHIPPED：规则树 + context-aware deny/ask/allow 三元判断（codex）

🟢 **SHIPPED** — **codex**（OpenAI 官方）用 Rust 实现了 `exec_policy.rs`，核心模式：

- `AskForApproval` 枚举：`Never` / `OnFailure` / `OnRequest` / `UnlessTrusted` / `Granular`
- 规则文件（`.rules`）+策略栈，决定每个 shell 命令是否需要 approval
- `is_known_safe_command` + `command_might_be_dangerous` 作为启发式 fast path
- `Granular` 配置下可以细分：sandbox approval 开关、rules approval 开关分别控制

**模式**：deterministic rule-based fast path → heuristic "dangerous command" detection → ask
— **无 LLM classifier**，完全确定性，速度快，可预测，但覆盖不了语义模糊的情形。

**源码**：`~/Repos/opensource-hub/codex/codex-rs/core/src/exec_policy.rs`

---

### 1.5 SHIPPED：hermes-agent skills_guard — 静态扫描触发 "ask" 升级

🟢 **SHIPPED** — `skills_guard.py` 对 agent-created skills 实施 trust-level × verdict 策略矩阵，
`"agent-created"` 来源 + `"dangerous"` verdict → 返回 `"ask"`，要求用户确认才安装。

这是一个**非 LLM、纯确定性的 escalation gate**：正则静态扫描 → 危险等级 → 安装策略。
说明 escalation 不必须走 LLM confidence：确定性规则对于"这件事明显危险"类决策更可靠。

**源码**：`~/Repos/opensource-hub/self-evolution/hermes-agent/tools/skills_guard.py:41–51`

---

### 1.6 RESEARCH（黑盒可落地）：Sampling-based self-consistency 作为置信代理

🟡 **RESEARCH** — 多次采样对比一致性（Self-Consistency, SC）是第一轮报告中证据最强的**黑盒**不确定性信号。
斯坦福医学信息学研究显示 SC by sentence embedding 在正确/错误回答区分上 ROC AUC 0.68–0.79，
优于 verbalized confidence 和 token-level probability。

**对开放式生成任务（非选择题）的适用性**：

- SC 原本为选择题设计（多次采样 → majority vote）。
- 对开放式生成（spec 段落、设计文档），SC 需要改造为
  **embedding similarity 矩阵**：N 次采样 → 两两相似度 → 平均相似度作为置信分。
- 若平均相似度高（>0.85），agent 的多次输出高度一致，置信高；若低（<0.6），说明有结构性不确定，触发 escalate。
- 这是**黑盒可行的**，只需 N 次 LLM 调用 + embedding 调用，无需 logprob。

**生产中是否 SHIPPED**：目前无已知开源 harness 对"spec/design 质量置信"做了 SC。
Claude Code 的 auto-mode classifier 是 transcript-level 判断，不是 output-level SC。

---

### 1.7 RESEARCH（黑盒，calibration 有限）：Verbalized confidence

🟡 **RESEARCH（⚠️ 慎用）** — 直接在 prompt 里问"你有多确信"。

关键问题（第一轮已证，这里重申工程后果）：
- RLHF 训练模型 ECE（Expected Calibration Error）约为 SFT 模型的 4 倍（0.135 vs 0.034）
- answer generation 电路与 confidence verbalization 电路在 LLM 内部解耦，导致系统性 overconfidence
- **对开放式生成任务更差**：没有"正确答案"作为校准锚点

**黑盒替代**：SC by embedding similarity。若计算成本不可接受，verbalized confidence 仍可作为**辅助信号**，
但不能作为 escalation 的主要依据。建议：verbalized confidence < 0.5 强制 escalate（精确率差但 recall 好）。

---

### 1.8 RESEARCH（黑盒，有校准集要求）：ConU / LofreeCP

🟡 **RESEARCH（黑盒可落地，有前置条件）** — ConU 和 LofreeCP 是 Conformal Prediction 的
logit-free 扩展，不需要 logprob，纯文本输出即可。

**落地条件**：
1. 需要一个**校准集**（exchangeable i.i.d. 样本，历史 human-reviewed 的 spec/design 决策）
2. 对每个决策定义非符合分数（non-conformity score）— 对开放式生成任务，这个分数本身难以定义（这是主要难点）
3. marginal coverage guarantee：P(correct ∈ set) ≥ 1-α，但是**条件覆盖无保证**

**对本场景的诚实评估**：
- "spec/design 决策对不对"没有明确的 binary ground truth，非符合分数难以定义
- 适用性**仅限于可以被形式化为多选题**的 spec 决策（如 API 风格选项 A vs B vs C）
- 纯开放式生成（整段 spec 好不好）目前没有 ConU/LofreeCP 的已知落地案例

---

### 1.9 value-fork 检测能否纯靠 prompting？

**结论：部分可以，但不可靠，不能作为唯一机制。**

**可以 prompting 检测的信号**（工程可落地）：
- agent 输出中出现表示权衡/偏好的语言标记："可以选择X或Y"、"取决于团队偏好"、"这是个风格问题"
- agent 主动请求澄清（`clarify` tool use）而非给出单一答案
- 在 critic 的 review 中，某条 issue 被标记为 "preference" 而非 "correctness"

**不可以纯靠 prompting 可靠检测的**：
- agent 高度自信地做了一个价值判断，且没有意识到这是 value fork — 最危险的情形
- spec/design 中的"隐性取舍"（如一个看起来是技术决策的选择，背后是架构哲学选择）

**工程对策**：不要依赖 agent 自行识别 value fork，而是**预置一份 value-sensitive decision checkpoint 列表**：
> "凡涉及以下类别的决策，无论 agent 置信度多高，一律 escalate：
> 数据模型设计、对外 API 接口设计、存储策略、技术栈选择、删除已有功能"

这是 deterministic gate，不依赖 LLM 的 value-fork 自我检测能力。

---

## 二、黑盒 CAN / CANNOT 总表

| 技法/模式 | 黑盒 CAN | 黑盒 CANNOT | 本场景可落地性 |
|---|---|---|---|
| Deny-by-default + ask/deny/allow 规则树 | ✅ 完全可 | — | **立即可用** |
| LLM-as-classifier（side-query 判断是否 block） | ✅ 纯文本 in/out | 需额外 LLM 调用开销 | **中期推荐** |
| Async deferred ask（事件驱动 human interrupt） | ✅ 完全可 | — | **立即可用** |
| Verbalized confidence prompt | ✅ 可读，但 calibration 差 | 不能作为唯一依据 | 辅助信号 |
| SC by embedding similarity（N 次采样） | ✅ 纯黑盒 | 开放式生成任务 recall 定义模糊 | 选择题类决策可用 |
| ConU / LofreeCP conformal | ✅ 需校准集 | 开放式生成非符合分数难定义 | 仅限多选题 spec 决策 |
| Value-fork 自动检测（prompting） | ✅ 语言标记检测 | 高置信 silent fork 无法检测 | 辅助，不能单独依赖 |
| 确定性 value-fork category gate | ✅ 完全可 | — | **立即可用** |
| Logit-based（entropy/MSP） | ❌ 黑盒 API 无 logprob | — | 不可用 |
| AMULET / T-POP 解码层 | ❌ 需 logit 访问 | — | 不可用 |
| LPP meta-model（gray-box 特征） | ❌ 部分特征需 logprob | black-box only 特征可用，效果降级 | 降权 |

---

## 三、对本 unit 实现的可操作建议

### 3.1 核心 escalation 架构（3 层）

**Layer 1 — 确定性 gate（0 LLM 调用，最高优先）**

```yaml
# 凡 spec/design 决策涉及以下类别，无论 agent 置信度，强制 escalate
MANDATORY_ESCALATE_CATEGORIES:
  - api_contract          # 对外接口设计（URL、参数名、返回结构）
  - data_model            # 数据库 schema、核心数据结构
  - tech_stack            # 技术选型（框架、数据库、消息队列）
  - feature_removal       # 删除/降级已有功能
  - architecture_boundary # 模块边界/依赖方向改变
  - security_policy       # 权限、认证、加密策略
```

实现：在 spec-author / design-author agent 的 output 阶段，用**正则/关键词规则**检查
是否触及以上类别 → 触及则在 artifact 中打上 `requires_human_decision: true` 标记。

参考实现模式：hermes-agent `skills_guard.py` 的 INSTALL_POLICY 矩阵（category × trust_level → allow/ask/block）

**Layer 2 — prompted 置信 + 结构化输出 escalation hint**

在 spec/design agent 的 output schema 中加入字段：

```json
{
  "confidence": "high | medium | low",
  "open_questions": ["..."],
  "value_sensitive_decision": true | false,
  "recommended_action": "auto_proceed | human_review | block"
}
```

agent 被 prompt 为：若存在多种合理选择且没有明确技术理由偏向某一方，必须报告
`value_sensitive_decision: true` 并在 `open_questions` 中列出。

**注意**：这个字段作为**参考信号**，不作为唯一 escalation 依据（verbalized confidence 有系统性偏差）。

**Layer 3 — SC by embedding（仅用于 design 方案选择，非整篇 spec）**

对于 design 中出现的离散选择（方案 A vs B vs C），可以：
1. 独立采样 3 次，让 agent 各自给出建议
2. 计算 3 次建议的 embedding 相似度
3. 若相似度 < 0.7（三次建议高度不一致），escalate to human

成本：3 次额外 LLM 调用，仅在 design decision point 触发，不必每个段落都做。

---

### 3.2 async human-on-the-loop 的工程结构

参考 opencode 的 `Question.ask` + hermes-agent `clarify_gateway.py`，本场景推荐：

```
1. spec-author 产出 artifact 后，读取 requires_human_decision 标记列表
2. 对每条 decision，构造结构化问题（question + options + 默认推荐）
3. 通过 IM 通道异步发给人（不阻塞整个 pipeline）
4. pipeline 暂停在 checkpoint，等待 human reply（可设 24h timeout，超时后用默认推荐继续）
5. 收到 reply 后，写入 design artifact，继续 orchestrator 流程
```

关键：**每次 escalation 都写入 audit log**（决策内容、触发原因、人的回答），
这些日志成为后续 few-shot 案例库的来源。

---

### 3.3 escalation rate 监控

参考第一轮报告中 I-CALM 的结论（4.1% abstention 增量 → 13% 成本降低），
建议设置 spec/design pipeline 的 escalation dashboard：

| 指标 | 目标值 | 超标含义 |
|---|---|---|
| Escalation rate（total） | 15–25% | >30% → agent 过度保守；<5% → 过度自信 |
| Mandatory gate 触发率 | 按类别追踪 | 某类别持续高 → 该类别加入 few-shot 案例库 |
| Human override rate | <20% | >30% → agent 建议质量差，需更新 constitution/critic |
| Escalation latency | <4h | 影响 pipeline 吞吐的核心指标 |

---

### 3.4 value-fork 检测的正确姿势（不过度依赖 prompting）

第一轮报告引用 FAccT 2025 的"AI value forks"概念是正确的方向，但落地建议应更保守：

**DO**：
- 维护一份**明确的 value-fork 触发词/决策类别列表**（deterministic）
- 在 critic agent 的 review schema 中加 `decision_type: factual | preference`，
  `preference` 类决策自动 escalate
- 每次人工裁决后，把"为什么这是 value 而非 fact"的原因写进 few-shot 案例库

**DON'T**：
- 依赖 LLM 自行判断"我现在面对的是 value fork"——当 agent 不知道自己不知道时，这失效
- 把 verbalized confidence 阈值（如"我有 80% 把握"）作为 value-fork 决策的 gate

---

## 四、诚实的 Reality Check

**哪些是真实可用的（现在就能搭）**：

1. deny-by-default + ask/deny/allow 规则树：最可靠，零额外 LLM 调用，claude-code 已经验证
2. async deferred human interrupt：opencode 和 hermes-agent 都有完整实现，直接参考
3. 确定性 value-fork category gate：规则写死，零 LLM，最高可靠性

**哪些需要一些工作但黑盒可行**：

4. LLM-as-classifier side-query：claude-code auto mode 的工程实现可以参考，
   对 spec/design pipeline，classifier 的 system prompt 需要针对"spec/design review"场景定制
5. 结构化输出中的置信字段：加 schema 约束，一次 LLM 调用出结果，但 calibration 有限

**哪些是 hype / 对开放式生成任务帮倒忙**：

6. SC by embedding 在整篇 spec 上做：定义"一致"本身有歧义，embedding 相似度高不等于质量高
7. ConU/LofreeCP 用于整篇 spec 评价：非符合分数无法定义，理论框架在这里落不了地
8. Verbalized confidence 作为主要 escalation 信号：系统性 overconfident，RLHF 模型尤甚

**最大工程风险**：

- **Silent value fork**：agent 高置信地做了一个架构决策，实际上是隐性的价值判断，
  任何黑盒技术都无法可靠检测。唯一对策是预置 mandatory escalation category 列表。
- **Escalation fatigue**：如果 escalation rate 过高（>30%），人会开始无脑批准，
  系统丧失 human-on-the-loop 的实质价值。要从一开始就把 mandatory gate 设计得精准。
- **Audit trail 缺失**：如果 escalation 历史不被记录为结构化日志，
  就无法反向优化 few-shot 案例库和 constitution，系统无法自我改进。

---

## 五、必读一手工程来源

| 来源 | 理由 |
|---|---|
| `claude-code/src/utils/permissions/permissions.ts` | 目前最完整的生产级 escalation pipeline 源码，8 层 decision ladder，denial tracking，classifier fallback |
| `claude-code/src/utils/permissions/yoloClassifier.ts` | LLM-as-classifier 的完整工程实现：2-stage，transcript compaction，fail-closed/open 设计 |
| `opencode/packages/opencode/src/permission/index.ts` | event-driven async human interrupt 的简洁实现，`Deferred.await` 模式直接可复用 |
| `opencode/packages/opencode/src/question/index.ts` | 结构化多选题 human ask，options + custom text，是 spec decision escalation 的 UI 原语 |
| `hermes-agent/tools/clarify_gateway.py` | gateway 模式下 blocking clarify 的完整线程安全实现，含 timeout / cancel / text-fallback |

---

*生成日期：2026-06-04*
*源码验证：本报告中所有"SHIPPED"条目均经过实际源码 grep/read 验证，非二手总结*

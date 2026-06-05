# 第二轮深度研究补充报告：spec/design 自动化前两环

> **服务目标**：直接服务于 feat-397 unit 的实施设计
> **第一轮已覆盖**：品味编译五层方案对比、escalation 五路线技术谱系、MAST 失败分类、四阶段顺序流水线推荐
> **本轮新增**：工程一手源码验证 + SDD 产品拆解 + 失败复盘 + 黑盒再过滤 + 评测 harness 落地
> **完成日期**：2026-06-04

---

## 1. 主表：架构模式/技法 × 标注 × 可迁移性

| 架构模式/技法 | 标注 | 谁在用（来源） | 黑盒 CAN/CANNOT | 对本场景可迁移性 |
|---|---|---|---|---|
| Orchestrator-Worker 分层 | 🟢 SHIPPED | Claude Code (`src/coordinator/coordinatorMode.ts`) | CAN | ⭐⭐⭐⭐⭐ 最直接可搬 |
| Subagent 独立 context 窗口 | 🟢 SHIPPED | Claude Code (`AgentTool/runAgent.ts L382,L531`) | CAN | ⭐⭐⭐⭐⭐ |
| disallowedTools 角色限制（READ-ONLY plan agent）| 🟢 SHIPPED | Claude Code (`built-in/planAgent.ts`) | CAN（纯配置）| ⭐⭐⭐⭐⭐ |
| Artifact 文件传递（文件即记忆）| 🟢 SHIPPED | Claude Code scratchpad + MARE 共享工作区 | CAN | ⭐⭐⭐⭐⭐ |
| ExitPlanMode human choke point | 🟢 SHIPPED | Claude Code (`ExitPlanModeTool/`) | CAN（复用 IM 通道）| ⭐⭐⭐⭐ |
| Coordinator 四阶段流水线（Research/Synthesis/Impl/Verify）| 🟢 SHIPPED | Claude Code `coordinatorMode.ts:204-259` | CAN | ⭐⭐⭐⭐ |
| Generator-Critic 顺序对 | 🟢 SHIPPED | MetaGPT QA role、CVE-Genie、INDICT | CAN | ⭐⭐⭐⭐ |
| AutoCompact 结构化摘要（9 节）| 🟢 SHIPPED | Claude Code `services/compact/prompt.ts` | CAN | ⭐⭐⭐⭐ |
| "保护首尾，压缩中间"轨迹压缩 | 🟢 SHIPPED | hermes-agent `trajectory_compressor.py` | CAN | ⭐⭐⭐⭐ |
| SOUL.md / constitution 按阶段注入 | 🟢 SHIPPED | openclaw `workspace.ts`、hermes-agent 三段式 | CAN | ⭐⭐⭐⭐ |
| Bootstrap 文件按阶段过滤（omitClaudeMd）| 🟢 SHIPPED | Claude Code `runAgent.ts` `omitClaudeMd` 标志 | CAN | ⭐⭐⭐⭐ |
| Artifact DAG（声明式依赖顺序）| 🟢 SHIPPED | OpenSpec (`schema.yaml` + Kahn 算法) | CAN | ⭐⭐⭐⭐ |
| Quick Plan vs 精细路径分叉 | 🟢 SHIPPED | Kiro Quick Plan + OpenSpec `/opsx:propose` | CAN | ⭐⭐⭐⭐ |
| Steering Files / per-artifact rules | 🟢 SHIPPED | Kiro Steering Files (inclusion: always/fileMatch)、OpenSpec rules | CAN | ⭐⭐⭐ |
| Decision-log.md 落盘（决策独立 artifact）| 🟢 SHIPPED | BMAD (`decision-log.md`) | CAN | ⭐⭐⭐ |
| EARS 结构化需求语法 | 🟢 SHIPPED | AWS Kiro (WHEN...THE SYSTEM SHALL) | CAN（格式约束）| ⭐⭐⭐ |
| Deny-by-default 权限门控 | 🟢 SHIPPED | Claude Code `permissions.ts`（8 层 decision ladder）| CAN | ⭐⭐⭐⭐ |
| LLM-as-classifier（side-query，两阶段）| 🟢 SHIPPED | Claude Code `yoloClassifier.ts` | CAN（纯文本）| ⭐⭐⭐ |
| Async deferred human interrupt（Deferred.await）| 🟢 SHIPPED | opencode `permission/index.ts`、hermes `clarify_gateway.py` | CAN | ⭐⭐⭐⭐ |
| 确定性 value-fork category gate | 🟢 SHIPPED | hermes-agent `skills_guard.py` INSTALL_POLICY 矩阵 | CAN（规则+正则）| ⭐⭐⭐⭐ |
| Prompt-as-test（结构性 spec 断言）| 🟢 SHIPPED | Claude Code `promptEngineeringAudit.runner.ts`（85 个断言）| CAN（零 LLM 成本）| ⭐⭐⭐⭐ |
| LLM-as-judge（few-shot 校准到单人品味）| 🟢 SHIPPED（judge 本身）+工程方法可实现 | Claude Code `/security-review` 排除清单模式 | CAN | ⭐⭐⭐⭐ |
| spec-smell 排除清单（规则性 judge）| 🟢 SHIPPED 模式 | 本仓库 `change-verifier` SKILL.md 三维框架 | CAN | ⭐⭐⭐⭐⭐ 已有基础 |
| CIPHER / PROSE 风格偏好推断 | 🟡 RESEARCH（已发表可复现，Cornell/Microsoft NeurIPS 2024）| — | CAN（无训练步）| ⭐⭐⭐ |
| ConU / LofreeCP（黑盒 conformal）| 🟡 RESEARCH（机制黑盒可行，尚无生产集成证据）| — | CAN（需校准集）| ⭐⭐（离散选择题类决策）|
| SC by embedding（多次采样一致性）| 🟡 RESEARCH（斯坦福医学研究 AUC 0.68-0.79）| — | CAN | ⭐⭐（open-ended 定义模糊）|
| MetaGPT 4 角色最优规模（消融实验）| 🟡 RESEARCH | — | — | 指导规模决策，≤4 角色 |
| Drift / AMULET / T-POP（解码层）| 🟡 RESEARCH | — | **CANNOT**（需 logit 访问）| ❌ 黑盒下不可用 |
| KnowNo 原版（需 next-token probability）| 🟡 RESEARCH | — | **CANNOT**（原版需 logit）| ❌ 改用 ConU/LofreeCP |
| PReF / VPL / RLPA（训练时个性化）| 🟡 RESEARCH | — | **CANNOT**（需训练奖励函数）| ❌ 改用 CIPHER 风格 |
| FSPO（Few-Shot Preference Optimization）| 🟡 RESEARCH | — | **CANNOT**（需 meta-learning 训练步）| ❌ 改用 few-shot 案例库直接 in-context |

---

## 2. 针对本 unit 的推荐架构

### 2.1 总体拓扑

在"已有文件化 artifact + 门禁 + orchestrator/worker/reviewer"之上，前两环推荐如下拓扑：

```
用户输入 brief
    │
    ▼
[spec-author agent]  ← 独立 context 窗口
 • system prompt: constitution（≤10 条）+ USER.md + spec 模板
 • 首先发起"价值岔路澄清"（1-2 个强制问题，异步 IM 等待回复）
 • 产出: spec.md（写入文件）
    │
    ▼
[spec-reviewer agent]  ← 独立 context（不携带 author 内部推理）
 • 只读 spec.md artifact + constitution
 • 产出: spec-verdict.md（PASS/FAIL + CRITICAL/WARNING 问题清单）
    │
    ├── PASS → 门禁 1 (orchestrator 层确定性检查: 文件存在 + 必填段落 + GIVEN/WHEN/THEN)
    │               │
    │               ▼ 通过 → 发 IM 通知用户"门禁 1 已过，请确认后进 design"
    │               ▼ 不过 → 打回 spec-author 修改（最多 2 轮）
    │
    └── FAIL → 问题清单发 IM，用户裁决（async，24h timeout 用默认推荐）
    │
    ▼
[design-author agent]  ← 独立 context 窗口
 • system prompt: constitution + spec.md（只读，immutable contract 声明）
 • spec 通过门禁 1 后变 immutable，hash 记录，不允许修改
 • 产出: design.md（写入文件）
    │
    ▼
[design-reviewer agent]  ← 独立 context（fresh eyes）
 • 只读 design.md + spec.md + constitution
 • 产出: design-verdict.md
    │
    ├── PASS → 门禁 2 (确定性检查) → 发 IM 通知 → 移交已有 change-orchestrator
    └── FAIL / value-sensitive → 发 IM async escalation → 用户裁决
```

### 2.2 Context / Artifact 流

**原则**：每个 artifact 以文件系统状态为真值，不以 agent 记忆为真值（OpenSpec OPSX 教训 + Claude Code Agent Teams 设计）。

| Artifact | 产出方 | 消费方 | 传递方式 | immutable 时机 |
|---|---|---|---|---|
| `spec.md` | spec-author | spec-reviewer, design-author | 文件路径（不在消息历史里传内容）| 门禁 1 通过后，hash 锁定 |
| `spec-verdict.md` | spec-reviewer | orchestrator（路由决策）| 文件 | — |
| `design.md` | design-author | design-reviewer, change-orchestrator | 文件路径 | 门禁 2 通过后 |
| `design-verdict.md` | design-reviewer | orchestrator | 文件 | — |
| `escalation-log.jsonl` | orchestrator | 后续 few-shot 案例库 | append-only 文件 | — |

**Context 隔离规则**：
- spec-author 不注入 CLAUDE.md 等代码操作约束（类似 CC `omitClaudeMd`），只注入 constitution + USER.md + 澄清结果
- reviewer 不读 author 的内部推理过程，只读 artifact 文件——这是 Claude Code "fresh eyes" 设计原则的直接应用（`coordinatorMode.ts:289` 原文验证）
- design-author 注入 spec.md 内容作为 attachment（post-compact 后 orchestrator 主动重注入），不放进消息历史

### 2.3 品味装载方式

三件套，对应 hermes-agent 三段式 stable/context/volatile（本轮一手源码验证，见 r2d4）：

**Stable tier（缓存命中最稳定）**
- `SOUL.md`（brand/identity/vibe，~500 字以内）
- `SOUL.md` 追加"Design Taste"段：从 `docs/changes/*/spec.md` 的 `A(原话)` 段 LLM 辅助蒸馏的 10-15 条决策示例（格式：情境 + 用户原话 + 判断模式）

**Context tier**
- `AGENTS.md` / 操作约束（红线、格式规范、澄清记录要记原话等）

**Volatile tier（per-session 刷新）**
- `USER.md`（用户偏好/工作风格，初版手填，后续每 5 unit 重新蒸馏一次）
- 检索到的 2-3 条历史相关 Q+A（CIPHER 风格：从 `docs/changes/*/spec.md` 关键词检索，注入 few-shot section）

**注意**：`/personality` 式的 overlay 切换（hermes 实现）在切换时会重建整个 agent（`agent = None`），使 prefix cache 完全失效——不适合高频 spec/design agent 场景。品味注入优先走 stable tier 文件，不走 overlay 切换。

### 2.4 Escalation 机制

三层结构，可靠性递减、成本递减：

**Layer 1 — 确定性 gate（0 LLM 调用，最高优先）**

```yaml
MANDATORY_ESCALATE_CATEGORIES:
  - api_contract          # 对外接口设计变更
  - data_model            # 数据库 schema / 核心数据结构
  - tech_stack            # 技术选型（框架/数据库）
  - feature_removal       # 删除已有功能
  - architecture_boundary # 模块边界/依赖方向改变
  - security_policy       # 权限/认证策略
```

实现：spec-author/design-author 产出后，orchestrator 用正则/关键词扫描是否触及上述类别，触及则打 `requires_human_decision: true`。参考 hermes-agent `skills_guard.py` 的 INSTALL_POLICY 矩阵模式（source × verdict → allow/ask/block）。

**Layer 2 — prompted 置信 + 结构化输出 escalation hint**

agent 输出 schema 增加字段：
```json
{
  "confidence": "high | medium | low",
  "open_questions": ["..."],
  "value_sensitive_decision": true,
  "recommended_action": "auto_proceed | human_review | block"
}
```

此字段为参考信号，不作为唯一 gate 依据。

**Layer 3 — Async escalation ticket（IM 通道）**

参考 opencode `Question.ask` + hermes `clarify_gateway.py`：
1. 产出 `requires_human_decision: true` 的 issue 列表
2. 构造结构化问题（context + proposed decision + alternatives）
3. 通过已有 IM 通道发给用户（不阻塞整个 pipeline，async）
4. 24h timeout → 使用默认推荐继续
5. 回复写入 `escalation-log.jsonl`（成为 few-shot 案例库原材料）

**永久约束**：不允许无上限自动重试——这是 McEntire 11 阶段流水线消耗全部预算的直接原因。每个 agent 最多 2 轮修改，超限强制 escalate。

### 2.5 评测 harness

两层，成本递增：

**Layer 1：结构性断言（prompt-as-test，零 LLM 成本）**

参考 Claude Code `promptEngineeringAudit.runner.ts`（本轮验证真实存在，85 个断言）：

```python
# tests/spec_eval/test_spec_structure.py
def test_spec_has_required_sections(spec_content):
    assert "## Purpose" in spec_content
    assert "## Requirements" in spec_content
    assert "## Acceptance Criteria" in spec_content

def test_acceptance_criteria_format(spec_content):
    # 每条验收标准必须有 GIVEN/WHEN/THEN
    scenarios = extract_scenarios(spec_content)
    for s in scenarios:
        assert re.search(r'GIVEN.*WHEN.*THEN', s, re.DOTALL)

def test_no_implementation_details(spec_content):
    # spec 不该包含实现层决策
    forbidden = ["使用 SQLite", "走 SSE", "用 FastAPI"]
    for f in forbidden:
        assert f not in spec_content
```

打 `@pytest.mark.spec_eval`，在门禁 1 前作为 orchestrator 的确定性检查运行。

**Layer 2：LLM-as-judge（有成本，可标 `@pytest.mark.e2e`）**

参考本仓库已有 `change-verifier` SKILL.md 三维框架（Completeness/Correctness/Coherence），前移到 spec 阶段：

```python
judge_prompt = f"""
# Constitution（spec 质量基准）
{constitution}

# Spec-Smell 排除清单（命中即 CRITICAL）
- spec 包含实现层决策（"使用 X 技术"）而非用户面行为描述
- 验收标准不含 GIVEN/WHEN/THEN（无法被测试化）
- 使用模糊表达（"适当地"、"尽快"）而无可测量标准
- 某条 requirement 无法被独立验证（依赖另一条才能判）

# 历史接受的 spec 片段（few-shot，2-3 条）
{retrieved_good_examples}

# 待评 spec
{spec_content}

输出格式：PASS/FAIL + CRITICAL/WARNING 分级问题清单
"""
```

judge 校准方式：`docs/changes/*/spec.md` 的历史 accepted spec 片段作为 good examples，历史 verifier 报告中标记为 CRITICAL 的 spec 片段作为 bad examples。**不要期望 judge 评测"可演进性"**——它能评的是"是否清晰可测试化"，可演进性靠下游滞后指标（fix_rounds / verifier_critical 数量）。

### 2.6 先做什么 / 什么先别做

**先做（P0，今天就能搭）**：

1. spec-author / design-author 作为独立 context 窗口启动，system prompt 用三件套（constitution + USER.md + SOUL.md 片段）
2. spec.md / design.md 以文件传递（不在消息历史里传内容）
3. orchestrator 层确定性 done 判定（文件存在 + 段落检查），不靠 agent 自报完成
4. 强制澄清窗口：spec-author 开始前发 1-2 个澄清问题到 IM，等回复后才继续
5. 门禁 1 / 门禁 2 后 spec 变 immutable（记录 hash），design-author 只能引用不能修改

**先别做（P1 之后）**：

- 多 agent spec debate / 群聊：Martingale Curse + 76-89% problem drift，开放式规划任务系统性失效
- 全自动无 human checkpoint：OpenEvolve reward hacking 证明系统会找最短路径绕过质量检查
- 超过 4 个 agent 角色：协调开销超过边际收益（MetaGPT 消融实验）
- 任务依赖 DAG 自动构建（Kiro Tasks 阶段做法）：spec/design 阶段依赖分析准确率不稳定，保留人工 milestone 拆分
- Steering Files 粒度化偏好注入：当 constitution 被证明不够用时再加，不要过早引入

---

## 3. 第一轮推荐的黑盒再过滤表

### 3.1 需要删除或降级的推荐（第一轮错误）

| 第一轮推荐项 | 问题 | 黑盒状态 | 替代方案 |
|---|---|---|---|
| **Drift（解码层对齐）** | 第一轮错误标为"无需训练可用"。实际：写入 logit 空间，黑盒 API 无法访问 (arXiv 2502.14289) | ❌ CANNOT | CIPHER 风格：属性分解 + prompted 偏好检索 + few-shot |
| **AMULET（test-time online learning）** | 每 token 解码层在线学习，需 token-level 访问 (ICLR 2025) | ❌ CANNOT | Session 内维护偏好 delta 文件，每轮结束 prompted agent 更新，下轮注入 |
| **T-POP（解码层 dueling bandit）** | token-level dueling bandit，需解码层控制 (ICML 2026) | ❌ CANNOT | 同 AMULET 替代 |
| **KnowNo 原版** | 需要 next-token probability。第一轮混淆"无需训练"和"黑盒可行" | ❌ CANNOT（原版）| ConU + LofreeCP；或 SC（embedding 相似度）+ verbalized 融合 gate |
| **PReF（矩阵分解奖励函数）** | 训练步需要 RL/DPO 基础设施 | ❌ CANNOT | CIPHER 风格：从历史 Q+A 原话推断偏好 → 结构化 preference_profile.json → 检索注入 |
| **VPL / RLPA** | 变分编码器训练 / RL fine-tune | ❌ CANNOT | 同 PReF 替代 |
| **FSPO（Few-Shot Preference Optimization）** | 框架名称含"Optimization"——需 meta-learning 训练步 | ❌ CANNOT | 直接用 few-shot in-context learning（FSPO 的原始动机黑盒可实现，不需要它的训练步）|
| **DPO-f+** | DPO 训练步 | ❌ CANNOT | 收集 approve/reject 对作为 few-shot 案例注入，无需训练 |
| **RLPA** | RL 训练步，fine-tune Qwen-2.5 | ❌ CANNOT | 同 PReF 替代 |

### 3.2 需要修正的推荐（部分成立）

| 第一轮推荐项 | 问题 | 修正后状态 |
|---|---|---|
| **LofreeCP / ConU** | 黑盒机制上可行，但尚无生产 harness 集成证据（🟡RESEARCH）；对 open-ended spec 生成，非符合分数难以定义 | 仅用于 spec 中**离散选择题类决策**（方案 A vs B vs C），不用于整篇 spec 质量评估 |
| **LPP（gray-box + black-box 特征融合）** | gray-box 特征（logprob）黑盒下不可用；black-box 特征子集（verbalized confidence、uncertainty indicators）可用但精度降级 | 仅使用 black-box 特征子集；gray-box 部分用 SC 替代 |
| **Procedural Memory（LangMem/Letta）** | 黑盒可行，但需自托管基础设施；`/personality` 切换会让 prefix cache 完全失效（本轮源码验证：`agent = None` 重建）| 可用，但退化方案更实用：结构化 JSON preference_profile 文件 + agent 读写工具 |
| **CIPHER 机构归属** | 第一轮调研报告标注"Microsoft/DeepMind"，交叉验证发现是 Cornell + Microsoft Research，无 DeepMind | 来源修正：Cornell/Microsoft Research NeurIPS 2024 |
| **Mem0 与 AWS 的关系** | 调研报告说"exclusive memory provider"，实际是 AWS Strands Agents SDK 的**可选**集成伙伴 | 措辞修正："AWS Strands Agents SDK 合作集成"，非 exclusive |

### 3.3 保留（验证属实）

| 推荐项 | 验证结论 |
|---|---|
| Constitution + Critic Agent + Few-shot 三件套 | 🟢 所有条目有生产证据，黑盒完全可行 |
| Claude Code 四阶段 coordinator 流水线 | 🟢 `coordinatorMode.ts:204-259` 原文验证，描述准确 |
| "不要 lazy delegation"（Synthesis 由 coordinator 自己做）| 🟢 源码原话验证，第一轮描述准确 |
| planner disallowedTools 白名单强制只读 | 🟢 confirmed（含 ExitPlanModeTool + NotebookEditTool，比第一轮描述更完整）|
| Verbalized confidence ECE 问题（可用但作辅助信号）| 🟢 保留，数据属实 |
| McEntire 11 阶段流水线 100% 失败 | 🟢 CIO.com 原文验证，数字完全吻合 |
| OpenSpec v1.0 删除"途中编辑"承诺（架构失败教训）| 🟢 CHANGELOG 原文确认 |
| Claude Code compact 9 节结构、post-compact 重注入 | 🟢 源码验证（节 6 "所有用户消息原文"是防 drift 关键段）|

---

## 4. 必读一手工程来源

**1. `~/Repos/opensource-hub/claude-code/src/coordinator/coordinatorMode.ts`**

目前最完整的公开 orchestrator 设计实现。370 行系统提示，包含四阶段流水线（Research/Synthesis/Impl/Verify）、并发策略、"不要 lazy delegation"的工程规范。spec-author 阶段的 Synthesis 角色直接参考这里。

**2. `~/Repos/opensource-hub/claude-code/src/services/compact/`（整个目录）**

生产级 compaction 的完整工程实现：9 节结构摘要（节 6 "所有用户消息原文"是防 intent drift 的关键）、post-compact 重注入（5 文件 × 5K tokens × 50K budget）、circuit breaker（3 次失败上限，有 BQ 数据支撑）。长规划链 context 管理的最优参考。

**3. `~/Repos/opensource-hub/OpenSpec/`（schema.yaml + CHANGELOG.md + docs/opsx.md）**

记录了"phase-locked 线性 spec 流水线的具体失败"（CHANGELOG v1.0）与修复路径（OPSX artifact DAG）。`<project_context>` 标签分离背景信息 vs 输出内容的机制可直接借鉴。

**4. 本仓库 `.claude/skills/change-verifier/SKILL.md`**

已 shipped 的 LLM-as-judge 三维框架（Completeness/Correctness/Coherence），是 spec 评测 harness 的最近邻参考。把它的评测逻辑前移到 spec 阶段（不看代码，只看 spec 结构）是最低成本的评测起步路径。

**5. `~/Repos/opensource-hub/claude-code/src/utils/permissions/permissions.ts` + `yoloClassifier.ts`**

生产级 escalation pipeline（8 层 decision ladder、denial tracking、LLM-as-classifier 2 阶段实现）。`clarify_gateway.py`（hermes-agent）是 IM 场景下 blocking clarify 的最完整 shipped 实现。两者合看可直接设计本项目的 escalation 机制。

---

## 5. Reality Check

### 5.1 被证明帮倒忙的

| 做法 | 证据 | 强度 |
|---|---|---|
| 多 agent debate 用于开放式规划 | Martingale Curse（数学证明）+ 76-89% problem drift（MAST 实测）| 🔴 高置信 |
| 11+ 阶段门控规划流水线 | McEntire 实验：28/28 成功（单 agent）vs 0/28（11 阶段管道）| 🔴 高置信 |
| 全自动 planning 无 human checkpoint | OpenEvolve：验证 agent 被进化算法移除，成功率 53%→30% | 🔴 高置信 |
| 同质 agent 水平扩展（>4）| "45% 规则" + 17.2x 错误放大（DeepMind）+ AgentPrune（ICLR 2025）| 🟠 中置信 |
| spec/design 通过消息历史传递（不文件化）| OpenSpec OPSX 架构倒退教训 + MAST FM-2.6 推理-行动不匹配 | 🟠 中置信 |
| constitution > 20 条 | 遵守率急剧下降（Curse of Instructions，多项独立报告）| 🟠 中置信 |

### 5.2 是 Hype 的

- **"多 agent = 更智能"**：信息论上界证明 MAS 性能上界由任务固有不确定性决定，不由 agent 数量决定。2 个认知互补的 agent 可匹配 16 个同质 agent（Yang et al.）。
- **"test-time 个性化方法（Drift/AMULET/T-POP）无需训练、个人开发者可用"**：这是第一轮报告的核心错误，本轮已纠正——它们"不训练"但需要解码层访问，黑盒 API 完全拿不到。
- **"全自动 spec/design 可达到生产质量"**：McEntire 实验、MAST 实测、OpenEvolve reward hacking 三方独立证据均指向相反结论。适度 escalation rate（15-25%）是质量保障，不是系统失败的标志。

### 5.3 最大工程风险

**风险 1（最高）：规划阶段无确定性终止条件**

spec/design 是开放式生成，没有"正确答案"。如果 done 判定靠 agent 自报（"我完成了"），agent 会无限精化或提前截断。必须在 orchestrator 层硬编码 done 条件（文件存在 + 段落检查），不能让 agent 自己决定。这是 McEntire 11 阶段管道 100% 失败的直接根因。

**风险 2（高）：Silent value fork**

agent 高置信地做了一个架构决策，实际上是隐性的价值判断，任何黑盒技术都无法可靠检测。唯一对策是预置 mandatory escalation category 列表（见 §2.4 Layer 1），确定性规则，不依赖 LLM 自识别。

**风险 3（高）：spec 被 design-author 悄悄修改**

OpenEvolve 实验证明，系统会找最短路径绕过质量检查。design-author 如果发现 spec 有遗漏或矛盾，最省力的做法是悄悄修改 spec 而不是 escalate。必须在 orchestrator 层锁定 spec（记录 hash），任何修改都触发 escalation。

**风险 4（中）：Escalation fatigue**

如果 escalation rate > 30%，用户会开始无脑批准，系统丧失 human-on-the-loop 的实质价值。从一开始就把 mandatory category gate 设计得精准——宁可漏报几条 soft preference，不要把所有判断都 escalate。

**风险 5（中）：Post-compact spec drift**

compaction 后摘要可能稀释 spec 原话意图。缓解：custom compact instruction 强制保留节 6（所有用户消息原文），spec.md 以 attachment 形式注入（compaction 后 orchestrator 主动重注入），不依赖对话历史保存 spec。

---

## 附：交叉验证纠正汇总

本轮对 9 个维度的关键断言进行了一手源码核实，以下是重要纠正（细节见各维度 r2d* 文件）：

| 被纠正断言 | 原状态 | 纠正后 |
|---|---|---|
| opencode `plan_enter`/`plan_exit` 在 `config/agent.ts` | confirmed（功能真实）| 路径错误：实际在 `agent/agent.ts`，不在 `config/agent.ts` |
| planAgent.ts disallowedTools 只有 AgentTool/FileEdit/FileWrite | 细节不完整 | 实际还有 ExitPlanModeTool + NotebookEditTool（plan subagent 不能自己退出 plan mode） |
| hermes-agent personality overlay "热切换不污染 cache" | 错误 | `/personality` 触发 `agent = None` 重建，prefix cache **完全失效**，不是热切换 |
| Claude Code compact 重注入包含"session start hooks 输出" | uncertain | 该子项在源码中未找到对应实现，其余 4 项重注入（文件/plan状态/skills/MCP）均属实 |
| promptEngineeringAudit 有"64 个断言" | 错误 | 实际有 85 个 `expect` 调用，非 64 |
| security-review 有"14 条 exclusion + confidence 0.7 以下不报" | 错误 | 实际 17 条 exclusion；confidence 阈值体系混用（正文 0.7，FALSE POSITIVE 段用 8/10，实际门禁是 `< 8`）|
| GitHub Spec-Kit "8 阶段流程 Constitution→Specify→Clarify→Checklist→Plan→Tasks" | 错误 | Spec-Kit 顶层命令 5 个，无独立 Clarify/Checklist 阶段；"8 步"是 constitution 命令**内部**步骤 |
| Kiro Steering Files 字段 `alwaysApply: true` | 错误 | 实际字段是 `inclusion: always`（及 `fileMatch`/`manual`/`auto`），无 `alwaysApply` 字段 |
| CIPHER 机构"Microsoft/DeepMind" | 错误 | Cornell University + Microsoft Research，无 DeepMind |
| Mem0 是"AWS exclusive memory provider" | 夸大 | 是 AWS Strands Agents SDK 的**可选**合作集成，非 exclusive |
| Claude Code Agent Teams 标为 🟢 SHIPPED 生产特性 | 标签偏强 | 外部用户需要 env var + flag + GrowthBook killswitch，更准确是 🟡 EXPERIMENTAL（内部默认开，外部 opt-in）|
| McEntire 实验 0/28 是"28/28 单 agent 成功 vs 多 agent 全失败" | confirmed | CIO.com 原文完全吻合，数字无误 |

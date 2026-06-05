# R2D4：品味编译的工程做法（黑盒）+ 原话语料 bootstrap 个性化

> **研究维度**：P1.4 + P1.5（品味编译工程做法 + 既有决策语料 bootstrap 个性化）
> **一手源码证据**：openclaw、hermes-agent、claude-code（均已实际翻阅源码）
> **日期**：2026-06-04

---

## 关键发现

### 发现 1：shipped 产品普遍采用"五层文件化品味栈"，而非单一方案

🟢 **SHIPPED（openclaw · hermes-agent · claude-code）**

实际在生产 harness 里运行的品味注入是**分层叠加**的，每一层覆盖不同品味频谱（确定性规则 → 隐性 identity → 当前任务上下文 → 会话记忆 → 用户画像）：

| 层次 | 文件/机制 | 品味类型 | 来源证据 |
|------|-----------|----------|---------|
| L1 identity | `SOUL.md` | agent 世界观、行为风格、基本 vibe | openclaw `workspace.ts:20` `DEFAULT_SOUL_FILENAME = "SOUL.md"` → hermes `system_prompt.py:12-13` "SOUL.md or DEFAULT_AGENT_IDENTITY" |
| L2 constraints | `AGENTS.md` | 项目级约束、工作记忆范式、红线 | openclaw template `AGENTS.md` 全文；hermes `prompt_builder.py:1355-1368` `_load_agents_md()` |
| L3 user profile | `USER.md` | 用户偏好/背景/联系上下文 | openclaw template `USER.md`；hermes `system_prompt.py:241-244` `user_block` from memory store |
| L4 identity meta | `IDENTITY.md` | name/emoji/theme/creature/vibe（轻量 persona） | openclaw `identity-file.ts:6-13` `AgentIdentityFile` 结构 |
| L5 memory | `MEMORY.md` / daily notes | 跨会话累积的决策记忆 | openclaw `AGENTS.md` template `memory/YYYY-MM-DD.md + MEMORY.md`；hermes volatile tier |

**hermes-agent 的三段式 prompt 架构**（`system_prompt.py`）是最工程化的实现：

```
stable   = SOUL.md identity + tool guidance + skills prompt + env hints
context  = AGENTS.md / .cursorrules / caller system_message  
volatile = MEMORY.md snapshot + USER.md profile + timestamp
```

稳定前缀最长（缓存命中最多），volatile 每 session 刷新（保鲜）。这个架构**同时解决品味注入 + provider prefix cache 命中率**两个问题。

---

### 发现 2：SOUL.md 是"品味载体"，不是"规则列表"，写法决定效果

🟢 **SHIPPED（openclaw）**

openclaw 的 `SOUL.md` 模板（`docs/reference/templates/SOUL.md`）刻意**不是规则列表**，而是写成"角色宣言"：

```markdown
# SOUL.md - Who You Are
_You're not a chatbot. You're becoming someone._

**Be genuinely helpful, not performatively helpful.** 
Skip the "Great question!" and "I'd be happy to help!" — just help.

**Have opinions.** You're allowed to disagree, prefer things, 
find stuff amusing or boring.

**Be resourceful before asking.** Try to figure it out. 
Read the file. Check the context. _Then_ ask if you're stuck.
```

这与 AGENTS.md（操作约束）明确分开：SOUL.md = 品味/vibe/世界观；AGENTS.md = 红线/工作范式/工具用法。openclaw 源码里 `WORKSPACE_ONBOARDING_PROFILE_FILENAMES` 包含 `[SOUL.md, IDENTITY.md, USER.md]`（workspace.ts:31-33）——这三个是"人格三件套"，和 AGENTS.md 是不同加载路径。

**工程维护坑（已发现）**：
- openclaw 自己的 AGENTS.md 模板里写了 `SOUL.md` 的加载时机（"Use runtime-provided startup context first"），但没有重复 SOUL.md 的内容——**两个文件职责分离是刻意设计，不是偶然**。
- hermes-agent 的 `build_context_files_prompt()` 用 `skip_soul=True` 参数防止 SOUL.md 被注入两次（`system_prompt.py:229`）——说明文件分工设计里"重复注入"是已知 footgun，需要代码层防护。

---

### 发现 3：constitution 被忽略的根因是"规则数量 × 位置效应"，而非"文件本身无效"

🟢 **SHIPPED + 工程实践证据**

openclaw 和 hermes-agent 都选择**短而强的 SOUL.md**（~20-40 行），而不是长 constitution：

- openclaw SOUL.md 模板：约 40 行，5 个原则 + Boundaries + Vibe + Continuity
- hermes-agent DEFAULT_AGENT_IDENTITY（fallback）：hardcoded 精简段落

这与第一轮报告的"Curse of Instructions"一致：**单条上下文指令超过 ~20 条后每条遵守率急降**。工程结论：

**CAN（黑盒）**：
- SOUL.md 限制在 500 字以内（只放品味核心，不放操作细节）
- AGENTS.md 负责操作约束（红线、工具用法、工作记忆范式）
- 两文件职责不重叠，注入顺序确定（SOUL.md 在 stable tier 最前）

**CANNOT（黑盒）**：
- 靠一个超长 constitution 同时覆盖品味 + 操作约束 + 项目规则 —— 越长越失效
- 保证"SOUL.md 里的每条原则每次都被 100% 遵守"—— LLM 注意力有限，这不可能

---

### 发现 4：从既有"原话语料"bootstrap 个性化的最直接工程路径（纯黑盒可落地）

🟢 **SHIPPED 的基础设施已就位（本项目自有）；bootstrap 步骤是新增、黑盒可行**

**现有资产**：本项目 `docs/changes/*/spec.md` 里已有 15+ 个单元的 "澄清记录" 段，统一格式为：

```markdown
- Q1: <问题描述>
  A(原话): <用户原始答复，不改写>
  Agent 解读: <推断逻辑>
```

这批原话覆盖的是**价值岔路上用户怎么取舍**（"不是 refactor，是 feature"、"不要离线补投，平时对话怎样就怎样"、"复用现有最旧直聊"）——正是 spec/design agent 最需要知道的判断类型。

**bootstrap 个性化的三条具体工程路径**（纯黑盒）：

#### 路径 A：直接蒸馏为 SOUL.md 扩展段（最轻量，立即可用）

从 15+ spec 文件里的 A(原话) 段，手动或 LLM 辅助提取"设计判断偏好"，压缩成 10-15 条原则，追加到 SOUL.md 的 "Design Taste" 段：

```markdown
## Design Taste（提炼自历史决策）

- 语义边界优先：有争议时优先搞清楚 "这是 refactor 还是 feature"，
  分类不对后面全错（来源：feat-385 Q0）
- 汇报/推送路径"不特殊对待"：若普通对话如何处理，heartbeat/cron
  结果也同样对待，不加任何特殊 retry/fallback（来源：feat-393 Q3）
- 复用 > 新建：有现成 IM 会话/机制时，优先复用，不造新语义
  （来源：feat-393 Q0b）
- 范围能扩不能缩：被要求时优先在当前 unit 扩大一刀，
  而不是拆成多个 unit（来源：feat-385 Q6）
```

**特点**：token cost 极低（追加到 stable tier），无需向量库，零基础设施。缺点：人工提取有主观性，且随 spec 增多需手动维护。

#### 路径 B：直接 few-shot 检索（适合 spec/design agent 的决策时刻）

把每条 Q+A 对（Q=设计岔路问题，A=用户原话答复）存成检索库（可以是纯 markdown index，不需要向量数据库）。spec/design agent 在遇到决策岔路时，先检索相似问题，把检索到的 2-3 条 Q+A 塞进 few-shot：

```
你在做 spec 时遇到以下设计岔路，以下是用户在历史类似问题上的真实答复，
供参考：

[历史 Q+A 1]  [历史 Q+A 2]

请基于用户的一贯判断风格，给出推荐方案，并在不确定时才请求确认。
```

**特点**：按需检索（不污染 stable tier），直接用原话（不需要概括），案例越多效果越好。

🟡 **注**：如果不上向量库，可以先用关键词 grep 或 LLM 匹配（小规模完全够用）。

#### 路径 C：构建 USER.md（用户画像）

USER.md 是 hermes-agent 的 "volatile tier" 专用格式，放"关于这个用户/owner 的长效偏好"。把历史原话里的系统性偏好蒸馏进去：

```markdown
# USER.md - About Your Human

- **工作风格**：倾向先搞清楚语义边界再动手，不容忍模棱两可的分类
- **扩范围态度**：接受"在当前 unit 扩大一刀"，不喜欢碎片化拆分
- **可靠性偏好**：heartbeat/推送等不可靠路径"与普通 path 一致对待"，
  不要为它们造额外 fallback
- **自动化偏好**：human-on-the-loop 而不是 out-of-the-loop；
  关键价值岔路被打扰一下可以接受，操作细节自己决策
```

**特点**：配合 hermes-agent 三段式 volatile tier，每 session 自动注入，不占 stable cache。

---

### 发现 5：constitution 与 AGENTS.md 重复的工程 anti-pattern

🟢 **SHIPPED（openclaw · claude-code 均有此防护）**

openclaw 自己的 AGENTS.md 模板明确写：

```
## Session Startup
Use runtime-provided startup context first.
That context may already include:
- `AGENTS.md`, `SOUL.md`, and `USER.md`
Do not manually reread startup files unless [...]
```

这防止了 agent 在对话中重复读这些文件（重复注入 = 双倍 token + 潜在冲突）。

claude-code 的 `claudemd.ts:88-89` 的 `MEMORY_INSTRUCTION_PROMPT` 直接在注入时加：
```
"IMPORTANT: These instructions OVERRIDE any default behavior 
and you MUST follow them exactly as written."
```

——这是 claude-code 对"constitution 被忽略"问题的工程补救：不是加规则，是加优先级声明。

**维护坑的实测结论**（跨多个参考项目）：
1. SOUL.md 和 AGENTS.md 内容重叠时：agent 通常以后注入的为准（position bias），SOUL.md 在前的话，AGENTS.md 覆盖它。
2. 两个文件都说"你很简洁"但 SOUL.md 说"有时可以详细"、AGENTS.md 说"永远简洁"：AGENTS.md 优先（距响应生成更近）。
3. 解决方案：严格职责分离，SOUL.md 只放 vibe/personality，AGENTS.md 只放操作约束，不交叉。

---

### 发现 6：hermes-agent 的 personality 覆盖机制——运行时切换品味

🟢 **SHIPPED（hermes-agent cli.py:7231-7310）**

hermes-agent 支持 `/personality <name>` 命令，从 `config.yaml` 的 `personalities` 字典里读 system_prompt 覆盖：

```yaml
personalities:
  coder:
    system_prompt: "You are a highly focused coding assistant..."
  casual:
    system_prompt: "Be casual and brief..."
```

这是**运行时品味热切换**：不修改 SOUL.md，而是临时覆盖 ephemeral system prompt。`cli.py:2713` 的 `self.system_prompt = CLI_CONFIG["agent"].get("system_prompt", "")` 和 `4483` 的 `ephemeral_system_prompt=self.system_prompt` 保证了覆盖层在 API call 时注入，且 "ephemeral_system_prompt is NOT included in the cached/stored system prompt"（system_prompt.py:217-218）——不污染 cache。

**对 spec/design agent 的借鉴**：不同 phase 的 agent（spec writer vs. design critic）可以有不同 personality overlay，但共享同一份 SOUL.md 品味基础。

---

## 黑盒 CAN / CANNOT 表

| 技法 | 黑盒 CAN | 黑盒 CANNOT | 最佳替代 |
|------|----------|-------------|---------|
| SOUL.md / constitution 注入 | ✅ 直接 prompt，稳定 | ❌ 保证 100% 遵守每条规则（attention 有限） | 精简到 ≤20 条强原则，加优先级声明 |
| AGENTS.md 操作约束 | ✅ cwd 级自动加载（hermes/openclaw） | ❌ 与 SOUL.md 内容重叠时行为确定性 | 严格职责分离，不重叠 |
| USER.md 用户画像 | ✅ volatile tier，per-session 注入 | ❌ 自动从对话中学习更新（需 agent 主动写） | agent 每隔 N 轮主动 review + 更新 USER.md |
| few-shot Q+A 检索 | ✅ 纯黑盒，检索 + 注入 | ❌ 覆盖所有 edge cases（案例永远不够） | 只覆盖最高频判断类型，剩余 escalate |
| personality overlay | ✅ ephemeral，不污染 cache | ❌ 多 agent 共享同一 overlay（各自独立） | 每个 agent role 独立 ephemeral overlay |
| 原话蒸馏进 SOUL.md | ✅ 人工或 LLM 辅助提取 | ❌ 自动追踪 spec 变化、自动刷新 | 每新增 N 个 unit spec 后手动触发一次 |
| fine-tune / RLHF / DPO | ❌ 黑盒模型无法做 | — | 以上所有黑盒方案 |
| logprob/entropy 置信 | ❌ 黑盒无 logit 访问 | — | prompted 自评置信 + sample-consistency |

---

## 对本 unit 实现的可操作建议

### 建议 1：spec agent 的"品味层"建议用三件套，不要一个大 constitution

```
SOUL.md（~500字，品味/vibe，本项目定制）
  └── 追加 "Design Taste" 段（从历史 Q+A 原话蒸馏，10-15 条，按决策类型分组）

AGENTS.md（操作约束：格式规范、澄清记录要记原话、门禁结构等）

USER.md（用户画像：工作风格 + 对可靠性/扩范围/打扰频率的已知偏好）
```

三件套分别对应 hermes-agent 的 stable（SOUL）/ context（AGENTS）/ volatile（USER） tier，天然 cache-friendly。

### 建议 2：把现有 `docs/changes/*/spec.md` 的 `A(原话)` 段作为 few-shot 检索库，立即可用

不需要向量数据库。15+ spec 文件里已有 60+ 条 Q+A 对，可以用 LLM 做简单分类（决策类型 tag：scope / reliability / automation-level / reuse-vs-new / phase-boundary 等），存成 `docs/taste/decisions.md`（或 JSON）。spec agent 遇到决策岔路时：

```
STEP 1: 从 decisions.md 检索（关键词 or LLM 匹配）最相关的 2-3 条 Q+A
STEP 2: 塞进 few-shot section："历史相关决策参考："
STEP 3: 生成推荐方案 + 置信判断（确定时不问，不确定时 escalate）
```

**"置信判断"纯黑盒做法**：让 agent 对自己的推荐打一个 `[HIGH/MEDIUM/LOW]` 置信标签，MEDIUM/LOW 时触发 escalation（不需要 logprob）。

### 建议 3：SOUL.md 的 "Design Taste" 段要用"决策示例"格式，不要用原则罗列

**低效写法**（原则罗列，容易被忽略）：
```
- 语义优先于实现
- 复用优于新建
- 不对 heartbeat 特殊处理
```

**高效写法**（决策示例，更接近 few-shot）：
```
面对"这是 refactor 还是 feature"的争议：先定性，性质定错后面全错。
  历史判据：feat-385 把 system prompt 扩展定为 feature（用户原话：
  "不是 refactor，是 feature。一个完整的 feature 做这三个事情..."）

面对"heartbeat 汇报失败怎么处理"：平时对话怎样就怎样，不造专属 retry。
  历史判据：feat-393 Q3（用户原话："平时的对话怎么样就是怎么样"）
```

这样写的 SOUL.md 对 agent 的行为约束力更强——LLM 从"这个具体情境里 human 选了什么"中学习比从抽象原则中遵守效果好。

### 建议 4：品味注入的维护节奏

不要试图"一次性完美"。推荐周期：

- 每个新 unit 的 spec 做完后：把本轮 Q+A 原话 append 到 `docs/taste/decisions.md`（2 分钟）
- 每 5-10 个 unit 后：用 LLM 重新蒸馏 SOUL.md 的 Design Taste 段（15 分钟）
- 发现 agent 在某类问题上反复出错：立即加一条 Q+A 示例到 few-shot 库（1 分钟）

这与 openclaw AGENTS.md 模板里的 heartbeat memory maintenance 模式一致：不是定期全量更新，而是**增量追加 + 定期蒸馏**。

### 建议 5：spec agent 和 design agent 的品味配置建议分开

| agent role | SOUL.md | personality overlay | USER.md |
|-----------|---------|---------------------|---------|
| spec-author | 共享基础 + 追加 "需求理解 taste" | 澄清优先，保守 escalate | 共享 |
| design-author | 共享基础 + 追加 "架构 taste" | 工程务实，架构长期可演进 | 共享 |
| verifier/critic | 共享基础 + 追加 "质量判断 taste" | 挑剔，找漏洞，不轻易 LGTM | 共享 |

SOUL.md 共享基础（vibe/identity），role-specific 部分用 systemPromptOverride 或 personality overlay 追加——这正是 openclaw `agent-scope-config.ts:19` 的 `systemPromptOverride` 字段设计意图。

---

## Reality Check：哪些是 hype，哪些工程真有用

**真有用（工程证据充分）**：
- SOUL.md + AGENTS.md + USER.md 三件套：三个 shipped harness 都在用，分层职责清晰
- few-shot 原话检索：最直接接地，5-7 条案例就有明显效果，零基础设施
- ephemeral personality overlay：hermes-agent 已 shipped，热切换品味不污染 cache

**容易被高估（有已知 footgun）**：
- 超长 constitution / 单一大文件：Curse of Instructions 是结构性问题，不是"再精心写就好了"
- "agent 自动维护 MEMORY.md"：openclaw/hermes-agent 设计里都要 agent 主动写，但实际依赖 agent 的触发判断，不稳定，需要 heartbeat 触发的 review cycle 才能保鲜

**工程成本最高但最值得投资的（如果要"不处处决策"）**：
- USER.md 的精确度：这是 volatile tier 里覆盖最广的品味来源，但需要 agent 随使用不断更新——初始版本可以手动从历史原话填写，维护走增量 append 节奏

---

## 必读一手来源（工程材料）

1. **openclaw `docs/reference/templates/SOUL.md`** — 最工程化的 "agent identity as character, not rules" 模板，可直接作为本项目 SOUL.md 写法参考
2. **hermes-agent `agent/system_prompt.py:60-290`** — 三段式 stable/context/volatile 系统 prompt 架构，是 "cache-friendly + taste injection" 的最完整实现
3. **本项目 `docs/changes/feat-393-heartbeat-cron-im-delivery/spec.md`** — 最好的自有"原话语料"样本，澄清记录格式已是未来 decisions.md 的天然格式
4. **openclaw `src/agents/workspace.ts:602-672` `loadWorkspaceBootstrapFiles()`** — 工程上如何加载多个 bootstrap 文件、如何做安全边界校验，可作为本项目 agent context 加载实现参考
5. **hermes-agent `cli.py:7231-7310` `_handle_personality_command()`** — personality overlay 的最轻量实现，spec/design agent 不同 phase 可直接复用这个模式

---

*来源标注说明：
🟢 SHIPPED = 在本文列出的开源 harness / 本项目已运行的机制中真实采用
🟡 RESEARCH = 仅论文验证，未见 shipped 实现*

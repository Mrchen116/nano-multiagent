# 第三轮深度研究：aws-samples/sample-claude-code-agent-team 拆解

> **来源**：https://github.com/aws-samples/sample-claude-code-agent-team  
> **克隆路径**：`/tmp/claude-feat397-r3/04-sample-claude-code-agent-team-aws-sample`  
> **标注**：🟢 SHIPPED — AWS 官方 sample，已公开发布，在 Claude Code agent teams 实验功能下可运行  
> **完成日期**：2026-06-04

---

## 0. 执行摘要

这个仓库是目前可见的、**最完整的 Claude Code native agent team 配置**——不是论文，不是概念设计，是可直接 cp 到 `~/.claude/` 跑起来的配置文件集。

它针对的核心失败模式是：**单 agent 同时担任规划者、实施者、审查者，自我审查无对抗性，且无法在角色边界上强制执行分工**。它的解法不是增加 agent 数量制造辩论，而是**通过角色边界硬分离 + 机器可执行的门禁 + artifact 所有权锁定**实现真正的认知异质性。

对 feat-397 而言：spec-workflow skill 的目录结构、`fullstack-agent` 的规划阶段约束、`review-agent` 的 objective isolation 方式，以及三个 hook 脚本的实现，均可直接搬运。

---

## 1. 这个源针对哪些 spec/design 失败模式，用什么结构去补

### 1.1 失败模式 A：单 agent 规划/实施/审查三合一，自我审查失效

**问题**：单 agent 写完 spec/design 后自己接着实施，再自己"验收"，等于自己出题自己判卷。前两轮研究已确认：移除 critic 后 safety 从 91% 降至 87%、helpfulness 从 79% 降至 72%（INDICT 消融），这是已测量的能力退化，不是理论风险。

**这个仓库的解法**：

`review-agent` 的 objective isolation 做到了三个层面的硬隔离，而非软约定：

**层面 1：文件所有权锁定（`docs/design.md` Agent Roles 表）**

```
fullstack-agent  → 写  spec.md, design.md, tasks.md, decisions.md
coding-agent     → 写  source code, test files
devops-agent     → 写  IaC files, CI configs, READMEs
review-agent     → 写  review.md only（仅此一个文件）
```

`review-agent` 的 system prompt 第一段话：

> "You do NOT write implementation code. You operate as a teammate in an agent team (you only write to `review.md`, not implementation files)."

第二段话明确了所有权单向性：

> "**You are the sole author of `review.md`.** No other agent — including the team lead — should write that file."

**层面 2：team lead 被显式禁止自我审查（`fullstack-agent.md` Review Gate Authority 段）**

```
## Review Gate Authority

You do NOT write `review.md`. The `review-agent` writes it.
Self-review is a category error — review-agent's role is adversarial,
and grading your own homework defeats the purpose of the gate.

If `review-agent` is unavailable for any reason, the review gate is **OPEN,
not auto-PASS**.
```

这是关键设计：工具不可用时门控开启而非默认通过，且 lead 被严格禁止填充该职能。

**层面 3：机器可执行的 TaskCompleted 门禁（`hooks/task_completed_verify_gate.py`）**

```python
# 两个条件缺一不可才允许 complete：
# 1. 任务携带 Run: <command>
# 2. 执行者写了 verification sentinel 文件
if not RUN_CMD.search(text):
    missing.append("task has no `Run:` verification command")
if not os.path.exists(sp):
    missing.append("verification sentinel not found at ...")
```

Sentinel 机制解决了一个关键问题：hook 只能读 lead 的 transcript，看不到 teammate 是否真的运行了测试。Sentinel 是 teammate 的书面证词，且是一次性的（完成后被删除，无法复用）。

---

### 1.2 失败模式 B：spec/design 生成时无结构化"提问-综合"阶段，需求直接映射为实现

**问题**：单 agent 接到 brief 后直接写 spec，缺少"对齐价值岔路"的强制停顿。两轮研究均识别了这个问题：价值岔路（做或不做某功能、边界哪里划）需要人决策，agent 无法可靠猜测。

**这个仓库的解法**：`/brainstorm` 命令（`commands/brainstorm.md`）

```
1. 分析想法 — 识别域、用户、价值主张
2. 最多 10 个澄清问题，一次一个，等待回答后再出下一题
   覆盖：target users / NFRs / scale / integrations / budget / edge cases / MVP scope
3. 综合需求 → 结构化 requirements.md
4. 与用户迭代确认
5. 保存到 .claude/specs/<slug>/requirements.md
   sections: Project Summary / Functional Requirements / NFRs /
             Edge Cases / Out of Scope / Open Questions / Notes
6. 输出物即 spec-workflow 的上游输入
```

这是从 brief 到 spec 的"价值岔路澄清"阶段的具体实现：一次一个问题、等待应答、适配前序答案、不重复已答问题。`requirements.md` 是独立的 artifact，不直接就是 spec——两者之间有一道人工确认门。

人介入点在步骤 4（"Review with user — iteratively refine until the user confirms"）和步骤 7（"Offer next steps"——不自动推进到 spec 阶段，而是等用户决定）。

---

### 1.3 失败模式 C：单 agent 在长任务中角色漂移，从规划者滑变为实施者

**问题**：第一轮研究识别的"长开放任务漂移"：单 agent 在规划阶段写了足够的 spec 后，会自然滑入"我来实现一下"的模式，即使没被要求。这是 objective 不够硬的结果。

**这个仓库的解法**：`fullstack-agent.md` 的"Delegation Is Mandatory"段，措辞强度显著高于普通约束：

```
## Delegation Is Mandatory

You are a **team lead**, not an implementer. Your job is to spec, plan,
and **delegate**. You MUST NOT implement non-trivial code yourself,
**even if it seems faster, even if you think the team-coordination tools
are unavailable, even if you have a fully-formed implementation in mind**.

Trivial direct work (allowed): small spec edits, decision-log updates,
  rewording a single requirement, answering a clarification, reading
  files for research, updating tasks.md status.
Anything else (forbidden — must delegate): scaffolding directories,
  writing any production code, ...
```

更重要的是，它连"降级路径"也封死了——工具不可用时，明确要求 escalate 而非继续：

```
If team-coordination tools appear unavailable, **STOP and escalate** with
a precise description of the failure mode... Do NOT propose pre-baked A/B/C
degraded options. Do NOT proceed with a single-threaded build.
```

Build Phase Entry Gate 条款则是另一道强制停顿：

```
Build Phase Entry Gate: After the user approves the spec, the FIRST tool call
in the build phase MUST be TeamCreate. Not a code edit. Not a Bash command.
Not an Agent spawn. Not a Write of scaffolding. Specifically TeamCreate <slug>-build.
```

---

### 1.4 失败模式 D：task 创建时格式不完整，导致下游无法验收

**问题**：spec 写完后 task 拆解不完整——缺文件路径、缺 acceptance criteria、缺验证命令——使验收变成主观判断而非可执行检查。

**这个仓库的解法**：`hooks/task_created_format_check.py` 在 `TaskCreated` 事件时机器检查：

```python
ROLE_TAG = re.compile(r"\[(coding|devops|sa|sfdc)\]", re.I)
RUN_CMD  = re.compile(r"\bRun:\s*\S")

# 必须同时满足：
# 1. [role] tag
# 2. 至少两个 "|" 分隔（| files | acceptance |）
# 3. Run: <command>
```

不满足则 exit(2) 回滚创建，并输出具体缺失项和修复说明。bypass token `[skip-format-check]` 供非 build 类 coordination task 使用，不影响正常流程。

这把"spec 质量"向下延伸到了"task 质量"——spec 写完不等于工作完成，task 的可验证性同样被门控。

---

### 1.5 失败模式 E：没有 idle-guard，teammate 完成分配任务后自动停止，留下未认领工作

**问题**：并行执行时，某个 teammate 完成自己的任务后直接 idle，不去认领同角色的其他未认领任务，导致工作堆积在 lead 需要手动重调度。

**这个仓库的解法**：`hooks/teammate_idle_workcheck.py` 在 `TeammateIdle` 事件时：

1. 扫描 `~/.claude/tasks/<team_name>/` 下所有 pending、无 owner、无 block、带本角色 tag 的任务
2. 若存在则 exit(2) 阻止 idle，输出 nudge 消息要求认领或通知 lead
3. 最多 nudge `MAX_NUDGES=2` 次（hash 同一任务集），防止死循环

---

## 2. Artifact 组织格式（`.claude/specs/<slug>/`）

`skills/spec-workflow/SKILL.md` 和 `agents/fullstack-agent.md` 都定义了同一个目录结构，重复出现确保每个 agent 都知道：

```
.claude/specs/<slug>/
  spec.md          # 设计决策、需求、约束
  design.md        # 架构、仓库结构（MUST include Security Considerations）
  tasks.md         # 并行分组任务列表（含 agent 分配）
  review.md        # review-agent 每轮产出（PASS/FAIL），仅 review-agent 写
  sa-review.md     # sa-agent Well-Architected 产出（可选）
  decisions.md     # 飞行中决策日志
  requirements.md  # 来自 /brainstorm（可选）
  prd/             # 产品需求文档（可选）
```

`tasks.md` 的格式（机器可执行的 task shape）：

```markdown
## Group 1: <description>
Spec ref: `spec.md#<section>` — <what this implements>.
- [ ] [coding] <verb> <what> | `path/to/files` | <acceptance>. Run: `<command>`
- [ ] [devops] <verb> <what> | `path/to/files` | <acceptance>. Run: `<command>`
```

关键约束（spec-workflow skill）：
- 同一 group 内的任务并行执行，group 间顺序执行
- 同一 group 内不能有两个任务写同一文件
- 有共享接口时，接口 contract 直接 inline 在 task description 里（不靠共享理解）
- SA review 与 implementation 并行运行（review 设计，不 review 代码）

---

## 3. `fullstack-agent` 的规划阶段 prompt 结构（spec/design 生成路径）

`fullstack-agent.md` Phase 1 Plan 段的完整流程：

```
Phase 1: Plan
1. Research — 委托 feature-dev:code-explorer 做深度代码分析
2. Spec at .claude/specs/<slug>/spec.md
   — 设计决策、备选方案、约束、设计
3. Design at .claude/specs/<slug>/design.md
   — 架构、仓库结构、基础设施设计
   — 委托 feature-dev:code-architect 生成实施蓝图
4. Tasks at .claude/specs/<slug>/tasks.md
   — 并行 groups，按 task authoring rules
```

spec.md 和 design.md 是 immutable contract 的体现——后续 build phase entry gate 要求 user 批准 spec 后才能 TeamCreate。整个 Phase 1 只有 fullstack-agent 参与，没有其他 agent；这是规划阶段的单一责任原则。

**spec 触发条件（spec-workflow skill 第一句话）**：

> "Create a spec before any non-trivial work — if it touches multiple files, involves architectural choices, or will be delegated to an agent team."

这是一个三选一的宽触发条件，确保 spec 不被跳过。

---

## 4. 人留在哪

以下是仓库中**显式**设计为人介入点的节点（非降级，是设计特性）：

| 介入点 | 位置 | 性质 |
|---|---|---|
| `/brainstorm` 逐题问答 | `commands/brainstorm.md` 步骤 2 | 强制，每题等待应答 |
| `requirements.md` 确认 | `commands/brainstorm.md` 步骤 4 | 强制，"until the user confirms" |
| Spec 批准（build phase entry gate） | `fullstack-agent.md` Phase 2 开头 | 强制，"After the user approves the spec" |
| Tooling failure escalation | `fullstack-agent.md` Tooling Failure Protocol | 强制，工具不可用时 STOP |
| 同一 blocker 出现两次 | `rules/agent-team-protocol.md` Blocker Reporting | 强制 |
| 超过 3 个 review cycle | `agents/fullstack-agent.md` exit criteria + spec-workflow skill | 强制 escalate |
| review-agent 不可用时 gate 开放 | `fullstack-agent.md` Review Gate Authority | 强制 escalate，不自动 PASS |
| 用户显式接受 open gate 时记入 decisions.md | `fullstack-agent.md` Review Gate Authority | 偏差记录，不静默 |
| AWS 破坏性操作（delete/terminate/modify） | `docs/design.md` Security Considerations | Claude Code permission system |

---

## 5. 黑盒 CAN / CANNOT

**全部可行（黑盒 CAN）**：

这个仓库的所有机制在黑盒 LLM 下完全可用：

| 机制 | 黑盒可行原因 |
|---|---|
| Agent role 分离（md frontmatter + system prompt） | 纯文本 prompt 配置，无训练 |
| `.claude/specs/<slug>/` artifact 组织 | 文件系统约定 |
| task shape 格式约束 | 正则检查，纯规则 |
| TaskCreated/TaskCompleted/TeammateIdle hooks | Python 脚本，读文件系统状态 |
| Verification sentinel 机制 | 文件写入/检查，无 LLM 介入 |
| Review gate authority（文件所有权锁定） | prompt 约束 + hook 强制 |
| `/brainstorm` 逐题问答流程 | 纯对话，无结构化推理需求 |
| Build Phase Entry Gate | 对话协议约束 |
| `[skip-format-check]` / `[skip-verify]` bypass token | 文本匹配 |
| decisions.md 决策日志 | 文件写入 |
| Nudge cap（MAX_NUDGES=2）loop guard | 状态文件计数 |

**无 CANNOT 项**：这个仓库没有使用任何需要 logit 访问、fine-tune 或训练时干预的机制。这是其工程价值的核心所在——所有机制都在 text-in/text-out + 文件系统这一层实现。

---

## 6. 标注

🟢 **SHIPPED** — aws-samples/sample-claude-code-agent-team，AWS 官方 GitHub 组织发布，MIT-0 license，明确标为"sample configuration for multi-agent development workflows using Claude Code"，可直接安装运行（需 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`）。

---

## 7. 对 feat-397 直接可搬的内容

### 7.1 `.claude/specs/<slug>/` 目录结构 → 可直接作为 nano-multiagent spec/design 的 artifact 组织规范

```
.claude/specs/<slug>/
  spec.md       ← change-spec-author 的输出
  design.md     ← change-design-author 的输出（MUST 含 Security Considerations）
  tasks.md      ← orchestrator 的工作分解
  review.md     ← change-reviewer 的独占输出
  decisions.md  ← 飞行中决策日志（orchestrator 写）
  requirements.md ← 可选，brainstorm 阶段产物
```

这个目录结构与 nano-multiagent 现有的 `docs/changes/<unit>/design.md` 等文件组织有直接对应关系，可以作为 unit 目录内的标准化子结构。

### 7.2 `review-agent` objective isolation 的三层实现 → 直接对应 change-reviewer 的设计约束

具体可搬的是三个措辞模式：
1. "`review.md` 是你唯一的输出文件，其他 agent 包括 orchestrator 不写这个文件"
2. "如果你发现 `review.md` 已被其他 agent 写过，视为 TODO 标记，不是有效 verdict，重新开始审查"
3. "如果 review-agent 不可用，门控开放而非自动 PASS"

### 7.3 task shape 格式约束 → change-orchestrator 拆解 milestone 时的 task 写法标准

```
[role] <verb> <what> | <file paths> | <acceptance criteria>. Run: <command>
```

这与 nano-multiagent 现有 `tasks.md` 中的 milestone 描述对应。TaskCreated hook 的正则逻辑（role tag + pipe count + Run: 检查）可作为 orchestrator 创建 task 的自检规则——即使不实现 hook，也可作为 orchestrator system prompt 里的格式约束。

### 7.4 Verification sentinel 机制 → change-impl-worker 的完成证明协议

Worker 完成任务后必须：
1. 运行 Run: 命令
2. 写 sentinel 文件（`echo "pytest PASSED" > .verified/task-<id>.verified`）
3. 才能 report 完成

这直接解决了 MEMORY.md 里记录的"change-impl-worker 收尾合并不可靠"问题——sentinel 是 worker 的书面证词，orchestrator 可以机器检查而非依赖 transcript 推断。

### 7.5 Build Phase Entry Gate 的"spec 批准后才 TeamCreate"约束 → spec/design 阶段结束的人工检查点

`fullstack-agent.md` 的措辞可直接搬入 change-orchestrator 的 system prompt：

> "After the user approves the spec, the FIRST tool call in the build phase MUST be TeamCreate. Not a code edit. Not a Bash command. Specifically TeamCreate."

对应到 nano-multiagent：design.md 门禁 2 通过（用户推进）后，orchestrator 的第一步是创建 worktree 和分支，不得直接开始修改代码。

### 7.6 Delegation Is Mandatory 的"不允许 lead 实施"措辞 → change-orchestrator 的角色锁定

```
You MUST NOT implement non-trivial code yourself, even if it seems faster,
even if you think the team-coordination tools are unavailable,
even if you have a fully-formed implementation in mind.
```

加上降级路径明确封堵：工具不可用时 STOP + escalate，不允许"先做点再说"。

### 7.7 `/brainstorm` 的逐题问答结构 → change-spec-author 的价值岔路澄清阶段

`commands/brainstorm.md` 的 10 个问题域（target users / scale / integrations / NFRs / budget / deployment / edge cases / MVP scope）可作为 change-spec-author 澄清问题的覆盖checklist。逐题模式（一次一题、等待应答、适配前序答案）是防止用户被问题墙淹没的工程实践。

### 7.8 三个 hook 脚本 → 可作为 nano-multiagent 的 Claude Code hooks 直接使用或参考实现

- `task_created_format_check.py`：TaskCreated 事件，格式检查
- `task_completed_verify_gate.py`：TaskCompleted 事件，sentinel 验证
- `teammate_idle_workcheck.py`：TeammateIdle 事件，未认领任务 nudge

`team_hook_common.py` 的 `read_payload / allow / block / audit / safe_path_component` 工具函数可直接复用。Fail-open 设计原则（任何内部错误 exit(0) 放行，防止 hook bug 阻断工作流）可直接沿用。

---

## 8. 与前两轮研究的衔接

| 前两轮已建立的结论 | 本源的补充/确认 |
|---|---|
| Generator-Critic 顺序对是 ROI 最高的品味注入 | 确认：review-agent 是纯 critic，代码所有权硬隔离，不可绕过 |
| Immutable contract（spec 需 human approval 才可变更） | 确认：Build Phase Entry Gate 要求 user 批准 spec 后才进入 build，飞行中变更写 decisions.md |
| Artifact 文件传递（文件即记忆） | 确认：所有 agent 通过 `.claude/specs/<slug>/` 共享状态，不靠共享 context |
| ExitPlanMode human choke point | 确认：spec 批准是显式 choke point，且不允许 lead 在工具不可用时降级绕过 |
| 4 角色是消融实验下的最优规模 | 本仓库恰好 4 个核心角色（fullstack/coding/devops/review），sa-agent 是 on-demand 扩展 |
| 认知多样性 > 同质数量 | 确认：4 个角色有完全不同的 objective（规划/实施app/实施infra/审查），不是同质扩增 |
| Prompt-as-test（结构性 spec 断言） | task shape hook 是这一模式在 task 层面的落地：task 本身携带可机器验证的格式 |

**本轮新增，前两轮未覆盖**：
1. **Verification sentinel 机制**：解决了"hook 看不到 teammate transcript"这一工程约束，是 attestation-by-file 模式
2. **Idle-guard（TeammateIdle hook）**：loop-safe 的 nudge 机制，有 MAX_NUDGES + content-hash 去重
3. **Review gate open（不等于 auto-PASS）**：工具失败时门控状态的明确语义
4. **Bypass token 设计**（`[skip-format-check]` / `[skip-verify]`）：不是所有任务都需要 Run: 命令，但 bypass 需要显式声明，不能静默跳过
5. **Session resume hygiene**：deferred tool schema 在 resume 时会被 drop，需要重新 load；team/task 状态持久在文件系统

---

## 附录：关键文件路径索引

| 文件 | 关键内容 |
|---|---|
| `agents/fullstack-agent.md` | Delegation Is Mandatory / Build Phase Entry Gate / Review Gate Authority / Tooling Failure Protocol / Session Resume Hygiene |
| `agents/review-agent.md` | Sole author of review.md / Review Methodology 四步 / 三个 review cycle 的 focus 递进 |
| `agents/coding-agent.md` | Required Skills 强制加载 / Verification sentinel 写法 |
| `agents/devops-agent.md` | 同 coding-agent + documentation skill 强制 |
| `agents/sa-agent.md` | On-demand 扩展 agent，medium effort，parallel with implementation |
| `skills/spec-workflow/SKILL.md` | `.claude/specs/<slug>/` 目录结构 / task format / 并行化原则 / security scan 优先级 |
| `commands/brainstorm.md` | 10 个问题域 / 逐题问答流程 / requirements.md 输出格式 |
| `rules/agent-team-protocol.md` | Teammate lifecycle / Verification gate / Enforced Hooks 说明 |
| `hooks/task_created_format_check.py` | ROLE_TAG + pipe count + RUN_CMD 正则 / bypass token / fail-open |
| `hooks/task_completed_verify_gate.py` | Sentinel 路径构造 / sentinel 消费（one-time use）/ fail-open |
| `hooks/teammate_idle_workcheck.py` | MAX_NUDGES=2 / content-hash loop guard / claimable task 扫描逻辑 |
| `hooks/team_hook_common.py` | read_payload / allow / block / audit / safe_path_component 工具函数 |
| `docs/design.md` | Agent Roles 表 / Coordination Model / Security Considerations 三节 |
| `settings.json` | CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 / hooks 事件绑定 / fail-open 语义 |

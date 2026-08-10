# Design Review: feat-517-python-dynamic-workflows

## Round 1

### Metadata

- reviewer: `/root/feat_517_design_reviewer`
- review_mode: `full`
- mode_reason: 首轮 Gate 2；需完整核对现状、12 项设计决策、Gate 1 全部约束、所有 delta-spec、原型与两个 milestone，并独立复核本仓代码/长青契约、Claude Code 2.1.226 capture 和 2026-08-09 当前官方文档。
- started_at: `2026-08-09T01:13:33+08:00`
- completed_at: `2026-08-09T01:24:44+08:00`
- duration: `11m11s`

### Verdict

Issues Found — 6 CRITICAL / 2 WARNING

### Coverage

| 输入 | 覆盖结果 |
|---|---|
| `spec.md` | 4 条澄清原话、10 个 Requirement、46 个 Scenario、范围与非目标均逐条核对 |
| `design.md` | 现状事实、架构总览、决策 1–12、接口/数据流、三入口 UX、测试、风险、runbook、milestone 均完整核对 |
| `prototype.html` | tool selected/deselected、下一轮生效提示、launch approval、compact progress、run detail/controls、desktop/mobile 响应式均核对；与设计 must-match 表一致 |
| delta-spec | kernel 5 份、CLI 1 份、Gateway 3 份、IM 3 份逐条与 canonical target 对账 |
| milestone | `M1-cli-workflow-runtime`、`M2-assistant-workflow-surfaces` 的纵向价值、依赖、范围交集与退出标准均核对；空目录骨架按约定不作为问题 |
| 独立事实核验 | 本仓 active-tool/prompt、SDK、PA 配置快照、child runner、background task、permission、session storage、命令/UI 接缝；本机 2.1.226 provider captures/二进制研究；2026-08-09 官方 Dynamic Workflows 文档 |

### 现状与证据台账

| 原子 | 独立核实 | 结论 |
|---|---|---|
| active tools 是每轮 provider tool schema 与 prompt 的共同输入 | `src/agent/core/agent/runtime.py:339-341,453-488,1152-1165`；`src/agent/core/agent/loop.py:228-258,371-382` | 成立；决策 1 可把 `Workflow` active tool 作为唯一开关 |
| PA 的工具选择是真白名单且按新轮 runtime snapshot 投影 | `src/personal_assistant/product.py:357-373`；`src/personal_assistant/gateway/session_composition.py:39-75`；`capability_projection.py:39-56` | 成立；Workflow 作为 optional/default-off 可实现完整下一轮切换 |
| 产品只能经 `agent.sdk` 使用内核，IM 不 import agent | `AGENTS.md` 与 `docs/specs/kernel/sdk-boundary.md:47-79` | 成立；决策 12 的归属正确，但 delta 合并缺口见 R1-C3 |
| child Agent 可复用既有 in-process runtime | `_SessionSubagentControl`、`RuntimeRunner` 与 `AgentTool` 当前接缝已检查 | 成立；不需要复制第二套 Agent loop |
| background task 当前只有 subagent/bash 语义，通用 notifier/stop 对非 subagent 按 bash 处理 | `src/agent/core/background_tasks/{models,registry,notifications}.py`；`src/agent/platform/tools/builtins/task_stop.py:143-152` | 成立；决策 6 的 WORKFLOW 类型、cooperative stop 和一次通知扩展方向闭合 |
| session storage 可派生 workflow artifact/journal 路径 | 当前 `JsonlSessionFiles` storage base 与 session/subagent 目录已检查 | 成立；决策 6 不引入进程外服务 |
| permission broker 可承载 launch card 与 child permission 回父会话 | current broker、auto-mode gate、父会话 permission route 已检查 | 成立；决策 8 与官方 Default/Auto/Bypass、child `acceptEdits` 行为一致 |
| CLI/Web/Gateway 命令发现目前各有明确接缝 | `src/coding_cli/input/repl_commands.py`、`src/coding_cli/commands.py`、Web `slash-candidates.ts`、Gateway inbound parser | 成立；决策 1/10 明确同源派生并禁止 parser 绕过 allowlist |
| provider 获得完整 Workflow tool object，且没有另一段稳定 Workflow system section | E1 request `.../896b1c37-dec8-402f-9116-238c55377086/2026-08-08_17-59-46_754-req-anthropic_messages.json` | 成立；canonical tool 21,259 chars / description 19,214 / schema 1,775 及 SHA-256 均与设计一致 |
| keyword/standing reminder 的逐字文本 | E1 与 `.../aa5fe232-c31f-45bf-a0dd-c416fb1dc66c/2026-08-09_00-56-12_152-req-anthropic_messages.json` | 文本成立；但 provider role/order 未固定，见 R1-W1 |
| Python 采用 AST policy + 真编译执行是 JS runtime 的必要语言移植 | 固定二进制调用链见研究 `research.md:113-129`，本设计 `design.md:148-201` | 成立；未额外发明 subprocess 或逐节点解释器 |
| resume chained v2 key | 二进制证据与研究 `Claude Code Dynamic Workflows 运行机制.md:259-284` | key 公式成立；并发 effect ordinal 仍是研究明确未知项，设计却承诺 100% 稳定，见 R1-C1 |
| saved workflow symlink 规则 | 2026-08-09 官方文档 “Save the workflow for reuse” | 设计规则不等价，见 R1-C5 |
| environment model override | 本仓仅有 `NANO_MULTIAGENT_LLM_MODEL` 作为基座/默认模型；当前 per-run `model_override` 优先于该基座；无 workflow-child 专用环境 override | 设计的“已有环境模型 override 最终优先”不成立，见 R1-C6 |

### 决策台账

| 决策 | Gate 1 / 现状 / 下游核对 | 结果 |
|---|---|---|
| 1. active Workflow tool 唯一开关 | 覆盖 schema/description、reminder、named/management commands、ultracode；next-turn snapshot 与运行中旧轮冻结均明确 | pass |
| 2. 逐字 capture，只做 Python 机械变换 | source locator、长度/hash、clause inventory、字段/schema 保留与动态 guideline 均可复核 | pass |
| 3. Python AST + compile/exec | capability boundary、禁止直接 OS 能力、checkpoint、线程/loop 生命周期均足以实施 | pass |
| 4. primitives/limits | `agent/parallel/pipeline/workflow/phase/log/budget` 与上游可观察语义完整；并发 ordinal 未闭合 | R1-C1 |
| 5. 复用 child loop | return-value、structured result、tool denylist、父权限路线合理；environment precedence 无现存 seam | R1-C6 |
| 6. journal/snapshot/state machine | background、pause/stop/restart、revision、一次 notification 和 session persistence 闭合 | pass |
| 7. chained v2 resume | key 与 prefix cut-off 正确；“actual start ordinal”未定义为 Python 并发下可重复的顺序 | R1-C1 |
| 8. permission broker | 三权限模式、Once/Always/Deny、child accept-edits、unattended fallback 与官方契约一致 | pass |
| 9. human origin/reminder/budget | origin 范围、无第二道资格 gate、+500k ledger 边界明确；provider reminder placement 仍有歧义 | R1-C4, R1-W1 |
| 10. save/discovery/named commands | roots、precedence、built-in/plugin adapter、禁用后不绕过工具正确；symlink 规则偏离 baseline | R1-C5 |
| 11. worktree adapter | 短生命周期、dirty 保留、失败不回退共享 cwd，归属与回退边界合理 | pass |
| 12. SDK query/control | DTO 与窄方法、不泄漏 manager、产品/内核边界合理；canonical SDK delta 未修改既有穷举契约 | R1-C3 |

### Gate 1 约束台账

| Spec 原子 | 场景数 | 设计覆盖 | 结果 |
|---|---:|---|---|
| 全入口可用且工具选择完整开关 | 4 | 决策 1、三入口 UX、A/B provider/command 测试 | pass |
| 默认逐次 opt-in / session ultracode / human-only | 5 | 决策 9、CLI/IM origin 与 mode | R1-C4, R1-W1 |
| 可检查、编辑、复用的受限 Python 脚本 | 5 | 决策 2–4、artifact/policy/runtime | pass |
| 确定性多 Agent 编排 | 5 | 决策 4–7 | R1-C1 |
| 后台、三入口进度与控制 | 5 | 决策 6、12、snapshot/events 与三入口 UX | pass |
| 同会话最长相同调用前缀恢复 | 4 | 决策 7 | R1-C1 |
| 保存、发现、分发、命名运行 | 5 | 决策 10 | R1-C5 |
| 启动与 child 权限 | 5 | 决策 8 | pass |
| 规模、成本、模型路由 | 5 | guideline/limits/usage 与决策 5 | R1-C6 |
| 错误可定位且不破坏主会话 | 3 | compiler errors、journal/snapshot、terminal diagnostics | pass |
| Q1 原话“都支持” | — | CLI/Web/飞书分两纵向 milestone，语义共用 SDK/runtime | pass |
| Q2 原话“不要做额外多余…就抄 claude code” | — | 绝大部分只做 Python/产品入口必要适配；symlink 规则是未被允许的偏离 | R1-C5 |
| Q3 完整 Claude Workflow 能力 | — | primitives、后台、保存、控制、resume、权限、规模/模型均在范围 | pass（受上述承重问题阻断） |
| Q4 disabled 时 model-facing 内容和入口全部移除 | — | 单一 active-tool switch、同源命令发现、next-turn A/B 测试明确 | pass |
| 非目标 | — | 不支持 JS/TS、不新增资格/权限体系、不含 cloud routines/hooks/agent teams | pass |

### Delta-spec 台账

| Target | 逐条核对 | 结果 |
|---|---|---|
| `kernel/workflows.md` | 8 条：能力开关；受限 Python；primitives；child Agent；运行查询控制；prefix resume；保存发现；预算规模 | consumer/SDK 视角基本正确；resume/symlink/model 受 R1-C1/C5/C6 影响 |
| `kernel/background-tasks.md` | 1 条：WORKFLOW task、cooperative stop、一次通知（3 scenarios） | pass |
| `kernel/runs.md` | 1 条：human/automatic/workflow origin（3 scenarios） | 新条目合理，但遗漏修改 canonical USER 场景，R1-C4 |
| `kernel/sdk-boundary.md` | 1 条：SDK 查询/控制/保存（3 scenarios） | 新 consumer 契约合理，但遗漏修改既有 build/method-set 条目，R1-C3 |
| `kernel/spec.md` | 新 Workflows area 索引，8 requirements | pass |
| `cli/interactive-repl.md` | MODIFIED command requirement；ADDED opt-in/ultracode；ADDED background control（15 scenarios） | MODIFIED 标题不是 canonical 精确锚点，R1-C2 |
| `gateway/agent-capabilities.md` | optional/default-off Workflow、保存开关/guideline/next-turn（5 scenarios） | 用户可观察且与既有真 allowlist 条目可并存，pass |
| `gateway/workflows.md` | 5 条：跨入口来源；prompt/command switch；state projection；permission route；delivery cadence（14 scenarios） | Gateway/IM consumer 可观察，pass |
| `gateway/spec.md` | 新 Workflows area 索引，5 requirements | pass |
| `im/agents-nodes.md` | 单一 Workflow tool selection、guideline 与 next-turn（5 scenarios） | 用户视角，pass |
| `im/workflows.md` | 5 条：持久状态；控制；launch approval；command switch；desktop/mobile（17 scenarios） | 用户视角，pass |
| `im/spec.md` | 新 Workflows area 索引，5 requirements | pass |

### Milestone 台账

| Milestone | 纵向性 / 范围 / 依赖 | 退出标准 | 结果 |
|---|---|---|---|
| `M1-cli-workflow-runtime` | 从 opt-in、批准、Python runtime/child/background 到 CLI 状态/控制/保存/通知，可独立交付；承担共享 SDK/runtime 是合理前置 | pure/unit/contract、CLI integration、provider A/B、Luna lifecycle 与 resume/notification journey 可验 | pass，但未标两轨，R1-W2 |
| `M2-assistant-workflow-surfaces` | 经 M1 稳定 SDK 把同一能力纵向接到 PA/Gateway/IM/Web/飞书；不是 backend/frontend 横切，和 M1 无并行 worktree 承诺 | backend/protocol/frontend、隔离真栈、mobile、飞书、disabled A/B、cleanup 均可验 | pass，但未标两轨，R1-W2 |

拆分举证充分：设计明确跨 core/platform/sdk、CLI、Gateway、IM backend/frontend 与 Feishu，超过单 worker 的 LOC/file/time 窗口；M2 依赖 M1 稳定 SDK，故是有序纵向分阶段而不是伪并行。

### 架构进攻

| 角度 | 进攻结果 |
|---|---|
| 归属 | Workflow policy/primitives/journal 在 core，child/permission/background/worktree adapter 在 platform，公开 query/control 在 SDK，产品只做 selection/projection/presentation；符合 `platform → core` 与产品只 import SDK 的红线。未发现反向依赖。 |
| 该不该存在 | 单一 manager 是并发槽、journal、resume、stop 的必要一致性 owner；complete snapshot/projection 是跨 Gateway/IM 恢复所需；design 明确不造通用 plugin manager。未发现只为假想多态新增的空层。 |
| 深还是浅 | 复用 `RuntimeRunner`、permission broker、background registry、session storage、slash/allowlist 接缝，新增 Workflow adapter 隐藏了编译/状态/恢复复杂度，接口显著窄于实现。model-env seam 未真正存在，形成 R1-C6。 |
| 治本还是补丁 | active tool 作为 schema/prompt/command 的共同真源、journal 单一终态、cooperative stop、revisioned snapshot 都在解决根因而非 UI 藏入口；未见硬编码旁路。symlink 自创规则会把 baseline 偏差固化到 canonical，形成 R1-C5。 |

### Issues

- [R1-C1][CRITICAL] [决策 4 / 决策 7 / 风险表 `design.md:203-230,281-293,500`]: 设计把 resume 次序定义为“每个实际 `agent()` 开始时由 manager 分配 ordinal”，同时允许 `parallel()`/`pipeline()` 并发启动，却没有规定并发 effect 在进入 task/semaphore 前如何取得稳定且可重放的 ordinal。现有研究还明确把“并发 effect ordinal”列为未建立事实（`Claude Code Dynamic Workflows 运行机制.md:282,417`）；官方只承诺按 agents started 的顺序 replay。不同 worker 可以分别实现为 coroutine 到达顺序、semaphore dispatch 顺序或 input/stage 预分配顺序，它们都符合当前文字但互不兼容。不修会使相同 Python script/args 在 fan-out resume 时无法兑现 spec 的 100% prefix hit，甚至同一 journal 在实现调整后改变 cut-off。设计必须在继续声称等价前补上游最小取证，或明确拍板一条可重复的 Python ordinal 分配契约（含 `parallel` 输入顺序、`pipeline` item/stage、nested workflow）并把 journal/test oracle 对齐。
- [R1-C2][CRITICAL] [CLI delta `specs/cli/interactive-repl.md:3-26`]: `MODIFIED` 标题写成“REPL 提供固定斜杠命令管理会话、上下文与 Workflow”，但 canonical 精确标题是“REPL 提供固定一组斜杠命令管理会话与上下文”（`docs/specs/cli/interactive-repl.md:34`）。delta 归并规则按同名 Requirement 替换；当前写法无法命中旧条目。不修会在归并后留下新旧两条 slash-command 契约，且旧正文/Scenario 不能被可靠保留或替换。应使用 canonical 原标题，写出含原全部语义和 Workflow 增量的完整 MODIFIED 条目。
- [R1-C3][CRITICAL] [SDK delta `specs/kernel/sdk-boundary.md:3-19` / 决策 10、12]: 设计新增 `build_kernel(workflow_search_roots=...)` 和五个 `Kernel` 方法，但 delta 只 ADDED 一个平行 Workflow Requirement，没有 MODIFIED canonical “装配与会话分两层,内核产品中立”。该 canonical 在 `docs/specs/kernel/sdk-boundary.md:51-60` 穷举 `build_kernel` 签名，并在 `:77-79` 穷举稳定方法集。不修会使归并后的 canonical 同时声称旧签名/旧方法集与新 Workflow SDK，消费者和 contract test 无法对账。应精确 MODIFIED 该既有 Requirement，忠实保留原全部 Scenario，并把 search root 与新方法并入完整条目；Workflow consumer 细节可继续保留为 ADDED。
- [R1-C4][CRITICAL] [Runs delta `specs/kernel/runs.md:3-21` / 决策 9]: 新 delta 引入可信 `human` origin，但没有修改 canonical `docs/specs/kernel/runs.md:64-67` 中“用户消息为 USER”的既有契约。设计又规定 interactive CLI/Web/外部 IM 应改为 `HUMAN`，普通 SDK 才保持普通 user；归并后两条规则直接冲突。不修时 steer 失败转交、队列重放等路径可能把真实人工输入降为 USER，导致 `ultracode` reminder 在这些路径时有时无。应 MODIFIED 含该 Scenario 的既有 Requirement（完整保留其余 steer 语义），明确 HUMAN/USER 都按原始注入来源保持。
- [R1-C5][CRITICAL] [决策 10 `design.md:327-338` / kernel delta `specs/kernel/workflows.md:145-163`]: symlink 规则不是 Claude Code 当前契约的机械移植。官方文档明确：project save 在 `.claude`、`.claude/workflows` 或目标文件任一为 symlink 时拒绝；personal save 只拒绝目标文件 symlink，允许 dotfiles 工具管理的 `~/.claude` 目录 symlink。设计却按“是否越出 scope”统一处理目录 symlink，并把同一规则扩到 discovery。它会错误允许部分 project symlink、拒绝官方允许的 personal config-dir symlink，还新增未取证的 discovery 行为，违反 Q2“除 Python 外就抄 Claude Code”。应逐 scope 写出官方不对称 save 规则；discovery 若无证据，不新增拒绝语义。证据：[Claude Code Dynamic Workflows — Save the workflow for reuse](https://code.claude.com/docs/en/workflows#save-the-workflow-for-reuse)（2026-08-09 核实）。
- [R1-C6][CRITICAL] [决策 5 `design.md:232-242` / 模型路由 `:408-415` / runbook `:521-534`]: “已有环境模型 override 最终优先”在本仓不是现状。搜索仅得到 `NANO_MULTIAGENT_LLM_MODEL`，它构造进程基座/default（`src/agent/sdk/dto.py:145-173`），而当前 runtime 是 `model_override or self._model`，显式 per-run model 反而优先；本仓没有等价于 `CLAUDE_CODE_SUBAGENT_MODEL` 的 workflow-child override。runbook 导出的 `CLAUDE_CODE_SUBAGENT_MODEL` 也不会被本仓读取。不修会迫使 worker猜测是误用全局 default（从而压掉脚本 stage routing）、新增哪个 public env/config，还是忽略 upstream precedence；三种实现互不兼容，模型路由 Scenario 与真实 Luna E2E 都无法可信验收。设计必须定义 nano 的专用配置名、解析/优先级、CLI/PA 适用范围和 substitution warning，或明确删除该 baseline 能力并回到 Gate 1 对齐（后者与当前 spec 冲突）。
- [R1-W1][WARNING] [现状事实 / 决策 9 `design.md:27-39,315-325`]: 两段 reminder 的逐字文本正确，但“turn attachment/reminder”没有固定 provider role 与相对顺序。实 capture 是 human user message 后追加独立 `role="system"` message；本仓当前 loop 则默认组装单个 leading system message（`src/agent/core/agent/loop.py:371-380`）。worker 可以把文本并入 leading system、拼进 user text，或追加 synthetic system message，都会满足当前措辞但 provider payload、prompt cache 前缀和行为不等价。不修会使“exact provider prompt evidence”只复刻文本而没复刻放置语义。应在 provider-independent message model 和最终 mapper payload 两层固定 role/order，并为 active/inactive、keyword/standing 双分支做 request golden。
- [R1-W2][WARNING] [Milestones `design.md:565-574`]: 两个 milestone 都是合格纵向切片，也都有产品旅程与实现验证，但退出标准没有按 skill 约定逐项标 `[reviewer]` / `[worker]`。不修不会改变架构，却会让 orchestrator 无法机械区分谁举证真实用户旅程、谁举证 pure/contract/provider seam，增加验收漏项或重复派发风险。应保留现有两行切片，只把每项退出标准拆成并标注两轨，不下沉成 tasks.md。

### Recommendations

- [R1-R1] 修订后用 `delta` mode 做 Round 2：重查 R1-C1/C5/C6 的上游等价性与实现 seam，逐一模拟 R1-C2/C3/C4 的 canonical 归并结果，并复核 R1-W1/W2；无需重审未受影响的 prototype 视觉细节。
- [R1-R2] 保持现有 M1→M2 有序纵向切片和空 milestone 骨架；本轮没有要求新增 milestone 或预填 `tasks.md`。

### Author Resolutions

- [R1-C1] Accepted：把 Python 端的 `agent()` 次序定义为 manager 串行 admission ordinal；`parallel` 在创建并发任务前按输入顺序 admission，`pipeline` 的首 stage 按 item index admission，后续 stage 按上一 stage 的 journal completion 顺序 admission，同一批完成以 item index 破平；nested Workflow 复用父 run 的同一全局 ordinal。恢复时 cached completion 按原 journal completion ordinal 释放，确保下游 admission 重现原 run。
- [R1-C2] Accepted：MODIFIED 标题恢复 canonical 原文，并完整保留已有四个 Scenario 后加入 Workflow 命令语义。
- [R1-C3] Accepted：补充 canonical `装配与会话分两层,内核产品中立` 的完整 MODIFIED 条目，将 `workflow_search_roots`、`workflow_subagent_model` 和五个 Workflow 方法纳入穷举表面；原有 Scenario 全部保留。
- [R1-C4] Accepted：补充 canonical steer Requirement 的完整 MODIFIED 条目；异常转交保持原始 `HUMAN` / `USER` / automation origin，不再把所有用户文本统一写成 `USER`。
- [R1-C5] Accepted：删除自创的 discovery symlink 限制；project save 严格拒绝 config dir、workflows dir 或目标文件任一 symlink，personal save 仅拒绝目标文件 symlink，允许 personal config/workflows 目录由 dotfiles symlink 管理。
- [R1-C6] Accepted：新增 nano 公共装配参数 `workflow_subagent_model`，CLI/PA 都从 `NANO_MULTIAGENT_WORKFLOW_SUBAGENT_MODEL` 解析；优先级为该进程 override > `agent(model=...)` > parent resolved model。requested model 不在 catalog 时替换为 parent resolved model并产生一次可见 warning，不把 Claude Code 专用环境变量误写成可用配置。
- [R1-W1] Accepted：新增 provider-independent `turn_system` message kind；它在当前 human message 后作为独立尾部 system message，mapper 保留该 role/order，不并入 leading system 或 user text。active/inactive、keyword/standing 各有最终请求 golden。
- [R1-W2] Accepted：保留两个纵向 milestone，只把退出标准拆为 `[worker]` 自动/接缝证据与 `[reviewer]` 真实产品旅程证据。

## Round 2

### Metadata

- reviewer: `/root/feat_517_design_reviewer`
- review_mode: `delta`
- mode_reason: R1 后的修订语义有界：并发 admission/replay、三处 canonical MODIFIED、save symlink、child model override、provider reminder placement 与 milestone 两轨；需求范围、核心分层、三入口数据流和 milestone 切片未变化。本轮复用 R1 full inventory，只重查 8 个历史项、受影响 delta 的真实归并结果及相关架构角度。
- started_at: `2026-08-09T01:40:00+08:00`
- completed_at: `2026-08-09T01:43:09+08:00`
- duration: `3m09s`

### Verdict

Issues Found — 1 CRITICAL / 1 WARNING

### Coverage

- changed_atoms: 决策 4/5/7/9/10/12、模型路由与 runbook、kernel workflows/runs/sdk delta、CLI command delta、kernel/gateway/IM package index delta、M1/M2 exit criteria。
- merge_simulation: 对 CLI、SDK Boundary、Runs 三个 MODIFIED Requirement 逐一核对精确标题与原 Scenario 子集；再按 canonical 当前计数 + 全部 ADDED Requirement 计算四包归并后 `Canonical Areas` 派生数量。
- retained_from: Round 1 — spec 范围、其余现状断言/决策/delta、prototype、三入口架构与 milestone 纵向切片未被本轮修订改变，R1 对应证据仍有效。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | manager 同步 admission；parallel/pipeline/nested 的 start/terminal ordinal 与 replay oracle | `design.md:233-241,292-304` 与 `specs/kernel/workflows.md:51-80,141-160` 已固定：`AgentCall` 在任何 await/semaphore 前取得全局 start ordinal；pipeline 后续按 journal terminal 顺序、同批 item index 破平；cache 按旧 terminal ordinal 释放。不同 worker 不再能用 coroutine 抢占顺序替代契约 | closed |
| R1-C2 | CLI 恢复 canonical 精确 MODIFIED | delta 标题与 `docs/specs/cli/interactive-repl.md:34` 逐字一致；canonical 原 4 个 Scenario 全部保留，并平行加入 `/workflows` Scenario | closed |
| R1-C3 | SDK 完整 MODIFIED build/method-set | `specs/kernel/sdk-boundary.md:5-60` 精确命中 canonical；原 7 个 Scenario 全保留，`workflow_search_roots`、`workflow_subagent_model`、五个 Kernel 方法与新模型 Scenario 均进入完整条目 | closed |
| R1-C4 | Runs 完整 MODIFIED steer origin | `specs/kernel/runs.md:5-38` 精确命中 canonical；原 6 个 Scenario 全保留，异常转交明确保持 HUMAN/USER/automation 原来源 | closed |
| R1-C5 | 严格采用 project/personal 不对称 save symlink | `design.md:340-350` 与 `specs/kernel/workflows.md:162-185` 已分别固定 project 三层拒绝、personal 只拒绝 target；discovery 不再增加 symlink 拒绝，且补齐沿 cwd→git root 的全部 project discovery | closed |
| R1-C6 | 新建 nano build-scoped child model override | `design.md:378,424-432,539-552` 与 SDK/workflows delta 已固定 `NANO_MULTIAGENT_WORKFLOW_SUBAGENT_MODEL` → `workflow_subagent_model`，优先级、catalog fallback 和一次 requested/resolved warning；不再引用 Claude 专用变量或误用全局 parent default | closed |
| R1-W1 | `turn_system` 独立尾部 system message + 四态 golden | `design.md:326-336` 与 kernel delta `:25-29` 固定 provider-independent kind、human 后相对顺序、mapper 最终 `role=system`、双 reminder 顺序及 inactive/active/keyword/standing golden | closed |
| R1-W2 | milestone exit criteria 标两轨 | `design.md:586-593` 两个 milestone 均含可验 `[worker]` seam/自动证据和 `[reviewer]` 真实产品旅程证据，纵向范围与依赖未改变 | closed |

### 本轮核实台账

| Changed atom / 波及链 | 独立核实 | 结果 |
|---|---|---|
| 并发 ordinal → journal → prefix replay | 同步 admission 与 terminal replay 都由 manager 单一 owner；delta 同时把开始/释放顺序变成 SDK consumer 可观察契约 | pass |
| provider `turn_system` → Anthropic/OpenAI mapper | 当前 `LLMMessage.role` 为可扩展 string（`src/agent/core/llm/interfaces.py:20-29`）；mapper 是唯一 provider 出口，新 kind 可在此映射且 golden 锁最终 payload | pass |
| build-scoped child model → CLI/PA/外部 SDK | 公共参数归 SDK 装配，产品 factory 只解析环境并传值，未引入产品→core/platform 依赖 | pass |
| CLI MODIFIED merge | 精确标题；4/4 旧 Scenario 保留；新增 Scenario 不覆盖旧语义 | pass |
| SDK MODIFIED merge | 精确标题；7/7 旧 Scenario 保留；build signature/method set 与新增 ADDED Workflow consumer 条目一致 | pass |
| Runs MODIFIED merge | 精确标题；6/6 旧 Scenario 保留；origin 转交与新增 human-origin Requirement 一致 | pass |
| Canonical Areas merge | future counts：CLI Interactive REPL `7+2=9`；kernel Background Tasks `4+1=5`、Runs `12+1=13`、SDK Boundary `5+1=6`、Workflows `8`；gateway Agent Capabilities `10+1=11`、Workflows `5`；IM Agents and Nodes `20+1=21`、Workflows `5` | R2-C1 |
| reviewer static runbook | 实际执行 `PYTHON=.venv/bin/python; $PYTHON scripts/docs-check` 会让 Python 解析 bash wrapper，在 `set -euo pipefail` 报 `SyntaxError`；真实入口要求 `PYTHON="$PYTHON" ./scripts/docs-check` | R2-W1 |

### 架构进攻（受影响角度）

| 角度 | 重查结果 |
|---|---|
| 归属 | admission/replay 仍集中在 Workflow manager；child override 属于 SDK build scope、环境读取留在产品 factory；`turn_system` 由 provider-independent message 表达、provider mapper 落最终协议。依赖方向正确，无新增反向依赖。 |
| 该不该存在 / 深浅 | admission coordinator 隐藏并发/恢复的必要确定性，`turn_system` 区分 leading system 与 mid-conversation system，build 参数对应真实进程级配置；三者都有独立契约价值，不是单实现的空包装。 |
| 治本还是补丁 | symlink 按 scope 精确复刻上游而非统一“安全”特例；model override 不再借全局 default 冒充；三处 MODIFIED 正面修 canonical 冲突。历史问题均属治本修订。新的 index 计数遗漏仍会在收尾制造机械契约失败，见 R2-C1。 |

### Issues

- [R2-C1][CRITICAL] [delta package indexes: `specs/{cli,kernel,gateway,im}/spec.md`]: 三份现有 package-index delta 只列新 Workflows area，且 CLI 完全没有 `specs/cli/spec.md` delta；它们没有更新被 ADDED Requirement 改变的既有 area 派生计数。按当前 canonical 与本 unit delta 归并后，必须得到 CLI Interactive REPL 9；kernel SDK Boundary 6、Runs 13、Background Tasks 5、Workflows 8；Gateway Agent Capabilities 11、Workflows 5；IM Agents and Nodes 21、Workflows 5。当前 delta 只提供三个 Workflows row，无法生成其余变化，CLI row 连入口都没有。不修会使 canonical 归并后立即违反 `docs/specs/CONTRIBUTING.md:99`，`scripts/docs-check` 机械报 Requirement count mismatch，change unit 无法完成规范归并。应新增 CLI index delta，并在四包 index delta 中列出每个实际变化的 area row 及归并后准确数量；未变化 row 不必复制。
- [R2-W1][WARNING] [Reviewer runbook `design.md:528-536`]: 静态命令把 bash wrapper 当 Python 文件执行：`$PYTHON scripts/docs-check` 已实测在 wrapper 的 `set -euo pipefail` 处报 `SyntaxError`。不修会让 reviewer 按设计操作时得到假的文档门禁失败并中断验收。应改为 `PYTHON="$PYTHON" ./scripts/docs-check`（或直接调用 `scripts/docs_check.py`，二选一拍死）。

### Recommendations

- [R2-R1] 作者只需修 R2-C1/W1 后再请求 `closure` Round 3；历史 R1-C1..C6/W1/W2 已有直接证据关闭，无需再次改动或重审。

### Author Resolutions

- [R2-C1] Accepted：新增 CLI package-index delta，并把四包所有发生变化的 area 更新为归并后计数：CLI Interactive REPL 9；kernel SDK Boundary 6、Runs 13、Background Tasks 5、Workflows 8；Gateway Agent Capabilities 11、Workflows 5；IM Agents and Nodes 21、Workflows 5。
- [R2-W1] Accepted：runbook 改为 `PYTHON="$PYTHON" ./scripts/docs-check`，按 shell wrapper 的真实调用契约执行。

## Round 3

### Metadata

- reviewer: `/root/feat_517_design_reviewer`
- review_mode: `closure`
- mode_reason: R2 后只修正 package-index delta 的机械归并计数与 reviewer runbook 命令，没有改变需求、架构、接口、数据流或 milestone 语义；影响边界完全封闭。
- started_at: `2026-08-09T01:45:18+08:00`
- completed_at: `2026-08-09T01:45:51+08:00`
- duration: `33s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1..C6 / R1-W1..W2 | 已在 Round 2 以修订后的设计、delta、上游/本仓证据逐项关闭 | 本轮只新增 index rows/counts、delta 清单链接与 runbook 命令；`design.md` 的 ordinal、model override、reminder、symlink、SDK/origin、milestone 语义未再变化，Round 2 的 closure 证据仍有效 | closed |
| R2-C1 | 新增 `specs/cli/spec.md`，四包 index delta 写入全部变化 area 的 future counts | 逐份重算：CLI Interactive REPL `7 + 2 ADDED = 9`；kernel SDK Boundary `5+1=6`、Runs `12+1=13`、Background Tasks `4+1=5`、Workflows `8`；Gateway Agent Capabilities `10+1=11`、Workflows `5`；IM Agents and Nodes `20+1=21`、Workflows `5`。四份 delta `spec.md` 的 rows/counts 全部一致，`design.md:485-490` 也已列 CLI index target | closed |
| R2-W1 | runbook 改按 shell wrapper 契约传递 `PYTHON` | 原样执行 `PYTHON=.venv/bin/python; PYTHON="$PYTHON" ./scripts/docs-check` 成功，输出 `documentation integrity passed: 223 maintained Markdown sources, 66 required routes`；不再由 Python 解析 bash wrapper | closed |

### Issues

- None.

### Recommendations

- [R3-R1] Gate 2 已通过，可进入 `change-orchestrator`；实现与验收按 M1→M2 的 `[worker]` / `[reviewer]` 两轨执行。

## Round 4

### Metadata

- reviewer: `/root/feat_517_design_reviewer`
- review_mode: `delta`
- mode_reason: 用户最终设计 review 只改变 Web Agent 设置的呈现与 guideline 配置入口：旧 checkbox/card 改为 current `PillSelector`，移除可见说明、独立 Workflow 开关和卡内 guideline，并把 PA guideline 契约收敛到 `/config`。需求范围、Workflow runtime、跨包架构、SDK/protocol 主干和 M1→M2 切片未变化，影响边界可枚举。
- started_at: `2026-08-09T02:39:31+08:00`
- completed_at: `2026-08-09T02:42:22+08:00`
- duration: `2m51s`

### Verdict

Approved — 0 CRITICAL / 1 WARNING

### Coverage

- changed_atoms: Web Agent detail 的工具选择 current fact、`prototype.html` 的 selected/deselected 交互、PA guideline 配置入口、gateway `agent-capabilities`/`workflows` delta、IM `agents-nodes`/package-index delta、M2 prototype must-match 与 reviewer journey。
- current_source_check: `agent-detail-page.tsx:1844-1866` 直接渲染 `PillSelector`；`pill-selector.tsx:59-86` 以 `button[aria-pressed]` 平铺 pill，正文只渲染 `opt.name`，description 只进入原生 `title`。
- retained_from: Round 3 — Python runtime、admission/replay、prompt placement、权限、模型路由、SDK/relay、保存发现、其余 delta 和 milestone 纵向结构均未被本轮 UI/config 修订触碰，Round 2/3 的核实证据仍有效。

### 历史问题闭环

| 历史项 | 本轮核实 | 状态 |
|---|---|---|
| R1-C1..C6 / R1-W1..W2 | 本轮只改 Agent 设置呈现和 guideline 的产品入口；ordinal、canonical MODIFIED、save symlink、model override、provider reminder 与 milestone 两轨原文未变 | closed |
| R2-C1 | `agents-nodes` 仍只新增 1 条 Requirement，删除的是其中 2 个旧 Scenario；归并后 IM Agents and Nodes 仍为 21。Gateway Agent Capabilities 仍新增 1 条 Requirement、Workflows 仍新增 5 条，既有 index future counts 不变 | closed |
| R2-W1 | reviewer runbook 仍为 `PYTHON="$PYTHON" ./scripts/docs-check`，本轮未回退调用方式 | closed |

### 本轮核实台账

| Changed atom / 波及链 | 独立核实 | 结果 |
|---|---|---|
| current Agent detail → prototype | 生产 detail 使用紧凑 `PillSelector`，选中真值来自 `tool_allowlist`；原型工具行只含 `read`、`agent`、`Workflow` 名称，Workflow 以同一 pill 的 `aria-pressed` 切换，无 header 二次开关、checkbox grid、说明行或嵌套设置 | pass |
| Agent tool single source → design / IM delta | `design.md:447,469,479` 与 `specs/im/agents-nodes.md:5-19` 均把现有 Workflow pill 写成 Agent 页唯一能力选择，并保留保存后 next-turn 生效/取消后完整移除语义 | pass |
| guideline → PA/CLI config command | `design.md:425-431` 明确 PA 只经 `/config workflowSizeGuideline <value>` 修改保存值、Web Agent 设置不提供控件；Gateway delta `workflows.md:34-38` 承担用户可观察配置契约，IM slash delta已有 active 时 config discovery，CLI delta也保留同形入口 | pass |
| delta 归属与归并计数 | Agent tool 可选/默认关闭留在 gateway Agent Capabilities；guideline 移到 Gateway Workflows；IM Agents and Nodes 只描述 pill 呈现。均为语义最窄 target，Requirement 数未因 Scenario 移动而变化 | pass |
| prototype must-match → M2 验收 | must-match 已改为“现有工具 pill 行里的 Workflow”，覆盖 desktop/mobile 与 selected/deselected；M2 reviewer 仍要求隔离真栈验证 tool selection next-turn A/B 和 desktop/mobile，未遗留旧 guideline 表单验收 | pass |

### 架构进攻（受影响角度）

| 角度 | 重查结果 |
|---|---|
| 归属 | Agent 页只写既有 `tool_allowlist`；PA runtime config 保存 guideline，Gateway command 修改，IM 只发现/转交命令。没有把 Agent runtime 配置真源复制到浏览器，也没有引入 IM→agent 依赖。 |
| 该不该存在 / 深浅 | 删除 Workflow 专属 card、feature toggle 与嵌套 guideline 后，UI 复用现有窄 pill seam；配置仍由同形 `/config` 入口承载，没有为单字段创建新的表单或前端状态层。 |
| 治本还是补丁 | `Workflow in tool_allowlist` 继续统一控制 tool/prompt/commands，修订消除了第二开关和卡内配置造成的双真源风险。唯一残留是现状表中的旧组件 locator，见 R4-W1。 |

### Issues

- [R4-W1][WARNING] [本仓当前接缝 `design.md:53`]: 现状表仍把 Agent allowlist 的代码入口写成 `allowlist-selector.tsx`，但当前 Agent detail 的生产路径实际在 `agent-detail-page.tsx:1844-1866` 渲染 `PillSelector`；`allowlist-selector.tsx` 是旧 checkbox/card 实现，当前 production source 没有 import。后面的 UX grounding、prototype 和 delta 已明确禁止旧 grid，所以这不再造成架构两解；但 worker 若从“当前接缝”表选改动入口，会扩展一个未消费的旧组件，或者把已删除的 checkbox/card 重新带回，最终在 M2 真浏览器验收才暴露。应把该行 locator 改成 `pill-selector.tsx` + `agent-detail-page.tsx`，并把结论中的 allowlist 组件语言明确为 tool pill 行。

### Recommendations

- [R4-R1] Gate 2 仍可进入 `change-orchestrator`；实施派发前先收掉 R4-W1 这一处 stale locator，随后按 M2 must-match 直接复用 `PillSelector`，不要修改或复活 `AllowlistSelector`。

### Author Resolutions

- [R4-W1] Accepted：将“本仓当前接缝”的旧 `allowlist-selector.tsx` locator 改为 production 实际消费的 `agents/pill-selector.tsx` 与 `agents/agent-detail-page.tsx`，并明确 M2 复用现有 tool pill 行、不得复活 checkbox/card allowlist。

## Round 5

### Metadata

- reviewer: `/root/feat_517_design_reviewer`
- review_mode: `closure`
- mode_reason: R4 后只修正一处 current-source locator 和对应消歧措辞；没有改变需求、架构、接口、数据流、delta-spec 或 milestone 语义，影响边界完全封闭。
- started_at: `2026-08-09T02:44:33+08:00`
- completed_at: `2026-08-09T02:44:44+08:00`
- duration: `11s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R4-W1 | current seam 改为 production 实际消费的 `agents/pill-selector.tsx` + `agents/agent-detail-page.tsx`，并明确不得复活 checkbox/card allowlist | `agent-detail-page.tsx:19,1844-1866` 确实 import 并渲染 `PillSelector`；`pill-selector.tsx:59-86` 确实以 tool pill button/`aria-pressed` 呈现名称。`design.md:53` 现在列出这两个真实入口，结论也明确复用 tool pill 行和禁止恢复旧 allowlist，worker 不再会被导向 dormant `AllowlistSelector` | closed |

### Issues

- None.

### Recommendations

- [R5-R1] Gate 2 已完整收口，可放心进入 `change-orchestrator`；M2 直接沿 production `PillSelector` seam 实施并按既有 must-match 契约验收。

## Round 6

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- prior_reviewer: `/root/feat_517_design_reviewer`
- failover_reason: 历史 reviewer target `/root/feat_517_design_reviewer` 已不在当前 agent tree，客观不可恢复；本轮由替代 target `/root/feat_517_design_reviewer_failover` 独立接管，未复用旧 target 的运行态或未提交判断。
- review_mode: `full`
- mode_reason: reviewer failover 按规则强制 full；同时当前 canonical specs/source 已在 Round 5 后继续演进，且用户最新确认删除 prototype、没有新前端设计、Gateway `/workflows` 改为直接查询 SDK 真源并禁止 IM run projection/event/专属 UI，必须重新完整核对 spec、design、13 份 delta、两个 milestone、历史 review、当前 canonical 与真实生产路径。
- started_at: `2026-08-10T08:20:08+08:00`
- completed_at: `2026-08-10T08:32:43+08:00`
- duration: `12m35s`

### Verdict

Issues Found — 4 CRITICAL / 1 WARNING

### Coverage

| 输入 | 覆盖结果 |
|---|---|
| `spec.md` | 4 条用户澄清、10 个 Requirement、46 个 Scenario、范围与非目标全部重读并映射到设计、delta 与 milestone |
| `design.md` | 现状、架构总览、决策 1–12、接口/数据流、三产品入口、测试、风险/回退、runbook、M1/M2 全量核对 |
| delta-spec | CLI 2 份、kernel 5 份、Gateway 3 份、IM 3 份全部读取；对 3 个 MODIFIED Requirement 做 current canonical 归并核对，并重算四包变化 area 的 future counts |
| milestone | `M1-cli-workflow-runtime/.gitkeep`、`M2-assistant-workflow-surfaces/.gitkeep` 均存在；按设计逐项检查纵向目标、依赖、worker/reviewer 退出标准和跨 milestone seam；空骨架符合当前阶段约定 |
| 历史 review | Round 1–5、全部 Issue/Resolution/closure 完整读取；旧结论只作为历史证据，因 failover 未采用 delta/closure 捷径 |
| frontend/prototype | 已确认 `prototype.html` 删除；设计明确“不产出前端原型”，并逐一落到 production `PillSelector`、`SlashPicker`、`PermissionCard`、`ToolCallsPanel` 与普通消息，不要求新组件或 prototype must-match |
| current canonical | 完整重读 CLI Interactive REPL、kernel Background Tasks/Runs/SDK Boundary、Gateway Agent Capabilities、IM Agents and Nodes 及四包 index；按需核对 Web Chat UX、Tool Timeline、Gateway Relay 等既有 surface 契约 |
| current source | 核对 active-tool/session projection、SDK composition、child runtime、permission broker/event、background registry/notifier/task_stop、Gateway foreground/background delivery、command parser，以及上述四个 production React surface |
| 静态文档门禁 | 原样执行 `PYTHON=.venv/bin/python; PYTHON="$PYTHON" ./scripts/docs-check`，通过：`documentation integrity passed: 226 maintained Markdown sources, 67 required routes`；该命令只检查当前 canonical，不会模拟本 unit delta 归并，故不否定 R6-C1/C2 |

### 历史问题闭环

| 历史项 | 本轮 full 核实 | 状态 |
|---|---|---|
| R1-C1 / C4 / C5 / C6 / W1 / W2 | admission/replay ordinal、HUMAN origin、save symlink、child model override、`turn_system` placement、milestone 两轨仍在 design/delta 中保持 Round 2 的已接受语义 | closed |
| R1-C2 | CLI delta 仍精确命中 canonical `REPL 提供固定一组斜杠命令管理会话与上下文`，并完整保留 current 原 Scenario 后增加 Workflow 语义 | closed |
| R1-C3 | SDK delta 仍有精确 MODIFIED 标题和 Workflow 方法，但 current canonical 后续新增的 `global_config_root`/workspace-config 条款没有被带入完整替换体；这是基线漂移产生的新问题，记为 R6-C1，不把旧 reviewer 当时基于旧基线的 closure 倒写为错误 | superseded by R6-C1 |
| R2-C1 | 四包 index delta 仍存在；但 current kernel Background Tasks 与 IM Agents and Nodes 均各新增了一个 canonical Requirement，旧 future count 已过期，记为 R6-C2 | superseded by R6-C2 |
| R2-W1 | reviewer runbook 仍按 shell wrapper 的真实调用方式执行，本轮实测通过 | closed |
| R4-W1 | current seam 仍指向 production `pill-selector.tsx` + `agent-detail-page.tsx`，未回退 dormant checkbox/card allowlist | closed |
| R3/R5 Gate 结论 | 当时输入范围内已闭合；本轮因 reviewer failover、设计/前端契约修订和 current baseline 漂移重新 full review，不沿用旧 Approved 作为当前 Gate 2 结论 | replaced by Round 6 verdict |

### 现状与证据台账

| 原子 | 独立核实 | 结论 |
|---|---|---|
| Agent tool allowlist 是下一轮完整运行配置真源 | `src/personal_assistant/product.py:354-370`；`gateway/session_composition.py:39-75`；production Agent detail 在 `agent-detail-page.tsx:1844-1866` 渲染 `PillSelector` | 成立；Workflow optional/default-off pill 可作为 model-facing tool/prompt/command 的统一开关 |
| Web 现有 surface 足以承载本功能 | `slash-picker.tsx:37`、`permission-card.tsx:78`、`tool-calls-panel.tsx:71`、`message-pane.tsx:1458-1477` 是真实消费路径 | 成立；用户确认无新视觉设计后删除 prototype 是一致收敛，不是缺件 |
| Gateway 当前命令 owner 只有既有 control | `gateway/inbound_pipeline.py:285-374` 只专门解析 `/stop`、`/new`、`/compact`；其他输入进入普通 Agent 路径 | 成立；M2 需要在该既有 owner 增加 active-tool gated `/workflows`/saved config 命令，并直接调 SDK，不能靠 IM projection |
| SDK 当前公共 build seam 已演进 | `src/agent/sdk/kernel.py:230-249` 已含 `global_config_root`；canonical `sdk-boundary.md:47-104` 还固定动态 `workspace_config_dirname`、验证、global root 有/无两场景 | 成立；unit MODIFIED 仍是较旧完整替换体，见 R6-C1 |
| child 权限事件默认属于 child run/session publisher | `runtime.py:1286-1483` 的 requester 捕获当前 runtime 的 `session_event_publisher` 并发出 request/resolved；现有 auxiliary runner 打开 child session（`runtime_runner.py:140-171`） | 成立；不会自动出现在已经结束的 parent foreground stream |
| PA foreground observer 能呈现权限，但只活在当前 run stream | `session_run_coordinator.py:1490-1531` 在消费当前 `run_id` 时调用 observer；`observer.py:1633-1700` 把 generic request/resolved 送 Web/外部 channel | 成立；async launch 后 child 后续请求需要明确的 long-lived parent bridge，见 R6-C3 |
| PA background subscriber 是可复用长连接，但当前不转发权限 | `background_session_events.py:25-33` 的 filter 只有 `self_evolution_review`；BACKGROUND_TASK 只特判 terminal assistant message | 成立；可扩展既有 generic event bridge，不需要也不允许新增 Workflow run projection/event，但设计必须指定 owner |
| generic background task 当前只有 subagent/bash + killed | `background_tasks/models.py:10-24`；`task_stop.py:143-159` 对非 SUBAGENT 同步 `kill(...notified=True)` 并返回 `killed`；notification 逐字输出 record status（`notifications.py:18-44`） | 成立；新增 WORKFLOW cooperative branch 方向正确，但 stopped/killed 双状态映射未闭合，见 R6-C4 |
| 既有后台结果可在 parent 空闲后回普通消息 | background notifier 注入 parent session，PA `BackgroundSessionEventSubscriber` 对 `origin=BACKGROUND_TASK` assistant message 走现有 relay | 成立；Gateway/IM 无需 Workflow run repo、durable projection 或专属 UI，终态可复用普通后台消息 |
| current package requirement counts | kernel Background Tasks current 为 5；IM Agents and Nodes current 为 21；CLI Interactive REPL 7、kernel SDK 5/Runs 12、Gateway Agent Capabilities 10 未漂移 | 前两者叠加 unit 各 1 个 ADDED 后应为 6/22，见 R6-C2；其余 future counts 仍正确 |

### 决策台账

| 决策 | Gate 1 / 现状 / 下游核对 | 结果 |
|---|---|---|
| 1. active Workflow tool 是唯一开关 | tool schema/prompt、reminder、saved/management commands、ultracode 均从同轮 active snapshot 派生；PA pill 只是写 allowlist | pass；disabled 旧 run 管理措辞有跨文档歧义，R6-W1 |
| 2. capture 逐字移植为 Python | 版本、source locator、长度/hash、mechanical transform 与动态 guideline 均保留；未借本轮 UI 收敛删短 prompt | pass |
| 3. AST policy + compile/exec | capability boundary、禁用 import/reflection/dynamic code、checkpoint 与生命周期明确，不把 sandbox 误写安全容器 | pass |
| 4. primitives/limits | 全局 admission ordinal、parallel/pipeline tie-break、nested reuse、硬上限与 output budget 形成单一 manager 语义 | pass |
| 5. child runtime 复用 | child tool snapshot、禁止 Agent/Workflow、自身 return/structured output、模型优先级与 worktree input 已闭合 | pass |
| 6. journal/snapshot/background | journal 真源、atomic complete snapshot、状态机与一次 notifier 合理；generic killed ↔ Workflow stopped 未拍板 | R6-C4 |
| 7. chained v2 resume | key、最长同前缀、start/terminal ordinal、同 live pause 与新 run resume 边界明确 | pass |
| 8. launch/child permission | launch card与 generic options grounded；child request 只写目标语义，未把 async launch 后的持久 bridge owner/dataflow 固定 | R6-C3 |
| 9. human reminder/budget | HUMAN/WORKFLOW origin、尾部 `turn_system`、无运行时第二资格 gate、共享 token ledger 与测试 oracle 明确 | pass |
| 10. saved discovery/commands | project/personal/plugin precedence、symlink save、bundled deep-research、active-tool gate 明确 | pass；禁用旧 run 可见性文字需统一，R6-W1 |
| 11. worktree isolation | detached、clean 自动清理、dirty 保留、失败不回退共享目录、无自动 merge，边界足够 | pass |
| 12. SDK query/control | 五个窄方法、SDK-owned DTO、Gateway 直查真源、不泄漏 manager 的架构成立 | 设计主干 pass；MODIFIED delta 未跟上 current canonical，R6-C1 |

### Gate 1 约束台账

| Spec 原子 | 场景数 | 设计 / delta / milestone 映射 | 结果 |
|---|---:|---|---|
| 全入口可用且工具选择完整开关 | 4 | 决策 1；CLI 默认；PA optional pill；三入口 next-turn A/B；M1/M2 分工 | pass（受 R6-W1 措辞影响但无第二开关） |
| 默认逐次 opt-in / session ultracode / human-only | 5 | 决策 8/9；HUMAN origin、launch ask、mode reset、unattended fallback | pass |
| 可检查、编辑、复用的受限 Python 脚本 | 5 | 决策 2/3、artifact layout、validation、save/discovery | pass |
| 确定性多 Agent 编排 | 5 | 决策 4–7、admission/terminal ordinal 与 runtime hard caps | pass |
| 后台、三入口进度与控制 | 5 | CLI event view；Gateway SDK query ordinary reply；generic completion/task_stop | R6-C4；无 IM projection/event 的新约束已满足 |
| 同会话最长相同调用前缀恢复 | 4 | 决策 7、journal replay、new run `resumed_from` | pass |
| 保存、发现、分发、命名运行 | 5 | 决策 10、SDK save/list、CLI/Gateway command discovery | pass |
| 启动与 child 权限 | 5 | 决策 8、broker/parent route、通用 Web/飞书卡、unattended | R6-C3 |
| 规模、成本、模型路由 | 5 | guideline、hard caps、usage、child model/effort catalog fallback | pass |
| 错误可定位且不破坏主会话 | 3 | prelaunch compile/meta error、journal/artifact、failed/stopped partial diagnostics | pass（terminal status 受 R6-C4 阻断） |
| Q1 “都支持” | — | M1 CLI + M2 Web/飞书，runtime/SDK 共用 | pass |
| Q2 除 Python 必要适配外复刻 Claude Code | — | capture、permission modes、resume、save、size/model 均有明确基线；本轮 UI 只复用本产品既有 surface | pass |
| Q3 完整 Workflow 能力 | — | generation、execution、background、control、resume、save、permission、cost/model 均在范围 | pass（实现入口受 R6-C3/C4 阻断） |
| Q4 disabled 完整移除 model-facing 内容与入口 | — | active tool snapshot 与 A/B tests 明确；旧 run 仅保留 generic completion/task_stop | pass in design/IM delta；Gateway wording R6-W1 |
| 非目标 | — | 无 JS/TS、无额外资格/权限体系、无 cloud routines/hooks/agent teams、无 Workflow 专属前端 | pass |

### Delta-spec 台账

| Target | 核对结果 | 结果 |
|---|---|---|
| `cli/interactive-repl.md` | 精确 MODIFIED 既有 slash requirement；另加 opt-in/ultracode、background view/control，共 3 Requirements / 15 Scenarios | pass |
| `cli/spec.md` | Interactive REPL future count `7+2=9` | pass |
| `kernel/workflows.md` | 8 Requirements / 38 Scenarios，覆盖 capability、runtime、primitives、child、query/control、resume、save/discovery、budget/size | pass，permission/terminal 分别受 R6-C3/C4 影响 |
| `kernel/background-tasks.md` | 1 ADDED / 3 Scenarios，要求 WORKFLOW cooperative stop、partial diagnostics 与一次通知 | 语义方向 pass；index count R6-C2，状态映射 R6-C4 |
| `kernel/runs.md` | 精确 MODIFIED steer origin + ADDED human/automatic/workflow origin；旧 Scenario 保留 | pass |
| `kernel/sdk-boundary.md` | 精确标题但 MODIFIED 替换体遗漏 current canonical 后增的 public build 参数、动态 workspace config 语义与两个 Scenario | R6-C1 |
| `kernel/spec.md` | SDK 6、Runs 13、Workflows 8 正确；Background Tasks 仍写 5 | R6-C2，应为 6 |
| `gateway/agent-capabilities.md` | Workflow optional/default-off、guideline 保存与 next-turn snapshot，归属正确 | pass |
| `gateway/workflows.md` | 5 Requirements / 15 Scenarios；Gateway 直查 SDK、普通回复、generic permission/completion 已写清 | pass；disabled 旧 run “查看”与 IM/design 不一致，R6-W1 |
| `gateway/spec.md` | Agent Capabilities `10+1=11`，Workflows 5 | pass |
| `im/agents-nodes.md` | 1 ADDED / 3 Scenarios，只把 Workflow 作为 production tool pill，不造第二 toggle | pass |
| `im/workflows.md` | 2 Requirements / 7 Scenarios；普通 tool row/card/message、slash discovery、disabled 后 generic task_stop | pass |
| `im/spec.md` | Workflows 2 正确；Agents and Nodes 仍写 21 | R6-C2，应为 22 |

### Milestone 台账

| Milestone | 纵向性 / 依赖 / 退出标准 | 结果 |
|---|---|---|
| `M1-cli-workflow-runtime` | 从 opt-in/approval 经 compiler/manager/child/background/SDK 到 CLI query/control/resume/save/completion，是可独立使用的纵向切片；worker/reviewer 两轨、provider golden、ordinal、一次 notification 与 Luna journey 可验 | 切片 pass；M1 必须先把 R6-C1 的 SDK 合并体、R6-C4 的 terminal mapping 和 child→parent generic permission event seam 固定，不能留给 M2 猜 |
| `M2-assistant-workflow-surfaces` | 只经 M1 SDK/snapshot 接 PA/Gateway/IM/Web/飞书；明确使用 existing pill/slash/permission/tool/message surface，且负向断言无 IM repo/event/专属组件 | 切片 pass；M1/M2 的 permission bridge owner 目前未分配完整，R6-C3 会导致两个 worker 各自实现一半 |

空目录骨架成立：实现期才写 `tasks.md`/`progress.md`。M2 依赖 M1，不存在伪并行承诺，也不需要因删除 prototype 新增前端设计 milestone。

### 整体判断

| 维度 | 判断 |
|---|---|
| 用户层 | 最新方向正确：Agent 设置只是 `Workflow` pill；slash、批准、tool audit、查询/控制/终态全落既有 production surface；没有新视觉概念需要 prototype |
| 数据流 | run state 留在 kernel journal/snapshot，CLI消费 session update；Gateway `/workflows` 每次直接查 SDK 并普通回复；IM 不持久化/relay Workflow run state，终态复用后台普通消息。主路径清楚；后台 child permission 的 long-lived generic bridge仍缺 owner |
| 一致性 | spec↔design 主语义基本一致，但 current canonical 漂移使 SDK MODIFIED 和两处 package count 失真；disabled 旧 run 可见性有一处措辞分叉 |
| 实施可执行性 | compiler/manager/resume/save/model/UI 都能形成确定 tasks；权限桥和 stopped/killed terminal mapping 仍允许互不兼容实现，不能进 worker 猜测 |
| Runbook | 静态、CLI Luna、隔离 Web、专用飞书路径和 cleanup 明确；docs-check 当前通过，但尚未验证未来 delta merge，修 R6-C1/C2 后需再跑 merge/docs gate |

### 架构进攻

| 角度 | 进攻结果 |
|---|---|
| 归属 | Workflow 编译/调度/journal 在 kernel 深模块，SDK 只导出 DTO/query/control，Gateway 只解析产品命令并直查 SDK，IM 只存 Agent allowlist 与显示普通消息；符合产品仅 import `agent.sdk`、IM 不 import agent 的红线。R6-C3 不是要求 IM 增加 projection，而是要求现有 generic permission delivery owner延长到 parent 空闲期。 |
| 该不该存在 | manager、journal、complete snapshot、child adapter 都隐藏真实并发/恢复/权限复杂度；前端没有新增 Workflow store/hook/component，避免了只为本功能造薄壳。新增 WORKFLOW background type有必要，但它与 generic status 的语义必须明确（R6-C4）。 |
| 深还是浅 | SDK 五方法把产品从 executor/store 隔离，Gateway 断线后直查真源，是深接口；当前 SDK delta 却会把已存在的 `global_config_root`/workspace-config 契约抹掉，使接口文档比实现更浅（R6-C1）。 |
| 治本还是补丁 | active-tool 单一开关、journal single terminal、cooperative stop、parent broker id 都是治本方向；若通过 IM run event/projector补 child 权限会违反已确认设计，若把 WORKFLOW 当 bash 同步 kill则会重现 partial-result race。设计必须在既有 generic seams 上把两条路径拍死。 |

### Issues

- [R6-C1][CRITICAL] [SDK canonical merge：`specs/kernel/sdk-boundary.md:5-60`]: 该 `MODIFIED` Requirement 仍是 Round 2 时的旧 canonical 完整替换体，而 current canonical `docs/specs/kernel/sdk-boundary.md:47-104` 已增加 `build_kernel(global_config_root=None)`、按 session `workspace_config_dirname` 选择/验证配置目录、global auto-mode root 的合并/省略语义及两个 Scenario；真实源码也已有 `global_config_root`（`src/agent/sdk/kernel.py:230-249`）。unit delta 的签名不仅漏掉该参数，还退回 `<repo_root>/.nano/{tools,hooks,skills}` 的旧硬编码，并删除两个新 Scenario。MODIFIED 归并会静默抹掉当前公共契约，不是单纯漏写 Workflow 增量。不修会让 worker/contract test 在“保留当前 global config 行为”与“按 delta 删除”之间无合法答案，并可能实际回归 auto-mode 配置。应从**当前** canonical 全文重建该 MODIFIED：原参数、动态 config-dir/validation、9 个 current Scenario 全保留，再只叠加 `workflow_subagent_model`、`workflow_search_roots`、五个 Kernel 方法与对应模型场景。
- [R6-C2][CRITICAL] [package index merge：`specs/kernel/spec.md:9`、`specs/im/spec.md:7`]: Round 3 的 counts 基于旧 baseline；current canonical 已是 kernel Background Tasks 5 Requirements（`docs/specs/kernel/background-tasks.md` 五个标题）和 IM Agents and Nodes 21 Requirements（新增“设置 detail 页工具勾选态按存储真值渲染”等 current 条目）。本 unit 又各 ADDED 1 个 Requirement，因此 future counts 必须分别是 6 与 22，而 delta 仍写 5/21。当前 `docs-check` 通过只证明未归并 canonical 自洽；归并后会立即触发 Requirement count mismatch，无法完成 archive。应只更新这两个派生数字；CLI 9、kernel SDK 6/Runs 13/Workflows 8、Gateway 11/5、IM Workflows 2 不要改。
- [R6-C3][CRITICAL] [决策 8 / PA background permission path：`design.md:307-323,475-480,494`]: “child permission request/resolved 路由到 parent session”只写了目标，没有指定 async launch 返回后的生产 bridge owner。当前 child runtime 捕获 child 自己的 `session_event_publisher`（`runtime.py:1286-1483`），foreground Gateway observer 只消费当前 parent run stream（`session_run_coordinator.py:1490-1531`），而长驻 parent subscriber 的 event filter 只有 `self_evolution_review`（`background_session_events.py:25-33`）。Workflow launch 立即返回后，child 可能数秒后 ask；按现状事件既不会进入 parent stream，也不会到 Web/飞书 generic `PermissionCard`，broker future 会一直 parked。不同 worker可能新增 child subscriber、重发 parent event、甚至误造被禁止的 IM Workflow event/projection，架构不兼容。不修会直接破坏 spec 的交互式 child 权限场景。设计应固定最窄路径和 M1/M2 owner：Workflow child adapter 以同一 global broker id 把既有 generic `permission_request/resolved` 发布到 parent session并附两个 workflow id；PA 扩展既有 long-lived `BackgroundSessionEventSubscriber`/delivery callback消费这两个**现有通用事件**，复用现有 Web/飞书 resolver；CLI 明确其等价长驻消费；无人值守仍在发布前走既有 fallback。明确这不是 `workflow_run_updated`、不新增 IM repo/event/projection，并给 async parent-turn-ended 测试。
- [R6-C4][CRITICAL] [决策 6 / terminal contract：`design.md:274-291,408-421`]: Workflow snapshot/notification 承诺终态 `stopped`，但 generic `BackgroundTaskStatus` 只有 `killed`，`task_stop` 对所有非 SUBAGENT 立即 `kill(...notified=True)` 并返回 `killed`，notifier 又逐字输出 record status。设计只说 WORKFLOW 不走 bash 同步 kill、manager 最后更新 generic record，没有拍板 generic record 最终是 `killed` 还是新增 `stopped`，也没规定 `task_stop` 立即 result、manager partial result 与 `notified` 的最终写入顺序。两种实现都符合局部文字却会产出不同 SDK/tool/notification 状态；错误沿用 `notified=True` 还会吃掉唯一完成消息。不修会使停止场景无法满足“generic record 与 Workflow snapshot 最终一致”和一次含 partial diagnostics 的 `<status>stopped</status>`。最直接的拍板是为 generic status 正式增加 `stopped`，让 WORKFLOW 的 task_stop result、record、snapshot、notification 全部一致，并同步修改所有 terminal 穷举；若坚持保留 `killed`，则必须在 design/delta 明确它与 Workflow `stopped` 的稳定等价映射并放弃逐字一致要求。无论选哪条，都必须写清 `task_stop` 只 request、manager 收口后谁落 terminal/partial/notified、重复 stop/error 以及测试 oracle。
- [R6-W1][WARNING] [disabled 旧 run：`design.md:449,499`；`specs/gateway/workflows.md:28-32`；`specs/im/workflows.md:33-42`]: design/IM delta 最新语义是取消工具后 `/workflows` 消失，旧 run 只保留既有后台终态与已知 task 的 generic `task_stop`；Gateway delta 却仍说旧 run“可被用户查看和停止直到终态”，风险/回退又写“仍能…读取诊断”。它可能被解释成 disabled 后仍保留隐藏 `/workflows` 查询/控制入口，违背 Q4 和“无专属管理 UI”。不修通常不会改变内核架构，但会造成 Web/飞书 disabled A/B 与 worker tests 互相打架。应区分“单 Agent tool disabled”与“全局功能回退”，把 Gateway 场景逐字对齐为：专属 query/control/saved discovery 全消失；只交付 generic terminal message，并允许对已知 task id 使用既有 `task_stop`。若全局 rollback 仍需诊断，明确它是运维 artifact/SDK 能力，不是用户命令入口。

### Recommendations

- [R6-R1] 先修 R6-C1/C2 两个 current-baseline 归并问题，再把 R6-C3/C4 的运行时 owner/状态机拍板，最后统一 R6-W1 措辞；这些都是文档级定案，不需要恢复 prototype 或新增前端设计。
- [R6-R2] 修订后由当前 failover reviewer 做 `delta` Round 7：逐一模拟 SDK MODIFIED 与两个 package index 的 canonical merge，并从“parent foreground 已结束”开始走 child permission request→Web/飞书 decision→broker resume、task_stop→partial result→single terminal notification 两条 production trace；其余已通过原子可复用本轮 full 证据。

### Author Resolutions

- [R6-C1] Accepted：从当前 canonical 重建 SDK MODIFIED，保留 `global_config_root`、动态 `workspace_config_dirname`/验证、部署根发现和原 9 个 Scenario，再叠加 Workflow child model/search roots、5 个 SDK 方法与模型覆盖 Scenario。
- [R6-C2] Accepted：按 current canonical 重算 future counts，kernel Background Tasks 改为 6，IM Agents and Nodes 改为 22；其余计数不变。
- [R6-C3] Accepted：固定 Workflow child adapter 用同一 global broker id 向 parent session 发既有 generic permission events。M1 由 CLI 现有 parent stream 长驻 drain 独占消费 tagged events；M2 由 PA 现有 `BackgroundSessionEventSubscriber` 与 permission delivery/resolver 独占消费。两路都要在 parent foreground 结束后验证，不新增 Workflow event、IM repo/projection 或前端组件。
- [R6-C4] Accepted：通用后台任务增加 Workflow cooperative stop 专用终态 `stopped`，保留既有 bash/subagent `killed`。`task_stop` 只返回接受态 `stopping`；manager 收口 partial result 后依次落 journal、snapshot 和 generic `stopped` record，notifier 原子 claim 后只投递一条 `stopped` 终态通知，重复 stop 幂等。
- [R6-W1] Accepted：单 Agent 取消 Workflow tool 后，专属 query/control/saved discovery 下一轮全消失，只留 generic terminal message 和已知 task id 的既有 `task_stop`。全局 rollback 的 SDK/artifact 诊断是运维路径，不是隐藏用户命令。

## Round 7

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `delta`
- mode_reason: Round 6 是同一 reviewer 刚完成的 full inventory；本轮修订只对应 R6-C1..C4/W1 五个已知原子，需求/非目标、总体分层、无新前端设计和 M1→M2 纵向切片均未变化。SDK replacement、counts、permission route、terminal race、disabled 行为的上下游可枚举，因此只重查这些 changed atoms；核到 permission presentation anchor 仍断裂后，影响仍封闭在 R6-C3 路径内，无需升级 full。
- started_at: `2026-08-10T08:41:02+08:00`
- completed_at: `2026-08-10T08:47:40+08:00`
- duration: `6m38s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- changed_atoms: current-based SDK MODIFIED；kernel/IM future counts；child→parent generic permission events 与 CLI/PA 独占 consumer；Workflow `stopping→stopped` single-writer/atomic notification；disabled 与全局 rollback 消歧。
- merge_simulation: 精确比较 SDK current/modified Scenario 标题与原语义；按 current canonical Requirements + delta ADDED 重算 CLI/kernel/Gateway/IM 所有变化 area。
- runtime_traces: 追 `parent foreground ended → child permission_request → CLI picker / Web PermissionCard / Feishu card → broker resolve`，以及 `task_stop → stopping → journal/snapshot/generic stopped → atomic claim → single notification`。
- retained_from: Round 6 — 其余 10 Requirements、46 Scenarios、决策 1–5/7/9–12、13 份 delta 中未改条目、production frontend grounding、无 prototype、两 milestone 纵向性与四角度 full attack 均未被本轮修订失效。
- static_checks: `PYTHON=.venv/bin/python; PYTHON="$PYTHON" ./scripts/docs-check` 通过（226 maintained Markdown / 67 routes）；unit 全范围 `git diff --check` 通过；future count assertions 与 `prototype.html` absence 均通过。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R6-C1 | 从 current canonical 重建 SDK MODIFIED，再叠加 Workflow seams | delta 精确保留 current `global_config_root`、动态 `workspace_config_dirname`/验证、部署 roots、9/9 原 Scenario；只新增 `workflow_subagent_model`、`workflow_search_roots`、五个方法与一个模型覆盖 Scenario。与 `src/agent/sdk/kernel.py:230-249` 的 current build seam 不再冲突 | closed |
| R6-C2 | Background Tasks 6、Agents and Nodes 22 | 独立计数：current CLI 7/kernel SDK 5/Runs 12/Background 5/Gateway Agent Capabilities 10/IM Agents 21；对应 ADDED 为 2/1/1/1/1/1，future rows 逐一得到 9/6/13/6/11/22；新 areas kernel/Gateway/IM Workflows 为 8/5/2 | closed |
| R6-C3 | parent generic event；CLI/PA 长驻独占 consumer；parent turn 后验；无 IM projection/UI | transport ownership 和 M1/M2 边界已固定，CLI current long-lived session drain（`commands.py:541-584`）与 PA current subscriber（`background_session_events.py:25-74`）可复用；但 Web generic permission delivery 仍缺失可恢复的 target `message_id`，见 R7-C1 | superseded by R7-C1 |
| R6-C4 | 新增 Workflow-only `STOPPED`；task_stop 仅返回 stopping；manager single writer；atomic notification claim；重复 stop 幂等 | `design.md:293,418-431` 与 background delta 四个 Scenario 已统一：bash/subagent killed 不变；Workflow terminal record/snapshot/notification 全为 stopped；先收 partial 再落 terminal，claim winner only notification，迟到 terminal 与重复 stop 都有唯一结果 | closed |
| R6-W1 | disabled 只留 generic terminal + known task_stop；SDK/artifact 仅全局运维 | `design.md:459,509`、Gateway delta `:28-32`、IM delta `:33-42` 已逐字同义；没有 hidden `/workflows`，也未借 rollback 恢复用户入口 | closed |

### 本轮重查证据

| Changed atom / 波及链 | 独立核实 | 结果 |
|---|---|---|
| SDK MODIFIED → canonical merge | current 与 delta 的 requirement title 精确相同；current 9 个 Scenario 标题全部按原顺序保留，body 中 config-root/config-dir 语义也保留；Workflow 只做加法 | pass |
| future counts → package indexes | 用 canonical heading count + delta ADDED count 重算；四份 `spec.md` rows 全部吻合，docs-check 当前态也通过 | pass |
| CLI child permission → parent long-lived drain | current REPL 从 session 建立起启动独立 `kernel.stream(sid)` task（`commands.py:541-584,774,794`）；设计指定 tagged event 由它直接 picker/resolve、foreground drain 跳过，并要求 parent terminal 后测试 | pass；“独占”同时排除了 process-global direct callback 的重复呈现，worker 无第二种产品语义可选 |
| PA child permission → parent replay/long-lived subscriber | current foreground terminal 后以 parent start anchor 建 subscription（`session_run_coordinator.py:911-930`），stream 可 replay anchor 后的 tagged event；设计指定 foreground observer skip、background subscriber delivery，Feishu request_id 当前也有 pending dedupe（`channels/feishu/approval.py:114-121`） | event transport pass；Web presentation anchor R7-C1 |
| Workflow stop → one terminal/notification | current hardcoded killed seams 已在 Round 6 取证；修订明确新增 stopped 到 DTO/store/terminal predicates/formatter，manager 唯一终态写者，task_stop 不改 notified，registry atomic claim 才投递 | pass；worker 不再能把 WORKFLOW 当 bash 或丢 partial result |
| disabled / rollback | 单 Agent runtime snapshot 与用户入口全部消失；generic task completion/known task_stop 不构成 Workflow command；SDK/artifact 只留给全局运维 | pass |
| frontend/prototype | `prototype.html` 不存在；本轮没有引入 IM run event/repo/projection、message type 或新组件，仍只复用 production surfaces | pass |

### 受影响的架构进攻

| 角度 | 重查结果 |
|---|---|
| 归属 | generic permission event 由 kernel parent session 持有，CLI/PA 各自在产品长驻 consumer 呈现，仍符合产品只 import SDK、IM 不 import agent；STOPPED/claim 留在通用 background registry，Workflow manager 只负责自身收口。Web message anchor 尚未指定 owner，R7-C1 会让 Gateway/IM 边界再次由 worker 猜。 |
| 该不该存在 | 复用 session stream、`BackgroundSessionEventSubscriber`、现有 broker/card 和 background registry，删除测试后都仍是生产必需能力；没有为 Workflow 新建 IM state/event/UI。原子 notification claim 是并发 once-only 的必要原语，不是预造抽象。 |
| 深还是浅 | SDK query/control 隐藏 manager/store，STOPPED 统一 tool/record/snapshot/notification，比 special renderer mapping 更深；permission transport 复用现有 event，但目前只解决“送到哪个 conversation”，尚未隐藏 Web card“挂到哪条 message”的复杂度，见 R7-C1。 |
| 治本还是补丁 | single terminal writer + claim 正面解决 stop/notify race；active-tool/rollback 消歧正面消除 hidden entrance；若让 worker 临时新建无 anchor bubble 或复用已回收 run context，会把 R6-C3 从 transport bug 换成 presentation patch，R7-C1 必须在设计层治本。 |

### Issues

- [R7-C1][CRITICAL] [决策 8 / M2 Web permission presentation：`design.md:327-333,485-490,578`]: 修订拍死了 child permission event 的 transport owner，却没有拍死 Web `PermissionCard` 在 parent foreground 已结束后挂到哪一条 IM message，也没有把所需 message anchor 带进 M2 seam。current `BackgroundSubscriptionRequest` 只保存 parent `session_id`、`after_sequence`、`ReplyContext`、`agent_id`（`background_subscriptions.py:25-45`），而 `ReplyContext` 只有 conversation/channel target（`channels/base.py:49-63`）；current Web permission delivery必须持有 agent bubble `message_id` 才能发送 `node.streaming_delta`（`runtime_delivery/observer.py:1633-1668`）。更关键的是 foreground `RunDeliveryContext` 虽曾持有该 `message_id`（`runtime_delivery/context.py:69-83`），却在 parent lifecycle completed 时立即 discard（`runtime_delivery/lifecycle.py:29-45,157-164`）。因此 background subscriber 按现设计拿到 tagged request 后，只能知道原 conversation，无法复用 existing `PermissionCard`。worker 会被迫在“提前把 launch bubble id 冻结进 subscription”“重新创建一条普通 agent bubble 承载 card”“保留已终态 RunDeliveryContext”之间猜；三者有不同持久化、重连和消息历史语义，错误实现会让 Web request 静默不显示、broker 永久 parked，或泄漏 live run context。不修会直接使 R6-C3 要求的 parent-turn-ended Web 旅程不可实施。设计应选择并固定一个既有-surface方案：推荐在 parent foreground terminal/discard 前，把确定的 conversation id + launch assistant `message_id` 作为 background permission delivery anchor 交给 subscription（或一个窄的 session delivery binding），tagged request 只按 request_id 幂等 append 到该既有 bubble；若产品要新开普通 agent bubble，也必须明确由哪个现有 `turn_start`/message owner 创建、如何取得并持久化 id、resolved/reconnect 如何命中同一 bubble。两种都不需要新前端组件或 Workflow IM projection，但必须在 design、M2 scope 和 parent-ended test oracle 中只留一种。

### Recommendations

- [R7-R1] 只需回 `change-design-author` 收 R7-C1：补 Web background permission 的 durable message anchor 与唯一 owner，并把 M2 worker test 固定到该 bubble；不要改已闭合的 SDK/count/STOPPED/disabled 条款，也不要恢复 prototype。
- [R7-R2] 修订后继续由当前 reviewer 做 `closure`：从 foreground bubble id 产生点追到 BackgroundSubscriptionRequest、tagged request append、permission resolved 和 reconnect dedupe；若只补这一条数据流，不需再审 CLI、terminal 或其他前端 surface。

### Author Resolutions

- [R7-C1] Accepted：M2 在 parent foreground terminal 丢弃 `RunDeliveryContext` 前，把 conversation id 与含 Workflow launch tool row 的 assistant `message_id` 快照成不可变 `BackgroundPermissionDeliveryAnchor`，随既有 `BackgroundSubscriptionRequest` 交给长驻 subscriber，不保留整个 live context。Web request/resolved 按 request id 幂等更新原 launch message 的现有 `PermissionCard`，IM message history 保证重连恢复；只有 tool row 时也保留该已有气泡。飞书仍走 `ReplyContext` 与通用原生卡。M2 测试固定在 parent context 已释放后验证同 message id、request-id dedupe、resolved 与 browser reconnect；不新增 IM repo/event/projection、message type 或前端组件。

## Round 8

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `delta`
- mode_reason: Round 7 已有可信的 Round 6 full inventory；本轮虽只处理 R7-C1，但新增了跨 foreground terminal 的不可变 anchor、气泡保留规则与 Gateway/IM 可观察契约，属有界设计语义变化而非只补证据或措辞。影响可封闭在 PA 每 session 长驻 subscriber 的 permission delivery binding、既有 IM message 持久化/重连与 M2 验收，未改需求范围、总体分层、M1 或其他共享契约，因此用 delta；重查发现的 subscriber 复用缺口仍在同一波及链内，无需升级 full。
- started_at: `2026-08-10T08:55:44+08:00`
- completed_at: `2026-08-10T08:59:48+08:00`
- duration: `4m04s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- changed_atoms: terminal 前从 `RunDeliveryContext` 快照 `BackgroundPermissionDeliveryAnchor`；anchor 经 `BackgroundSubscriptionRequest` 交给每 session 长驻 subscriber；tagged request/resolved 按 request id 更新原 launch message；tool-row-only 气泡保留；IM history/reconnect；Gateway/IM delta 与 M2 test oracle。
- affected_trace: `foreground turn_start ACK → Workflow tool row → parent terminal → anchor registration → existing/new per-session subscriber → tagged child request/resolved → IM persistence → browser reconnect`。
- retained_from: Round 7 — R6-C1/C2/C4/W1 已闭合的 SDK replacement、package counts、Workflow stopped/notification 与 disabled 契约未变；其余 Requirements/决策/delta、无 prototype/无新前端设计、M1→M2 纵向切片仍继承 Round 6 full 证据。
- static_checks: `PYTHON=.venv/bin/python; PYTHON="$PYTHON" ./scripts/docs-check` 通过（226 maintained Markdown / 67 routes）；`git diff --check` 通过；`prototype.html` 与 `workflow_data_root`/equivalent 草案均不存在，artifact 仍使用 workspace-aware session storage。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R7-C1 | terminal 前冻结 conversation/message anchor，长驻 subscriber 在原 launch message 幂等投递，不保留 live context | 单次首次 subscription 的 message target、context lifetime、request-id persistence/reconnect 已拍死；但 current manager 对已有 per-session subscriber 直接返回 `ALREADY_ACTIVE`，新 request/anchor 不会进入已捕获旧 request 的 callback，且设计未定义多 launch binding，见 R8-C1 | superseded by R8-C1 |

### 本轮重查证据

| Changed atom / 波及链 | 独立核实 | 结果 |
|---|---|---|
| launch message id 产生→terminal 快照 | Web 正常 turn 的 `turn_start` 由 foreground pipeline await ACK 后回填 `RunDeliveryContext.message_id`（`runtime_delivery/observer.py:868-912`）；coordinator 在 terminal 后、completed lifecycle discard 前调 `ensure_after_foreground_terminal`（`session_run_coordinator.py:911-941`，`runtime_delivery/lifecycle.py:29-45`） | pass；narrow anchor 能在 live context 回收前形成，无需保留整个 context |
| tool-row-only launch bubble | current `RunDeliveryContext` 明示 process event 不 commit visible bubble（`runtime_delivery/context.py:60-67`），current `turn_end` 会 discard 无文字的 Web bubble（`runtime_delivery/observer.py:1339-1365`）；设计现已唯一指定 Workflow launch tool row 阻止该 discard（`design.md:331`） | pass；这是 M2 必须改动的既有 visibility seam，不是新气泡/组件 |
| per-session subscriber 复用→anchor 更新 | current manager 只有一个 subscriber/session（`background_subscriptions.py:50-75`）；已存在时 `ensure_after_foreground_terminal` 直接返 `ALREADY_ACTIVE`（`:94-117`）；subscriber callbacks 闭包捕获创建时的 `request`（`:167-216`） | fail；后续 foreground turn 的 anchor 无交付通道，见 R8-C1 |
| tagged request/resolved → persisted message → reconnect | current repository 按 request id append/replace 并在同一 message 上按 id resolve（`src/IM/infra/repositories/messages.py:959-1069`）；history DTO 读回该 list（`:1136-1171`）；frontend reducer 与 REST/WS merge 均按 request id 幂等（`chat-stream-reducer.ts:315-340`，`chat-workspace-page.tsx:92-112,204-225`） | pass；一旦选对 message id，无需新 IM repository/event/projection/component |
| Gateway/IM delta 与 M2 oracle | Gateway delta 要求 terminal 后幂等更新原 launch message 且重连可见（`specs/gateway/workflows.md:55-67`）；IM delta 要求 request/resolved 同 message 且无专属组件（`specs/im/workflows.md:17-21`）；M2 要求 live context 释放后的同 message/dedupe/reconnect（`design.md:578`） | single-launch 行为已对齐；未覆盖“subscriber 已存在/多 launch”绑定语义，见 R8-C1 |
| artifact path clarification | unit/research 中无 `workflow_data_root` 或等价新 root；`design.md:258-272` 仍只使用已选 workspace/config-dir 下的 session storage | pass；中途草案未改变当前评审语义 |

### 受影响的架构进攻

| 角度 | 重查结果 |
|---|---|
| 归属 | 从 terminal run context 提取窄、不可变 anchor 并交给 PA 长驻 delivery owner 的层次正确；但 anchor 附在一个可被 `ALREADY_ACTIVE` 丢弃的启动 request 上，并未落到能处理同 session 后续 launch 的 binding owner，R8-C1 会让 worker 重新猜职责。 |
| 该不该存在 | `BackgroundPermissionDeliveryAnchor` 取代已终态的整个 `RunDeliveryContext`，删除测试后会直接丢失 Web 原 message 投递，因此它是必要而非 YAGNI；但多 launch 的可变索引与每 launch 的不可变 anchor 必须分开，不能用一个“最新 anchor”替代。 |
| 深还是浅 | IM 现有 permission persistence/reducer 已隐藏同 message 的 dedupe/reconnect 复杂度，复用是深接口；PA subscriber 若只捕获初次 request 中的单 anchor，却对外宣称支持后续 Workflow launch，就是把路由复杂度泄给 worker 的浅接缝。 |
| 治本还是补丁 | 只覆盖当前 anchor 会让较早 Workflow 的迟到 request 被误投到较新 bubble；只保留首个 anchor 则会丢后续 launch。必须用 tagged event 已有的 Workflow 关联 id 解决 exact binding，否则只是从 context-lifetime bug 换成 cross-turn routing bug。 |

### Issues

- [R8-C1][CRITICAL] [决策 8 / M2 `BackgroundPermissionDeliveryAnchor` 的多 launch 绑定：`design.md:327-333,488,578`]: 修订把一个不可变 launch anchor 放入 `BackgroundSubscriptionRequest`，但没有定义已存在的 per-session subscriber 如何接收当前或后续 Workflow launch 的 anchor，也没有定义多个未终态 Workflow 的 anchor 如何与 tagged event 精确匹配。current `BackgroundSubscriptionManager` 一个 kernel session 只启一个 subscriber（`background_subscriptions.py:50-75`），后续 `ensure_after_foreground_terminal` 在检测到已存在后立即返回 `ALREADY_ACTIVE`（`:94-117`），而 callback 闭包一直捕获首次创建时的 request（`:167-216`）。这不是罕见边界：同一会话在 Workflow 之前完成过任何 foreground turn 就可能已有 subscriber，spec 还明确允许 ultracode 在同会话编排“一个或多个 Workflow”（`spec.md:79-83`）。不修时，worker 只能在“永远使用第一个 anchor”、“覆盖为最新 anchor”、“自行新增按 run 索引”之间猜；前两者会让后续或并发 child request 丢失/挂到错误 assistant message，使 broker 永久 parked 或重连后出现错卡。设计必须拍死一个仍属 Gateway 内部的窄 binding owner：每次 Workflow launch 即使 subscriber 已 active 也能注册不可变 anchor，并用已规定的 `workflow_run_id` / `agent_call_id` 把 request/resolved 解析到精确 launch message；同时说清 terminal/无 pending 后的清理边界。M2 永久测试必须至少覆盖“subscriber 先于 Workflow 已存在”和“两个 launch message id 各自收到自己 request/resolved”；这不需要 IM run projection/event/新组件，也不应恢复 live context。

### Recommendations

- [R8-R1] 只回 `change-design-author` 收 R8-C1：把 anchor 从“只随首次 subscriber admission 传入”收敛为“每个 Workflow launch 可更新注册、按 Workflow 关联 id 路由、有明确清理”的窄 Gateway binding，并在 M2 加已有 subscriber + 两 launch 的测试 oracle。不要改已闭合的 IM persistence/reconnect，artifact storage 或无新 UI/projection 边界。
- [R8-R2] 修订后当前 reviewer 可用 `delta` 只重查 binding 注册、已 active subscriber 更新、多 launch exact routing 与清理；这是有界的共享 seam 语义修订，不必重做整份 full inventory。

### Author Resolutions

- [R8-C1] Accepted：不再把 launch anchor 只闭包在首次 `BackgroundSubscriptionRequest`。M2 在每次 Workflow `tool_end` 看到 `runId` 时向 Gateway 进程内 `WorkflowPermissionDeliveryBindingRegistry` 注册 run-level immutable anchor；per-session subscriber 无论是否早已 active，callback 都只闭包该 registry。request 经 `workflow_run_id` 命中 run anchor 后注册 `(workflow_run_id, agent_call_id, request_id)` 精确 binding，resolved 只按该三元组回原 message，禁止 first/latest fallback。run terminal 时无 pending 立即清理，有 pending 则等最后 resolved 后清理。M2 永久测试固定“subscriber 预先存在 + 同 session 两个 Workflow launch message + 各自 request/resolved/reconnect/cleanup”；不新增 IM durable state、event、projection 或前端组件。

## Round 9

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `delta`
- mode_reason: Round 8 已将未闭合范围精确限定在 PA multi-launch permission binding；本轮新增 Gateway 进程内 registry、run-level anchor 注册、三元组 exact binding 和清理状态，是有界共享 seam 语义修订，因此继续 delta 而非 closure。需求范围、分层、M1、IM 持久化/UI 及其他契约未变；本轮新发现仍封闭在“Workflow tool result → registry → permission/terminal event”同一波及链，无需升级 full。
- started_at: `2026-08-10T09:09:04+08:00`
- completed_at: `2026-08-10T09:13:30+08:00`
- duration: `4m26s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- changed_atoms: `WorkflowPermissionDeliveryBindingRegistry` 归属；Workflow `tool_end` 的 run anchor 注册；已 active subscriber 只闭包 registry；`workflow_run_id/agent_call_id/request_id` exact binding 与禁止 first/latest fallback；run terminal/pending-resolved 清理；同 session 两 launch 的 delta/M2 oracle。
- affected_trace: `Workflow manager async launch → child permission/terminal publication || parent tool result/tool_end → Gateway anchor registration → exact request binding → resolved → cleanup`，特别重查两条并发链的 happens-before 与 machine-readable correlation。
- retained_from: Round 8 — terminal 前只快照窄 anchor、tool-row-only 气泡保留、IM request-id persistence/reconnect、无 IM projection/event/新 UI、nano workspace-aware artifact storage 均未变；Round 6 full 及 Round 7 已闭合的 SDK/count/stop/disabled 证据仍有效。
- static_checks: 同步后 current baseline 上原样执行 `PYTHON=.venv/bin/python; PYTHON="$PYTHON" ./scripts/docs-check` 通过（214 maintained Markdown / 67 routes）；`git diff --check` 通过；`prototype.html` 不存在；除历史 review 文字外，当前受审 design/spec/delta/research 无 `workflow_data_root` 或等价新 storage root。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R8-C1 | 每 launch 注册 run anchor；subscriber 只闭包 registry；三元组 exact binding；terminal/pending 清理；测已 active subscriber + 两 launch | 已消除首次/最新 anchor 歧义，多 run ownership、lookup key 与清理目标均已拍死；但注册入口尚无可用的 machine-readable Workflow run id，且 permission/terminal 可早于 tool_end 注册，没有乱序契约，见 R9-C1 | superseded by R9-C1 |

### 本轮重查证据

| Changed atom / 波及链 | 独立核实 | 结果 |
|---|---|---|
| 已 active subscriber → multi-run registry | current manager 的 per-session subscriber 只创建一次且旧 callback 闭包初始 request（`background_subscriptions.py:50-75,94-117,167-216`）；修订现指定 callback 改为闭包 process registry，每 launch 另行注册 run anchor（`design.md:331-335`） | pass；R8 的 `ALREADY_ACTIVE` 断路已在正确 owner 层解除 |
| run/call/request exact routing | child generic event 已规定附 `workflow_run_id` / `agent_call_id`（`design.md:329`）；registry 用三元组幂等绑定，resolved 同 key 回原 anchor，明禁 first/latest fallback（`:333`）；Gateway delta 同步约束两 launch 不串消息（`specs/gateway/workflows.md:64-68`） | pass；不需要 IM 第二份 run state |
| parent `tool_end` → Workflow run anchor key | current realtime hook 只把 parent foreground `run_id`、tool `call_id`、arguments/status/presentation 放入 `tool_end`；raw tool output 仅交给 presenter，未透传（`src/agent/platform/hooks/builtins/realtime_stream.py:85-115`）。Workflow 返回值中的 camel-case `runId` 不是该 parent `run_id`（`design.md:397-408`），设计也未定义它通过哪个 machine-readable 字段进入 Gateway | fail；worker 会在扩共享 tool event、把控制键塞入 presentation detail、解析 summary 之间猜，见 R9-C1 |
| async launch ↔ anchor 注册时序 | current tool body 在 worker thread 中运行，只在 `tool.run` 返回后才组装/发布 `tool_result`（`src/agent/core/tools/registry.py:361-364,417-435`）；已有 async Agent 模式也是先启动独立 auxiliary，再返回 `async_launched` id（`src/agent/platform/tools/builtins/agent.py:329-370`）。Workflow 设计同样“manager 后台运行 + tool 立即返回”（`design.md:95,397-408`），因此 child request 或快速 terminal 与 parent tool_end 没有已建立 happens-before | fail；registry miss 的 buffer/barrier/tombstone 语义未定义，见 R9-C1 |
| terminal → closing/cleanup | 设计规定了 closing/pending 状态机（`design.md:333`），但未指定哪个 production owner 把 terminal 信号交给 registry。current subscriber 默认只转发 `self_evolution_review`（`background_session_events.py:25-29,65-85`）；本设计另有 `workflow_run_updated`，但 Gateway 不复制 Workflow 状态（`design.md:420`） | partial；清理算法已对，terminal source/乱序还需拍死，见 R9-C1 |
| M2 oracle | 已覆盖 subscriber 预先存在、同 session 两个 Workflow/两个 message、各自 request/resolved/reconnect/cleanup（`design.md:337,582`） | multi-launch mapping pass；该顺序是先完成 launch/anchor 再触发 request，不会暴露 pre-anchor request 或 pre-anchor terminal |
| UI/projection/artifact 边界 | registry 明确为 Gateway 进程内窄路由表，Web/Feishu 继续复用现有 card/message，无 IM durable state/event/projection/新组件（`design.md:333-335`）；storage 仍为 workspace-aware session root（`:258-272`） | pass |

### 受影响的架构进攻

| 角度 | 重查结果 |
|---|---|
| 归属 | run/message binding 是 PA/Gateway 呈现路由，放在 Gateway 进程内而不放 IM 或 kernel manager 是正确依赖方向。但若为拿 run id 而解析 user-facing presentation，就会让控制路由反向依赖前端展示契约；长期任一 presenter 文案/截断变更都会破坏批准路由。 |
| 该不该存在 | 删除 registry 就无法在 live context 回收后把多 run permission 定位到原 message，因此新抽象有必要；它也只是路由表，没有复制 Workflow snapshot。 |
| 深还是浅 | exact binding + pending-aware cleanup 可以把 multi-launch 和 context lifetime 复杂度封装在一处，是深 seam；但如果 caller 必须保证 tool_end 总早于 child event，接口就把最危险的调度假设泄漏到外层，测试稍换时序就失效。 |
| 治本还是补丁 | 禁止 first/latest fallback 正面解决了 cross-run 错绑；但在 registry miss 时直接 drop，或假设 async 任务不会先跑，只是用调度偶然性遮住同一个路由 bug。 |

### Issues

- [R9-C1][CRITICAL] [决策 8 / M2 registry 注册与清理数据流：`design.md:327-337,489-494,582`]: registry 的 owner、exact key 和 pending-aware cleanup state machine 已拍死，但它的两个必需输入仍没有可实施契约。第一，设计说 foreground observer 从 Workflow `tool_end` 看到 tool result `runId`，但 current `tool_end` 中的 `run_id` 是 parent foreground run；raw tool output 只传给 presenter，最终 session event 仅有 parent `run_id` / call / args / status / presentation（`src/agent/platform/hooks/builtins/realtime_stream.py:85-115`）。因此 worker 必须猜是扩充共享 tool event 的 machine field、借 presentation detail，还是解析可截断 summary；后两者会让 permission control path 依赖展示文案，前者又是未定义的跨 M1/M2 共享契约。第二，Workflow manager 在后台开始执行后 tool 才返回 id；current tool pipeline 也只在 `tool.run` 返回后才发 tool result（`src/agent/core/tools/registry.py:361-364,417-435`）。设计没有建立“anchor 注册早于 child 发布”的 barrier，也没有规定 registry 如何缓冲/retire 早到的 `permission_request` 或 terminal；terminal 信号由哪个 production owner 交给 registry 也未写明。不修时，快速 child 的第一个 request 会在 run anchor 存在前被 drop，broker future 永久 parked；零/快速 run 的 terminal 先到时则会在 tool_end 后注册一个再也不清理的 anchor。现有“先 launch 再触发 request”测试不会抓到两者。设计必须同时拍死：(1) 一个不泄漏 raw output、不解析 presentation 的 machine-readable Workflow run correlation seam；(2) 明确 happens-before，或让 registry 按 run id 有界地保留 pre-anchor request/terminal tombstone，anchor 注册后幂等 drain/cleanup；(3) 唯一 terminal producer/consumer 路径。M2 测试再强制“request 先于 anchor”和“terminal 先于 anchor”，同时保留已 active subscriber + 两 launch 验收。这仍只需 Gateway 进程内调度/路由，不需要 IM durable state、projection、新 event type 或新 UI。

### Recommendations

- [R9-R1] 只回 `change-design-author` 收 R9-C1：为 Workflow `tool_end` 定义独立于 presentation 的 machine correlation，并在“启动 barrier”与“registry 缓冲 pre-anchor event/tombstone”中选一条拍死，同时指定 terminal signal owner；测试强制两种早到顺序。
- [R9-R2] 修订后可由当前 reviewer 再做 `delta`：从 tool raw result 追 machine correlation 到 Gateway registry，再分别执行 pre-anchor request 与 pre-anchor terminal 时序；其他 Round 8/9 已通过原子可直接继承。

### Author Resolutions

- [R9-C1] Accepted：machine correlation 不从 presentation 或 raw output 解析。M1 为 tool result 增加无 secret 的 `event_metadata` 侧车链：`Workflow.result_event_metadata(raw_result) -> ToolRegistry out_meta -> ToolResult.event_metadata -> realtime_stream tool_end.event_metadata`，其中通用 `tool_end.run_id` 继续只表示 parent foreground run；Workflow 在创建 run id 后、启动后台 manager task 前先把同一 correlation 写入 run record，permission 与 terminal event 也携带它。M2 在 `tool_start` 先按 parent session/tool call 注册 launch message pre-anchor，再由 `tool_end.event_metadata` 绑定 run id；Gateway registry 对 anchor、request/resolved、terminal 任意先后实行 pre-anchor buffer + closing tombstone，绑定后按 parent session event sequence 幂等 flush。Workflow manager 是唯一 terminal producer：先收口 pending broker request，再持久化终态，最后发布带 correlation 的 terminal `workflow_run_updated`；Gateway 同一 per-session subscriber 是唯一 cleanup consumer，只送 registry、不 relay IM。永久测试同时固定 request-before-anchor、terminal-before-anchor、subscriber 预先存在及同 session 两个 launch exact routing/cleanup。

## Round 10

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `full`
- mode_reason: 本轮不仅收口 R9-C1，还改变了用户可观察的 Web IM 非目标/展示契约并恢复 `prototype.html`，同时为 core tool result、通用 session event 与 Gateway registry 增加跨层 machine-correlation dataflow；这些分别命中“需求/非目标变化”和“核心边界/共享数据流高风险变化”，按 skill 必须 full。故重新逐条核对五类承重原子和四个架构进攻角度，不继承 Round 9 的 delta 范围。
- started_at: `2026-08-10T09:56:31+08:00`
- completed_at: `2026-08-10T10:04:44+08:00`
- duration: `8m13s`

### Verdict

Issues Found — 2 CRITICAL / 1 WARNING

### Coverage

| 类别 | 本轮完整范围与动作 |
|---|---|
| 首文档 | 完整读取 `spec.md`；逐条核 4 个澄清、4 段用户场景、10 Requirements / 46 Scenarios、范围与非目标 |
| 设计 | 完整读取 Changelog、6 条上游事实、7 条本仓接缝、5 条既有约束、架构图/归属、决策 1–12、接口数据流、Web/CLI/飞书、原型、测试/风险/runbook、M1/M2 |
| delta-spec | 完整读取四包 13 份 delta；对 3 个 MODIFIED Requirement 与 current canonical 做标题/Scenario 归并模拟，对全部 ADDED 条目核消费者视角与可观察 THEN，并重算所有变化 area 的 future counts |
| current canonical | 完整核相关 `docs/specs/{kernel,cli,gateway,im}` package index 与 SDK Boundary、Runs、Background Tasks、Interactive REPL、Agent Capabilities、Agents and Nodes；current 已同步到 feat-519，不能沿用 Round 9 前的计数快照 |
| 生产源码 | 正向追 active tools/prompt、SDK、tool gate/result/realtime、child/background/permission、PA config/subscriber/IM delivery、message persistence/reconnect、PillSelector/slash/ToolCallsPanel/AgentCard/PermissionCard 的实际生产路径 |
| 原型与静态门禁 | 完整读取 `prototype.html`；Node 编译内联脚本成功，枚举 6/6 review states（running/permission/launched/completed/failed/stopped）且 deny interaction 存在；无 progress-strip/detail-sheet/run-panel；`PYTHON=.venv/bin/python; PYTHON="$PYTHON" ./scripts/docs-check` 通过（215 maintained Markdown / 67 routes）；unit 范围 `git diff --check` 通过 |

### 历史问题闭环

| 历史项 | Author Resolution | 本轮独立核实 | 状态 |
|---|---|---|---|
| R1-C1–C6 / R1-W1–W2 | ordinal、canonical MODIFIED、symlink/model/reminder placement、milestone 双轨 | 决策 2/4/5/7/9/10/12、三份 MODIFIED 与 M1/M2 仍保留对应收口；未因本轮 UI/correlation 改动失效 | closed |
| R2-C1 / R2-W1 | 四包 future indexes 与 docs-check 调用修正 | shell wrapper 命令仍正确；但 current Gateway/IM canonical 再次演进，旧计数结论客观过期，见 R10-C1 | superseded by R10-C1 |
| R4-W1 | 改用 production PillSelector / Agent detail 路径 | `agent-create-page.tsx` 与 `agent-detail-page.tsx` 当前均 import/render `PillSelector`；design locator 与本轮原型没有复活 checkbox/card allowlist | closed |
| R6-C1/C3/C4 / R6-W1 | SDK current replacement；child generic permission owner；Workflow cooperative stopped；disabled/rollback | SDK MODIFIED 仍保留 current 9/9 Scenario；CLI/PA 长驻 consumer、manager single terminal writer、atomic notification claim、disabled 后专属入口消失均仍成立 | closed |
| R6-C2 | 当时按 canonical 重算 Background 6、IM Agents 22 | Background 6 仍正确；IM current 又从 21 增到 23，unit future 应为 24，且 Gateway current 也从 10 墁到 12，见 R10-C1 | superseded by R10-C1 |
| R7-C1 / R8-C1 | terminal 前窄 message anchor；已 active subscriber + multi-launch exact binding | foreground `tool_start` pre-anchor、registry-only callback、run/call/request 三元组、IM request-id 持久化与重连均已完整串起；不再闭包首次 request 或保留 live context | closed |
| R9-C1 | event_metadata sidecar；pre-anchor buffer/tombstone；唯一 terminal/cleanup owner | current `out_meta` 已是 per-call non-model sidecar（`registry.py:166-175,257-264`），`ToolResult` 经 loop 的 observe payload到 realtime `tool_end`（`tool_executor.py:189-213`、`loop.py:794-825`、`realtime_stream.py:85-115`）；设计在这些同一承重点增加 `event_metadata`，并明确 tool_start pre-anchor、任意乱序、manager terminal 与 subscriber cleanup，machine route 不再解析 presenter/raw output | closed |

### 现状断言核实台账

| 承重原子 | 本轮独立证据与结论 |
|---|---|
| 上游 async tool→background→notification | 固定 trace/run/journal locator 仍在 `research.md:156-160,201-217`，研究对工具启动与终态通知有逐事件记录；design 的有限同步 launch 结论成立 |
| 上游完整 tool object、无第二段稳定 Workflow prompt | capture manifest 仍记录 21,259/19,214/1,775 chars 与 hashes（`research.md:201-217`）；design 只从 active tool 派生 prompt，成立 |
| keyword/standing reminder role/order | 两个本地 proxy session 仍存在；design 固定逐字文本与 human 后尾部 `role=system`（`design.md:32-44,353-363`），没有退回 leading system/user 拼接，成立 |
| AST + VM 与 chained-v2 resume | 固定 binary hash、Acorn→instrument→VM 路径在 `research.md:108-129`，chained prefix 证据在 `research.md:262-263`；Python 的 AST+compile 与 prefix ledger 是明确语言适配，不是臆造逐节点解释器 |
| active tool 同源决定 schema/prompt | production loop 解析 active tools 并同时交给 prompt 与 provider request（`src/agent/core/agent/loop.py:269-286,409-423`）；runtime/session allowlist 路径在 `runtime.py:1235-1242,1988-1992`，决策 1 落在真路径 |
| SDK/import 边界 | `agent.sdk.Kernel` 的 create/preview/list_session_tools 等生产表面在 `src/agent/sdk/kernel.py:1105-1200,1735-1762,2172-2280`；项目架构红线与 current SDK canonical 一致，design 没让 CLI/PA import platform，也没让 IM import agent |
| child、background、permission 可复用 seam | child hook context 保留 permission requester（`runtime.py:1321-1523`）；generic background registry/task_stop/notification 为现有真路径；PA composition 实际装配 `BackgroundSubscriptionManager` 与 Web/Feishu permission sender，新增 Workflow adapter/registry 均落在生产 owner，不复制 loop 或第二审批链 |
| PA allowlist next-turn | `resolve_enabled_tools` 在 `src/personal_assistant/product.py:359-375`，session composition 在 `gateway/session_composition.py:72-103`，live config lookup 在 `composition.py:790-816`；Workflow optional pill→下一轮 snapshot 设计成立 |
| Web current surfaces | production `ToolCallsPanel` 分派 `ToolDetailBody`（`tool-calls-panel.tsx:1-8,298-312`）；`AgentCard` 的 prompt-first/pending-hide-result 在 `tool-detail-renderers.tsx:305-338`，BESPOKE/dispatch 在 `:541-626`；PillSelector、slash、PermissionCard 都有实际 import/test owner，新增窄 Workflow renderer 的落点真实 |
| Session/workspace artifact root | current SDK/canonical 已把 `workspace_config_dirname`、session workspace 和 global root 分开；delta SDK 完整保留 current 9 个装配 Scenario，design 的 `<workspace>/<config-dir>/sessions/<session-id>/workflows` 没有另造 `workflow_data_root` |
| 既有依赖/权限/worktree约束 | core→platform 禁止、同步 Tool.run 经 worker thread、effects 只经 child tools、开发 worktree runtime 不作产品 API，均与 `AGENTS.md`、`registry.py:323-366` 和 design 模块归属一致 |
| launch permission 时的 tool row | 不成立：production `ToolRegistry` 先 await intercept/gate（`registry.py:221-255`），只有 gate allow 后才 dispatch `tool_execution_start`（`:323-328`）；源码注释和对应测试明确这是为了避免 permission park 前出现 `tool_start`（`tests/unit/test_agent_loop.py:60-67`）。PA 的 `permission_request` 分支只发送批准卡（`runtime_delivery/observer.py:1633-1668`），不会 upsert tool row。design/prototype 却把“权限待决”画成已有 Workflow row + input-only detail，见 R10-C2 |

### 决策核实台账

| 决策 | 完整性 / 自洽 / grounding / spec 驱动 | 结果 |
|---|---|---|
| 1. active Workflow 单一开关 | Q3/Q4 驱动；active tool snapshot 同源生成 provider/tool/reminder/commands，running round 固定 snapshot | pass |
| 2. capture prompt 机械 Python 变换 | Q2 与 Python-only 非目标驱动；变换 ledger、保留 clause、字段 precedence 均拍死 | pass |
| 3. AST policy + 真编译 | Python 脚本与拒绝直接 OS capability 场景驱动；allowed/denied surface、checkpoint、thread/private loop 和安全边界完整 | pass |
| 4. primitives + 单 manager | parallel/pipeline/nesting/limits/ordinal 各有确定 oracle；single admission 避免 coroutine scheduling 成为契约 | pass |
| 5. 复用 child loop | inheritance、StructuredOutput、model/effort/permission/return-value 差异是窄 adapter；不复制 RuntimeRunner | pass |
| 6. journal + snapshot + generic task | 诊断/resume/query/stop 驱动；single writer、atomic notification claim、stopping→stopped 和 late terminal 覆盖明确 | pass |
| 7. chained v2 prefix resume | 同 session、key inputs/omissions、terminal release、first miss cutoff、新 run id 均拍死 | pass |
| 8. broker + parent permission route | R9 sidecar/乱序/terminal 数据流现已闭合；但 launch permission pending 的 Web tool-row 可观察契约没有现有事件来源，见 R10-C2 | partial — R10-C2 |
| 9. trusted human reminder | Q2/opt-in 场景驱动；HUMAN/WORKFLOW/automation origin、turn_system role/order、token budget 均不加第二硬门 | pass |
| 10. product-root saved discovery | project/personal/plugin precedence、symlink 不对称、命令等价 tool invocation、inactive absence 均明确 | pass |
| 11. Workflow worktree adapter | isolated child 场景驱动；detached、clean remove、dirty preserve、failure no shared-cwd fallback/no auto-merge，职责独立于 e2e adapter | pass |
| 12. SDK-only management | 五方法、SDK-owned complete snapshot、action enum/validation、同 manager instance 与不泄漏 executor/store 均明确 | pass |

### spec 约束核实台账

| spec 原子 | design/delta 落点与结论 |
|---|---|
| Q1 + all-entrypoint 用户场景 | 架构图、决策 1/8/9/12、CLI/PA/IM delta 与 M1→M2 覆盖 CLI、Web、飞书 | pass |
| Q2 + Python-only/non-goal | 决策 2/3/8/9/10 严格限制为语言适配，不增资格门、权限体系、cloud routines/hooks/agent teams | pass |
| Q3 完整能力 | 决策 3–12 覆盖 generation/runtime/primitives/background/query/control/resume/save/permission/cost/model/diagnostic；Web 通过普通 `/workflows` 回复仍可查看，不需要进度面板 | pass |
| Q4 complete active/inactive A/B | 决策 1、PA/Web surface、Gateway/IM disabled Scenario 与 runbook 明确下一轮完整出现/消失；旧 run 只留 generic terminal + known task_stop | pass |
| R1 所有入口 + complete switch（4 Scenarios） | CLI default 与 PA optional 的产品差异、next-turn snapshot 和 provider absence 都有 delta/test oracle | pass |
| R2 opt-in/ultracode（5） | trusted origin、keyword/standing reminder、ordinary no-auto、new/high reset、automation no-trigger 均覆盖 | pass |
| R3 Python script（5） | source precedence、artifact/edit/rerun、primitives、capability reject、JSON args 均覆盖 | pass |
| R4 deterministic orchestration（5） | admission/terminal ordinal、parallel barrier、pipeline item flow、Python control flow、empty-on-agent-error、transcript isolation 均覆盖 | pass |
| R5 background/progress/control（5） | async launch、SDK snapshot、CLI interactive/non-TTY、Gateway ordinary reply、pause/stop/restart/save、single terminal notification | pass；Web 无专属 panel 不缩水 query/detail contract |
| R6 prefix resume（4） | journal key、same-session prefix、edited cutoff、100% replay、cross-session cold start | pass |
| R7 save/discover/name（5） | project/personal precedence、bundled/plugin namespace、inactive disappearance | pass |
| R8 permissions（5） | launch broker/consent、bypass/unattended、child allowlist、generic child request、no mid-run human input | launch/child runtime pass；Web launch-pending presentation R10-C2 |
| R9 cost/limits/model（5） | usage/snapshot、large warning/guideline、16/1000/4096、override precedence/substitution warning | pass |
| R10 error/diagnostics（3） | pre-launch error, terminal failed with partials, artifact/run/journal locators and normal main-session continuity | pass |
| 范围/非目标 | 没有 JS runtime、额外 automatic activation、IM run projection/event/detail page/progress panel；prototype 只表达既有 chat surfaces | pass；“不新增前端组件”残留措辞与 WorkflowCard 冲突，R10-W1 |

### delta-spec 归并台账

| delta target | 用法、current merge 与可观察性核实 | 结果 |
|---|---|---|
| `cli/interactive-repl.md` | MODIFIED 精确命中 current slash Requirement并保留原 4 Scenarios，新增 `/workflows`；另 ADDED opt-in 与 background control，共 3 Requirements / 15 Scenarios | pass |
| `cli/spec.md` | current 7 + 2 ADDED = Interactive REPL 9 | pass |
| `kernel/workflows.md` | 真新增 8 Requirements / 38 Scenarios，按 SDK consumer 视角覆盖 capability/runtime/primitives/child/query/resume/save/budget | pass |
| `kernel/runs.md` | MODIFIED steer 精确保留 current 6/6 Scenarios；ADDED origin 3 Scenarios，共 2/9 | pass |
| `kernel/background-tasks.md` | ADDED Workflow cooperative stop 1/4；消费者看到 stopping/stopped/一次通知/既有 task 类型不变 | pass |
| `kernel/sdk-boundary.md` | MODIFIED assembly 从 current 重建，9/9 原 Scenario + 1 Workflow model Scenario；ADDED SDK management 3 Scenarios，共 2/13 | pass |
| `kernel/spec.md` | current SDK5/Runs12/Background5 + unit 增量 → 6/13/6；new Workflows8 | pass |
| `gateway/agent-capabilities.md` | ADDED optional/default-off/next-turn snapshot 1/4，不修改 current allowlist Requirement | pass |
| `gateway/workflows.md` | ADDED 5 Requirements / 17 Scenarios；人工来源、active command、SDK truth、parent permission、delivery cadence 均是 channel 用户可观察结果 | pass |
| `gateway/spec.md` | current Agent Capabilities 已是 12（`docs/specs/gateway/spec.md:23`），unit 再 ADDED 1，应为 13；delta 仍写 11（`:7`） | fail — R10-C1 |
| `im/agents-nodes.md` | ADDED Workflow pill 1/3；只表达保存后选择真值与 next-turn 能力 | pass |
| `im/workflows.md` | ADDED existing-chat surface 1/5 与 command/disable 1/3，共 2/8；终态/查询/permission 无专属 projection/card | partial — pending tool row受 R10-C2 影响 |
| `im/spec.md` | current Agents and Nodes 已是 23（`docs/specs/im/spec.md:26`），unit 再 ADDED 1，应为 24；delta 仍写 22（`:7`） | fail — R10-C1 |

所有 delta Scenario 的 THEN 均落在终端用户或 SDK consumer 可观察结果；没有用内部类/函数调用替代验收。`docs-check` 只检查尚未归并的 current canonical，因此当前通过不反证 R10-C1。

### Milestone 台账

| Milestone | 垂直性 / 依赖 / 范围 / 退出标准 | 结果 |
|---|---|---|
| M1 `cli-workflow-runtime` | 从 Python tool、manager/child/background/SDK 到 CLI opt-in/query/control/save/notification 的独立可交付纵切；pure/contract/provider/CLI `[worker]` 与 Luna/CLI journey `[reviewer]` 双轨完整 | pass |
| M2 `assistant-workflow-surfaces` | 在 M1 稳定 SDK/event seam 上交付 PA→Web/Feishu 完整用户入口；不复制 manager，Gateway/IM/frontend tests 与真栈/Feishu journey 双轨完整；multi-launch/乱序/重连/cleanup oracle 已进范围 | partial — package counts 与 launch-pending row 分别受 R10-C1/C2 阻断 |

两 milestone 是按“CLI runtime 可先独立交付、assistant surfaces 再消费稳定 SDK”分阶段验证，不是 data/backend/frontend 横切；M2 依赖 M1 且没有被标并行组，范围交叠不会产生并行 worktree 冲突。目录只有 `.gitkeep` 符合 skeleton 契约。

### 整体判断

| 维度 | 结论 |
|---|---|
| 人类可读上层 | 架构综述、图、模块归属与 12 条一句话决策能直接说明“deep Workflow module + thin product surfaces”；最新 Web 非目标也在 Changelog、现状、surface、prototype、test/runbook/M2 多处贯通 |
| 接口与数据流 | manager→journal/snapshot/SDK/query、manager→generic notification、child→parent permission、tool result→event_metadata→Gateway registry 已闭合；唯一未闭合的是 launch permission pending 到 tool row 的事件来源，R10-C2 |
| 自洽/命名 | run/task/call/request correlation、stopping/stopped、tool completed vs run terminal、disabled vs global rollback 一致；`design.md:349` 的“无前端组件”是与明确 WorkflowCard 冲突的残留，R10-W1 |
| 风险/回退/runbook | stop/resume/permission/worktree/query/cost 风险都有具体 owner和回退；隔离 e2e-up/down、Vite、浏览器对照和清理命令可执行；静态命令实测通过 |

### 架构进攻

| 角度 | 主动进攻结果 |
|---|---|
| 归属 | Workflow state/compiler/journal 在 core/platform，SDK 只给 snapshot/control，Gateway registry 只管 run→message delivery，IM 不持 run projection，依赖方向自然。把 machine correlation 放通用 non-model event sidecar也比让 Gateway解析 presenter正确。反例是 pending tool row：若 worker为了原型去改全局 gate顺序或在IM从 permission卡猜 tool call，会把展示需求错放到共享执行/持久层，见 R10-C2。 |
| 该不该存在 | WorkflowManager、journal/snapshot、child adapter、Gateway binding registry 均经删除测试：删除会分别丢单 writer/resume、断线真源、return/permission差异、多 launch原消息路由，因此不是YAGNI。`WorkflowCard`只是现有 renderer分派的一项，不是新产品 surface；但必须消掉“无任何前端组件”的伪禁止，R10-W1。 |
| 深还是浅 | complete snapshot+五个SDK方法隐藏 executor/store，registry隐藏乱序/multi-launch，ToolResult sidecar隐藏 raw output，均是深接口。当前 pending呈现却要求调用方知道 gate内部时序而不给事件，是浅且断裂的接缝；任何实现都会把这一复杂度泄给另一层。 |
| 治本还是补丁 | 禁止 first/latest fallback、pre-anchor buffer/tombstone、single terminal/cleanup owner正面解决 race；直接查询SDK而不建IM副本正面解决重连状态。若只让prototype“看起来有 pending row”而没有生产事件契约，则会用前端合成或全局 pre-gate `tool_start` 掩盖根因，后续每个需审批工具都承担时序回归。 |

### Issues

- [R10-C1][CRITICAL] [delta package future counts：`specs/gateway/spec.md:7`、`specs/im/spec.md:7`]: Round 9 后 current canonical 又同步了 feat-519：Gateway `Agent Capabilities` 当前是 12 Requirements（`docs/specs/gateway/spec.md:23`；实际 12 个 headings），IM `Agents and Nodes` 当前是 23（`docs/specs/im/spec.md:26`；实际 23 个 headings）。本 unit 两处各 ADDED 1 条，因此归并 future state 必须是 **Gateway 13、IM 24**，delta 仍写旧基线的 11/22。CLI 9、kernel SDK6/Runs13/Background6/Workflows8、Gateway Workflows5、IM Workflows2 仍正确。不修时 archive 合并立即产生 package index requirement-count mismatch，`docs-check` 会失败；更糟的是归并者可能按旧数字误删 feat-519 的 current Requirements。只应更新这两个派生数，不改已有 delta正文。

- [R10-C2][CRITICAL] [Web launch permission pending contract：`design.md:425-433,487,504-507,610,630`；`specs/im/workflows.md:5-19`；`prototype.html:383-386,469-493`]: 最新契约/原型要求 `permission` 状态下同一 assistant 气泡已经有 `Workflow` tool row，展开只显示 input script、无 result，下面再显示现有 `PermissionCard`；M2 也把 input-first/pending-no-result 当组件/浏览器 oracle。但生产时序明确相反：`ToolRegistry.execute()` 先 await `tool_call` intercept/permission gate（`src/agent/core/tools/registry.py:221-255`），只有获准后才 dispatch `tool_execution_start`（`:323-328`）并由 realtime/PA upsert tool row；源码测试注释还明确这是一次有意修复，避免在 gate park 前发 `tool_start`（`tests/unit/test_agent_loop.py:60-67`）。pending 的 `permission_request` 只带 request/tool/input/question/options，并只追加 PermissionCard（`runtime.py:1334-1364`、`runtime_delivery/observer.py:1633-1668`），没有 call id/tool-row upsert。因此当前设计没有任何数据源能让 `ToolCallsPanel` 在 pending 时出现该行。不修时 worker只能三选一：保留现状导致 delta/prototype/M2失败；把全局 `tool_start` 移到 gate 前导致所有被拒工具先伪装成 running并回归 bugfix-367；或在 Gateway/IM 从 permission request 合成 Workflow row（又缺 call id、引入未设计的专属状态）。三种架构不兼容。design 必须拍死唯一方案并同步 delta/prototype/test：最小复用 production 的方案是 permission pending 只显示现有 PermissionCard/raw input，allow 后才出现 input-first Workflow row；若用户必须在 pending 时也看到 tool row，则要明确新增一个通用、带 parent call id 的 pre-execution presentation seam及其所有工具/deny/replay语义，不能让 M2 worker临场猜。

- [R10-W1][WARNING] [Decision 8 与 Web renderer 边界：`design.md:349` vs `:425-433,487,541,630`]: permission-routing 段仍说 M2“不新增……前端组件”，而接口、Web、测试与 milestone 又明确要求在既有 `ToolDetailBody` 增加 `WorkflowCard` 并写组件测试。结合全文可判断用户禁止的是独立 progress/detail/permission surface，而不是禁止一个现有工具详情 renderer，所以主架构没有两解；但 worker按前一句可能跳过 renderer，按后文则新增组件，造成 scope/验收措辞打架。应把 `:349` 收窄为“不新增 Workflow 专属 permission 组件或独立产品 surface”，保留既有 ToolCallsPanel 内的 `WorkflowCard` renderer。

### Recommendations

- [R10-R1] 先回 `change-design-author` 只更新 Gateway Agent Capabilities 13、IM Agents and Nodes 24；用 current heading count + delta ADDED 重新做 future assertion，别改其余已正确数字。
- [R10-R2] 就 launch permission pending 选且只选一条生产契约。推荐最小改动：pending 沿用现有 PermissionCard（raw script 已可见），Workflow tool row 从 allow 后的真实 `tool_start` 开始；同步修 design表、IM Scenario、prototype permission state、M2 component/browser oracle。若用户坚持 pending row，必须把通用 pre-gate event/call-id/deny/replay contract 提升为 M1共享 seam并补回归范围。
- [R10-R3] 把“无前端组件”改为“无独立 Workflow surface/专属 permission 组件”，避免与 `WorkflowCard` renderer 的明确实现范围冲突。R10-C1/C2 修订会同时改 canonical派生数与共享 tool timeline契约，下一轮至少用 `delta` 重查 counts、gate→event→Gateway→IM时序、prototype和M1/M2波及；若选择全局 pre-gate event，应升级 `full`。

### Author Resolutions

- [R10-C1] Accepted：按 current canonical heading count + 本 unit ADDED 1 重算，只把 `specs/gateway/spec.md` 的 Agent Capabilities future count 改为 13、`specs/im/spec.md` 的 Agents and Nodes future count 改为 24；其余已核对数字不动。
- [R10-C2] Accepted：选择最小且与 production gate 一致的唯一方案，不新增 pre-gate presentation seam。launch permission pending 时只显示现有 `PermissionCard` 及 raw input，不显示“过程”或 Workflow tool row；免确认或用户 allow 后，真实 `tool_start` 才创建 input-first 的工具行，tool result 返回后在输入下方追加结果。已同步 presenter 表、Web surface、UX grounding、prototype contract、测试策略、Runbook、M2、IM delta 与 `prototype.html`；拒绝不合成 running 行。
- [R10-W1] Accepted：将边界收窄为“不新增独立 Workflow surface 或专属 permission 组件”，明确保留现有 `ToolDetailBody` 内的 `WorkflowCard` renderer。

## Round 11

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `delta`
- mode_reason: Round 10 有可信 full inventory；本轮只改变 launch permission pending/allow/deny 的既有 Web tool-timeline呈现，另修两处 future count 与一个组件边界措辞。影响可枚举在 `gate → permission event / ToolResult → realtime tool_end → Gateway tool_call → ToolCallsPanel/PermissionCard`、prototype、IM delta 与 M2，不改变需求范围、Workflow runtime/SDK、child background permission registry 或 milestone 拆分，因此用 delta。重查在同一 deny 波及链发现 terminal audit row 仍未闭合，无需升级 full。
- started_at: `2026-08-10T10:13:27+08:00`
- completed_at: `2026-08-10T10:15:37+08:00`
- duration: `2m10s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- changed_atoms: Gateway Agent Capabilities/IM Agents and Nodes future counts；launch permission pending 只显示 `PermissionCard`；allow/免确认后的真实 `tool_start` 才创建 Workflow row；tool-result pending/input-first/result-second；deny 不经历 running；`WorkflowCard` 是现有 detail renderer 而非独立 surface；prototype 6 states；M2 component/browser oracle。
- affected_trace: 分别追三支：`ask → permission_request → card pending`；`allow → tool_start → running row → tool_end async_launched`；`deny → ToolError(reason_code=denied, approval=user_deny) → ToolResult → tool_result observe → tool_end → terminal denied tool row`。
- retained_from: Round 10 full — 4 个澄清、10 Requirements / 46 Scenarios、其余 12 个设计决策、13 份 delta 未改条目、R9 machine correlation/乱序 registry、M1 纵切及四角度 full attack均未被本轮有界 Web launch-state 修订失效。
- static_checks: current/delta heading assertions为 Gateway `12+1=13`、IM `23+1=24`；prototype inline JS syntax通过、6/6 tab states与 deny interaction存在、permission state命中 `process.hidden=true`；相关 denial/tool-end unit tests `18 passed`；`PYTHON=.venv/bin/python; PYTHON="$PYTHON" ./scripts/docs-check` 通过（215 maintained Markdown / 67 routes）；unit `git diff --check` 通过。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R10-C1 | 只把 Gateway/IM future counts 改为 13/24 | current `agent-capabilities.md` 实测 12 headings、delta ADDED 1、index 13；current `agents-nodes.md` 23、delta ADDED 1、index 24；其他 index rows 未被这次修订改变 | closed |
| R10-C2 | 不加 pre-gate seam；pending 仅现有卡，allow/免确认后真实 tool_start 才建 row；deny 不合成 running row | pending 与 allow 链已逐层对齐 production；但现有 deny 虽不发 `tool_start`，仍必经 `ToolResult → tool_end` 形成一条 terminal denied/not-executed audit row，当前 IM delta/原型却让 deny 后完全无工具行，见 R11-C1 | superseded by R11-C1 |
| R10-W1 | 禁止独立 surface/专属 permission 组件，保留 ToolDetailBody 内 WorkflowCard | `design.md:349` 已使用收窄后的边界，接口/Web/test/M2 仍一致要求 `WorkflowCard` renderer；不再有 scope 两解 | closed |

### 本轮重查证据

| Changed atom / 波及链 | 独立核实 | 结果 |
|---|---|---|
| future count merge | `docs/specs/gateway/spec.md:23` 为 current 12，unit `gateway/agent-capabilities.md` ADDED 1，delta index `gateway/spec.md:7` 为 13；`docs/specs/im/spec.md:26` 为 current 23，unit `im/agents-nodes.md` ADDED 1，delta index `im/spec.md:7` 为 24 | pass |
| permission pending | `ToolRegistry` 在 `tool_call` intercept/gate 返回前不 dispatch observe（`src/agent/core/tools/registry.py:221-255`）；pending publisher只发送 request/tool/input/question/options（`runtime.py:1334-1364`），Gateway只追加 `PermissionCard`（`runtime_delivery/observer.py:1633-1668`）。design presenter表 `:429`、Web `:488`、UX `:508`、IM delta `:16-20` 与 prototype `process.hidden=waiting` 已一致 | pass；不需要 pre-gate event或合成 row |
| allow/免确认 → real running row | gate通过后 registry 才 dispatch `tool_execution_start`（`registry.py:323-328`），realtime 转 `tool_start`，Gateway `runtime_delivery/observer.py:1479-1541` 才 upsert running call；design `:430,434,488` 固定 input-first与 tool-result pending无结果，prototype running/launched亦对应 | pass |
| deny → terminal audit row | gate block 抛出的 `ToolError.details` 携带 `reason_code=denied` / `approval=user_deny`（`registry.py:236-255`）；executor无论未发生 tool_start 仍构造 terminal `ToolResult`（`tool_executor.py:230-277`）；loop明确“tool_start也不发，前端只在tool_result阶段渲染✕”（`loop.py:520-521`）并 dispatch result observe（`:547-549,565-583,794-828`）；realtime生成 `tool_end`（`realtime_stream.py:85-115`），Gateway无条件发送 `tool_call_completed`（`runtime_delivery/observer.py:1543-1631`）。production frontend永久测试要求 denied row显示“已拒绝”+“未执行”（`tool-calls-panel.test.tsx:1130-1143`），current canonical也要求被拒绝工具终态显示已拒绝（`docs/specs/im/tool-timeline.md:23-31`） | fail；当前 prototype `process.hidden = waiting || launchDenied`、IM delta“allow后才显示工具行”把合法 terminal denied row一并删除，R11-C1 |
| no-new-surface boundary | `design.md:349,425,488,543,632` 现统一为既有 ToolCallsPanel/ToolDetailBody 内的 WorkflowCard、现有 PermissionCard，无独立 progress/detail/permission surface | pass |
| prototype state mechanics | Node编译脚本成功；6 个 tab state与 deny按钮存在；permission隐藏process正确。deny按钮进入额外内部 `denied` state，但该 state隐藏整个process，未表现production terminal denied row | partial — R11-C1 |
| M2 scope/tests | M2 已要求 pending-only-card、allow后真实tool_start、WorkflowCard pending/result ordering；尚未要求 deny后从未running但经真实tool_end出现的 audit row | partial — R11-C1 |

### 受影响的架构进攻

| 角度 | 重查结果 |
|---|---|
| 归属 | 删除 pre-gate presentation seam是正确归属：批准待决属于现有 PermissionCard，执行中工具行属于真实 tool_start。拒绝审计则已经由 core ToolResult→通用 tool_end→现有 ToolCallsPanel拥有；若为 Workflow 在Gateway/frontend特判隐藏，会让同一 generic denial语义按工具名分叉。 |
| 该不该存在 | 本轮不需要新 event、call-id carrier或专属 UI。现有 permission request承担pending，现有 terminal tool_end承担deny，现有 WorkflowCard承担allow后的input/result；删除任一条都会丢用户可观察状态，新增第四条反而重复。 |
| 深还是浅 | `reason_code + approval` sidecar已把“未执行但须审计”封在通用 terminal result中，并被 current Gateway/frontend/canonical共同消费。prototype若把“无tool_start”误等同“无tool_end”，就是绕过这条深接口，让worker重新理解gate内部异常路径。 |
| 治本还是补丁 | 正确治本是三态分离：pending无row、allow有running→completed、deny无running但有terminal denied row。只在prototype用 `launchDenied` 隐藏process，或实现时按Workflow名字抑制tool_end，是遮掉审计证据的UI补丁；长期会让permission历史、折叠授权计数与其他工具不一致。 |

### Issues

- [R11-C1][CRITICAL] [launch deny terminal contract：`design.md:429-434,488,508,516-518,543,612,632`；`specs/im/workflows.md:16-20`；`prototype.html:383-386,469-494`]: R10-C2正确删除了 permission pending 的 pre-gate tool row，却把“deny不经过 running”错误收缩成“deny后永远没有工具行”。current production明确区分这两件事：gate deny不会发 `tool_start`，但 executor仍把 `ToolError(reason_code=denied, approval=user_deny)` 收敛为 `ToolResult`；loop注释逐字说明前端会“只在 tool_result 阶段渲染 ✕”（`src/agent/core/agent/loop.py:520-521`），随后 realtime `tool_end` 与Gateway `tool_call_completed`创建一条从未running过的terminal denied row。frontend test固定该行显示“已拒绝”和“未执行”（`src/IM/frontend/src/features/chat/components/tool-calls-panel.test.tsx:1130-1143`），current canonical `docs/specs/im/tool-timeline.md:23-31` 也要求拒绝终态可见。当前 prototype却在 `launchDenied` 时隐藏整个process，IM delta又写“用户允许后才……显示工具行”，M2没有deny audit oracle。不修时worker只能保留production而失败prototype/delta，或为Workflow特判丢弃通用tool_end，从而丢失拒绝审计、授权计数并违反current canonical；二者互不兼容。最小且production-compatible的唯一契约应是：pending只显示卡；allow后有真实running row；deny后卡消失，不曾出现running，但真实 `tool_end` 直接产生terminal Workflow denied/not-executed row，保留原输入与 `approval=user_deny`，且没有后台run/终态消息。

### Recommendations

- [R11-R1] 只回 `change-design-author` 收 R11-C1：在presenter表单列“launch被用户拒绝”状态，明确无tool_start但有tool_end terminal row；IM delta把“allow后才显示工具行”改成“pending不显示；allow走running row；deny由terminal result显示已拒绝/未执行”。
- [R11-R2] prototype的 `denied` interaction应显示process + terminal denied Workflow row（无running脉冲、无duration、gate=已拒绝、result=未执行/launch denied），仍隐藏PermissionCard且不显示background terminal message；不要新增第7个tab或新组件。
- [R11-R3] M2 worker/component/browser oracle补一条“deny从未出现running、但最终tool row可审计”，并断言production现有 `reason=denied` / `approval=user_deny` / not-executed行为。修订若只触及这些位置，下一轮可用 `closure`；不要重开已闭合counts、pre-gate seam或R9 registry。

### Author Resolutions

- [R11-C1] Accepted：三态严格分开并复用通用 tool timeline：permission pending 只有 `PermissionCard`；allow/免确认后才有真实 `tool_start` 与 running→completed；deny 不发 `tool_start`、不曾显示 running，但 executor 产出的 denied `ToolResult` 经真实 `tool_end` 直接留下“已拒绝 / 未执行”的终态 Workflow 行，保留输入与 `approval=user_deny`，没有 duration、run/task id 或后台终态消息。已同步 presenter 表、Web surface、UX grounding、prototype contract、测试/Runbook、M2、IM delta 与 prototype deny interaction；未增加第七个 tab、专属事件或组件。

## Round 12

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `closure`
- mode_reason: Round 11 已有可信的 delta inventory 和完整 `gate → ToolResult → tool_end → Gateway → ToolCallsPanel` 证据；本轮 Author Resolution 只把 R11-C1 已拍死的 deny terminal 展示契约同步到 presenter 表、Web/UX/prototype/test/Runbook/M2 和 IM delta，没有改变架构、共享接口、需求范围或 milestone 拆分，影响可封闭，因此用 closure。
- started_at: `2026-08-10T10:21:45+08:00`
- completed_at: `2026-08-10T10:23:56+08:00`
- duration: `2m11s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R11-C1 | pending 仅通用批准卡；allow 后真实 `tool_start` 才 running；deny 不 running，但 denied `ToolResult` 经真实 `tool_end` 直接留下终态审计行 | `design.md:429-435,489,509,517,544,613,633` 已一致写明三态，并在 M2 固定 `reason=denied` / `approval=user_deny`、无 duration/run/task id/后台 run；`specs/im/workflows.md:16-21` 同步可观察契约。这与现行 `registry.py:236-255`、`loop.py:517-521,547-549,565-583`、`runtime_delivery/observer.py:1543-1631` 和 `tool-calls-panel.test.tsx:1130-1143` 的通用 deny 终态链一致 | closed |

### 闭环核实证据

- `prototype.html:383-390,407-423,464-498` 保留 6 个评审 tab，deny 为卡片内 interaction 产生的内部状态；pending 隐藏 process row，deny 显示 failed tool row、“已拒绝” gate 和 `✕ 未执行 · launch denied`，tool duration 为空、批准卡消失、后台终态消息不可见；没有第七个 tab 或新 surface。
- 独立静态检查通过：protoype inline JavaScript 可编译，6/6 tab states 齐全，pending/deny 分支的行、结果、duration、permission 与 background-message 断言均成立；`PYTHON=.venv/bin/python ./scripts/docs-check` 通过（222 maintained Markdown / 67 routes）；unit 范围 `git diff --check` 通过。

### Issues

None.

### Recommendations

- [R12-R1] Gate 2 设计审查已闭环；可进入 `change-orchestrator` 实施，并按 M2 已写明的组件/真浏览器 oracle 保留 deny terminal audit row。

## Round 13

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `full`
- mode_reason: Round 12 后用户把“可归因后台原始返回”明确并入本 unit，同时覆盖 Workflow 和 `Agent(run_in_background=true)`；首文档需求/非目标、核心通知数据流、Gateway→IM 共享协议、IM 消息持久化、前端 `ProcessItem` 和两个 milestone 都发生高风险语义变化，上一轮 closure inventory 不再足以继承，因此强制 full review。
- started_at: `2026-08-10T11:17:46+08:00`
- completed_at: `2026-08-10T11:32:45+08:00`
- duration: `14m59s`

### Verdict

Issues Found — 3 CRITICAL / 0 WARNING

### Coverage

- 完整重读 `spec.md` 11 Requirements / 52 Scenarios、`design.md` 13 个决策、17 份 delta-spec、M1/M2 骨架、`prototype.html` 与 `design-review.md` 全部历史；对新增 Q5、whole-run terminal 判定、Decision 13、4 份新 delta 和 M1/M2 增量不做抽查。
- 重新追了生产真路径：`agent.core.background_tasks.notifications` → `platform.background_tasks.wiring._deliver_notification()` → `RunsRegistry` active/idle carrier → `pending_injection_consumed` / `assistant_message` → PA `BackgroundSessionEventSubscriber` / `build_bg_reply_sender()` → IM `agent.message` / `EventBridge` / `MessageRepository` → frontend `ToolCallsPanel` / `ToolDetailBody`。
- 重新核对 current canonical 中所有被 `MODIFIED` 的 Requirement 与 Scenario，并按 current heading 实数验算 future package counts。
- 原型独立静态核对：inline JavaScript 可编译，7 个可见 tabs / 8 个内部 states 齐全；desktop tool row 为 7 个可见子项列，mobile 隐藏 duration 后为 6 个可见列；Agent launch 保留 input-first/result-second，后台终态在后续普通消息的“过程”内展示，未新建 progress/detail surface。
- 用包含 4 份新 delta 的临时 index 运行 `PYTHON=.venv/bin/python ./scripts/docs-check`，通过（228 maintained Markdown / 67 routes）；unit 范围 `git diff --check` 通过。普通 working-index docs-check 只因这 4 份文件尚未 tracked 而报 8 个 broken link，属当前 staging 状态，不是文档内容结论。

### 历史问题闭环

| 历史项 | 本轮核实 | 状态 |
|---|---|---|
| R1-C1…C6 / R1-W1…W2 | 并发 ordinal/resume、canonical anchors、symlink、child model、turn-system role/order 和 milestone 两轨仍在 `design.md:131-159,214-320,362-415,687-696` 与现有 deltas 中保持闭合；新 sidecar 不改写它们 | retained closed |
| R2-C1 / R2-W1，R4-W1 | CLI/kernel/Gateway/IM index rows 已补齐，runbook 仍用 shell wrapper，production locator 仍指向 `PillSelector` / `agent-detail-page.tsx`；新 area counts 本轮重算见 delta 台账 | retained closed |
| R6-C1…C4 / R6-W1 | SDK current canonical、cooperative `stopping→stopped`、manager single terminal writer / atomic notification claim、parent generic permission consumer 和 disabled 语义仍闭合；`design.md:302-304,320-360,432,500` 还明确 Bash 现有行为不变 | retained closed |
| R7-C1 / R8-C1 / R9-C1 | launch message anchor、run/call/request 精确 binding、pre-anchor buffer / closing tombstone、`event_metadata` machine correlation 和唯一 cleanup consumer 仍在 `design.md:320-360`；新 background-return 不重开 permission registry | retained closed |
| R10-C1…C2 / R10-W1，R11-C1，Round 12 | current counts 再次以 heading 实数核对；permission pending / allow / deny 三态仍与生产 gate→tool_end 一致；原型只因新需求增加 `Agent 后台完成` tab，没有改回 pre-gate row 或新 permission surface | retained closed; Round 12 approval is superseded only by the new scope |

### 核实台账·现状断言

| 原子 | 独立核实证据 | 结论 |
|---|---|---|
| active tool 快照同时控制 schema/prompt | `src/agent/core/agent/prompt_sections/base.py:44-114` 的 immutable `PromptContext.available_tools/has_tool()`，与 `design.md:112-130` 的唯一开关一致 | 成立 |
| 产品只经 SDK 使用内核 | `src/agent/sdk/kernel.py:230-250` 是唯一 composition root；`tests/contract/test_agent_sdk_boundary_contract.py:19-57` 和 `test_core_no_platform_imports.py:13-20` 守边界 | 成立 |
| child Agent 与现有 loop 可复用 | `src/agent/sdk/kernel.py:106-227`、`src/agent/platform/background_tasks/runtime_runner.py:28+`、`src/agent/platform/tools/builtins/agent.py:210+` 是 production wiring，无平行 Agent loop | 成立 |
| generic background registry 可作顶层 handle | `src/agent/core/background_tasks/models.py:10-59` 和 `platform/background_tasks/wiring.py:50-103` 表明它仅持有 task record/stop/notification，适合增 `WORKFLOW` 而不承担 journal | 成立 |
| 批准链已有唯一 broker 与通用 UI | `src/agent/platform/permissions/broker.py:102+`、`runtime_delivery/observer.py:1543+`、`frontend/.../permission-card.tsx:75+` 是实际路径 | 成立 |
| PA tool allowlist 是真白名单/optional 投影 | `src/personal_assistant/product.py:359-378`、`gateway/session_composition.py:47-101`、`reporter/capability_projection.py:34-53` | 成立 |
| Web 现有表面可复用 | `tool-calls-panel.tsx:33-75,88-175` 已有 per-message process union/seq/summary；`tool-detail-renderers.tsx:303-337,542-617` 已有 input-first `AgentCard` 与 typed dispatch；`message-pane.tsx:1458-1477` 装配 panel/card | 成立，原型与此 grounding 一致 |
| notification 当前只有 XML 投影 | `src/agent/core/background_tasks/notifications.py:18-51` 从 record 渲染 XML，`platform/background_tasks/wiring.py:155-200` 只传 `LLMMessage`/`source_task_id` | 成立，Decision 13 的同源 projection 有真 seam |
| active/idle 通知有两条 carrier | `wiring.py:162-170` 注入 active run，`:193-200` 为 idle run submit；`loop.py:617-623,764-792` 只在真正 drain 后发 consumed event | 基本成立，但 terminal-stranded 分支未被设计收口，见 R13-C2 |
| PA idle background reply 当前是纯文本 | `background_subscriptions.py:181-206` 只提取非空 `content`，`runtime_delivery/background.py:177-213` 只传 `{text,to,from_session_id}` | 成立，扩展点真实；空正文协议未闭合，见 R13-C3 |
| IM 消息可持久新 sidecar 并共享 seq | `domain/models.py:204-325`、`repositories/messages.py:627-710,777-807` 已有 message-owned thinking/tool JSON 和唯一 seq 分配模式 | 成立，增 nullable JSON 比新 repository 更自然 |
| workspace-aware session root | `src/agent/core/session/jsonl_files.py:12-42,90-93` 从 `workspace_root/workspace_config_dirname` 派生，`build_kernel:674-680` 真实装配 | 成立，不需要 `workflow_data_root` |

### 核实台账·决策

| 决策 | 核实动作 / 证据 | 结论 |
|---|---|---|
| D1 active tool 唯一开关 | 对照 Q3/Q4 (`spec.md:27-34`)、`PromptContext.has_tool()` 与 PA allowlist 真路径 | 拍死、不与 disabled 语义冲突 |
| D2 逐字 capture 只做 Python 机械变换 | 对照 Q2 与 `design.md:131-157` 的 capture/provenance/clause inventory | 拍死，无 surrogate prompt |
| D3 AST 辅助 + 真编译执行 | 对照生成/编辑/权限非目标和 `design.md:159-212` 的 capability globals | 闭合，未把 AST 当安全容器 |
| D4 primitives 全进同一 manager | 逐项对照 parallel/pipeline/runtime branch/limits 与 run-global ordinal (`spec.md:124-149`) | 闭合 |
| D5 复用 child loop + return-value contract | 对照 child `None`、structured output、model/effort 与当前 AgentTool/RuntimeRunner | 闭合；whole-run 不按 child `None` 误判 |
| D6 journal + atomic snapshot / single terminal writer | 对照 `spec.md:142-145,151-174,303-311`；`design.md:265-304` 明确 stop 优先、顶层 exception failed、normal return completed | 闭合，whole-run 三态无文本质量猜测 |
| D7 chained-v2 最长相同前缀 | 对照 resume 4 Scenarios 和 ordinal/journal 契约 (`design.md:306-318`) | 闭合 |
| D8 通用 launch/child permission 回父交互面 | 重查 broker、parent event、message anchor、registry ordering/cleanup (`design.md:320-360`) | 历史 R6-R9 闭环仍有效 |
| D9 仅信任人工入口生成 reminder | 对照 opt-in 5 Scenarios、turn-system role/order 与 Runs origin delta | 闭合 |
| D10 product roots 发现/saved command | 对照 save/discovery 5 Scenarios、disabled next-turn 和 symlink 不对称规则 | 闭合 |
| D11 Workflow 自有短生命 git adapter | 对照 isolation 只属 child tool layer、不复用开发 E2E worktree (`design.md:390-398`) | 属性正确，无多余产品 API |
| D12 SDK 只暴露 query/control/save | 对照 current SDK boundary canonical 和 `specs/kernel/sdk-boundary.md` 完整 MODIFIED | 闭合，manager 未泄漏 |
| D13 task notification structured sidecar | 正向追 projection→active/idle→Gateway→IM→frontend，并反向强制 terminal race / empty-body 两条路径 | 归属和主路径合理，但 terminal-stranded 与 idle empty-body 边界未拍死，见 R13-C2/C3 |

### 核实台账·spec 约束

| 原子 | design 投影 | 结论 |
|---|---|---|
| Q1 三个产品入口 | SDK runtime + CLI M1 + PA/Web/飞书 M2 (`design.md:98-108,687-696`) | 覆盖 |
| Q2 只抄 Claude Code，仅 JS→Python | D2-D7/D9-D11 与 non-goal 逐项限制 | 不越界 |
| Q3 完整能力 + tool 控制提示 | D1-D12 与 CLI/Gateway/IM deltas | 覆盖 |
| Q4 disabled 后全部专属入口消失 | D1/D9/D10、Web surface 和 Gateway/IM disabled Scenarios | 覆盖，仅 generic terminal + 已知 task stop |
| Q5 本 unit 同时展示 Workflow/Agent 后台原始返回 | D13、Web/prototype、M1/M2、kernel/Gateway/IM deltas | 主路径覆盖，但受 R13-C2/C3 阻断 |
| 用户场景 1：明确 opt-in 才大规模编排 | D1/D9 + CLI/Gateway origin | 覆盖 |
| 用户场景 2：Python script/child effects/背景运行/终态返回 | D3-D6 + D13 | 覆盖，carrier 终态竞态见 C2 |
| 用户场景 3：background Agent 保留 launch row，后续普通回复显原始返回 | D13 presenter/Web/prototype | 覆盖，idle 空正文见 C3 |
| 用户场景 4：control/resume/save/各入口 | D6-D8/D10-D12 | 覆盖 |
| 用户场景 5：下一轮 tool selection A/B | D1/D9/D10 + M2 | 覆盖 |
| R1 入口/能力开关（4 Scenarios） | D1，CLI/Gateway/IM capability deltas | 覆盖 |
| R2 opt-in/ultracode（5） | D2/D9，Runs origin + CLI/Gateway deltas | 覆盖 |
| R3 Python script（5） | D2-D4，kernel workflows delta | 覆盖 |
| R4 确定性编排（6） | D4-D6，含 whole-run terminal | 覆盖，top-level normal/exception/stop 已拍死 |
| R5 后台进度/控制（5） | D6/D8/D12，CLI/Gateway command surface | 覆盖 |
| R6 Web 后台返回（5） | D13 + 4 条 carrier/persistence/frontend dataflow | 不完全；C2/C3 |
| R7 resume（4） | D6/D7 | 覆盖 |
| R8 save/discovery（5） | D10/D12 | 覆盖 |
| R9 permission（5） | D8 + R6-R11 历史闭环 | 覆盖 |
| R10 scale/cost/model（5） | D4-D6 + runtime/snapshot | 覆盖 |
| R11 errors/diagnostics（3） | D3/D6/D7 | 覆盖，child `None` 不误判 whole-run failed |
| 非目标 | JS/TS、额外激活/权限、cloud routines/hooks/teams、Bash 新可视化、AgentCard 改版、外部 IM 新卡、独立 progress/detail page | design 均显式排除；原型只复用现有 process/tool visual grammar | 不越界；但 delta 必须同时保留 Bash 现有文本行为，见 C1 |

### 核实台账·delta-spec

| delta | 类型 / 数量 | canonical 锚定与可观察性 | 结论 |
|---|---:|---|---|
| `cli/interactive-repl.md` | MODIFIED 1 + ADDED 2 / 15 Scenarios | 精确命中 current slash title，保留 4 旧 Scenarios 后增 Workflow | 通过 |
| `cli/spec.md` | index | current 7 + 2 ADDED = future 9 | 通过 |
| `kernel/workflows.md` | ADDED 8 / 39 | 新 canonical area；consumer-visible SDK/runtime/control/save/budget 结果 | 通过 |
| `kernel/runs.md` | MODIFIED 1 + ADDED 1 / 9 | current steer 6 Scenarios 全保留，新 origin 独立 | 通过 |
| `kernel/sdk-boundary.md` | MODIFIED 1 + ADDED 1 / 13 | 从 current 9 Scenarios 重建，保留 global/config-dir 语义 | 通过 |
| `kernel/background-tasks.md` | MODIFIED 1 + ADDED 1 / 10 | title 命中，但 MODIFIED 静默删除 current auto-background subagent Scenario | 失败；R13-C1 |
| `kernel/spec.md` | index | SDK 5+1=6，Runs 12+1=13，Background 5+1=6，Workflows 8 | 数字通过；受 C1 merge body 阻断 |
| `gateway/agent-capabilities.md` | ADDED 1 / 4 | optional Workflow 开关为平行新 Requirement | 通过 |
| `gateway/workflows.md` | ADDED 5 / 17 | human origin/capability/query/control/permission/terminal 均对用户可观察 | 通过 |
| `gateway/routing-delivery.md` | MODIFIED 1 / 4 | 命中 current title，但把 current background Bash 文本回复场景缩为 subagent/Workflow | 失败；R13-C1 |
| `gateway/relay-protocol.md` | ADDED 1 / 3 | active/idle 使用现有 event/message type，THEN 是协议消费者可观察 | 主体通过；empty text 语义见 C3 |
| `gateway/spec.md` | index | Routing 14、Capabilities 12+1=13、Relay 13+1=14、Workflows 5 | 通过 |
| `im/agents-nodes.md` | ADDED 1 / 3 | Workflow optional pill 是平行能力 | 通过 |
| `im/workflows.md` | ADDED 2 / 8 | 现有 permission/tool/message/slash surfaces，无专属 run projection | 通过 |
| `im/gateway-relay.md` | MODIFIED 1 / 4 | 命中 current title，但同样丢掉既有 background Bash 实时文本气泡保证 | 失败；R13-C1 |
| `im/tool-timeline.md` | MODIFIED 1 / 5 | Requirement title 与 current 不同，且没有忠实保留“无思考但有 tool 时不出思考空壳” Scenario | 失败；R13-C1 |
| `im/spec.md` | index | Agents 23+1=24，Gateway Relay 11，Tool Timeline 8，Workflows 2 | 数字本身通过；Tool Timeline title 未命中时实际 future 会变 9，见 C1 |

### 核实台账·Milestones

| Milestone | 核实 | 结论 |
|---|---|---|
| `M1-cli-workflow-runtime` | 核心 runtime→SDK→CLI 是可独立使用的纵向切片，超单 worker 窗口的拆分举证明确；worker/reviewer 两轨、whole-run、single notification 和 active/idle 都有 oracle | 切片成立；但 active 通知跨 terminal 的搬运分支/test 缺失，R13-C2 必须回到 M1 |
| `M2-assistant-workflow-surfaces` | 依赖 M1 稳定 SDK/sidecar 后接 PA/IM/Web/飞书，为第二个产品纵向切片；已含 permission ordering、reconnect/dedupe、empty body、prototype browser 两轨 | 切片成立；但 idle empty-body 线协议与 sender 缺决策，R13-C3 会让 M2 worker 猜接口 |

### 整体判断

- 上层方向清晰：只有一份 terminal record projection，XML 给 model、structured sidecar 跟实际消费轮次到产品，IM 只存消息从属数据，不存 Workflow run 第二真源。
- whole-run 终态已完整拍死：whole stop 优先 `stopped`，顶层未捕获异常才 `failed`，`main()` 任何正常返回都 `completed`；child `None`/空值/低质量不是失败判据。
- UX 选择合理：Workflow launch 在现有 `ToolCallsPanel/ToolDetailBody`、Agent launch 保持 production `AgentCard`，终态 raw return 为 process union 第三类；无专属面板、详情页、event 或卡片。
- 不过，delta 并入会回归 current 行为，两个高风险 carrier 分支又没有形成可兼容的跨包接口；当前不能交给 orchestrator。

### 架构进攻

| 角度 | 主动攻击 | 发现 |
|---|---|---|
| 归属 | 问“raw return 应由 Workflow manager、Gateway 还是 generic notifier 解释”，并叠加 `core←platform←sdk/product` 依赖约束 | generic notification projection 作 semantic owner 最自然；Gateway 只搬运、IM 只持久/呈现。但 stranded carrier 与 idle wire validation 正处于责任交界，不拍死会丢数据，见 C2/C3 |
| 该不该存在 | 删除测试：尝试去掉 `BackgroundReturnInfo`、IM JSON sidecar、Workflow permission registry、WorkflowCard | projection/sidecar 分别避免 XML/prose 反解析和第二 run 真源，registry 解决已取证多 launch 乱序，WorkflowCard 仅是现有 detail dispatch renderer；都有实际简化，不是 YAGNI |
| 深还是浅 | 对比“一份 projection + 现有 carrier”与“Gateway 重解 XML / IM 建 run repo / 前端伪 ToolCall” | 当前设计集中隐藏 terminal record 细节，并复用 existing event/message/process seam，比替代方案更深；没有浅 wrapper 新问题 |
| 治本还是补丁 | 攻击是否仅把 parsed XML 塞进 UI，以及是否为 Workflow 新造专属 relay | 从 terminal record 同源投影治的是“原始返回不可归因”根因；禁止 IM run projection/event 也避免了补丁化。剩余 C2/C3 是必须正面完成的共享 carrier 契约，不能用 placeholder text/“最新气泡”猜测绕过 |

### Issues

- [R13-C1][CRITICAL] [delta-spec canonical merge：`specs/kernel/background-tasks.md:5-41`、`specs/gateway/routing-delivery.md:5-29`、`specs/im/gateway-relay.md:5-27`、`specs/im/tool-timeline.md:5-28`]：4 份 `MODIFIED` 没有忠实保留 current canonical。具体是：① kernel Background Tasks 删掉了 current “前台 subagent 超预算转后台后仍发一次完成通知”（`docs/specs/kernel/background-tasks.md:40-44`），尽管新 Scenario 自己还声称覆盖 auto-background；② Gateway Routing 把 current background Bash 例子 `run_in_background: sleep ...` 的第二条文本回复保证（`docs/specs/gateway/routing-delivery.md:294-306`）缩为 subagent/Workflow；③ IM Gateway Relay 也把 current 任意 background task 的实时终态文本气泡（`docs/specs/im/gateway-relay.md:116-128`）缩为 subagent/Workflow，与 `design.md:432` “Bash 文本投递不变”直接失配；④ IM Tool Timeline 把 canonical 精确标题“内部 IM 把思考与工具调用展示为过程时间线、外部不展示”改了标题，导致 MODIFIED 无法命中，同时还删掉 current “无思考时不出思考空壳” Scenario（`docs/specs/im/tool-timeline.md:187-199`）。不修时 archive merge 会静默回归 auto-background subagent/Bash 现有用户契约，Tool Timeline 则会新旧两条并存、future count 从写下的 8 变成 9；worker 也可能误把“Bash 无新 sidecar”实施成“Bash 无原有文本通知”。必须从每份 current canonical 完整重建 MODIFIED：标题精确不变，原 Scenario 全保留，再叠加 subagent/Workflow sidecar；Bash 仍只是无 UI sidecar，不是无文本完成回复。
- [R13-C2][CRITICAL] [Decision 13 active carrier / M1：`design.md:434-438,599,693`]：设计只覆盖 `PendingMessage` 被正常 loop drain 时的 `pending_injection_consumed` 路径，没有规定“active 注入已接受，但 run 在下一 round boundary 前异常终止/被 `/stop`”时 sidecar 如何继续跟随真正消费它的 reply。当前内核对文本已有两条不丢分支：非用户终止在 `_settle_terminal_pending()` 把 stranded `PendingMessage.message` 转成 continuation `submit()`（`src/agent/core/runs/registry.py:550-609`）；用户 `/stop` 把整个 PendingMessage 暂存 `_held_pending`，下次 submit 又只把 `pending.message` 转 parts（`:196-201,302-313`）。Decision 13 新加的 `background_return` 若不显式进入 continuation/held flush 的 `source_background_returns`，XML 会存活，结构化 sidecar 却会丢失或被挂到更晚的无关回复，直接违反 `spec.md:194-200` 的同消息归因/exact-once。设计必须拍死：PendingMessage sidecar 与 message 同命运穿过 `_settle_terminal_pending` 与 `_held_pending`；非用户 continuation 按 FIFO batch 传入 `source_background_returns`；`/stop` held sidecar 在下一次真正消费它的 submit/reply 中携带。M1/M2 永久 oracle 必须强制 terminal-before-boundary 和 `/stop` held flush，包含多条 FIFO，不能只测平稳 active/idle。
- [R13-C3][CRITICAL] [Decision 13 idle relay / Gateway relay delta / M2：`design.md:437-440,602-603,694`]：文档在前端端已拍死“非空 `background_returns` 本身算可见，正文为空也保留”，但 idle `assistant_message → agent.message → IM` 的发送/协议端仍被描述为“既有文本 payload 外加 sidecar”，没有明确 `text` 在 sidecar 非空时可为空。现行生产链会在三处拦掉它：`BackgroundSessionEventSubscriber` 对空 `content` 直接 return（`src/personal_assistant/gateway/background_subscriptions.py:186-190`），`build_bg_reply_sender` 再对空 text return（`runtime_delivery/background.py:177-180`），IM relay `_require_text` 和 `EventBridge.emit_instant_message` 又要求非空（`src/IM/ws/gateway/relay.py:194-196`、`ws/gateway/protocol.py:223-226`、`application/event_bridge.py:73-105`）。不修时 worker 会在“继续丢消息”、“伪造占位文本”、“绕过 agent.message 直写 IM”之间猜测，第一种直接违反验收，后两种会建出不同协议/幂等路径。必须在 Decision 13 与 `specs/gateway/relay-protocol.md` 拍死唯一共享契约：`agent.message` 在 `background_returns` 非空时允许 empty `text`；subscriber/sender 的 visibility gate 为 `text.strip() or background_returns`；IM relay/EventBridge/MessageRepository 只在 sidecar 非空时使用既有 `allow_empty` 能力，同一 `message.created` 完整携带 sidecar。再增 idle + empty text + realtime/history/replay 的 protocol/integration oracle；外部 IM 仍按非目标不收 sidecar，无文本时也不伪造卡片。

### Recommendations

- [R13-R1] 回 `change-design-author` 先收 R13-C1：四份 MODIFIED 都以 current canonical 标题/全 Scenario 为底稿重建，然后只叠加 Workflow/subagent structured-return 增量；重跑 heading/future-count assertion 和临时-index docs-check。
- [R13-R2] 在 Decision 13 的 active/idle 列表中增第 3 条 terminal-stranded carrier，明确 normal drain、non-user continuation、`/stop` held 三条都使用同一 sidecar 并归因到实际消费 reply；同步 M1/M2 tests。
- [R13-R3] 把 idle wire contract 补成 `text-or-background_returns` 可见性契约，点名 subscriber、sender、`agent.message`、EventBridge/repository 四层，不使用 zero-width/placeholder 文本，不新建 wire event。
- [R13-R4] 保留现有原型语义：7 个 tabs/8 states、desktop/mobile grid、AgentCard-like input-first/result-second、普通消息 + background-return 过程项；这些已通过本轮复核，不需为修 C1-C3 新造 UI。

### Author Resolutions

- [R13-C1] Accepted：4 份 MODIFIED 已从 current canonical 完整重建。kernel 恢复“前台 subagent 超预算转后台”场景；Gateway Routing 与 IM Gateway Relay 明确保留 background Bash 的第二条实时文本回复；IM Tool Timeline 恢复 canonical 精确标题、原多思考/工具、无思考空壳和外部 channel 场景，再叠加 background-return。future counts 不变。
- [R13-C2] Accepted：Decision 13 已明确 `PendingMessage.background_return` 与 XML 同命运穿过三条 active 路径：正常 drain、非用户 terminal 的 contiguous-origin continuation `source_background_returns`、用户 `/stop` 的完整 `_held_pending` 与下一次 submit flush；kernel delta、测试策略及 M1/M2 均增加 terminal-before-boundary、held flush、多条 FIFO 和 task-id exact-once oracle。
- [R13-C3] Accepted：idle 共享协议已固定为 `text.strip() or background_returns`。subscriber、reply sender 不再先丢空正文；`agent.message` 只要求非空 text 或非空 typed sidecar，IM relay/EventBridge/repository 仅在 sidecar 非空时复用 allow-empty seam，并由同一 `message.created` 完整发布；两者皆空仍拒绝，外部 IM 无文本时不伪造占位或卡片。Gateway/IM delta、测试策略、风险和 M2 已同步。

## Round 14

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `delta`
- mode_reason: Round 13 已有可信 full inventory；本轮 Author Resolutions 只修 4 份 MODIFIED canonical merge、Decision 13 的 terminal-stranded carrier，以及 idle `text-or-background_returns` 共享 wire 契约，影响可枚举在对应 delta、测试策略和 M1/M2。重查没有发现这些原子使其余 Workflow runtime、permission registry、Web presenter 或 prototype inventory 失效，因此用 delta；但 Gateway relay delta 新写入实现走查，按 delta-spec 红线独立报阻塞项。
- started_at: `2026-08-10T11:38:35+08:00`
- completed_at: `2026-08-10T11:42:11+08:00`
- duration: `3m36s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- changed_atoms: R13-C1 的 4 份 MODIFIED canonical merge；R13-C2 的 normal drain / non-user continuation / `/stop` held-flush 三条 active carrier；R13-C3 的 subscriber→sender→`agent.message`→IM repository/EventBridge empty-text sidecar 通路；对应 kernel/Gateway/IM delta、测试策略、风险与 M1/M2。
- affected_trace: `terminal record → notification XML + sidecar → PendingMessage → normal boundary | terminal continuation | /stop held flush → consuming reply`；以及 `idle assistant_message → Gateway agent.message(text-or-sidecar) → IM message persistence → single message.created → history/reconnect`。
- retained_from: Round 13 full — 11 Requirements / 52 Scenarios、其余 13 份 delta、现状源码 grounding、whole-run terminal 判定、permission correlation/cleanup、Web `ProcessItem`/prototype 和两个纵向 milestone 的其余范围，均未被本轮有界修订失效。
- static_checks: 以包含新 delta 的临时 index 运行 docs-check 通过（228 maintained Markdown / 67 routes）；prototype inline JavaScript syntax 通过；unit `git diff --check` 通过。本轮不重开已通过的 prototype/UI 语义。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R13-C1 | 4 份 MODIFIED 从 current canonical 重建，恢复 auto-background subagent、Bash 文本回复与 Tool Timeline 原标题/三场景 | `kernel/background-tasks.md:5-53` 保留 current 5 个场景后叠加 3 个 sidecar 场景；`gateway/routing-delivery.md:5-35`、`im/gateway-relay.md:5-37` 均显式保留 Bash 与原重启/重发语义；`im/tool-timeline.md:5-40` 精确命中标题并保留原三场景 | closed |
| R13-C2 | sidecar 与 XML 同命运穿过 normal drain、non-user terminal continuation 和 `/stop` held flush；补 FIFO/exact-once oracle | `design.md:435-441` 已指定三条 carrier 及实际 consuming reply；kernel delta `:49-53`、测试策略 `design.md:602,605-606`、M1/M2 `:697-698` 均覆盖 terminal-before-boundary、held multi-FIFO 与 task-id exact-once | closed |
| R13-C3 | idle 链统一 text-or-sidecar，both empty 拒绝，sidecar-only 走同一 message.created，外部不伪造空消息 | runtime/interface 决策在 `design.md:439-445`、测试与 M2 已闭合；IM consumer delta `specs/im/gateway-relay.md:34-37` 也正确。但 Gateway delta 把内部类、visibility gate 与 repository 路径写进 Scenario，见 R14-C1 | runtime/interface closed; delta-spec superseded by R14-C1 |

### 本轮重查证据

| Changed atom / 波及链 | 独立核实 | 结果 |
|---|---|---|
| R13-C1 canonical merge | 四个 Requirement 标题均精确命中 current。kernel 恢复前台 subagent 超预算转后台；Gateway/IM relay 恢复 background Bash 第二条实时文本回复；Tool Timeline 恢复多思考/工具、无思考空壳、外部 channel 三个原场景，再追加 background-return | pass |
| future package counts | current heading + delta ADDED 重算：kernel Background Tasks `5+1=6`；Gateway Routing `14`、Relay `13+1=14`；IM Gateway Relay `11`、Tool Timeline `8`；各 package index 行与此一致 | pass |
| terminal-before-boundary | `design.md:438` 明确 `_settle_terminal_pending()` 按 contiguous-origin/FIFO 搬 `source_background_returns`，`/stop` 暂存完整 PendingMessage 并在下次 submit 合并；`specs/kernel/background-tasks.md:49-53` 把 XML+sidecar 同命运、FIFO 和 task-id once-only 写成消费者可观察结果 | pass；R13-C2 根因闭合 |
| idle empty-text runtime contract | `design.md:439-441` 给 sender/wire/storage 唯一契约：非空 text 或 typed sidecar、both empty 拒绝、sidecar-only 复用 allow-empty seam、单次 `message.created`、task-id merge；`design.md:605-606,622-623,698` 有 protocol/integration/replay oracle | pass；worker 无需在丢消息、占位文案和旁路写库之间猜 |
| idle empty-text delta | IM delta从用户视角写“接受并持久化、同一 message.created、刷新恢复、无占位”；Gateway delta却在 WHEN/THEN 逐层点名 `BackgroundSessionEventSubscriber`、reply sender、visibility gate 和 EventBridge/repository | fail；R14-C1 |

### 受影响的架构进攻

| 角度 | 重查结果 |
|---|---|
| 归属 | terminal projection 的 semantic owner 仍是 generic notifier，Gateway 只搬运、IM 只持久/呈现；Decision 13 把 terminal race 与 empty-text boundary 放在正确 owner。内部 subscriber/repository 的实现归属应留在 design/test，不能变成 Gateway canonical 消费者契约。 |
| 该不该存在 | `source_background_returns` 和 typed wire sidecar 分别解决 terminal-stranded 丢归因与 XML/prose 反解析，删除都会破坏 exact-once/可归因需求；没有新增 Workflow event、IM run repository 或占位消息。 |
| 深还是浅 | text-or-sidecar 是一个共享、单一的消息可见性接口，隐藏了各层旧的 text-only validation，方向足够深；若 canonical Scenario 把每层 class/helper 固化，反而会把深接口重新摊平成实现清单，使将来等价重构也被误判为契约回归。 |
| 治本还是补丁 | R13-C2/C3 已从 carrier/validation 根部消除 sidecar 丢失，没有靠“最新气泡”、placeholder 或直写数据库补洞。剩余问题只需把 delta 改回可观察 wire/postcondition，不能为了修文档撤回已经正确的 runtime 决策。 |

### Issues

- [R14-C1][CRITICAL] [Gateway relay delta 的 Scenario 实现层越界：`specs/gateway/relay-protocol.md:13-18`]：R13-C3 已在 design 中拍死正确的共享接口，但 delta 的“idle parent 正文为空时按 sidecar 可见”把实现走查写进 canonical：WHEN 点名 `BackgroundSessionEventSubscriber` 与后台 reply sender，THEN 又要求“两层按 `content.strip() or background_returns` 判定”并点名 EventBridge/message repository。`docs/specs/CONTRIBUTING.md:24,35-40,87-91` 明确 HOW、函数/类名和内部结构留在 design/code，Scenario 的 WHEN 是消费者动作、THEN 是消费者可观察结果；`change-design-reviewer` 也将 THEN 内部函数/类/调用断言定为 CRITICAL。该写法会把可替换的 PA/IM 内部组成误升级为长青 Gateway 契约，未来即使 wire 行为完全不变，重构 subscriber 或 repository 仍会虚假违反 canonical；同时真正的消费者——IM service——要观察的 frame/postcondition反而被实现清单遮蔽。最小修复不是改 Decision 13，而是把场景改为纯 wire 行为：Gateway 有一条 empty text + non-empty typed `background_returns` 的 idle 后台回复时，经既有 `agent.message` 发送；接收方得到一次 `text:""` + 完整 sidecar，IM 产生一次可持久/可重连的 `message.created`；both empty 拒绝，且不新增占位文本或 wire event。具体 subscriber/sender/EventBridge/repository 与 allow-empty seam 继续只留在 design 和测试。

### Recommendations

- [R14-R1] 仅回 `change-design-author` 改写 `specs/gateway/relay-protocol.md:13-18`：GIVEN/WHEN/THEN 使用 Gateway wire consumer 可观察的输入、单次投递/重连结果与拒绝条件，删除内部类名、逐层 gate 和 repository 路径。
- [R14-R2] 不修改 R13-C2/C3 的 runtime/interface 决策、IM delta、M1/M2 或 prototype；这些已经闭合。修订若只触及这一场景，下一轮可用 `closure`。

### Author Resolutions

- [R14-C1] Accepted：仅将 Gateway relay delta 的 empty-text Scenario 改写为消费者可观察的 wire 输入与结果：既有 `agent.message` 发送 `text:""` 和完整 sidecar，IM 在原会话单次创建并持久化终态消息，在线实时收到且刷新/重连可恢复；both-empty 明确拒绝，不出现占位文本或新增 wire event。内部 subscriber、sender、EventBridge、repository 与 visibility gate 仍只保留在 design/test，未改 runtime/interface 决策、IM delta、M1/M2 或 prototype。

## Round 15

### Metadata

- reviewer: `/root/feat_517_design_reviewer_failover`
- review_mode: `closure`
- mode_reason: Round 14 的唯一未闭合项 R14-C1 只要求把一个 Gateway delta Scenario 从内部实现走查改回消费者可观察的 wire 契约；本轮实际修订局限于该场景和 Author Resolution，没有改变 runtime/interface、IM delta、M1/M2 或 prototype，影响可完全封闭，因此用 closure。
- started_at: `2026-08-10T11:45:47+08:00`
- completed_at: `2026-08-10T11:46:49+08:00`
- duration: `1m02s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R14-C1 | 仅把 Gateway relay 的 empty-text Scenario 改为 `agent.message` wire 输入与 IM 可观察结果，移除内部类、逐层 gate 和 repository 走查 | `specs/gateway/relay-protocol.md:13-18` 现在以 Gateway/IM 协议消费者为主语：输入是 `text:""` + 完整 sidecar，结果是原会话单次终态消息、同一 `message.created` 实时送达、历史刷新/重连恢复、both-empty frame 拒绝且无占位/新 event；全文不再出现 `BackgroundSessionEventSubscriber`、reply sender、`content.strip()`、EventBridge、MessageRepository/repository 或 `allow_empty`。这符合 `docs/specs/gateway/spec.md:5` 的消费者边界及 `docs/specs/CONTRIBUTING.md:24,35-40,87-91` 的 Scenario 可观察性纪律 | closed |

### 直接证据

- 修订没有撤回 R13-C3 已闭合的唯一共享契约：wire 仍是 text-or-sidecar、both empty 拒绝、sidecar-only 只产生一次可持久/可重连的既有消息；没有新增 wire event、占位文本或内部实现约束。
- 临时 index 下 docs-check 通过（228 maintained Markdown / 67 routes），unit cached diff-check 通过；prototype inline JavaScript syntax 通过。closure 范围内没有发现新的波及项。

### Issues

None.

### Recommendations

- [R15-R1] Gate 2 设计审查已闭环；可进入 `change-orchestrator` 实施，并保留 M1/M2 已冻结的 terminal-stranded、empty-text sidecar、replay/exact-once 与真实产品旅程 oracle。

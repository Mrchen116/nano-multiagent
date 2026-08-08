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

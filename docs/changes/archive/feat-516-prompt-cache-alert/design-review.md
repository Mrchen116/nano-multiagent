# Design Review: feat-516-prompt-cache-alert

## Round 1

### Metadata

- reviewer: `feat_516_design_reviewer`
- review_mode: `full`
- mode_reason: `R1`；首次独立审查，按五类承重原子与四个架构进攻角度完整复核。
- started_at: `2026-08-07T16:59:52+08:00`
- completed_at: `2026-08-07T17:05:47+08:00`
- duration: `5m 55s`

### Verdict

Issues Found — 1 CRITICAL / 3 WARNING

`AgentLoop` 的 per-call 落点、Gateway metadata 边界、固定阈值和日志字段方案本身都合理；但 Anthropic 真实 SSE 的缓存 usage 尚未在设计中闭合。照现方案实施，很容易让本地 fixture 把缓存字段塞进 terminal frame 而测试变绿，真实流中却把 provider 已报告的缓存命中当作“缺失”并静默跳过告警。另有一处 turn 聚合语义与两项 canonical/E2E 收尾义务未被纳入范围。

### Coverage

| 类别 | 清单 | 本轮核实 |
|---|---|---|
| 现状断言 | 现状分析、既有约束、可复用能力、相关历史共 14 项 | 已逐条追到 AgentLoop、四个 provider parser、HookContext/logger、Gateway binder、E2E 启动器及 session JSONL 路径；见「核实台账」。 |
| 决策 | 4 项 | 决策 1、3、4 成立；决策 2 的 Anthropic streaming 输入边界缺失，见 R1-C1；其 aggregate 附带语义未定义，见 R1-W1。 |
| spec 约束 | 2 Requirements、4 Scenarios、澄清 Q1–Q4、4 项非目标 | 每次调用、严格边界、缺字段静默、固定无配置、字段/无 prompt 及非目标均有落点，无缩减或越界。 |
| delta-spec | 1 ADDED Requirement、2 Scenarios | 对应 Gateway 运维者可观察行为，THEN 不含内部符号；语义 target 合理。归并后的派生计数更新遗漏，见 R1-W2。 |
| milestone | M1 | 单一垂直切片、范围无并行冲突、reviewer/worker 双轨退出标准齐全；真实 Anthropic 帧形状和 catalog 登记尚未纳入，见 R1-C1、R1-W3。 |

### 核实台账

| 原子 | 结论与直接证据 |
|---|---|
| 现状：per-call terminal usage | 成立。`AgentLoop` 只在 terminal LLM message 记录 `latest_usage`（`src/agent/core/agent/loop.py:403-407`），随后在循环边界才调用 `_accumulate_usage`（`:537-541`）；在二者之间插入判断能保持 per-call 口径。 |
| 现状：统一 TokenUsage 分子/分母 | 成立。`TokenUsage` 已有 `cache_read_tokens`、`cache_total_input_tokens`（`src/agent/core/types.py:10-23`）；Anthropic parser 以未缓存输入 + creation + read 求总输入（`src/agent/platform/llm/providers/anthropic/client.py:315-335`），OpenAI-compatible 以 `prompt_tokens` 为总输入（`src/agent/platform/llm/providers/openai_compat/client.py:297-324`）。 |
| 现状：缺字段与显式 0 被混同 | 成立。四个 parser 都以 `... or 0` 降级缓存字段，例如 Anthropic client `:317-334`、OpenAI client `:312-323`；对应 mapper 也有同样形状（`anthropic/mapper.py:366-386`、`openai_compat/mapper.py:308-334`）。 |
| 现状：Gateway agent/session/log correlation | 成立。binder 每次建 session metadata 写入 `agent_id`（`src/personal_assistant/gateway/session_binder.py:795-850`）；`HookContext.__post_init__` 将 session/turn/trace fields 固定到 logger（`src/agent/core/hooks/context.py:168-188`）；隔离 Gateway 前台 stdout/stderr 写入 `.gateway.log`（`scripts/e2e-up.sh:301-315`）。session JSONL 的根地址为 workspace 配置目录下的 `sessions/<id>.jsonl`（`src/agent/core/session/jsonl_files.py:36-42`）。 |
| 既有约束：分层与 relay 不变 | 成立。kernel canonical spec 要求 core 不依赖 platform/products（`docs/specs/kernel/sdk-boundary.md:14-43`）；现有 turn-end relay usage 是显式白名单，只有两个既有 cache 数字进入 payload（`src/agent/core/agent/loop.py:633-642`），Gateway observer 同样只投影这两个数（`src/personal_assistant/gateway/runtime_delivery/observer.py:419-445`）。设计的不序列化约束因此可行。 |
| 可复用能力：现有 logger 与 Gateway metadata | 成立。`HookLogger.warning` 走结构化 fields（`src/agent/core/hooks/context.py:65-139`），没有必要新增 Gateway logger、hook event 或 RPC；以非空 metadata `agent_id` 作为 product gate 不会引入 core → Gateway 依赖。 |
| 决策 1：每次调用而非 turn 汇总 | 成立且完整覆盖 Q1、Requirement 1 / Scenario 1。`_accumulate_usage` 明确把 cache 数字按多 round 求和（`src/agent/core/agent/loop.py:1132-1172`），用于本期阈值会改变用户已拍板的 per-call 语义；设计的前置判断避免该错误。 |
| 决策 2：可用性 | 方向成立，覆盖 Q2 与显式 `0`；但真实 Anthropic streaming 帧没有定义采集与合并规则，不能实现完整，见 R1-C1。 |
| 决策 3：字段与隐私 | 成立且覆盖 Q4/Requirement 1。所列 `model`、agent/session id、整数 token 与百分比不需要传递 `messages_for_llm`；现有 logger 会保留 correlation，固定 fields 可被稳定断言。 |
| 决策 4：固定规则 | 成立且覆盖 Q3、边界 Scenario、Requirement 2。`> 30_000` / `< 80%` 与 spec 的严格文字一致；无 YAML/env/config 扩张。 |
| delta-spec | 成立。delta 的 operator-facing GIVEN/WHEN/THEN 与 canonical `Service Lifecycle` 的运维者受众相容（`docs/specs/gateway/service-lifecycle.md:6-21`），并且没有泄露 helper、类型或日志实现名。 |
| M1 | 成立。单一 M1 是完整的 provider → core → Gateway log 垂直切片，未按层拆分；其边界、负例、隐私断言和真进程验收均可验证。 |

### 架构进攻

| 角度 | 结论 |
|---|---|
| 归属 | 告警判断放在拥有 terminal `TokenUsage` 的 `AgentLoop`，但用 Gateway 已提供的 metadata 决定是否产生产品日志；没有 core 反向依赖或把 provider parsing 挪到 Gateway，归属正确。R1-C1 要求的 frame merge 也应留在 Anthropic provider client，而非污染 AgentLoop。 |
| 该不该存在 | 没有新增服务、RPC、配置或 notifier。直接复用 `HookContext.logger` 和两个既有 cache 数字，`cache_usage_available` 只解决“未知”与已知零值不可区分这一必要信息，不是预造抽象。 |
| 深浅 | helper 的输入被限定为 model、terminal usage、hook context，不接收 prompt；它把阈值、product gate 与隐私边界收敛在一个窄接口，未重造 relay/observability 能力。 |
| 治本 | 通过 provider 解析保存“是否报告”的事实而非以 `0` 猜测，方向是治本。若不补 R1-C1，则会在 Anthropic 真流的帧边界重新丢失这个事实，形成只对 test fixture 有效的补丁。 |

### Issues

- [R1-C1][CRITICAL] [现状分析「Anthropic…读取真实流」、决策 2、接口与数据流、M1 E2E]: 设计没有规定 Anthropic streaming 如何把 `message_start.message.usage` 的 input/cache fields 与 `message_delta.usage` 的 terminal output 合成一次 terminal `TokenUsage`。现有 client 只在 `message_delta` 覆盖局部 `usage`，并在 `message_stop` 才解析它（`src/agent/platform/llm/providers/anthropic/client.py:192-205`），对 `message_start` 没有 usage 分支。[Anthropic 的 prompt-caching 文档](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)明确把 streaming cache fields 放在 `message_start` usage；现有 fake fixture 也把 start 与 delta 分成不同帧（`scripts/fixtures/anthropic_sse_ok_recording.py:29-70`）。不改，worker 可以让 fixture 把 cache token 人为放入 `message_delta` 并通过 E2E，但真实 provider 已报告的 cache read 会被标成 unavailable、告警静默，直接违反 Requirement 1 / Scenario 1 的告警义务。设计须拍死：client 在 `message_start` 保存完整 input/cache usage，在 terminal delta 合并 output/finish reason，并以合并后的 raw presence 设置 `cache_usage_available`；E2E fixture 与 client unit test 必须使用这个真实帧分布（含显式 `0` 与字段缺失）。

- [R1-W1][WARNING] [决策 2 第 3 段、M1 worker 退出标准]: 「多轮合并时只在各轮都有数据时保留 true」没有定义 terminal usage 为 `None` 时如何保留“曾缺失一轮”的信息。当前 `_accumulate_usage(current, None)` 直接返回 current（`src/agent/core/agent/loop.py:1156-1159`）；第一轮无 usage、后续一轮 available 时也没有现成 state 能让 `TokenUsage` 知道前一轮缺失。若只在两个非空 `TokenUsage` 上 AND，未来 turn-level consumer 会把部分未知错误标成完整可用。请明确选择：本期删除这项未来语义，或在 loop 中维护独立的 per-round completeness state（覆盖首轮/中间轮 terminal usage 缺失），并把它压回最终 aggregate。当前 per-call 告警不依赖 aggregate，可保持不受影响。

- [R1-W2][WARNING] [契约层增量、M1 范围]: delta 会把 `Service Lifecycle` 从 5 条 Requirement 增至 6 条，但设计没有列出归并时对 `docs/specs/gateway/spec.md` 的派生计数（及实际修改文件的 `对齐` 标记）更新。该入口当前声明 5（`docs/specs/gateway/spec.md:19-25`）；`scripts/docs-check` 会机械比较该数与 area 标题数（`scripts/docs_check.py:642-663`）。不补，canonical 归并后的本地 CI 必失败，或 reviewer 被迫在设计外补一项行为不明的文档修改。将这个 entry-count update 加入 M1 scope/收尾验证；它不需要重复一份 delta Requirement。

- [R1-W3][WARNING] [Runbook for Reviewer、M1 退出标准]: 设计已把新增测试定位为 `tests/e2e/critical_paths/test_prompt_cache_alert_critical_path.py`，却未把它登记进 `docs/development/e2e-critical-paths.md` 或 M1 范围。catalog 规定每个新增关键特性必须有一条可收集的守护测试登记（`docs/development/e2e-critical-paths.md:26-28`），并已给出 fake-LLM 真栈的独立 config/stub 生命周期范式（`tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py:152-244`）。不补，新的长期关键路径没有单一权威索引，维护者也容易误把它接到需要 `:4000` 的 live fixture，破坏设计承诺的确定性、无密钥验收。请在 M1 写明：复用/扩展该 fake-stack 模式，以临时 copied config 指向本地 stub、无需 live-proxy gate，并在 catalog 加相应的 fake-LLM 行与可收集 node id。

### Recommendations

- [R1-R1] 修订决策 2 和时序图：将 Anthropic `message_start` usage snapshot + `message_delta` terminal usage merge 作为 provider client 的明确职责，并在 M1 写入分帧正/负例。
- [R1-R2] 为 `cache_usage_available` 的 turn aggregate 写出完整真值表（包括任一 round `usage=None`），或删除本期不消费的 aggregate 承诺，避免多引入无状态的语义负债。
- [R1-R3] 在 M1 的归并/验证范围补列 `docs/specs/gateway/spec.md` 的 `5 → 6` 派生计数和 `docs/development/e2e-critical-paths.md` 的 fake-LLM critical-path 登记；继续只让业务 delta 落在 `service-lifecycle.md`。

### Author Resolutions

- [R1-C1] accepted — `AnthropicClient` 当前只在 `message_delta` 保存 usage、`message_stop` 才解析，真实 start-frame cache data 确会丢失。已在 `design.md` 的现状、决策 2、架构图、时序图、接口与 M1 明定 start snapshot + delta merge，并要求分帧 E2E 与 client 测试。
- [R1-W1] accepted — 本期没有 turn-level consumer，给 `_accumulate_usage` 定义不完整的 availability 合并属于额外语义。已删除该承诺：标记仅服务逐调用告警，turn aggregate 继续只维护既有数字字段。
- [R1-W2] accepted — canonical `service-lifecycle.md` 现有 5 条 Requirement，而包入口维护派生计数。已在 M1 归并收尾明确更新 area 的对齐标记及入口的 `5 → 6` 计数。
- [R1-W3] accepted — 新增 fake-LLM 真栈关键路径必须有 catalog 入口，且不应继承 live-proxy gate。已在 M1 范围与退出标准明确复用临时 copied config + local stub 模式，并登记 `docs/development/e2e-critical-paths.md` 与可收集 node id。

## Round 2

### Metadata

- reviewer: `feat_516_design_reviewer`
- review_mode: `delta`
- mode_reason: `R1` 的四项修订局限于现状说明、决策 2、接口/数据流和 M1 退出标准；Requirement、delta-spec、总体分层与非目标未变。修订为 Anthropic 跨帧状态、逐调用可用性语义和既有文档/测试收尾增加了实现细节，影响超过纯引用核对，故采用 `delta` 而非 `closure`；其余全量覆盖保留自 R1。
- started_at: `2026-08-07T17:11:42+08:00`
- completed_at: `2026-08-07T17:13:13+08:00`
- duration: `1m 31s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

四项 R1 问题均在设计的职责边界、数据流和 M1 可验证工作项中闭合；修订没有扩大产品契约、配置面或 core 与 Gateway 的依赖方向。

### Coverage

- `retained_from: Round 1` — 现状基线、spec/delta-spec 覆盖、固定阈值与字段/隐私契约、Gateway metadata/logger 分层、整体架构进攻结论。
- 本轮重查：R1-C1 的 Anthropic 真 SSE 分帧归一、R1-W1 的 turn aggregate 语义收缩、R1-W2 的 canonical 派生计数归并、R1-W3 的 fake-LLM critical-path 登记及其 M1 验证路径。

### 历史问题闭环与变更台账

| 历史项 | 修订后的直接证据 | 结论 |
|---|---|---|
| R1-C1 | 设计现状、决策 2 和接口均明确 client 保存 `message_start.message.usage` 的 input/cache snapshot、在 `message_delta.usage` 补 output 后于 `message_stop` 产生 terminal `TokenUsage`（`design.md:15-16, 64-68, 86`）；架构图和时序图同步标注该合并（`:43, 52, 101`）。M1 要求真实 Anthropic frame split 的 client 正/零/缺失测试及同形状 E2E fixture（`:140`）。这直接填补当前 client 仅在 `message_delta` 赋 usage 的缺口（`src/agent/platform/llm/providers/anthropic/client.py:192-205`），并保持 mapper 只处理完整非流式 response 的职责。 | Closed |
| R1-W1 | 决策 2 明定 `cache_usage_available` 仅服务逐调用告警，不进入 turn aggregate；`_accumulate_usage` 保留既有数字累计且不新增未消费的完整性约定（`design.md:68`）。M1 同步要求 aggregate 仅断言既有数字口径（`:140`）。这与当前 `update is None` 时保留既有 aggregate 的行为（`src/agent/core/agent/loop.py:1156-1172`）一致，未留下无法表达的跨轮真值表。 | Closed |
| R1-W2 | M1 明定归并 `service-lifecycle.md` 的对齐标记，并把 Gateway 入口的 Service Lifecycle Requirement 派生计数由 5 更新为 6（`design.md:140`）。这精确对应入口当前的 5（`docs/specs/gateway/spec.md:19-25`），未把实现细节误写进业务 delta。 | Closed |
| R1-W3 | M1 明定复用临时 copied config + local SSE stub 起真 IM/Gateway，检查真实 `gateway.log` 与 session JSONL，并把可收集测试/node id 登记到 `docs/development/e2e-critical-paths.md`、不接入 live-proxy gate（`design.md:140`）。这满足 catalog 对每个关键特性的登记和守护测试要求（`docs/development/e2e-critical-paths.md:26-28`），并与现有 fake-LLM 真栈条目的隔离模式相容（`:48`）。 | Closed |

### 受影响架构重查

| 角度 | 结论 |
|---|---|
| 归属与依赖 | 跨帧 merge 被限定在 Anthropic provider client；`AgentLoop` 只消费已归一的 terminal usage 与 hook context，Gateway 仍只通过 metadata/log 承接可观察行为（`design.md:52, 66, 72-76`）。没有 core → Gateway 依赖或把 provider 协议泄漏到 loop。 |
| 语义边界 | 显式 `0` 与字段缺失的区别只由原始字段 presence 决定；没有把未知降为零，也没有为无消费者的 turn aggregate 发明新语义（`design.md:64-68`）。 |
| 可验证性与长期维护 | 分帧 unit/provider cases、严格边界/缺字段负例、真实进程日志与 JSONL 对照、catalog 登记、canonical 对齐和 docs-check 都已列入同一 M1，测试不依赖个人 proxy 或密钥（`design.md:130-140`）。 |

### Issues

- 无新增问题。

### Recommendations

- 无新增建议。

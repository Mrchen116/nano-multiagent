# Design Review: feat-541

## Round 1

### Metadata

- reviewer: `feat-541-design-reviewer`
- review_mode: `full`
- mode_reason: Gate 2 Round 1，skill 规定 R1 恒为 full；无作者对齐对话，不继承任何期望 verdict。
- started_at: `2026-08-18T11:12:00+08:00`
- completed_at: `2026-08-18T11:18:42+08:00`
- duration: `7m`

### Verdict

Issues Found — 1 CRITICAL / 2 WARNING

### Issues

- [R1-C1][CRITICAL] [决策 1+2+6 / 接口与数据流「本轮何时换」]: 产品层 failover 循环在生产路径上未闭合，「本轮静默换模型、用户先收到备用回复」无法按设计实施。不改的话，worker 只能在三种互不兼容的架构里猜，且都会违反 spec「而不是先看到一轮失败再发下一条才换」，或偷偷改内核。

  独立从入口追到的生产事实（不是 design 引用）：

  1. **失败不会作为 `ModelError` 回到 Gateway。** 聊天 `SessionRunCoordinator` 对 `kernel.submit` 只入队、不带 `model=`（`session_run_coordinator.py:1387-1393`）；`Kernel.submit` 在已有 session runtime 时要求 `model` 与 runtime 一致，否则 `ValueError`（`kernel.py:1755-1759`）。后台 run 把 `ModelError` 压成 `{code: "run_execution_failed", message: str(exc)}`，只有 `CompactionError` 走 `to_dict()`（`runs/registry.py:553-562`）。`agent.sdk` 不导出 `ModelError`（`sdk/__init__.py`）。决策 6 写「读 SDK `ModelError` 的 message/status/code」在消费面不成立：`status_code` / `provider_code` / `retryable` 在 `run_status.error` 上已经丢掉。

  2. **可用性失败在终态之前就已经是用户可见回复。** `runtime.py:806-849` 在 `ModelError` 时先合成 `⚠️ 模型调用失败:…` assistant（`is_provider_error=True`），再 `message_end` + `turn_end(completed=False)`。Gateway observer 在 `_await_terminal_run` **内部**同步转发（`session_run_coordinator.py:2165-2168` → `observer.py:1468-1471`）。stream 上 `assistant_message.metadata` 恒为 `{}`（`realtime_stream.py:72-82`），产品层无法干净区分「错误气泡」和真回复。决策 2 的「尚无可见回复才换」若含这条合成错误，则本轮永远换不了；若不含，用户已经先看到一轮失败。设计拒绝「删半截气泡再开新气泡」，但没处理这条**现状就会投出的失败气泡**。

  3. **第二次 `submit` 不是「同一轮换模型」。** 用户 `parts` 已随第一次 run 进 transcript，失败路径还留下错误 assistant。再 `submit(parts=原文)` 会再写一条用户消息；不带 parts 则模型会看见失败气泡。心跳/cron 同理（`heartbeat_scheduler.py:518` / `cron_runner.py:149` 之后由 `stream_run_to_completion` 等终态）。设计只写「包在 submit + 等终态外面 / 再 submit 下一候选」，没拍：要不要 `reconfigure_session`、丢哪些 transcript、observer 停在循环哪一侧。

  下游坏事：两个 worker 会分别做成 (a) 看见任何 assistant 就不换 → spec 本轮续答失败；(b) 等终态后再 submit → 用户先看到失败气泡再看到备用回复；(c) import `agent.core.errors` 或改内核分类器/物化时机 → 撞 `AGENTS.md` 包边界或决策 1。orchestrator 无法按现在的接口段派工。

- [R1-W1][WARNING] [现状分析 / 决策 3]: 「各聊天与心跳专用 session 各记一份」与生产不符。心跳**优先复用 owner canonical 直聊** kernel session（`heartbeat_scheduler.py:435-449`），没有直聊时才退回 `:heartbeat` session。粘性若严格按 `kernel_session_id` 实现，直聊与心跳会共享一份覆盖（这对 OpenClaw 式「心跳是主会话 turn」其实合理）；若 worker 按「心跳专用 session」另建命名空间，canonical 切换后粘性丢失或一份 session 两套状态。不改 → 心跳/直聊粘性语义分叉，`/new` 清粘性是否覆盖心跳变得可猜。

- [R1-W2][WARNING] [Milestones feat-541-M1 范围 / 选模 §]: cron 等终态不在 `cron_runner.py`。`CronRunner.submit` 只入队（`cron_runner.py:148-174`）；真正 `stream_run_to_completion` 在 `CronRunTerminalConsumer`（`cron_execution_service.py:363-395`）。M1 范围列了 `cron_runner.py`，未列 `cron_execution_service.py`、`runtime_delivery/stream.py`、`runtime_delivery/observer.py`、`IM/infra/db.py`（`agent_profiles` 加列的既有 ALTER 落点，`db.py:53-72, 694+`）。不改 → worker 可能把 failover 塞进只负责 submit 的 cron_runner，心跳/cron 与聊天三条路径更容易做成三套循环；IM 列迁移也容易漏。

### Recommendations

- [R1-R1] 把 R1-C1 收成三条无歧义契约，而不是再补一句「在等终态外包一层」：(1) Gateway 判定入口 = `run_status.error` 的实际形状（`run_execution_failed` + message 字符串，`compaction_failed` 不换），禁止 `except ModelError` / import `agent.core`；(2) 用户可见失败气泡的时机：要么窄开内核「非最终尝试不物化 provider error」，要么产品层在 observer 缓冲到终态前不投递——必须写清对成功路径 streaming 的影响；(3) 换候选时对 transcript / `reconfigure_session` / 第二次 submit 的 parts 写死一份。
- [R1-R2] 决策 3 改成「粘性键就是 kernel session」；写明心跳复用 canonical 直聊时与该聊天共享粘性，`:heartbeat` 回退 session 单独一份。不要再写「心跳专用 session 各记一份」。
- [R1-R3] M1 范围补上 `cron_execution_service.py`、`runtime_delivery/stream.py`、`observer.py`（若 R1-C1 选产品层 hold）、`IM/infra/db.py`、前端 `im-agent-config-api.ts`。选模段把 cron 等终态改到 `CronRunTerminalConsumer`，不要写 `cron_runner`。

### Coverage

本轮 `full`：通读 `spec.md`、`design.md`、`prototype.html`、四份 delta-spec、`M1-impl/.gitkeep`；从 IM 配置页 / Web IM 入站 / 心跳 tick / cron 入队四条生产入口追到 `文件:行`；对照 canonical `docs/specs/im/agents-nodes.md`、`docs/specs/gateway/agent-capabilities.md`、`external-channels.md`、`heartbeat-cron.md` 与 `AGENTS.md` 包边界。无历史 Round 可继承。

### 核实台账

#### 现状断言

| 原子 | 结论 | 证据 |
|---|---|---|
| 编辑/新建页主模型是单个 `im-input` `<select>`，紧挨 `ModelReasoningField` | 成立 | `agent-detail-page.tsx:1887-1929`；`agent-create-page.tsx:984-1023`；技能统计链 `im-agent-access-skills-link` 在同卡 `agent-detail-page.tsx:1830-1836` |
| IM profile 只有 `default_model`，SQLite + 乐观锁 apply | 成立 | `AgentProfile.default_model` `domain/models.py:80`；`agent_profiles` 无 fallback 列 `db.py:53-72`；apply 键集 `_GATEWAY_CONFIG_KEYS` 含 `default_model` 不含 fallbacks `agent_config_operations.py:24-37` |
| `local_store.resolve_run_model` 是产品层选模，聊天/心跳/cron 共用；`explicit > agent.default_model > 平台默认` | 成立（产品层） | 定义 `local_store.py:651-673`；聊天 `_resolve_agent_model` `session_run_coordinator.py:2807-2814`；heartbeat/cron shim `kernel_client.py:80-83,148-151,218-228`。内核另有 `engine.resolve_run_model` 给子 agent（`sdk/kernel.py:144-145`），不参与对话选模 |
| 聊天 `kernel.submit(model=一个)` | **不成立（聊天路径）** | 聊天 submit **不传 model** `session_run_coordinator.py:1387-1393`，模型来自 `_admit_runtime` → `SessionRuntimeConfig.model`。心跳/cron 才 `submit_message(..., model= 或 agent_id)` `kernel_client.py:223-228` |
| 心跳 `reconfigure` 只带一个模型 | 成立 | `ensure_agent_runtime` → `resolve_run_model` → `reconfigure_session` `kernel_client.py:148-175` |
| `session_composition` 把本轮模型写入 `SessionRuntimeConfig.model` | 成立 | `session_composition.py:83-84` |
| Kernel 不改；per-run 单模型；`RetryingLLMClient` 同请求重试；部分输出不原位重放 | 成立 | `RetryingLLMClient` `retry.py:19-31,51-57`；`submit(model=)` docstring `kernel.py:1739-1744` |
| `error_classifier`：欠费/限流可重试；上下文超长永久；Gateway 只消费 SDK `ModelError` 事实 | **部分不成立** | 分类器本身成立：`authentication_error` 永久 `error_classifier.py:55-67`；billing/quota 文本可重试 `173-176`；`context_length_exceeded` 在 permanent codes `77`。**消费面不成立**：见 R1-C1，Gateway 看不到 `ModelError` |
| `runtime_footer` 默认关，不当切换说明 | 成立 | `DisplayConfig.runtime_footer_enabled: bool = False` `local_store.py:325`；`_runtime_footer_enabled` `runtime_footer.py:56-60` |
| `_deliver_control_reply` 压缩确认同一出站，Web IM + 飞书 | 成立 | 函数体 `session_run_coordinator.py:2049-2092`；compact `ack_tag="compact-ack"` `:882-888`；`bg_reply_sender` 同时外发飞书与 IM `runtime_delivery/background.py:197-247`。**并非绑死 compact**：`/new` `/stop` `/effort` 共用 |
| 不用 `node.system_message` 当飞书提示 | 成立 | `node.system_message` → `sender_type='system'`，且只认 `self_evolution_review` `relay.py:405-445`；外部-channels canonical：其他系统通知不外发飞书 |
| 心跳 `submit_message(model=agent.default_model)` 会走 explicit 盖住链 | 成立 | `heartbeat_scheduler.py:518-525`；`resolve_run_model` 第一句 `if explicit: return explicit` `local_store.py:669-670` |
| 契约层与代码一致、无 drift；缺口是两边只有一个有效模型 | 成立（配置面）；运行面缺口比「一个模型」更大 | canonical `agent-capabilities.md:14-16` 与 `resolve_run_model` 一致。失败物化/扁平化是既有 bugfix-380 行为，design 当「Kernel 返回 ModelError」上报是 drift |
| `personal_assistant` 只 import `agent.sdk`；IM 不调 agent | 成立 | `AGENTS.md`；`session_run_coordinator.py:15` `from agent.sdk import`；gateway spec Purpose 同约束 |
| 内核不持有对话默认模型（bugfix-429） | 成立 | `resolve_run_model` docstring `local_store.py:660-662`；`kernel.submit` `kernel.py:1739-1744` |
| 已开始的整轮不中途换运行配置 | 成立 | `_admit_runtime` 在 submit 前；canonical `agent-capabilities.md:28-31` |
| 工具审批专用模型失败不改用对话模型 | 成立（非目标可守） | 审批模型在 `build_kernel(tool_approval_model=...)` `composition.py:244`；**不走** `InProcessKernelClient.submit_message`（全仓仅 heartbeat/cron 调用）。只要 failover 不包内核内部 LLM 调用就不会误伤 |

#### 决策

| 决策 | 拍死 | 无歧义 | 互洽 | spec 驱动 / 现状内 | 结论 |
|---|---|---|---|---|---|
| 1 Gateway 包 failover，不改 Kernel | 是 | 落点文件级清楚 | 与 2、6 组合后**无法在现状上实施** | spec Q8 / bugfix-429；归属正确 | **因组合失败记入 R1-C1**，单条归属成立 |
| 2 仅无可见回复时换；有吐字则本轮收口 + 粘性 | 是 | 「可见回复」含不含 bugfix-380 合成错误、工具时间线？设计后文定义为正文或工具时间线，**没提失败气泡** | 与 spec「本轮仍回复、不先看到失败」冲突于生产路径 | 来自 design 移交项 3 | **R1-C1** |
| 3 粘性在 Gateway、按 kernel session；不写回 profile | 是 | 键清楚；清粘性触发清楚 | 与「心跳专用 session」现状不符 | spec Q2 | 决策本身可实施；现状句 **R1-W1** |
| 4 复用 `_deliver_control_reply`，不走页脚 | 是 | 文案、先说明后正文、Web IM Agent 短气泡均锁死；「若绑死 compact 则抽一层」生产上并未绑死，可当实施细节 | 与 canonical 外发规则一致 | spec Q4 | 成立 |
| 5 备用用模型自己的默认档，跳过 `/effort` overlay | 是 | 链头走 `_reconcile_runtime`，非链头跳过 | 与决策 1 一致 | spec 移交项 5，用户确认「用默认」 | 成立 |
| 6 Gateway 按错误事实换；不把 `retryable` 当唯一开关；不改分类器 | 表面拍死 | **判定输入形状未对准生产 `run_status.error`** | 认证失败要换在分类器语义上正确，但 Gateway 拿不到 `provider_type` | spec Q5 | **R1-C1** |

#### spec 约束

| 原子 | 覆盖 | 不冲突 | 不越界 |
|---|---|---|---|
| Req 配置页折叠备用 | 决策未编号；前端原型 + IM delta | 是 | 是 |
| Scenario 默认折叠 / 展开保存 / 清空等价 | 原型契约 must-match + M1 `[reviewer]` | 是 | 是 |
| Req 可用性失败本轮改用备用 | 决策 1–2、6 | **机制与「不先看到失败」冲突** → R1-C1 | 是 |
| Scenario 上下文太长不换 | 决策 6 | 是（`CompactionError` 可识别；纯 `context_length_exceeded` ModelError 只剩 message 字符串） | 是 |
| Scenario 没配 / 整链耗尽按现状失败 | 组链单元素、耗尽表 | 是 | 是 |
| Req 轻量说明 + 粘住后不重复 | 决策 4 + sticky.noticed | 是 | 是 |
| Scenario 外部通道同样看到 | 决策 4 + external-channels delta | 是（`bg_reply_sender` 有外发） | 是 |
| Req 粘在当前聊天、不写回主模型 | 决策 3 | 是 | 是 |
| Scenario `/new`、改配置清粘性、另一聊天互不影响 | 决策 3 状态图 | 是 | `/new` 换 session 自然清；改配置需按 agent 扫 session，`session_binder` 可做，M1 未列该文件但 `agent_config_sync` 已列 |
| Req 心跳与 cron 同链 | 选模 § + heartbeat-cron delta | 覆盖意图在；**等终态落点写错** → R1-W2；C1 同样卡住本轮换 | 是 |
| 非目标：多钥匙 / 节点默认链 / CLI / `/model` / 辅助任务链 / 审批失败语义 | 决策 1 拒绝内核 failover；不改 coding_cli；审批不走 kernel_client | 是 | 未夹带 |
| 澄清 Q1–Q8 | 均有落点 | Q5/Q6 的「本轮」被 C1 架空 | 是 |

#### delta-spec 条目

| 条目 | 锚 canonical / 用法 / THEN |
|---|---|
| im/agents-nodes ADDED「配置页可设置有序备用」 | 最窄 area 正确；Scenario 用户可观察；含「自动切换不改写编辑页」 |
| im/agents-nodes MODIFIED「配置中心可读可改…」 | 正确 MODIFIED：锚定既有标题，原 Scenario 保留，新增备用目录校验 Scenario；THEN 无内部符号 |
| gateway/agent-capabilities ADDED 备用链 | 用户/通道可观察；「已有可见回复后再失败」是 design 补充，THEN 可观察 |
| gateway/agent-capabilities MODIFIED「选定的模型…生效」 | 正确 MODIFIED：改成链头 + 无 sticky 时行为与变更前相同；原 Scenario 保留 |
| gateway/external-channels MODIFIED 用户可见控制投递 | 正确 MODIFIED：把说明列入用户可见事件，保留原控制确认 Scenario；新增飞书触发/内部触发两条；THEN 可观察。实现层「同一投递形态」未点函数名 |
| gateway/heartbeat-cron ADDED 同链 | 正确 ADDED；THEN 可观察 |
| kernel / cli / web-chat-ux: no spec delta | 配置 UX 在 agents-nodes、说明形态复用既有 Agent 气泡，说得通。**若 R1-C1 收成为窄开内核物化时机，则 kernel「no spec delta」要作废** |
| 无「改既有契约却只写 ADDED」 | 成立 |
| 消费者视角 | IM/Gateway 终端用户主语正确 |

#### milestone

| 原子 | 结论 |
|---|---|
| 单 M1 | 成立：配置 + failover + 提示是一条用户可观察切片；拆分举证不需要 |
| 非横切 | 成立（垂直切片） |
| 两轨退出 | 成立：`[reviewer]` 引 spec Scenario + 原型 must-match；`[worker]` 组链/粘性/心跳 cron/不改 Kernel |
| 范围文件 | **不全** → R1-W2 |
| 空 `M1-impl/.gitkeep` | 设计阶段故意为空，不报 |

### 架构进攻

#### 角度一·归属

把 failover 放在 Gateway 产品层、不放 Kernel / IM，与 `platform → core`、`personal_assistant` 只 import `agent.sdk`、IM 不执行 LLM 一致。单条决策 1 是对的。

叠加后：决策 1「不改 Kernel」+ 决策 2「本轮用户不可见失败」要求产品层在 **observer 投递之前**介入，但现有投递缝在内核物化之后。这不是放错层，是**该层缺少失败缝**。隐含依赖：若 worker 为了读 `ModelError` 去 import `agent.core.errors`，就反向穿透 sdk。长远代价：包边界被第一次「只是读一下异常类型」打破后，审批/摘要路径更容易被误挂 failover。

心跳粘性按 session 键是对的归属；写成「专用 session」是现状误判（R1-W1）。

#### 角度二·该不该存在

`resolve_model_candidates` + 粘性表 + 包住「submit+等终态」的循环：删掉后调用方仍得在聊天/心跳/cron 各写一遍，复杂度是真集中，不是假抽象。抽「短系统文本投递」供 compact 与 fallback 共用：`_deliver_control_reply` 已经通用，**不必**为 compact 再拆一层（design 的「若绑死则抽」生产上未发生）。不报新抽象。

#### 角度三·深还是浅

没有重造 `RetryingLLMClient`（那是同请求、同模型），正确。风险是聊天 / 心跳 runner / cron consumer 三处各写一套循环：接口不会比「等终态 + 再 submit」更简单，bug 会出在「哪次 observer 已经投过错误气泡」。这是浅复制，不是新模块。R1-C1 不收口的话，三处复制会把错误气泡/二次 submit 做成三种样子。

#### 角度四·治本还是补丁

「换模型是产品选模」是治本。但在 bugfix-380「失败即用户可见 assistant」和 registry「ModelError 压成 run_execution_failed」之上叠循环，是在共享失败路径上打补丁。长远代价：每次内核改错误物化文案或 observer 时序，备用链就会静默失效或把失败气泡漏给用户；上下文超长以外的判定只能靠 message 子串，和分类器表会再漂一次。正面做法是给产品层一条「最终失败才对用户可见」的缝，而不是解析 `⚠️ 模型调用失败`。

### 整体判断

上层（总览图 + 六条决策一句话）能看懂方向：Gateway 链循环、Kernel 单模型、粘性不写回。给人审核方向足够。

接口图把聊天画成 `submit(model=主)`，与聊天生产路径（runtime 已 admit、submit 不带 model）不一致，强化了 R1-C1。

完整性：无模板残留/TBD；Changelog 段为空但不阻断；风险段写了心跳 explicit 和部分输出——部分输出应对仍停在「粘性留给下一轮」，没覆盖「失败气泡已经发出」。Runbook 有可照搬的 e2e-up/down，常驻服务重启命令够用。原型与折叠 UX、切换文案 must-match 清楚，配置面可实施。

### Author Resolutions

- [R1-C1] **escalated**：独立核生产路径成立。聊天 `submit` 不带 `model=`（`session_run_coordinator.py:1387-1393`）；`ModelError` 在 `runtime.py:806-849` 先物化 `⚠️ 模型调用失败` 再失败终态；registry 把非 `CompactionError` 压成 `{code: "run_execution_failed", message: str(exc)}`（`runs/registry.py:554-562`）；`agent.sdk` 不导出 `ModelError`。再 `submit` 会重复写入用户 parts。这与用户已确认的决策 1「完全不改内核」叠加后，无法同时满足 spec「本轮仍回复、不先看到失败」。暂停修订，交用户在窄开内核缝 vs 改验收之间拍板。
- [R1-W1] **accepted**：心跳优先复用 canonical 直聊 session（`heartbeat_scheduler.py:435-449`）。待 C1 拍板后把决策 3 改成「粘性键 = kernel_session_id」，直聊与心跳共享、`:heartbeat` 回退单独一份。
- [R1-W2] **accepted**：cron 等终态在 `CronRunTerminalConsumer`（`cron_execution_service.py`），不在 `cron_runner.py`。待 C1 拍板后改 M1 范围与选模段。
- [R1-C1] 用户拍板后 **accepted**：Q9 改为先投下带模型名的失败气泡，再同轮 replay 备用。决策 1 改为内核窄开三条缝（失败文案含模型 id、`run_status.error.kind`、replay-last-user），不 hold 失败气泡、不复制用户消息。W1/W2 已写入决策 3 与 M1 范围。

## Round 2

### Metadata

- reviewer: `feat-541-design-reviewer`
- review_mode: `full`
- mode_reason: Q9 改了需求可见顺序；内核从「不改」变为窄开三条消费者缝；新增 kernel delta-spec 与数据流（replay-last-user）。属需求变化 + 核心边界/共享契约高风险变化，不能用 closure/delta。
- started_at: `2026-08-18T11:30:00+08:00`
- completed_at: `2026-08-18T11:32:55+08:00`
- duration: `3m`

### Verdict

Issues Found — 2 CRITICAL / 2 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | accepted：Q9 先失败气泡再同轮换；内核三条缝；不 hold | 三条缝对准了 R1 生产洞（气泡已投出、error 扁平化、空 parts 非法 `registry.py:203-204`）。原「静默换 vs 完全不改内核」已解开。残留的「失败气泡算不算真实正文」「粘性何时 admit」另立 R2-C1/C2 | closed |
| R1-W1 | accepted：粘性键 = kernel_session_id；canonical 直聊共享 | 决策 3 已按生产 `heartbeat_scheduler.py:435-449` 改写 | closed |
| R1-W2 | accepted：cron 等终态在 CronRunTerminalConsumer；M1 补文件 | 选模 § 与 M1 范围已含 `cron_execution_service.py`、`db.py`、`session_binder.py`、kernel 缝文件 | closed |

### Issues

- [R2-C1][CRITICAL] [决策 2 / 选模「本轮何时换」]: Gateway **如何认定「尚无真实正文/工具时间线」**没拍死。Q9 要求失败气泡必须先投下，且它**不算**挡住换候选的真实回复；但生产里这条气泡与真回复走同一条 `assistant_message`，Gateway 现有等终态把**任何** assistant 文本写入 `reply_text`（`session_run_coordinator.py:2176-2179`）。stream 的 `assistant_message.metadata` 恒为 `{}`（`realtime_stream.py:82`）；`message_end` 也不带 `is_provider_error`（`runtime.py:823-829`）。内核 replay 缝虽规定「已有真实输出则拒绝」，产品循环没有写死「以 `kind` 可换则尝试 replay、以内核拒绝为准；失败气泡不得当成真实正文」。不改 → worker 用「有 assistant 文本就不换」会让 failover 永不触发（Q9 作废），或解析 `⚠️` 字符串（决策 6 已拒绝的做法）。

- [R2-C2][CRITICAL] [决策 3 / 选模组链 / 时序图]: **粘性接到哪一次 admit 没拍死。** 组链写明有 sticky 时链头就是 `sticky.model`，「不再把已经失败的链头放回本轮」；但时序图画的是 `admit runtime(主) + submit(parts)`，选模又强调 `resolve_run_model` 仍只回答保存的链头、failover「包在等终态外面」。生产 `_project_runtime` 只调 `_resolve_agent_model` → `resolve_run_model`（`session_run_coordinator.py:1786-1814`）。不改 → worker 只在失败后再 replay，下一轮用户消息仍先 admit 主模型：每条都会先再撞一次已挂主模型并再丢失败气泡，直接违反 spec「新回复继续使用 B，不再先撞已经失败的主模型」。必须写死：每次新回复的 **第一次** admit/reconfigure 用 `candidates[0]`（sticky 或链头），`resolve_run_model` 只当组链输入。

- [R2-W1][WARNING] [delta-spec `specs/gateway/agent-capabilities.md` ADDED 需求正文]: 正文仍写「尚未向用户投出**可见回复**时」才换候选；Scenario 已改成「真实正文或工具时间线」，与 Q9/决策 2 相反。不改 → 归并 canonical 后需求段与 Scenario 自相矛盾，worker 可能重新 hold 失败气泡。

- [R2-W2][WARNING] [现状分析 · 可复用能力]: 仍写「Gateway 只消费 SDK 抛出的 `ModelError` 事实」（design.md 现状 L18），与决策 6「读 `run_status.error.kind`、不 `except ModelError`、不 import `agent.core`」直接打架。不改 → worker 可能再走 R1 已否定的异常类型路径。

### Recommendations

- [R2-R1] 产品循环写成：`kind ∈ {quota,overload,timeout,rate_limit,auth}` 则调用 replay-last-user；内核因「已有真实输出」拒绝 → 本轮收口并按表写 sticky；不要用 `reply_text` 是否为空，也不要匹配 `⚠️`。若担心内核拒绝不够早，给 stream/run_status 加可观察的 `replay_eligible` / provider-error 标记（第四条缝），不要让 Gateway 猜气泡。
- [R2-R2] 时序图改成 `admit runtime(candidates[0])`；补一条「已粘住时下一轮不再 admit 主模型」的图或表。点名改 `_project_runtime` / 等价 admit，不要只包 `_await_terminal_run`。
- [R2-R3] 改掉 gateway delta 需求正文「可见回复」；现状 L18 改成只消费 `run_status.error.kind`。

### Coverage

本轮 `full`：重读修订后的 `spec.md`（含 Q9）、`design.md`、`prototype.html`、kernel/gateway delta-spec；对照 R1 已追过的生产路径（聊天 admit/submit/等终态、心跳 canonical session、cron `CronRunTerminalConsumer`、registry 空 parts、stream metadata）核新缝是否可实施。IM agents-nodes / external-channels 无本轮语义变化，作 retained。

### 核实台账

#### 现状断言

| 原子 | 结论 | 证据 |
|---|---|---|
| 配置页单 select + ModelReasoningField | 成立 | retained_from: Round 1 — 前端未改主模型控件 |
| IM profile 仅 `default_model` + 乐观锁 | 成立 | retained_from: Round 1 |
| `resolve_run_model` 产品层链头 | 成立 | `local_store.py:651-673`；聊天仍经 `_resolve_agent_model` |
| 聊天 `submit` 不传 `model=` | 成立（已写入既有约束） | `session_run_coordinator.py:1387-1393` |
| Kernel 窄开三条缝；今天失败气泡无模型名、error 丢事实 | 成立（现状） | `_build_provider_error_message` `runtime.py:2506-2526`；扁平化 `registry.py:553-562` |
| Gateway 只消费 SDK `ModelError` 事实 | **不成立** | 生产不抛给 Gateway；sdk 不导出。决策 6 已改，现状 L18 未改 → R2-W2 |
| `error_classifier` 不改重试表 | 成立 | 决策 6；kind 是投影不是重写 retryable |
| footer 默认关；`_deliver_control_reply` 可复用 | 成立 | retained_from: Round 1 |
| 心跳 `model=agent.default_model` 走 explicit | 成立 | `heartbeat_scheduler.py:518-525`；design 已当链头 |
| 心跳优先 canonical 直聊 session | 成立 | `heartbeat_scheduler.py:435-449`；决策 3 已对齐 |
| 空 `submit(parts)` 非法 | 成立（replay 缝的前提） | `registry.py:203-204` |
| stream 无法区分 provider-error 气泡 | 成立 | `realtime_stream.py:82`；→ R2-C1 |
| 包边界：PA 只 import `agent.sdk` | 成立 | 决策 6 禁止 except/import core |

#### 决策

| 决策 | 拍死 | 无歧义 | 互洽 | spec 驱动 | 结论 |
|---|---|---|---|---|---|
| 1 Gateway 持链；内核三条缝、不持 fallbacks | 是 | 三条缝职责清楚；replay 因空 parts 非法而必要 | 与 Q9/R1-C1 闭合 | Q9 + bugfix-429 | 成立 |
| 2 先失败气泡再同轮换；真实吐字后不换 | 表面拍死 | **「真实正文」检测口未对准生产事件** | 与 Q9 一致，与现有 `reply_text` 累加冲突 | Q9 | **R2-C1** |
| 3 粘性键 kernel_session_id；canonical 共享 | 是 | 清粘性触发清楚 | 与组链/时序图/现有 admit **未接线** | Q2 | 键成立；接线 **R2-C2** |
| 4 `_deliver_control_reply` | 是 | 顺序改为失败→已改用→正文 | 与 Q9 一致 | Q4 | 成立 |
| 5 备用用模型默认档 | 是 | 跳过 `_reconcile_runtime` overlay | 成立 | 移交项 5 | 成立 |
| 6 读 `error.kind`；五类换、context/other 不换 | 是 | 禁止 except ModelError / 解析 ⚠️ / import core | 与 R2-C1：若 worker 用 ⚠️ 识别失败气泡会违反本决策 | Q5 | 判定口成立；与 C1 耦合 |

#### spec 约束

| 原子 | 覆盖 | 不冲突 | 不越界 |
|---|---|---|---|
| Q9 先失败气泡（带模型名）再同轮换 | 决策 2、内核文案缝、原型三条消息 | 是 | 是 |
| 欠费等本轮仍收到备用回复 | 决策 1+2+replay | 机制依赖 C1/C2 接线 | 是 |
| 上下文太长不换 | 决策 6 `context_length` + CompactionError | 是 | 是 |
| 没配 / 整链耗尽 | 组链；耗尽每条带模型名 | 旅程段已改；Scenario 标题仍像「与现在完全一样」，design 风险已注明仅文案增加模型名，不另报 | 是 |
| 轻量说明 + 粘住不重复 | 决策 4；粘住后再撞主模型会破坏「不重复」→ C2 | 是 | 是 |
| 粘在聊天、不写回、`/new`、改配置、另一聊天 | 决策 3 | C2 会破坏「不再先撞主模型」 | 是 |
| 心跳/cron 同链 | 选模落点已改对 | 是 | 是 |
| 非目标 CLI/审批/多钥匙/`/model` | 决策 1 不把链放进内核；审批不走 kernel_client | CLI 只见失败文案变化，走 model-runtime | 是 |
| Q1–Q8 | retained；Q8「本轮继续回复」被 Q9 具体化为先失败再回复 | 是 | 是 |

#### delta-spec 条目

| 条目 | 锚 canonical / 用法 / THEN |
|---|---|
| kernel/model-runtime ADDED 失败文案含模型 id | 最窄 area 正确；THEN 可观察；滤掉失败 assistant 写的是消费者上下文 |
| kernel/model-runtime ADDED `error.kind` | 正确 ADDED；THEN「不需要解析失败气泡」可观察；消费者经 sdk |
| kernel/runs ADDED replay-last-user | 正确 ADDED（新能力非改 submit 旧 Scenario）；THEN 不复制 user 消息、有真实输出不可 replay |
| 未 MODIFIED「submit 必须非空 parts」 | 可接受：replay 是平行入口，不是改 submit 空 parts |
| gateway/agent-capabilities ADDED | Scenario 已跟 Q9；**需求正文仍「可见回复」** → R2-W1 |
| gateway/agent-capabilities MODIFIED 链头+粘性 | 正确 MODIFIED，原 Scenario 保留 |
| gateway/heartbeat-cron ADDED | 已改为失败提示带模型名 + 真实正文条件 |
| gateway/external-channels、im/agents-nodes | retained_from: Round 1 — 本轮未改语义；失败气泡走既有 assistant 文本外发 |
| cli / web-chat-ux no delta | 成立（文案在 model-runtime；气泡类型仍是 Agent） |
| sdk-boundary 无 delta | 可接受：不新增导出符号则 kind/replay 是 Kernel/stream 字段与方法 |

#### milestone

| 原子 | 结论 |
|---|---|
| 单 M1 垂直切片 | 成立：配置+三条缝+failover 仍是一条用户可观察切片 |
| 范围 | R1-W2 已补；含 kernel `runtime.py` / `registry.py`、`cron_execution_service.py`、`db.py`、`session_binder.py` |
| 两轨退出 | 成立：`[reviewer]` 含失败→已改用→正文；`[worker]` 含 kind/replay/不复制 user |
| 空目录 | 不报 |

### 架构进攻

#### 角度一·归属

三条缝放在 Kernel、链与粘性留在 Gateway，符合 `personal_assistant` 只经 `agent.sdk`、内核不持产品 fallbacks。不把 failover 列表塞进内核，审批/`tool_approval_model` 不会被误挂。叠加后：Gateway 必须在 **admit** 用 sticky、在 **replay 拒绝** 上认真实输出；这两处若不写进决策，产品层会倒逼解析内核文案（反向依赖展示层）。长远代价：包边界形式上守住、判定却靠气泡字符串，和 R1 同一类洞。

#### 角度二·该不该存在

replay-last-user：删掉则只能再 `submit(parts)`（复制 IM 用户气泡）或空 parts（`registry.py` 直接拒）。这层缝是必要的，不是假抽象。kind 投影：删掉则产品只能 parse message。失败文案带模型 id：Q9 要求。不报多余模块。

#### 角度三·深还是浅

没有重造 `RetryingLLMClient`。风险是聊天 / heartbeat_runner / CronRunTerminalConsumer 各猜「什么叫真实正文」和「第一次 admit 用谁」。接口若只说「包在等终态外面」，等于浅包一层现有 wait，真正的模型选择仍在 `_project_runtime`。长远代价：三处循环行为不一致，粘性只在一条路径生效。

#### 角度四·治本还是补丁

相对 R1：用 kind + replay 缝替代「完全不改内核硬叠循环」，是治本。未完成的是把这两条缝接到 **admit 与等终态判定**，否则仍会在 observer/`reply_text` 上打补丁。不报新的「不该开内核」——用户已拍 Q9，窄开是对的。

### 整体判断

上层能看懂：先失败气泡、再 replay、粘性在 Gateway、内核三条缝。原型三条消息与 Q9 一致。时序图仍画 `admit(主)`，把粘性路径藏进组链文字，人审核方向时容易以为每轮都先打主模型。风险段已覆盖重复用户消息与可见顺序。Runbook 要求看到「失败→已改用→正文」，与 Q9 对齐。M1 仍单切片，合理。

### Author Resolutions

- [R2-C1] **accepted**：生产 `assistant_message.metadata` 恒为 `{}`（`realtime_stream.py:82`），Gateway 不能靠 stream/`reply_text`/`⚠️` 区分失败气泡。产品循环写死：终态只看 `kind` 决定是否调用 replay-last-user；是否已有真实输出以内核拒绝为准。不新开第四条缝。落点：`design.md` 决策 2、「本轮何时换」、`specs/kernel/runs.md`。
- [R2-C2] **accepted**：生产 `_project_runtime` 只走 `resolve_run_model`（`session_run_coordinator.py:1786-1814`）。写死每次新回复第一次 admit 用 `candidates[0]`；时序图改为 `admit runtime(candidates[0])`。落点：决策 3、选模 §、时序图、`specs/gateway/agent-capabilities.md` MODIFIED、M1 `[worker]`。
- [R2-W1] **accepted**：已改掉 ADDED 需求正文「尚未投出可见回复」。
- [R2-W2] **accepted**：现状 L18 改为只消费 `run_status.error.kind`，禁止 `except ModelError`。
- [R2-R1] 采纳产品循环；拒绝第四条 `replay_eligible` 缝——内核拒绝 replay 已是权威口。
- [R2-R2] 已改时序图并点名 `_project_runtime` / `ensure_agent_runtime`。
- [R2-R3] 已改 gateway delta 与现状 L18。

## Round 3

### Metadata

- reviewer: `feat-541-design-reviewer`
- review_mode: `delta`
- mode_reason: spec/非目标未变；三条内核缝与 Gateway 持链的架构未变。本轮是 R2 决议的有界接线（产品循环、第一次 admit、delta 措辞）。发现心跳 submit 与 admit 冲突后仍保持 delta，未升级 full（影响封闭在 unattended 入队口）。
- started_at: `2026-08-18T11:34:00+08:00`
- completed_at: `2026-08-18T11:36:35+08:00`
- duration: `3m`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-C1 | accepted：只看 `kind`；真实输出以内核拒绝 replay 为准；不看 `reply_text`/`⚠️`/stream metadata；不第四条缝 | 决策 2、「本轮何时换」五步循环、`specs/kernel/runs.md` Scenario「仅 provider-error 气泡不阻止 replay」均写死。聊天路径 `submit` 不传 `model=`，与该循环兼容 | closed |
| R2-C2 | accepted：第一次 admit 用 `candidates[0]`；时序图改为 `admit runtime(candidates[0])` | 决策 3、选模 §2、时序图、gateway MODIFIED「有粘性则第一次就用粘性模型」、M1 `[worker]` 已接线。**聊天** `_project_runtime` 改完即可。心跳/cron 入队仍 `submit(model=链头)`，与 admit sticky 冲突 → R3-C1 | closed（聊天 admit）；残留见 R3-C1 |
| R2-W1 | accepted：ADDED 正文不再写「尚未投出可见回复」 | `specs/gateway/agent-capabilities.md` L10 已改为先失败提示，再用「非失败气泡的真实正文」 | closed |
| R2-W2 | accepted：现状不写消费 `ModelError` | design.md L18 已改为读 `run_status.error.kind`，禁止 except/import core | closed |

### Issues

- [R3-C1][CRITICAL] [选模 §3 心跳/cron / `kernel_client.submit_message`]: R2-C2 只把 **admit** 接到 `candidates[0]`，没有把 **入队 `kernel.submit` 的 model** 接到同一候选。生产上心跳在 `ensure_agent_runtime` 之后仍 `submit_message(model=agent.default_model)`（`heartbeat_scheduler.py:518-525`）；shim 把 explicit 解成链头再 `kernel.submit(model=resolved_model)`（`kernel_client.py:218-229`）。内核要求 submit model 与 session runtime 一致，否则 `ValueError`（`kernel.py:1755-1758`）。design 还写「`submit_message(model=agent.default_model)` 只当作组链的链头输入，第一次 admit 仍用 `candidates[0]`」——等于承认继续传主模型。不改 → 直聊已粘在备用 B 后，心跳复用同一 `kernel_session_id`（决策 3），`ensure_agent_runtime(B)` + `submit(model=主)` 直接被拒，Q6「心跳走同一条链」在粘性场景上不可用。cron 新建会话时 sticky 通常为空，风险低于心跳，但同一 shim 只要 `resolve_run_model` 出链头、runtime 已是 sticky，同样炸。

### Recommendations

- [R3-R1] 写死：心跳/cron 入队的 `kernel.submit` 必须 `model=candidates[0]` 或省略 `model=`（让 runtime 生效）。删掉「submit_message(model=agent.default_model) 只当链头输入」这句。组链仍可用 `resolve_run_model` 当链头；explicit 不得盖住 sticky。

### Coverage

本轮 `delta`：核 R2 四条 issue 的落点 + 组链/admit/产品循环/kernel replay Scenario 的上下游。未改 spec/原型/其它 delta。其余原子 `retained_from: Round 2 — 架构与契约未再移动`。

### 本轮重查

| 原子 | 结论 | 证据 |
|---|---|---|
| 决策 2 产品循环 | 成立 | 不读气泡/`reply_text`；`kind` 决定是否 replay；内核拒绝则收口。对准 `session_run_coordinator.py:2176-2179` 与 `realtime_stream.py:82` 的陷阱 |
| kernel/runs replay | 成立 | 新 Scenario 明确「仅失败气泡不阻止」；THEN 可观察 |
| 决策 3 + 时序图 admit `candidates[0]` | 聊天成立 | 与 `_project_runtime` 改点对齐；图已是 `admit runtime(candidates[0])` |
| 心跳第一次 admit | 半成立 | 点名了 `ensure_agent_runtime`；**未点名改 `submit_message` 的 explicit model** → R3-C1 |
| gateway ADDED 正文 | 成立 | 已无「尚未可见回复」 |
| 现状 L18 | 成立 | 判定入口改为 `kind` |
| M1 `[worker]` | 聊天/判定成立；心跳入队未写 model 匹配 | |

`retained_from: Round 2` — 决策 1/4/5/6、配置字段、IM/external-channels delta、单 M1、原型 must-match、Q9 可见顺序。

### 架构进攻（受影响角度）

- **角度一·归属**：拒绝第四条 `replay_eligible` 缝成立——replay 拒绝口已在内核。缺口是产品层 heartbeat shim 仍用链头 explicit 打进 `submit`，和 sticky runtime 抢模型。长远代价：canonical 直聊一粘性，心跳整条不可用，failover 只在 Web IM 真。
- **角度三·深还是浅**：聊天 admit 已接到 `_project_runtime`；心跳若只改 `ensure_agent_runtime`、不改 `submit_message`，是浅接线。必须让 admit 与 submit 的 model 是同一个 `candidates[0]`。
- 角度二/四 retained_from Round 2：三条缝仍必要，不是补丁。

### Author Resolutions

- [R3-C1] **accepted**：独立核成立。心跳 `submit_message(model=agent.default_model)`（`heartbeat_scheduler.py:518-525`）经 shim `resolve_run_model(explicit=…)`（`kernel_client.py:218-229`）打进链头；内核 `submit model must match the session runtime`（`kernel.py:1755-1758`）。直聊粘在备用后心跳复用同一 session 会被拒。已写死：入队 model 与 `candidates[0]` 相同或省略；禁止再传主模型 explicit。落点：决策 3、选模 §3、时序主流程、`specs/gateway/heartbeat-cron.md`、M1 `[worker]`、风险段。
- [R3-R1] 已按建议改。

## Round 4

### Metadata

- reviewer: `feat-541-design-reviewer`
- review_mode: `delta`
- mode_reason: spec/非目标/三条内核缝/Gateway 持链未变。本轮只补 R3-C1 的心跳/cron 入队接线与 `heartbeat-cron` 新 Scenario。发现「省略 model=」在 `submit_message` 上不等于聊天后仍保持 delta，未升级 full（影响仍封闭在 unattended 入队口）。
- started_at: `2026-08-18T11:38:00+08:00`
- completed_at: `2026-08-18T11:40:00+08:00`
- duration: `2m`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R3-C1 | accepted：入队 model 与 `candidates[0]` 相同或省略；禁止再传主模型 | 禁止传 `agent.default_model` 已写进决策 3、选模 §3、主流程、风险段、M1 `[worker]`、`heartbeat-cron` 新 Scenario。但「省略」在生产 `submit_message` 上仍会注入链头，与 R3-C1 同一失败模式 | **未闭环**（残留见 R4-C1） |
| R3-R1 | 已按建议改 | 建议里的「或省略」被原样写进 design，而聊天省略成立的前提（直调 `Kernel.submit`）心跳/cron 不具备 | 建议本身把陷阱写进了契约 |

### Issues

- [R4-C1][CRITICAL] [选模 §3 心跳「或像聊天一样省略 `model=`」 / 风险段 / R3-C1 残留]: R3 要求入队与 admit 同一 `candidates[0]`。作者把「传 `candidates[0]`」和「像聊天一样省略」写成等价二选一。聊天省略成立，是因为 `SessionRunCoordinator` **直调** `kernel.submit` 且不传 `model=`，内核在 `runtime_model is not None` 时用 runtime（`kernel.py:1755-1759`；聊天入队 `session_run_coordinator.py:1387-1393`）。心跳/cron **不走这条路**：它们只调 `InProcessKernelClient.submit_message`（全仓仅此两处：`heartbeat_scheduler.py:518-525`、`cron_runner.py:149-157`）。shim 无论 caller 是否传 `model=`，都 `resolve_run_model(...)` 再 `kernel.submit(model=resolved_model)`（`kernel_client.py:218-229`）。`explicit` 为空时 `resolve_run_model` 返回 `agent.default_model`（`local_store.py:669-672`），不是「让 runtime 生效」。因此 worker 按 §3 最便宜的改法——删掉心跳的 `model=agent.default_model`、cron 继续只传 `agent_id=`——admit 已经是 sticky B 后，submit 仍打进链头，内核照样 `ValueError`（`kernel.py:1757-1758`）。`heartbeat-cron` 新 Scenario「第一次就用 B」在这条实施下不可用。决策 3 一句话写「admit 和 submit 都用 `candidates[0]`」是对的；§3 / 风险段的「或省略」把它拆成一条在生产 shim 上不成立的等价物。

  不改 → 两个 worker：(a) 传 `model=candidates[0]`（闭合）；(b) 只删 explicit、不改 shim（R3-C1 原样复发）。orchestrator 无法按现在的二选一派工。

### Recommendations

- [R4-R1] 选模 §3 心跳/cron **删掉「像聊天一样省略」**，只保留显式 `model=candidates[0]`。若坚持省略，必须**同时**改 shim：未传 `model=` 时不要把 `resolve_run_model` 的链头打进 `kernel.submit`（让已 admit 的 runtime 生效）。风险段同样去掉「或省略」，或写明省略的前提是改 `kernel_client.submit_message`。组链仍可用 `resolve_run_model` 当链头。

### Coverage

本轮 `delta`：核 R3-C1 落点（决策 3、选模 §3、主流程、风险、M1 `[worker]`、`specs/gateway/heartbeat-cron.md` 新 Scenario）+ 生产 `submit_message` / shim / `Kernel.submit` 三跳。未改 spec/原型/其它 delta。其余原子 `retained_from: Round 3 — 架构与聊天路径未再移动`。

### 本轮重查

| 原子 | 结论 | 证据 |
|---|---|---|
| 决策 3 一句话：admit + submit 都用 `candidates[0]` | 成立 | L93；心跳禁止再传 `agent.default_model` 当 explicit（L95）对准 `kernel.py:1755-1758` |
| 选模 §3 入队必须与 admit 相同 | **半成立** | 传 `candidates[0]` 闭合；「像聊天一样省略」在 `kernel_client.py:218-229` 上不成立 → R4-C1 |
| 接口主流程 | 成立（约束） | L125「不得再传保存的主模型」；时序图仍是聊天 `submit(parts)`，不覆盖心跳 shim |
| `heartbeat-cron` 新 Scenario | 产品 THEN 成立 | 「第一次就用 B / 不因传入主模型失败」可观察；实施若走省略则 Scenario 落空 |
| 现状 `kernel_client` L15 | 成立 | 独立追到：心跳 `heartbeat_scheduler.py:518-525` `model=agent.default_model`；shim `kernel_client.py:218-229`；`explicit` 空则链头 `local_store.py:669-672` |
| cron 入队 | 与 R3 相同风险形态，sticky 更少 | `cron_runner.py:149-157` 不传 `model=`、传 `agent_id=`，shim 仍 `resolve_run_model` 出链头。新建会话 sticky 通常为空，与 admit 链头碰巧一致；一旦复用已粘 session 同样炸 |
| M1 `[worker]` | 半成立 | L331 写了「入队 model 与之相同」和禁止 `model=agent.default_model`；未排除「只删 kwargs、不改 shim」 |
| 风险「心跳 submit 盖住粘性」 | 应对不完整 | L289「相同（或省略）」把 R4-C1 写进了应对 |

`retained_from: Round 3` — 决策 1/2/4/5/6、聊天 `_project_runtime`、三条缝、IM/external-channels/kernel delta、单 M1、原型 must-match、Q9 可见顺序。

### 架构进攻（受影响角度）

- **角度三·深还是浅**：R3 已指出必须让 admit 与 submit 同一 `candidates[0]`。本轮把「省略」写成与聊天等价，是浅接线——没碰到真正注入模型的 `submit_message`（`kernel_client.py:223-228`）。长远代价：worker 改完 `heartbeat_scheduler` 单测红，再回头改 shim，粘性心跳仍是第二条实现。
- **角度一·归属**：谁负责把 `candidates[0]` 打进 `kernel.submit`——caller 显式传，还是 shim 停止用 `resolve_run_model` 当 implicit explicit——没拍死。两条都能闭合，但不能假装已经等价。角度二/四 retained_from Round 3。

### Author Resolutions

- [R4-C1] **accepted**：独立核成立。聊天省略 `model=` 是因为直调 `Kernel.submit`（`session_run_coordinator.py:1387-1393`）。心跳/cron 只走 `submit_message`，shim 总会 `kernel.submit(model=resolved_model)`（`kernel_client.py:218-229`）；省略时 `resolve_run_model` 仍出链头（`local_store.py:669-672`）。已删掉「像聊天一样省略」；心跳/cron 只保留显式 `model=candidates[0]`。落点：现状 `kernel_client`、决策 3 理由、选模 §3、主流程、风险、M1 `[worker]`、`heartbeat-cron`。
- [R4-R1] 已按建议改：只保留显式传入，不走「省略且改 shim」那条并行路。

## Round 5

### Metadata

- reviewer: `feat-541-design-reviewer`
- review_mode: `closure`
- mode_reason: spec/非目标/三条缝/Gateway 持链未变。本轮只把 R4-C1 的二选一锁成「心跳/cron 显式 `submit_message(model=candidates[0])`」，删掉省略等价物；`heartbeat-cron` 同步写「不得省略」。无新架构边界、无无法枚举的共享契约变化。
- started_at: `2026-08-18T11:41:00+08:00`
- completed_at: `2026-08-18T11:43:00+08:00`
- duration: `2m`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R4-C1 | accepted：删掉「像聊天一样省略」；只保留显式 `model=candidates[0]`；不改 shim | 独立再追生产三跳：聊天仍直调 `Kernel.submit` 且不传 `model=`（`session_run_coordinator.py:1387-1393`）；心跳 `submit_message(model=agent.default_model)`（`heartbeat_scheduler.py:518-525`）、cron 只传 `agent_id=`（`cron_runner.py:149-157`）；shim 无论是否传 model 都 `resolve_run_model` 再 `kernel.submit(model=resolved_model)`（`kernel_client.py:218-229`），`explicit` 空则链头（`local_store.py:669-672`），与 runtime 不一致则拒（`kernel.py:1755-1758`）。design 现状 L15、决策 3 理由、选模 §3、主流程 L125、风险 L288、M1 `[worker]` L330 均只允许显式 `candidates[0]`，禁止省略。传 `explicit=B` 时 shim 原样返回 B，与 sticky admit 对齐，R4 的 (b) 路已关掉 | closed |
| R4-R1 | 已按建议改 | 未保留「省略且改 shim」并行路 | closed |
| R3-C1 | 经 R4 残留未闭环 | 显式传入锁死后，粘性心跳不再被链头 explicit 盖住 | closed |

### Issues

无。

### Recommendations

无。

### Author Resolutions

- 本轮无新 Issue。作者核对 R4-C1 / R3-C1 闭环证据与 `design.md` 选模 §3、`heartbeat-cron`「不得省略」一致；Round 5 完成后不再改受审产物。

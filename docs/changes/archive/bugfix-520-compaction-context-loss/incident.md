# bugfix-520: 自动压缩丢失长任务上下文

## Relations

- Related: `refactor-462`（引入 `JsonlTranscript.list_event_entries()` 投影路径）
- Related: `feat-330`（JSONL compaction boundary 与 resume 持久化）
- Related: `bugfix-443`（压缩模型继承回归，但真栈未触发阈值压缩）

## 原始报告

> [http://100.88.34.122:8011/chat/553cd222c972444b8006a42be23512dc](http://100.88.34.122:8011/chat/553cd222c972444b8006a42be23512dc) 最后是啥问题啊？压缩机制出了问题吗？

> 1. 为什么没有任何测试或者e2e测试发现这个问题，压缩是一个这么重要的特性
> 2. 看当初的设计，应该是参考CC的，你给我开个unit做修复

## 澄清记录

- 用户要求：`本unit要补长青 E2E上下文压缩`
- 已确认：本 unit 必须把上下文压缩连续性补成长期维护的 E2E 关键路径和发布门禁，而不是仅保留临时复现脚本或单元测试。
- 用户确认失败语义：`按照CC的业务逻辑来`
- 已确认：以 Claude Code 的用户可观察业务语义为基线；摘要失败不得伪装为压缩成功、不得写入虚假摘要或切断原历史，自动压缩连续失败应熔断并显式暴露问题。
- 用户确认三个入口统一语义：`对`
- 已确认：手动压缩、自动阈值压缩、overflow 恢复必须遵守同一套不丢上下文语义，并纳入回归矩阵。
- 用户确认 E2E 数量：`对。好。这个需要一个长的jsonl对吧，可以用刚刚失败了哪个`
- 已确认：本 unit 新增一个上下文压缩长青 E2E 关键旅程；其他成功/失败组合由稳定的单元测试和集成测试覆盖。
- 用户确认 fixture 约束：`一点不用考虑敏感，但是确实不用200K，可以短点，短而完整的`
- 已确认：E2E fixture 可以从本次生产失败 JSONL 提炼，不要求制造 200K+ token；样本必须短而完整，保留 user、assistant tool call、匹配 tool result、压缩触发与后续继续任务所需的真实结构。
- 用户追问飞书失败闭环：`按你这个设计，如果用户是在飞书上用的话，然后他触发了自动压缩，然后压缩又失败了，用户会收到什么提示消息吗？`
- 已确认：前两次 threshold summary 失败仍可使用原上下文时不产生噪音提示；第三次连续失败或 overflow summary 失败导致本轮无法继续时，必须在 failed terminal 前向用户发送“上下文压缩失败，已停止本轮以避免丢失对话内容。原对话仍保留。请稍后重试，或发送 /compact <希望保留的重点> 后继续。”；飞书触发时同一文本回原 chat 并同步 IM shadow。该显式提示是本 unit 的 Nano 产品决策，不宣称 Claude Code 固定源码具有相同文案或投递行为。

## 现象与复现

2026-08-09 的生产会话 `553cd222c972444b8006a42be23512dc` 在长任务执行过程中触发自动阈值压缩。压缩前的原始 JSONL 仍完整保存了用户请求、assistant tool call 和对应 tool result；压缩后，运行时只看到固定 fallback 摘要，其中 `All user messages`、`Pending Tasks` 等关键字段均为 `None` 或泛化占位文本，随后 assistant 无法识别正在执行的任务。

已在生产版本 `b0aedcb4` 上完成确定性、无写入复现：

1. 原始 tool result 的 `tool_call_id` 存在且可由 transcript 的常规 `load()` 路径恢复。
2. 同一条 raw turn 经 `JsonlTranscript.list_event_entries()` 投影为 `SessionEntry`，再经 `message_from_turn_entry()` 重建后，`tool_call_id` 变为 `None`。
3. compaction summarizer 把该消息序列交给 provider mapper 时触发 `tool message requires tool_call_id`。
4. 自动压缩捕获异常后返回固定 fallback 摘要，仍提交 `compact_boundary`。
5. 后续加载按最新 boundary 跳过此前完整历史，只剩无业务内容的 fallback 摘要，造成静默上下文丢失。

该复现不依赖摘要模型质量、token 估算误差或偶发网络状态；只要待压缩窗口包含 tool result，就可能稳定触发结构字段丢失。

## 影响范围

- **自动阈值压缩**：高风险。摘要失败被伪装成成功并提交 boundary，用户正在执行的长任务会静默丢失上下文。
- **overflow 恢复压缩**：高风险。与自动阈值压缩共用非 strict 摘要路径，同样可能用固定 fallback 覆盖有效历史后继续重试。
- **手动 `/compact`**：当前 strict 路径不会在摘要失败时提交 boundary，因此原历史仍在，但包含工具历史的正常会话可能无法完成手动压缩。
- **恢复与重启**：原始 JSONL 数据没有被物理删除，但最新 compact boundary 是运行时上下文起点；重启或 resume 不会自动绕过已经提交的坏摘要。
- **适用会话**：Coding CLI 与 Personal Assistant 共用 kernel compaction 机制；任何包含工具调用并达到压缩条件的长会话均在风险范围内。

本事故不只是单个 provider 的兼容问题。provider mapper 的报错揭示了 transcript 投影已经破坏核心消息不变量；即使某个 provider 容忍缺失字段，压缩输入也已不再是原始会话的无损表示。

## 根因分析（RCA）

### A. Transcript 事件投影丢失结构字段

`JsonlTranscript.list_event_entries()` 在处理 raw `turn` 时，仅把 `_turn_metadata(raw)` 作为 metadata 传入 `new_turn_appended_entry()`。`_turn_metadata()` 保留 `tool_calls`、`tool_name` 等字段，却不包含 `tool_call_id` 与 `group_id`。

下游 `message_from_turn_entry()` 又从 `entry.data["tool_call_id"]` 和 `entry.data["group_id"]` 顶层读取这两个字段。生产者没有写、消费者却假设存在，导致 tool result 与 tool call 的对应关系在 compaction 专用投影路径上丢失。

该不对称由 `refactor-462` 引入。已有 transcript 测试覆盖常规 `load()`、持久化 tail、恢复和 compaction epoch，却没有覆盖 `raw turn → SessionEntry → Message` 的结构字段 round-trip 契约。

### B. 自动摘要失败被错误地转换成“成功”

`CompactionSummarizer.summarize(strict=False)` 捕获任何异常后返回固定 `_fallback_summary()`。该摘要不包含真实请求、技术上下文、文件、用户消息或待办，但调用方仍把它当作有效摘要并提交 boundary。

这一 fallback 源于历史 M16 “摘要模型失败时不中断主流程”的稳定性硬化。它优化了流程存活，却破坏了 compaction 更重要的业务不变量：只有能够继续原任务的摘要才有资格替代历史。失败因此从可观察错误变成不可逆的静默语义丢失。

Claude Code 的公开业务契约是通过摘要释放上下文并保留请求和关键工作，而不是以无业务内容的占位摘要替换历史：

- [How Claude Code works — When context fills up](https://code.claude.com/docs/en/how-claude-code-works#when-context-fills-up)
- [Explore the context window — What survives compaction](https://code.claude.com/docs/en/context-window#what-survives-compaction)

固定版本的参考源码观察也一致：压缩异常返回 `wasCompacted=false`，原消息不被替换，并通过 query 内连续失败计数有界停止新的 auto-compact 尝试。该源码不会在第三次 summary exception 时主动发送用户消息；公开 troubleshooting 的可见错误描述的是“压缩成功后上下文立即再次填满”的 thrashing，是另一种故障。nano 原始 compaction 确实参考了 CC 的结构化摘要 prompt，后续持久化也参考了 compact boundary，但“固定空摘要也算成功”是偏离 CC no-replacement 原则的本地设计。本 unit 复用该原则和 bounded retry；跨 threshold/overflow 的 session 级计数与固定用户提示是经用户确认的 Nano 增量。

### C. 测试分层在关键接缝处断开

现有测试分别证明了局部组件能工作，却没有证明真实压缩输入能无损穿过完整链路：

- loop 单元测试使用 `_FakeCompactionEntries` 与固定 `_FakeCompactionSummarizer`，绕过真实 transcript 投影和 provider 消息校验。
- kernel compaction 集成测试使用纯文本对话与固定响应 client，只验证 threshold、boundary、restart 等控制流，不包含 assistant tool call + tool result。
- transcript 单元测试验证常规 `load()` 能恢复工具字段，没有验证 `list_event_entries()` 的 round-trip。
- 历史真实验收使用简单对话验证手动 compact/resume；`bugfix-443` 明确因实际上下文约 12K、低于 200K+ 阈值而只用单元测试验证阈值压缩。
- `docs/development/e2e-critical-paths.md` 已把“上下文压缩恢复”登记为后续 unit，但从未落成长期运行的 E2E 门禁。
- M16 的故障注入测试把“summary 失败后 fallback 并继续”作为绿色期望，反而固化了本次事故中的危险行为。

因此，现有门禁能发现“压缩没有触发”“boundary 没写”“resume 没加载摘要”，却无法发现“摘要输入已经损坏”以及“无业务内容的摘要被误判为成功”。

## 修复方向

### 业务不变量

1. compaction 输入必须无损保留 tool call、tool result、并行分组和结构化 parts 的配对关系；不能只保证纯文本 content。
2. 只有成功生成可用于继续原任务的摘要，才能提交 compact boundary 并替换活动历史。
3. 摘要失败时不得写入固定空摘要或其他虚假成功记录；原 transcript、活动历史和 compaction boundary 保持不变。
4. 手动压缩、自动阈值压缩、overflow 恢复遵守同一套不丢上下文语义。
5. 自动压缩失败复用 CC 的 no-replacement 与 bounded retry 原则，避免每轮无限重试；按本 unit 确认的 Nano 语义跨 threshold/overflow 跟踪 session 级连续失败，并在到达无法继续的上下文边界时显式暴露可诊断错误和用户安全提示。
6. 已成功提交的压缩在当前进程、restart 和 resume 后都必须保持任务连续性。

### 长青回归门禁

本 unit 必须新增一个长青 E2E 关键旅程，把“上下文压缩恢复”从 E2E backlog 移入长期维护的关键路径套件。门禁不得依赖制造 200K+ token 的真实成本；可以从本次生产失败 JSONL 提炼短而完整的 fixture，并通过受控 context window、阈值或等价的稳定测试配置触发真实 kernel compaction 链路，同时保留产品真实的数据投影、事务和恢复路径。

最低回归矩阵：

| 入口 | 摘要结果 | 必须验证 |
|---|---|---|
| 自动阈值 | 成功 | 含 tool call/result 的长任务完成压缩，下一轮仍能准确继续原请求 |
| 自动阈值 | 失败 | 不提交 boundary、不替换历史；连续失败有界熔断，并按本 unit 的 Nano 语义显式可诊断 |
| overflow 恢复 | 成功/失败 | 成功后只重试一次并保持任务；失败时原历史不变且不伪装成功 |
| 手动 `/compact` | 成功/失败 | 成功后继续任务；失败返回可观察结果且 transcript 不变 |
| restart / resume | 已成功压缩 | 从持久化 boundary 恢复后仍能继续压缩前的用户目标与待办 |

至少一个常驻 E2E 场景必须贯穿真实 `JsonlTranscript → SessionEntry → Message → compaction summarizer → compact boundary → 后续 turn` 链路，并包含真实的 assistant tool call 与匹配 tool result。单元测试和仅返回固定摘要的局部集成测试不能替代该场景。

### 非目标

- 不在本 unit 引入 Claude Code 的 Session Memory Compact、MicroCompact、Context Collapse 等新产品能力。
- 不重做摘要 prompt 或以主观摘要质量优化扩大修复范围。
- 不删除历史 transcript，也不通过忽略 provider 的 tool 配对校验掩盖结构字段丢失。

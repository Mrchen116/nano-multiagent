# kernel (agent) - Context and Persistence Specification

> 对齐: bugfix-471, bugfix-520
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

上下文压缩、会话档案、事件溯源、带外消息、transcript 闭合、项目指令、图片历史和 fork 的对外契约。

## Requirements

### Requirement: 上下文压缩在长会话中保持可恢复

内核在 LLM 调用前后检查上下文是否接近/超出上限，必要时把旧轮次摘要化并落盘为压缩记录，保留首个保留事件 id 以保证可重建与可审计；overflow 后可恢复重试。包含 assistant tool call、匹配 tool result、并行分组或结构化内容的可恢复历史进入压缩时，这些关系在压缩结果与后续会话中保持有效。只有摘要移除 provider reasoning 等非正文内容后仍为非空有效文本，且 compaction record 持久提交成功，内核才以摘要替换活动上下文；摘要为空、生成错误或提交失败时，不追加 compaction record，也不以通用摘要替换原历史。用于生成摘要的内部模型交互不投影为本轮的 assistant 消息或 turn 事件。

消费者也可手动触发压缩，且可经 `await kernel.compact(session_id, workspace_root=..., focus=..., idempotency_key=...)` 为这一次手动压缩提供可选非空文本重点和可选 opaque operation identity。内核用 focus 指导被摘要的旧窗口应优先保留什么，但不把 focus 作为普通用户消息或独立会话事件写入；同一非空 idempotency key 重试复用已经提交的 manual compaction，不产生第二条压缩边界。自动阈值和 overflow 压缩不接收也不受这两个参数影响。

手动压缩失败以可辨识错误结束。自动阈值摘要失败时，内核在仍可调用模型的前提下保留原上下文继续；同一进程中的同一会话连续三次自动摘要失败后停止新的自动摘要尝试，先向消费者流发送一条用户可见 assistant 消息“上下文压缩失败，已停止本轮以避免丢失对话内容。原对话仍保留。请稍后重试，或发送 `/compact <希望保留的重点>` 后继续。”，再以可辨识失败结束，避免无限重试。overflow 恢复摘要失败时不发起压缩后的模型重试，发送同一 assistant 消息，并在 failed terminal 的诊断信息中保留原始 overflow failure。该失败提示不作为普通会话历史提供给后续模型。任一成功压缩重置连续自动失败状态；该状态不进入会话档案，进程重启后可重新尝试。compaction record 持久化异常导致 automatic compaction 无法继续时发送同一提示并以可辨识失败结束，但不计作 summary failure。

压缩判定所用的**上下文上限按当前轮所用模型取**：消费者经 `build_kernel(llm=…)` 为某模型声明的上下文窗口生效于该模型的运行；未声明窗口的模型回退到内核默认上限。判定上限时保留的安全余量是全局策略量，不随模型变化。

#### Scenario: 手动触发压缩
- **WHEN** 消费者 `await kernel.compact(session_id)`
- **THEN** 返回压缩结果(或在无需压缩时返回 None),压缩落盘后会话仍可由事件重放重建

#### Scenario: focus 指导手动压缩的后续上下文
- **GIVEN** 一个已有可压缩历史的 workspace-bound session，历史包含认证方案和未完成事项
- **WHEN** 消费者调用 `await kernel.compact(session_id, workspace_root=..., focus="保留认证方案与未完成项")`
- **THEN** 返回压缩结果并落盘，后续运行可从压缩摘要延续该重点
- **AND** transcript 不包含一条把 focus 当作普通 user turn 的独立消息

#### Scenario: 手动压缩摘要失败不改变上下文
- **GIVEN** 一个已有可压缩历史的 session
- **WHEN** 消费者发起手动 compact，但摘要生成为空或发生错误，或 compaction record 无法持久提交
- **THEN** 调用以可辨识错误结束
- **AND** 不追加 compaction record，后续运行仍能使用压缩前的可恢复上下文

#### Scenario: 自动阈值压缩失败不伪装成功
- **GIVEN** 一个达到自动压缩阈值且包含完整工具调用历史的 session
- **WHEN** 摘要生成为空或发生错误
- **THEN** 不追加 compaction record，不以通用摘要替换活动上下文
- **AND** 在当前上下文仍可用时，后续模型调用继续看到压缩前的可恢复历史

#### Scenario: 只有 reasoning 的摘要响应视为失败
- **GIVEN** 摘要模型返回了 provider reasoning，但移除 reasoning 后没有摘要正文
- **WHEN** 内核校验本次摘要结果
- **THEN** 按空摘要失败处理，不追加 compaction record，也不以空文本替换活动上下文

#### Scenario: 摘要生成的内部事件不泄露给消费者
- **WHEN** 内核为 threshold、overflow 或 manual compaction 调用摘要模型
- **THEN** 消费者不会收到该内部模型调用产生的 assistant 消息或 turn 事件
- **AND** automatic compaction 只有在按本契约需要报告失败时才发送固定失败消息

#### Scenario: 连续自动压缩失败有界并可诊断
- **GIVEN** 同一 session 已连续两次自动摘要失败，期间没有成功压缩
- **WHEN** 第三次自动摘要仍失败，或失败上限后再次需要自动压缩
- **THEN** 消费者在 failed terminal 前收到上述用户可见 assistant 失败消息，本轮再以可辨识压缩失败结束，不继续重复调用摘要模型
- **AND** transcript 仍无这些失败尝试对应的 compaction record

#### Scenario: overflow 恢复摘要失败保留原错误与历史
- **GIVEN** 一次模型调用因上下文 overflow 失败，且内核无法获得有效压缩摘要
- **WHEN** 内核尝试 overflow 恢复
- **THEN** 不发起压缩后的模型重试，在 failed terminal 前发送上述用户可见 assistant 失败消息，并在诊断信息中保留原始 overflow failure
- **AND** 不追加 compaction record，后续恢复仍可读取压缩前历史

#### Scenario: 压缩记录持久化失败不暴露半提交上下文
- **GIVEN** manual、threshold 或 overflow 已获得有效摘要，但 compaction record 无法持久提交
- **WHEN** 本次压缩结束
- **THEN** 不追加 compaction record，也不以未提交摘要替换活动上下文
- **AND** manual 调用以可辨识错误结束；automatic 路径在 failed terminal 前发送上述 assistant 失败消息，诊断信息区分持久化失败与 summary failure

#### Scenario: 含工具历史的压缩在重启后继续任务
- **GIVEN** 一个会话的可压缩历史包含 assistant tool call、匹配 tool result 和尚未完成的用户目标
- **WHEN** 自动阈值、overflow 或手动压缩成功，随后消费者继续运行该会话或在进程重启后恢复它
- **THEN** 后续运行仍能延续压缩前的用户目标与未完成事项，且会话可从已提交的 compaction record 恢复
- **AND** 压缩边界后的项目指令重新注入不截断该摘要的可恢复父链

#### Scenario: 成功压缩后不沿用压缩前的 token 判定重复压缩
- **GIVEN** manual 或 overflow compaction 已成功提交，活动上下文已替换为压缩后历史
- **WHEN** 内核继续该会话但还没有新的模型 usage
- **THEN** 不仅因压缩前一次模型调用的 token 数再次触发 threshold compaction
- **AND** 下一次模型调用直接使用刚提交的压缩后历史

#### Scenario: 自动压缩不继承手动关注点
- **GIVEN** 一个 session 曾以 focus 完成手动压缩
- **WHEN** 该 session 后续因 token threshold 或 overflow 自动压缩
- **THEN** 自动压缩按既有 planner 和摘要策略执行，不复用先前手动 focus

#### Scenario: 相同手动操作 identity 不重复压缩
- **GIVEN** 消费者已使用非空 `idempotency_key` 成功完成一次手动压缩
- **WHEN** 消费者因重放或响应丢失以相同 key 再次调用 `kernel.compact`
- **THEN** 内核返回第一次已提交的手动压缩结果
- **AND** transcript 不新增 compaction record，focus 文本不作为该 identity 的替代

#### Scenario: 按当前轮模型的窗口判定压缩
- **GIVEN** 消费者为某模型声明了与内核默认不同的上下文窗口
- **WHEN** 用该模型推进一个持续增长的会话直到接近"该模型窗口 − 全局安全余量"
- **THEN** 内核在该模型窗口对应的边界触发压缩,而非内核默认上限对应的边界

#### Scenario: 未声明窗口的模型回退默认上限
- **GIVEN** 某模型未声明上下文窗口(或声明值非正整数)
- **WHEN** 用该模型推进会话
- **THEN** 内核按默认上限判定压缩,运行不因缺少该声明而报错

#### Scenario: 工作区绑定的会话压缩落盘后运行透明继续
- **GIVEN** 一个绑定了 `workspace_root` 的会话(消费者经 `create_session(workspace_root=…)` 创建),其上下文已增长到触发压缩(自动阈值或 overflow 恢复)
- **WHEN** 消费者继续推进该会话一轮
- **THEN** 内核完成压缩并落盘,该轮以成功终态正常完成,**不因无法定位会话存储位置而失败**;压缩后会话仍可由事件重放重建,且先前轮次内容不被清空

### Requirement: 会话档案为无状态 per-workspace JSONL

会话档案是每会话一个 append-only JSONL,落 `{workspace_root}/{workspace_config_dirname}/sessions/{session_id}.jsonl`。存储组件无状态(不持 session→位置映射,按调用方传的 `workspace_root` 当场定位);位置由 `create_session(workspace_root)`决定,无中心 session db 路径配置。

#### Scenario: 不同 agent 会话落各自 workspace
- **GIVEN** 两个会话以不同 `workspace_root` 创建
- **WHEN** 各自产生 turn
- **THEN** 档案分别落各自 `workspace_root` 下,互不混写

### Requirement: 会话事件溯源持久化,进程重启后可恢复

每次状态变更产生事件并经会话存储持久化;会话可由事件重放重建,进程重启后可恢复。运行时不直接写 SQL, 只经会话存储接口。

#### Scenario: 重启后恢复会话
- **GIVEN** 一个已持久化的会话
- **WHEN** 进程重启后消费者按 session_id 取该会话
- **THEN** 会话历史与状态可由持久化事件重放重建

### Requirement: 经 append_message 带外写入的消息对后续轮次可见

消费者(如 Gateway)可在不触发模型运行的前提下,经 `append_message` 把一条消息持久化进会话;该消息进入会话线性历史,对该会话此后任意一轮运行可见——既不被丢弃,也不被运行时的内存历史遮蔽。`append_message`在返回前自动同步该会话的持久化与 live state;消费者不负责管理或失效内核缓存。

#### Scenario: 带外追加的消息进入下一轮上下文
- **GIVEN** 一个已运行过至少一轮的会话
- **WHEN** 消费者经 `append_message` 向该会话追加一条消息,随后再提交一轮运行
- **THEN** 该追加消息出现在这一轮的模型上下文里(不被陈旧缓存或历史链断裂遮蔽)

### Requirement: 持久化 transcript 在进入模型前保持 tool call 闭合

消费者中断、取消或关闭包含工具调用的运行后,内核必须使已持久化的每个 assistant tool call 具有对应的 tool result。进程异常退出留下的历史悬空调用在下次提交运行前自动恢复为取消终态; 恢复保持 append-only、按 tool call id 幂等,并向 provider 物化为合法消息顺序。只读加载、列表和预览不得因检查完整性而改写会话。

#### Scenario: 中断权限等待后继续同一会话
- **GIVEN** 一个运行已经持久化 assistant tool call,正在等待权限决定
- **WHEN** 消费者调用 `kernel.interrupt(session_id)`,随后向同一会话再次 `submit`
- **THEN** 原 tool call 以取消结果闭合,新一轮模型请求收到合法 transcript 并可继续运行

#### Scenario: 重启后恢复悬空 tool call
- **GIVEN** JSONL 历史中存在没有对应 tool result 的 assistant tool call
- **WHEN** 新 Kernel 实例加载该 session 并提交下一轮
- **THEN** 内核自动追加一次引用原 call id 的恢复记录,并把取消结果物化到合法位置

#### Scenario: 重复准备恢复保持幂等
- **GIVEN** 某个 call id 已有恢复记录
- **WHEN** session 被并发或重复准备、fork 或继续运行
- **THEN** 不为该 call id 产生第二条恢复结果,transcript 仍保持闭合

#### Scenario: 只读加载没有修复副作用
- **GIVEN** session 含有悬空 tool call
- **WHEN** 消费者只执行列表、预览或其他只读加载
- **THEN** 会话文件不发生变化;下一次实际提交运行时才原子地写入恢复结果

### Requirement: 会话上下文自带工作区 AGENTS.md（机制 A，默认恒开）

创建会话时，若 `workspace_root` 根目录存在 `AGENTS.md`，内核自动将其内容（含 `@import` 展开）纳入该会话的系统提示，无需消费者额外传入、无需 agent 主动读取。无该文件则不注入，会话照常工作。此行为不可经任何 per-session / per-agent 开关关闭。注入内容在一个上下文压缩窗口内**冻结**（与 MEMORY/USER 快照同生命周期，保前缀缓存稳定）；发生上下文压缩或开启新会话时**刷新**为磁盘最新内容。

#### Scenario: workspace 根有 AGENTS.md
- **WHEN** 消费者以一个根目录含 `AGENTS.md` 的 `workspace_root` 创建会话并提交一轮运行
- **THEN** 该 agent 的系统提示包含该 `AGENTS.md` 内容，agent 可据其中约定行动

#### Scenario: workspace 根无 AGENTS.md
- **WHEN** 消费者以一个根目录无 `AGENTS.md` 的 `workspace_root` 创建会话
- **THEN** 不注入项目指令，会话正常运行、无错误

#### Scenario: AGENTS.md 含 @import
- **GIVEN** 工作区根 `AGENTS.md` 内有 `@./sub.md` 形式的 import
- **WHEN** 会话启动注入
- **THEN** 被 import 文件的内容一并纳入（递归最深 5 层、环引用不重复、不存在的 import 静默忽略）

#### Scenario: 压缩窗口内冻结、压缩边界刷新
- **GIVEN** 会话已注入工作区根 `AGENTS.md`（快照 X），其后磁盘上被改为 Y
- **WHEN** 在同一压缩窗口内继续提交运行
- **THEN** 系统提示仍含 X（不随磁盘变动而变，保前缀缓存）
- **AND** 发生上下文压缩（或新会话）后的下一轮，系统提示刷新为 Y

### Requirement: read 工具触发就近项目指令加载（机制 B，可选，默认开）

当 `nested_memory` 内核特性开启（默认 `default_on=True`，不投影为产品/用户 toggle）时，agent 经 `read` 工具读取文件，内核在该 read 的工具结果中追加项目指令上下文：被读文件在 `workspace_root` 内 → 追加其目录链（至 workspace 根）上各级 `AGENTS.md` 的正文（`@import` 展开、`<project-instructions>` 标签包裹）；在 `workspace_root` 外 → 追加英文路径提示（`<project-instructions-hint>`），范围为该文件目录至最外层 git 仓根逐级、不含正文。同一份 AGENTS.md（按绝对路径）在一个上下文压缩窗口内只追加一次（含机制 A 已注入的工作区根那份）；发生上下文压缩后去重记录清空，使压缩后的 read 可重新追加（取磁盘最新内容）——与机制 A 的压缩边界刷新一致。

#### Scenario: 读工作区内子目录文件，链上有 AGENTS.md
- **GIVEN** `nested_memory` 开启，workspace 内某子目录有 `AGENTS.md`
- **WHEN** agent read 该子目录（或更深）下的文件
- **THEN** 该 read 的工具结果含该 `AGENTS.md` 正文（`<project-instructions>` 包裹）

#### Scenario: 读工作区外 git 仓内文件
- **GIVEN** `nested_memory` 开启，被读文件在 workspace 外、属于某 git 仓，文件目录至最外层仓根之间有 `AGENTS.md`
- **WHEN** agent read 该文件
- **THEN** 工具结果含英文路径提示（列出各级 AGENTS.md 路径，不含正文）

#### Scenario: 读不属于任何 git 仓的工作区外文件
- **WHEN** agent read 的文件在 workspace 外且不属于任何 git 仓
- **THEN** 工具结果不含任何项目指令提示

#### Scenario: 同一 AGENTS.md 多次命中只追加一次（压缩窗口内）
- **WHEN** 同一压缩窗口内多次 read 命中同一份 `AGENTS.md`（含机制 A 已注入的工作区根那份）
- **THEN** 仅首次追加，后续不重复

#### Scenario: 压缩后 read 重新追加（去重记录随压缩清空）
- **GIVEN** 某 `AGENTS.md` 已在本压缩窗口内因一次 read 被追加过
- **WHEN** 发生上下文压缩后，再次 read 命中该文件
- **THEN** 重新追加该文件当前磁盘内容（压缩已把旧追加内容摘要掉，去重记录已随压缩清空）

#### Scenario: 关闭 nested_memory 后 read 不再追加
- **GIVEN** `nested_memory` 特性关闭
- **WHEN** agent read 工作区内/外文件
- **THEN** 工具结果不含项目指令内容/提示
- **AND** 机制 A 的工作区根 AGENTS.md 仍照常注入系统提示（不随之关闭）

### Requirement: 消息携带图片块时图片送达模型并随会话历史保留

消费者经 `agent.sdk` 提交（`submit`）或追加（`append_message`）一条携带图片部件（image part）的消息时，图片须送达底层模型，且随会话历史持久化——同一会话后续轮次重建历史时，该图片仍作为图片内容呈现给模型，而非被降级为纯文本占位符。两条入口（`submit` / `append_message`）在「能携带并保留图片」这一点上行为一致。

#### Scenario: 提交含图片的消息，当轮模型即可见
- **WHEN** 消费者 `submit` 一条 parts 含 image part 的用户消息
- **THEN** 该图片送达模型并被模型理解（模型据其内容作答），而非被降级为 `[image:placeholder]` 纯文本占位

#### Scenario: 单条消息含多张图片时全部送达
- **WHEN** 消费者 `submit` 一条 parts 含多个 image part 的用户消息
- **THEN** 所有图片都送达模型（不因多部件内部展开而丢失其中任一张）

#### Scenario: 含图片的消息跨轮重建后图片仍在
- **GIVEN** 某会话已持久化过一条含图片的用户消息
- **WHEN** 消费者在同一会话发起新的一轮、内核重建该会话历史
- **THEN** 重建出的历史里那条消息仍带有图片内容，发往模型的请求中图片可见

#### Scenario: append_message 追加的图片同样被保留
- **WHEN** 消费者用 `append_message` 追加一条 parts 含 image part 的消息
- **THEN** 该图片随会话历史持久化，后续轮重建历史时仍可见（与 `submit` 行为一致）

#### Scenario: 纯文本消息的持久化与回放不受影响
- **WHEN** 消费者提交一条不含图片的纯文本消息并在后续轮重建历史
- **THEN** 其持久化与回放结果与本变更前一致，无可观察差异

#### Scenario: 含图消息触发模型错误后，后续轮不再因该图重复失败
- **GIVEN** 某含图片的消息触发了一次模型调用错误
- **WHEN** 消费者在同一会话提交后续消息、内核重建历史
- **THEN** 历史中那张图不再发往模型，后续消息不会因它重复触发同一错误（该消息的文本保留；纯文本消息的既有错误处理不受影响）

> 失败契约（图片无法获取 / 超大 / 损坏）属 gateway 入站职责（见 gateway 契约「用户经 IM 发送的图片被 Agent 看到」下的异常图片 Scenario），不在内核重复——图片校验在 gateway 入站完成，到达内核的 image part 已是校验过的 data URL，内核不产出图片失败信号。

### Requirement: 消费者可在同一会话上持久替换后续运行配置

`agent.sdk` 的消费者可为已有会话提供包含 resolved model、PromptSlots、skills、enabled tools 与 features 的完整新运行配置。替换与当前 turn 串行，在返回成功前完成持久化，并保持 session id、既有上下文、压缩状态和父链不变。相同配置的重复替换幂等；消费者不负责计算运行配置身份或失效内核 live state。

#### Scenario: 替换配置后下一轮延续原历史
- **GIVEN** 一个已有多轮消息与工具调用历史的会话
- **WHEN** 消费者成功替换该会话的 model、prompt、skills、tools 或 features 后再提交下一轮
- **THEN** 下一轮使用替换后的完整运行配置，并仍能看到替换前的可用历史
- **AND** 会话 id 不变

#### Scenario: 删除工具只限制未来调用
- **GIVEN** 会话历史中已有某工具的 call 与 result
- **WHEN** 消费者把运行配置替换为不含该工具后继续会话
- **THEN** 历史 call/result 仍能被后续模型上下文读取
- **AND** 该工具不能被后续运行再次执行

#### Scenario: 活跃 turn 期间替换不造成半轮切换
- **GIVEN** 会话正在用配置 A 执行一个 turn
- **WHEN** 消费者同时请求替换为配置 B
- **THEN** 已开始的 turn 完整使用配置 A，替换在其后原子完成，下一新 turn 才使用配置 B

#### Scenario: 配置替换持久恢复
- **GIVEN** 消费者已成功替换一个会话的运行配置
- **WHEN** 进程重启后按原 session id 和 workspace 恢复该会话
- **THEN** 会话使用替换后的配置并保留替换前后的历史

#### Scenario: 重复替换等价配置幂等
- **WHEN** 消费者对同一会话重复提交等价的完整运行配置
- **THEN** 返回可辨识的未变化结果，不产生重复配置代次，历史不变

#### Scenario: 持久化失败不暴露半应用状态
- **WHEN** 运行配置替换无法持久化
- **THEN** 调用失败，后续运行不会观察到新旧字段混合的配置

### Requirement: 消费者可读取会话当前持久运行配置身份

消费者可经 `agent.sdk` 读取会话当前持久化的完整运行配置及按当前 schema 计算的稳定身份，用于恢复外围绑定。身份 canonicalization 由 SDK 单点拥有；消费者不依赖会话档案内部 entry 或 metadata 格式。缺少完整运行配置的旧档案返回明确的不可用结果。

#### Scenario: 重启后读取已替换的运行配置
- **GIVEN** 会话已持久化运行配置替换
- **WHEN** 新 Kernel 实例读取该会话的当前运行配置
- **THEN** 返回与替换成功时等价的运行配置和身份

#### Scenario: fingerprint schema 升级时从完整配置重算
- **GIVEN** 会话保存了完整运行配置，但其历史 identity 使用旧 fingerprint schema
- **WHEN** 消费者读取当前运行配置
- **THEN** 返回按当前 schema 重算的 identity，不把 schema 变化解释为运行配置变化

#### Scenario: 极旧档案没有完整运行身份
- **GIVEN** 旧会话档案没有足够信息重建包含 model 的完整运行配置
- **WHEN** 消费者读取当前运行配置
- **THEN** 返回明确的不可用结果，不猜测配置，也不改写档案

### Requirement: fork_session 复制源会话在 fork 点的上下文与运行配置到独立新会话

`agent.sdk` 的消费者可对已有会话发起 fork，指定消息 M 为 fork 点。内核复制源会话在 M 时所用的上下文视图和当时已持久化的运行配置，生成独立新会话。源若已压缩，复制的是含当时压缩摘要的视图；M 之后的源内容与配置替换不进入新会话。两边后续历史和配置独立演进。

#### Scenario: fork 带着源在 fork 点的记忆与配置
- **GIVEN** 源会话在 M 之前形成历史并经历过运行配置替换
- **WHEN** 消费者经 `agent.sdk` fork 到 M
- **THEN** 新会话的上下文与运行配置等于源在 M 时的持久视图
- **AND** M 之后的消息或配置变化不进入新会话

#### Scenario: fork 复刻源在 fork 点的压缩态
- **GIVEN** 源会话在 fork 点之前曾发生上下文压缩
- **WHEN** 消费者 fork 该会话到 fork 点 M
- **THEN** 新会话得到源在 M 时已生效的压缩视图，不还原压缩前的完整原始历史，也不丢失源当时已有内容

#### Scenario: fork 后两边配置与历史独立
- **GIVEN** 已从源会话 fork 出新会话
- **WHEN** 消费者在任一侧继续对话或替换运行配置
- **THEN** 另一侧的历史和运行配置不受影响

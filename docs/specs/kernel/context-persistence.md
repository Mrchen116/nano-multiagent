# kernel (agent) - Context and Persistence Specification

> 对齐: feat-445
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

上下文压缩、会话档案、事件溯源、带外消息、transcript 闭合、项目指令、图片历史和 fork 的对外契约。

## Requirements

### Requirement: 上下文压缩在长会话中保持可恢复

内核在 LLM 调用前后检查上下文是否接近/超出上限,必要时把旧轮次摘要化并落盘为压缩记录,保留首个保留
事件 id 以保证可重建与可审计;overflow 后可恢复重试。消费者也可手动触发压缩。压缩判定所用的**上下文上限按当前轮所用模型取**：消费者经 `build_kernel(llm=…)` 为某模型声明的上下文窗口生效于该模型的运行;未声明窗口的模型回退到内核默认上限。判定上限时保留的安全余量是全局策略量,不随模型变化。

#### Scenario: 手动触发压缩
- **WHEN** 消费者 `await kernel.compact(session_id)`
- **THEN** 返回压缩结果(或在无需压缩时返回 None),压缩落盘后会话仍可由事件重放重建

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

会话档案是每会话一个 append-only JSONL,落
`{workspace_root}/{workspace_config_dirname}/sessions/{session_id}.jsonl`。存储组件无状态(不持
session→位置映射,按调用方传的 `workspace_root` 当场定位);位置由 `create_session(workspace_root)`
决定,无中心 session db 路径配置。

#### Scenario: 不同 agent 会话落各自 workspace
- **GIVEN** 两个会话以不同 `workspace_root` 创建
- **WHEN** 各自产生 turn
- **THEN** 档案分别落各自 `workspace_root` 下,互不混写

### Requirement: 会话事件溯源持久化,进程重启后可恢复

每次状态变更产生事件并经会话存储持久化;会话可由事件重放重建,进程重启后可恢复。运行时不直接写 SQL,
只经会话存储接口。

#### Scenario: 重启后恢复会话
- **GIVEN** 一个已持久化的会话
- **WHEN** 进程重启后消费者按 session_id 取该会话
- **THEN** 会话历史与状态可由持久化事件重放重建

### Requirement: 经 append_message 带外写入的消息对后续轮次可见

消费者(如 Gateway)可在不触发模型运行的前提下,经 `append_message` 把一条消息持久化进会话;该消息进入会话
线性历史,对该会话此后任意一轮运行可见——既不被丢弃,也不被运行时的内存历史缓存遮蔽。内核另提供
`invalidate_session_cache`,供消费者在带外改动会话持久化后显式失效内存缓存。

#### Scenario: 带外追加的消息进入下一轮上下文
- **GIVEN** 一个已运行过至少一轮的会话
- **WHEN** 消费者经 `append_message` 向该会话追加一条消息,随后再提交一轮运行
- **THEN** 该追加消息出现在这一轮的模型上下文里(不被陈旧缓存或历史链断裂遮蔽)

### Requirement: 持久化 transcript 在进入模型前保持 tool call 闭合

消费者中断、取消或关闭包含工具调用的运行后,内核必须使已持久化的每个 assistant tool call
具有对应的 tool result。进程异常退出留下的历史悬空调用在下次提交运行前自动恢复为取消终态;
恢复保持 append-only、按 tool call id 幂等,并向 provider 物化为合法消息顺序。只读加载、
列表和预览不得因检查完整性而改写会话。

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

### Requirement: fork_session 复制源会话「在 fork 点那一刻的上下文」到独立新会话，使分支与源体验一致

`agent.sdk` 的消费者（如 Node Gateway）可对一个已有会话发起 fork，指定其中某一条消息为 fork 点 M：内核复制**源会话在 M 那一刻所用的上下文视图**（即源会话自己运行时所见的历史——源若已对 M 之前的内容做过上下文压缩，复制的就是含该压缩摘要的视图；源未压缩则为到 M 为止的全部原始内容），生成一个**独立**的新会话。新会话拥有自己的历史副本，后续运行的记忆与「在源会话里从 M 继续」**一致**——既不比源记得更多（不还原压缩前全量），也不更少；fork 点 M 之后的源内容不进入新会话；对新会话的追加不回流源会话。

#### Scenario: fork 出的新会话带着源在 fork 点的记忆，可指代追问
- **GIVEN** 一个已有多轮对话的源会话，消费者指定其中某一条消息为 fork 点（即便同一轮里产出了多条消息，也能精确指向其中某一条）
- **WHEN** 消费者经 `agent.sdk` fork 该会话到该 fork 点
- **THEN** 得到一个新会话，其上下文 = 源会话在该 fork 点那一刻所用的视图；在新会话里继续运行时，模型对这段历史的「记忆」与源会话在该点时一致；fork 点之后的源内容不在新会话中

#### Scenario: fork 复刻源在 fork 点的上下文（含压缩态），与源体验一致
- **GIVEN** 源会话在 fork 点之前曾发生过上下文压缩（M 之前的历史在喂模型时被摘要替代）
- **WHEN** 消费者 fork 该会话到 fork 点 M
- **THEN** 新会话得到的是源在 M 那一刻的视图（含当时已生效的压缩摘要），与源在该点的记忆**逐字一致**——既不还原压缩前的完整原始历史（不比源记得更多），也不丢失源当时已有的内容

#### Scenario: 新会话与源会话相互独立
- **GIVEN** 已从源会话 fork 出新会话
- **WHEN** 在新会话继续对话、或在源会话继续对话
- **THEN** 两者各自独立演进，互不影响对方的历史

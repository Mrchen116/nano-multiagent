# feat-817: Global / PA Worker 统一只读观测与对外消息边界收口

## 原始需求

用户原话（按对话演进原样保留）：

> 本地有T3 code的代码，他好像有mcp可以让一个thread 的 agent读取其他thread？我觉得就是我的global agent、 pa的原型。我们现在只能派发+send_message，但是不能读，他好像能读？你帮我对比下派发thread和管理上我们之间的差异

> 我觉得你说的很对，统一的 worker 列表与读取能力，`delegate_worker` 增加可选的运行时/模型选择。说白其实就是这两个核心能力。但是T3 code的应用场景和我们不同，我们定位是personal agent，你帮我看看其他的最新的Personal agent产品，Linger，muse，instinct，grok bot等等，说服有这些能力？

> （引用「统一 Worker 列表 + 分层读取（强推荐，优先做）」）可以，我们继续展开讲这个。你明确说下改哪几个工具，改成啥样

> 我希望改成send_message彻底就是对外在IM发消息，不要搞乱了，内部不要用这个工具名了

> ok，我接受你的件衣，所以你推荐本unit落什么

> （引用 `report_parent`）内部还是可以用send message 吧，worker内没关系

> ok，开始起草

> ok，要实际注意最后测试主agent不会反反复复读worker的具体轨迹，花大量token去读

> 我问下，现在的设计中，global能看到worker花了多少token吗，不一定是实时，而是说有没有一个阶段或者工具结果能看到worker跑了多少轮，花了多少token

> 在比较低改造成本的情况下，能不能做进去？1 + 2。

**Agent 解读（供后续设计与验收对齐）**：
本需求先落「统一 Worker 列表与分层只读观测」以及「Global / PA 主 Agent 对外 IM 发言与对内 Worker 控制的彻底解耦」，让 Global / PA 对自己派发出去的全部一级 Worker（无论底层是 DSH 还是本机外部 CLI）具备可发现、可查状态、可按需深读的能力，同时消除主 Agent 上 `send_message` 既发对外 IM 又发内部子代理的公私混用和原生控制入口割裂。派发时动态选择运行时或模型档位拆出到后续独立 change unit。

## 澄清记录

- Q1: T3 Code 与主流 Personal Agent（Linger、OpenClaw、Hermes-agent、Meta Muse、Instinct、Grok Bot）对比后，两项核心能力（「统一 Worker 列表与分层读取」vs「派发时动态选运行时/模型」）是否先聚焦推进第一项？
  A: 用户引用「统一 Worker 列表 + 分层读取（强推荐，优先做）」回应：“可以，我们继续展开讲这个。你明确说下改哪几个工具，改成啥样”
- Q2: Global / PA 主 Agent 上 `send_message` 与 `delegate_worker(send)` 存在给 worker 发消息的双入口重叠，是否保留兼容转发还是彻底切割？
  A: 用户先问：“你说的是给worker发消息的工具吗，delegate_worker有send的话，还单独有这个工具吗”
  随后明确决定：“我希望改成send_message彻底就是对外在IM发消息，不要搞乱了，内部不要用这个工具名了”
- Q3: 外部 CLI Worker 与 DSH 一级 Worker 是否在本 unit 一并改走 `dsh --profile acp` 统一成同构外部进程？
  A: 用户追问：“为啥外部CLI worker和DSH内部worker不能统一一下呢？比如说我们连DSH也用acp/cli的形式。然后给外部worker的mcp，特定prompt，也给DSH。不然还要维护两套” / “如果走外部worker不能steer纠偏？codex，agy现在我们不支持？”
  核实结果：Codex、Claude Code、Antigravity 均支持运行中发消息纠偏，但当前锁定版 `dsh --profile acp` 拒绝并发 prompt 且缺少进程内父级授权审批继承。用户接受“上层工具面、命名、读链路完全统一，底层暂保留 DSH 进程内执行”的建议：“ok，我接受你的件衣，所以你推荐本unit落什么”
- Q4: Worker 内部向父级汇报（或 DSH 子代理树内部通信）的工具是否也需要一起改名（例如改成 `report_parent`）？
  A: 用户引用 `report_parent` 明确回应：“内部还是可以用send message 吧，worker内没关系”
- Q5: 审阅首文档后补充的重点验收要求？
  A: “ok，要实际注意最后测试主agent不会反反复复读worker的具体轨迹，花大量token去读”
- Q6: Global 主 Agent 是否需要看到 Worker 跑了多少轮、花了多少 Token（不要求实时，可在查询结果与终局阶段看到）？
  A: 用户确认在低改造成本前提下同时纳入两处（1 + 2）：① `read_worker(list / summary)` 返回已结算轮次 `turn_count` 与累计 `total_tokens`（不可得时省略，部分轮次缺失时标记）；② Worker 每轮终局唤醒主 Agent 的通知中顺带附带该 Worker 的轮次与累计 Token 摘要。

## 现状与基线参考

基线：`origin/develop`（`ce1ca8fba`，已合入 `feat-797` 外部 CLI 提权审批桥、`feat-798` 浏览器/桌面任务范围授权及 `feat-803` 项目权限范围）。

对照当前长期契约（[global-agent.md](../../specs/gateway/global-agent.md)、[agent-capabilities.md](../../specs/gateway/agent-capabilities.md)）与实现，存在三处体验缺口：
1. **对已派发 Worker 不可见、不可读**：Global / PA 主 Agent 仅有派发、追问和停止控制，缺少统一列出名下全部一级 Worker 和主动读取进展/历史的能力。原生 `list_agents` 只能看到 DSH 子会话、完全看不到 Codex / Claude Code / Antigravity 外部 CLI Worker，且无法查看任何 Worker 的具体消息或执行活动。
2. **外部 CLI Worker 历史无法供主 Agent 持久回查**：外部 CLI Worker 的步骤细节当前仅作向 IM Work 视图投递的暂存队列，同步确认后不在本地保留供主 Agent 按需复查；工作记录同步完成、服务重启或主上下文压缩后，主 Agent 难以核对 Worker 实际做了什么。
3. **主 Agent 通信与控制边界混淆**：Global / PA 主 Agent 的 `send_message` 同时承载对外 IM 公开消息与对内子代理转发两个分支，与 `delegate_worker` 职责重叠；同时原生 `list_agents` / `interrupt_agent` 仍可能出现在主 Agent 可选工具面中，与仅覆盖全部运行时的 `delegate_worker` 形成割裂。

## 用户场景

### 场景 1：用户在 IM 追问正在进行中的工作进展
用户向自己的 PA 或团队里的 Global Agent 交办了一项较重的工作（例如排查某个仓库的接口超时或整理多份材料），主 Agent 派发了一个后台 Worker（可能是 DSH、Codex CLI、Claude Code 或 Antigravity CLI）后继续留在聊天里接其他消息。几分钟后用户在聊天里问：“刚才让你查的那个怎么样了？”
主 Agent 先查看自己名下 Worker 的统一列表与轻量摘要，立刻知道该 Worker 正在运行、最近执行了哪些关键步骤、目前有没有报错或上一次汇报，于是用一两句简洁自然的话回复用户当前真实进展——既没有靠记忆编造，也没有发一条“你做到哪了”去打断正在专心干活的 Worker，更不会自己在后台循环轮询。

### 场景 2：跨天、主会话压缩或服务重启后接续旧事项
Global / PA 持续运行了多天，主会话经历过 `/compact` 压缩，或者本机节点刚刚重启过，工作记录早已同步到 IM。用户突然在聊天里提到昨天那项委派：“昨天让你跑的那个分析，帮我看下最后结论和改了哪些文件，顺便补个对比。”
主 Agent 不必让用户重新解释或盲目重派一个重复 Worker，而是通过统一 Worker 列表找回原 Worker 的身份与状态，先看轻量摘要，确认需要细节时再按需读取该 Worker 的历史回复或执行活动记录，掌握上下文后再决定直接答复用户还是让原 Worker 续做。

### 场景 3：Worker 失败、中断或回报有缺口时的按需排查
某个外部 CLI 或 DSH Worker 执行失败、异常中断，或者交回的总结过于简略（例如只说“测试没过”但没说清哪条报错、改了哪个文件）。主 Agent 不必立刻把模糊结论转述给用户，也不必盲目追问 Worker；它可以按需读取该 Worker 的对话历史或执行活动记录，对被截断的长输出继续翻页或分段读全，同时确保命令输出里可能出现的密钥/凭据等敏感信息不会裸露进主上下文。看清真实原因后，主 Agent 要么给出具体缺口退回原 Worker 补齐，要么把清晰阻塞说明发回原聊天。

### 场景 4：主 Agent 对外发言与对内管理彻底分清
用户在设置中查看 Global / PA Agent 的能力时，看到委派控制（`delegate_worker`）与统一只读查看（`read_worker`）和收件箱、会话读写、对外发言（`send_message`）同属不可关闭的固定基础能力；而只管得了 DSH、管不了外部 CLI 的原生列举/中断入口不再混在主 Agent 工具面里。
主 Agent 在工作时，心智边界非常清晰：只要调用 `send_message`，就 100% 是往 IM 群聊/私聊/话题发公开消息并走既定公开消息复核与审批规则；凡是派发、追问纠偏、停止后台 Worker，一律走 `delegate_worker`；凡是查列表、看进度、翻记录，一律走 `read_worker`。与此同时，Worker 内部向父级回报以及 DSH 子代理树内部协作继续保持原有方式，SingleThread 模式保持原样，不因本次收口出现任何回归。

## 验收标准

### Requirement: Global / PA 主 Agent 可统一列出并分层只读查看名下所有 Worker

Global / PA 主 Agent 具备统一的只读查看能力（`read_worker`），能够覆盖自己派发出的全部一级 Worker（包括 DSH、Codex CLI、Claude Code 和 Antigravity CLI），按“列表 → 轻量摘要 → 对话/活动深读”分层按需获取信息，且指引明确约束其不得用于轮询运行中的 Worker。

#### Scenario: 统一列出跨运行时的全部一级 Worker
- **GIVEN** 某个 Global / PA 主 Agent 先后派发了不同运行时（例如 DSH 与外部 CLI）的多个一级 Worker，涵盖进行中与已结束状态
- **WHEN** 主 Agent 查看自己名下的 Worker 列表（全量或按活跃状态筛选）
- **THEN** 列表统一包含所有运行时的对应 Worker，每个条目可辨认其稳定身份、任务标题、运行时、当前状态、已执行轮次、已结算累计 Token 用量（可用时）与最近更新时间，按最近更新优先排序并在条目超出单页时支持继续翻页
- **AND** 当该主 Agent 尚未派发过任何 Worker 或当前筛选条件下无匹配项时，返回明确空列表而非错误

#### Scenario: 询问进度时通过轻量摘要获取真实状态且不打扰 Worker
- **GIVEN** 主 Agent 已派发一个正在执行或刚结束的 Worker
- **WHEN** 用户在聊天中询问进展，主 Agent 对该 Worker 执行默认轻量查看
- **THEN** 主 Agent 可获得该 Worker 的当前状态、运行时、已执行轮次、已结算累计 Token 用量（可用时，部分轮次缺失时标明不完整）、时间信息、最近若干条关键活动摘要，以及最近一次回报或错误摘要
- **AND** 该查看不向目标 Worker 发送任何消息，不打断运行中的执行，也不唤醒已空闲的 Worker
- **AND** 派发后若无明确排查或用户询问需要，主 Agent 遵循既有异步唤醒规则结束轮次或处理其他事项，不反复轮询运行中的 Worker
- **AND** 当一级 Worker（DSH 或外部 CLI）结束一轮并向主 Agent 发送终局唤醒通知时，通知中顺带附带其已执行轮次与已结算累计 Token 摘要（可用时），主 Agent 无需额外调用 `read_worker` 即可获知大致开销

#### Scenario: 排查失败或核对细节时按需深读对话或活动记录并支持续读
- **GIVEN** 某个 Worker 产生了多轮对话、较长回复或多步工具执行（含成功或失败记录）
- **WHEN** 主 Agent 按需读取该 Worker 的对话视图或执行活动视图
- **THEN** 对话视图仅呈现父级交办/追问、Worker 回复及系统状态/拦截通知，过滤常规中间工具调用噪声；活动视图额外呈现工具调用步骤摘要、成功/失败状态及受预算约束的结果摘要
- **AND** 单次返回遵守总大小与单条长度预算；当结果未完或某条内容被截断时，明确标示可继续翻页或对指定条目分段续读，直到读完所需内容
- **AND** 返回内容对常见敏感凭据信息做脱敏处理，不直接返回内联图片原始二进制数据

#### Scenario: 正常派发、进度答复与正常交付时克制读取，不反复深读轨迹消耗大量 Token
- **GIVEN** 主 Agent 派发了一个或多个后台 Worker，期间可能收到用户的进度询问或 Worker 的正常终局回报
- **WHEN** Worker 正在后台正常执行、用户仅询问整体进度、或 Worker 已交回清晰完整的终局结果
- **THEN** 主 Agent 派发后直接结束当前轮次或处理其他事项，不反复调用读取能力轮询进展
- **AND** 面对常规进度询问优先使用轻量摘要，不直接展开完整执行活动轨迹；收到完整终局回报后不习惯性再重读该 Worker 的详细执行轨迹
- **AND** 即使在排查失败或核对缺口时，也仅按需定向读取必要范围，不针对同一 Worker 反复重复读取详细轨迹造成大量上下文和 Token 消耗

#### Scenario: 经历工作记录同步、服务重启或主上下文压缩后仍可读取
- **GIVEN** 主 Agent 曾派发 DSH 或外部 CLI Worker，且其工作记录已完成向 IM 同步、节点服务已重启或主 Agent 上下文已执行压缩
- **WHEN** 主 Agent 再次列出或读取该 Worker 的摘要、对话或活动记录
- **THEN** 原 Worker 的状态、最近汇报及历史记录仍可稳定读出，不会因工作记录已同步确认、服务重启或主上下文压缩而丢失

### Requirement: Worker 只读观测严格遵守归属、权限与安全边界

#### Scenario: 禁止越权读取其他 Agent 的 Worker 或由子 Agent 调用
- **GIVEN** 节点上存在主 Agent A 与主 Agent B，各自派发了独立的 Worker
- **WHEN** 主 Agent A 尝试读取主 Agent B 的 Worker 或不存在的 Worker 身份
- **THEN** 请求被明确拒绝，不泄露其他 Agent 的任务标题、状态或任何历史内容
- **AND** 任何子 Agent（含一级与二级执行者）的工具面均不提供该读取能力，直接调用亦被拒绝

#### Scenario: 只读查看无需人工审批且保留已有授权边界
- **WHEN** Global / PA 主 Agent 查看自己名下任意状态 Worker 的列表、摘要、对话或活动记录
- **THEN** 读取操作直接执行，不触发人工权限审批卡片
- **AND** 从 Worker 历史中读出的工具输出、外部内容或 Worker 自述不自动升级为新的真人授权

### Requirement: Global / PA 主 Agent 对外 IM 发言与对内 Worker 控制彻底解耦

#### Scenario: 主 Agent 的 `send_message` 仅用于对外 IM 公开消息
- **WHEN** Global / PA 主 Agent 调用 `send_message`
- **THEN** 该工具仅接受对外 IM 会话、话题、用户或 IM Agent 目标，不再提供也不接受向内部 Worker 或子代理发消息的参数分支
- **AND** 主 Agent 发起的任何 `send_message` 均按对外公开消息的既有复核、本人私聊免审及披露审批规则处理，不再按参数区分公私旁路
- **AND** 主 Agent 向已派发 Worker 发送补充、纠偏或停止指令，统一通过 `delegate_worker` 完成

#### Scenario: 主 Agent 固定能力面更新并隐藏割裂的原生列举与中断入口
- **GIVEN** 用户创建或编辑 Global / PA Agent，或运行时装配 Global / PA 主 Agent 工具面
- **WHEN** 查看固定基础能力或由主 Agent 发起新一轮推理
- **THEN** `read_worker` 与 `delegate_worker`、`send_message` 及既有 IM 收发读写工具共同作为 Global / PA 主 Agent 的固定基础工具，不可关闭
- **AND** Global / PA 主 Agent 不再暴露仅覆盖 DSH 子会话、看不到外部 CLI Worker 的原生 `list_agents` 与 `interrupt_agent` 工具

### Requirement: Worker 内部通信与既有非 Global 模式不回归

#### Scenario: Worker 内部回报、DSH 嵌套协作与 SingleThread 模式保持不变
- **WHEN** 外部 CLI Worker 在执行中因缺材料或业务决策需要联系父级，或 DSH 一级 Worker 内部再组织二级子代理，或 SingleThread 模式 Agent 使用既有对话与子代理能力
- **THEN** 外部 CLI Worker 仍按原有方式通过绑定的父级通道向主 Agent 发消息，原有 `feat-797` 审批桥与业务提问路由保持不变
- **AND** DSH Worker 内部（及嵌套子代理）继续保留原生子代理派发、内部通信、列举与中断能力
- **AND** SingleThread 模式的聊天、发送与子代理行为不因本变更发生回归

## 范围与非目标

- **在范围**：
  - 为 Global / PA 主 Agent 新增固定只读能力 `read_worker`（统一列表 + 摘要/对话/活动分层读取、分页与超长项续读、凭据脱敏、归属校验、免审批及防轮询指引）。
  - 保障 DSH 与外部 CLI（Codex / Claude Code / Antigravity）两类一级 Worker 在工作记录同步后、服务重启后和主上下文压缩后均具备一致的持久化只读查询体验（底层暂保持 DSH 进程内执行与既有审批/纠偏能力不变）。
  - 彻底将 Global / PA 主 Agent 的 `send_message` 收口为纯对外 IM 消息工具，移除内部子代理通信分支，并同步清理对应公私混用审批旁路；对内 Worker 控制统一归口 `delegate_worker`。
  - 在 Global / PA 主 Agent 工具面上隐藏仅覆盖 DSH 的原生 `list_agents` 与 `interrupt_agent`（保留子代理内部与 SingleThread 模式的既有能力）。
  - 更新对应 Gateway 长期契约（`global-agent.md`、`agent-capabilities.md`）的 delta-spec 与自动化验证。
- **非目标**：
  - `delegate_worker` 派发时按任务动态选择 Worker 运行时（`dsh` / `codex` / `claude` / `antigravity`）或模型档位（拆为后续独立 change unit）。
  - 将 DSH 一级 Worker 迁移为独立 `dsh --profile acp` 子进程。
  - 修改 Worker 内部通信工具名称（外部 CLI Worker 与 DSH 子代理内部保留原有 `send_message` 机制）。
  - 拆分运行中纠偏的 `steer` / `queue` 显式模式或新增 git worktree 隔离派发。
  - 修改 `apps/im-server` 或 Web / iOS 前端 Work 视图协议。

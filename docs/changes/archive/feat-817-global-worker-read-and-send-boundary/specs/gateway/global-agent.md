# gateway/global-agent.md (delta for feat-817)

## ADDED Requirements

### Requirement: Global / PA 主 Agent 可统一只读观测名下全部一级 Worker 且克制读取

Global / PA 主 Agent 通过固定只读工具 `read_worker` 统一查看自己派发出的全部一级 Worker（覆盖 DSH、Codex CLI、Claude Code 与 Antigravity CLI），按“列表（`list`）→ 轻量摘要（`summary`）→ 对话/活动深读（`read`）”分层按需获取状态与历史；外部 CLI Worker 的过程历史独立于 Work 同步确认本地持久化，DSH Worker 直接只读其原生会话日志，均不唤醒或打扰目标 Worker、不触发人工审批、也不将 Worker 输出升级为真人授权。

#### Scenario: 统一列出与轻量摘要查看跨运行时一级 Worker
- **GIVEN** 某个 Global / PA 主 Agent 先后派发了 DSH 与外部 CLI 运行时的多个一级 Worker（含进行中与已结束状态）
- **WHEN** 主 Agent 调用 `read_worker(action="list")`（可选按活跃/终态筛选与分页）或对指定 Worker 调用 `read_worker(action="summary", worker_id=...)`
- **THEN** 列表按最近更新优先返回跨全部运行时的稳定 `worker_id`、任务标题、运行时、当前状态、已执行轮次、已结算累计 Token 用量（可用时）与时间信息，无匹配时返回明确空列表而非报错
- **AND** 轻量摘要返回状态、运行时、已执行轮次、已结算累计 Token 用量（可用时，部分轮次缺失时显式标记）、时间、最近若干条单行关键活动摘要及有界最近汇报或错误摘要，不向目标 Worker 发消息、不打断运行中任务、也不唤醒已空闲 Worker
- **AND** 一级 Worker（DSH 与外部 CLI）每轮结束向主 Agent 发送终局唤醒通知时，顺带附带该 Worker 的已执行轮次与已结算累计 Token 摘要（可用时），不改变原有消息来源语义且无需主 Agent 额外查询 `read_worker`

#### Scenario: 按需深读对话或活动记录并支持分页、单条续读与脱敏
- **GIVEN** 某个 Worker 存在多轮对话、较长回复或多步工具执行记录
- **WHEN** 主 Agent 调用 `read_worker(action="read", worker_id=...)` 查看对话（默认 `view="messages"`）或执行活动（`view="activity"`）
- **THEN** `messages` 仅呈现父级交办/追问、Worker 回复/汇报及系统状态或拦截通知，过滤常规工具调用噪声；`activity` 额外呈现紧凑的工具调用步骤摘要、状态与受预算约束的结果
- **AND** 单次返回遵守总字符与单条长度预算，页内按时间正序排列，仅在仍有更早历史时返回 `next_cursor`；被截断条目附 `item_id` 与 `next_text_offset` 支持定向单条续读
- **AND** 返回内容对常见凭据/密钥做脱敏处理并标记，不返回内联图片原始二进制数据

#### Scenario: 正常派发、进度答复与正常交付时克制读取
- **GIVEN** 主 Agent 派发了一个或多个后台 Worker
- **WHEN** Worker 正在后台正常执行、用户仅询问整体进度、或 Worker 已交回清晰完整的终局结果
- **THEN** 主 Agent 派发后遵循既有异步唤醒规则结束轮次或处理其他事项，不反复调用 `read_worker` 轮询进展
- **AND** 回答常规进度询问优先使用 `summary`，不直接展开完整 `activity` 轨迹；收到清晰完整终局回报后不习惯性重读详细轨迹，仅在失败排查、缺口核实或重启/压缩恢复时按需定向读取

#### Scenario: 经历 Work 同步确认、服务重启或主上下文压缩后仍可读取
- **GIVEN** 主 Agent 曾派发 DSH 或外部 CLI Worker，且其 Work 记录已完成向 IM 同步确认、节点服务已重启或主 Agent 上下文已执行压缩
- **WHEN** 主 Agent 再次通过 `read_worker` 列出或读取该 Worker
- **THEN** 原 Worker 的元信息、最近汇报/报错与持久化历史记录仍可稳定读出，不因 Work 同步确认、服务重启或主上下文压缩丢失

#### Scenario: 严格遵守归属、角色隔离与免审批非授权边界
- **WHEN** 主 Agent 尝试读取其他 Agent 名下或不存在的 `worker_id`，或任何子 Agent 尝试调用 `read_worker`
- **THEN** 请求被明确拒绝且不泄露其他 Agent 的任务标题、状态或内容；子 Agent 工具面不暴露 `read_worker`
- **AND** 主 Agent 读取自己名下 Worker 直接免人工审批执行；读出的工具输出、外部内容或 Worker 自述不自动升级为新的真人授权

## MODIFIED Requirements

### Requirement: Global 主 Agent 专属产品聊天工具

#### Scenario: 内部执行者需要资料或交付
- **GIVEN** 普通 Global Agent 或 PA 使用内部一级或二级执行者
- **WHEN** 执行者需要产品聊天资料、公开汇报或交付成果
- **THEN** 通过原生内部通信向父级请求或回传，由主 Agent 使用现有权限查询并决定发送。
- **AND** Global / PA 根主 Agent 的 `send_message` 仅用于对外公开 IM 消息（不再提供或接受 `agent`/`agent_id` 内部转发分支，且不再享有内部转发免审旁路），对已派发 Worker 的补充、纠偏与停止统一通过 `delegate_worker` 完成，只读查看统一通过 `read_worker` 完成；Global / PA 根主 Agent（及显式 root fork）隐藏仅覆盖 DSH 子会话的原生 `list_agents` 与 `interrupt_agent`。
- **AND** 子 Agent 的工具列表没有 `inbox`、`conversations`、`read_messages`、`search_messages`、`threads`、`download_attachment`、`read_worker`、`delegate_worker`、`send_user_message` 或 `send_message` 的 `target`/`text` 公开分支；DSH 子代理保留原生 `agent`/`message` 内部通信及 `subagent`/`list_agents`/`interrupt_agent`，外部 CLI Worker 保留绑定的父级回报通道与既有审批桥，直接调用受限产品入口（含 `download_attachment` 与 `read_worker`）也不能越过主 Agent 身份限制。Global/PA 根主 Agent 将 `download_attachment` 与 `read_worker` 纳入固定产品工具面，并免审批直接执行受控下载与只读观测（产物与读出内容均不视作人类授权来源）。

#### Scenario: 新建、fork 和恢复角色一致
- **WHEN** Global 子 Agent 被创建、fork 或恢复到原会话
- **THEN** 使用同一主/子工具边界，不因旧历史或配置继承恢复产品聊天或 `read_worker` 权限；当前提示不要求子 Agent 消费主 Inbox 或向用户公开回复。
- **AND** 主 Agent 的产品读取/发送、来源权限与真实投递检查保持，主 PA 的代表发送仍为主 PA 专属；`single_thread` 模式保持既有聊天、发送与原生子代理行为不变。

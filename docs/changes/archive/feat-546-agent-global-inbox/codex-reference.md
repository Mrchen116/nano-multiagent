# Codex：跨任务读取、显式传话与运行中续接

调研日期：2026-09-09。本地参考仓库 `/Users/czj/Repos/opensource-hub/codex`，HEAD `1bfd383890b1bd7fab0d1b3d5e05129a9e293d8a`，提交日期 2026-09-09；检查时工作区干净。本轮只读，没有更新仓库、编译或启动运行时。本单尚未采用这些机制。

## 结论

当前源码不只有跨 Thread 读取，还包含列举任务、读取历史、向已有任务发送信息、等待结果，以及创建和 fork 任务的工具。这里的 Thread 是 Codex 任务／对话，不是 Slack 频道中的子讨论。

这些任务保留各自的历史与执行状态，通过显式读取和投递连接；不能因可跨任务访问而解释为一个全局共享 Session。已核对路径由调用方指定目标，没有找到足以证明存在 Claude Tag 式自动关联新消息与在途工作的机制。

## 主动读取别的任务

`codex-rs/tui/src/dynamic_tools.rs` 声明 `list_threads`、`read_thread`、`wait_threads`。`read_thread` 读取指定 threadId 的状态，并分页获取历史轮次，可选择是否包含工具输出及限制输出长度。它不是将全部任务历史持续推入当前上下文。[工具定义](/Users/czj/Repos/opensource-hub/codex/codex-rs/tui/src/dynamic_tools.rs:147)、[读取实现](/Users/czj/Repos/opensource-hub/codex/codex-rs/tui/src/dynamic_tools.rs:483)

用户引用另一个任务时，TUI 将引用转成任务 ID，并明确提示模型先调用 `read_thread`；任务引用本身不包含正文。这是让模型知道“去哪里读”的入口。[引用处理](/Users/czj/Repos/opensource-hub/codex/codex-rs/tui/src/task_mentions.rs:223)

## 向已有任务补送信息

`send_message_to_thread` 接收目标 threadId 和 prompt。实现先读取、恢复目标任务，再提交输入。输入包含来源 Thread ID，并以命名工具输出送入目标；不能将其误解为新的人类最高优先级指令。[发送路径](/Users/czj/Repos/opensource-hub/codex/codex-rs/tui/src/dynamic_tools.rs:744)、[来源封装](/Users/czj/Repos/opensource-hub/codex/codex-rs/tui/src/dynamic_tools.rs:1163)、[输入提交](/Users/czj/Repos/opensource-hub/codex/codex-rs/tui/src/dynamic_tools.rs:1275)

App Server 将这类工具输出交给 `start_or_steer_turn`。Core 的接口区分开始新轮次、向活动轮次补充输入和不接受输入，因此向忙碌任务传话不必然要求等它完全结束，也不等于强制中断。能否接入仍受当前轮次状态与约束影响。[服务端路径](/Users/czj/Repos/opensource-hub/codex/codex-rs/app-server/src/request_processors/turn_processor.rs:590)、[Core 提交语义](/Users/czj/Repos/opensource-hub/codex/codex-rs/core/src/codex_thread.rs:316)

例如 A 任务读到新证据后，显式将线索发给正在调查的 B，B 的工作可以继续吸收该信息。这是由工具能力推导的使用方式，不是本轮实际运行证据。这里有“补送给已有工作”的执行能力，但调用方仍需判断目标 B。

## 等待与子 Agent 消息不是同一个入口

`wait_threads` 面向显式给定的任务集合，等待完成、审批或用户输入等状态，支持游标及即时快照。它不是自动筛选相关任务的订阅器。[等待实现](/Users/czj/Repos/opensource-hub/codex/codex-rs/tui/src/dynamic_tools.rs:850)

Core 还存在多 Agent v2 通信：`send_message` 采用 QueueOnly，`followup_task` 采用 TriggerTurn；共享投递路径使用明确的 Agent 目标，后者能触发工作。它们属于 Agent 协作控制，不能无条件等同于访问侧栏所有用户任务的工具。[共享通信实现](/Users/czj/Repos/opensource-hub/codex/codex-rs/core/src/tools/handlers/multi_agents_v2/message_tool.rs:1)

## 与 Clowder AI、Claude Tag 的关系

| 比较点 | 本轮 Codex 代码证据 |
|---|---|
| 跨任务读取 | 已有明确工具与历史读取路径 |
| 跨任务传话 | 已有，显式指定目标并保留来源 |
| 补充正在做的任务 | 已有 start-or-steer 提交路径，受轮次状态约束 |
| 自动判断消息属于哪个在途工作 | 在本轮核对范围内未找到对应证据 |
| 所有任务共享一个持续上下文 | 上述机制不支持这一结论 |

它与 [Clowder AI](clowder-ai-reference.md) 的相似点是独立工作上下文和显式通信。与 [Claude Tag](claude-tag-reference.md) 对照时，不能说 Codex 缺少“把信息送入已有工作”的能力；更值得比较的是发现关联、选择目标和主动参与的产品行为。仅凭代码存在与否也不能下“效果更差”的结论。

## 证据边界

本轮直接实现证据主要位于开源 TUI 的 `codex_tui` 工具、App Server 和 Core。客户端连接方式与工具注册会影响可用面，不将其等同于所有已发布版本的默认行为，也不声称桌面 `codex_app` 的完整实现都位于该仓库。[工具接入](/Users/czj/Repos/opensource-hub/codex/codex-rs/tui/src/app_server_session.rs:429)

未对全部扩展或桌面内部代码作穷尽审计，未做消息投递实测；“未找到自动相关性路由”是本轮阅读边界内的结论，不是对所有 Codex 产品实现的绝对否定。

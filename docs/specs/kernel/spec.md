# kernel (agent) Specification

> 对齐: bugfix-536
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

`agent`(内核)是整个系统唯一的 Agent 执行内核,是一个**库**:单 Agent 运行时 + 工具执行 + 技能发现
+ 事件扩展 + 会话持久化 + 上下文压缩 + 多 LLM provider 适配。

它对外**只暴露 `agent.sdk`**——`build_kernel()` 装配出一个进程内 `Kernel`,消费者持有它并 `await` / 调用其方法。内核**不内置任何 HTTP / 网络 API**;呈现为终端软件、常驻 gateway 还是云 API,是产品层决策,内核不持形态偏好(refactor-387)。

**显式不负责**:不知道什么是 coding / assistant(产品语义);不做 IM 接入 / channel 路由 / heartbeat 调度;不做 CLI 交互;不做对外网络服务。这些由消费它的产品承担。

## Canonical Areas

本包长青行为契约按 area 拆分维护。`spec.md` 是入口索引;具体 Requirement/Scenario 以同目录下的 area 文档为准。

| Area | Covers | Requirements |
|---|---|---|
| [SDK Boundary](sdk-boundary.md) | SDK 表面、产品中立装配、扩展协议、能力查询、公开类型与 Workflow 管理 | 6 |
| [Runs](runs.md) | create_session、submit/stream、steer、运行来源、权限、中断、liveness、关闭与 self-evolution side-chain 事件可见性 | 15 |
| [Model Runtime](model-runtime.md) | LLM config、per-run model routing、推理强度、模型错误恢复 | 3 |
| [Background Tasks](background-tasks.md) | 后台完成通知、subagent follow-up、Workflow、task_stop、派生子 agent 隔离 | 6 |
| [Workflows](workflows.md) | Python Workflow tool、编排 runtime、子 Agent、后台控制、resume、保存发现、预算与规模 | 8 |
| [Context and Persistence](context-persistence.md) | compaction、会话档案、事件恢复、append_message、tool call 闭合、AGENTS.md、图片、运行配置、fork_session | 11 |
| [Tools and Hooks](tools-hooks.md) | built-in tools、Hook、presenter、授权决策、cache/thinking、拒绝文本、session-local workspace extensions | 11 |
| [Skills](skills.md) | 有序 Skill 发现、读取、管理、生命周期、使用统计、preview/list_skills | 8 |
| [Prompts](prompts.md) | PromptSlots、产品中立 prompt、runtime footer policy、系统提示模板 | 4 |

## Maintenance Rule

- 新增或修改契约时,优先落到语义最窄的 area 文档;只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全,其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档,但每条 Requirement 仍必须保持 `Purpose + Requirement/Scenario` 形态。

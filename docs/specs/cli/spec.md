# cli (coding_cli) Specification

> 对齐: refactor-486-agent-native-repository-knowledge-system
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本契约层只收 **终端用户在 CLI 上可观察的对外
> 行为**；CLI 内部如何编排内核、渲染、消费事件不在此层。每条 Scenario 的主语是在终端敲命令或读输出的
> 人、消费 JSON/NDJSON 的脚本，或契约测试。

## Purpose

`coding_cli` 是面向开发者的本地编码助手终端应用：在终端内与 Agent 交互式对话，辅助读代码、写代码、
执行命令和调试问题。

它经 `agent.sdk` 在进程内装配并持有内核，不提供独立 HTTP server，也不启动 agent 子进程。它对外呈现
面向人的异步 REPL，以及面向脚本和 CI 的非交互输出。

它面向低心智负担的日常使用：默认无参启动即可用，内部连接和端口参数不得成为日常必填项。

**显式不负责**：不实现 Agent Loop、不直接调用 LLM、不管理会话持久化；不做 IM 接入、channel 路由或
heartbeat。这些分别由内核和 Gateway 承担。

## Canonical Areas

| Area | Covers | Requirements |
|---|---|---|
| [Interactive REPL](interactive-repl.md) | 启动、会话、斜杠命令、流式呈现、运行中输入、错误和非 TTY | 7 |
| [Automation Interface](automation-interface.md) | `llm-config get` JSON 与 `--text` NDJSON | 2 |
| [Product Integration](product-integration.md) | SDK 边界、CLI 自有装配和扩展目录 | 2 |

## Maintenance Rule

- 新增或修改契约时，优先落到语义最窄的 area 文档；只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全，其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档，每条 Requirement 仍保持
  `Purpose + Requirement/Scenario` 形态。

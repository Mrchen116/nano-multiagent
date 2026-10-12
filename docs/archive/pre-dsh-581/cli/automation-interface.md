# cli (coding_cli) - Automation Interface Specification

> 对齐: refactor-486-agent-native-repository-knowledge-system
> 上级: [cli (coding_cli) Specification](spec.md)

## Purpose

约束脚本和 CI 通过单命令 JSON 或 `--text` NDJSON 使用 CLI 时可依赖的机器可读接口。

## Requirements

### Requirement: llm-config get 输出单个 JSON 对象供脚本消费

`llm-config get` 把当前连接配置作为恰好一个 JSON 对象打印到 stdout。命令执行阶段失败时，stdout 输出单行 `{error, suggestion, layer}` JSON，退出码非零。模型和 provider 的启动配置通过命令行参数或环境提供；CLI 不提供已退役的 `llm-config set` 子命令。

#### Scenario: llm-config get 输出单个 JSON
- **WHEN** 脚本运行 `llm-config get`
- **THEN** stdout 是恰好一个 JSON 对象，含 `provider`、`model`、`base_url` 和 `timeout_seconds`

#### Scenario: 单命令执行错误输出单行错误 JSON
- **GIVEN** `llm-config get` 已通过命令行解析
- **WHEN** CLI 在装配或执行阶段遇到输入类错误
- **THEN** 退出码为 1，stdout 是单行 JSON，至少含 `{error, suggestion, layer}`，且 `layer == "input"`

### Requirement: --text 非交互模式单次提交并流式 NDJSON，退出码反映运行结局

带 `--text <内容>` 运行时，CLI 提交一次该文本，把过程事件逐行以 NDJSON 流到 stdout，运行到终态后退出；退出码 0 表示 `completed`，非 0 表示 `failed` 或 `cancelled`。

#### Scenario: --text 流式 NDJSON 到 stdout 并按结局给退出码
- **WHEN** 脚本运行 `--text "..."`
- **THEN** stdout 逐行输出 NDJSON 事件，首行含提交回执的 `run_id`
- **AND** 运行 `completed` 时退出码为 0，否则为非 0

#### Scenario: --text 配合 --resume 使用指定会话
- **WHEN** 脚本运行 `--text "..." --resume <session_id>`
- **THEN** 文本提交到该指定会话

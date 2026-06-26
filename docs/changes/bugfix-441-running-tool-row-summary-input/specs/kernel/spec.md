# kernel delta-spec — bugfix-441

> 对齐: bugfix-441

本 unit 对 `docs/specs/kernel/spec.md` 的增量。

## MODIFIED Requirements

### Requirement: 工具展示由工具自带的 presenter 决定

(原条目不变,补充"参数侧展示在 `tool_start` 即产出":自带 presenter 的工具,其 `tool_start` 事件的 presentation 携带 `summary` 与**从入参即可得出的那部分** `detail`(参数侧,如 bash 的命令、agent 的 prompt);`tool_end` 事件携带含执行结果的完整 `detail`(参数侧字段 + 结果侧字段)。无 presenter 的工具其 `tool_start` 不产 `detail`。`tool_start` 参数侧 `detail` 中的大字段(如待写内容)与 `tool_end` 的 `detail` 共享同一硬上限与 `truncated` 语义,执行刚开始即受截断,不因来自入参而绕过上限。)

#### Scenario: 自带 presenter 的工具在执行中即产出参数侧展示
- **GIVEN** 一个自带 presenter、且其展示含结构化 `detail` 的工具(如 `bash` / `agent`),消费者订阅会话事件流
- **WHEN** 该工具开始执行(尚未结束)
- **THEN** 其 `tool_start` 事件的 presentation 携带 `summary`,以及只含参数侧字段的 `detail`(如 bash 的 `detail.command`、agent 的 `detail.prompt`/`detail.description`),不含执行结果字段

#### Scenario: 执行结束时携带参数侧 + 结果侧的完整展示
- **GIVEN** 同一工具调用
- **WHEN** 该工具执行结束
- **THEN** 其 `tool_end` 事件携带完整 `detail`,既含参数侧字段(如 bash 的 `detail.command`),也含结果侧字段(如 bash 的 `detail.stdout` / `detail.exit_code`)

#### Scenario: 无 presenter 的工具执行中不产 detail
- **GIVEN** 一个未带 presenter 的工具(走默认 presenter)
- **WHEN** 它开始执行
- **THEN** 其 `tool_start` 事件携带默认 presentation(可见 + 名称 + 截断后参数的 `summary`),不携带结构化 `detail`

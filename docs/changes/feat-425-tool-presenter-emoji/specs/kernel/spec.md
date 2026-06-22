# feat-425 — kernel 契约层增量 (delta-spec)

> 对齐 canonical: `docs/specs/kernel/spec.md`。本文件只列本 unit 对 kernel 契约的变更,
> 收尾由 orchestrator 软对账后并进 canonical。

## MODIFIED Requirements

### Requirement: 工具展示由工具自带的 presenter 决定

工具在流式事件上的展示(`tool_start`/`tool_end` 携带的 presentation:`visible`/`label`/`summary`/
`detail`/`emoji`)由该工具自身的 `presenter`(SDK-owned `ToolPresenter`,缺省即无)决定;未带 presenter
的工具走默认渲染。应用经 `build_kernel(tools=…)` 传入的工具,其 presenter 随对象一起生效,无须额外注册
步骤。`ToolPresenter` / `ToolPresentationEvent` 在公共表面;`ToolPresentationEvent` 含 `emoji` 字段
(空串表示工具未声明,由消费者自行兜底),使工具/presenter 自带的视觉标识随事件一并透传。内置工具
`read` / `write` / `edit` / `bash` / `web_fetch` / `agent` / `memory` / `skill_manage` / `task_stop`
均自带 presenter,其 `tool_end` 事件携带结构化 `detail`(而非默认的截断参数);`detail` 中的大字段
(stdout/stderr/diff/content)受硬上限尾截断,截断时 `detail.truncated` 为真。

#### Scenario: 自带 presenter 的工具产出自定义展示
- **GIVEN** 应用经 `build_kernel(tools=…)` 传入一个带 `presenter` 的工具,消费者订阅会话事件流
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 字段为该工具 presenter 产出的
  `visible`/`label`/`summary`/`detail`/`emoji`

#### Scenario: presenter 声明的 emoji 随事件透传
- **GIVEN** 一个带 `presenter` 的工具,其 presenter 在 presentation 上声明了非空 `emoji`
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 携带该 `emoji` 值

#### Scenario: 无 presenter 的工具走默认展示
- **GIVEN** 一个未带 presenter 的工具(如 MCP / 工作区运行时发现的工具)
- **WHEN** 它被调用
- **THEN** 其 `tool_start`/`tool_end` 事件携带默认 presentation(可见 + 名称 + 截断后的参数),
  且 `emoji` 为空串(由消费者兜底)

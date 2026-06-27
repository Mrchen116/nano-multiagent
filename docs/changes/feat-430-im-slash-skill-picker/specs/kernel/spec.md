# feat-430 delta-spec: kernel

> 对齐 canonical: [`docs/specs/kernel/spec.md`](../../../../specs/kernel/spec.md)
> 本文件只列 feat-430 对内核（经 `agent.sdk`）对外可观察行为的增量。草案——收尾由 orchestrator 据实际 diff 校正并软对账并入 canonical。

## MODIFIED Requirements

### Requirement: 同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致

在 canonical 同名 Requirement 基础上，`list_skills` 返回项向消费者暴露技能路径，使同名不同路径的技能可被区分。

#### Scenario: list_skills 返回项携带 SKILL.md 路径
- **WHEN** 消费者调用 `list_skills(workspace_root)`
- **THEN** 返回的每个 `SkillInfo` 携带 `location`（该技能 SKILL.md 的路径，可空），消费者据此区分同名但不同路径的技能

### Requirement: Skill 自动发现走 prompt 列表,显式调用改写为自然语言

在 canonical 同名 Requirement 基础上，`/skill:<name>` 改写：① 命令前允许一个可选的 `[..]` 标注段（产品无关语法，内核不解析其内容、原样保留）；② 覆盖多 part 输入里命令所在的那个 part。下方 Scenario 以 IM 群聊的 `[sender]` 标注为例，但内核不感知"发送者/群聊"概念。

#### Scenario: 带发送者前缀的群聊 /skill 命令被改写且保留发送者
- **WHEN** 消费者提交一条带发送者前缀的群聊消息 `[Alice] /skill:doc fix spacing`
- **THEN** 内核将其改写为保留发送者标注的自然语言指令（前导 `[Alice]` 保留 + `Use the "doc" skill for this request.` + `User input:` 段），接收 Agent 仍可从该轮看出发送者是 Alice

#### Scenario: 群聊有其他成员先发言（多 part）时 /skill 仍被改写
- **WHEN** 群聊里其他成员先发了消息成为本轮上下文，消费者随后提交 `[Alice] /skill:doc`（该轮因此含多个 part）
- **THEN** 命令所在 part 仍被改写为保留发送者的自然语言指令，不因多 part 或非首行而漏改（接收 Agent 按 skill 执行）

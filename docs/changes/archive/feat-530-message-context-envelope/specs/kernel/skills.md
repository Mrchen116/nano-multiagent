# kernel / skills — delta (feat-530)

> Target canonical: `docs/specs/kernel/skills.md`

## ADDED Requirements

（无。）

## MODIFIED Requirements

### Requirement: Skill 自动发现走 prompt 列表,显式调用改写为自然语言

存在可见 skill 时,内核在 system prompt 注入 `<available_skills>` 列表(名称 + 描述 + 路径),模型按需用 `skill_view(name=...)` 加载 SKILL.md 全文;消费者输入的 `/skill:<name>` 被改写为自然语言指令;命令前可选的一个或多个 `[..]` 标注段被原样保留(内核不解析其内容),多 part 输入中改写作用于命令所在的那个 part。

#### Scenario: 显式 skill 命令被改写
- **WHEN** 消费者输入 `/skill:doc`(或带参数 `/skill:doc fix heading spacing`)
- **THEN** 内核将其改写为 `Use the "doc" skill for this request.`(带参数时追加 `User input:` 段), 然后走常规推理,不在改写阶段直接展开 SKILL.md 原文

#### Scenario: 命令前带一个或多个标注段时改写保留全部标注
- **WHEN** 消费者提交 `[Alice] /skill:doc fix spacing`,或提交 `[Feishu Tue 2026-08-11 15:53 CST] [Alice] /skill:doc fix spacing`
- **THEN** 内核改写命令并原样保留前面的全部标注段,带参数时追加 `User input:` 段;内核不解析标注内容

#### Scenario: 多 part 输入中命令所在 part 被改写
- **WHEN** 消费者提交多 part 输入(如群聊缓冲上下文,或文本命令 + 末尾图片),其中一个 text part 是 `/skill:doc`
- **THEN** 改写作用于该命令 part(不因命令不在首行或末位而漏改),其余 part 原样保留

#### Scenario: skill_view 启用时 available skills guidance 引导按名加载
- **GIVEN** 消费者创建的 session 启用了 `skill_view`
- **WHEN** 系统提示词包含 `<available_skills>`
- **THEN** 每个 skill 仍包含 name / description / location,且 guidance 指示 agent 通过 `skill_view`按名字加载 skill 内容

#### Scenario: skill_view 关闭时不渲染 skill_view 调用 guidance
- **GIVEN** 消费者创建的 session 未启用 `skill_view`
- **WHEN** 系统提示词包含 `<available_skills>`
- **THEN** guidance 不指示 agent 调用 `skill_view`

## REMOVED Requirements

（无。）

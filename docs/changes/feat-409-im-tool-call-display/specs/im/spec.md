# im Specification (delta for feat-409-im-tool-call-display)

> 视角:IM 终端用户(Web IM 里和 agent 对话的人)在工具调用面板上可观察的展示行为。
> 这是 spec.md【验收标准】4 个 Requirement 的契约层镜像。

## ADDED Requirements

### Requirement: 工具调用折叠态摘要有信息量且用真实工具名

每条 agent 消息下方的工具调用面板,折叠态每行显示"工具在干什么"的一句人话而非仅工具名+耗时,失败行有
可见失败标识,工具名一律为真实注册名。

#### Scenario: bash 带 description 显示人话
- **WHEN** agent 调用 bash 且填了 description
- **THEN** 该工具行折叠态显示 description 文案,不显示命令本身

#### Scenario: bash 未填 description 降级
- **GIVEN** 某次 bash 调用的 description 为空
- **WHEN** 用户看该工具行折叠态
- **THEN** 降级显示命令首段(截断),而不是空白

#### Scenario: 工具调用失败时折叠态标红
- **GIVEN** 某个工具调用失败(bash 退出码非 0、edit 未命中、web 返回错误等)
- **WHEN** 用户扫工具调用面板而不展开任何一行
- **THEN** 失败的那一行有可见的失败标识(标红 + 失败提示)

#### Scenario: 工具名显示真实注册名
- **WHEN** 用户看任意工具调用行
- **THEN** 工具名显示其真实注册名(`bash` / `read` / `write` / `edit` / `agent` / `task_stop` /
  `web_fetch` / `memory` / `skill_manage`),不出现别名或改写名

### Requirement: 工具调用展开态按工具类型呈现详情

展开一行工具调用时,按工具类型给出对应的结构化呈现,而非裸 JSON。

#### Scenario: bash 展开看到命令与输出
- **WHEN** 用户展开一个 bash 工具行
- **THEN** 看到 description、执行的命令、以及该命令真实的 stdout/stderr
- **AND** 退出码非 0 时,exit code 与报错以标红呈现

#### Scenario: edit 展开看到 diff
- **WHEN** 用户展开一个 edit 工具行
- **THEN** 看到增删着色的 diff,而不是裸 JSON

#### Scenario: write 展开看到写入内容
- **WHEN** 用户展开一个 write 工具行
- **THEN** 看到写入的文件内容预览与字节数

#### Scenario: web_fetch 展开看到网页信息
- **WHEN** 用户展开一个 web_fetch 工具行
- **THEN** 看到网页标题、URL 和正文摘录

#### Scenario: agent 展开看到完整派发 prompt
- **WHEN** 用户展开一个 agent 工具行
- **THEN** 完整(不截断)显示派发给子 agent 的 prompt
- **AND** prompt 呈现在子 agent 执行结果之前

#### Scenario: memory / skill_manage / task_stop 有专属呈现
- **WHEN** 用户展开 memory、skill_manage 或 task_stop 工具行
- **THEN** 看到该工具的结果卡片(写入的记忆 / 创建的 skill / 停止的任务),而不是截断的 JSON

### Requirement: 长输出可控展开,不撑爆聊天流

工具输出很长时,展开态默认截断 + 可控展开全部,展开后限高内部滚动,不打乱聊天流滚动位置。

#### Scenario: 长输出默认截断
- **GIVEN** 某工具输出超过单屏展示阈值
- **WHEN** 用户展开该工具行
- **THEN** 先显示截断版输出,并提供"点击展开全部"入口

#### Scenario: 展开全部后限高滚动
- **WHEN** 用户点"点击展开全部"
- **THEN** 补出完整输出,且详情区限高、内部滚动,聊天流整体高度与滚动位置不被撑乱
- **AND** 提供"收起"回到截断态

#### Scenario: 源头已截断的输出
- **GIVEN** 工具输出大到在产生端已被截断
- **WHEN** 用户展开全部
- **THEN** 在输出末尾明确标注"输出过长,已在源头截断"

### Requirement: 工具执行中状态不退化

工具尚在执行时折叠态保持运行中提示,完成后自动更新为完成态。

#### Scenario: 工具执行中
- **GIVEN** 某工具调用尚未完成
- **WHEN** 用户查看工具调用面板
- **THEN** 该行折叠态显示"运行中"提示(脉冲),完成后自动更新为完成态

# kernel / tools-hooks — delta (feat-474)

> 目标 canonical: `docs/specs/kernel/tools-hooks.md`

## ADDED Requirements

### Requirement: agent 工具以轻量参数派发真类型子 agent

消费者经会话启用的 `agent` 工具新建子 agent 时，只需提供短描述与任务说明；不必提供 skill 列表、类别别名或前台超时参数。可选 `subagent_type` 从内置真类型中选取；省略时按 `general-purpose` 运行。工具说明向消费者列出至少 `general-purpose`、`Explore`、`Plan` 及缺省行为。各类型在父会话允许的工具范围内提供可区分能力：`general-purpose` 可做修改类工作；`Explore` 与 `Plan` 不能获得会改仓库的写文件类工具，并携带只读角色指引。

#### Scenario: 最少参数新建成功且默认 general-purpose
- **WHEN** 消费者经 `agent` 新建子 agent，只提供 description 与 prompt，不传 skill 列表、类别或前台超时
- **THEN** 派发成功，子 agent 按 `general-purpose` 能力运行

#### Scenario: 工具说明列出可用类型与缺省
- **WHEN** 消费者查看 `agent` 工具的说明
- **THEN** 说明中可获知可用类型至少包含 `general-purpose`、`Explore`、`Plan`，以及不传类型时默认 `general-purpose`

#### Scenario: Explore / Plan 无写仓库工具
- **WHEN** 消费者以 `Explore` 或 `Plan` 新建子 agent
- **THEN** 该子会话面向模型暴露的工具集合不含会直接改仓库的写/编辑类工具（在父会话已启用这些工具的前提下仍被去掉）

#### Scenario: 未知或错误大小写类型失败并可理解
- **WHEN** 消费者以不存在的类型名或错误大小写（如 `explore`）新建子 agent
- **THEN** 该工具调用失败
- **AND** 失败信息指出类型未找到，并列出当前可用类型

## MODIFIED Requirements

（无整段替换；既有「agent 工具的 detail 含完整派发 prompt」Scenario 保持，detail 中不再依赖 category / load_skills 字段。）

## REMOVED Requirements

（无整 Requirement 删除。）

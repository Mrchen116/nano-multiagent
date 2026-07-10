# im delta-spec — bugfix-441

> 对齐: bugfix-441

本 unit 对 `docs/specs/im/spec.md` 的增量。

## MODIFIED Requirements

### Requirement: 工具调用折叠态摘要有信息量且用真实工具名

(原条目不变,补充"展示时机":一个工具调用的展示分两类信息源——**参数**(从入参得出:折叠行摘要 + 展开卡的命令/入参/prompt/查询词等)与**结果**(执行产出:展开卡的 stdout/退出码/正文/搜索结果等)。参数在工具**执行中**即展示,结果在**执行完**展示。)

#### Scenario: 工具执行中折叠行显示参数摘要
- **GIVEN** agent 调用一个执行耗时较长的工具(如带 description 的 bash、子任务 agent、web_search)
- **WHEN** 该工具正在执行、尚未结束
- **THEN** 其工具行折叠态显示参数摘要(bash 显 description / 命令首段,agent 显 description,web_search 显查询词),而非仅图标 + 名 + 运行中脉冲

#### Scenario: 工具执行中展开卡只显参数、不显结果或完成标记
- **GIVEN** 同上,工具正在执行
- **WHEN** 用户展开该工具行
- **THEN** 展开卡显示该次调用的参数(bash 显命令、agent 显派发 prompt、write 显待写内容)
- **AND** 不显示执行结果(stdout/退出码/搜索结果/正文),也不显示完成标记(如 `✓ completed`、"搜索无结果"空态)

#### Scenario: 工具执行完展开卡显示参数与结果全貌
- **GIVEN** 同一工具调用执行结束
- **WHEN** 用户看该工具行
- **THEN** 折叠行显示其完成态摘要,展开卡同时显示参数(命令/入参)与结果(stdout + 退出码 / 搜索结果 / 正文等),失败调用标红显失败标识

#### Scenario: 无结构化展开 detail 的工具执行中折叠仍显参数摘要
- **GIVEN** 一个执行完也无结构化展开 detail 的工具(走默认 presenter)
- **WHEN** 该工具正在执行
- **THEN** 其折叠行显示参数摘要(截断入参),展开区不残留多余内容

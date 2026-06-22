# feat-425 — im 契约层增量 (delta-spec)

> 对齐 canonical: `docs/specs/im/spec.md`。本文件只列本 unit 对 IM 契约的变更,
> 收尾由 orchestrator 软对账后并进 canonical。

## MODIFIED Requirements

### Requirement: 工具调用折叠态摘要有信息量且用真实工具名

每条 agent 消息下方的工具调用面板,折叠态每行显示"工具在干什么"的一句人话而非仅工具名+耗时,失败行有
可见失败标识,工具名一律为真实注册名。每行带一个图标:工具自带图标时显工具自带的,未自带时回退通用图标。

#### Scenario: bash 带 description 显示人话
- **WHEN** agent 调用 bash 且填了 description
- **THEN** 该工具行折叠态显示 description 文案,不显示命令本身

#### Scenario: bash 未填 description 降级
- **GIVEN** 某次 bash 调用的 description 为空
- **WHEN** 用户看该工具行折叠态
- **THEN** 降级显示命令首段(截断),而不是空白

#### Scenario: web_search 折叠态显示查询词
- **WHEN** agent 调用 web_search
- **THEN** 该工具行折叠态显示 🔍 图标 + 查询词文本,而非裸 JSON 参数或通用扳手图标

#### Scenario: web_fetch 折叠态显示抓取网址
- **WHEN** agent 调用 web_fetch
- **THEN** 该工具行折叠态显示 🌐 图标 + 抓取的 URL,而非 `status=200 (title)` 这类机器视角文案

#### Scenario: 工具调用失败时折叠态标红
- **GIVEN** 某个工具调用失败(bash 退出码非 0、edit 未命中、web 返回错误,或 memory/skill_manage
  返回 success=false 这类不抛错的失败)
- **WHEN** 用户扫工具调用面板而不展开任何一行
- **THEN** 失败的那一行有可见的失败标识(标红 + 失败提示),失败行折叠文案仍为该工具的人话主参数
  (web_search 为查询词、web_fetch 为 URL),不拼接错误文本

#### Scenario: 工具名显示真实注册名
- **WHEN** 用户看任意工具调用行
- **THEN** 工具名显示其真实注册名(`bash` / `read` / `write` / `edit` / `agent` / `task_stop` /
  `web_fetch` / `web_search` / `memory` / `skill_manage`),不出现别名或改写名

#### Scenario: 工具自带 emoji 时显示自带图标
- **GIVEN** 一个工具(含用户自定义 / MCP / 产品工具)声明了自带 emoji
- **WHEN** 该工具的调用行出现在面板
- **THEN** 折叠行显示该工具自带的 emoji

#### Scenario: 工具未声明 emoji 时回退通用图标
- **WHEN** 一个未声明 emoji 的工具(自定义 / MCP)的调用行出现在面板
- **THEN** 折叠行回退显示通用扳手图标 🔧,与变更前一致

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

#### Scenario: web_search 展开看到结果列表
- **WHEN** 用户展开一个 web_search 工具行
- **THEN** 看到逐条搜索结果(每条含标题、URL、摘要),而非裸字符串

#### Scenario: web_search 无结果时显示空态
- **GIVEN** 一次成功执行的 web_search 查询无任何命中
- **WHEN** 用户展开该工具行
- **THEN** 看到明确的"无结果"空态文案,而非空白或裸字符串

#### Scenario: web_fetch 展开看到网页信息
- **WHEN** 用户展开一个 web_fetch 工具行
- **THEN** 看到 URL、HTTP 状态码,以及抓取到的网页正文(正文非空)

#### Scenario: web_fetch 抓取失败展开看到可读错误
- **GIVEN** 一次 web_fetch 因网络错误、URL 非法或服务端 4xx/5xx 而未取到正常内容
- **WHEN** 用户展开该工具行
- **THEN** 看到 URL 与可读的错误说明或状态码,不出现空正文或 `status=None` 这类机器串

#### Scenario: agent 展开看到完整派发 prompt
- **WHEN** 用户展开一个 agent 工具行
- **THEN** 完整(不截断)显示派发给子 agent 的 prompt
- **AND** prompt 呈现在子 agent 执行结果之前
- **AND** 子 agent 失败时仍显示派发 prompt 与错误文本(不退化为空错误卡)

#### Scenario: memory / skill_manage / task_stop 有专属呈现
- **WHEN** 用户展开 memory、skill_manage 或 task_stop 工具行
- **THEN** 看到该工具的结果卡片(写入的记忆 / 创建的 skill / 停止的任务),而不是截断的 JSON
- **AND** memory / skill_manage 返回失败(success=false)时,卡片呈现失败态而非成功态

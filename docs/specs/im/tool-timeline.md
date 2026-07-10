# IM - Tool Timeline Specification

> 对齐: feat-447
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

工具调用在聊天流里的徽标、摘要、图标、展开详情、长输出、执行中状态、思考时间线和权限卡契约。

## Requirements

### Requirement: 工具徽标按中断原因显示终态

run 异常终止、工具自身超时或工具被拒绝时,IM 工具徽标必须从「运行中」收口为一个**按原因区分**的非成功
终态,不再停留在转圈状态。失败原因区分:工具因自身 deadline 到点被掐 → 「执行超时」(耗时过长);run 因
看门狗 liveness 收尸或进程异常/中断 → 「已中断」(卡死/中断)。

#### Scenario: 在飞工具按原因收口
- **GIVEN** 一条消息里某工具已开始执行(徽标运行中)
- **WHEN** 终态下发到前端
- **THEN** 该工具徽标收口为对应文案:工具自身超时显示「执行超时」、看门狗 liveness 收尸或其他异常终止显示「已中断」

#### Scenario: 被拒绝的工具显示已拒绝
- **GIVEN** 一个工具被 auto_mode 分类器自动 block 或被用户在权限卡片上拒绝
- **WHEN** 该工具的终态渲染
- **THEN** 徽标显示「已拒绝」(区别于「执行超时」「已中断」)

#### Scenario: 权限未决期间显示等待批准
- **GIVEN** 一个工具正等待用户权限决策(未批未拒)
- **WHEN** 徽标渲染
- **THEN** 显示「等待批准」,既不收口为失败也不显示「已拒绝」

#### Scenario: 已完成工具徽标不被改写
- **GIVEN** 同一条消息里其他工具已正常完成
- **WHEN** 在飞工具收口
- **THEN** 已完成工具的徽标保持原终态不变

#### Scenario: 超时收口的工具仍显示其命令与描述
- **GIVEN** 一个 bash 工具调用运行中,已显示其命令与 description
- **WHEN** 该工具因看门狗超时(或其他异常终止)被收口为失败态
- **THEN** 该工具行仍显示原命令与 description(连同失败标识),用户能看出是哪条命令被中断,
  而非只剩工具名 + 失败标识

### Requirement: 工具调用折叠态摘要有信息量且用真实工具名

每条 agent 消息下方的工具调用面板,折叠态每行显示"工具在干什么"的一句人话而非仅工具名+耗时,失败行有
可见失败标识,工具名一律为真实注册名。工具调用展示分两类信息源:参数(从入参得出,如折叠摘要、命令、
prompt、查询词)在工具执行中即可见;结果(如 stdout、退出码、搜索结果、正文)只在工具执行完后展示。

#### Scenario: bash 带 description 显示人话
- **WHEN** agent 调用 bash 且填了 description
- **THEN** 该工具行折叠态显示 description 文案,不显示命令本身

#### Scenario: bash 未填 description 降级
- **GIVEN** 某次 bash 调用的 description 为空
- **WHEN** 用户看该工具行折叠态
- **THEN** 降级显示命令首段(截断),而不是空白

#### Scenario: 工具执行中折叠行显示参数摘要
- **GIVEN** agent 调用一个执行耗时较长的工具(如带 description 的 bash、子任务 agent、web_search)
- **WHEN** 该工具正在执行、尚未结束
- **THEN** 其工具行折叠态显示参数摘要,而非仅图标 + 名称 + 运行中脉冲

#### Scenario: 工具执行中展开卡只显参数
- **GIVEN** 同一工具调用正在执行
- **WHEN** 用户展开该工具行
- **THEN** 展开卡显示该次调用的参数(如命令、派发 prompt、查询词、待写内容)
- **AND** 不显示执行结果或完成标记(如 stdout、退出码、搜索结果、`completed`、"无结果"空态)

#### Scenario: 工具执行完展开卡显示参数与结果全貌
- **GIVEN** 同一工具调用执行结束
- **WHEN** 用户查看该工具行
- **THEN** 折叠行显示完成态摘要,展开卡同时显示参数与结果;失败调用标红并显示失败标识

#### Scenario: 无结构化展开 detail 的工具执行中折叠仍显参数摘要
- **GIVEN** 一个执行完也无结构化展开 detail 的工具(走默认 presenter)
- **WHEN** 该工具正在执行
- **THEN** 其折叠行显示参数摘要,展开区不残留多余内容

#### Scenario: 工具调用失败时折叠态标红
- **GIVEN** 某个工具调用失败(bash 退出码非 0、edit 未命中、web 返回错误,或 memory/skill_manage
  返回 success=false 这类不抛错的失败)
- **WHEN** 用户扫工具调用面板而不展开任何一行
- **THEN** 失败的那一行有可见的失败标识(标红 + 失败提示)

#### Scenario: 工具名显示真实注册名
- **WHEN** 用户看任意工具调用行
- **THEN** 工具名显示其真实注册名(`bash` / `read` / `write` / `edit` / `agent` / `task_stop` /
  `web_fetch` / `memory` / `skill_manage` / `web_search`),不出现别名或改写名

#### Scenario: web_search 折叠显查询词
- **WHEN** agent 调用 `web_search` 搜索某查询词且搜索成功
- **THEN** 该工具行折叠态显示 `🔍` 图标 + 查询词文本(如 `🔍 nano multiagent 架构`),不出现裸 JSON args
- **AND** 搜索失败(provider 不可用/报错)时折叠仍显 `🔍` + 查询词,该行标红,展开能看到出错原因

#### Scenario: web_fetch 折叠显抓取的网址
- **WHEN** agent 调用 `web_fetch` 抓取某 URL
- **THEN** 该工具行折叠态显示 `🌐` 图标 + 该 URL(如 `🌐 https://example.com/doc`),不显示
  `status=200 (title)` 这类机器视角文案
- **AND** 抓取失败(网络错误/非法 URL/4xx-5xx)时折叠仍显 `🌐` + 该 URL

### Requirement: 工具折叠行图标随工具自带,自定义工具可拥有专属图标

折叠行图标优先取工具/presenter 自带的 emoji(经内核事件透传 + 落库);工具未声明 emoji 时回退到前端
按工具名的图标表(内置工具不退化,未知/DIY/MCP 工具回退通用 🔧)。

#### Scenario: 自定义 / MCP 工具声明了 emoji
- **GIVEN** 一个自定义(`.nano/tools/`)/ MCP / 新产品工具的 presenter 声明了专属 emoji
- **WHEN** agent 调用该工具,记录出现在聊天面板
- **THEN** 折叠行显示该工具自带的 emoji,而非通用 🔧

#### Scenario: 工具未声明 emoji 回退(不退化)
- **WHEN** agent 调用一个未声明 emoji 的工具
- **THEN** 折叠行回退按工具名取图标:内置工具显其既有图标,未知/DIY/MCP 工具显通用 🔧

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
- **WHEN** 用户展开一个抓取成功的 web_fetch 工具行
- **THEN** 看到 URL、状态码,以及抓取到的正文文本(正文非空)
- **AND** 抓取失败时,展开看到可读的错误说明或状态码,绝不出现空正文或 `status=None` 这类机器串

#### Scenario: web_search 展开按结果条目渲染
- **WHEN** 用户展开一个成功的 web_search 工具行
- **THEN** 展开区按条目列出每条结果的标题、网址(完整可读的纯文本,可手动复制)、摘要,而非一坨原始字符串
- **AND** 查询无任何命中时,展开区显示明确的"无结果"空态文案,而不是空白或原始字符串

#### Scenario: agent 展开看到完整派发 prompt
- **WHEN** 用户展开一个 agent 工具行
- **THEN** 完整(不截断)显示派发给子 agent 的 prompt
- **AND** prompt 呈现在子 agent 执行结果之前
- **AND** 子 agent 失败时仍显示派发 prompt 与错误文本(不退化为空错误卡)

#### Scenario: memory / skill_manage / task_stop 有专属呈现
- **WHEN** 用户展开 memory、skill_manage 或 task_stop 工具行
- **THEN** 看到该工具的结果卡片(写入的记忆 / 创建的 skill / 停止的任务),而不是截断的 JSON
- **AND** memory / skill_manage 返回失败(success=false)时,卡片呈现失败态而非成功态

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

### Requirement: 内部 IM 把思考与工具调用展示为过程时间线、外部不展示

#### Scenario: 内部 Web IM 一轮含多段思考与工具调用
- **WHEN** 一轮带多段思考、多次工具调用的助手回复在内部 Web IM 展示
- **THEN** 气泡内有一个可折叠「过程」区域，把多段思考与工具调用按真实先后次序混排；每段思考可展开读完整内容、可收起；历史回看仍可展开

#### Scenario: 内部 Web IM 无思考
- **WHEN** 助手回复本轮无任何思考
- **THEN** 过程区域里不出现思考行（无思考不留空壳）

#### Scenario: 外部 channel
- **WHEN** 同一条回复送达外部接入的 IM
- **THEN** 只显示正文、不含任何思考

### Requirement: 待决权限卡提供常驻选填的拒绝理由输入框

IM 的待决工具授权卡在决策按钮区上方常驻一个选填的拒绝理由输入框。用户拒绝时填写的理由随拒绝决定一并提交、最终透传给处理该运行的节点；选择允许类决策时该输入框内容不产生任何效果。

#### Scenario: 待决权限卡展示理由输入框
- **GIVEN** 一张处于待决态、显示「允许 / 本会话内允许 / 拒绝 / 总是允许」的工具授权卡
- **WHEN** 用户查看该卡片
- **THEN** 决策按钮区上方常驻一个选填理由输入框，留空亦可正常做任意决策

#### Scenario: 拒绝时提交所填理由
- **GIVEN** 待决权限卡的理由输入框已填入文本
- **WHEN** 用户点「拒绝」
- **THEN** 该拒绝决定连同所填理由一并被提交转发给承载该运行的节点

#### Scenario: 允许类决策忽略理由框
- **GIVEN** 待决权限卡的理由输入框已填入文本
- **WHEN** 用户点「允许 / 本会话内允许 / 总是允许」中任一
- **THEN** 该工具被照常放行，理由框内容不产生任何可观察影响

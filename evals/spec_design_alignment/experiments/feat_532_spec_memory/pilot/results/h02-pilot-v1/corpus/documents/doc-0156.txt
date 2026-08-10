# feat-409: IM 工具调用展示体验重做

## Relations

- Closes: #84（本 unit 主 issue:IM 工具调用展示体验重做）
- Closes: #83（feat-337 遗留:task.py 死代码 / agent 工具无 presenter / kernel spec 仍写 task — 经澄清并入本 unit）
- Related: #93（脱敏 follow-up，本 unit 非目标，单独跟进）

## 原始需求

> （触发）现在 bash 工具在 IM 上显示的输出是啥
>
> 我觉得用户体验很差。exit=0 elapsed=152ms 一点信息量都没有
>
> 你可以看看 openclaw，Hermes agent 的是怎么设计这个体验的
>
> 不单单是 bash 工具，其他工具都审视一遍，我的和他们的区别
>
> 你直接做个页面原型我看下吧
>
> task 的 prompt 一定要呈现，在展开后要有。这是用户判断 task 是否准确的非常关键问题
>
> bash 的输入有 description 对吧？这就是给用户看的，你没呈现？
>
> 我觉得在展开之前，不用给用户看命令吧，就看这个描述，展开后再看命令
>
> 名字不要改，比如原本工具名叫 task_stop，那就叫这个名字展示
>
> 点击展开全部 是真能展开吗？展开之后是什么效果？（→ 确认展开后限高滚动 + 可收起）
>
> 先按这个原型来

参考产物：页面原型 `docs/changes/feat-409-im-tool-call-display/prototype.html`（仓库根目录，已与用户多轮对齐定稿，左=现状 / 右=提案）。

## 澄清记录

- Q1: #83（feat-337 遗留:task.py 死代码、agent 工具没有 presenter、kernel spec 仍写 task）是否并入本 unit 一起做?
  A(原话): 并入本 unit(推荐)
  Agent 解读: 本 unit 同时承担 feat-337 收尾清理——删 task.py、把 `_TaskPresenter` 迁移为 `agent` 工具的 presenter、修正 kernel spec 工具清单。Depends-on 关系作废，#83 直接 Closes 进本 unit。

- Q2: 展示面从"只有摘要"扩成"完整 stdout / 入参 / 文件内容"后泄露面放大，本期是否同步做敏感值脱敏(token/key/password 打码)?
  A(原话): 你是看到了参考项目有做吗 …… 先不做
  Agent 解读: 核实结果——openclaw 有(`redactToolDetail`，默认开，~20 条正则 + 首6尾4 打码)，hermes 没有。用户拍板本期不做，留作 follow-up。脱敏列入【非目标】，并开 follow-up issue 记录"展示面放大但脱敏未跟上"的风险窗口。

- Q3: 生效范围只做 IM(个人助手 Gateway → Web IM 前端)，还是 coding_cli REPL 也一起改?
  A(原话): 只做 IM(推荐)
  Agent 解读: 本 unit 展示渲染只动 IM 链路。内核 presenter 改动(agent presenter 迁移、缺失 presenter 补齐)是 core/platform 共享的，coding_cli 进程内也会受益于 detail 更全，但 CLI 的 REPL 渲染层不在本期改造范围。coding_cli REPL 展示列入【非目标】。

## 用户场景

用户在 IM(Web IM）里和 agent 对话。agent 干活时会调用工具——跑命令、读写文件、改代码、查网页、派子 agent、写记忆。每条 agent 消息下方挂一个可折叠的工具调用面板:顶部一行"N tool calls · 总时长"，展开后一行一个工具调用，每行还能再点开看详情。

**今天的痛点**:用户点开一个工具调用，详情区几乎没有信息量。最典型的是 bash——点开只看到 `exit=0 elapsed=152ms`，命令产出了什么、改了什么、为什么失败，全看不到。edit 点开看不到改了哪几行，web 查到的内容看不到，子 agent 派去干了什么、回来说了什么也看不到。memory / skill_manage / task_stop / agent 这几个甚至连专属呈现都没有，点开是一串截断到一半的 JSON。结果是:工具调用面板形同虚设，用户无法判断 agent 到底做了什么、做得对不对。

**重做后用户能得到的体验**(逐条对应原型 `docs/changes/feat-409-im-tool-call-display/prototype.html` 右侧):

- **折叠态(不展开就能扫)**:每行不再只有工具名+耗时，而是"工具在干什么"的一句人话。bash 显示它的 description(如"跑 heartbeat 单元测试")，而不是命令本身；子 agent 显示派发任务的简述；web 显示站点+标题。哪个工具失败了，那一行直接标红(如 bash 失败行显示红色 `exit 1`)——不用逐个点开就知道哪一步出了问题。工具名一律用真实注册名(`bash` / `task_stop` / `web_fetch` / `skill_manage` / `agent` …)，不改名、不用别名，emoji 只作视觉前缀。

- **展开态(点开看详情)**:按工具类型给到对的呈现——
  - bash:顶部 description，下面是命令和真实的 stdout/stderr；失败时 exit code 和报错标红。
  - edit:红绿 diff，看清增删了哪几行。
  - write:写入的文件内容预览 + 字节数。
  - web_fetch:网页标题 + URL + 正文摘录。
  - **agent(子 agent):完整的派发 prompt(不截断)排在最前面，再是子 agent 的执行结果**——用户先看"让它干什么"，再对照"它实际干了什么"，才能判断这次派发准不准。
  - memory / skill_manage / task_stop:各自的结果卡片(写入了什么记忆 / 创建了哪个 skill / 停了哪个任务)，不再是截断 JSON。

- **长输出可控**:输出很长时，展开态先给截断版 + 一个"点击展开全部"。真点它，会补出完整输出，但详情区限高内部滚动——再长也不会把整条聊天流撑开、不打乱消息列表的滚动位置；可以再点"收起"。若输出长到在源头就被截断了，明确标注"输出过长，已在源头截断"。

- **执行中**:工具还在跑的时候，折叠态保持现有的"运行中"脉冲提示，跑完自动变成完成态——这一行为不退化。

## 验收标准

### Requirement: 折叠态摘要有信息量且用真实工具名

#### Scenario: bash 带 description
- **WHEN** agent 调用 bash 且填了 description
- **THEN** 该工具行折叠态显示 description 文案，不显示命令本身

#### Scenario: bash 未填 description(边界)
- **GIVEN** 某次 bash 调用的 description 为空
- **WHEN** 用户看该工具行折叠态
- **THEN** 降级显示命令首段(截断)，而不是空白

#### Scenario: 工具调用失败时折叠态标红
- **GIVEN** 某个工具调用失败(如 bash 退出码非 0、edit 未命中、web 返回错误)
- **WHEN** 用户扫工具调用面板而不展开任何一行
- **THEN** 失败的那一行有可见的失败标识(标红 + 失败提示，如 bash 显示红色 exit code)

#### Scenario: 工具名显示真实注册名
- **WHEN** 用户看任意工具调用行
- **THEN** 工具名显示其真实注册名(`bash` / `read` / `write` / `edit` / `agent` / `task_stop` / `web_fetch` / `memory` / `skill_manage`)，不出现别名或改写名

### Requirement: 展开态按工具类型呈现详情

#### Scenario: bash 展开看到命令与输出
- **WHEN** 用户展开一个 bash 工具行
- **THEN** 看到 description、执行的命令、以及该命令真实的 stdout/stderr
- **AND** 退出码非 0 时，exit code 与报错以标红呈现

#### Scenario: edit 展开看到 diff
- **WHEN** 用户展开一个 edit 工具行
- **THEN** 看到增删着色的 diff(改了哪几行)，而不是裸 JSON

#### Scenario: write 展开看到写入内容
- **WHEN** 用户展开一个 write 工具行
- **THEN** 看到写入的文件内容预览与字节数

#### Scenario: web_fetch 展开看到网页信息
- **WHEN** 用户展开一个 web_fetch 工具行
- **THEN** 看到网页标题、URL 和正文摘录

#### Scenario: agent(子 agent)展开看到完整派发 prompt
- **WHEN** 用户展开一个 agent 工具行
- **THEN** 完整(不截断)显示派发给子 agent 的 prompt
- **AND** prompt 呈现在子 agent 执行结果之前

#### Scenario: memory / skill_manage / task_stop 有专属呈现
- **WHEN** 用户展开 memory、skill_manage 或 task_stop 工具行
- **THEN** 看到该工具的结果卡片(写入的记忆内容 / 创建的 skill / 停止的任务)，而不是截断的 JSON

### Requirement: 长输出可控展开，不撑爆聊天流

#### Scenario: 长输出默认截断
- **GIVEN** 某工具输出超过单屏展示阈值
- **WHEN** 用户展开该工具行
- **THEN** 先显示截断版输出，并提供"点击展开全部"入口

#### Scenario: 展开全部后限高滚动
- **WHEN** 用户点"点击展开全部"
- **THEN** 补出完整输出，且详情区限高、内部滚动，聊天流整体高度与滚动位置不被撑乱
- **AND** 提供"收起"回到截断态

#### Scenario: 源头已截断的输出(边界)
- **GIVEN** 工具输出大到在产生端已被截断
- **WHEN** 用户展开全部
- **THEN** 在输出末尾明确标注"输出过长，已在源头截断"

### Requirement: 执行中状态不退化

#### Scenario: 工具执行中
- **GIVEN** 某工具调用尚未完成
- **WHEN** 用户查看工具调用面板
- **THEN** 该行折叠态显示"运行中"提示(脉冲)，完成后自动更新为完成态

## 范围与非目标

- **在范围**:
  - IM(个人助手 Gateway → Web IM 前端)链路的工具调用展示重做:折叠态人话摘要、展开态分工具渲染、长输出可控展开。
  - 内核 presenter 改造:补齐 memory / skill_manage / task_stop / agent 的专属 presenter，使各工具 detail 完整。
  - Gateway 透传 `presentation.detail`(现状被丢弃)。
  - #83 收尾清理:删除死代码 `task.py`、将 `_TaskPresenter` 迁移为 `agent` 工具的 presenter、修正 `docs/specs/kernel/spec.md` 工具清单。

- **非目标**:
  - 敏感值脱敏(token/key/password 打码)——本期不做，留 follow-up issue(展示面放大但脱敏未跟上的风险窗口)。
  - coding_cli REPL 的展示渲染改造——本期不动 CLI 渲染层(内核 presenter 改动会被 CLI 进程内共享，但不为 CLI 单独做展示层)。
  - 不改动工具调用面板的整体交互结构(顶部总开关 + 逐行展开沿用现状)。
  - 不引入新的工具或改动工具的执行行为——仅改"怎么把已发生的工具调用展示给用户"。

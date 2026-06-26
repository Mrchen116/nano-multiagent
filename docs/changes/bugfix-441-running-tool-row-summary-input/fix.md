# bugfix-441: 工具执行中折叠行不显示 summary、展开看不到 input

## Relations

- Related: feat-409-im-tool-call-display(建 summary→output 折叠链 + 展开卡按 detail 渲染)、feat-425-tool-presenter-emoji(给 tool_start 加 presentation 转发,但只取 emoji)、bugfix-427-bash-start-description(把 bash format_start 改成产 description summary)

## 原始报告

> 表象就是 bash 工具执行的时候，summary 没有，我也无法展开，看 input

补充(对齐过程中用户进一步精确范围):

> 准确来说，修的是：不显示 summary 和 input

Agent 解读:症状是一个——**工具执行中(running 态)那一行是空的**——但有两个面:(1) 折叠行没有 summary 文案;(2) 点开展开卡看不到 input/命令。两面根因不同(见【根因】)。本单元不含"内核 error 原文直透气泡"那个伴生问题(与本 bug 文件、根因均无交集),已与用户确认排除。

## 现象 / 复现

前置:在 IM 群聊或单聊里与 agent 对话,触发一个执行耗时较长的 bash 工具调用(短命令毫秒级跑完、running 态一闪而过,不易观察)。

1. **折叠行无 summary**:工具开始执行后、跑完之前,该工具调用的折叠行只显示 emoji + 工具名 + "运行中"脉冲,**没有** summary 文案(bash 本应显示 `description`,空则命令首段)。要等工具执行**完成**,summary 才出现。
2. **展开看不到 input**:在工具执行中点开这一行的展开卡,**展开区是空白的**——看不到正在执行的命令/参数。同样要等执行完(展开卡按 detail 渲染出命令)才有内容。

期望(对齐 CC / codex 的执行态行为,本单元目标):
- 工具一开始执行,折叠行就显示 summary(bash=description / 命令首段);执行完 summary 不变(失败转失败态)。
- 工具执行中点开展开卡,能看到该调用的 input(命令/参数);执行完照常追加结果(stdout / exit 等)。
- 该现象对所有工具同构(Read/Grep/Edit 等只是太快、running 态一闪而过不易感知),但本单元以 bash 为主验证窗口。

不变量(修复必须保住,不得为消症状而破坏):
- feat-409:工具执行中折叠态保留"运行中"脉冲、跑完自动转完成态,不退化。
- feat-425:tool_start 已转发的 emoji 全程透传,自定义/MCP 工具图标不退化为 🔧。
- 工具执行完后,折叠行 summary / 展开卡内容由 `tool_end`(format_end)的权威结果覆盖执行中的临时值(含失败态)。

## 根因

症状一个、根因两处,分属 gateway 与前端两层:

**面 1 — 折叠行无 summary(gateway 转发缺口)**

- `realtime_stream.py:69` 的 `on_tool_call` 在工具开始执行时调 `presenter.format_start()`,bash 的 `_BashPresenter.format_start`(`bash.py:95-104`)**已产出 summary**(bugfix-427 改为优先 `description`、空则命令首段)。
- `_presentation_dict`(`realtime_stream.py:220-230`)序列化时**带了 `summary`**,tool_start payload(`realtime_stream.py:77`)挂了完整 `presentation`——**summary 确实随 tool_start 事件到达 gateway**。
- gateway `main.py:3668-3692` 处理 tool_start 时,取出了 `start_pres = event.get("presentation")`,却**只读 `emoji`(:3670-3671),丢掉 `summary`**;构建的 `start_tool_call` 没有 `output` 字段。
- 前端折叠行 `collapsedSummary`(`tool-presentation.ts:53-55`)**只读 `call.output`**,running 行无 output → 返回 ""。
- 对比 `main.py:3726-3732` 的 tool_end 分支:它把 `pres["summary"]` 写进 `output`——所以 summary 只在执行完才出现。

**面 2 — 展开看不到 input(前端展开卡不读 input + running 态无 detail)**

- 前端展开卡 `ToolDetailBody`(`tool-detail-renderers.tsx:498-514`)渲染逻辑:有 `call.detail` 就按工具名走 bespoke/generic 卡,无 detail 降级读 `call.output` 字符串,**全程不读 `call.input`**。
- `detail` 只有 `format_end` 才产(bash `format_start` 只产 summary、**不产 detail**,`bash.py:100-104`)。
- 故 running 态:`detail` undefined → `output` undefined(受面 1 拖累) → `ToolDetailBody` 返回 **null,展开区空白**。
- `call.input` 虽经 `main.py:3677` 转发到前端(bugfix-416 #111 为 reconcile re-emit 而存),但**前端无任何渲染分支把它上屏**(全前端 grep `.input` 无渲染使用)。

**为什么这种错能进来(设计意图追溯)**

- feat-409 建 summary→output 链时,只在 tool_end 接线;其"执行中状态不退化"Requirement 当年仅指"保住 running 脉冲、跑完转完成态"(verification.md:38「沿用现有 running + pulse，代码未改动」),**summary 在 running 态显示从不是 feat-409 的目标**——当时 running 折叠行设计上就是 emoji+名+脉冲。
- feat-425 的 design.md:29 明确记录"tool_start relay 当前**不带** presentation",该 unit **新增**了 tool_start 转发 presentation,但其范围**严格限定 emoji**(整单做 emoji);序列化进事件的 `summary` 被留在地上没接(design.md:104 风险项「运行中行 tool_start relay 不带 presentation → 名表兜底」即此残留的侧写)。
- bugfix-427 随后把 bash `format_start` 改成产 description summary(消除"开始态显命令、完成态才切 description"的断层),**投资了内容,却因 feat-425 的转发缺口死在管道上、从未到达用户**——两个 unit 的取舍没被串起来看。
- 展开卡只读 detail(feat-409-M2)是原始设计:detail 只在 format_end 产,running 态展开为空是从未被覆盖的**原始缺口**,非某次提交引入的回归。

故无单一 `git blame` 回归点:面 1 是 feat-425 起的转发不完整 + bugfix-427 内容到位但管道断;面 2 是 feat-409-M2 起展开卡只认 detail 的原始缺口。

## 修复

<!-- worker 在 milestone 完成后回填:改了什么 + commits。 -->

## 验证

<!-- worker 回填:修前能复现(running 态折叠无 summary / 展开空白)→ 修后两面都出;
     回归:running 脉冲、emoji 透传、tool_end 覆盖、Read/Edit 等其它工具均不退化。 -->

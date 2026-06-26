# bugfix-441: 工具执行中不展示参数(折叠摘要 summary + 展开命令 input),要等执行完才出

## Relations

- Related: feat-409-im-tool-call-display(建 summary→output 折叠链 + 展开卡按 detail 渲染)、feat-425-tool-presenter-emoji(给 tool_start 加 presentation 转发,但只取 emoji)、bugfix-427-bash-start-description(把 bash format_start 改成产 description summary,false-fix,见 RCA)

## 原始报告

> 表象就是 bash 工具执行的时候，summary 没有，我也无法展开，看 input

补充(对齐过程中用户进一步精确范围):

> 准确来说，修的是：不显示 summary 和 input

Agent 解读:症状是一个——**工具执行中(running 态)那一行是空的**——但有两个面:(1) 折叠行没有 summary 文案;(2) 点开展开卡看不到 input/命令。两面根因不同(见 RCA)。本单元不含"内核 error 原文直透气泡"那个伴生问题(与本 bug 文件、根因均无交集),已与用户确认排除。

## 澄清记录

- Q1: 把"内核 error 原文直透气泡的丑陋英文串"(437 决策3 的伴生体验问题)纳入本单元,还是排除?
  A(原话): 同意
  Agent 解读: 排除。该问题与本 bug 的文件、根因均无交集,合并会让范围发散;若要修另立单元或回 437 收口。
- Q2: 本单元修的精确表象?
  A(原话): 表象就是bash工具执行的时候，summary没有，我也无法展开，看input / 准确来说，修的是：不显示summary和input
  Agent 解读: 锁定为 running 态"折叠行无 summary"+"展开看不到 input"两面,以 bash 为主验证窗口(短命令 running 态一闪而过不易观察)。
- Q3: 升 lite 还是 full?
  A(原话): 升级成full要做design
  Agent 解读: 升 full(根因横跨 gateway/前端/IM 落库多模块;实现路径取舍需 design 拍板),走 design 阶段。
- Q4: 这个缺陷的本质模型是什么(参数/结果两类信息源的时机)?
  A(原话): 这里面我和你有gap，一个工具要展示的内容，两个部分，一部分是展示工具的参数，一部分是需要展示工具输出的结果。当然这里不是说很死板的直接展示，而是说就这两个信息源。那么第一部分，应该在工具调用开始就展示，第二部分就是工具执行完再展示。现在应该是两个部分都在工具调用完才是真正展示的时候。你应该做的是给我把两者分开，而不是新增展示任何东西。
  Agent 解读: 一个工具调用的展示分两类信息源——【参数】(在执行什么)和【结果】(执行产出)。参数在发起时即确定、本应执行中就展示;结果执行完才有、执行完展示。现状两类都卡到执行完才出。修复=按天然时机把两者拆开(参数提前到开始),不新增任何展示内容。我先前"summary 缺 / input 缺两个面"的拆法模糊了这一点:这两个其实都是【参数侧】的展示(折叠摘要=参数标题,展开命令=参数详态),都被错误推迟到结尾;结果侧现状正确、不在缺陷内。

## 现象与复现

前置:在 IM 群聊或单聊里与 agent 对话,agent 调用一个执行耗时较长的工具(以 bash 为典型;短命令毫秒级跑完、执行中一闪而过,不易观察)。

**一个工具调用行,用户能看到两类信息源:**
- **参数**(这次在执行什么):折叠行的一句话摘要(bash 是 description,空则命令首段),以及点开展开卡里的命令 / 入参。
- **结果**(执行产出):展开卡里的 stdout、退出码等。

参数在调用发起时就已确定,结果要执行完才有。

**实际(bug)**:工具**执行中**,这一行只有图标 + 工具名 + "运行中"脉冲——**参数和结果都看不到**(折叠行无摘要;点开展开卡是空白)。两类信息都要等工具**执行完**才一次性冒出来。

**期望**:把两类信息按各自天然时机分开——
- **参数**:工具一开始执行就展示(折叠行出摘要;展开卡出命令 / 入参),用户执行中就能知道 agent 在跑什么。
- **结果**:执行完再展示(展开卡追加 stdout / 退出码),与现状一致。

**关键定性(用户原话 Q4)**:这不是新增任何展示。参数和结果本来都会展示,只是现状两者都卡在执行完才出;本单元只把【参数】这一类信息提前到调用开始,结果维持在结尾。亦即"summary 不显示"和"展开看不到命令"是同一件事——都是【参数侧】展示被错误推迟到结尾(摘要=参数的折叠标题,命令=参数的展开详态);结果侧现状正确,不在缺陷范围内。以 bash 为主验证窗口,行为对所有工具同构。

不变量(修复必须保住,不得为消症状而破坏):
- **执行完的展示与旧代码完全一致**(用户原话:"做完本需求,工具执行完,应该和在旧代码上展示一致")——折叠行摘要、展开卡的命令+结果、失败态,逐项与变更前等同。本单元只改"执行中"那一段:从"什么都没有"变成"展示了参数(部分内容)"。这是本单元最硬的回归判据。
- 工具执行中折叠行保留"运行中"脉冲、跑完自动转完成态。
- 工具自带图标(emoji)执行中即正确显示,自定义 / MCP 工具不退化为通用图标。
- 工具执行完时,参数展示不因结果到达而丢失或错乱;失败调用转失败态展示。

## 影响范围

- **谁受影响**:IM 所有用户,所有 agent 的所有工具调用,只要 running 态停留够久就可见(bash / agent 子任务 / web_fetch 等耗时工具最明显;Read/Edit 等毫秒级工具理论同受影响但难感知)。
- **严重度**:中。纯展示/可观察性缺陷——执行中用户无法得知"agent 正在跑什么命令",削弱信任与可控感(尤其长命令、需人盯的场景);跑完后信息完整,**无功能性损坏、无数据损坏**。
- **持续时间**:面 1(summary)自 feat-425 给 tool_start 加转发起即存在,bugfix-427 误判已修(见 RCA);面 2(input 展开)自 feat-409-M2 展开卡建成起即存在,从未被覆盖。两者都不是近期回归,是长期存在的可观察性缺口。

## 根因分析（RCA）

症状一个(【参数侧】展示被整体推迟到执行完),根因两处——参数的两个展示位(折叠摘要、展开命令)各自被一处缺口卡住,分属 gateway 与前端两层:

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
- **bugfix-427 是 false-fix**(PR #138,已合入 main):它把 bash `format_start` 改成产 description summary,意在让开始态也显人话,但**只改 presenter(`presentation.py` 一个文件)、只做 presenter 层单测(`test_presentation.py::TestBashPresenter` 断言 `format_start(...).summary == "跑单元测试"`),从未端到端验证 UI**。其【现象】段写的"开始态显示原始 command"是**从 presenter 代码推断、非 UI 实测**——真实的 running 态 UI 因本面 1 的 gateway 转发缺口(427 未碰 gateway,其 Relations 亦记"feat-425 未触及本缺口")根本不显示任何主参数,正是用户给 427 的原话"description 开始调用时没出现"。故 427 presenter 内容改对了、单测绿、unit 判"已修复",但用户可观察症状从未解决,现作为本单元面 1 重新浮出。427 的价值在于已让 presenter 在 tool_start 备好正确 summary;本面 1 是把它从 gateway 真正转发出去,让 427 的投资第一次到达用户。**教训:presenter 层单测绿 ≠ 端到端显示生效,展示链 bug 必须经真栈 e2e 看 UI 才算闭合。**
- 展开卡只读 detail(feat-409-M2)是原始设计:detail 只在 format_end 产,running 态展开为空是从未被覆盖的**原始缺口**,非某次提交引入的回归。

**回归引入点定位**:无单一 `git blame` 回归点。面 1 是 feat-425(给 tool_start 加 presentation 转发时只接 emoji)起的转发不完整,叠加 bugfix-427 内容到位但管道断;面 2 是 feat-409-M2(展开卡只认 detail)起的原始缺口。两面均为"功能从未完整实现",非"曾正常后被改坏"。

## 修复方向

高层方向(行级方案与最终取舍留给 design + milestone):

- **面 1(gateway 转发 summary)**:gateway `main.py` 的 tool_start 分支镜像 tool_end,把 `start_pres["summary"]` 写进 `start_tool_call["output"]`。需顺带核对 IM 域模型 / 落库(`tool_calls_json`) / WS delta 链是否要同步(对照 feat-425 emoji 当年走的同一条链),并确认前端 reducer `mergeToolCall` 的 tool_end 覆盖不被"非空不 clobber"挡住(`chat-stream-reducer.ts:72-74` 已预判:tool_end 带非空 summary 时正常覆盖)。
- **面 2(running 态展开显示 input)**:让执行中展开卡能显示该调用的命令/参数。实现路径有多条(前端 `ToolDetailBody` 在无 detail 时降级渲染 `call.input`;或 `format_start` 也产 detail;或两者结合),**纯实现取舍,留给 design 按最小改动 + 一致性拍板**。
- **验证硬约束(防重蹈 427 覆辙)**:本单元验证**必须经真栈 e2e 看 UI**——presenter / 单测绿不算闭合;须实际观察 running 态折叠行出 summary、展开卡出 input,并回归 running 脉冲 / emoji 透传 / tool_end 覆盖 / 其它工具不退化。reviewer 阶段产出独立回归矩阵(`regression.md`)。

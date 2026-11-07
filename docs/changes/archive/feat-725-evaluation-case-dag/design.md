# feat-725 技术方案

## 现状与复用

当前 evals/ui/server.ts、catalog.ts、app.js 提供 Memory 和 Intelligent UI 的统一入口，Memory 轨迹通过既有 observer 桥读取。Spec/design alignment 有八份 case.json。内部协作的 GC-01/02 分别从 Markdown 解析消息，再由两个 Python 文件安排顺序与条件。score.py 和图片探针也依赖 case 编号。旧脚本和材料均属于本次已在工作的 eval 分支。

本轮复用 eval-ui 服务、目录与原生轨迹桥，扩展 catalog。统一内部协作的图定义和 Python engine，启动器、默认能力核验及 scripted child provider 继续使用当前实现。产品运行时仍只经已有 integration 公共 API。

## 接口与职责

cases/<id>/case.json 为协作 case 唯一定义。必需元数据包含 version、id、title、description、context、tasks、nodes。节点有 id、type、task、title、after（成功依赖）、order_after（仅等前节点结束）、worker（逻辑执行者）、content（text 或 file）、attachments、when、fallback、checks、source。节点类型 user_message、delegate、worker_message、user_reply、child_message 分别对应用户输入、观察派工、内部回报、观察公开回复、观察向子 Agent 的续派。worker_message.final 表示有内容的正常收尾。

delegate 观察真实直属子会话收到的任务，根据 matcher 绑定逻辑 worker，允许在同一会话内承担新阶段。它不会代主 Agent 调用派工。matcher 只支持 all/any/not 文本正则以及 source_node（匹配实际投递文本），不执行任意代码。user_reply 支持 after_report，必须在该回报实际进入根模型后才匹配公开消息。child_message 同样检查实际子模型输入。对于已排队的续派，fixture 可以执行一次只读 read 使被阻塞的模拟轮次推进，随后重新核验真实模型请求。

公共 loader 校验重复/缺失 ID、worker 绑定、未知类型、坏正则、缺失材料、环、引用路径。after 与 order_after 均形成 DAG；失败只通过 after 传播。一个 event loop 推进可就绪节点，对每个等待节点独立计时，避免一条慢分支堵住全部 case。发送副作用前保存 intent，成功后保存回执；无法确认是否发送的中断标为需要核对，不自动重发。默认新 run；resume 只接续已保存且结果明确的节点。

统一 runtime 适配器处理登录续期、IM 发信、实际子会话观察、回报投递、图片探针和持久化。与纯 DAG 调度之间保留唯一 dispatch/poll 接口，以确定性模拟验证分支和证据，不复制真实运行逻辑。CLI run.py CASE RUN；原 run_gc01.py/run_gc02.py 仅保留短参数转发入口。迁移后的 score 直接遍历图和运行记录生成事实与全案审阅材料，固定按节点类型检查原话、附件、备注和授权。

## 四类评测展示

catalog 从各 suite 的权威 case 数据构建统一 EvaluationCase。Memory 展示随仓 synthetic 示例，已有私有单题归档继续通过原命令挂接。Intelligent UI 展示四 case。Spec/design alignment 从 dataset.json 指向的 case.json 和 public brief 构建列表，详情说明实验状态与来源，不从 judge-private 复制答案。内部协作由相同 case.json 加载 DAG，文件正文在后端解析成详情。页面只展示登记过的材料。

前端保留左侧 suite/case 导航，协作详情使用任务筛选、可缩放纵向 DAG 和右侧节点详情。图节点展示编号、动作类型、谁到谁与一行摘要，边区分成功前置和顺序约束，选节点高亮直接前后关系。详情展示完整正文、附件声明、前置/备用路径、来源和类型检查项。图外同时有按序列表便于窄屏和键盘阅读。结果可选由 CLI --coord-run 挂接，显示 passed/failed/blocked/pending 和证据入口，静态定义默认明确未运行。

## Context 影响

Consumer 为被测主 Agent 和原生子 Agent。case 定义与评分材料留在控制进程；只有所选用户消息、附件与 scripted child 消息进入模型。迁移保持消息原话和图片引用。实际原生模型请求是消费证据，队列回执单独显示。after_report 必须以根模型收到回报为界，不能用 mock 排队时刻替代。

## 前端原型

见 prototype.html。must-match 为四类目录、任务筛选、图中连线和节点详情、完整文本与前置条件、窄屏可操作。既有相邻页面依据 evals/ui/index.html 和 app.js 的目录、白色材料区和 observer 桥。字体、色彩与留白沿用该页，按查看图与阅读消息的任务重组材料区。原型为交互示意，实施阶段用真实 GC-01/02 数据验证。

## 迁移与验证

无生产部署迁移。当前未提交的 eval 资产沿本分支继续保存。GC-01/02 的 case.md 改为说明与来源指针，完整时间线由 case.json 提供，rubric 保留语义注意点。删去 case 专用控制流程。校验两份图无环、消息正文与现有材料一致、真假前置、分支失败不串线、同一 worker 续派、重复派工绑定歧义、图片真实 read_image 和结果导出。页面检查四 suite、详情/筛选/长文/窄屏、既有 viewer 测试回归。本轮通过无模型的假传输验证共享 engine，并保留真实 IM adapter 作为后续实跑入口；新 engine 首轮真实 A/B 单独记录覆盖与限制。

## Runbook

pnpm eval-ui --output <私有目录>，CLI 输出唯一服务入口。Ctrl-C 关闭当前 viewer。无需启动产品隔离栈即可预览所有公共 case。内部协作真实回放沿 start.sh 启动隔离栈，模型和默认配置核验继续沿用。界面验收在真实浏览器上检查登记、选择、DAG、过滤、节点详情与窄屏。

## Milestone

| ID | 依赖 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-unified-cases | 无 | evals/agent_coordination、evals/ui、相关入口文档 | [reviewer] 四 suite 同一服务、GC-01/02 可读 DAG 与完整材料、新 case 无专用代码可预览；[worker] loader/engine/adapter 窄测试、迁移校验与 viewer 回归通过，浏览器交互核验，保留真实模型未测边界 |

## Spec delta

评测工具独立于产品 current specs。no spec delta，更新 evals/README、evals/ui/README 与 suite README 作为维护入口。

## 条件、状态与接续契约

after 为硬依赖，order_after 仅约束观察起点。所有节点在两类前置都进入终态后开始自己的 timeout 秒计时；after 任何节点未 passed，则本节点 blocked，order_after 不传播失败。观察窗口从这些前置的实际完成时间开始，绑定角色的首次派工可匹配当前 run 中先前的委派，续派只匹配该来源用户消息投递之后的请求。after_report 还要求内部回报正文进入根模型的实际请求，以请求时间作为公开消息下界。

when 是当前节点的内容选择门，不另造执行支路。无 when 直接执行；when 成立使用 content；截止不成立且有 fallback 使用 fallback，两者都记 passed，收据保留 chosen=content/fallback、实际正文和证据。截止无 fallback 则 untriggered，下游硬依赖 blocked。条件不成立只表示 case 前置未触发，审阅再判断 Agent 是否合理内部决定。硬失败 failed 用于错误、错投或明确动作失败。optional 观察若未触发也为 untriggered，对 order_after 的其他事项没有影响。并行汇合 after 等待所有成功，order_after 只等待结束。节点级次数由状态机控制，成功发送不重复。

示例，GC-02 U06 的 when={source:"public", matcher:{any:["agent-desktop"]}}，content 保留原句，fallback 使用明确项目名的独立问题。U09 的公开观察节点需要 S02 的 after_report，matcher 同时要求三平台和真实选择题；之后用户节点 when 匹配 B 对应 macOS 优先，未匹配用明确文字 fallback。没有公开问题时观察节点 untriggered，U09 blocked。

checkpoint 保存 frozen case SHA256、全部节点状态、chosen、实际正文、观察消息/请求 ID、worker 绑定、每节点 start/deadline 和 action intent/receipt。resume 校验 case 哈希，沿用已终态节点和已决定内容，不重新选择。未结束的纯观察沿用截止；发送前 intent 已存在但缺明确 receipt 时标 uncertain 并阻断依赖，要求操作者按真实 IM 查明后重开 fresh run，默认不自动重发。图片上传及 IM 发送使用同一收据边界。

auto delegate 匹配到多个未绑定会话时不猜，记录候选；运行目录 bindings.json 可为逻辑 worker 选择已通过同一 matcher 的真实子会话。同一实际会话可以绑定不同阶段角色。S12 分开委派时以两个各自回报节点表达，不由一个节点替别人宣告完成。

## 真实通信验证

M1 另要求一条新建隔离 Global 会话的最小真实链路，使用默认工具/feature/skills、Sol 6.1 high：主 Agent 派工，脚本子 Agent 回报，根模型实际收到，IM 公开询问，用户回复，同一子模型实际收到续派。包括一次 fixture read advance 和对应收据。以真实 wire、native session 和 IM 消息对齐，证明 adapter 的事件边界。完整 GC-01/02 效果比较仍属独立实验。

## 原型 must-match 投影

| 区域 | viewport / 状态 | 体验结果 | M1 验收 |
|---|---|---|---|
| 四 suite 导航 | 桌面，切换目录/case | 返回前一个案例和选择其他评测材料可发现 | 实际服务逐类打开 |
| DAG 与筛选 | 1280px，全部/iOS/旁支 | 能辨认独立工作，过滤后保留外部前置提示 | 真 GC-01/02 检查 |
| 节点详情 | 长报告、用户批准、图片声明 | 流向、正文、来源、前置和检查项随选择一起变化 | 点击对应真实节点 |
| 阻断分支 | 公开提问未出现 | 受影响节点与继续的独立任务可辨认 | 模拟失败及运行覆盖 |
| 按序列表 | 390px，长正文 | 无需缩小文字即可选择节点和读消息 | 窄屏真浏览器 |

原型走查已用本机 HTTP 预览和 Playwright CLI 在 1280×800、390×844 检查节点选择、两任务旁支、阻断演示、任务过滤、长正文及 Memory 返回入口。桌面截图在本地 .playwright-cli/page-2026-11-07T04-53-58-850Z.png；该文件为本地证据，不提交。实际完整图的缩放和全量节点连线在 M1 真页面检查。

when 支持 evidence_node 引用已成功前置的收据正文，直接检查那条消息而不重新套用当前节点的时间窗口。GC-02 U09 的 B/文字选择必须用该方式读取公开选择题收据。仅显式 source=public 的条件才在当前窗口扫描新的公开消息。派工的角色匹配则使用受派内容和 source_node 指定的用户原话；角色绑定歧义保持待核对。

2026-11-07 M1 实施采用同一数据驱动的 78/24 节点定义，来源说明跟随各节点。worker_titles 仅为图中的角色名展示，不改变 runtime 绑定。四 suite 可发现、分支模拟和条件消费边界的窄测试已通过；真实隔离链与最终界面验收另记录证据。

## 用户缩限后的验证范围

用户明确本轮无需真实评测，立即停止两处新建模型现场。此前 M1 真实通信短链的追加退出标准由该决定撤回。M1 交付以共享 loader/engine/runtime 的模拟与协议边界测试、真实 Web 服务与浏览器操作为准；真实完整 case 与 Prompt 效果均不在本轮结论内。静态审查仍检查消费证据的实现语义，不能以排队充当已读。

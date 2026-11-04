# M1 实施记录

> 当前状态：实现与适用验收完成，已归档。原始实现冻结 c46e35c43；开放 PR 默认值补充源码冻结 b628f3398。PR 远端 CI 属于随后交付门禁，结果以 PR 为准。

## 基线与范围

- 开发基线：`492b72603cebc5f904f7001b12e3d4475ce55639`（Gate 2 R4 已批准）。独立开发 worktree：`/Users/czj/.codex/worktrees/unit-feat-705/nano-multiagent`，分支 `unit/feat-705`。
- 主线负责角色工具／Context、配置更新／占用／恢复及验收；独立首轮子任务负责根／一级指导、PA 默认、两个随包 Skill 和 Node 创建默认值，提交 `fcd995949`。
- Task 业务、调度、数据与客户端布局不改。父子通信直接复用 DSH；不加 parent-ID 或 send_message 指导，不新增 fork 清理流程。

## 测试策略与既有覆盖

| 风险 | 归属及处置 | 证据 |
|---|---|---|
| Global 根／一级／二级／fork 的工具、初始 Context 与冷恢复 | 扩展既有 `global-child-tools.test.ts`；保留原权限／冷恢复保护，调整已被新分工取代的 Global 通用 child 身份文案断言；SingleThread 原断言保留 | RuntimeClient 真 DSH，捕获实际 llm/stream 请求、native schemas、工具结果及原 ID 冷恢复 |
| 根选择不误撤工作能力、占用仍记账 | 扩展 `capability-state.test.ts` 和上述原生 fixture；不另建平行套件 | 根配置变更期间 child read 仍合法，根继续接新输入；内部完整占用与编辑器选择依赖投影分开 |
| Goal 独立选择与根 fork opt-in | 扩展 `goal-opt-in.test.ts` 的既有配置矩阵 | 默认及显式 fork-only 不改变 Goal，保存／撤回原规则保留 |
| 创建目录与 PA 用户配置 | 保留 Node capabilities、IM personal-agent 测试，仅增加 fork default_on 断言 | 子任务 Node24 红绿，25/25 通过；旧 Persona 不回填保护保留 |
| 内部消息、来源、归属与 Task 边界 | keep communication-native、llm-attribution、task-child-context、native-human-source | 纳入窄回归，未改 Task 执行规则 |
| 自主分工与公开交付 | daily 隔离 Global／PA 真实模型旅程，独立产品验收 | 待版本冻结后执行；不能用 stub 代替 |

## 已执行证据

- 使用本机 dev_host check 核对 Air；固定 Node24、主仓 Python venv；worktree 独立 frozen-lockfile 安装及构建，不复用指向主仓 lib 的 node_modules。
- `/tmp/feat705-baseline-red.log`：临时还原五个 runtime 源文件到 `fcd995949` 构建，修正后的新增原生用例确实失败：一级只得到根所选 subagent/send_message/context 工具，缺 read/write/bash/fork/管理工具。随后原样恢复候选源文件并重建；临时还原未提交。
- `/tmp/feat705-core-tests2.log`：第一组3文件9用例通过，包含无额外二级身份、原生父级 ID／AGENTS、真实内部工具执行、同 ID 冷恢复与 Goal。
- `/tmp/feat705-narrow2.log`：7文件18用例通过，包含根选择变更时一级继续工作及新输入接收。工具占用编辑器只显示真正依赖根选择的调用，后端仍保存全部调用并保护共享 Feature／Skill 撤回。
- 后续增加 fork 的实际 system 内容与父一级一致断言，发现共享 PA／Task／UI 指导只识别普通 child 的真实缺口；通过已有可信 fork 角色识别，统一为 internal execution 解释，保留根直接 fork 和 SingleThread 原规则。`/tmp/feat705-narrow3.log` 最终7文件18用例全部通过，包含新增 fork system 与父一级一致断言。
- 测试注入曾误返回 presentAs 的 disposer，导致后续 agent/created 装配被截断；已修正测试回调。该现象不是产品工具泄漏，不作为产品修复结论。

## 尚待完成

最终窄回归、完整 CI 等价检查、daily Global／PA 实测、独立产品审查、code review＋verification、delta 校正／current 归并、final sync、归档和 PR／远端 CI。当前不宣称已完成这些门禁，不部署或合并。

## 最终请求与运行门禁补充

- `/tmp/feat705-provider-wire2.log`：将新增 Global／PA 两个用例改为本地 Anthropic SSE recording provider（复用 llm-attribution 的公开适配路径），2/2 通过。断言直接消费 HTTP 请求体；metadata 仅从只观察、不替换响应的 llm/stream middleware 取得 native 身份。覆盖一级、普通二级、worker fork 的实际 wire system/tools/messages、原生父级 ID／AGENTS、fork system/tools 与父一级一致，以及同 ID 一级和二级冷恢复；总会话数保持4，没有重复创建。
- 独立静态审查 `45cd9117c` 的 code findings=[]；verification 记录运行证据尚未完成及 delta 需修改旧身份条目。后者已在能力 delta 显式 MODIFIED 同名工具规则与子执行 Context 条目，保留 SingleThread／fork 行为；待独立校正复验。
- 初次后端／前端／daily 构建并行造成多项跨进程和 DOM 超时，已保留 `/tmp/feat705-ci-test.log`、`/tmp/feat705-ci-frontend.log`，仅停止本轮两个过载 CI 及其后代，不作为通过证据。后续对同一完整测试集合限并发复跑，不改断言或超时标准。
- Python 辅助／架构回归129 passed /28 deselected；ruff check、ruff format（97文件）及 docs-check 通过。最终 build、typecheck、packaged iOS runtime 检查通过。daily 真栈已ready，独立产品 reviewer 正在自然旅程验收；ready 不等于验收通过。

## R1 产品问题与修正

- 独立 R1 报告已保留于 acceptance.md（运行源45cd9117c）：E 委派前与一级重复读同三份资料、PA 把独立新产物并到已完成事项、fork设置刷新超时无法关闭，均不降为通过。
- 根指导补明确：独立完整事项先委派；通用 Persona／workspace 的资料读取、实施、验证要求交给一级，不作为根先执行一遍的理由。按请求产物识别独立事项，另一个独立交付即使比较旧成果也新派一级，原成果路径只作上下文；旧目标的补齐／修订仍联系原执行者。不回写 Persona，不改 Task。
- 全量限并发结果暂不通过：184文件1089用例通过，25文件28项失败，绝大多数为超时，含临时检查清理未确认。现场发现本轮失败测试遗留7个独立DSH进程持续占CPU；仅按本unit路径与PPID=1清理它们，真实R1服务由e2e-down正常停止，其他现场未操作。失败集合保留 `/tmp/feat705-failed-tests.json`，后续逐文件低并发复验，不隐藏失败。
- 清理后 R2 相关原生回归 `/tmp/feat705-r2-narrow.log`：Global child tools（含HTTP wire与两级冷恢复）＋Goal opt-in 2文件7用例通过，46.81s。
- R1 当前共享4000代理未开日志。R2复用现有 LLM_PROXY 的官方 --log 独立实例，绑定127.0.0.1:56067；工作目录和日志均为本轮私有临时根，仅隔离daily配置指向它。生产共享代理、用户dev-host配置均不改；实例运行数据／认证／原始请求不提交。待R2自然旅程及upstream捕获后再结论。

## 当前交接状态（仍未完成 M1）

- 已同步 `origin/main@aa0a3d126c5bf88a20af87c7c9db458706ea3c4e` 的 feat-703；合并冲突只在内部工具排除集合，保留分层并排除 `agent_creation`。普通一级、二级和 worker fork 不取得该主 PA 产品能力。当前实现冻结 `9af20eae88a5f327ad9981d3a81eae029809fab2`，后续仅审查报告／本记录。
- 独立 R2 静态复验（code-review.md／verification.md）：code findings=[]；旧 V2 关闭、delta aligned；HTTP wire 与普通二级同 ID 恢复缺口已关闭。V1 仍在，1 CRITICAL /0 WARNING，不能以静态通过宣布产品验收完成。
- `/tmp/feat705-ci-rechecks.json`：原全量失败的25个文件逐文件串行复跑全部通过；此前全量其余184文件1089项通过。两份运行记录分别保留，不伪称同一次全绿运行。
- `/tmp/feat705-ci-frontend-bounded.log`：111文件1056用例全部通过（maxWorkers=1）；interactive assets 检查通过。critical级别audit门禁通过，不声称依赖没有低于该门槛的报告。
- 同步后 build/typecheck、docs-check通过；原Python129项、ruff、packaged iOS runtime检查仍适用。合并主干后的 Global child tools 和 PA 创建后端正常；personal-security 两项目录检查超时尚未转绿。
- 对照实验 `/tmp/feat705-main-baseline-catalog.log`：同一环境临时将本unit改动的integration runtime源码全部还原到未修改 `origin/main`，重建并执行原目录用例，仍报 `Capability inspection deadline exceeded`。随后 finally 原样恢复候选源码并重建，git status 核实没有残留源码改动。它证明失败非候选独有，不足以断言环境是唯一根因。
- R2 daily bootstrap 两次遭遇目录超时／配置准备不可用，未绕过默认工具同步、未延长检查期限、未关闭 Task 或降级验收。R1 两处行为问题已有指导修订，仍需在正常真栈中复测，不能标为已解决。设置 fork 的关闭旅程也未完成。
- 已向用户异步澄清是否将现有目录阻塞的排查修复作为本轮前置一起推进；未收到答复不视为授权扩范围。分支保留、unit active，不归并 current、不归档、不创建 Ready PR、不合并或部署。
- 恢复位置：本 worktree／unit/feat-705；先读 spec/design、R1 acceptance 和 R2静态报告。下一步是收取范围答复、处理／恢复能力检查前置，正常 daily 环境中重测 Root 先委派、同项目新独立产物与旧产物修订、fork开关，并补真实provider/upstream证据，完成剩余门禁及PR交付。
- 本轮收尾：独立 IM／Node／DSH 栈已按 e2e-down 停止；独立模型日志代理已核对私有 cwd 后停止，其认证／上游配置副本已删除，56067无监听；本unit测试没有遗留native进程。开发worktree保留用于未完成M1，不依赖旧ready标记，恢复验收须重新准备私有模型配置与隔离栈。主工作区及其他服务未操作。

## 2026-11-04 最新主干续验

- 用户要求在最新 remote main 继续真实验收；同步 `3da78a00a7cc8ace9d172c0b0d59c5d6e7881e0b` 后冻结 `30eafa50c80182bb39cb2b26fe01c0729f3ba78b`。main 增量是 PA 专属出行 Skill 与 Dreaming 测试退出修复；无合并冲突。独立静态 R3 已核其分层交互，findings=[]，V1 等待证据。
- `/tmp/feat705-r3-regressions.log`：4文件22例通过；`r3-build/typecheck/docs/python/ruff/ios-runtime/audit.log`：构建、类型、文档、129 Python、ruff、原生渲染检查与 critical audit 门禁通过。旧前端全量有效范围暂保留，后端最终全量待续跑。
- 新 daily 环境正常 seed，node `wt-nano-multiagent-96298`、IM62948；未绕过同步或延长检查期限。独立私有模型代理沿官方 `--log` 记录本轮真实请求，不动共享代理或生产。
- R2 产品报告 `ab8973f8b`：11 pass／2 fail／2 inconclusive。E 委派前重复读已消失，PA 同项目独立新成果与旧成果修订已正确归属并交付；E 收完整成果后又完整读四份原文做一遍核对，仍为 major。根指导补清全程（含交付后返回）由执行者调查验证，主按需看成品、覆盖和具体缺口，缺口交原执行者，禁止例行重新读原文审计；待新运行复验。
- 设置保存检查仍复现7秒超时。定界于临时原生进程进入 Nano initialize 之前；离线同 profile／cwd／owner 环境启动约1–2秒，未确认唯一根因。临时只对检查进程做栈／CPU采样；用于定位的编译产物日志插桩已 finally 还原，不作为产品修复。带调试采样的一次开启成功不计自然验收；随后未调试的正常API关闭200／1.96秒，同栈fork已关闭，但仍需独立界面开关旅程，不称超时已修复。临时端口9229已随检查进程退出释放。
- R3 产品报告 `1a6c4a5c3`：12 pass／1 fail／2 条件分支未触发。fork 在一次页面刷新恢复后真实完成开、保存、重载、关、重载，三项 Goal 不联动；不声称已有偶发目录超时根治。E 回报后只读成品，交付阶段不重复原文已改善；但委派前仍读原三份材料，raw upstream 确含新指导，排除陈旧版本。进一步将既有主从职责置于 Global 指导首部，明确根协调身份、读材料前按请求产物定执行者，多来源调查并制作分析／文档／实现属于整项委派，即使工具步数少；Persona 的先读要求不作为根初始化清单。未修改或回填用户 Persona，工具权限未收紧，待 R4 真实复验。

## 最终集成检查与 R4 运行

- 已进一步同步 `origin/main@90efdd3dc2c1dda9efd5ffc0f2acbb01f5492dde`（706 Web 日期分隔），冻结源 `c46e35c43c12b744d4c05be160dc173d25bde499`。后端及 Context 无额外主干实现变化；新前端已真实构建，未改本 unit 的角色或 Persona 基线。
- `/tmp/feat705-r4-backend-serial.log`：单worker完整后端 **210文件1129项全部通过**，732.20秒。开始于 f514 已构建 lib；期间 c46 新增的 Global 指导没有重建或混入该运行，90ef 相对3da的主干代码仅前端显示。因此该证据保留用于未变执行机制，不冒称其验证了新指导的自主行为。
- 随后在 c46 构建／类型检查全过；`/tmp/feat705-r5-narrow.log`：4文件12项全部通过，覆盖 Global/PA 两级最终wire和同ID恢复、Goal/fork、Context revalidation provider、native communication。此为最新已构建指导的窄机制证据；自主行为由 R4 真栈另证。
- `/tmp/feat705-r5-frontend-all.log`：最新前端完整 **112文件1059项全部通过**，含706新增日期用例；pretest interactive assets通过。`r5-frontend-audit.log` critical门禁通过（有低于门槛的既有报告），`r5-ios-runtime.log`原生渲染资产／类型检查通过。
- `/tmp/feat705-r5-python.log`129 passed／28 deselected，ruff check与97文件format通过；docs-check通过。最终归并／归档后仍须再跑文档及unit归档门禁。
- R4 fresh daily：node `wt-nano-multiagent-64076`、IM62610，c46构建后正常seed并ready，无期限放宽或同步绕过。独立产品 reviewer 按 E 主链复验，R2 PA、R3手动开关等有效具体结论保留。两个未自然触发条件按 design 的 worker原生机制与产品自然旅程分层记录，未故意删除状态或诱导错误，也不声称其模型分支已发生；不将故障注入额外强制为本轮自然验收门槛。

## M1 退出与交付

- R4 独立产品验收 `97edacf4a` 必验路径通过：根全程不读原三份资料、唯一一级负责、原ID补充、日常直接回应、只读成品并向原聊天实际交付。旧轮次反例完整保留，两个未自然触发条件不冒充模型分支已通过。
- 最终独立 code review／Context findings=[]；verification Round6 targeted-closure PASS，V1 closed，0 CRITICAL／0 WARNING，delta aligned。实现冻结 c46、验收报告97ed，后续归并／归档不改运行源码。
- 三份 delta 依最终核对归并 current Gateway Global／PA／能力 area，更新 Gateway 入口派生计数；Task 业务与客户端布局不在本unit改造范围。
- 全部自建 IM／Node／DSH 与私有模型代理已停止；IM62610、模型56067和临时调试9229均无监听；tmux本轮session已清理。认证／上游配置私有副本已删除，合成日志本地保留不提交。开发worktree为后续PR审查保留，不部署、不合并。
- M1 实现与适用本地验收完成；unit整套归档，最终文档/归档检查及PR远端CI随后由交付方执行。远端全绿前不声称PR已交付。

- 归并／归档后 `scripts/docs-check` 通过（278 maintained Markdown／68 required routes），`check_change_unit_archived.py --head-ref unit/feat-705` 通过；`git diff --check` 通过。最终归档提交仅文档移动、相对链接校正与已审 delta 的机械归并，运行源码和测试未改变，既有门禁结论有效。

## 开放 PR 默认值复核（2026-11-04）

- 用户明确授权 `exit_plan_mode` 默认关闭、可手动开启且旧显式名单不改，纳入本 unit；PR #459 核实仍 open／unmerged，基线 main 90ef 未推进。无需新增生命周期或 Task 机制。
- `/tmp/feat705-plan-exit-red.log`：新增默认值断言在旧实现上确实失败（Node 默认标记、原生默认工具集各一处）；随后只修改两层默认选择及实际默认限制，不改已保存名单。
- `/tmp/feat705-plan-exit-build.log` 构建通过；`/tmp/feat705-plan-exit-green.log` 3文件11项通过，含普通／Global 未配置默认关闭、显式开启、实际 llm/stream 工具列表，以及 Global／PA 两级 HTTP wire 和同 ID 恢复回归。llm/stream 的新增断言是录制 fixture，不冒充新增真实 provider 自主行为。
- 初始上下文数据由真实 R4 上游请求重新计算核对，已创建 [Issue #460](https://github.com/Mrchen116/nano-multiagent/issues/460)，含完整22,200字符 System、36工具统计和18,701总构成。样本显式开启 exit，保持历史原文与计数，不回写成新默认；完整优化另议。
- 用户已要求保留轨迹预览，隔离服务 http://127.0.0.1:62610 持续保留；不重置或重 seed 现有数据。此前退出时清理记录是历史状态，现为重新开放预览。
- 本轮待独立 patch code/Context review、targeted verification、设置页 targeted 验收及新 head CI；其他指导、自然模型旅程和未改区域的既有证据保留，不机械重复全量验收。

- R7 静态检查在用户停止 review 前已完成：findings=[]、delta aligned；用户停止后仅保存既有报告，提交 b05c46ffd。产品 R5 实际已在停止通知前完成并提交794f3293b：新建默认、手动开关保存重载、旧E显式开启保留和Goal/fork独立均pass。两报告通知到达顺序不同，verification追加事实校正，没有重新启动review。
- 测试 Agent `r5-exit-settings` 保留为v3／exit关闭，无未保存更改；没有发送模型任务，旧E／原轨迹未改。正常CLI restart后Node ready，IM62610及对照页面HTTP200；用户要求的预览继续保留。

## 用户复核后的提示词精简（2026-11-04）

- 按用户要求对本次主从规则及其中继承的旧段落一起精简，而非把“旧代码已有”当保留理由。root 协调段649→216 tokens、整个 Global 指导1211→778；一级职责259→100（同一 o200k_base 估算口径）。移除回执／恢复笔记频率等常驻细则，保留实际职责与本产品公开交付边界。
- PA 新建默认移除重复的主从职责，复用共享 Global 指导，只保留个人助手特有观察、推荐、按需 Skill 和表达要求；不回填现有 Persona。原 Task、工具选择、权限和普通二级无变化。
- `/tmp/feat705-concise-build.log` 构建通过；`concise-tests.log` 3文件10项通过，覆盖 Global/PA 两级实际HTTP wire、同ID恢复、默认工具及原生通信。受控provider证据不冒称新自然模型旅程；R4自主行为仍仅证明其原长版，不把它改记为精简版实测。
- 用户已要求停止review，本次不重新派独立审查或自然任务验收；只做当前修改的基本回归和CI。精简的收益目前是确定的静态token减少，行为及性能改善未另行实测。

- `/tmp/feat705-concise-im-build.log` 和 `concise-pa-tests.log`：IM构建及2文件30项PA创建／默认／不回填回归通过。PA新建默认419→205 tokens。
- 原上下文对照页面保留R4真实捕获，新增精简版源码及明确标记的同配置System重建下载，不覆盖旧请求或将其冒充新真实模型运行。最终System重建估算为3851 tokens（原4284）；完整工具／消息部分未因本轮文字精简改变。

## 对外角色措辞与新对照页（2026-11-04）

- 用户明确外部身份是一个负责的 IM Agent，与人和其他 IM Agent 平等协作；内部委派不使主会话成为所有聊天的总负责人。根开头移除 main coordinator／sole user-facing contact，改为同一对外角色及自身接受事项的责任；current／delta 用同一句边界，Requirement 数不变。
- 调整后的 root 完整指导797 tokens（改前main712；上轮长版1211），协调正文208；一级100；PA新建默认205。`/tmp/feat705-identity-build.log` 构建及 `identity-tests.log` 2文件9项原生wire／恢复／通信通过，不冒称新增真实模型自主旅程。
- 用户要求现有对照URL改为最新main与PR，并加入Personal Agent；main重新fetch仍为90ef。对照页会清楚区分原始真实捕获与两侧源码重建，并分别展示新建PA默认说明与既有Persona不回填。

## 四份实际请求与对照交付（2026-11-04）

- 用户要求以真实捕获为准，已用 git archive main90ef 的integration源码重新编译（只在ignored cache内，不改主仓）；PR49ee独立已构建lib。两个版本分别通过标准prepareProfile／RuntimeClient启动新DSH进程。普通Global和Personal各一份首次provider/upstream请求，均走现有隔离56067代理和真实配置模型，各自产生恰好1次请求并completed；未替换或拼接System。
- Global main session efe7d395-5eb4-42eb-9f77-8963d35a7851／PR 5f946929-b7bb-422d-a393-956d57f671b1；Personal main dabd9e92-c279-48c6-aaad-28f89ed1a912／PR 28188fc4-845f-4e11-b973-2bf7fd6a2002。原请求和SHA-256在本地 .cache/feat705-context-capture/actual-manifest.json、页面actual-provenance.json可复查。私有headers／凭据不复制进页面或提交。
- 同角色workspace、AGENTS、模型、输入和工具／Feature显式选择固定；Global保持E Persona，Personal默认Persona按各版本实际模块加载。只使用对应版本打包Skill，不读私人全局扩展；Task宿主为空闲，产品写入拒绝。原始动态时间和ID不归一化，已有PA Persona与原IM聊天轨迹不改；采样不等于新的IM自然交办验收。
- 实际完整System：Global3785→3870 tokens，Personal4560→4552；工具分别36／39，两侧保持。采样整体分别15487→15568、16884→16880；与原R4的18701是不同动态消息／AGENTS配置，不能把总量差异全算作压缩收益。
- 原URL重做为Global／Personal两类的main／PR实际对照，含职责说明、完整System、逐行差异、首轮消息、逐工具token、原请求下载及来源。旧R4及旧重建页面仅保存在r4-captured历史入口，不再作为本轮实际对照。浏览器真实切换Global／Personal和完整System已核可用；四个原生采样进程均已正常shutdown，预览服务按用户要求保留。

- 最终检查发现 context-revalidation-provider 的既有装配断言使用旧身份首句作Global段标记。保留其“原生Global指导确实进入请求”的检验，改用未变的 Messages and public delivery 段标记，避免将身份措辞锁死。`/tmp/feat705-identity-context-revalidation.log` 1文件2项通过；仅测试断言调整，不改运行源码，四份49ee实际请求仍是当前实现的有效捕获。

## PA 专属提示与不相关指导收口（2026-11-04）

- 用户要求清理普通 Global／一级中的 PA 专属内容，并以实际捕获更新全行对照。PR459核实open／unmerged、HEAD e2034a204，开工clean。本轮自行修正与验证，不重新派独立审查。
- 复用 global-child-tools 的 Global／PA HTTP wire 矩阵增加消费者边界保护：普通根／一级无 sender.is_owner／delivery=observer，PA仍有；普通 Inbox 不声明review/message_id；一级保持交互产物Skill入口而不带ComposeMessage聊天操作段。`/tmp/feat705-role-guidance-red.log` 旧实现两例按新边界失败。
- 来源专属段移入Personal角色section，一级换短授权边界；根工具Schema／说明按personal投影。清理通用根中PA代发和Heartbeat重复句，Global/PA一级UI改为短的按需制作／回传要求。通用pa_agent_id消息归属、Task、Memory／Skill及DSH工作指导仍按其真实用途保留。
- `role-guidance-build.log` 构建通过。`role-guidance-green.log` 4文件12例中11通过，旧父子读取例一次返回diagnostic/unavailable；无源码调整的同文件重跑 `role-guidance-recheck.log` 6/6通过，其他3文件6例首次已通过。新增角色检查全过；此仅记录一次未复现的旧读取异常，根因未确认，没有修改读取／恢复机制或声称已修复。
- 真实捕获、页面更新与新head CI待补；旧请求会保留历史快照，不以源码替换改写模型输入。

- 最终补齐Heartbeat仅主会话装载的角色约束；新构建 `role-guidance-final-build.log` 通过，`role-guidance-final-wire.log` 2文件8项通过（含两级HTTP wire、fork前缀、同ID恢复、开启Heartbeat时根有quiet协议而一级无、Context revalidation）。`role-guidance-security.log` 2文件24项通过，覆盖独立来源审核与PA权限；先前 personal-child-delivery／native communication 的有效结果保留。

## 角色收口后的实际请求（2026-11-04）

- 同步main0287088be（仅bugfix709文档）后冻结运行源码5a97b6ce8。重新通过标准RuntimeClient／原生subagent采样Global／PA主会话、一级、二级共12份首次真实provider/upstream请求。没有替换输入或模型响应；四条链均记录实际turn/end并正常shutdown。与上轮一样为受控原生委派，不冒称模型自主选择分工或新IM自然任务验收。
- `.cache/feat705-context-capture/role-guidance-tree-manifest.json` 与页面actual-provenance.json保存版本、父子ID、输入、原请求路径、SHA-256和实际原生完成事件；全部raw哈希和消息中的Current context window id逐份一致。普通根／一级无sender.is_owner和delivery=observer，PA根／一级仍有；普通Inbox实际schema不含review/message_id、PA仍保留；所有一级均不带ComposeMessage和Heartbeat协议，二级继续纯原生。
- 完整System实际估算：普通Global main3785→PR3757，一级2274→1205，二级2274→672；PA主4560→4522，一级2373→1387，二级2373→672。相对上轮候选普通根3870→3757、一级1749→1205；PA根4552→4522、一级1848→1387。工具定义投影变化以原JSON／逐工具统计为准，不把System下降冒充总请求等量下降。
- 对照页按新12份捕获重生成，6组main／PR差异逐行核对与两侧完整System完全一致，保留空行和全部未改动行。旧12份页面与请求归档到role-scope-before，未重写旧证据。原IM聊天／轨迹和用户Persona不改，当前预览待正常Node重载；自建采样进程已退出。
- 合并main后文档／归档检查通过；main仅文档推进未失效本轮相同运行源码的窄检查。新head远端CI随后执行；不声称旧head全绿已证明本轮代码，也不将一次未复现的旧父子读取异常称为修复。


## 移除重复历史恢复提示（2026-11-04）

- 用户确认没有 Nano 差异时不重复强调上游已有规则。核对 Super Agent 的 admission／subscriptions 及当前 dsh-agent-context checkpoint：换窗已有 recovered material 不产生授权的实际提醒。删除主会话 source 段的两句历史／恢复说明，以及一级 delegated source 的同义句；不改原生组件，不删 Task 控制的 Nano 特有来源语义或独立审核器规则。
- 此次只删重复文案，不新增文本快照测试；复用既有 Global／PA 两级实际 wire、恢复与权限检查，并重新捕获候选请求更新全文对照。原 main 实际捕获保留，页面标明各自采样时间和版本。

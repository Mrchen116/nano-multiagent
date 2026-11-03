# M1 实施记录

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

# feat-705 产品验收

## R1 · full · 2026-11-03

**Verdict — fail**。Global 和 PA 能交办、接收补充并同时处理日常消息。固定日常环境的工程 Global 在委派前重复做了一级执行者的资料调查；PA 把独立的新比对工作接到了已交付的旧提纲事项。现有设置页成功保存 fork 开启，重新加载后无法恢复编辑。

受审运行源 `492b72603cebc5f904f7001b12e3d4475ce55639 → 45cd9117cb6183f504cdf63bdb5c8aef4e882dd3`。测试、进度和 delta 文档随后更新至 `d0c37a863`，运行栈未换版。使用 daily 模板，节点 `wt-nano-multiagent-5095`、本地 IM 56142。E/P/Q 为 codexOAuth:gpt-6.1-sol / high，PA 为 codexOAuth:gpt-6-astra / medium；codex 审核用 gpt-6-luna。测试主人、普通 Global 和 PA 均为隔离身份。新增一个 E 私聊，两份主委托和关联练习、缺资料分支。Task 保持日常配置。

### 用户旅程与证据定位

- E 私聊 `c_xw0ywm5u`，根 `1e9d5c7b-332d-4b90-97fc-9ce3f7e0008e`。清单委托 `45cdb8ad4fcc` 对应一级 `40c9da4b-287b-447e-a1ed-3a8377a59c5d`。主 turn 1 在创建一级前依次读取项目三个资料；一级 turn 1 实际又读取 brief.md、feedback.md、checklist.md。daily 角色说明要求“先读取”三份资料。用户的日常算时与新增分类要求由主分别回应、投递给原一级，公开回复 `e0f5ef241ba0`。产物 r1-qa.md 末尾标出 QA-06、QA-07 必须离开再回来，明确未实际执行应用测试。
- 同一 E 聊天的练习卡 `ea0430a47aba` 由独立一级 `8c946357-02aa-4932-8e00-787f36d4ec9b` 承接。停止指示 `481980c99eb7` 仅命中练习卡，根 turn 3 实际 interrupt_agent 成功，公开回执 `6f33f507ae36`。明确接续 `9133533b6db0` 在根 turn 4 转回同一 ID，子轨迹保留 interrupted turn 和接续后的 turn；既有清单继续执行。
- PA 私聊 `c_3f56ed3391fa`，根 `19e2e718-65c4-42dd-bdba-a62d48c422d8`，一级 `d50038a5-814c-4429-9249-03943aa73c91`。会议提纲委托 `e6635f48f8a5`、午饭散步状态 `d67be12ef5c2`、限时补充 `cd70ea88e47a`。PA 直接回应状态、向原一级转发 15 分钟约束，未为自述增开执行。主在原聊天发出 `07ba2a35ff42`，四项为 5/4/3/3 分钟，与 r1-meeting.md 一致。随后 `7d2e39265b2e` 明说“另有件事”，提供新输入、要求单独交付新比对；主给已交付提纲的原一级发 send_message，将新单作为旧事项后续处理。
- Web Chromium，1280×720。Agents → P → Config → Tool Allowlist，subagent_fork、get_goal、create_goal、update_goal 均未勾选。选择 fork、Save Agent，重载后 fork 仍勾选。刷新状态显示 Refresh failed，整个名单按钮禁用，无法撤回；多次 Refresh status、切换至 Q 再切回 P 状态相同。隔离 gateway.log configuration-inspector 对 daily-product 连续 timeout，样例 request_id `d4663a37-0e55-45ec-a96e-e890a3d29b9b`，耗时 7275ms。截图保存在验收机器临时文件 `/tmp/r705-fork-refresh.png`。无新增布局或设计稿。
- Work 的主/子记录、真实工具结果、来源聊天的消息及公开回执独立核对。Air 声明的 LLM_PROXY 日志目录内无本轮真实会话，session 与 raw/openai_codex 最近记录止于 10/26，4000 监听进程未带 --log。真实模型请求的上下游原文在 R1 不可验证；未变更共享代理。另有机制证据 `/tmp/feat705-provider-wire2.log` 的受控原生 RuntimeClient + HTTP recording provider 两个用例通过，覆盖 Global/PA、普通二级、fork 继承与原 ID 冷恢复；`/tmp/feat705-narrow3.log` 18 项、`/tmp/feat705-role-boundaries.log` 9 项通过。两类证据分别使用。

### 问题

| 级别 | 用户可观察结果 | 再验所需 |
|---|---|---|
| major | E 主和一级对同一份清单重复调查三份原始资料 | 保留原 daily 角色说明，重走自然任务 |
| major | PA 将另行交办的访谈比对沿用已完成提纲的执行者 | 同一项目分别测修订旧成果与交付新成果 |
| major | P 保存开启 fork 后无法再编辑关闭 | 已保存配置重载后重测开关、其他工具及 Goal，保留超时现场 |

### 首文档场景覆盖

期望均来自本 unit 的 spec.md 同名 Scenario，以下按首文档顺序记录。

| Scenario | 结果 | 证据及边界 |
|---|---|---|
| 整项交办与内部再分工 | fail | E 根和一级均实际读取同组三份资料；PA 提纲仅由一级调查。 |
| 返回结果不足或执行能力不可用 | inconclusive | 访谈文件未预置；PA 在源聊天 b0f442e73ff3 说明缺少原文，未虚构新增需求。未触发已交回成果遗漏后需要原执行者补做的分支。 |
| 新工作与原事项更正 | fail | 两条补充均正确回到原一级，E 新卡片独立；PA 新比对归属错误。 |
| 内部普通进展无需父级续令 | pass | E、PA 一级自行推进读取、制作和核查，根没有逐步骤批复或重复播报。 |
| 一天内的小事与状态变化 | pass | 算时直接回答 14:30；PA 回复午饭散步状态，无额外执行或日程。 |
| 日常中出现独立交办 | fail | 原提纲与日常并行；随后独立比对并入旧工作。 |
| 决策与最终结果 | pass | E 在 19577070b320 公开交付清单路径与覆盖；PA 已公开交付，与文件一致。练习卡选型在源聊天 94c43e85cf25 由 E 提问；主人选择 b8b0fcb38fb3 由 E 原生 send_message 给原一级 8c946357。 |
| subagent 始终通过 Global 与用户沟通 | pass | 用户侧仅见 E/PA 原聊天消息，一级沿原生父子通信，工作轨迹可单独查看。 |
| 更正或停止一个独立事项 | pass | 两个不同一级；只 interrupt 练习卡，清单继续，并保留已有文件。 |
| 明确接续与原执行者不可用 | inconclusive | 原练习卡 ID 续推已证实；原执行者无法恢复时的说明未实际触发。 |
| 主会话关闭 fork，一级仍可组织下级 | pass | 受控实际 HTTP 请求核对一级的工作工具、fork 与子父关系，未要求真实模型为验收机械分工。 |
| 初始上下文与责任不串层 | pass | 受控 provider 请求覆盖普通一级、普通二级、fork 原生继承，一级与二级冷恢复 ID 一致。 |
| 新建与无显式选择 | pass | daily P 界面默认未勾选且可找到 fork；默认值边界结合工具选择回归。 |
| 手动开启与关闭 | fail | 保存开启后重载仍勾选；实际页面持续禁用，R1 未能完成关闭。 |
| 保留已有选择和一次性语义 | pass | P 保存的 fork 选择重载后保留；历史显式名单、一次性原生语义结合受控能力和冷恢复证据。 |

R1 截止时训练卡已按选定受众交给原执行者制作；未将其最终文件计作通过证据。P 临时 fork 开启状态因配置页无法编辑保留在本轮隔离环境。

长期 current spec 的归并归本 unit 交付方。验收未修改源码、配置文件或上层文档。服务生命周期由主 Agent 管理。

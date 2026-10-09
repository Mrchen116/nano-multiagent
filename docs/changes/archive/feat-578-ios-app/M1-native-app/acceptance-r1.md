# feat-578-ios-app — 原生产品验收 R1

> Review date: 2026-10-05 (Asia/Shanghai)
> mode: full；executed_base / validated_at: `b970e20a60c0d1e18bc10d1d734b75d3d11cf4d6`
> 本报告只评价已安装的该版本，不评价后来工作树的修复。开始时 HEAD 与 validated_at 一致；结束时 HEAD 为 `8b30e23614c289a7064c78dcf2711357caace540`，caller 已在并行推进合并/下一版修复，未更新本轮安装的 binary。

## Verdict

**fail**。一个已观察到的 major 产品问题；其余未完成的必验分支为 **inconclusive**，不能将已经跑通的主路径扩大为 S1–S30 全部通过。

Highest Required Action: **fix-implementation**。需要针对新构建复验，并在可操作环境恢复后补齐本报告所有 inconclusive 分支。

验收后段 CUA 返回：`The Mac is locked and automatic unlock could not unlock it.`。因此停止 UI 操作，没有绕过锁屏，也没有争用手机。此环境阻塞不是产品缺陷。真机、Mini AltServer、USB 拔除后的同网续签与自然过期恢复，按用户已明确的先完成 App/模拟器/IPA 顺序延后；尚待用户安排，未请求或接触手机。

## 方法、版本和环境

- 独立读取 change-reviewer skill、spec.md、design.md、coverage.md、prototype.html、installation-plan.md、worktree-runtime.md 和相关 current IM 账号/任务/Work/消息/指标契约；**未读取实现源码、worker 成功叙述或测试来代替产品验收**。
- iPhone 17 Pro Simulator，iOS 26.4，UDID `1CE31893-672F-495A-B2B5-3ACF39A7A257`；native Simulator CUA。截图为 780×1678 的含模拟器边框画面；不冒充 390/430/600 多尺寸全部验过。
- IM `http://127.0.0.1:62008`，实测 listener PID 11706，cwd `/private/tmp/nano-feat578-ios-runtime`；测试账号 nano。运行环境由 caller 准备并负责清理。未重启任何服务，未触碰生产/Mini/iPhone Mirroring/Chrome 用户数据。
- API 只用于准备隔离测试数据（注册可处置成员、向真实 Agent 发任务图请求）以及 S18 的第二客户端并发写。产品结果均从原生 UI 检查；API 成功本身没有记为 UI 通过。
- 未使用 paste。CUA 的非 ASCII 实际输入未成功；中文 IME 完整输入/组合行为不能据此判定产品失败。普通数字文本真实键入/发送成功。原生表单通过 `Scroll Down/Up` 辅助动作可滚动；普通滚轮和 drag 的失败属于本轮驱动限制。
- 只写此报告，无 commit。截图本地产物不提交。测试数据及状态留给 caller：peer 私聊改名 578001 并置顶；节点别名 578；账号语言中文；策略保留天数 31；新全局 Agent ID 578001、最终显示名 578002；测试群 578100；测试用户 578review 已停用；任务图 tg_457e364c。

## 实际用户旅程与证据

### J1 原生聊天与偏好

原有 peer 私聊打开详情，将名称改为 `578001` 并置顶。返回后标题更新；通过实际 UITextView 键入 `234+567=?`，提交时可见 Sent/Running，随后出现 Completed 和真实回复 `801`，附本轮上下文、缓存比例与 1.0s。会话详情未占用底部四入口。当前账号没有在这些截图中展示其他非验收会话内容。

群创建中选择 e2e-peer 与新全局 Agent，输入 `578100`，实际进入空群聊；提及菜单列出这两个真实 Agent。一次点击输入位置后输入插入到了提及中间，提交的是错误测试字符串，**不作为正确提及路由证据**。slash 菜单选择 `/skill:nanoassistant-docs` 后只进入草稿，没有自动发出。

### J2 全局 Agent 创建、Work 与任务回聊

从我的设备进入创建页，使用在线节点、默认真实 workspace，设 ID/名称 578001、全局模式。核对模型、工具、Skills 与运行特性，打开真实提示词预览；界面明确稳定提示词不含运行时上下文。创建后显示“Agent 已创建”和实际目录，返回节点列表 Agent 数从 2 变为 3，Agent 列表出现新 Agent，详情提供全局 Work。

为形成真实任务数据，通过 API 向此 Agent 的真实聊天发“保存原生验收计划、准备材料→完成检查、只保存不执行”。随后在原生 Work 看到主执行运行中、inbox/task_graph 调用、一次失败后成功、思考、send_message 和完成记录。展开 task_graph 得到真实参数、结果、耗时及“工具调用完成不代表子执行完成，也不代表已向聊天发送”。这不是 fixture。

Tasks 出现“原生验收计划”；原生关系图显示准备材料→完成检查；打开后者显示前置和变更说明；点击回聊后跳到正确会话并把 `[完成检查](...node=n3)` 追加到既有空白草稿，发送按钮可用但未自动发送。聊天中真实 Agent 明确仅记录、未执行。

证据：`output/feat578/reviewer-agent-created.png`、`reviewer-work-tool.png`、`reviewer-task-graph.png`、`reviewer-task-reference.png`。

### J3 配置冲突与恢复

UI 打开新 Agent v1，把名称改为未保存草稿 578002。独立 API 客户端按真实 v1 配置更新为 v2/578003。UI 提交旧版时显示“状态冲突；草稿已保留，请重读并核对。profile_version conflict”，编辑禁用且提供重读。

重读后可展开服务端值 578003/v2，并明确选择“保留草稿，基于此版本继续编辑”或“使用服务端配置替换草稿”。回到顶部确认 UI 仍持有 578002/v1；明确选择保留后再次保存，显示“配置已由节点确认；聊天在下一轮采用新配置”。返回列表后显示名 578002。没有把旧草稿静默覆盖到第二客户端版本。

进入 HEARTBEAT.md 可见真实默认文件；cron 列表显示没有返回任务，并明确超时也可能返回空列表，未伪造成功读取。没有现有 cron 可执行删除验收。

证据：`output/feat578/reviewer-config-conflict.png`，本轮 CUA 可见反馈。

### J4 我的、节点、策略、公司准入

- Profile 选择中文，保存显示已保存，返回主入口后主要导航变中文。
- 节点别名改 578，保存说明配置已保存、状态以真实心跳为准；返回列表保持 578，实际状态在线。
- 管理员策略页可见默认模型、审计、最大步数、请求限制、附件大小、保留天数。把保留天数 30→31，保存显示策略已保存；容量显示整个服务 0.0 MiB 已用/预留、10240 MiB 上限。尚无 owner 上传量数据，不能据服务总量证明 owner 分项。
- API 准备 pending 测试用户 578review，UI 列出待批准→批准加入→有效成员；点击停用最后管理员显示影响确认，确认后明确拒绝“不能停用最后一位有效管理员”。测试用户停用亦经明确确认，最终显示已停用，管理员仍有效。
- 绑定设备页清楚显示当前接收账号与“链接仅在当前页面内存、不要发到聊天”；未有可用待绑定 Gateway flow，不冒充双端接受成功。

证据：`output/feat578/reviewer-policy.png`、`reviewer-last-admin.png`，本轮 CUA 状态反馈。

### J5 提醒与安装、附件入口

Help 明确：仅前台跨未静音聊天提示且不显示正文；后台/锁屏/终止不保证系统推送；免费签名通常 7 天，以 AltStore 实际到期为准；同网需要配对、Wi-Fi sync 与 Mini AltServer；失败可 USB 恢复；过期保持同账号/标识，不先删除 App，不重启 IM/Gateway。实际 Work 期间出现过“收到新消息”且没有正文的轻提示；没有对提醒去重、关闭与跳转完成全分支验收。

文件入口实际弹出系统 Files，显示无最近项目，取消后回聊天且发送按钮禁用。照片入口在相同群的附件菜单点击两次，菜单关闭后仍为聊天，没有选择器或错误提示；第二次经过其他工作后再观察仍相同。随后尝试用新截图坐标复核时电脑已锁定，未能完成该次操作。未上传或分享任意用户文件。

证据：`output/feat578/reviewer-install-help.png`；照片失败与 Files 取消的实际 CUA 截图/状态在本次验收记录中，锁屏阻止保存照片复核的独立本地截图。

## Reference Artifacts Reviewed

参考为 design.md 的 P1–P5 和 prototype.html 相应页面；只比较导航、交互、信息语义，不比较 UIKit 与 HTML 像素。

| Reference | Required contract | Actual product evidence | Viewport/state | Conclusion |
|---|---|---|---|---|
| P1 四入口/详情/composer | 四入口、原生返回、详情隐藏全局栏、草稿 | J1、task-reference.png | 单个 iPhone 17 Pro Simulator，780×1678 外框截图 | 已走的结构 match；中文 IME/软件键盘/多尺寸/Dynamic Type 未完成，整体 inconclusive |
| P2 Tasks 图→节点→回聊 | 真实图、依赖/层级、引用追加不发送 | task-graph.png、task-reference.png，J2 | DAG 两节点、真实 Agent 生成 | DAG 主路径 match；探索/子层级/失效聊天未完成，整体 inconclusive |
| P3 Work/子执行/审批 | 主子归属、明细、审批等待确认 | work-tool.png，J2 | 真实 global_main 工具明细 | 主轨迹 match；子轨迹和实际审批无数据，整体 inconclusive |
| P4 全管理与错误恢复 | 完整分组、实际保存、冲突恢复、权限 | config-conflict.png、agent-created.png、policy.png、last-admin.png，J3/J4 | owner/admin 在线、真实并发冲突 | 已走旅程 match；通道生命周期、普通成员权限等未完成，整体 inconclusive |
| P5 提醒与安装 | 前后台边界、续签失败/过期恢复说明 | install-help.png，J5 | 完整帮助滚动到底 | 说明语义 match；真机实际续签未验，不能用帮助内容替代 |

## 问题清单

| ID | Severity | Regression Relation | 期望/实际/复现证据 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| R1-01 | major | direct | S10：群578100→附件菜单→照片，两次菜单关闭后仍为聊天，无照片选择器/可行动错误；同菜单文件可进入 Files。J5实际UI记录。 | fix-implementation | 不能开始照片上传核心旅程；修复后必须真实选择、上传、接收、预览/分享复验。不得以本轮之后源码变更回写通过。 |
| R1-02 | blocking (evidence/environment) | unclear | Mac 锁定，CUA明确无法自动解锁；剩余模拟器分支未完成。 | resume-acceptance | 不是实现缺陷；需恢复人工可访问桌面后继续，无需生产或手机。 |
| R1-03 | blocking (scheduled evidence) | unrelated-existing | S29/S30及真机输入/媒体/前后台证据按用户安排延后。 | schedule-acceptance | 不提前索取手机；完成当前阶段后按用户时段落实实际安装、续签与过期恢复。 |

Side finding (minor)：创建/编辑页将整段长工具说明直接展开，抵达保存按钮需越过约数十屏，Workflow 说明单项占很多屏。主操作可达，未将此记为阻塞；可考虑折叠长说明以降低常规编辑成本。

## 验收标准逐 Scenario 覆盖

所有期望来源均为本 unit `spec.md` 对应编号；并参照 `coverage.md` C01–C34 与 design.md P1–P5。`inconclusive` 明确表示整个 Scenario 尚未完成，已成功的子步骤不会掩盖其剩余范围。

| Requirement | Scenario | 实际证据/验证方式 | 结果 | 未完成或限制 |
|---|---|---|---|---|
| R1 | S1 四入口与原生返回 | J1–J5：四入口、聊天/Tasks/Agent/我的下级均为原生，详情无全局栏，返回自然 | pass | 仅本模拟器观察范围；不证明真机安装 |
| R1 | S2 键盘、长内容与辅助操作 | 实际数字输入、长表单辅助滚动到保存、可读AX名；J1/J3 | inconclusive | 中文组合输入、软件键盘、大字体、VoiceOver实际导航、复制未完成 |
| R2 | S3 登录、注册与恢复 | 会话已登录；API准备pending用户不作为原生注册证据 | inconclusive | 原生登录/注册、重启恢复及停用账号本人页面未走完，锁屏中断 |
| R2 | S4 暂时失败与退出切换 | 未执行身份切换与429/断网 | inconclusive | A→B页面/附件/草稿清理及迟到响应需恢复UI后实测 |
| R3 | S5 找人、建聊与群设置 | J1/J2 创建Agent私聊、J1创建578100群，联系人真实身份/设备；群入口成功 | inconclusive | 搜索、真人私聊、成员增删/解散确认与人数变化未完成 |
| R3 | S6 会话偏好与已读 | J1改名/置顶、返回回显 | inconclusive | 静音、可见域已读、历史不强拉到底未完成 |
| R3 | S7 发送、提及、命令与历史 | J1真实数字发送→801；slash只填草稿；J2引用保留 | inconclusive | 群提及测试误插入，未形成有效路由证据；分页、配置边界、草稿隔离未完整验 |
| R3 | S8 发送结果不确定与重连 | 正常发送完整完成；未制造断网/响应丢失 | inconclusive | 幂等恢复及前后台断线补齐需实际故障窗口 |
| R3 | S9 消息操作、fork 与Skill蒸馏 | 看到整理会话知识入口；未形成完成旅程 | inconclusive | 复制/fork/草稿生成、离线原因未验；入口不等于通过 |
| R4 | S10 上传、接收与导出 | J5 Files打开/取消；照片入口两次未开 | fail | R1-01；图片上传/预览/分享整条旅程受阻 |
| R4 | S11 附件失败与权限改变 | 尚无本轮成功上传媒体 | inconclusive | 超限/上传下载失败/撤权缓存/外链凭据均未验 |
| R5 | S12 过程与结果 | J1回复指标；J2真实Work含工具/思考/失败/耗时与完成边界 | inconclusive | 子任务后台返回、统计明细/未知项、回看全部分支未完成；不引用root静态结论代替UI |
| R5 | S13 审批提交与确认 | 本轮真实运行没有触发权限请求 | inconclusive | 缺pending实际请求与延迟回执数据；未用伪造审批卡代替 |
| R6 | S14 任务层级、关系与回聊 | J2真实DAG→完成检查→前置/变更说明→正确聊天追加引用 | inconclusive | 探索图、子层级面包屑、搜索分页、无权/失效关联未完整覆盖 |
| R6 | S15 全局Agent主子工作轨迹 | J2真实全局主轮次及过程 | inconclusive | 未产生真实子执行/分页历史，非owner权限未验 |
| R7 | S16 在线节点创建与路径确认 | J2 UI真实创建全局Agent，实际目录、节点数3、模型能力/预览 | inconclusive | 已有目录确认、切节点保持模式、离线/重复ID/路径错误/草稿取消未完整验 |
| R7 | S17 所有配置字段与预览 | J3改名保存/重开列表；完整字段分组、Skills模式、真实preview、固定workspace | inconclusive | 所有模型备用/推理/工具/Skills选择逐项保存未验，不能以字段存在替代 |
| R7 | S18 保存冲突、确认中和权限 | J3真实v1/v2冲突、草稿保留、重读/明确选择、最终节点确认 | inconclusive | 冲突主路径通过；节点延迟确认、非owner隔离未完成 |
| R7 | S19 Skills、心跳与定时任务 | Skill空状态；HEARTBEAT.md实际正文；cron空结果/超时说明 | inconclusive | 无已有cron删除对象；心跳设置保存、Skills有用量/离线未全验 |
| R8 | S20 新增、编辑与凭据替换 | Add channel原生SecureField、单provider说明、空字段禁保存 | inconclusive | 无独占测试Bot授权与凭据注入，不触碰生产；未创建/替换真实通道 |
| R8 | S21 连接、停用与删除恢复 | 空通道页说明保留历史 | inconclusive | 缺独占通道真实连接/停止失败/离线与删除回执数据 |
| R9 | S22 接受、拒绝与过期绑定 | J4当前接收账号/链接内存说明 | inconclusive | 缺待绑定Gateway flow；接受/拒绝/过期双端状态未验 |
| R9 | S23 节点配置与状态 | J4改别名保存/重开保持，实际在线心跳；从节点成功创建 | inconclusive | 未切中继/上报以免影响其他正在验的运行；非owner/离线恢复未验 |
| R10 | S24 账号与语言 | J4英文→中文保存成功、返回中文主要界面 | inconclusive | 默认入口和个人资料修改重开、全部错误语言未完整验 |
| R10 | S25 公司准入与停用 | J4实际pending→批准→停用；最后admin确认后明确拒绝 | inconclusive | 主要管理动作通过；普通成员入口、分页、被停用客户端/名下机器后果未验 |
| R10 | S26 策略与附件容量 | J4全部策略字段、保留天数保存31、实际服务容量 | inconclusive | 普通成员只读、失败保留草稿、owner容量分项尚无证据 |
| R11 | S27 前台提醒与返回App | J2 Work时出现不含正文“收到新消息” | inconclusive | 未点击跳转、静音/关闭/历史重放去重/前后台恢复未完成 |
| R11 | S28 不承诺免费后台推送 | J5完整帮助准确说明边界、不声称推送已开启，不申请通知权限 | pass | 以实际帮助与本轮交互所见为限；后台未知消息到达不在承诺内 |
| R12 | S29 首次安装 | 只操作Simulator已装版本 | inconclusive | 按用户安排延后真机/账号/签名；未把unsignedIPA或模拟器冒充免费真机安装 |
| R12 | S30 同网续签与失败恢复 | J5恢复说明完整 | inconclusive | Mini/配对/同网刷新/自然过期实际恢复均未安排；帮助不是实证 |

## 上层文档同步

- [x] `SPEC.md`：此轮不做归并；需 owner 核对最终新增客户端的顶层入口是否需摘要。
- [x] `docs/specs/im/`：仍需最终行为稳定且验收完成后归并 unit delta；本轮不能宣称 current 已完成。
- [x] `AGENTS.md` / `CLAUDE.md`：本次产品验收无需修改。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。
- [x] 安装 runbook：当前只能说明准备/步骤，真实签名及续签证据尚不可写为成功。

报告未 commit，遵循本次 caller 的只写报告授权。未启动额外服务；清理由 caller 负责。

## 续验交接

- 停止 UI 时位置：测试群 `578100`（`c_ptpu3rt7`）附件菜单；最后一次照片坐标点击被 Mac 锁屏拦截，不能断言该次点击已送入 guest。恢复后先获取最新 AX/screenshot，不沿用旧索引。
- 安全 peer 私聊：`c_t6292ein`，标题 578001、Agent e2e-peer；新全局 Agent 私聊：`c_ts2skl8m`，Agent ID 578001/当前显示名578002；图 `tg_457e364c`、节点 n2/n3。后者草稿曾由任务引用变为 `/skill:nanoassistant-docs `，未发送。
- 可用长表单手势：读取当前 AX，找到包含 `Secondary Actions: ... Scroll Down, Scroll Up` 的 container，再执行 `await app.performSecondaryAction(index, 'Scroll Down')`；反向为 `Scroll Up`。整段长说明滚动时 AX文本可能无变化，但截图显示位置变化；不能仅据无diff判断未滚动。普通 `app.scroll` 和触点drag本轮未产生可靠滚动。
- 数字TextField修改用真实click、全选、typeText；不要以setValue的短暂AX变化当作binding已更新。UITextView点击可能改变插入位置，发送前必须核对完整可见草稿；本轮错误提及就是点击后插入位置改变造成，未据此推断产品路由缺陷。禁止paste；不复用或记录此前非验收剪贴板内容。

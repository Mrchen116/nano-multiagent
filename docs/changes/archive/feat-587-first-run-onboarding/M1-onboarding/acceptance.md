# feat-587 — 独立产品验收报告

> Round 1 · full · 2026-10-13
> Validation snapshot: `b70d4a7bd80b → 59650f196`
> Reviewer: independent product reviewer; only this report is edited.

## Verdict

**fail**。实际首次注册、无预装 Node 安装、网页绑定、自定义 API 验证、助手创建及两轮真实模型回复均已完成；原版本存在两项阻塞体验问题，最终冻结版本还需定点复验。

## 版本与环境边界

- Caller 提供 `59650f196` 构建的隔离 IM/Web/release，入口 `http://127.0.0.1:18490`；初次 release 为 `3c2e7c950d13215f96319663324701646dceec44fe12745021846bfbf532524f`。本 reviewer 从注册入口独立创建 `review-new`，未预配模型或助手。
- Playwright 独立会话 `nano587review`。安装根为 `.dsh-runtime/review/computer`，`NANO_INSTALL_AUTOSTART=0`；命令 PATH 仅含 macOS 系统工具，实际自动下载 Node `24.21.0`，而非复用 Homebrew Node。
- 本文截图均为工作树本地 `output/playwright/review-587-*.png`，不提交截图缓存。安装记录位于 `.dsh-runtime/review/installer-retry.log`、`installer-repeat.log`。
- 初次 runtime 解压遭本机磁盘不足；caller 释放本次临时验收资源后，**未删除任何本 reviewer 安装文件**，重跑同一命令成功。该故障属于环境条件；终端明确告知文件保留与重试方法。不能据此推断所有部分解压形态均可恢复。
- 17:12 UTC 左右 caller 通知已更新共享前端构建。reviewer 当前页面仍是 17:08 UTC 加载的原 bundle，随后只做 SPA 导航，所以原页面的离线缺陷仍是基线观察；未用新 bundle 的结果关闭问题。
- 17:14 UTC 后再次运行同一安装命令，实际下载了新 release `20e14034c3ebf7fc6b2f8b62a86463f2d29ff6978d540be207c4be1d2509cc5a`。这一轮不再是指定快照，不能作为 `59650f196` 的安装恢复证明。
- 原生 Codex OAuth 仅执行真实 begin、设备码/官方授权链接展示及取消；没有登录生产第三方账号。符合 design 允许的授权边界。首次聊天使用真实本机代理 `codexOAuth:gpt-6-luna`。

## 用户旅程体验

**首次进入与安装。** 注册后直接显示个人空间和四步向导，没有管理员准入阻断。复制得到的 Agent prompt 包含当前 IM URL、完整 curl/bash 命令、保留文件与配置、网页确认、返回配置模型等操作目标，不含密码或模型密钥，不需要仓库路径。本 reviewer 作为独立本地 Agent 按该材料执行；手动入口呈现相同命令并明确 macOS/Linux、Windows WSL 和无需安装 IM。浏览器绑定 `computer-07d05566` 后，页面自动进入模型选择。

**模型与助手。** 发现的本机代理明确标为待验证；原生 Codex 授权显示真实 code/link 并可取消。自定义 API 故意填写 `127.0.0.1:1` 后失败，中文与英文提示均解释检查地址、模型或 Key，继续按钮禁用，绑定保留。修正为 `http://127.0.0.1:4000/v1`、模型 `codexOAuth:gpt-6-luna` 后真实验证通过，进入用途页；返回后 Key 为空。用途切换为研究伙伴时目标随之改变，名称仅改为“验收研究助手”，创建前明确显示真实电脑和独立 workspace。缺陷 #1 出现在返回模型页再次使用发现代理时。

**首次完成。** 创建 `assistant-5cb23157` 后，研究用途建议以草稿交接到 `c_o9svq57y`，没有自动冒充回复。手动发送“比较两种笔记方法”请求，收到完整三步研究计划；继续追问单人研究，收到相应调整建议。重新登录后原助手、会话和两轮回复都保留，没有创建第二个助手。聊天可进入 Agent 管理及 Work。

**离线恢复。** 创建前停止本安装目录下节点，刷新显示电脑 Offline 与重跑同一命令的修复说明；重跑恢复相同配置、已验证模型与候选助手 ID，自动回到定义助手。创建后再停节点，聊天确实显示 offline，但从“Set up your assistant”进入原向导仍宣称助手 ready，缺少恢复命令（缺陷 #2）。

**团队与隔离。** 新用户主动申请后显示等待批准，并可继续个人设置和完成私人助手。批准前新聊天联系人为空。管理员仅看到已申请者和既有团队成员；批准后 `review-new` 的助手目录是个人助手 + 团队资料助手。管理员、旧团队成员仍只看见团队资料助手；另一个私人账号 `review-private` 助手目录为空。旧管理员和旧成员登录均直接进入聊天。没有向其他人发消息。

**视觉和交互。** 1280×900、768×1024、390×844 已查看安装、模型失败/OAuth、助手表单及聊天代表画面。浅灰背景、白卡片、青绿主要动作延续认证基线；桌面左侧步骤、窄屏顶部步骤均能辨认当前进度。长命令和实际长 workspace 路径换行，控件不横溢，表单纵向滚动可达。英文窄屏品牌出现两行，但不阻碍内容与操作。主要问题是状态真实度与恢复引导，而非排版。

## Reference Artifacts Reviewed

读取 spec、design 与 current auth-tenancy 契约、共同体验标准；另通过独立静态服务渲染 `prototype.html`，查看安装→模型→助手连续状态。原型截图 `review-587-reference-{install,model,assistant}.png` 与真实产品区分保存。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype 四步层级 | 清楚位置、下一步、恢复，无聊天侧栏干扰 | install-desktop / install-tablet / install-narrow | 1280/768/390，安装 | 层级 match；创建后离线恢复 deviation #2 |
| 两种安装选择 | 同目标、复制反馈、长文本可读、真实执行 | install-desktop / install-narrow / offline-before；两次 installer 日志 | 默认、复制、窄屏、离线 | 安装与创建前恢复 match；创建后 deviation #2 |
| 模型来源、验证与错误 | 发现不等于验证、可操作恢复、Key 不回显 | oauth-narrow / api-error-narrow / api-error-tablet；模型返回状态 | OAuth、API失败与成功返回 | 基本 match；重复发现连接 deviation #1 |
| 团队申请 | pending 可继续私人使用，批准不公开私人历史 | team-pending / team-approved / admin-private-hidden / colleague-agents / approved-union | 390 pending、1280批准/目录 | 已观察目录与聊天隔离 match；对象级私人 Work/任务矩阵仍需补验 |
| 用途与少量输入 | 默认目标、名称、电脑与真实路径，无进阶阻断 | assistant-desktop / assistant-narrow | 1280/390，研究用途 | 正常创建 match；创建失败重试状态未实测 |
| 首次真实聊天 | 草稿与回复区分、可继续、重进不重建 | first-reply-narrow / first-reply-desktop / chat-after-reentry | 390/1280，真实两轮对话 | 真实回复与重进 match；重进状态旁出现 failed 需解释，见观察 #3 |

## 问题清单

| # | 严重度 | 实际现象与用户代价 | 处置 |
|---|---|---|---|
| 1 | major | 自定义 API 已成功连接 gpt-6-luna → 返回模型 → 返回发现连接 → 选同一代理模型 → Connect and test，两次均立即出现“Connection failed… check sign-in/URL/model/key”，同时上方显示该模型已连接。用户被要求修复本来可用的连接，发现入口没有兑现可验证使用结果。 | 在冻结版本上复验已连接复用；不得用 API 成功替代发现入口通过。基线快照 `.playwright-cli/page-2026-10-12T17-03-31-872Z.yml`。 |
| 2 | major | 已创建助手后停止电脑，从聊天的 Set up your assistant 进入 /onboarding，电脑/模型全部打勾并显示“验收研究助手 is ready”，只给开始任务，未显示离线和重连命令。用户无法从首次向导恢复工作电脑。 | `review-587-offline-after-original.png`；冻结修复后重验离线→重跑安装→同助手同聊天恢复。 |
| 3 | 待核实 | 重新进入私人聊天，首条已获得真实完整回复的用户消息旁出现字面量 `failed`；第二条追问也已实际获得回复。此前首答截图未显示 failed。 | `review-587-chat-after-reentry.png`。需确认失败属于什么结果，并给出用户可理解的状态；本 reviewer 未读实现或推断根因，不独立归类为模型未回复。 |

## 验收标准覆盖

以下证据名均在本地 `output/playwright/review-587-` 下；Scenario 来源统一为本 unit `spec.md`，原型约束来源 `design.md` 原型对齐契约。

### Requirement: 个人注册立即可用并与现有团队隔离 — 组内结论：inconclusive

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S1 新用户拥有独立空间 | 真实注册、个人向导、批准前联系人为空；另一私人账号助手为空 | install-desktop、private-contacts、other-private-empty | inconclusive | 注册与已观察目录通过；没有专门创建私人任务并验证对象级 Work/任务读取矩阵，不能扩大为空间全部数据面验收。 |
| S2 团队加入需批准 | 主动申请→pending→继续个人使用→独立管理员批准→新用户看到团队Agent；旧成员保留目录 | team-pending、team-approved、approved-union、colleague-agents、admin-private-hidden | pass | 私人助手和聊天未自动公开；不声称已覆盖未创建的私人任务。 |

### Requirement: 页面提供两条真实可执行的安装路径 — 组内结论：fail

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S3 交给本地 Agent 安装 | 读取实际剪贴板 prompt，由本独立 reviewer 执行同一命令 | install-desktop；installer-retry.log | pass | prompt 自足，不含凭据和仓库路径。 |
| S4 手动安装 | 系统 PATH 无 Node，页面命令实际下载 Node/依赖、网页绑定、启动节点 | installer-retry.log；模型步骤真实电脑 | pass | macOS 实测；Linux/WSL为页面支持说明，未伪称跨OS实机验收。 |
| S5 安装恢复与电脑掉线 | 磁盘故障同命令恢复；创建前停止/重跑；创建后离线进入向导 | offline-before、offline-after-original；installer-repeat.log | fail | 创建前通过，创建后缺恢复入口 #2；最后重复安装被分发版本变化污染，不归基线。 |

### Requirement: 模型接入在页面完成并验证真实可用性 — 组内结论：fail

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S6 复用已有本机连接 | 发现代理、选 gpt-6-luna 点击测试；另原生 OAuth begin/code/link/cancel | oauth-narrow；17:03模型错误快照 | fail | API成功后发现入口重复连接失败 #1。未进行真人第三方登录，遵照 design允许边界。 |
| S7 使用 API | 自定义协议、地址、模型，测试成功后创建助手并真实聊天，返回检查Key空 | api-error-tablet、assistant-desktop、first-reply-desktop | pass | 使用免密本地代理路径；失败实验使用非秘密测试字符串，无真实Key泄漏。 |
| S8 连接不可用 | 错误loopback端口/模型→失败、继续禁用→修正成功；切中英文；OAuth取消 | api-error-narrow、api-error-tablet、oauth-narrow | pass | 当前错误提示可行动，绑定保留；未伪称验证所有第三方过期token。 |

### Requirement: 有指导地创建首个助手 — 组内结论：pass

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S9 用少量输入定义助手 | 用途切换、名称输入、默认目标和真实电脑路径、实际创建 | assistant-desktop、assistant-narrow | pass | 正常旅程通过；must-match创建失败状态仍缺实际故障证据。 |
| S10 完成第一件事 | 建立真实聊天，编辑起步草稿，发送研究任务与追问，看到对应真实回复 | first-reply-narrow、first-reply-desktop、chat-after-reentry | pass | 两轮均有真实文本；观察 #3的后续failed标志不应被当作未收到回复。 |

### Requirement: 引导连续、可恢复且与已有体验一致 — 组内结论：fail

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S11 刷新恢复 | 创建前刷新、节点重跑恢复已配模型；创建后重新登录恢复唯一助手/原会话 | offline-before、approved-union、chat-after-reentry | fail | 正常重进保留资源，但已有助手离线时仍误报ready #2；新产物上的刷新需冻结复验。 |
| S12 已有用户与窄屏 | 旧admin/colleague登录直接聊天；1280/768/390安装、OAuth、API错误、助手及聊天 | install-*、api-error-*、assistant-*、first-reply-*、colleague-agents | pass | 中英文规则和失败反馈可用，无横向溢出。 |

## 定点复验范围

1. 冻结新的 validated_at，确认 IM/Web/installer/release 一致后，复验 #1、#2与S5/S6/S11。
2. 补充私人任务、Work对象读取的隔离矩阵（S1），以及创建失败后重试的真实界面证据。
3. 澄清首答后 `failed` 标志的真实结果语义；若仍可复现，纳入相应修复和复验。
4. 完整视频由 caller 独立制作，本报告未把视频存在当作证据。

## 上层文档同步

- [x] `SPEC.md`：需要由 caller核对个人空间与统一授权职责增量；本 reviewer不改架构文档。
- [x] `docs/specs/<包>/`：需要更新。当前 auth-tenancy 仍写注册等待公司批准；本unit已有delta，交付前须由caller归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新，既有边界与验收隔离规则仍适用。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，本unit未改文档体系。

## 环境收尾

混合版本的最后安装终态为 `Gateway startup timed out`，随后提示 `Installation paused. Your files are preserved. Run the same command to continue.`，原日志 `.dsh-runtime/review/installer-repeat-after-assistant.log` 保留。只读进程检查没有本reviewer安装根下的剩余Node进程；保留安装目录、用户数据和截图供R2使用，不删除、不改用户资源。原型静态服务由reviewer停止；caller持有的18490 IM未操作。

---

# Round 2 · targeted · 2026-10-13

> validated_at: `00dd42398d4b9ec9baf0e136d786299659cf8cd3`；本轮范围 `59650f196..00dd42398`，累计基线 `b70d4a7bd80b4424fea430e507390c5dde7c0a05`。

## Verdict

**fail：1 项新增 major 阻塞。** 本轮关闭重复模型连接与已创建助手重新进入时的离线恢复问题，并补齐任务/Work 隔离和创建失败重试证据；但私人助手拒绝正常私人任务保存，错误地告诉用户 task_graph 是公司共享资源。后端隔离通过不能代替这个实际用户旅程通过。

## 冻结环境与真实操作

- 沿用隔离 IM/Web `18490`、R1 测试账号与原数据；核对指定 HEAD 及 installer manifest release `ed0edc04dc32670eef31068d2249c37569e0d3cf2750f69d4318f6033f59a0ad`。本轮未修改实现、配置或生产服务。
- 在原安装根重跑同一安装命令，成功启动已绑定电脑、恢复原助手和原会话；再以 `review-private`、独立安装根 `.dsh-runtime/review/computer-r2` 完成新电脑绑定、发现本机模型测试及助手创建。安装日志 `.dsh-runtime/review/installer-r2.log`、`installer-r2-fresh.log`。
- 新助手创建时，浏览器仅对实际创建 POST 注入 connectionfailed 网络故障；真实界面显示 Check and retry，保留名称、用途目标和路径。撤销路由故障后点击重试，真实服务创建 `assistant-245ccec4`，目录只有该助手。没有伪造成功响应。390px 窄屏截图已检查错误与恢复状态。
- 用本人真实私人会话请求保存笔记对比任务，助手先声称任务图公司共享而拒绝。进一步明确允许保存这份不含敏感信息的验收草稿后，真实创建任务 `tg_fd82a621`。仅测试资源写入，没有向其他用户发消息。

## 前轮问题复验与新增问题

| 问题 | 实际证据 | 判定 |
|---|---|---|
| R1 #1 重复模型连接 | 新电脑发现 `codexOAuth:gpt-6-luna`、Connect and test 成功；返回显示 Already connected、连接动作禁用、Continue 可用 | closed；`review-587-r2-model-reuse.png` |
| R1 #2 已有助手重新进入误报 ready | 原电脑离线时重新打开向导，出现 offline 与安装恢复入口；同安装根重跑后自动恢复同一助手，原聊天保留 | 本轮实测的重新进入路径 closed；不外推为页面持续打开时掉线已验证 |
| R1 #3 已回复后 failed | 本人从 Agents → Work 展开原执行，实际先有成功 send_message，再有 502 upstream_empty_stream；第二次执行完成 | clarified；真实上游失败，不能归类为虚构回复或丢失回复；`review-587-r2-owner-work.png` |
| R2 #4 major：私人保存任务被拒绝 | 正常要求把研究计划保存为私人任务时，助手称 task_graph 是公司共享资源、无法保证私人；改用普通保存请求仍出现 AutoDenied，要求先确认写入公司共享任务图。只有明确允许保存非敏感验收草稿才成功。 | **blocking**。新用户的私人空间内不能顺畅保存个人任务，且会被误导认为私人内容会公开；`review-587-r2-private-task-refusal.png`、`review-587-r2-task-denied.png` |

## Scenario 与 must-match 覆盖

Scenario 来源仍为本 unit `spec.md`；未受改动影响的项引用 R1 连续真实旅程，未重复无关操作。

| Scenario | 本轮证据与范围 | 结果 |
|---|---|---|
| S1 独立私人空间 | 本人可读 `tg_fd82a621` 及私人助手 Work；另一私人账号与既有团队成员直接打开该任务均显示无访问权限，打开私人 Work 均无法加载该助手。批准加入团队的 owner 仍拥有私人任务。隔离矩阵通过，但私人任务保存实际被错误共享语义阻断，见 #4 | fail |
| S2 团队批准 | 沿用 R1 申请、pending、批准及批准后的目录并集；本轮追加批准后私人任务/Work 对团队成员不可读 | pass |
| S3 Agent 安装 | 沿用 R1 剪贴板 prompt 实际执行；本轮同命令恢复真实 frozen release | pass |
| S4 手动安装 | 原安装根升级成功；第二根实际安装、网页绑定、启动及模型配置 | pass |
| S5 安装恢复与离线 | 冻结版本上离线重新进入→明确恢复→同根重跑→恢复原助手和历史，日志与界面一致；持续停留页面的掉线状态不在本轮观察范围 | pass |
| S6 复用本机连接 | 新电脑真实发现→测试成功→返回已连接复用 | pass |
| S7 自定义 API | 沿用 R1 真实 API 成功与 Key 不回显；本轮升级保留该配置及原助手 | pass |
| S8 不可用连接 | 沿用 R1 错误地址失败、禁用继续、修正成功与 OAuth 取消 | pass |
| S9 少量输入创建 | 第二账号真实创建；注入实际网络失败后字段保留、可重试、最终成功且无重复助手 | pass |
| S10 完成第一件事 | R1 两轮真实研究回复保留；本轮进一步保存为私人任务时遇到 #4，不能完整完成私人任务目标 | fail |
| S11 刷新与恢复 | 原助手、模型、聊天在 frozen release 重装后保留；新助手失败后成功恢复 | pass |
| S12 既有用户与窄屏 | 沿用 R1 desktop/tablet/mobile 与旧成员直入聊天；本轮 390px 创建失败/重试文本和控件可用 | pass |

原型 must-match：本轮新增创建失败与重试画面，保留字段、恢复动作、无重复结果，符合契约；模型已连接复用与重新进入离线恢复符合目标。R1 其余整体布局对照沿用。新增 #4 属于完整个人助手旅程问题，不因原型没有逐条画出而忽略。

截图主要位于本地 `output/playwright/review-587-r2-*.png`；最终另一私人账号任务拒绝证据为 `.playwright-cli/review-587-r2-private-task-denied.png`。矩阵截图包括 owner-task、owner-work、private-work-denied、team-work-denied、team-task-denied；创建截图 create-error-narrow、create-recovered。截图与 runtime 文件不提交。

## 后续与收尾

需在新的冻结版本复验 #4：本人正常保存私人任务无需同意公司共享，实际保存成功，私人任务对其他账号继续不可读。若 caller 修复持续停留向导时的离线优先级，应同时补验“创建后不刷新、电脑掉线→恢复命令→同助手恢复”。

上层文档同步要求沿用 R1。两个 reviewer 节点均已通过各自安装 CLI stop 返回 STOPPED；保留数据供后续复验。没有停止 caller 的 IM 或录像服务。

---

# Round 3 · targeted · 2026-10-13

> validated_at: `b1a70198cfbe720b7fabcc56e87c84186cc87e10`（源码修复 `07f55e714`）；executed_base: `b70d4a7bd80b4424fea430e507390c5dde7c0a05`。

## Verdict

**fail：1 项新增 major 阻塞（#5）。** R2 #4 私人任务误报公司共享已关闭；同页不刷新掉线恢复也通过。普通请求现在确实保存成功，但助手未把结果送回原聊天，用户只在 Work 才能看到完成文本，S10 首次工作交付仍失败。

## 冻结环境与连续旅程

IM/Web 固定 `18490`，安装版本 `b1a70198cfbe`、release `2190800dd654053c2552ba52357382fa3ed716939b179fddf6a9b10ac0e483a3`。独立 reviewer 在原 `computer-r2` 安装根重跑页面命令，保留 `review-private` 的电脑、模型与 `assistant-245ccec4`。日志 `.dsh-runtime/review/installer-r3.log`、`installer-r3-reconnect.log`。

1. 在已创建助手的 ready 页面保持不刷新，停止该安装根节点；页面自动回到 Connect computer，显示 Offline、重跑命令及身份/文件保留说明。再运行同一安装命令，页面自动恢复“恢复验证助手 is ready”，同一个助手继续进入会话 `c_rprqeogj`。1280×900 实际截图已目视核对，恢复动作明确可达。
2. 在该助手尚无历史消息的新会话正常发送：“请把我的私人学习计划保存成任务，标题是‘私人学习计划-R3’。目标是本周了解两种笔记方法。两步即可：先比较大纲笔记与卡片笔记，再整理适用场景。请直接保存，不必先追问。”没有同意公司共享或提示绕过权限。
3. 任务页真实出现 `tg_021a12df`，owner 为 `assistant-245ccec4`，Revision 2，包含所需两步及依赖。本人可查看；既有团队成员 `review-colleague` 和另一私人助手所有者 `review-new` 直接访问相同任务 URL 均被拒绝。
4. 返回原聊天后没有助手消息。独立进入该助手 Work，执行已于 01:39:05 完成：4 次工具调用只有 inbox 两次、task_graph 两次；Agent response 为“已保存任务图「私人学习计划-R3」，包含两步：先比较大纲笔记与卡片笔记，再整理适用场景。”没有 send_message 调用。该文本不能当作已送达聊天的回复。

## 问题与覆盖变化

| 项目 | 结果 | 证据与影响 |
|---|---|---|
| R2 #4 / S1 私人任务保存 | closed / pass | 普通私人保存请求直接成功，未再声称公司共享；本人可读且两名其他账号不可读。 |
| S5 / S11 同页掉线与恢复 | pass | 全过程无刷新或重新导航：ready → Offline + 命令 → 同助手 ready。 |
| 新 #5 / S10 真实结果交付 | **major / fail** | 任务成功而原聊天无结果；Work 已完成且有最终文本，但没有消息送达。用户从聊天发起后无法获知完成，需要自行翻查 Tasks / Work。Caller确认这是本unit首用交付阻塞。 |
| S2–S4、S6–S9、S12 | pass（沿用） | R1/R2 未受本轮修复影响的真实证据继续有效；不重复无关矩阵。 |

本轮截图均在本地 `output/playwright/review-587-r3-*.png`：`live-offline`、`live-recovered`、`private-task-saved`、`work-undelivered`、`team-denied`、`other-owner-denied`。聊天未交付通过返回 `c_rprqeogj` 的实际 snapshot 核对；展开的 Work snapshot 保存在 `.playwright-cli/page-2026-10-12T17-41-13-439Z.yml`。以工具调用与界面实况为准，不读取实现解释根因。

上层文档同步要求沿用 R1。下一轮只需普通私人任务请求→真实保存→结果回到原聊天的闭环，不用用户额外指定 send_message。reviewer 的 `computer-r2` 节点已 stop 返回 STOPPED；原 `computer` 节点本轮未启动。IM 与数据留给 caller。

---

# Round 4 · targeted · 2026-10-13

> validated_at: `f881314a469e97178cd91e59a308c0d3625404d9`；executed_base: `b70d4a7bd80b4424fea430e507390c5dde7c0a05`。

## Verdict

**pass，0 项未关闭阻塞。** R3 #5 已通过真实原聊天交付复验；结合前三轮保留证据，S1–S12 全部 pass。本轮只重验私人任务保存到原聊天交付，不把前轮结果伪称为本轮重新执行。

## 冻结版本与实测结果

- 固定 IM/Web `18490`，未重启 IM。原安装根 `computer-r2` 重跑同一安装命令，实际运行 release `17b2d8891d7df680c855a7ded017fa756336535ce447d19d70855decf89aa308` 的 CLI；进程 command 核对一致，日志 `.dsh-runtime/review/installer-r4.log`。
- `review-private` 在原会话 `c_rprqeogj` 向同一个 `assistant-245ccec4` 普通请求保存“周末阅读计划-R4”，目标周末读完一篇技术文章，分阅读并摘录重点、写一段总结两步；未要求使用 send_message，未加入额外共享授权。
- **原聊天实际收到助手消息**：“已保存「周末阅读计划-R4」，目标是周末读完一篇技术文章，分为两步：先阅读并摘录重点，再写一段总结。”消息显示助手身份、01:45 时间及 View Work 链接；不是输入框草稿或 Work 文本。
- 再从真实 Tasks 入口核对 `tg_6bd77847`：标题、目标、两步及先后依赖一致，Revision 2，owner `assistant-245ccec4`。R3 任务也保留。`output/playwright/review-587-r4-chat-delivered.png` 与 `review-587-r4-task-saved.png` 已目视核对，1280×900 下聊天结果与任务结构清楚可读。

## 最终 retained coverage

| Scenario | 最终结果 | 实际来源 |
|---|---|---|
| S1 私人空间 | pass | R1注册/目录；R2私人Work及任务对象矩阵；R3正常私人保存且其他账号不可读 |
| S2 团队批准 | pass | R1 pending→批准→目录并集，R2/R3批准不公开私人任务/Work |
| S3 Agent安装 | pass | R1剪贴板prompt真实执行，R2–R4同命令真实升级 |
| S4 手动安装 | pass | R1无预装Node实际安装，R2新根安装及网页绑定 |
| S5 安装恢复与离线 | pass | R1部分安装/创建前恢复，R2冻结版本恢复，R3同页掉线→重跑→同助手 |
| S6 已有模型复用 | pass | R2发现连接实测成功，返回已连接且可继续 |
| S7 API配置 | pass | R1真实API验证/聊天、Key不回显，R2升级保留 |
| S8 不可用连接 | pass | R1失败提示、禁止继续、修正恢复、OAuth取消 |
| S9 少量输入创建 | pass | R1用途/默认值/真实创建，R2真实网络失败保留字段后重试成功且不重复 |
| S10 完成第一件事 | pass | R1真实研究回复及追问；R4普通私人任务请求→实际任务→原聊天收到结果 |
| S11 刷新与恢复 | pass | R1/R2重进保留助手/模型/会话，R3持续页面真实离线恢复 |
| S12 旧用户与窄屏 | pass | R1旧用户直接聊天、1280/768/390中英文代表状态，R2窄屏创建失败/恢复 |

R1–R3 must-match 原型对照和创建失败证据保留，未受本轮通信提示修改影响。R1 #1/#2、R2 #4、R3 #5 均关闭；R1 #3 已明确为真实上游执行失败，未当作无回复证据。上层文档同步责任沿用 R1，由 caller 收口。

reviewer 节点已通过本轮 release CLI stop，返回 STOPPED；另一个 reviewer 节点未启动。保留 IM、账号、任务、会话与截图供 caller 收尾；只提交本报告，不改实现、不 push。

---

# Round 5 · feat-588 集成后 targeted 复验 · 2026-10-13

> validated_at: `77622d2152fe7e1bb2966fb656adf9e41613aed6`；实际候选包版本 `0247eb0e610bbf366f37b34f41015430cdaff8f7`。两者经 `git rev-parse <revision>^{tree}` 独立核对均为 `85a9120442e4b5a7ed2df13360d77bf9da90558f`。执行时间约 13:12–13:25 Asia/Shanghai。

## Verdict

**pass。0 blocking、0 major、0 新增 minor 实现问题；保留 1 项非阻塞运行观察。** 新个人注册→电脑安装/绑定→API 错误恢复与成功→指导创建→原聊天真实首答→日常编辑与继续对话→刷新/重新登录→掉线重装恢复均已真实完成。S1–S12 按下表完成对账；旧 S6 的开发者代理发现已被用户明确修改的 feat-588 API 优先需求取代，**没有把旧发现路径报成集成后仍需或已经通过的行为**。

该结论允许 caller 用另一全新身份录制新版中文新手流程；不表示视频已录制、PR 已合并 main、公开 Release 已发布或生产已部署。

## 环境、范围与证据边界

- 当前工作树 `/Users/czj/.codex/worktrees/feat-588-model-services/nano-multiagent`、branch `codex/feat-587-final-review`。开工 HEAD 为 validated_at，仅原有 `.runtime/`、`output/` 未跟踪内容，未改动。执行期间 caller 新增 `22aa42c62` 的文档校正但未重建/重启运行栈；不把后续文档 HEAD 冒称另一次产品验收。
- 先读 caller 的 `.dsh-runtime/feat587-integrated/README.txt`、587/588 spec、588 修订 design/原型对齐契约、current IM/Gateway 模型契约及共同体验标准。复用的是前轮独立验收证据，非 worker 成功叙述。
- 独立全新 IM `18495`；真实推理测试 API `18496`；本轮从真实注册页创建 `review-integrated` / 集成验收用户，绑定 `computer-bee36202`，创建唯一 `assistant-ad93eb60` / 我的阅读伙伴，会话 `c_5fgupv3r`。没有访问用户试用端口 52267、生产、旧验收 18490 或修改 LLM_PROXY。
- 原样执行页面复制命令，安装根严格为 `.dsh-runtime/feat587-integrated/review/computer`、AUTOSTART=0；PATH 仅运输 fixture 和系统工具，实际自动下载 Node、安装依赖、网页绑定并启动节点。manifest 固定 GitHub URL、版本及 SHA256 `872603f98a3031aef8102fe5a52024f7e066cfc81cec74a6ace75dfa35220291`。精确 asset URL 由 caller 运输 fixture 供给候选字节；这是安装生命周期与校验的真实执行，**不是公开 GitHub Release / 匿名下载验收**。
- 内置 `deepseek` 目录来自实际运行时；为测试将可选地址覆盖为 `18496/v1`，使用隔离测试 Key 和 `deepseek-chat` 别名，经 4000 转发真实推理。**不是真人 DeepSeek 云账号认证**。自定义服务同样使用隔离 API，未读取真实用户凭据。
- 截图根 `E = output/playwright/review587-integrated/`；安装日志 `R = .dsh-runtime/feat587-integrated/review/` 下 `install.log`、`reinstall.log`。截图、日志、配置、凭据和数据库均不提交。

## 连续真实旅程

1. **注册与安装。** 中文注册直接进入个人空间，无等待审批。分别点击“复制安装说明”和“复制安装命令”，实际剪贴板含当前 IM、完整命令与保留配置/网页绑定目标，不含账号或模型凭据、仓库路径。手动终端执行命令后，网页明确显示接收账号与电脑名，点击确认；节点上线后进入模型步骤。桌面和390px下命令可换行、复制状态可辨，安装位置/WSL说明可读。证据 `install-agent-1280.png`、`install-manual-390.png`、`install-command-390.png`。
2. **API 优先与失败恢复。** 模型页初始即内置服务商/API 表单，真实目录有约40个选项，订阅授权位于次要折叠区；无开发者代理发现结果。选 `deepseek`、名称“阅读研究 API”、模型 `deepseek-chat` / “日常研究模型”，先填错误 Key。实际失败反馈紧贴提交区，名称/模型/绑定保留，“继续”禁用。只修正测试 Key 后真实验证成功，才可继续。证据 `model-api-1280.png`、`model-error-390.png`、`model-ready-390.png`、`model-ready-768.png`。
3. **定义与首次工作。** 从日常用途切到资料研究，默认目标随之成为有来源的研究结论；只改名“我的阅读伙伴”，模型显示服务归属，真实电脑和独立 workspace 清楚可见。创建后建议是输入框草稿，尚无消息。改写为比较大纲笔记/卡片笔记的三步任务并发送，原聊天收到对应三步回复，链接可进入 Work；不是预置答复。证据 `assistant-guidance-390.png`、`first-reply-390.png`、`first-reply-1440.png`。
4. **日常模型管理。** 通过桌面头像菜单的“模型服务”进入，原电脑与服务可辨，无需重走引导。编辑时电脑/厂商不可切换，API Key 为空且说明留空保留。改名“阅读研究 API · 更新后”并轮换测试 Key，真实测试保存成功。再通过自定义 API 入口配置地址、Chat Completions、Key、`nano-demo-model` / 备用阅读模型，真实保存成功。列表按服务名→类型→模型组织，两项服务的编辑/移除动作在手机保持同行。证据 `custom-editor-1440.png`、`custom-editor-390.png`、`services-{1440,768,390}.png`。
5. **同助手继续。** 返回原会话追问每周半小时应如何选择，原助手真实回复两句建议。第二轮 Work 最终明确“已完成”，不是收到气泡就假定整轮完成。原助手未重建、原聊天未换，证据 `reply-after-edit.png`、`work-final-states.png`。
6. **重进、掉线与恢复。** 退出登录后，旧团队账号 `review-colleague` 正常直入聊天；再登录新账号并刷新原聊天，两轮内容仍在。进入已创建助手的向导，停本轮安装节点，同页不刷新自动显示暂时离线及重跑命令。日常模型页显示离线/恢复说明与“查看连接指引”，添加禁用而非误报空配置。按指引重跑同一安装命令，恢复同电脑/助手，刷新仍 ready；目录只有原助手。重开模型编辑，名称、只读 deepseek、模型 ID 保留，Key 不回显；两项服务均保留。证据 `chat-after-reentry.png`、`onboarding-offline.png`、`models-offline-390.png`、`onboarding-recovered-390.png`、`services-after-restart-en-390.png`。

## 视觉、交互及 must-match 对照

判断来自真实截图与连续操作；没有以 DOM 存在、接口成功或无横向溢出替代体验结论。

| 设计契约 | 本轮实际画面/状态 | 结论 |
|---|---|---|
| 587集中向导层级、当前步骤/唯一下一步、真实安装与恢复 | 1280安装、768模型成功、390安装/错误/助手/恢复 | match；步骤与卡片层级连续，长命令/路径可纵向阅读，恢复不要求重建 |
| 588紧凑电脑上下文、服务名称主层/类型模型次层、手机动作同行 | 1440/768/390两服务列表及390英文重启后列表 | match；日常页没有套用首次引导的大说明区，主操作与归属可直接辨认 |
| 588单一编辑区、连接/模型分组、提交自然在表单内 | 1440自定义编辑、390错误与自定义编辑、原服务重开 | match；窄屏单列、字段标签明确，滚动成本合理，按钮不遮字段；已存厂商只读、凭据不回显 |
| 588API反馈贴近表单、授权次要且局部、恢复动作可辨认 | 错Key→修正成功、离线模型页→连接指引 | match；失败不跳过模型，草稿保留；订阅完整授权矩阵保留588独立证据，本轮不伪称真人登录 |

手机证据是390×844真实浏览器客户端宽度，不是物理手机或原生iOS。新手页面有较多纵向内容，但安装/模型/助手各阶段主动作与实际结果清楚，未发现集成带来的阅读、操作或一致性阻塞。

## 非阻塞运行观察：首答已送达后的上游失败

首轮用户消息回看带“失败”。本轮独立查看 Work：13:17:27–13:18:13、3次工具，`send_message` 已调用完成并将完整三步答复送达原聊天，随后模型返回 `502 upstream_empty_stream`；这轮最终是失败，不能写为 completed。第二次追问 13:20:24–13:21:17 最终明确已完成，原聊天两轮回复在重新登录/刷新后均保留。证据 `upstream-after-delivery.png`、`work-final-states.png`、`chat-after-reentry.png`。

对用户的影响是已获得答复的请求旁仍出现整轮失败，需进入 Work 了解后续失败；没有丢失答复、阻断继续对话或破坏模型设置。本次确认的触发与既有587 R1 #3/588运行观察同类，但判定依据是本轮先送达、后上游失败及下一轮成功的实际证据，不是因为历史有记录就忽略。按S10“真实回复到达、可继续并进入管理”的既定验收目标，不将其判为本集成新增阻塞；保留作为运行限制，不保证下一次录像上游绝不失败。

## S1–S12 最终覆盖对账

| 587 Scenario | 结论 | 本轮与 retained 来源 |
|---|---|---|
| S1 个人独立空间 | pass | 本轮全新注册/绑定/唯一私人助手；587 R2/R3私人Task/Work对象级隔离矩阵retained，588模型跨owner矩阵retained，无需机械重跑未改权限面 |
| S2 团队加入需批准 | pass / retained | 587 R1申请pending→批准→目录并集、R2/R3私人内容不公开；本轮旧团队账号仍直入聊天 |
| S3 Agent安装prompt | pass | 本轮实际剪贴板核对当前IM、完整目标、保留文件、无凭据/仓库要求；手动与Agent使用同安装器 |
| S4 手动安装 | pass（运输边界如上） | 本轮系统PATH自动准备Node/依赖、浏览器绑定和启动；macOS实测，不外推所有OS或匿名公网Release |
| S5 安装/掉线恢复 | pass | 本轮真实stop、同页离线、管理页恢复入口、原命令重装同电脑同助手；下载/校验负向矩阵保留588 S9 |
| S6 旧开发者发现路径 | not-applicable / superseded | 588用户原话和spec澄清明确API优先、开发者代理仅可选自定义；替代契约588 S1/S3与current首次API接入在本轮pass。订阅可选路径保留前轮，不宣称旧自动发现仍应存在 |
| S7 API接入 | pass | 本轮内置目录、自定义API、真实Key测试、首回复、编辑轮换、密钥不回显和同助手继续 |
| S8 不可用连接 | pass | 本轮错误Key→可行动反馈/继续禁用/草稿绑定保留→修正成功；588取消/冲突/原连接保护retained |
| S9 指导首助手 | pass | 本轮用途默认目标、名称、模型服务、真实电脑/workspace与创建；587 R2创建网络失败重试不重复retained |
| S10 第一件事 | pass | 本轮原聊天真实首答与追问，管理入口可达，第二轮最终completed；私人任务普通保存→原聊天完成消息沿用587 R4 |
| S11 刷新重进 | pass | 本轮退出/重登/刷新、同根重装后唯一助手与聊天/服务保留 |
| S12 旧用户与窄屏 | pass | 本轮旧团队用户直入聊天；1280/1440、768、390实际看图，中英文列表及错误恢复可用；其他未改语言状态retained |

588完整多模型同名区分、依赖移除、取消、并发revision、空Key保留及owner矩阵，以其独立 `M1/acceptance.md` R1/R2最终pass证据为retained；本輪没有发现需推翻这些结果的新副作用。587原must-match中被588改写的模型区以上述新契约为准，其余前轮证据保留。

## 收尾与文档

只追加本587归档报告，不改源码、配置、设计或588报告，不push。已恢复中文并关闭本轮独立浏览器；按caller明确要求保留安装节点（恢复后PID 66428）、IM/API、数据与现场，交caller统一清理；没有停止共享服务。当前current specs已体现API优先及常驻管理，caller另做安装文档校正，不在本报告复制长期事实。新版交付视频由caller另用全新身份录制，止于首个真实回复，不追加刷新章节；merge main仍未执行。

---

# Round 6 · main 合流后空间与任务 targeted 复验 · 2026-10-13

> validated_at: `ad0b096f9f8b2093bd59fa3839a44a5cb326ca7d`；执行约 17:58–18:09 Asia/Shanghai。调用方确认 IM 与前端来自本 checkout 的冻结构建；reviewer 开工独立核对 HEAD。后续修复不算本轮已验版本。

## Verdict

**fail：1 项 major（#6），1 项 minor（#7）。** 私人任务保存、私人/公司权限隔离、批准不公开既有私人内容、公开群访客读取与加入后协作均通过。含私人助手的建群流程仍承诺“公司内公开”，保存却变成不可切换的私密群，范围选择不能可靠表达用户决定；需修复后 targeted 复验。

## 环境与范围

- checkout `/Users/czj/.codex/worktrees/pr337-main-sync/nano-multiagent`，branch `codex/pr337-main-sync`；仅追加本报告，保留开工时既有 code-review.md / verification.md 修改与 `.review-private/`。没有提交、push、读实现定位原因或停止共享服务。
- 仅使用独立 `http://127.0.0.1:52335`，通过 CUA 后台 IAB 操作真实 Web；Chrome 连接不可用后切换，不使用生产与原试用 62307。桌面 1280×900、窄屏 390×844；不是物理手机或原生 iOS。
- 测试身份：`pr337private`（私人验收用户）与 `nano`（Test User）。调用方最初称 nano 是 legacy 公司用户，随后核实其实际是个人空间启用且公司 active；其 E2E Agent 固定在 nano 私人空间。因此本轮**不宣称 legacy 无个人空间账号迁移实测**。
- 私人 Node `pr337-private-node`，Agent `pr337-private-agent` 的 UI 名称实际为 E2E Agent。首次 Agent 保存任务返回 not_found_or_forbidden；调用方核实 fixture 初始 tool_allowlist 为空。依授权在真实 Agent 设置页启用 task_graph/send_message，保存为 profile v2 后原聊天再次请求，真实创建成功。前次失败作为环境前置缺失记录，不据此推断 ACL 缺陷。
- 本地截图根 `output/review587-r6/`，不入 git。所有写入仅这套独立账号、群与任务。

## 连续操作与实际结果

| 目标 / 来源 | 实际证据 | 结果 |
|---|---|---|
| 587 S1；current conversations 私人会话 | 私人目录只见自己的助手；新聊天建立 `c_a9a8nmly`，显示本人、助手及私人 Node；批准后仍能回看原历史 | pass |
| 587 S1/S10；current task-graphs 私人保存 | Web 新建 `tg_4895053a`「私人阅读计划 R6」，私密·仅成员；390 宽度编辑状态为进行中、负责人为本人、记录结果，新增子任务成功；图 revision 与保存内容一致 | pass |
| Agent 普通私人请求保存 | 补齐测试工具配置后请求「私人学习计划 R6B」，实际 `tg_5d9982dc`，两步分别比较方法、整理适用场景；原聊天真实回复“已保存，未执行”，Tasks 可见两节点且归属原私人会话 | pass |
| 587 S2；auth-tenancy 申请与批准 | 账号→团队资格→申请后显示等待批准；nano 公司成员页批准，显示已加入 | pass |
| 587 S1/S2；私人数据不可被公司读取 | nano 在批准前和批准后分别直接访问 `tg_4895053a` 均显示“任务不存在或你已无权访问”；访问 `c_a9a8nmly` 均回聊天空选择，不显示私人历史；批准后私人本人仍见原任务与会话 | pass |
| current conversations 公司公开群读取/加入 | 用两个 active 真人创建 `c_54bgsp30`「公司读书会 R6」；nano 退出后从“发现公开群”进入，能读原消息，明确“只读·加入后可协作”，不可发言且不自动入列表；点击加入后发言成功 | pass |
| current task-graphs 公开可读、加入后写 | `tg_2e273592`「公司笔记分享 R6」：nano 未入组时能读详情但没有编辑/领取；加入后领取，负责人 Test User、状态进行中；编辑结果并提交待确认成功，私人创建者回群看到分配与待确认系统消息、可回原任务 | pass |
| 587 S12 与 current task 体验 | 1280 总览五列按状态区分、任务标题/负责人/所属会话/直属子任务清楚；详情抽屉不挤窄看板；390 单列分组、编辑字段和保存按钮完整可达，保存后详情显示新值；私人和公司任务在本人总览共存 | pass |
| 私人助手群的可见范围决定 | nano 新建群选择自身 E2E Agent，表单仍显示“公司内公开”；保存 `c_vzmt40ab`「阅读协作公开群 R6」后配置却显示私密且禁用范围选择，任务 `tg_eb709c0a` 也显示私密 | **fail / #6 major** |

## 体验裁决与问题

**#6 major：建群可见范围承诺与保存结果不一致。** 选择私人助手后仍可看到公司公开默认值，没有解释该助手固定私人空间；保存后的私密结果无法切换。用户想建立公司可发现的协作入口，却只有保存后进入配置才发现无法实现；这是决定与结果不一致，不是颜色或文案偏好。私人资源不被自动发布的边界应保留，但界面必须在提交前表达真实可用范围。实际对象与步骤见上表，调用方已确认进入修复。

**#7 minor：会话列表的任务系统消息预览暴露原始格式。** 公司任务待确认后，左侧列表预览含 `Test User \\(u\\_hh4oa27i\\)`、Markdown 任务链接与 `<mention type="user" target_id=...`；原群正文正确显示任务链接与 @姓名，点击与任务处理正常。列表的扫读质量下降，但不会阻断本轮读写和访问边界。证据 `private-agent-saved.png` 左侧列表及本轮 CUA snapshot；不把正文正确渲染当作列表也正确。

关键截图：`private-detail-390.png`、`private-edit-390.png`、`private-board-390.png`、`private-agent-saved.png`、`private-agent-task-1280.png`、`company-denied-private-task.png`、`company-denied-after-approval.png`、`public-guest-chat-1280.png`、`public-guest-task-1280.png`、`public-joined-claimed-1280.png`、`company-overview-1280.png`、`mixed-overview-{1280,390}.png`。均通过真实画面目视判断；缩放过渡时的 `private-board-1280.png` 不作为桌面布局依据。

## Retained 与未宣称项

- S3–S5、S7–S9、S11 保留 R5 的安装生命周期、API 接入/编辑、错误恢复、创建助手、重登/掉线恢复具体结论；没有本轮重新安装声明。S6 仍按 R5 为 superseded。
- S10 本轮新增私人任务成功与原聊天结果；R5 普通首答/追问及 R4 私人保存交付历史仍保留。真实公开 Release/匿名下载安装不属于本轮，待发布后独立验收。
- R5 对 587/588 原型 must-match 的安装与模型区对照 retained；本轮只判断受 main 合流影响的会话/空间/任务实际体验，不把旧模型截图当成任务页证据。
- 不外推原生 iOS、所有 OS、真实 Release、生产部署或旧 DB 升级。调用方负责整体门禁与上层文档同步。

保留独立环境与测试数据供修复闭环；本轮没有启动或停止服务。

---

# Round 7 · 私人助手建群范围修复 targeted closure · 2026-10-13

> validated_at: `864d44e281779f06dde7c771ac49d5dbf4e30e96`；执行约 18:10–18:12 Asia/Shanghai。调用方重建并重启本轮 IM 52335、保留原 DB/签名；reviewer 刷新真实客户端后执行。

## Verdict

**pass-with-issues：0 blocking / major，保留 R6 #7 一项 minor。** R6 #6 已关闭；当前受影响私人/公司空间与任务协作组合可交付。R6 的真实私人保存、批准前后隔离与公司公开群读/加入/写矩阵 retained，不重复声明为本轮重跑。

## 实际闭环

1. 私人验收用户进入新建群聊，未选成员时仍可选择公司公开；选 `pr337-private-agent` 后，范围即时变为“私密·仅成员”且不可切换，下方明确“包含私人助手的群聊保留在个人空间，仅成员可见”。桌面 1280×900 与 390×844 已目视核对，说明紧邻决定、群名和创建动作可见，不需保存后猜测范围。
2. 在 390 宽度直接创建「私人阅读群 R7」`c_t4bsv0rn`；进入真实群配置，实际范围为私密·仅成员，与提交前展示一致。
3. 再开建群：先选私人助手、取消，再只选公司成员 Test User，范围恢复可选择；真实切换私密→公司公开后创建「公司阅读群 R7」`c_vx5grxq3`，配置显示公司内公开。未因修复把所有群强制私人化。
4. 真实截图位于 `output/review587-r6/`：`r7-private-scope-1280.png`、`r7-private-scope-390.png`、`r7-private-created-390.png`、`r7-company-created-1280.png`。截图不入 git。R6 的 Agent 原聊天最终回复与实际图 `tg_5d9982dc` 已确认成功，不以 retained 隐去前置缺失后的最终结果。

R6 #7 系统通知在会话列表预览中的原始格式仍可观察；仅局部扫读问题，正文及协作操作正常，保留 minor。R5 安装/模型具体 retained 结论及真实 Release 尚未实测的边界继续适用。只追加报告，未改源码/设计/测试、未 commit/push；浏览器视口已恢复并关闭本轮临时 tab，所有独立服务交由 caller 管理。

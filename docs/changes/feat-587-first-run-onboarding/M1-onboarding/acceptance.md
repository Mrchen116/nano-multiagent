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

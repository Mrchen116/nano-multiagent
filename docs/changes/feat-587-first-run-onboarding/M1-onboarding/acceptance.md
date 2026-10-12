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

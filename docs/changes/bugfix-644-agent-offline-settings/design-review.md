# bugfix-644 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/bugfix644_design_review`（独立 reviewer，未参与受审设计）
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖 incident R1–R11、设计决定、真实组装入口、两份 delta、原型及 M1 骨架。
- started_at: `2026-10-23T22:27:00+08:00`
- completed_at: `2026-10-23T22:36:38+08:00`
- duration: `9m38s`
- 设计声明基线：`59ca15b2a85b56674cffe2b0284d485d14ff79ea`；审查时 main HEAD 为 `1fce5eb1b`，额外提交属于 feat-645 文档。核对上述基线到当前 `apps/im-server/src`、`src/IM/frontend/src`、`src/IM/ios` 无 diff，未修改其他任务内容。
- 只新增本报告；没有修改设计、原型、delta、产品代码或提交 Git。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。Gate 2 本轮未通过。**

后端职责、只读快照与当前操作条件的分离、禁止新离线写入且继续恢复既有操作的方向成立。阻断点是两个直接涉及 must-match 的前端设计证据缺口：配置版本冲突尚缺可供用户判断的实际交互；模型草稿在掉线转换时与保留的强度草稿错误配对。均不要求提前实现真实后端。

### Coverage 与证据

| 范围 | 独立核对与判断 |
|---|---|
| 实际产品入口 | `src/IM/frontend/src/app/router.tsx:64` → `agent-profile-page.tsx:27` → `AgentDetailPage`。详情在 `agent-detail-page.tsx:1272` 挂载真实 query、状态订阅与草稿；`:1690` 起组装插件、渠道等分区，`:1758` 挂载 PA 设置。审查不是仅核测试 mock。 |
| RCA 与核心配置 | `im-agent-config-api.ts:622` 确有失败后从保存值构造候选目录；`model-reasoning-field.tsx:57` 将 descriptor 缺失判为 stale；当前页面还会随新配置整体重置草稿。D2/D3/D5 正面消除这些混淆，而非补一个默认值。 |
| IM 组装与副作用前置 | `apps/im-server/src/server.ts:177` 注册 Control，`:178` 注册 PA；Channels 的真实 HTTP 路由位于 `channels.ts:681`。`control.ts:780` 的 PATCH、`:844` 的插件、`:899` 的 cron，`personal-agent.ts:374–387` 的改名／policy／解除联系人限制，均有明确设计落点。渠道 create/update/delete 当前在 push 前写 desired，故 D4 必须在 service mutation 前 gate；设计已明确这一点。 |
| R1/R2：跨浏览器、默认与未知 | D1 与接口 §1/§2 定义 IM 持久、有限 section、成功空与未取得、时间／来源、绑定 epoch／workspace／profile version 校验；显式配置继续来自 profile。完整模型候选不持久化、不从 IM 文件系统推断。HEARTBEAT／提示词只保留本页内容，跨浏览器未知符合 incident 的非通用文件同步范围。 |
| R3/R4：全页及渠道只读 | D3/D4 和写入边界表覆盖主表单、PA、插件、cron、渠道新增到删除重试及已打开弹窗；阅读、取消、检查连接仍可用。`Gateway.isOnline` 当前只查 Map，`gateway.ts:82` 的 valid 与 socket OPEN 可提供所需真实前置；不必扩大全仓 isOnline 语义。 |
| R5：节点自治与最后状态 | 渠道继续使用 desired/observed、received_at，原型明确区分“已配置为启用”与“最后已知：已连接”；`work.ts:465–476` 确有离线运行态转 unknown 和 node_connection_state。设计不停止本地执行。 |
| R6/R9/R10：草稿与恢复 | base/draft/latest、查询代次与 AbortSignal、恢复先刷新、区域依赖解锁的文字契约完整；`realtime/user-stream/user-stream-runtime.ts` 确有 onRecovery 与 onConnectionStatus 可复用。可交互原型仍存在下述 R1-W1/W2，不能把文字承诺代替关键选择的体验证据。 |
| R7/R8：在途与历史 pending | `ConfigOperations` 确有 serialized、active、recover、receipt/CAS/compensation；渠道已有 manifest/revision/removal。D4 不把这些恢复调用归入新写入；§3 对没有精确 receipt 的插件／cron 不虚构成功。新增 `/settings` 避免旧 `/config` 的 pending 异常遮蔽整页，职责合理。 |
| R11：在线恢复后的正常操作 | 设计保留 live-only 校验、显式保存、原渠道生命周期；M1-U3/W1/W2 覆盖在线正常行为与旧相反测试调整。原型演示不被当作真实生命周期成功证明。 |
| delta-spec | 两份 delta 指向正确 canonical 文件。逐 Requirement 比对 Scenario：除被明确替换的“节点离线仍可保存并在重连后自动应用”外，MODIFIED 均保留原 Scenario；cron 的离线空数组与新渠道离线写入契约确有修改，PA 聊天内风险保护未被设置页 gate 扩大。未提前改 current。 |
| iOS 边界 | 读取 `AgentConfigView.swift` 与 `AgentSkillsView.swift`，旧在线成功 shape 继续兼容，新 cron 错误有现有 catch 路径。按用户范围不要求 iOS 原型／模拟器验收；尚未运行编译或 wire 测试，不能称原生体验通过。需关注下述 R1-R1。 |
| milestone 与前置 | 一个 M1 覆盖整条旅程，`.gitkeep` 未预填实施记录。must-match 均映射 reviewer 用户结果与 worker 证据；runbook 有隔离栈、仅停 Node、恢复、清理、真实 Web 与接口边界测试分工。`e2e-up/down.sh` 可核实独立 config、端口文件、测试账号和 Feishu listener lock。专用渠道凭据可用性采用作者已记录的检查证据，本轮未重复访问秘密或连接 Bot；未来验收须重新核对。 |

**架构判断：** 现有 profile、operation、channel、Work／PA 持久资源继续各自承担权威，新增 `agent-settings.ts` 只隐藏展示投影、绑定隔离和设置写入前置，符合 IM 的产品读取职责；相对复制整个 capability response 或增设后台扫描，有限按需快照足以满足跨浏览器需求，维护成本合理。前端局部 hook 统一状态但按资源解锁，避免统计失败拖住主配置。没有发现扩大 DSH 接入、跨包私有依赖或第二套执行机制的决定。

### 独立画面与交互观察

使用 Playwright CLI 专用 session `bugfix644-r1-review`；真实登录并浏览作者隔离环境 `http://127.0.0.1:53041/settings/agents/e2e`，切到 Channels；原型为 `http://127.0.0.1:53042/prototype.html`。未修改真实产品配置、未停任何共享服务。已关闭本 reviewer 创建的 session（含两个 tab）。

| 观察 | 可复查证据与体验裁决 |
|---|---|
| 当前桌面配置 1440×1000、手机渠道 390×844 | 本轮截图 `/tmp/bugfix644-review-current-desktop.png`、`/tmp/bugfix644-review-current-mobile.png`；与 unit 的 [基线桌面](design-evidence/baseline-desktop.png)、[基线手机](design-evidence/baseline-mobile.png) 一致地保留身份、详情分区、白色卡片及底部操作。原型有精简背景，design 已明确实施不照搬字段删减。 |
| 离线桌面只读 | `/tmp/bugfix644-review-offline-desktop.png`：身份下先出现失联原因与时间，再进入配置；禁用输入正文仍可读，操作原因不依赖猜测灰色含义。 |
| 渠道编辑中掉线 | 在线打开“编辑”，输入“渠道未提交草稿”，再切离线；390×844 实际画面 `/tmp/bugfix644-review-mobile-dialog.png` 保留输入、禁用保存并可取消。背景仍显示已保存渠道名称与最后已知连接，不混为草稿或已停机。 |
| 恢复刷新 768×1024 | `/tmp/bugfix644-review-tablet-refresh.png`：在线角标出现，提示仍为正在更新，渠道操作保持禁用；卡片与操作行未横向溢出。 |
| 无快照手机 | `/tmp/bugfix644-review-empty.png` 与原型文字区分显式规则和未知完整名单，禁用重新生成；没有将未知目录显示成空列表。文件预览未知分支的文案由源码核对；本轮未在该状态展开预览，不追加该交互的通过声明。 |
| 冲突与模型草稿 | `/tmp/bugfix644-review-conflict.png`、`/tmp/bugfix644-review-model-draft.png`；发现 R1-W1/W2。浏览器 snapshot 辅助确认控件和状态，截图均已由 reviewer 实际查看。 |

本轮临时截图只用于审查证据，不作为产品交付物提交；复现步骤及对应原型位置保留在本报告。控制台仅有 favicon 404 与密码控件非 form 的浏览器提示，无原型脚本异常。没有执行产品断网、真实渠道变更、LLM 回复或实施测试；这些属于 M1 验收。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — WARNING：配置版本冲突缺少可核对的服务端新值与保留修改路径

- 位置：`design.md:95–99`、`:187`、原型对齐表“冲突由用户确认”；`prototype.html:38`、`:73–78`。
- 证据：在原型在线编辑名称后切到“恢复后 · 配置冲突”，画面标题说“最新配置与当前草稿有差异”，实际只给出 high 不受支持的目录校验提示。没有显示服务端最新名称／其他改变字段，没有“核对后保留修改”的入口；“放弃草稿”只回到固定 initialDraft。主表单的真实当前实现也没有可直接沿用的版本差异视图，因此不是已存在 UI 的简单继承。
- 后果：R10 同时包含真实能力变化与他处配置变更，这两个问题需要不同判断。实施者现在仍须自行决定用户在哪里看服务端新值、确认保留哪些草稿，以及何时更新 base revision；容易做成只解除校验就重新保存整份旧草稿，或只能全部放弃。文字中“核对差异后确认”没有给用户可执行的核对流程。
- 关闭条件：补一个明确的并发配置变化例子，实际呈现当前服务端值与草稿的对应关系，并走通“采用最新配置／确认保留修改后手动保存”的选择。可用紧凑差异说明或展开区，不要求通用 merge editor；模型目录失效继续单独表达。同步 design/must-match，并实际观察桌面及窄宽度下的必要关系。

#### R1-W2 — WARNING：关键模型／强度草稿在离线原型中错误配对

- 位置：`prototype.html:31` 的 draft、`:45` 的模型与强度区、`:81` 的输入处理；对应 `design.md` 的模型／强度配对和草稿保留 must-match。
- 复现：在线选择模型 `deepseek:deepseek-v4-flash`，选择强度 `medium`，切换“离线 · 有历史信息”。实际画面变成模型 `codexOAuth:gpt-6.1-sol`，强度却是 `medium · 未保存草稿`。本轮 768×1024 截图 `/tmp/bugfix644-review-model-draft.png` 与 snapshot 均确认该组合。原因是模型未进入 draft，离线模型固定字符串，而强度保留草稿。
- 后果：这是本 bug 的核心配对信息和编辑中掉线旅程，不能作为不相关演示背景忽略。用户无法判断显示的是已保存的一对值还是自己准备保存的一对值，原型也无法证明 R6 的模型草稿保留；当前文字契约与可评审产物相冲突。
- 关闭条件：模型纳入原型草稿，明确只读时的草稿来源，并在需要显示已保存配置时保持两组信息各自成对；实际操作模型与强度→掉线→刷新中→在线，确认草稿不被替换、不自动保存。无需补齐整套模型能力后端。

### Recommendations

#### R1-R1 — 新离线错误的 iOS 兼容测试应点名 409 分类

`AgentConfigView.swift:106` 当前把所有非 pending 的 HTTP 409 归为 `conflicted`。新 `agent_node_offline` 也使用 409，因此建议将“离线业务码不误导为配置版本冲突”列为设计已要求的 wire/error 回归的具体断言；可直接在现有错误绑定中按 code 分类，不需要新原生页面。此项属于已授权兼容核对的具体测试提醒，不要求扩大本轮 iOS 视觉范围。

### 受审文件指纹

审查结束时记录 SHA-256，供后续复审判断改动范围：

| 文件 | SHA-256 |
|---|---|
| `incident.md` | `e63583c1854a44e734c448aa6710f4fc48fb2b69d8dbe66a77c9be353bc400ca` |
| `design.md` | `6bead8206d2ea3b672c35f0e337cd1a08c6f533a738f5292980f173094f07e3c` |
| `prototype.html` | `3494049f6fe041b6749730cfd81ce2ebb71381eb924825fbb11bbb36cb1ba304` |
| `specs/im/agents-nodes.md` | `0c9e541deaa6ccb255ca1a9fa472f5157fc577b3c0cfc74bb2a466f07e1510cb` |
| `specs/im/personal-agent.md` | `de17472976cb211e274132bcd43c910828c6ba149ae90d2fe416643aee72da67` |
| `M1-offline-settings/.gitkeep` | `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b` |

### Author Resolutions — Round 1

- **R1-W1 — accepted**：补充 design §前端读取、状态与草稿的具体核对流程；原型新增独立“他处修改配置”状态、逐字段草稿／最新值对照、采用最新／显式保留修改两条路径。保留只覆盖真正由用户修改的字段，模型与强度成组处理，其余采用最新配置；确认不提交，仍需手动保存。桌面和手机走查与两条选择的结果见 design §审查修订走查。
- **R1-W2 — accepted**：原型模型字段纳入 draft，离线只读直接显示该 draft，并与强度共同注明来源；已保存的一组值另行展示。实际完成模型＋强度→掉线→刷新→在线，草稿未替换、未自动保存。证据 `design-evidence/r2-model-pair.png`。
- **R1-R1 — accepted**：核对现有 iOS 错误分类的建议有实际依据，design §风险与回退明确要求 `agent_node_offline` 不被归为版本冲突；属于共享接口兼容绑定，不扩大原生 UI 范围。

修订范围：`design.md`、`prototype.html`、新增三张 R2 正式设计证据及本 resolutions。incident、两份 delta、milestone、后端架构和验收范围不变。请求原 reviewer 根据实际变化决定复审模式。

## Round 2

### Metadata

- reviewer_target: `/root/bugfix644_design_review`（与 Round 1 同一独立 reviewer）
- review_mode: `delta`
- mode_reason: 修订不仅修正原型模型绑定，还细化了字段合并与版本冲突选择规则；属于有界的前端设计变化，展开审查该变化及草稿／恢复影响。需求、后端职责、公共接口与 milestone 未变，无需重复 full。
- started_at: `2026-10-23T22:40:00+08:00`
- completed_at: `2026-10-23T22:43:42+08:00`
- duration: `3m42s`
- retained_from: `Round 1`
- 当前 HEAD：`1fce5eb1b`。incident、两份 delta 和 M1 骨架 SHA-256 与 Round 1 完全一致；基线至当前产品代码仍无 diff。核对 design 原 staged blob `c8d75c570` 与修订文件，变化仅在草稿冲突细节、must-match、修订走查及 iOS 错误分类提醒；原型差异围绕上述两项问题。新增三张 R2 图为补充证据。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1 与 R1-W2 已关闭，R1-R1 已纳入设计。此结论批准当前设计进入后续实施，不代表离线快照、真实网络恢复、渠道生命周期或 iOS 回归已经实现／通过。

### Coverage 与 retained 依据

本轮展开检查 `design.md` §前端读取、状态与草稿，模型配对和冲突 must-match，§风险与回退，以及 `prototype.html` 的 draft、versionReview、两条冲突选择与状态转换。字段合并明确只保留用户相对 base 的实际修改，其余采用最新值；模型与强度成组、显式集合整体处理；确认后仍需 live 校验和手动保存。更高服务端版本要求重新确认，未将快照或确认动作升级为保存许可。

这仍是现有前端表单草稿职责内的固定字段处理，没有新增通用合并框架、后端写接口或离线队列。原 profile CAS、当前能力校验和 pending 恢复继续承担提交边界，职责划分成立。

Round 1 的真实组装入口、RCA、D1–D4 快照与新写入边界、R5 节点自治、R7/R8 已接受操作恢复、delta Scenario 保留、M1 和 runbook 前置证据均 retained：其相关文件／决定没有变化。Round 1 已独立观察的真实产品桌面／手机基线也 retained；本轮不重复登录同一未变产品，不将重复观察当作新增验收。

### 历史问题闭环

| Issue | Author Resolution 与本轮证据 | 状态 |
|---|---|---|
| R1-W1 | accepted。独立在原型编辑名称“独立复审草稿”、模型与强度，再切“他处修改配置”。1440×1000 显示同字段两侧的新旧值和自己是否修改；390×844 改为逐字段上下排列，标签及长指令可读，按钮自然换行。选择“已核对，保留我的修改”后，名称保留自己的值、模型／medium 保留，未改过的专属指令变为服务端“负责产品研究与需求评审。每次输出附上可核对的依据。”；页面仍为未保存且需手动保存。再次进入冲突，选择“采用最新配置，放弃草稿”，得到服务端名称和 codexOAuth/high，dirty 消失、保存禁用。独立 screenshot 与 snapshot 均复核，不仅凭作者声明。 | **closed** |
| R1-W2 | accepted。独立选择 deepseek:deepseek-v4-flash + medium，经历 offline → refreshing → online。离线与刷新中两项均显示未保存草稿，另行显示已保存的 codexOAuth/high；刷新中保存禁用，在线后两个选择仍原样且仍为未保存。未发生自动保存或旧模型替换。 | **closed** |
| R1-R1 | accepted。design 风险段明确要求按 `agent_node_offline` code 区分 409，不误归配置版本冲突；对应 Round 1 核实的 Swift 错误分支，属于既有兼容回归范围，无新增原生视觉要求。实际代码测试留在 M1，不在设计阶段伪称已经通过。 | **closed（设计采纳）** |

### 独立浏览器证据

Playwright CLI 专用 session `bugfix644-r2-review`，原型 URL 与 Round 1 相同；本轮创建的 session 已关闭，没有停止作者服务。

- 独立截图 `/tmp/bugfix644-r2-pair.png`：两组模型／强度来源清楚，草稿与已保存值不会混成一组。
- 独立截图 `/tmp/bugfix644-r2-conflict-desktop.png`：字段横向对照、已修改／未修改标签与动作说明足以判断保留的范围。
- 独立截图 `/tmp/bugfix644-r2-conflict-mobile.png`：每个字段先草稿后服务端值，两个选择完整可见；不依赖记忆桌面另一列。并查看作者的 [手机证据](design-evidence/r2-conflict-mobile.png)，与本轮画面关系一致。
- 交互结果由本轮实际操作及 Playwright snapshot 核实；恢复过程中未重新保存，“保留修改”确认后仍显示未保存，“采用最新”后显示无未保存更改。

未扩展模拟真实后端或编写产品代码；平台／网络实际结果仍按既定 M1 验收。未发现需要新增 WARNING 的变化，停止本轮审查。

### Issues

无新增问题，无未关闭 CRITICAL / WARNING。

### Recommendations

无新增建议。

### 本轮受审文件指纹

| 文件 | SHA-256 |
|---|---|
| `design.md` | `4db65a604538486627bc69754c4a3aa169c27b54a1464ec1ddf31053f85cf59e` |
| `prototype.html` | `912d849c66cd77935b19a37e26cbff65ead11fb18f4ba4a757c42a137c37e786` |
| `design-evidence/r2-model-pair.png` | `f11513446d2feaa83f2b62dfcea0d650ccdb2cbbfe509c919ff38e6662f4270c` |
| `design-evidence/r2-conflict-desktop.png` | `4a316c225608ed851950a25ff34b265ba74f44f972c42bef724b56e7a9875ae8` |
| `design-evidence/r2-conflict-mobile.png` | `7538d9145a5fcca3e1aeee390db44b52be6575cf53764418ddbc03586e45dd18` |

### Author Resolutions — Round 2

作者核对本轮独立交互证据与文件指纹，无实质异议；R1-W1/R1-W2 已关闭，R1-R1 已采纳为实施回归断言。本轮无新增问题或建议，受审设计与原型不再修改，Gate 2 收口。

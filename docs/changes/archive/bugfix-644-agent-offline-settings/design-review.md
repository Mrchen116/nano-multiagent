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

### Author Amendment — 用户要求恢复现有界面（Round 3 输入）

用户指出 Skill 的“已禁用”标签属于擅自设计，并明确要求“顺便检查一下原型里还有没有类似擅自新增的设计，全部沿用现有界面，只改这次需要的离线行为”。据此撤销此前允许原型重排／合并背景的做法。改动仅 unit 设计产物：原型主体改用当前真实 DOM/CSS 的静态提取，恢复现有卡片、字段、分区、Skills 和通道向导；新增 `prototype-current.css` 只用于离线打开原型。design 中增加逐项范围核对及 R3 当前证据，旧图不再作为实施模板。

同时撤销 R2 的差异对照／选择性合并新界面：沿用现有错误提示和“放弃修改”载入最新值后再编辑，保持草稿、CAS 和当前能力校验。该项是按用户最新范围纠正先前 author 决定；不是反转用户的 R10 要求，仍不自动覆盖或保存。incident、delta-spec、后端快照／写入接口及 M1 范围不变。请求原独立 reviewer 根据实际修改选择复审模式，重点核对“只改离线行为、其余沿用现有界面”。


## Round 3

### Metadata

- reviewer_target: `/root/bugfix644_design_review`（与 Round 1/2 同一独立 reviewer，未参与受审修订）
- review_mode: `full`
- mode_reason: 用户新增“全部沿用现有界面，只改这次需要的离线行为”的明确边界，原型主体和冲突交互整体替换；重新审查全套体验关系与需求覆盖，未变化的后端证据经文件／代码差异核对后复用，不将旧 Approved 当作新版本通过依据。
- started_at: `2026-10-23T23:07:00+08:00`
- completed_at: `2026-10-23T23:13:20+08:00`
- duration: `6m20s`
- checkout: 主仓 `main`；审查期间其他任务推进 HEAD，结束核对为 `15063908d`。设计基线 `59ca15b2a` 至审查时 `apps/im-server/src`、`src/IM/frontend/src`、`src/IM/ios` 无差异。保留其他 staged／untracked 内容，仅追加本报告，不提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

现有卡片、字段顺序、Skills 来源组／颜色、通道卡片及手机底部弹层已恢复。当前新增内容围绕离线、刷新、未知、待确认与草稿保护；未发现仍需作为本次设计要求移除的额外正常在线界面改造。通过的是设计门禁，不是后端实现、真实掉线恢复或生产验收。

### Coverage 与证据

| 范围 | 本轮判断与依据 |
|---|---|
| 用户新增边界 | 独立打开真实隔离页面与原型，对照身份、行为、访问与模型、工作区卡片及分区导航。`agent-detail-page.tsx:1704–2038` 的内容关系与新模板一致；普通 Agent 没有新增工作入口，Skill 没有“已禁用”后缀，也没有模型双列比较块。演示栏在产品区域之外，design 明确不进入实施。 |
| R1/R2：最后配置与未知 | 离线仍保留原字段、模型／强度、工具与 Skill 分组。手机无快照状态实际显示“自动发现的完整 Skills 名单暂时无法获取”，Features 用未确认态与说明，未把未知显示为已关闭或空名单。有限快照、显式 profile 与默认发现的职责保持 D1/D2 原方案；incident 与 delta 指纹未变。 |
| R3/R4：全页只读与渠道 | 配置及渠道控件随离线、刷新禁用；取消、阅读和重新读取仍为设计允许入口。实际走过已有通道编辑、无通道 provider picker／新增凭据步骤及手机底部弹层掉线；App ID 输入保留，保存与输入禁用，取消和关闭可用。`agent-channels-panel.tsx:340/436/507` 确认这些弹层及 keep/replace 是现有结构。未引入渠道名称字段。PA、插件、cron 等完整流程仍按原组件接入统一条件，原型未删除或重新设计它们。 |
| R5：最后状态 | 768×1024 渠道恢复中画面明确“正在确认”，操作禁用；离线卡片保留最后状态说明，不声明本地停止。D4 不改变节点自治，沿用已有 manifest／observed 与 Work 状态契约。 |
| R6/R9：草稿与恢复 | 在线输入名称“R3 独立草稿”、选择 `codexOAuth:gpt-6.1-sol`／`max`，切离线、刷新中、在线；两项保留在原连续字段，未自动保存。刷新禁用和 ready 后 dirty 条件由本轮交互与当前脚本核对。宽度切换仍保留表单草稿。设计继续要求取消旧查询、读取代次和区域依赖解锁。 |
| R10：配置冲突 | 冲突前草稿值完整保留且保存禁用。实际点击现有“放弃修改”后显示示例服务端新名称 `E2E Agent（最新名称）`，dirty 清除、保存仍禁用。设计明确 latest 尚未取得不能假称载入最新；离线普通放弃只还原已确认 base，不解除冲突。`agent-detail-page.tsx:1465/2041` 验证已有 discard 和 footer error 承载位置，新增的是状态处理，不是另造比较／合并产品流程。 |
| R7/R8：在途与历史 pending | D4 与接口 §3 未改变：新写入在副作用前拒绝，已接受 operation／manifest 的恢复继续。原型 pending 仅作反馈证据，真实 ACK／receipt／迟到响应仍由 M1 验证；复用 Round 1 的真实服务组装与恢复入口证据。 |
| R11：在线正常行为 | 原有表单／通道在线流程继续由现有组件承担；静态模板不成为重写正常业务的要求。模型切换联动、通道凭据验证与既有权限仍按原实现。此次未用静态演示宣称这些后台动作已通过。 |
| RCA、接口与架构 | 重新核对设计 D1–D6 与 Round 1 核实的真实组装链，D1–D4 及公共接口未变化，目标仍覆盖能力缺失误判与离线写入不一致。IM 的局部快照／读模型、前端局部状态 hook、既有 profile CAS 与恢复机制各司其职；移除字段合并机制进一步减少维护范围，不需要新增通用编辑框架。没有扩大 DSH 接入或引入第二套执行机制。 |
| delta、milestone、iOS | 两份 delta、incident 和 M1 骨架与 Round 1 指纹完全相同，canonical target、Scenario 保留及共享接口边界继续成立。must-match 已改为原界面与必要状态反馈，M1-U1/U2/U3/W3 对应完整；iOS 409 按 code 分类提醒仍保留，不要求新原生界面。runbook 的隔离栈、真实 UI 与受控边界测试分工未变化。 |

### 独立画面与交互证据

Playwright CLI 专用 session `bugfix644-r3-review`：真实页面 `http://127.0.0.1:53041/settings/agents/e2e` 与原型 `http://127.0.0.1:53042/prototype.html`。本轮登录并读取真实配置，没有修改真实产品数据、凭据或停服务。以下截图已实际查看，不仅依据 DOM／源码作体验判断：

- `/tmp/bugfix644-r3-current.png`：1440×1000 真实在线配置；与新原型的卡片、字段及导航结构对照。真实会话默认英文，原型为现有中文语言文案；该差异不视为新文案设计。
- `/tmp/bugfix644-r3-proto-online.png`：新原型正常页面，身份／行为等原有排列；没有旧重排或解释标签。
- `/tmp/bugfix644-r3-offline-pair.png`：原有工具灰／绿色与模型、强度连续字段，保留本轮编辑值。
- `/tmp/bugfix644-r3-conflict.png`：1440×1000，现有 footer 错误文字、放弃修改和禁用保存；没有字段对照或“保留我的修改”新按钮。
- `/tmp/bugfix644-r3-unknown-mobile.png`：390×844，未知 Features／Skills 提示与保存规则可读，现有手机底部导航保留。
- `/tmp/bugfix644-r3-dialog-mobile.png`：390×844，原编辑底部弹层、App ID、keep/replace、取消／保存关系保留；离线提示位于内容上方，草稿 `cli_r3_draft` 可读。
- `/tmp/bugfix644-r3-tablet-refresh.png`：768×1024，原通道卡片与恢复反馈，无横向溢出，所有变更操作禁用。

新增向导也实际完成 provider picker → App ID `cli_r3_add` → 离线，返回的控件状态确认为保存禁用、取消／关闭可用。一次自动化定位同时命中页头与空态的两个既有“添加通道”按钮，改用明确首个入口后完成；这属于审查脚本定位歧义，不是产品问题。临时截图不提交，专用浏览器关闭，不关闭作者服务。

### 历史问题闭环

| Issue | 本轮处置与依据 | 状态 |
|---|---|---|
| R1-W1 | 用户新边界明确排除额外在线界面改造，因此撤销先前要求新增差异对照／保留合并的关闭方式。保留草稿、禁止覆盖新版本、现有错误提示、放弃后载入最新再编辑已形成可执行路径，满足 R10；不因删除旧比较面板而重开。 | **closed，按用户新边界替换解决方式** |
| R1-W2 | 新原型直接在原模型与强度字段保存草稿，本轮离线／恢复与冲突读取均得到 `codexOAuth:gpt-6.1-sol`／`max`，不再错误拼接为已保存模型加草稿强度。额外保存值面板按用户要求删除，不影响配对与来源。 | **closed** |
| R1-R1 | iOS `agent_node_offline` 的 409 分类回归仍明确写在 design 风险段；本轮没有测试原生实现，不扩张结论。 | **closed（设计采纳）** |

### Issues

无新增问题，无未关闭 CRITICAL / WARNING。

### Recommendations

无新增建议；停止本轮审查，不追加无关 UI 优化。

### 本轮受审文件指纹

| 文件 | SHA-256 |
|---|---|
| `incident.md` | `e63583c1854a44e734c448aa6710f4fc48fb2b69d8dbe66a77c9be353bc400ca` |
| `design.md` | `757c040f86ce5fb3239065972124a89b53e85faed84da7bcc8c1bb7962a4cb91` |
| `prototype.html` | `515d4b39492c428d2ba767c7753a0d0f31e29c79f6bf0137d11848260aa5a9b0` |
| `prototype-current.css` | `ef995e4dbdb691414b8b2f61f1673c5746ea6e1f5e6edf1a0357356734366b28` |
| `specs/im/agents-nodes.md` | `0c9e541deaa6ccb255ca1a9fa472f5157fc577b3c0cfc74bb2a466f07e1510cb` |
| `specs/im/personal-agent.md` | `de17472976cb211e274132bcd43c910828c6ba149ae90d2fe416643aee72da67` |
| `M1-offline-settings/.gitkeep` | `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b` |

### Author Resolutions — Round 3

作者核对独立复审的现有界面对照与交互证据，无实质异议。本轮无新增问题或建议；确认按用户最新要求沿用现有界面，仅新增必要离线行为，旧原型的额外界面设计不再作为实施要求。受审设计与原型保持不变，Gate 2 以本轮 Approved 收口。

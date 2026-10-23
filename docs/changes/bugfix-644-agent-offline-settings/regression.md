# bugfix-644 — 回归验证

> 对齐：[incident.md](incident.md)、[design.md](design.md) 的 R3 原型契约及 Runbook。
> Round 1；2026-10-23 至 2026-10-24；mode=full；revalidation_mode=full。
> Validation snapshot: `1ef49808ffd2618c275b6e38683f93f74ff8455d → 4ba1eefca3c547f40f9b1060c64941ee3cf6ee09`。

## Verdict

**fail**。Highest Required Action：**fix-implementation**。4 major、1 minor；需要复验，没有创建外部 issue。

原报告中的主模型／强度离线误判未再出现，普通、Global 和 PA 的核心表单可转只读；真实恢复先刷新再解锁、未提交草稿保留、跨浏览器历史信息读取均取得正面证据。但是已接受配置操作的待确认事实在离线页面消失，在线渠道重连／删除不能完成，已保存备用模型无法离线展开阅读，单个统计读取失败仍误报 Gateway offline，整体尚不可交付。

本轮没有读实现定位根因或修改产品代码。报告中的因果只限可见操作和网络／持久状态核对；交由 owner 定位实现原因。未把 worker 成功叙述或单元测试替代真实体验。

## 环境、版本与真实覆盖

- checkout：`.worktrees/unit-bugfix-644`，branch：`unit/bugfix-644`。开始时 HEAD 与 validated_at 一致且 clean。
- caller 提供隔离 IM `http://127.0.0.1:59021`、Vite `http://127.0.0.1:59020`、真实 Node/DSH 和经身份核验的专用 Feishu 渠道。浏览器使用 `nano` 测试账号；无外部消息发送。
- caller 交接后端构建及当前 Web 源码来源。验收中 HEAD 增加 `a685d1aa4`，其差异仅 code-review.json、verification.md；caller 后续修改后端源码但明确未构建／重启，且未修改 Vite 前端，故本报告仍对应原 validated_at 的运行实现。
- Playwright 专用 session：`bugfix644-review`。桌面 1440×1000、手机 390×844、平板 768×1024；另用独立 browser context 重新登录验证离线首次访问。
- 普通 `e2e`、Global `e2e-global`；通过真实聊天入口创建 PA `pa_9344b21d3d8e`（Review Assistant）。创建最初返回未就绪，稍后成功并能进入配置；没有将初次延迟直接判为产品失败。
- 停 Node 实验与仅断 Relay 实验分别进行。后者用临时 59029 透明转发代理，切断 WebSocket 而保留 Node PID 15140 运行；没有注入假业务响应。配置 pending 实验仅暂停 Node→IM 的真实流，再断连接丢弃未转发结果。
- 单分区读取失败实验仅中止浏览器真实 `/settings/sections/usage` 请求，Node 及其他请求保持正常。
- iOS 依派发范围交 caller 做共享错误分类契约及构建；本轮不声明原生 UI 体验通过。

## 复现验证与场景矩阵

| 来源 | 结论 | 实际观察与证据 |
|---|---|---|
| R1 离线首次打开／刷新／另一浏览器 | **fail** | 主模型 `codexOAuth:gpt-6.1-sol` 与 high 在离线刷新及独立新浏览器仍配对显示，没有不支持／移除错误；Features、工具、Skills 保留，顶端显示时间。但已保存的一个备用模型折叠后无法展开，见 I3。[新浏览器](review-evidence/r1-fresh-browser-offline.png)、[平板模型](review-evidence/r1-tablet-reopen-model.png)。 |
| R2 继承、默认发现、从未取得 | **inconclusive** | 未曾读取的 Skills 统计和插件区离线显示“Unavailable; no previously confirmed information is available.”及 Retry，没有伪造空结果；恢复后真实 usage 返回空快照，才显示 No skill usage yet。PA 的 Platform default、默认发现 Skills 和 Follow node 可见。未完成核心配置完全无快照、所有继承 Feature 来源及旧快照版本错位的完整交叉验证，不宣称完整通过。 |
| R3 全页只读与保留阅读操作 | **fail** | 普通／Global 表单字段与预览、保存禁用；PA 离线 input/select/textarea 中可操作者仅搜索框，聊天范围可展开与搜索，名称／策略／心跳等只读。分区切换和取消可用。但备用展开也被禁用（I3）。PA 当前无受限联系人、无可删除 cron 条目；插件已读到真实 dsh-agent-context，但插件启停／卸载的完整离线生命周期未完成，保留缺口。[PA](review-evidence/r1-pa-offline.png)、[Global](review-evidence/r1-global-offline.png)。 |
| R4 渠道禁止新离线变更 | **inconclusive** | 已有渠道的 Add/Edit/Disable/Delete/Reconnect 均禁用；手机编辑弹层和停用确认框掉线后提交禁用、取消可用。完整配置 API 离线返回 409 agent_node_offline，Global profile_version 保持 1、pending=null。渠道本身各写 API 的离线无副作用及旧删除记录的 retry 未全部实测；旧自动应用提示仍矛盾（I5）。[渠道](review-evidence/r1-relay-cut-channel.png)、[手机弹层](review-evidence/r1-mobile-channel-draft.png)。 |
| R5 失联不等于本地停止 | **pass** | 真实仅断 Relay 时 `ps` 仍确认 Node PID 15140 存活；原 Connected 卡片变成 Node offline，并写“Last known status: Connected (node offline; not a current connection)”及最后时间，没有宣称停用／删除。[证据](review-evidence/r1-relay-cut-channel.png)。未用 stop Node 作为此项证明。 |
| R6 编辑中掉线 | **pass** | 名称 E2E Review Draft、主模型及 high 草稿保留；分区切换、手机宽度切换不丢输入。手机渠道 App ID 草稿 cli_review_unsaved 保留，输入／Save and connect disabled、Cancel enabled；停用确认框 Confirm disable disabled、Cancel enabled。恢复不会自动保存草稿，手动保存后才变为持久版本。[桌面](review-evidence/r1-desktop-offline-draft.png)、[手机模型](review-evidence/r1-mobile-model-draft.png)、[手机弹层](review-evidence/r1-mobile-channel-draft.png)。 |
| R7 已提交结果未确认 | **fail** | 真实保存生成 durable pending，丢失 Node 回传后页面退为 Unsaved changes，没有结果待确认。见 I1。[原页](review-evidence/r1-config-pending-offline.png)。 |
| R8 已接受旧操作保留与恢复 | **fail** | 在已存在 pending 时离线重新打开，接口仍返回 pending，UI 却显示旧名／No changes。恢复后同一操作收敛，读到 Review pending accepted 且 pending=null；恢复机制的正面结果不能补齐离线事实展示。旧渠道 removal/retry 未完成，页面 DELETE 先被 400 阻断（I2）。[重开](review-evidence/r1-pending-reopened.png)。 |
| R9 先刷新再开放 | **pass** | Node 重新启动后先显示“Connected. Refreshing information before enabling changes.”，Display Name disabled；稍后自动恢复可编辑，名称和模型草稿仍保留。仅 Skills 读取失败时 Config 仍可编辑。没有手动刷新整页才解锁的依赖。 |
| R10 目录／版本变化或读取失败 | **fail** | 另一请求真实更新服务器名称后，本地 Review concurrent draft 保留，提示 Settings changed elsewhere 并阻止 Save；在线放弃后可回到服务器值。单独 usage 请求失败却报 Gateway offline（I4）。真实目录删除模型／强度／工具／Skill 的分支未完整实测。[冲突](review-evidence/r1-conflict.png)、[读取失败](review-evidence/r1-read-failed-mislabel.png)。 |
| R11 恢复后正常保存与渠道生命周期 | **fail** | 名称、主模型、高强度和备用模型通过真实表单保存；另关闭 Intelligent UI、lark-calendar、web_search，200 后刷新仍分别为 false。渠道新增、编辑保留密钥、停用、重新启用成功，卡片实际 Connected。Reconnect POST 与 Delete DELETE 都为 400，见 I2；删除重试尚未可用。仅为准备“无渠道”状态，用管理 API 携带空 JSON body 删除成功，再走真实新增表单；这不计为 UI 删除通过。[在线](review-evidence/r1-online-final.png)。 |

## 整体体验与 must-match 对照

Reference Artifacts Reviewed：design.md R3 表格、design-evidence/r3-current-mobile.png、r3-offline-desktop.png、r3-original-skills-model.png、r3-original-dialog-mobile.png；同时读取 incident 全部 R1–R11。未以旧 R1/R2 原型替代最新契约。

- 正常框架／字段顺序：实际 Identity、Behavior、Access & Model、Workspace & Runtime 顺序延续基线；原 Skills 来源组、计数和灰绿选中态保留，模型／强度仍是连续原字段。桌面、手机和平板实际内容可读，没有引入差异合并面板。手机基线也存在底部横向滚动条，本轮不凭该现象单独推断新增布局回归。
- 离线／草稿：状态说明和最后确认时间帮助理解数据时效；模型／强度不跳值。实际状态说明在主内容上方展开，不是原型中的白色卡片，但没有妨碍阅读，不以纯样式差异阻塞。备用模型无法展开则直接妨碍读懂已保存配置（I3）；pending 缺失让用户无法判断是否已提交（I1）。
- 渠道与手机弹层：保留 App ID、keep/replace secret、Save and connect、Cancel 结构和底部弹层；没有新增渠道名称或新凭据规则。掉线草稿只读且取消可达。在线 400 使正常生命周期不能完成（I2），不能以结构一致放行。
- 未知／冲突反馈：未知统计与真实空结果的区别已有正面观察；并发版本冲突可辨认且不覆盖草稿。单次读取失败的 Gateway offline 与同屏绿色在线状态矛盾（I4）。因此 must-match 未全部满足。

## Issues

### I1 — major：已接受配置 pending 在离线页面消失

- Regression Relation：direct；Recommended Action：fix-implementation。
- 来源：R7、R8；D2/D4/D5 与 operation_pending 状态契约。
- 复现：在线编辑名称为 Review pending accepted → 临时代理暂停 Node→IM 回传 → 点击 Save Agent → 持久库产生 `5e9c3433bfa844dfab91736b3c92c63c`，status=pending，created_at=2026-10-23T16:05:55.014Z → 切断 Relay → 查看原页，再离线刷新。
- 实际：原页显示 Unsaved changes；刷新后旧名 E2E Review Draft、No changes；没有 alert 或待确认状态。真实 `/settings` 同时返回该 pending_operation，ready=false；只读数据库核对仍 pending、无 error_code。恢复连接后同一已接受操作成功收敛。
- 期望：明确保留已提交、结果待确认，不能把它表述为未提交草稿／没有变化。
- Action Rationale：用户无法知道动作已经被接受，也无法可靠决定是否需要再提交；属于核心结果真实性缺失。
- 证据：[断线原页](review-evidence/r1-config-pending-offline.png)、[离线重开](review-evidence/r1-pending-reopened.png)。

### I2 — major：在线渠道重连及删除均返回 400

- Regression Relation：suspected-regression；Recommended Action：fix-implementation（原因由 owner 判定）。
- 来源：R11、原有渠道正常生命周期。
- 复现：专用 Feishu 卡片已 Connected → Reconnect；或 Delete → Confirm delete。
- 实际：`POST /im/v1/agents/e2e/channels/feishu%3Ae2e/actions/reconnect` 与 `DELETE /im/v1/agents/e2e/channels/feishu%3Ae2e?channel_revision=4` 都返回 400，detail=`Body cannot be empty when content-type is set to 'application/json'`。删除确认框不关闭，渠道仍存在。
- 期望：在线且当前状态已确认时完成对应管理动作，随后按真实节点结果显示。
- Action Rationale：两个明确的正常用户动作不能完成，直接阻塞 R11。管理 API 携带 `{}` 后删除成功仅用于后续新增准备，不抵消 UI 失败。
- 证据：[删除错误](review-evidence/r1-delete-error.png)；该截图为错误发生后再断线的画面，400 的在线请求时序和状态码以上述独立响应捕获为准。

### I3 — major：折叠的已保存备用模型离线不可阅读

- Regression Relation：direct；Recommended Action：fix-implementation。
- 来源：R1、R3 的完整已保存配置与展开阅读。
- 复现：在线添加并保存备用 deepseek:deepseek-v4-flash（PATCH 200）→ Hide fallbacks → 断 Relay。
- 实际：只有 Fallbacks 1，按钮 disabled=true；Fallback 1 combobox 数量为 0，无法读到备用模型名称和顺序。
- 期望：只禁用修改，保留展开／折叠及既有备用信息的阅读。
- Action Rationale：用户知道“有一个”却无法判断“是哪一个”，破坏本次离线仍能理解完整配置的目标。
- 证据：[备用不可展开](review-evidence/r1-fallback-hidden.png)。

### I4 — major：节点在线时单个统计请求失败仍误报离线

- Regression Relation：direct；Recommended Action：fix-implementation。
- 来源：R10，读取失败必须与节点离线区分。
- 复现：Node 在线、渠道 Connected → 仅 abort `/settings/sections/usage` 的真实 HTTP 请求 → 打开 Skills。
- 实际：同屏绿色在线节点标记，正文红字 Gateway offline / Failed to fetch / Retry。切回 Config，Display Name 仍可编辑；恢复请求后 Retry 得到真实空 usage。
- 期望：说明统计读取失败，保留节点状态，不把读取失败解释为电脑离线。
- Action Rationale：本次修复的核心就是不把无法获取信息错误归类为另一个业务状态；误报将用户引向无关的节点排障。
- 证据：[在线读取失败](review-evidence/r1-read-failed-mislabel.png)。

### I5 — minor：渠道只读页仍承诺离线变更上线后自动应用

- Regression Relation：direct；Recommended Action：fix-implementation。
- 来源：R4、用户确认的禁止新离线变更原则。
- 实际：只读提示下同时显示“Changes are saved securely and apply automatically when the node returns.”，即便没有新待处理操作；与本次禁用行为矛盾。
- 期望：提示需恢复连接才能修改；如有旧 pending，应针对已接受操作单独说明。
- Action Rationale：局部文案会误导用户，但本轮该处修改入口实际已禁用；单独作为 minor，不降低其他 major 的阻塞性。
- 证据：[渠道离线页](review-evidence/r1-relay-cut-channel.png)。

## 复验尚需补齐的证据

除 I1–I5 修复后的对应重验，下一轮需提供并实际覆盖：核心配置完全无历史信息及继承来源、目录真实改变后的不兼容；PA 有可勾选聊天／既有受限联系人和 cron 非空记录；插件可修改实例的禁用入口；已有渠道 removal/retry 与完整渠道离线 API 无副作用。当前无这些完整证据，不因本轮已有阻塞而写作通过。没有测试或操作生产对象。

## 自动化测试增量与范围

本角色没有新增或运行自动化测试，也未读取实现寻找根因。caller 负责后端／前端／iOS 契约和 CI；本报告仅记录所列真实浏览器、真实网络控制、真实 API 与必要只读数据核对。需要将 I1–I4 的用户结果加入回归覆盖；自动化通过不能替代本报告缺失的 UI 观察。

## 上层文档同步

- [x] `SPEC.md`：无需因本轮发现改变跨包顶点架构。
- [x] `docs/specs/im/agents-nodes.md`、`personal-agent.md`：需要在实现修复并通过验收后由 caller 按 delta 归并；当前不能把未通过的目标描述为已完成行为。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 环境收尾

测试期间只操作本次隔离 Node 与临时代理。临时 Gateway config 的 IM URL 已恢复 `http://127.0.0.1:59021`，Node 重启 PID 29150；59029 转发进程已停止。隔离 IM/Vite 仍交 caller 管理；不执行 e2e-down 以免影响其后续复验。专用渠道已通过真实新增恢复，未外发消息。普通 Agent 最终显示名 E2E Agent；测试保存的模型／强度／一个备用及 Feature/Skill/tool 选择留在本次隔离数据中供复验，未修改生产。浏览器 session 在最终在线确认后关闭。

---

# Round 2 — 2026-10-24 复验

> mode=full；revalidation_mode=full。真实受验业务源码 `acf0c72f2e799775311cca501dfb934d9174472f`；开始 HEAD `f226eb2b2b177b2d9aa4f64b54ec85431e3a488f`。caller 说明 IM 已在 `82cf77613` 构建，后续 acf 只涉及 Vite 直接服务的 Web 修正。期间合入的 `516a6a1e98e902fbba4026c43a8716c36c221c73` 仅同步文档、skills 和 CI；未将它冒充本轮全部重验过的新业务树。

## Verdict

**fail**。Highest Required Action：**fix-implementation**。**1 major、0 minor**；needs_re_review=true。

Round 1 的 I1–I5 均关闭。真实 pending、渠道生命周期、非空 PA/cron/插件只读、历史正文、目录变化和明确纠正已取得决定性证据。但完全无历史快照的 Skills 区把尚未确认的启用数量显示为 `0 selected`，与空禁用名单语义及同区未知说明矛盾，R2 尚未满足。只需修复 I6 并对无快照／旧快照／真实空选择做局部复验；下列其他证据可以按其具体边界保留，不需要重跑整套渠道及断线旅程。

## 环境与证据来源

- 继续使用 Round 1 的专用隔离 IM 59021、Web 59020、Node/DSH 及测试账号。浏览器 session `bugfix644-review-r2`；主要桌面 1440×1000，PA 页 2400×1454，完全无快照页手机 390×844。没有访问生产对象或外发消息。
- 新增前置来自本次隔离运行数据：真实未来 cron `Offline review future reminder`（2027-12-31）、可启停和卸载的 `review-offline-plugin`、测试模型 `review:catalog-model`、workspace Skill `review-offline-skill`；PA 有真实测试群 `Offline review source chat` 和隔离数据库中的合成受限联系人 `review-restricted-contact`。
- 无快照：停止隔离 Node 后，只删除 `e2e-peer` 的显示快照，保留真实 committed profile。旧快照错位：先真实读取 Global settings，再通过真实 PATCH 将 description 改为新值并提交 profile v2，不再次读取 settings 即停止 Node；离线页面面对 v1 显示快照和 v2 committed profile。
- pending 与 removal 实验仅暂停／切断真实 Relay，未替换业务 HTTP 响应。API 验证使用浏览器真实登录身份；数据核对只读。读取失败实验仅 abort usage 请求。
- 本轮没有读取产品实现定位原因、修改业务源码或以自动化测试代替体验判断。原生 iOS UI 不在本次实际体验声明内，继续由 caller 依交接范围承担共享契约及构建验证。

## 复验矩阵

| 来源 | 结论 | 实际结果与证据 |
|---|---|---|
| R1 离线首次进入／刷新／完整配置 | **pass** | 主模型与 high 保留；折叠的已保存备用模型可离线展开，`Fallback 1` 显示 deepseek:deepseek-v4-flash 且不可修改。I3关闭。[备用模型](review-evidence/r2-offline-fallback.png)。独立浏览器首次进入及平板证据保留 Round 1 R1 的已验证部分；本轮修正未改变该读取路径。 |
| R2 默认、继承与没有历史信息 | **fail** | Global 旧快照/新 profile 下，Feature default、Skills 来源与 reasoning 均标为未确认；没有沿用旧默认值。无快照 e2e-peer 身份与显式配置保留、推理显示 current value unavailable，但 Skills 在真实 `explicit_denylist` / `skills=[]` 下错误显示 0 selected。见 I6。[旧快照](review-evidence/r2-old-snapshot.png)、[无快照手机](review-evidence/r2-no-snapshot-mobile.png)、[错误计数](review-evidence/r2-no-snapshot-skills.png)。 |
| R3 全页只读与保留阅读 | **pass** | PA 非空聊天 checkbox、既有联系人 Unblock 均 disabled；搜索/展开仍可用。非空 cron 的 `Delete Offline review future reminder` disabled。已安装测试插件的启停 switch 和 Uninstall disabled。I3 的备用阅读已修复。[PA状态](review-evidence/r2-offline-pa.png)、[真实控制项](review-evidence/r2-offline-pa-controls.png)、[插件](review-evidence/r2-offline-plugin.png)、[cron与正文](review-evidence/r2-history-body.png)。 |
| R4 禁止新离线变更 | **pass** | create、edit、disable、enable、delete、reconnect 六项渠道真实 API 均返回 409 / agent_node_offline，前后 channel GET 完全相同；实际 channel_id 使用真实资源 ID。初次使用旧已删除ID得到404的请求不计覆盖。removal retry 也409，receipt 的 created_at 与 updated_at 均保持 16:55:14.972Z、apply_state=pending。页面 Add/Edit/Disable/Delete/重连或 retry 均禁用。旧离线自动应用文案已改为恢复并刷新后可修改，I5关闭。[只读渠道](review-evidence/r2-channel-offline.png)、[删除回执](review-evidence/r2-removal-offline.png)。 |
| R5 失联不等于本地停止 | **pass / retained** | Round 1 的仅断 Relay、Node存活、Last known status而非当前Connected证据保持有效。本轮代理再次仅切断传输；卡片仍写 Node offline 与最后已知连接状态，未把失联解释成停用／删除。 |
| R6 编辑中掉线 | **pass / retained** | 保留 Round 1 名称/模型/high、手机渠道弹层草稿与取消可达证据。本轮未提交 review:catalog-model 也跨 Node 停止/启动保留，不自动保存。 |
| R7 提交结果待确认 | **pass** | 真正保存生成 operation `daa43840dbbd478d9debdb02758fc2a5`，16:53:12.662Z，数据库 status=pending；丢弃回传并断线后，离线重开明确显示 submitted change awaiting confirmation / Do not repeat，并保持 Save disabled。I1关闭。[pending重开](review-evidence/r2-pending-reopen.png)。 |
| R8 旧操作保留与恢复 | **pass** | 上述同一 config operation 恢复后 committed、error_code=null，页面名称成为 R2 pending accepted。在线删除返回200后丢弃回执，离线重开仍有 Deletion pending、credentials removed 与保存时间，Retry apply disabled，直调retry409不改receipt。恢复后同一removal变applied，页面不再保留待删卡片；随后可真实新增渠道201。[删除待确认](review-evidence/r2-removal-offline.png)。 |
| R9 先刷新后开放 | **pass** | 本轮恢复及保存后看到 Connected. Refreshing information before enabling changes；表单先禁用，再在真实 ready=true 后可编辑。保留 Round 1 的完整草稿恢复证据。统计单区失败不阻断其他已确认配置。 |
| R10 目录／版本变化与读取失败 | **pass** | 单独 abort usage 后，同屏节点在线；区域说明 Could not refresh / last confirmed view preserved，不再报Gateway offline，Retry恢复。I4关闭。[读取失败](review-evidence/r2-read-failed.png)。保留未保存测试模型草稿，实际移除模型、workspace Skill并通过UI卸载插件200；恢复后模型 review:catalog-model、工具 review_offline_echo 原选择仍在，各自明确提示 unavailable并阻止Save。用户通过真实表单取消失效工具、重选codex模型/high后PATCH200。当前Skills是explicit_denylist：启用项由发现集推导；移除默认启用测试Skill后变为真实0项，保存的其他禁用名称保留，此处不能误当显式allowlist丢失。[目录冲突](review-evidence/r2-catalog-conflict.png)。并发版本冲突保留 Round 1 R10 的有效证据。 |
| R11 恢复后正常操作 | **pass** | 在线 Reconnect200、Delete200，I2关闭。目录纠正后真实PATCH200；最终名称恢复 E2E Agent，模型codexOAuth:gpt-6.1-sol/high、备用保留。专用渠道通过真实凭据表单新增201，最终实际Connected；编辑/停用/启用沿用 Round 1 已成功路径。[最终在线](review-evidence/r2-online-final.png)。 |

### 历史正文与时效补证

在线实际读取 HEARTBEAT.md 的 `Offline settings review` 正文，断线后正文仍可读，同区保留最后确认 00:57:29 与“当前未确认”；非空 cron 独立保留 00:56:51。[正文与cron](review-evidence/r2-history-body.png)。stable prompt preview 在真实在线读取后也跨断线保留正文，独立最后确认 00:59:58；未把未加载正文的折叠区当作通过。[prompt历史](review-evidence/r2-prompt-history.png)。

## 整体体验与 must-match

沿用已审阅的 design R3 must-match，而非重新定义验收线。核心表单、Skills分组/pills、连续模型/推理字段、普通导航和渠道弹层结构保留；这轮新增状态提示没有阻断可读内容。备用展开、非空历史正文、非空PA控制项和旧操作状态均通过真实阅读/操作核验。关键截图已打开检查；手机无快照的字段没有被整页错误替代，已保存值仍可读。

唯一剩余体验冲突在 Skills 局部：标题右侧明确给出零数量，下面又说完整发现列表未知。用户会把未知能力集合理解为已禁用全部技能，因此不能以更小字号的免责声明抵消确定性错误。整体暂不可交付，受影响范围集中在无快照状态的计数表达。

## 新问题 I6 — major：无快照的空禁用名单被显示为零个启用 Skill

- Regression Relation：direct；Recommended Action：fix-implementation。
- 来源：incident R2 与设计“未确认/无历史信息不能伪装为已确认空值”的 must-match。
- 复现：停止本次隔离Node → 仅移除e2e-peer显示快照 → 手机390×844重新打开Config → 展开阅读Access & Model；最后再次点击Refresh并真实直读settings核对。
- 实际：settings `ready=false`，`config.skills_selection_mode=explicit_denylist`、`config.skills=[]`；页面Skills标题显示 **0 selected**，下方同时显示 `The full discovered Skills list has not been confirmed for this configuration`。列表只有 `-`。空禁用名单表示没有显式禁用名称，无法在发现集合未知时推出启用数量为零。
- 期望：把完整启用数量明确标为未知／尚未确认；显式禁用名单和已知名称仍可阅读。只有已确认候选结果或真实显式空选择的适用语义才可显示确定的零。
- Action Rationale：这正是本次要修正的“未知被解释成业务值”，会使用户误认为全部技能关闭；属于R2核心结果，不因其他旅程通过降级。
- 证据：[真实手机画面](review-evidence/r2-no-snapshot-skills.png)。复验期间两次独立清除该Agent快照并观察到同样结果，未改业务返回值。

## 后续局部复验边界

I1–I5关闭；R1、R3–R11及历史正文证据可保留，前提是修正只影响未知Skills计数/来源表达。下一轮只需覆盖：无快照+空explicit_denylist、未知发现集合+非空名单、旧快照/新profile的未知来源，以及真实已确认空结果；确认未知不再显示零、显式信息仍可读且只读。若修改扩大到配置提交、渠道或恢复机制，应按实际影响扩大复验。

## 自动化与文档归并

本角色未新增/运行自动化测试。caller应为I6补最窄回归，保留其独立code review与既有测试证据。`SPEC.md`、AGENTS与CONTRIBUTING无需变化；IM current spec 的最终归并仍由caller在I6通过后进行。本次报告不把未通过的R2写成current行为。

## Round 2 环境收尾

- 透明代理59029已停止，临时Gateway IM URL恢复直连59021；测试模型与workspace Skill文件已恢复。测试插件已通过真实Uninstall移除，失效工具allowlist也经用户式操作纠正；未触碰dsh-agent-context。
- HEARTBEAT fixture放到实际workspace的`.nanoassistant/HEARTBEAT.md`，非空cron及合成PA前置保留给局部复验。e2e-peer显示快照在最后一次实验中删除，Node恢复后会自然重建；其committed配置未改。
- e2e名称恢复E2E Agent，codexOAuth:gpt-6.1-sol/high及一个deepseek备用保留；专用Feishu渠道已重新新增并实际Connected，无外发消息。
- caller仍拥有隔离IM/Vite。只清理本角色浏览器与代理；Node直连恢复后的最终PID随交接消息提供，不执行e2e-down。

---

# Round 3 — 2026-10-24 I6 局部复验

> mode=full；revalidation_mode=targeted。Validated at：`feb2e1885129bc9479bd29821065101149b6584d`。本轮开始checkout clean；caller冻结Web业务源码，并声明仅修正Skills发现计数确认状态及page接线，无后端/API/保存/恢复逻辑变更。Vite实际服务本checkout；沿用同一隔离栈，不重建无变化的后端。effective_base `55376c111` 的文档/CI增量不改变本轮产品判据。

## Verdict

**pass**。**0 major、0 minor**；Highest Required Action：**none**；needs_re_review=false。I6关闭，I1–I5继续保持关闭。

无快照的空禁用名单和非空禁用名单均显示“Default state has not been confirmed”，不再把未知完整启用数量写成零；真实在线确认的零选择仍能显示零。修正后的信息表达满足R2，连同Round 2已通过／retained证据，R1–R11全部通过。本结论仍限定于报告声明的真实Web体验与caller承担的平台契约范围，不新增原生iOS UI通过声明。

## 四项决定性证据

| 来源与前置 | 结论 | 真实操作与观察 |
|---|---|---|
| I6 / R2：无快照，空explicit_denylist | **pass** | 停止隔离Node后，仅删除e2e-peer显示快照，保留profile。手机390×844从真实入口进入，settings ready=false、source=unavailable、skills_selection_mode=explicit_denylist、skills=[]；Skills总数改为未确认，`0 selected`不存在；保存禁用，模型/已有工具仍可读。[手机](review-evidence/r3-no-snapshot-empty-denylist.png)。 |
| I6 / R2：未知发现集合，非空禁用名单 | **pass** | 在线先把e2e真实47项全部取消并保存，随后停Node并仅删除该Agent显示快照。桌面1440×1000的真实settings ready=false、source=unavailable，profile仍有47个显式禁用名称。完整启用数量显示未确认，没有0 selected；47名称保留为未选只读项。可见分组0/47对应这份显式禁用名单，没有把它当作完整发现集合；下方仍说明完整列表尚未确认。[非空名单](review-evidence/r3-no-snapshot-nonempty-denylist.png)。 |
| I6 / R2：旧快照、新profile | **pass** | 在线读取Global v2快照；离开详情页后真实PATCH description返回200，提交v3，未再次读取settings即停Node。离线settings source=last_known、profile_version=3；页面保留已知名称，Skills总数未确认，分组为—/34、—/12，未沿用旧启用数，也未归零。[版本错位](review-evidence/r3-old-snapshot-new-profile.png)。 |
| I6边界：真实已确认零选择 | **pass** | Node在线时通过真实Config页面取消最后启用的review-offline-skill，PATCH200后重新打开。真实settings ready=true、目录47项、explicit_denylist保存47项，页面0 selected且各组均0；未被一律替换为未知。随后同一配置被用于上一行无快照非空名单试验，证明两种状态的可见区别。[真实零](review-evidence/r3-confirmed-zero.png)。 |

本轮关键截图已逐张打开检查。手机未确认文案在原Skills标题旁完整可读，已保存工具与模型继续可见；桌面没有新增面板或改动既有字段顺序。明确禁用名称与未知发现总数可区分，原有灰色未选样式和只读条件保留。未采用模拟HTTP业务响应。

## 保留证据与范围

Round 2的R1、R3–R11及历史heartbeat/prompt正文证据全部retained；Round 2 I1–I5关闭依据保持有效。原因是本次补丁仅限Skills未知计数表达和其page接线，未改变配置提交、渠道写入、pending/removal恢复、PA、cron、插件或其他分区读取；本轮真实入口也未观察到需要扩大范围的新副作用。不重复完整渠道或Relay丢ACK旅程。

本角色未读取实现、未新增/运行自动化测试。caller所报两文件23测试和前端tsc仅作为交接信息，未替代上述真实体验。后续current spec归并和最终CI由caller完成；不再遗留产品验收阻塞项。

## Round 3 环境释放

恢复本轮临时改动：e2e再次启用原review-offline-skill，其余禁用项保持原值；Global description恢复Round 2结束值。均通过真实配置保存恢复。e2e-peer committed配置从未修改；两个Agent显示快照由Node恢复后正常重建。未更改渠道、cron、PA或插件配置。

Node重新直连59021；未启用代理59029。IM59021/Vite59020继续由caller管理。专用浏览器`bugfix644-review-r3`关闭后释放；本轮没有遗留正在执行的页面动作、路由拦截、临时断流或后台代理。最终Node PID及恢复核验随完成消息提供。

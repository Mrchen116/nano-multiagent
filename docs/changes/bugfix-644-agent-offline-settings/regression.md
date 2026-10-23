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

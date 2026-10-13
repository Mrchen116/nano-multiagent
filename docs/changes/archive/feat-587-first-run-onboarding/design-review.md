# feat-587 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review`（独立子 agent）
- reviewer target: `feat-587-first-run-onboarding`；main `b6b003dd9` 的已提交 spec，加本轮未提交 design/prototype/delta。
- review_mode: `full`
- mode_reason: 首次 Gate 2；覆盖需求、核心空间授权、安装与模型接入、前端旅程、delta 与 M1。
- started_at: 2026-10-13T00:10:00+08:00（开始时间约值）
- completed_at: 2026-10-13T00:16:47+08:00
- duration: 约 6 分钟

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

整体方向服务原始目标：用户只安装电脑端，注册后个人可用；复用现有设备绑定、节点生命周期、配置操作和 DSH 原生模型能力，避免引入另一执行引擎。当前不能放行：delta 无法按既有 canonical 规则归并，必要前端分支尚无可评审的交互与画面，现有整机转移与固定私人空间的交集还需明确裁决。以下问题应在实施前集中修订；不要求提前接真实后端。

### Coverage 与证据

**现状与真实装配入口。** 读取 `apps/im-server/src/server.ts` 的 createServer、preHandler/onSend 与 route registration，确认实际 IM 注册 identity/messaging/control/work/media/trajectory 模块；`identity.ts` 当前以 membership active 放行真人、WS ticket 与机器凭据；`messaging.ts` 的 contacts 全局目录、`work.ts` 和 `task-graphs.ts` 的公司共享表面与设计现状一致。`db.ts` 当前执行 schema 建表，确实需要显式旧库迁移。Web `features/auth/register-page.tsx:80` 当前固定跳 `/membership`，login 根据 membership 决定深链，与设计要修改的入口一致。

**架构与职责。** `apps/node/src/main.ts` 确认 Node 通过 integration/client 管理 stdio RuntimeSupervisor，setup RPC 应在同一链路承接；Node 保有路由/持久配置、integration 对接 credentials/settings/llm 的分工合理。`providers.ts` 当前强制兼容协议和 baseURL，显式 native 路由改动必要。`cli.ts`、`device-binding.ts`、`lifecycle.ts` 是安装后 setup/bind/start 应复用的现有落点。固定空间叠加 owner/participant 比放开 active gate 后逐路由补漏更符合当前共享产品约束；为 conversations/agents/task graphs 固化范围有真实隔离价值，并非无依据抽象。无需新 agent loop、内核 HTTP、全量团队重构或新 supervisor。

独立读取已安装 DSH 0.2.1-alpha.1 的公开 package exports 与 `dsh-authorization`、`dsh-credentials`、`dsh-llm-pi-ai`：authorization.begin/interaction、credential record 与 pi-ai native OAuth/device-code adapter 有现成公开 seam，声明直接依赖后由 integration 使用符合边界。依赖位于 managed worktree `/Users/czj/.codex/worktrees/feat-587-onboarding/nano-multiagent/node_modules/.pnpm/`。未运行第三方真人 OAuth；源码支持不等于真人账号已验收。author 另报告已用空 providers/agents 初始化真实 DSH 并清洁退出；本 reviewer 将该项保留为 author evidence，不冒称独立复跑。

**用户约束与主决定。** S1/S2 的个人与公司分离、旧 pending/suspended 保留、私人历史不随批准扩散均明确；S3–S5 的同源发布包、同一安装器双入口、当前用户目录和幂等恢复有落点；S6–S8 不复制 Codex refresh token，以原生独立授权或已有代理/API 接入，凭据留节点，operation 避免 Gateway 长请求超时；S9–S11 用现有 ConfigurationOperations、稳定候选 ID、状态重建继续首个助手与真实聊天；S12 保留已有用户深链与双语窄屏目标。设计的 scope 与单一 M1 相称，无并行写冲突。前端未完成决定见 R1-W2。

**独立视觉与交互。** 用独立 Playwright session `feat587-review` 实际打开 `http://127.0.0.1:18487/register` 与刷新后的 `http://127.0.0.1:18488/prototype.html`，查看截图而非只读 DOM。走过两种安装选择、模拟连接、模型 API/自定义选择、验证、用途/名称目标、创建、起步任务与模拟回复；检查桌面、768 和 390 宽。原型 chat onclick 修复后能显示消息。浅灰背景、白色卡片、青绿动作与现有注册页连贯，四步导航和安装卡片信息层级明确，768 中间宽度及 390 单列没有可见重叠；纵向滚动合理。模拟控制在产品外侧标注，未被当作真实产品能力。

本轮证据为本机缓存，不提交截图：`output/playwright/feat-587-review-baseline.png`、`feat-587-review-install.png`、`feat-587-review-manual1280.png`、`feat-587-review-model.png`、`feat-587-review-custom.png`、`feat-587-review-assistant768.png`、`feat-587-review-assistant390.png`、`feat-587-review-chat390.png`。这些证明布局和已走查分支，不证明安装、OAuth 或模型请求真实成功。

**delta 与 milestone。** 四个现有 delta 的目标目录正确，新增 onboarding/model/bootstrap 消费者结果大体合适；auth delta 未锚定 canonical 且相关共享条目未同步，见 R1-W1。M1 在 design 中包含 worker/reviewer 双退出标准，单里程碑可行，不要求在空 M1 目录另造重复计划。Runbook 有隔离启动/停止、已有模型代理和录像入口；真实新用户录屏必须继续使用新账号、新安装根和真实回复。OAuth 可控交互证据须与实际第三方账号授权区别报告，不能用代理成功替代 Codex 真人授权成功。

### 历史问题闭环

无；这是首次 full review。

### Issues

#### R1-W1 — auth delta 无同名替换目标，且遗留共享契约会与新行为冲突

- 位置：`specs/im/auth-tenancy.md:1–25`；design「契约层增量」。
- 证据：该文件把「个人可用性与公司资格分离」「固定空间叠加原有对象授权」放在 MODIFIED，但 canonical `docs/specs/im/auth-tenancy.md` 中没有这两个 Requirement 名称。现有「账号注册/登录走 JWT,刷新令牌轮换且可吊销」「Web 认证入口在提交前说清规则并给出可行动反馈」「数据面按登录身份、聊天成员与资源管理归属确定访问」「公司成员资格由管理员批准和停用」仍分别写注册 pending、成功进待批准、所有数据面需公司 active、停用全部机器。`docs/specs/im/agent-work.md` 的共享 Work 和 `docs/specs/im/task-graphs.md` 的公司任务条目也会受新增私人范围影响，但无对应 delta。
- 后果：按 CONTRIBUTING 的同名替换规则无法归并；若作为新增追加，canonical 同时声称新用户立即可用和必须获批，后续实施/验证不能确定该保留哪些旧场景。若粗略替换整章则会丢掉浏览器 Cookie、深链、owner/成员权限等不变场景。
- 要求：以现有同名 Requirement 写完整 MODIFIED 并保留未变 Scenario；真正新规则用 ADDED；为实际改变的 Work/任务共享语义补最小精确 delta（可链接统一空间规则，避免重复全文）。其余 delta 同步标准标题层级。无需重写未影响 canonical。

#### R1-W2 — 必要前端路径仅有文字承诺，原型尚不足以约束实施体验

- 位置：`design.md:75,86–90,116`；`prototype.html` 的模型步骤与最终步骤；S2、S5、S6–S10。
- 独立交互证据：选择「自定义兼容服务」后仍仅有 Key 和「推荐模型」，无协议/地址；Codex 的按钮直接变为已验证，没有 code/link、等待、取消；无本机连接/发现代理没有可切换的代表状态。电脑离线、创建失败和恢复未呈现。最终步骤预先显示助手口吻消息，点击固定周计划后显示模拟回复，「进入聊天」是无行为按钮，没有真实 chat 背景/输入框交接。选择资料研究/编程用途仍只有同一周计划建议；文件位置只有「独立文件夹」描述。全流程未给出「申请加入团队」的产品入口与 pending 后继续个人使用的界面。
- 后果：这些恰是新用户最容易卡住的授权、配置、失败恢复与首次价值交接；只能沿固定成功分支播放，无法判断用户怎样完成自定义代理接入、如何从浏览器去授权再回来、失败后怎样继续、怎样按自己的目标开始工作。此处的 must-match 不能由一句「实施时补充」或仅证明按钮存在来替代。
- 要求：补齐最小可连续操作的必要分支与代表状态（状态可模拟，外层明确标注），将 Codex code/link/等待/取消、自定义服务地址协议、无发现/已有代理、离线/创建失败恢复纳入原型；给团队申请一个可发现入口；明确用途对默认目标/建议的作用和真实文件位置呈现；以现有聊天容器背景展示发送、自写任务及继续聊天的交接，并区分静态欢迎/建议与示例模型回复。无需实现真实 OAuth、安装或后端，也无需重建无关聊天功能。按影响在桌面、768、390 复查后更新 must-match 与 M1 证据。

#### R1-W3 — 整机转移后的私人 Agent/Work 范围尚未裁决

- 位置：design「可复用能力」的跨 owner 转移，以及关键决策 2 的固定空间；需对应 `specs/im/agents-nodes.md` 的设备转移契约。
- 证据：现有 `apps/im-server/src/identity.ts:774–790` 在双端确认提交时更新节点及其所有 Agent 的 owner；本设计保留该流程，又规定 Agent `space_id=personal:<owner>` 固定、Work/trajectory 继承 Agent，但未定义显式转移时空间如何处理。本项由 author 提醒边界后，reviewer 独立检查了真实提交路径。
- 后果：仅复用当前 owner 更新会使接收者拥有设备却无法访问仍属原私人空间的 Agent；若实施者顺手迁移空间，Agent/Work 历史则会随整机转移对接收者开放，当前确认文案和验收没有约束。两种处理有不同的真实用户结果，不能靠实现者临场选择。
- 要求：明确本期选择并落实到最小 delta/确认信息/迁移测试。可以复用既有明确整机转移并定义 Agent 与 Work 历史随转移、原私人会话保持原空间；也可明确限制不支持的私人转移。无需增加空间切换器或新的资源迁移系统，但必须说明旧会话关联、转移后访问与持续事件的边界。

### Recommendations

无额外扩展建议。集中解决上述三项即可复审，不扩成全产品重设计。

### Author resolutions for Round 1

- R1-W1：以 canonical 同名 Requirement 完整复制并只修改受影响 Scenario，auth 四个现有块保留其他场景；新增固定空间规则用 ADDED。补 Work 三个受影响块、任务三个共享块与私人任务新增规则；agents-nodes 的设备绑定/目录使用 MODIFIED。全部 delta 统一标准标题层级。
- R1-W2：补可切换的无发现/代理/Codex、code/link/等待/取消、自定义协议地址、离线恢复、创建失败与核对重试、真实路径样例、用途相关目标与起步建议、团队申请。最终进入现有聊天结构的背景与可继续输入的模拟消息流，示例回复明确标注，删除预置助手欢迎。已用浏览器走通新增分支并查看 1280/390 截图；768 保留此前布局证据，复审可检验新分支。
- R1-W3：保留显式整机转移。私人 Agent 及 Work/trajectory 转入新 owner 私人空间，原会话/附件/任务图空间不变、转移 Agent 不能再读写旧私人空间；公司 Agent 仅能转给公司 active 用户并保持公司空间。双端确认说明工作历史随设备转交，事务同步空间且终止旧 observer，M1 要覆盖转移访问矩阵。

## Round 2

### Metadata

- reviewer: `/root/design_review`（同一独立 reviewer）
- reviewer target: R1 Author resolutions 后的 main 工作区 design/prototype 与七份 delta；未实施产品代码。
- review_mode: `delta`
- mode_reason: 三项有界修订涉及契约替换、既有整机转移的空间消歧与必要 UI 状态补全；原需求、包职责、公开 DSH seam、安装分发和单一 M1 不变。扩大到补入的 Gateway task-graphs delta，核对其与 IM 空间权威的一致性。
- started_at: 2026-10-13T00:22:30+08:00
- completed_at: 2026-10-13T00:26:54+08:00
- duration: 约 4 分钟
- retained_from: Round 1。现状装配入口、DSH 公开 exports、CLI/生命周期复用、无第二执行引擎、隔离安装/真模型录像前置及已看过的注册基线无实质变化，保留其证据。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1 三项均已闭环。方案与增量契约足以约束后续实施；原型展示所需决定和关键恢复状态，不将模拟授权、模型回复或后台事件当作运行验收。

### Coverage 与证据

**契约修订。** 独立逐块读修订 delta，并用一次性只读比较核对 canonical 同名 Requirement 和 Scenario 集：auth 4、agents-nodes 2、Work 3、IM task-graphs 3、Gateway task-graphs 2 个 MODIFIED 均有唯一同名目标。旧 Scenario 仅注册成功的名称随目标行为由待批准改为个人首次设置；其余原有 Scenario 均保留。对注册会话、Cookie/深链、公司准入/停用、目录、Work、任务权限及设备交接的正文逐项核对；新增私人范围以 ADDED 放置，Gateway 任务规则引用 IM 权威空间约束。未改 canonical current 文件。

**空间/转移决定。** `specs/im/auth-tenancy.md` 明确显式整机交接是 Agent 范围变化例外，`specs/im/agents-nodes.md` 明确私人 Agent 与 Work/trajectory 转到接收人私人空间、工作历史随转交且双端确认告知；原会话/附件/任务图保留原空间，转移 Agent 不再读写旧私人空间；公司 Agent 仅转给有效公司成员并保留公司范围。Author resolutions 明确事务同步与旧 observer 终止，M1 新增转移前后访问矩阵。此决定复用 R1 已检查的现有设备提交操作，不新增一套迁移系统，与公司批准不改变私人历史的规则可并存。

**重新渲染和连续操作。** 独立新会话 `feat587-review-r2` 重新打开已更新的 18488 原型，非沿用作者截图。实际执行 Codex 开始→看到 code/link/等待→取消，无现成连接→自定义服务，选择代理→验证→资料研究→创建失败/核对→恢复→创建→进入聊天→研究起步建议→发送→另写任务再次发送；另从 header 申请团队并在 pending 后返回个人设置。检查真实呈现的 1280 授权与聊天、768 创建失败及工作目录、390 自定义地址/协议/团队/聊天画面。页内主操作和结果清楚，恢复状态不掩盖下一步；长路径换行和窄屏表单可读，未见遮挡或横向溢出。聊天保留导航背景、用户任务/示例回复区别和可继续输入的出口；不要求原型重新实现整个既有客户端。

本轮本机截图：`output/playwright/feat-587-review-r2-oauth.png`、`feat-587-review-r2-custom390.png`、`feat-587-review-r2-team390.png`、`feat-587-review-r2-create-failure768.png`、`feat-587-review-r2-chat390.png`、`feat-587-review-r2-chat1280.png`。查看了这些像素；页面可见一次性代码是原型样例，没有访问第三方授权网站。更新后的 design 已覆盖相关 must-match 与 M1 用户结果/实施证据；离线状态与同身份恢复动作已呈现在原型，并由运行期验收继续验证。

**验收边界。** 空 DSH 初始化继续引用 author 真实运行证据。Gate 2 通过不等于 installer、所有权迁移、模型调用或新用户视频已经通过；这些仍按 M1 真栈执行。原生 OAuth 交互测试与真实第三方账号授权证据仍需分开报告。除契约补齐和明确转移例外，本轮没有扩大安装/模型路由的实现范围。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮独立证据 | 结论 |
|---|---|---|---|
| R1-W1 | 同名完整 MODIFIED，保留旧场景；补 Work、设备、IM/Gateway 任务 | 14 个 MODIFIED 全部匹配 canonical；唯一 Scenario 名称变更是目标内注册成功路径；正文无再将私人使用强制公司 active 的整体规则 | closed |
| R1-W2 | 补授权、模型分支、恢复、团队、用途/路径和聊天交接 | 新 Playwright 会话真实点击并查看上述多宽度画面；code/cancel、自定义地址、pending 继续、研究目标/建议和两轮聊天均可到达 | closed |
| R1-W3 | 明确转移例外、历史告知和旧资源边界 | auth 例外引用 + devices 整机交接完整 Scenario + author 事务/observer 裁决 + M1 转移访问矩阵 | closed |

### Issues

无。

### Recommendations

无新增建议。按既定单一 M1 实施并完成真实体验验收。

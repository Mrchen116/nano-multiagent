# Design Review — feat-588-model-service-management

## Round 1

### Metadata

- reviewer_target: `/root/models_design_review`，独立 change-design-reviewer；仅写本报告，不修改设计或实现。
- review_mode: `full`
- mode_reason: 首次 Gate 2，覆盖 S1–S9、全部关键决定、两份 delta、原型和 M1；没有可 retained 的旧轮次。
- started_at: `2026-10-13T09:51:45+08:00`
- completed_at: `2026-10-13T09:58:19+08:00`
- duration: 6 分 34 秒；计时以独立浏览器会话创建为起点，前置资料读取不计。
- baseline: 主仓 `main@f8a0aab1d46f3ede0fc6fd22c97d030a560d1525`；实现前置按 `origin/codex/feat-587-first-run-onboarding@7083a0936a9ad6afa92fc2f5d7ac127ff8178d57` 的 `git show` 核对。没有把主仓尚不存在的 feat-587 代码误判为缺实现。
- DSH reference: `5badb15009ae1756c3afe0ae0cef1faafc290ccc`，本地源码公开接口；本轮未安装或运行新的 DSH 包。
- scope update: 收到主 Agent 转达的用户安装分发决定后，再读最新 `spec.md`、`design.md`、`specs/im/agents-nodes.md`；S9、decision 7、安装分发、M1 F/G 均纳入本轮。未将侧聊授权更新遗漏或另造重复轮次。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。Gate 2 尚未通过。**

API 优先及常驻服务管理的总体方向成立；现有模块与 DSH 公开接口足以承载主要能力。仍需闭合提交的可见性边界，并修正两处会使实施偏离已定需求的原型交互。不是要求先实现后端，也不要求新增真人厂商密钥验收。

### Coverage 与证据

**现状和组装入口。** 阅读 `docs/README.md`、`SPEC.md`、current IM/Gateway 对应契约及 feat-587 同路径增量。核对前置版本 `apps/node/src/main.ts` 中 ModelSetup 实例、relay、RuntimeSupervisor、ConfigurationOperations 的真实接线；并阅读 Node `model-setup.ts`、`configuration.ts`、`providers.ts`，integration `model-setup.ts`/公开 client，以及 IM `onboarding.ts`。现状所述仅能新增、全局 model name 冲突、API 次要入口、owner 双侧检查和白名单状态投影均有依据。

**职责与复用。** Node 持有 YAML、产品模型引用、依赖与写队列；integration 持有 DSH settings/credential/profile/stream；IM 负责 owner relay 与非敏感投影，Web 共用编辑器。职责与 SPEC 一致，不应把 DSH 结构继续上推 PA/IM。复用 RuntimeClient 创建短命探测进程相较替换 live 配置探测有明确收益：坏 key/坏 URL 测试不污染现有助手；不是第二套 Agent Loop。代价是进程启动与清理，设计已限制无 Agent/独立 home/finally 清理，规模适当。共享写队列复用合理，但其覆盖边界见 R1-W2。

**公开接口可行性。** DSH `llm/src/index.ts` 有 `listConfigurableProviders`；`llm-pi-ai/src/index.ts` 注册完整目录与 discovery，并公开导出 `recordKeyFor`、profile 类型与协议列表。既有 integration 已用公开 credentials、settings、authorization 和 stream。`llm-pi-ai/src/adapter.ts:329` 起说明每次 stream 捕获 profile/model，credential 随调用解析；没有单次 generate 的 key/baseURL 覆盖，因此隔离 probe 有依据。目录 metadata 本身不含统一 auth-kind 字段，实施需用公开授权信息/明确映射区分 OAuth 与 API，不能假设 directory 有此字段或导入私有 catalog；列为 R1-R1 的实现提示，不据此扩大需求。

**S1–S5 与 S8 的产品体验。** 独立 Playwright 会话 `review588r1` 实际访问 `http://127.0.0.1:18487/prototype.html`，查看画面并操作，未复用作者浏览器会话。看过前置真实手机截图 `review-587-api-error-narrow.png`；它原有集中式步骤、青绿主动作、卡片和错误反馈成为对照。新版列表先明确电脑，再按服务展示模型与操作；编辑器把 API 入口前置，密钥提示与保存反馈清晰。1440、768、390 宽度下，名称/字段/按钮有清晰层级，手机模型 ID 与名称分行，未出现横向挤压。实际完成首次 API 示例 key→测试保存→继续创建助手→示例聊天；聊天被标为静态背景，不当作真实推理。常驻自定义服务编辑与多模型列表也实际检查。稳定服务身份在编辑态有一处相反交互，见 R1-W3。

**S6–S7。** 失败反馈靠近保存区、服务依赖提示能指明两个助手及主/备用用途，整体可读。实际走了编辑草稿→离线→恢复，以及冲突→重新载入动作；恢复体验不兑现设计，见 R1-W1。修正前 M1 C 所对应 must-match 不能放行。依赖检查包含默认隐式引用、备用和审批模型，设计覆盖充分；并发检查与 live 变更顺序仍需消歧。

**S9 分发。** 对照前置 `apps/im-server/src/install.ts`、`assets/install.sh`、`scripts/build-node-release.mjs` 与现有 CI 入口。沿用 allowlist 打包、哈希命名安装目录和完成后提升；IM 只提供固定 manifest/脚本，旧包地址用 302，curl 已支持跟随跳转。固定完整 SHA/tag、匿名下载校验后才提升 manifest、IM/manifest 同时回退的方案闭合。暂无 Release 发布不阻塞设计；真实匿名下载被明确留给发布阶段，不能把 fixture 下载当作 GitHub 发布验收。

**Delta 与 milestone。** 两份 ADDED delta 分别落在 IM 的 owner/入口/反馈/安装消费者契约，以及 Gateway 的路由引用/持久化/并发/凭据契约，canonical target 正确。没有 MODIFIED 丢旧 Scenario。前置的发现连接能力仍可保留为次要路径，新增 API 优先不要求删掉旧能力。M1 单组覆盖整个闭环，没有并行文件冲突；A/B/C 投影前端 must-match，D/E 投影实现及真实证据，F/G 覆盖安装增量；M1 目录当前仅骨架符合设计阶段。

**验收资源。** 主 Agent 提供既有 LLM_PROXY 真推理基线，并报告外部隔离 fixture 已在 18489/18490 启动、错误 key 401、正确 key 转发真实推理。本 reviewer 独立请求 `18489/health` 得到 `{"ok":true}`；未在本轮重新调用 LLM，故不把转发成功报告写成独立实测。本 unit 不要求所有云厂商真人 key，隔离端点适用于 key、URL、同名/多模型与旧连接保持验证；真实客户端、重启及权限仍属实施后验收。

本轮截图缓存位于仓库本地 `output/playwright/`（不提交）：`review588r1-desktop.png`、`review588r1-tablet.png`、`review588r1-mobile.png`、`review588r1-conflict.png`、`review588r1-journey.png`、`review588r1-dependency.png`、`review588r1-error.png`、`review588r1-provider-edit.png`。已实际查看桌面、平板、手机、冲突、旅程、依赖及失败图片；provider-edit 另有实际控件操作与快照佐证。控制台唯一 error 为 favicon 404，不影响这些判断。

### 历史问题闭环

无：本轮为 R1，没有历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 离线恢复丢草稿，冲突恢复没有可核对的新配置

- 位置：`prototype.html` 的 `showOffline` / `showError` / `setPage`；`design.md` 产品 RPC、原型 must-match 第三项；S6。
- 证据：在团队服务编辑器将名称填为“保留草稿-审查”，触发电脑离线再点“重新检查连接”，回到原服务列表，草稿消失。冲突后点“重新载入配置并核对草稿”，仅清掉提示并启用原表单保存；没有新配置、差异或选择界面。源码进一步确认前者替换 content，后者只复位 conflict/disabled。
- 后果：正常掉线需要用户重填；并发编辑时用户无法知道另一页面改了什么，表面恢复容易再次覆盖。它们正是本次 must-match 的恢复旅程，不能以“原型不接后端”为由省略可见的模拟结果。
- 收口要求：用代表性新旧值模拟一次离线保留/恢复与冲突核对；明确保留草稿、当前服务器值及重新应用选择的关系。无需做通用 diff 系统，但不能把“重新载入”实现成仅解除保存锁。

#### R1-W2 — stage、最终依赖检查与 live 生效的先后关系未闭合

- 位置：`design.md:38-39`、`design.md:58`；Gateway delta 的失败恢复/拒绝在用引用移除；S6/S7。
- 证据：文字顺序是“live integration … stage”→“Node 在持久化队列中再次检查 revision/依赖”→落盘→finish，但接口没有定义 stage 是仅内存候选还是已修改 live settings/credential。前置 `NativeModelSetup.apply` 的 settings.mutate 会立即改变模型路由；DSH adapter 每次 stream 读取新快照，不受 Node 的 YAML 写队列保护。现有 `ConfigurationOperations` 则先 persist 再 apply，并有独立 Agent 队列。
- 后果：若 stage 已 live apply，删除初检后另一个 Agent 在写队列先保存对此模型的引用，stage 可先撤掉路由，随后最终检查才拒绝并恢复；中间已有合法助手能撞上暂时缺失的连接。若 stage 只是内存暂存，则真正 live apply 落在 finish、YAML 已落盘之后，apply/finish 失败如何恢复 YAML/profile/key 又未定义。实施者按两种理解都会得到不同失败语义。
- 收口要求：给出一个明确提交边界，说明最终 revision/依赖检查、live apply、YAML、finish/rollback 哪些处于同一个 Node 提交临界区，以及失败后哪份配置权威；旧连接何时仍可见也应明确。复用现有队列即可，不要求新数据库或分布式事务框架。加一条删除与 Agent 保存交错的窄验证，以及选定提交边界的失败验证。

#### R1-W3 — 编辑已有内置服务仍可切换厂商，与稳定服务身份相冲突

- 位置：`prototype.html` 的 `renderEditor` / `catalogChanged`；`design.md:36-37`。
- 证据：实际打开“编辑 DeepSeek”后，服务商下拉可改成 OpenAI，模型立刻变为 gpt-4.1；标题仍为“编辑 DeepSeek”，密钥仍提示“已保存 / 留空保留当前密钥”，保存可用。与“内置 provider ID 固定”“服务 ID 不改”的设计决定不一致。
- 后果：用户会理解为可把现有 DeepSeek 连接原地改成 OpenAI，并沿用旧密钥和助手引用；按冻结原型实施会使服务身份、凭据含义和模型迁移保护产生歧义。
- 收口要求：已有服务明确固定厂商身份，改厂商走新增服务；仅在创建态允许选择。同步原型与 must-match，并走一次已有内置服务编辑验证。无需改变已确认的服务 ID 策略。

### Recommendations

- R1-R1：实施目录分类时先核对锁定安装的公开 authorization/provider 信息。`LlmConfigurableProvider` 提供 namespace/declared 等字段，不直接提供 auth-kind；将必要分类留在 integration，避免把私有 DSH catalog 或 provider 特例扩散到前端与 Node。

### 下一轮范围

作者追加 resolutions 后，按真实修订选择 closure 或 delta：R1-W1/W3 需实际操作修订原型；R1-W2 涉及提交职责与共享接口，至少复查更新的数据流与波及 delta/M1。其余安装分发与既有架构证据可保留；若边界发生实质扩大则再扩审。

### Author Resolutions — Round 1

- **R1-W1 accepted**：原型离线改为保留现有表单并禁用保存；恢复保留全部输入。冲突新增电脑最新服务/地址/模型摘要及“使用电脑上的配置 / 核对后重新应用我的修改”两个明确动作。design 产品 RPC/提交段说明 revision 仅在明确选择后更新。作者实际浏览器走查和截图见 evidence/prototype-review.md 的 R1 修正段。
- **R1-W2 accepted**：design 新增“提交临界区与失败权威”，最终 revision/依赖检查先于 stage，并与 live apply、YAML 写和失败 rollback 位于同一现有 Node persistence 队列；Agent write 在队列内重新 resolve。finish 成功仅释放内存，无第二次持久化。定义失败与成功的配置权威，并将交错保存/删除及 stage/YAML 失败验证投影到 M1 D。未新增数据库或事务框架。
- **R1-W3 accepted**：已有内置服务商下拉禁用且提示新增服务路径；创建态仍允许选择。原型实际断言已有 DeepSeek 下拉 disabled；must-match 增加已有厂商只读约束。
- **R1-R1 accepted**：实施目录分类留在 integration，先核对锁定安装的公开目录/授权信息，不依赖不存在的 auth-kind，不做 private import。必要的小型 OAuth 分类不会扩散到 Web/Node。

## Round 2

### Metadata

- reviewer_target: `/root/models_design_review`，与 R1 相同的独立 reviewer。
- review_mode: `delta`
- mode_reason: 修正涉及共享提交接口及失败权威，超过单纯文字 closure；影响范围限于 R1-W1/W2/W3、前端恢复状态、原型契约和 M1 D，不改变需求、模块依赖、安装分发或 milestone 划分。
- started_at: `2026-10-13T10:03:12+08:00`
- completed_at: `2026-10-13T10:06:33+08:00`
- duration: 3 分 21 秒；计时以独立浏览器会话创建为起点。
- baseline: 再次确认 main `f8a0aab1d`、前置实现 `7083a0936`；本轮读取冻结的 design、prototype、evidence 和 R1 Author Resolutions。
- retained_from: `Round 1`。实际组装入口、DSH 公开能力、稳定引用设计、IM owner 投影、两份 delta 的 canonical target、S9 固定版本 GitHub 分发及验收资源未受本轮修正影响，保留原证据与判断。真实产品/发布验收仍未执行。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 通过。**

三项 R1 问题均已在设计层闭环。此结论批准设计进入实施，不代表已实现提交事务、通过真实故障注入或完成生产发布。

### Coverage 与证据

**提交职责与接口增量。** 重新审阅 decision 4/5、本机 stage/finish、“提交临界区与失败权威”和 M1 D。现在由现有 Node persistence 队列包住最终 revision/依赖检查、live stage、YAML 提交及失败回滚；Agent write 在同队列再次 resolve。ModelSetup 用 apply/rollback 回调接线，NodeConfiguration 不 import DSH，integration 继续负责 profile/key 变更。相比新增事务管理器，该扩展保持现有职责且能消除 R1 所指的“先撤路由、后发现新依赖”交错。成功权威在 YAML/revision，finish(true) 仅释放快照，失败不再有两种相反理解。M1 D 已要求双向交错及 stage/YAML 失败验证，能检验用户结果而不只检查内部调用顺序。

**原型独立复验。** 使用新 Playwright 会话 `review588r2`，390×844 实际操作并看图：打开已有 DeepSeek，厂商下拉为 disabled，旁边说明更换服务商需新增；打开团队服务，将名称改为“R2独立草稿”、地址改为 `https://draft.example.com/v1`，触发离线时保存禁用且输入仍在，恢复后两个值与模型列表保留。随后触发冲突，保存保持禁用；点击查看最新配置能看到另一页面的名称、地址和单模型摘要，与当前两模型草稿明确区分。

实际分别操作两个恢复选择：“核对后重新应用我的修改”保留草稿并要求再次测试保存；再次触发冲突后选“使用电脑上的配置”，名称、地址和模型全部切换为展示过的最新值。没有只凭 DOM、作者断言或截图文字判定恢复成功。手机完整截图 `output/playwright/review588r2-recovered.png`、`output/playwright/review588r2-conflict.png` 已实际查看：长名称/地址换行，反馈位于保存区上方，两个决策动作可辨认可触达。其他宽度的容器与布局未修改，沿用 R1 的 768/1440 证据；未发现需要扩大整页重审的视觉变化。

**契约和波及面。** must-match 增加“已有服务厂商只读”，与稳定 provider ID 决策一致。离线/冲突修正兑现既有 S6，未改变 spec/delta；M1 C 承接恢复体验，M1 D 承接新增提交边界检查。S9 及 F/G 未改，R1 审查仍有效。无需新建 milestone、修改上游 DSH 或扩大权限/数据存储范围。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-W1 | 离线保留表单；冲突展示最新配置并提供两个选择 | 独立填名称/URL→离线→恢复均保留；两个冲突恢复分支分别实际操作，结果符合标签；390 完整图已查看 | closed |
| R1-W2 | 最终检查移到 stage 前且同队列；定义 YAML 成功与回滚边界 | 重读新增临界区四步、回调职责、Agent 再 resolve、无 I/O 的 finish；M1 D 已覆盖交错与失败 | closed |
| R1-W3 | 已有厂商只读，新增态仍可选择 | 实际进入已有 DeepSeek，控件 disabled 且有新增服务说明；must-match 同步固定身份 | closed |

### Issues

无新增 CRITICAL 或 WARNING。

### Recommendations

- R2-R1：实现“执行子进程退出后恢复旧凭据”分支时，可复用已有仅本机的 credential RPC，在 live stage 前让 Node 的操作内存保留不透明旧 API record，恢复后清理；不能依赖已经退出的 integration 内存快照，也不应为此新增凭据数据库。属于实现中对既定回滚责任的落实，不增加跨 Node 进程崩溃的持久事务要求。
- R1-R1 的公开目录分类建议继续有效，作者已接受。其余验证按既定 M1 收口，不再为假设性故障扩大设计范围。

### Author Resolutions — Round 2

作者核对 R2 的逐项闭环与独立原型证据，无实质异议；R1-R1 公开目录分类提示保留为实施约束。R2 后受审设计/需求/delta/原型无语义修改，Gate 2 有效。

## Round 3

### Metadata

- reviewer_target: `/root/models_design_review`，独立 reviewer；未修改产品实现。
- review_mode: `delta`
- mode_reason: 用户实际试用否定旧 UI，故本轮重新检查全部受影响 UI 的信息组织、密度、视觉关系及操作；后端提交边界、接口、模型引用、权限和安装分发未发生设计变化。采用有界 UI delta，不以 R2 Approved 保留旧 UI 判断。
- started_at: `2026-10-13T11:28:52+08:00`
- completed_at: `2026-10-13T11:33:54+08:00`
- duration: 5 分 2 秒。
- checkout: `/Users/czj/.codex/worktrees/feat-588-model-services/nano-multiagent`，`codex/feat-588-model-services`。已有大量实施 dirty/untracked，全部保留。本轮只追加报告和本地审查截图缓存。
- reviewed: design 的“2026-10-13 UI 设计修订”及 must-match、最新 prototype、evidence Round 3；另读 design 其余段落确认波及边界。
- retained_from: `Round 2` 的后端契约、职责/公开接口和提交边界，以及 `Round 1` 的安装分发/两份 delta canonical target。旧 UI 的视觉完成度结论不 retained。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。本次 UI 修订尚未通过 Gate 2。**

新的设置组织方向成立：服务内容成为主体，电脑上下文从大卡片变为紧凑一行，常用编辑与低强调移除稳定同行，订阅授权反馈回到自己的区域。它解决了用户截图里真实存在的层级和空间浪费；但手机编辑遮挡与电脑归属切换仍会影响正常操作，不能按“比旧版紧凑、无横向溢出”直接放行。

### Coverage 与证据

**从用户实际落差重新判断。** 实际查看用户提供的桌面截图 `codex-clipboard-7dfebbdb-dd7b-4ce2-bc49-cc3fc991fd76.png` 和手机截图 `codex-clipboard-13fd9cf8-317a-4995-a02e-0ea871f5c085.png`。旧界面的问题不是缺功能：眉题/大标题/介绍/电脑卡片/章节标题连续占据首屏；授权横幅插到服务前，首字头像、模型标签、编辑及红色移除均抢主次；手机操作换行进一步放大行高。R1 的“能阅读、无挤压”不足以衡量用户完成设置的整体成本，本轮不再以该标准替代体验判断。

**参考采用合理。** 核对本机 DSH `ModelsSection.module.css` 的 720px 内容宽、16px 标题、14px 服务名、紧凑 row/actions 和按需 editor 组织。新方案借用了层级关系而非照搬整个 DSH 设置；Nano 保留多电脑归属、真实测试和恢复路径，有产品依据。

**独立画面。** 新会话 `review588r3` 只访问 18487 原型，未访问或操作用户的 52267 服务、真实 OAuth 或模型数据。重新渲染 1440×900、768×1024、390×844，不依赖作者小修前的截图。实际查看桌面/手机列表、订阅授权、手机/平板编辑、失败反馈与首次模型步骤。桌面阅读宽度收敛，标题与新增主操作对齐；手机正常首屏同时呈现电脑、两项服务、添加和订阅入口，信息按服务名→类型→模型读取。普通编辑动作不会因手机窄屏另起一行，授权卡片不再推动服务离开视野。

**代表性内容和操作。** 实际从列表进入编辑、展开订阅并触发模拟授权、进入首次 API、切换自定义、触发测试失败/冲突；修改示例服务为“工作室共享推理服务与日常办公模型”，模型为 `us.anthropic.claude-sonnet-4-5-20250929-v1:0`，模拟保存后名称与长模型能换行，编辑/移除仍可辨认。平板编辑的地址/协议双列、两行模型、贴近提交区的失败信息组织清楚。手机新增保留 API 优先，订阅为次要入口。新增、编辑与失败状态的总体组织不需要再扩大重设计；具体遮挡见 R3-W1。

**历史功能和架构波及。** R1-W2 后端提交决策仍 closed，本次不复做实现审查或故障注入。原型保留 R1-W1 的草稿/冲突恢复函数及 R1-W3 的已有厂商只读处理，没有理由据 UI 重排要求改后端或另加事务机制；实际产品仍须按 M1 验收。此次新增的“编辑中电脑禁切换”责任是前端保持操作上下文，与 Node owner/RPC 权限互补，不能依靠后端权限替代，见 R3-W2。must-match 与 M1 A/B/C 的对应关系成立，非敏感数据契约和安装分发没有波及。

本轮截图缓存位于本 worktree `output/playwright/`：`review588r3-desktop.png`、`review588r3-mobile.png`、`review588r3-auth.png`、`review588r3-editor.png`、`review588r3-edit-focused.png`、`review588r3-long-list.png`、`review588r3-tablet.png`、`review588r3-error.png`、`review588r3-onboarding.png`；均已实际查看。缓存不提交。`git diff --check` 对本 unit 通过，不把它作为视觉证据。

### 历史问题闭环

- R1-W1：数据保留/冲突选择逻辑未改，R2 的功能闭环 retained；本轮发现的新手机布局遮挡单列 R3-W1，不回写旧结论。
- R1-W2：提交顺序及失败权威设计未变，retained closed。
- R1-W3：已有内置厂商仍只读，已有编辑态进一步去掉不可切换的方式 tabs；retained closed。
- 用户对旧 UI 的新反馈：已转化为当前修订段及整体体验检查。旧 UI 视觉批准不再作为本轮的通过依据。

### Issues

#### R3-W1 — 手机悬浮保存栏遮挡正在填写的模型名称

- 位置：`prototype.html` 的手机 `.footer { position:sticky; bottom:0; ... }`；design 的“提交紧邻表单底部”和编辑区 must-match。
- 证据：390×844，打开团队服务的两模型编辑器，保存栏悬在第一模型显示名称附近；实际向第一个“模型显示名称”填入 `Review display name` 并聚焦，输入值与光标所在区域仍被保存栏盖住。`review588r3-edit-focused.png` 是当时的 viewport 截图，`review588r3-editor.png` 显示栏跨在模型行中间及剩余表单。不是仅从 full-page 截图推断。
- 用户代价：正常填写时看不到输入结果，保存区看起来像表单终点却还有模型与高级设置在后方；用户需额外猜测滚动位置才能核对。提高保存按钮可达性不能以遮挡当前工作内容为代价。
- 收口要求：优先让提交区回到自然表单末尾；若保留 sticky，需留足滚动/焦点避让空间，证明每个模型 ID、显示名称、移除和错误反馈在点击/键盘聚焦后都能完整看到。只修受影响手机编辑，不要求重做桌面。

#### R3-W2 — 编辑中仍能切换电脑，表单与归属说明出现矛盾

- 位置：design “2026-10-13 UI 设计修订”电脑上下文条目；`prototype.html` 的电脑 select 与 `renderEditor`。
- 证据：实际编辑团队服务时，电脑下拉仍可从 MacBook Air 切到“工作室 Mac mini”；原表单及已保存密钥状态继续显示，说明仍写“密钥保存在 MacBook Air”。`review588r3-tablet.png` 同时显示 Mac mini 标题上下文和 MacBook Air 密钥说明。原型与本轮明确的“编辑时禁切换”决定相反。
- 用户代价：用户无法确定当前更改会作用在哪台电脑；相同服务名存在于多机时尤其容易误判。这里不是要求原型接真实后端，而是它必须表达已经选定的编辑归属约束。
- 收口要求：进入新增/编辑即固定所选电脑，返回列表/取消后才能切换；文字与固定上下文一致。将这一点补进 must-match 并复查进入、取消、返回及保存结果，避免只在文档中承诺。

### Recommendations

- R3-R1：设计段写“移除为低强调图标动作”，原型仍是低强调文字“移除”。当前文字不妨碍辨认，也没有重新争夺主次，因此不阻断；实施前统一文字与图标的选择即可，不必为追求图标增加用户识别成本。

### 下一轮范围

两处局部 UI 问题修正后可做 closure：独立看手机字段聚焦/滚动及电脑固定路径，保留本轮列表密度、授权局部化、三宽度和长内容的判断。若因此改变整套编辑组织，再按真实影响扩大到 delta。产品代码与用户正在使用的服务无需为本轮设计复审被重启或改写。

### Author Resolutions (Round 3)

- R3-W1 accepted：手机 footer 回到自然文档流，移除 sticky；design 明确不得悬浮遮挡。
- R3-W2 accepted：renderEditor 禁用电脑选择器，renderList 解锁；密钥归属文字取当前所选电脑，取消/保存/返回均回到列表。must-match 加入编辑中固定归属。
- R3-R1 accepted：统一低强调文字“移除”，既保持识别也避免增加图标说明。

## Round 4

### Metadata

- reviewer_target: `/root/models_design_review`，独立 reviewer；未修改产品实现。
- review_mode: `closure`
- mode_reason: 本轮只修手机提交栏定位、编辑电脑固定与对应说明，没有改变整套编辑组织；按 R3 下一轮范围逐项闭环。
- started_at: `2026-10-13T11:35:17+08:00`
- completed_at: `2026-10-13T11:39:04+08:00`
- duration: 3 分 47 秒。
- checkout: `/Users/czj/.codex/worktrees/feat-588-model-services/nano-multiagent`，`codex/feat-588-model-services`；保留已有 dirty/untracked，只追加本报告与本地截图缓存。
- reviewed: R3 Author Resolutions、design 修订段及 must-match、最新原型中的受影响路径。
- retained_from: R3 的列表密度、授权局部化、1440/768/390 与长内容判断；R2 的后端契约和提交边界；R1 的安装分发与 delta canonical target。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。R3 两项 WARNING 已闭环，当前设计通过 Gate 2。**

此结论是设计与原型审查，不替代真实产品的 M1 验收，也不表示当前实施或部署已通过。

### Coverage 与证据

使用全新独立 Playwright 会话 `review588r4`，仅访问 `http://127.0.0.1:18487/prototype.html`，390×844 实际操作；未操作用户的 52267 服务、真实模型配置或 OAuth。

**手机填写与提交区。** 进入两模型团队服务，向第一个模型显示名称填入 `Review display name R4` 并保持焦点，实际查看 viewport 截图 `output/playwright/review588r4-focused.png`：字段、文字及聚焦框完整可见，保存栏不再盖在其上。又填写第二个模型名称，实际查看 `review588r4-second.png` 的滚动后 viewport；页面按自然高度滚动，没有悬浮提交层。完整查看 `review588r4-editor.png`，两模型及高级设置之后才是取消/测试并保存，表单的结束位置明确。design 同步写明自然末尾与不得悬浮遮挡。本轮没有移动其余控件或要求新增滚动补偿机制。

**电脑上下文。** 在列表选择“工作室 Mac mini”后进入已有服务，电脑选择器 disabled，密钥说明明确写同一台 Mac mini。实际取消后选择器恢复可用；进入新增同样固定电脑且说明一致，点击“← 模型服务”返回后可切到 MacBook Air；再次编辑时重新固定 MacBook Air，说明随之更新。最后点击模拟测试并保存，成功回到列表且选择器解锁。这些状态来自实际操作与新 snapshot，不仅凭源码判断。must-match 已加入“编辑中固定”，与行为一致。

原型唯一 console error 为未提供 `favicon.ico` 的 404，与本轮路径无关。审查会话已关闭。截图为本地缓存，不提交；未修改实施文件。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R3-W1 | 手机 footer 回到自然流 | 实际填写并查看聚焦 viewport；完整图确认提交区位于所有模型/高级设置之后，第一字段不再受遮挡 | closed |
| R3-W2 | 新增/编辑固定电脑，列表解锁，说明取当前选择 | Mac mini 与 MacBook 两种上下文核实；新增、已有编辑、取消、返回、模拟保存均实际操作 | closed |
| R3-R1 | 统一低强调文字“移除” | design 与当前原型一致；不增加图标识别成本 | accepted |

### Issues 与 Recommendations

无新增 CRITICAL 或 WARNING，也无新增整改要求。保留 R3 已通过的视觉判断及 R2 后端判断；后续按既定 M1 将当前原型与 must-match 落实到真实产品，不因本轮 closure 扩大设计范围。

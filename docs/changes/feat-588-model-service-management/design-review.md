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

# feat-614 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review_614`（独立 change-design-reviewer）
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖首文档、完整设计、delta-spec 与 milestone 骨架，并从产品装配入口核实复用能力和锁定依赖公开接口。
- started_at: 2026-10-15T23:48:00+08:00（约）
- completed_at: 2026-10-15T23:50:54+08:00
- duration: 约 3 分钟
- reviewed checkout: `/Users/czj/Repos/nano-multiagent`，`main`，HEAD `4b152e471`；工作区有既有修改，本轮只写本报告。
- inputs: `spec.md`、`design.md`、`specs/gateway/agent-capabilities.md`、`M1-plugin-development/.gitkeep`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

方案在现有职责和已安装公开 API 内可实施，新增机制与需求规模相称。批准的是设计可执行性；不代表开发 Skill 已交付、真实模型已经理解指导、业务插件已验收或生产已部署。

### Coverage 与证据

#### 现状与产品装配

- `apps/node/src/main.ts:40` 在启动时调用 `installBuiltinSkills`；`packages/personal-assistant/src/builtin-skills.ts:15-58` 从 assets 递归复制完整内置目录并替换旧资源。`scripts/build-node-release.mjs:35-36` 将已跟踪 PA assets 纳入安装包。新增独立 Skill 及其 references/templates 可以复用该链路，无需额外发现服务。
- `packages/dsh-integration/src/agent-config.ts:35-36,89` 实际创建 `WorkspaceExtensions` 并在 preset 装配中 attach；`workspace-tools.ts:52-80` 按真实 workspace 共用 owner、在每个 preset 注册管理工具和挂载树。不是仅测试使用的孤立实现。设计关于共享安装状态、每个 Agent 各有 mount、私有服务不能假定全节点单实例的判断成立。
- `workspace-tools.ts:113-137,154-202` 复用原生 profile、PluginPackages、Loader、PluginManager、Include、HMR 与泄漏审计；现有 refresh 还为每个 mount 的 isolate label 加命名空间。既有机制适合作为生命周期 owner，不需要新插件运行时。
- `docs/specs/gateway/agent-capabilities.md:636` 起的 current Requirement 已覆盖自助安装、提示词贡献、热应用、停用、共享与隔离、第三方依赖及压缩引擎。设计维持这些契约，新增开发知识与当前接口发现，不重复实现生命周期。

#### 关键决定与公开 API

- 查验 `packages/dsh-integration/package.json` 及本机已安装包 manifest：五个 topic 对应的七个包均为 integration 已声明依赖；每个包均声明 `./package.json` export、根公开 types，且 types 文件存在。DSH 包版本为 `0.2.1-alpha.1`，Cordis 为 `4.0.5-alpha.1`，loader 为 `1.0.6-alpha.1`。按 manifest 返回实际文件位置可实现，不需要猜源码目录或依赖参考仓库 HEAD。
- 已安装 `@deepseek-ai/dsh-tools/lib/types/index.d.ts:85-102` 明确 `tools/result` 为按 `exec.agent` scope-filtered 的冻结结果 emit，而 `tools/change` 为 unfiltered。设计只推荐前者作为被动局部监听，并要求按工具名过滤及管理 cleanup，支持面有具体依据。公开声明可见的其他事件不自动获得支持。
- 已安装 `@deepseek-ai/dsh-system-prompt/lib/types/index.d.ts` 的 `section`/`context` 是 scope 注册；同名可遮蔽宿主贡献，`complete` 可替换完整 section。因此设计要求独立命名、禁用完整替换做法，与实际 API 风险匹配。
- 已安装 `@deepseek-ai/dsh-compaction-basic/lib/types/index.d.ts` 公开 `BasicCompactionEngine`、配置、自动/人工压缩方法，并注明 `summarize()` 为唯一 subclass customization hook。设计复用现成引擎、保留事务与配对逻辑，适合当前需求。实施资料应按此已声明扩展点落实。
- `workspace-tools.ts:267-270` 已将 list 查询置于 pending 拒绝之前；设计对 `describe_api` 的只读处理有直接可复用落点。接口 topic 有限、包名非模型输入、返回资料而非另造 API schema，复杂度合理。

#### 用户约束与验收

- 首文档的六类用户场景均在 design 的真实旅程表有对应目标和业务效果证据：工具、提示词、服务/局部监听、压缩、调度/交付组合、宿主边界以及生命周期/失败恢复。
- 用户特别要求观察 Agent 是否理解并创作各种插件。设计明确自然语言任务不注入 Skill 名、参数或代码，保留第一次失败与修复轨迹，记录真正读指导/查 API 的行为，独立 reviewer 自行驱动创作，并将安装、业务结果、持续行为分开。该验收方案可以识别“模板可安装但模型不会开发”的实质失败。
- 报告格式以新聊天贡献和停用撤销验证，索引以文件变化后的查询验证，压缩要求真实事务而非 no-op；不是以 Agent 自述代替效果。工具选择、同 workspace 共享、跨 workspace 隔离和恢复均列入回归。
- runbook 提供隔离启动/停止、配置与代理前置、双 workspace 和同 workspace 对照；通过 IM 产品路径执行，且不宣称浏览器视觉或物理 iOS 验收。本次没有 UI 变更，不需要前端原型。

#### Delta 与 milestone

- delta 路径准确对应 canonical `docs/specs/gateway/agent-capabilities.md`；仅 ADDED 开发指导 Requirement，保留既有生命周期的原 Scenario，不错误覆盖 current。新增条目从使用者角度描述版本准确的指导、选择尊重、范围说明和真实验证，不把内部 topic schema 固化成长期产品契约。
- 单个 M1 覆盖开发发现、资产、相关测试和真实创作验收，退出标准同时包含工程检查与独立产品证据；无多 milestone 并行写入冲突。
- `M1-plugin-development/` 当前仅含 `.gitkeep`，符合 `docs/development/change-workflow.md:109-111` 与 `docs/changes/README.md:65-66` 的设计阶段骨架要求，不需要提前编造 tasks/progress。

#### 架构判断

运行时包解析留在 integration，PA 只持有随包知识资产，Node 复用现有安装和配置路径；依赖方向符合 `SPEC.md:40-50`。管理、持久化、工具选择与资源释放继续归现有 owner；指导不接管权限、路由、消息交付或调度。相较引入完整 DSH inspection 或新 API 注册表，有限 topic 返回公开资料路径避免维护第二份接口事实。可信代码与 OS 沙箱的区别明确，没有用现有 scope 审计作强安全承诺。

### 历史问题闭环

首轮，无历史问题。

### Issues

无。

### Recommendations

无额外要求；按设计中现有真实模型旅程和退出标准执行即可。已有测试本轮只做内容核对，未运行实现验收，也没有以本轮文档审查替代后续业务效果验证。

### Author Resolutions

- R1 无 issue；作者核对公开包资料、现有装配链和验收范围，与审查事实一致，接受 Approved（0/0）。无实质修改，进入默认简化实施流程。

- 交付有效性：真实验收发现的热更新修复仍通过公开loader生命周期兑现原设计更新要求；新增cwd和Cron排队提示仅校准使用指导，没有扩大能力面或改变架构决定。依据design Changelog与独立代码/产品/一致性复验，Gate2结论保留至最终集成tree `a60a3239e`；后续只做已审契约归并与机械归档。

## Round 2

### Metadata

- reviewer target: `/root/design_revision_614`（独立 change-design-reviewer）
- review_mode: `delta`
- mode_reason: 用户明确授权在同一 PR #364 修订知识来源与安装更新语义；本轮复核这些有界变化及其对既有契约、测试和真实模型验收的影响。支持能力、有限 API 发现接口、产品责任边界及单 milestone 结构未扩大，不重开 unit。
- started_at: 2026-10-16T10:44:38+08:00
- completed_at: 2026-10-16T11:05:49+08:00
- duration: 21 分 11 秒
- reviewed checkout: `/Users/czj/.codex/worktrees/feat-614-plugin-development/nano-multiagent`，`codex/feat-614-plugin-development`；HEAD `36ebeed51ea20e4e4157fce7a285b63320b5e6bd`，已集成 `origin/main` `481467ac16f0eda4561fca5c8230050541600de9`。
- reviewed target: 以上 HEAD 加本轮未提交的 `spec.md`、`design.md`、`specs/gateway/agent-capabilities.md` 修订；以 `design.md:5-13` 的“当前交付修订”为目标，后文被明确取代的 generation/在线更新决定仅作历史。
- grounding: 本仓 current 契约、产品装配与锁定安装包；DSH 参考源码 HEAD `5badb15009ae1756c3afe0ae0cef1faafc290ccc` 的原 Skill、PluginManager、HMR 与 profile resolver。
- scope: 只追加本报告，不修改设计或实现、不提交、不执行模型或 runtime 验收。读取期间作者已开始修改 `workspace-tools.test.ts`，仅核对测试处置方向，不将该未验证实现当通过证据。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

修订将包安装与 JavaScript 更新责任交回原生 PluginManager，并保留 Nano 实际需要的 workspace 挂载、选择与审计责任。知识适配和验证边界已明确，可进入实施与受影响门禁复验。本结论不代表新版 Skill 已改善真实 Agent 行为，也不代表原安装更新门禁在新实现上仍有效。

### Coverage 与证据

#### 用户约束与上游知识复用

- `spec.md:17,42-44` 明确记录用户对同 PR、原始 Skill/原生语义、必要 Nano 差异、取消额外热更新承诺及新真实 Agent 普通场景的授权。`design.md:7` 指定新节取代旧决定，因而后文历史 Changelog 中的强制重载做法不是本次目标；无需依据 archive 目录另建生命周期。
- 上游 `packages/preset/agent-preset/skills/cordis-plugin-development/SKILL.md:8-10,20-32` 的主要流程是普通 workspace 文件创作、按需发现、原生安装、检查 application/warnings、实际使用及只修复观察到的缺陷。`design.md:9` 复用这个流程及 bundle manifest/exports/生命周期资料，没有继续维护完整平行教程；来源、适配清单与 MIT 许可有明确落点。已核上游根 `LICENSE` 为 MIT，复制实质内容须保留其版权与许可。
- 上游同 Skill 的默认视觉目的地、Client Slots、宿主 profile、MCP、广域 `cordis_inspect_*` 以及权限提示依赖 DSH 产品组装，不能直接套入 Nano。保留 `describe_api` 有限主题和 Nano workspace/客户端/审批差异是必要适配：本仓 `cordis.patch.yml:9-12` 禁用原生技能文件发现与管理工具，`SPEC.md:33-48` 将运行时接线限定在 integration，Nano 客户端也不消费原生 Web UI 插件。
- `defineTool` 不是新增 Nano DSL：已安装 `dsh-tools/lib/types/index.d.ts:24` 公开导出该 helper，`schema.d.ts:73-84,180-210` 明确 per-property 参数与 canonical output/execute 契约。改为优先复用其公开 DSL、按当前声明支持子集编写资料和模板，能消除原资料中第二种 schema 教程的维护分叉；不需增加另一套 schema 转换器。
- 会话 cwd、workspace 私有服务/cleanup 和 `schedule_run` 排队提醒均有实际边界依据。`workspace-tools.ts:55-82` 以可信 workspace 建立各 preset mount；`index.ts:476-489` 将手动 schedule 输入通过 `agent.followup` 排队后返回输入证据。因此“先交付状态并结束当前轮、随后核实结果”属于 Nano 适配，不应从上游通用插件教程删除。

#### 原生管理语义与复杂度

- 上游 `references/host-plugin.md:68-70` 已写明首次安装可以通过 HMR 激活，但替换已安装包需要 restart 才加载新的模块；`packages/boot/plugin-manager/src/index.ts:573-577` 在 `before` 已含包名时直接返回 `restart-required`，不 refresh/reload。锁定安装包 `dsh-plugin-manager/lib/index.js:1838-1842` 有同样分支，故结论不只依赖参考仓库 HEAD。
- 当前待删除机制的位置明确：`workspace-tools.ts:136-149` 改写 bundle rows 来源，`:179-194` 按路径变化强制释放 fiber，`:232-247` 复制源码到随机 generation，`:328-335` 对本地包继续 refresh 并重写 application。`design.md:11` 完整覆盖这条链的移除与覆盖安装提前返回，避免只删复制逻辑却仍冒称新代码已生效。源码归属校验和禁用状态保持仍归现有 owner。
- 仍保留的挂载/解析是必要 Nano 责任：`agent-config.ts:89` 在实际 preset 装配中 attach，`workspace-tools.ts:114-134` 为 workspace 建立独立 profile/manager 与配置观察，`:198-230,339-347` 负责服务泄漏审计、工具选择和等待卸载清理。原生 manager 的 owner 不持有这些 preset 执行树，`index.ts:781-792` 的原生 refresh/reload 不会替代 Nano 的 workspace mount。继续沿公开 profile 解析与 Include 更新完成首次安装/启停/卸载，没有另造 loader。
- 删除强制 remount 不等于取消必要的卸载等待。上游 `profile-resolution/resolver.ts:126-136` 明确 resolver replace 保留已有模块与 Node cache，包映射要在插件停止后移除；保留异步 cleanup 及卸载后再移除映射，与这一公开约束一致。
- 原生源码 HMR 与覆盖包安装分别成立：上游 `dsh-hmr/README.md:27-47,57,96-97` 将 source roots 设为 opt-in，覆盖安装仍需重启；Nano `client.ts:18-24` 复用 base bundle，锁定 base patch `:27-32` 的 module roots 为 `[]`。本次既不新增 source watcher，也不把启停作为升级保证；“更新待重启，正常 Node/DSH 重启后实调新版”的策略可执行。没有要求运行时 private import、fork 或宿主重启器。

#### Current 契约、delta 与 milestone

- current `agent-capabilities.md:679-698` 的成功安装后即时使用、已加载贡献启停和资源释放仍由首次安装/既有生命周期满足；`:705-708` 更新保持停用、`:710-713` workspace overlay 配置热应用也保留。覆盖源码包更新待重启与配置热应用是不同操作，不需要删除后者。
- 新 delta 对 `docs/specs/gateway/agent-capabilities.md` 的目标锚点正确，完整保留原开发指导 Requirement 的四个 Scenario，并增加 `restart-required` 不得宣称新版可用、重启后实调的 Scenario。相对最新 `origin/main`，该开发指导 Requirement 仍是本 PR 新增内容，保留 `ADDED` 合理；分支上已有上一轮 canonical 归并，收尾应按设计中的 corrected-delta 更新同名条目，不能重复追加。`design.md:13` 已明确安排契约校正复验，当前未提前把目标当成通过后的 current。
- `spec.md:122-129` 的更新、重启与失败恢复仍可满足：重启后实调新版，首次失败源码修复也保留原生待重启结果，而非要求修复必须在线。新增约束 `:44` 与此共同解释生命周期，没有下游必须二选一的未决行为。
- 单 M1 的实现范围仍为 integration、PA 资产、测试与 current docs；新的顶部验证/收尾决定取代旧“生命周期测试 keep”中受影响的热更新断言，其余 milestone 出口保持。没有引入新的共享接口或并行修改冲突。

#### 测试处置与新模型证据

- 受影响覆盖已有具体 owner `packages/dsh-integration/tests/workspace-tools.test.ts`。设计明确 rewrite 原“覆盖后立即执行新版”及“坏源码修复立即可用”断言为原生 pending/restart 链，验证更新后旧调用、启停不能冒称升级、正常进程重启后新版及同 workspace peer。读取时作者的未提交测试已朝此方向修改（`:87-121,165-183`）；本轮未运行这些测试。
- 安装/共享、跨 workspace 隔离、空工具集、禁用选择、忙碌管理、异步 cleanup、模板、压缩和停用回落仍有现有行为保护（测试 `:98-110,137-164,187-212,214-267`），设计要求 keep，而不是因为删除 generation 整体删掉回归。测试仍通过真实锁定 runtime 与公共执行 seam 观察结果，没有增加 generation 路径或逐句文案断言，符合 `docs/development/testing.md:24-36` 的受影响测试处置原则。
- `design.md:12-13,108-121` 对新证据要求充分：全新 DeepSeek/Astra Agent、自然工具/报告/索引监听/压缩/更新目标、不给 Skill 名/API/代码、观察首次失败和实际业务效果，压缩保持默认配置。安装状态、业务调用、用户交付和持续行为分别核对。旧低阈值压力样本与旧热更新成功记录仅为历史，不能证明新指导避免误导。
- main 已集成 feat-615 后使用当前正常 Auto 并重跑本地 CI，避免把旧审核档位故障或曾用的环境修正当作本轮正常产品路径。独立产品 targeted、代码/一致性 delta 和 corrected-delta 均列入收尾，旧门禁只可按真实未受影响范围保留。

#### Retained coverage

- retained_from: **Round 1**。有限主题只读 API 发现、公开资料路径、PA 随包资产与 Node 安装链、技能禁用选择、支持事件/压缩扩展点及无客户端 UI 变化的设计判断继续有效；本轮重新核对 `apps/node/src/main.ts:40`、`builtin-skills.ts:18-61`、`agent-config.ts:89`、`plugin-development.ts:6-50` 与已安装工具公开类型，未发现本次修订改变这些职责。
- 不保留 Round 1 Author Resolutions 中“强制释放 fiber 只是原设计兑现、旧 Gate 2 可覆盖该修复”的有效性判断。用户本次改变了交付决定，已由本 Round 独立重新核查；后续实现、业务与 CI 仍须按新范围验证。

### 历史问题闭环

Round 1 为 0 CRITICAL / 0 WARNING，无历史 issue 待关闭。旧产品 A1 的热更新结果不在本轮重判为“已修复”；本轮批准的是用户授权的语义收敛及新验证方案，旧失败与旧修复记录保持原样。

### Issues

无。

### Recommendations

无新增要求。实施后按当前设计中的测试处置、新 Agent 普通旅程和受影响门禁执行；本轮静态设计审查不能替代其结果。

## Round 3

### Metadata

- reviewer target: `/root/design_revision_614`（独立 change-design-reviewer，承接 Round 2）
- review_mode: `delta`
- mode_reason: 原生语义实施中新增有界的挂载恢复决定，改变派生配置的加载/持久化方式；不是单纯关闭历史 issue。本轮仅审 `design.md:12` 的 EntryTree 内存挂载及其工具归属、父树与清理影响，未受影响范围保留 Round 2。
- started_at: 2026-10-17T00:05:54+08:00
- completed_at: 2026-10-17T00:07:40+08:00
- duration: 1 分 46 秒
- reviewed checkout: `/Users/czj/.codex/worktrees/feat-614-plugin-development/nano-multiagent`，`codex/feat-614-plugin-development`，HEAD `36ebeed51ea20e4e4157fce7a285b63320b5e6bd` 加本次未提交设计/实现修订；上游参考 HEAD `5badb15009ae1756c3afe0ae0cef1faafc290ccc`。
- scope: 只追加评审记录，不修改设计/代码、不提交、不运行模型或重复验收。作者报告的真实 runtime 诊断用于确定审查范围，本轮独立核对源码机制；正在运行的窄测试不作为通过证据。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

由原生 profile 唯一持久化安装与选择状态，再用公开 EntryTree 重建各 preset 的 workspace 挂载，符合用户要求的上游复用与必要 Nano 适配。它移除派生文件的第二条恢复路径，不新增加载器或在线代码更新承诺；设计可以实施，实际恢复及 cleanup 结果仍由受影响测试核实。

### Coverage 与证据

- **公开能力与上游复用**：锁定 `@deepseek-ai/cordis-plugin-loader` 的根 export 同时在运行时 `lib/index.js` 和公开 `lib/types/index.d.ts:13` 导出 EntryTree；`config/tree.d.ts:5-33` 明确树的生命周期接口和内存树可将 `write()` 实现为空。上游 `packages/preset/agent-preset-registry/src/mount.ts:8-24,204-209` 的 PresetTree 正是同一模式；锁定 preset-registry 的 `lib/index.js:63-76` 也包含它，结论不依赖未安装的新接口。Nano 只通过已声明包根消费公开类，没有 import 上游私有 mount 模块或复制一套 loader。
- **恢复与工具归属**：旧 Include 的初始化会先读文件并 `root.update`（上游 `vendor/include/src/index.ts:245-262`），而 Nano `WorkspaceOwner.refresh` 在应用当前 rows 前，把尚未记入 `mount.tools` 的现有工具收入 baseline（`workspace-tools.ts:163-168`），随后从 workspace 工具集合排除 baseline（`:210`）。这条源码顺序支持作者报告的重启后 workspace 工具误归静态、catalog 消失的诊断；本轮没有独立重跑复现。新 `attach` 在 baseline 后创建空内存树，再由 owner.refresh 首次装配（`:83-89`），避免派生 rows 提前注册。`capabilities.ts:40-45` 继续根据既有 installed 集合标注 workspace 来源，不通过放宽白名单或 catalog 特判掩盖归属问题。
- **唯一持久化权威**：`WorkspaceOwner.create/rows` 保留原生 `initProfile`、`loadProfileDirectory` 和 `composeEntries`（`:121-145`）；不再创建、读取或写入 `runtime.json`。上游 app-boot `profile.ts:740-765` 从已选择 bundle layers 与 user overlay 重建 rows，`index.ts:346-355` 已将插入的相对模块路径锚定到各 patch 文件，故移除 Include 的派生文件 baseUrl 不要求另造路径解析。内存树 `write` 为空也不会把 runtime 装配结果反写成另一份安装状态。不清空共享 Include 文件，避免作者已经观察到的其他 preset 重载路线；旧派生文件无需被当成用户安装状态迁移或删除。
- **父树与生命周期**：EntryTree 构造器和 EntryGroup 构造器会分别占用 `ctx.fiber.entry.subtree/subgroup`（上游 `vendor/loader/src/config/tree.ts:15-20`、`group.ts:11-14`）。Nano `WorkspaceTree` 保存并恢复这两个字段（`:33-46`），与上游 PresetTree 一致，保留原 preset inventory 的归属。`attach` 的 scope effect 停止本树并移除 mount（`:87`），对应上游 `mountPreset` 的 scope-owned `tree.root.stop()`；原 owner 的 `root.update`、`auditRows`、服务泄漏检查、异步 fiber.inertia 等待、resolver 收尾以及 close 顺序继续存在（`:175-215,315-323`）。没有将 profile 持久化责任交给内存树，也没有取消等待卸载的约束。
- **契约与测试处置**：本增量恢复既有“重启保留持久选择、workspace 工具在既有/新聊天可用、隔离与工具选择保持”的 current 场景（`agent-capabilities.md:679-698`），没有新增消费者接口或支持能力，因此无需另加 delta Requirement。Round 2 的覆盖安装 `restart-required` 和新 Agent 普通场景要求仍适用。已有 `workspace-tools.test.ts:91-124` 从进程重启、真实工具调用、workspace catalog 来源、显式空集、重复 catalog 和同 workspace peer 观察这条风险；`:189-210` 继续保护异步清理和停用持久化。保留并运行这项相关窄测试即可形成所需工程证据，不需要增加 runtime.json 文本断言、再写一份平行测试或重复全量产品验收。本轮不宣称该测试已完成。

### Retained coverage

- retained_from: **Round 2**。原 Skill 适配、有限 describe_api、原生包更新待重启、工具选择/信任边界、PA 资产交付、单 M1 与新真实 Agent 验证方案未被本项改变，理由与证据沿用。
- Round 2 中关于“继续沿 Include 更新挂载”的实现落点由本轮 EntryTree 决定取代；保留的是公开原生 Loader/EntryGroup 生命周期、审计和清理职责，不将旧 Include 派生文件机制继续视为目标。

### 历史问题闭环

Round 2 无 CRITICAL/WARNING issue。作者新报告的挂载恢复失败有可执行的设计处理及既有测试保护，但本轮不将待完成 runtime 测试记成缺陷已经实证关闭。

### Issues

无。

### Recommendations

无新增要求；记录正在运行的相关测试实际结果，并继续原有受影响代码/一致性门禁即可。

### Author Resolutions

- 作者核对 Round 2/3 的公开接口、上游知识来源、profile 持久化与内存树生命周期，接受 Approved（各 0/0）。实际窄回归随后完成 2/2，通过证据见 [原生语义修订回归](evidence/native-semantics-revision.md)；本轮冻结实现为 `f56e5e6d8`，未将历史热更新或低阈值压力样本作为本次成功证据。
- `f09df0d25` 只在压缩参考中明确既有用户 `/compact` 入口和当前轮结束的交接时机；依据 current `gateway/global-agent.md` 的手动压缩契约与原生 idle 要求。没有新增接口、能力或运行时机制，属于 Round 2 已批准的 Nano 宿主职责/可用环境验证边界补清；保留设计结论，代码/一致性与真实模型对该文案增量另做有界复验。

## Round 4

### Metadata

- reviewer target: `/root/design_revision_614`（独立 change-design-reviewer）
- review_mode: `delta`
- mode_reason: owner 新明确本轮普通模型试用的 acceptance bar，改变证据缺口对整体裁决的处置，而非补证关闭缺口；有界复核其授权依据、与支持契约的区别及是否掩盖实现缺失。
- started_at: 2026-10-17T00:50:33+08:00
- completed_at: 2026-10-17T00:52:37+08:00
- duration: 2 分 4 秒
- reviewed checkout: `/Users/czj/.codex/worktrees/feat-614-plugin-development/nano-multiagent`，`codex/feat-614-plugin-development`；HEAD `f09df0d25dd39d4e17b56ac140077003e4caf17b`，runtime 冻结于 `f56e5e6d89cd496ef0bcdf75816db37313281a63`，加未提交 `spec.md:46-48` 与 `design.md:18` 的证据边界裁决。
- inputs: 最新用户原话、Round 2/3 设计决定、两个冻结版本的指导差异、current/delta 契约、acceptance Round 3/R3-E1、code-review Round 4/5、verification Round 2/3、产品 reviewer 规则；只读核对当前压缩接线、原生公开声明/参考实现及本次合成测试生成的压缩插件。
- scope: 只追加本报告；不改实现、spec/design 或其他报告，不提交，不运行新模型或重复验收，不预判正在进行的独立压缩对照。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

该裁决可作为本轮普通模型试用的明确 acceptance bar，条件是保留自动路径的未观察/证据缺口，不将其改写为 pass、不关闭旧 R3-E1，也不把自动支持契约删减。批准的是证据处置边界，不是产品最终通过或自动路径的新运行证据；其他必验项与独立新对照仍按实际结果裁决。

### Coverage 与证据

- **最新授权与事前范围**：`spec.md:15,17` 的用户原话要求真实常规场景、复用 DSH、仅补必要 Nano 差异；没有要求为达到测试条件新增压力机制。冻结 `f56e5e6d8` 的 design 顶部验证策略已明确默认配置、不给普通任务注入生命周期压力、低阈值旧样本不能证明新指导成功；同版本 compaction reference 已写明自动未发生时报告未观察。上述方法边界早于本轮产品结果，不能解释成因为重复验收失败才临时发明“普通场景”。本次将由此产生的证据限制显式写入 spec，并清楚标为 owner 裁决，没有冒充新的用户原话。
- **支持承诺与证据状态不同**：`spec.md:109-111` 的自动/人工支持场景和 current `agent-capabilities.md:710-713` 均保留；新裁决只限定本次模型指导试用如何收集和报告自动路径证据。用户仍应能在真实自动触发后使用 workspace 引擎，停用后回落；“未观察”不能成为发生自动失败时的免责理由。`acceptance.md:139-140,157,177` 的真实人工186项事务、继续对话及停用后52项默认事务不能替代自动触发证明；本轮也没有如此使用它们。无需修改支持能力的 canonical/delta，亦不能据这项方法裁决宣称自动/人工全场景均已验收。
- **当前没有被文档掩盖的已知实现缺失**：`36ebeed51..f56e5e6d8` 未修改 integration 的 `compaction.ts`；该文件 `:17-25` 继续对 preset 引擎让出自动触发并将人工命令路由到其 `compactNow`。本次生成的 `decision-compaction/compaction.mjs:46-60` 只继承 BasicCompactionEngine 并覆写 summarize，bundle patch 以隔离 compaction provider 挂载，没有 `auto:false`、删除监听或仅实现人工路径。锁定公开 `dsh-compaction-basic` 声明明确 auto 默认 true、阈值0.8/保留0.16；参考实现 `packages/compaction/compaction-basic/src/index.ts:137-140,158-165,269-308` 保留自动 pre-step 监听和压力判断。因此没有具体证据支持“本次实现根本不提供自动路径”；但静态存在及人工通过同样不能证明这个新普通模型样本已成功走过自动路径，也不能据此断言未发生的具体原因必为阈值不足。
- **规则允许的是有条件 pass-with-issues**：产品 reviewer skill `:22-24` 要求每项有证据状态、必验 fail/inconclusive 不得直接通过，同时明确“major 默认阻塞，只有 caller 明确 acceptance bar 才可 pass-with-issues”。`acceptance.md:166` 的 R3-E1 处置建议本身也包含由 owner 明确本次必验范围。现在 spec 已明确只有这一自动新样本证据缺口可以被接受，人工/继续/停用、新指导对照及其他必验结果仍须真实通过，且不得有实现阻塞，符合该有限例外。它不能扩大为任意必验失败均可带过，也不能把 major 降成 minor 或 not-applicable 来获得纯 pass。
- **旧失败与后续独立裁决**：acceptance Round 3 的 `fail`、`R3-E1` major 及压缩 Scenario `inconclusive` 应原样保留；本轮设计 Approved 不为它补出不存在的证据。后续产品 Round 可以引用明确 acceptance bar，在问题/覆盖表中继续保留自动未观察和接受理由，并据其他结果选择 pass-with-issues 或 fail；不能把旧 Round 改成成功。旧0.01阈值自动事务只保留其原版本/配置身份，不作为新指导普通场景的成功证据。
- **手动入口文案与未完成对照**：`f56e5e6d8..f09df0d25` 只有两份文档4行新增，明确既有用户 `/compact` 与 idle 交接，不改变自动条件或能力面；code-review Round 5、verification Round 3 的静态结论可保留。本轮未将这两项结论当成新模型行为已改善的证明；独立新身份 compact 对照仍由产品 reviewer 观察并另报，任何新发现仍可能阻塞上述有条件收口。

### Retained coverage

- retained_from: **Round 2 / Round 3**。上游 Skill 复用、公开 API 边界、原生安装更新语义、profile/EntryTree 挂载与清理职责未被本次文档裁决改变。
- 不保留或重写旧产品整体 pass/fail。支持路径的历史证据和新指导普通模型证据继续按其实际版本、配置、样本身份分别说明；本轮没有新增 runtime 通过证据。

### 历史问题闭环

- **R3-E1（产品验收）**：Author Resolution 为本轮 spec/design 的显式 acceptance bar；本轮核实该方法边界与事前范围、reviewer 例外规则相容。**证据缺口仍 open/inconclusive，未关闭为 pass**。旧 Round 3 fail 保留；仅解除“在本次普通试用中必须强造一次自动触发才可给出任何可交付结论”的解释，后续整体裁决须由独立产品 reviewer 依据明确条件记录。
- 设计 Round 2/3 无历史 CRITICAL/WARNING issue 待关闭。

### Issues

无。

### Recommendations

无新增实现或测试要求；后续报告须继续使用上述证据身份和限定结论，不能把本设计批准写成自动路径已验证或产品已通过。

### Author Resolutions

- 作者接受 Round 4 Approved（0/0）。自动新样本 R3-E1 保持 open/inconclusive，旧产品 Round 3 fail 不重写；最终产品结论按显式 bar 与真实新结果另列。本轮裁决及已审 canonical delta 的归并不修改运行时或自动/人工支持契约，保留 Round 2/3 的实现设计边界。

## Round 5

### Metadata

- reviewer target: `/root/design_scope_614`（独立 change-design-reviewer，新 reviewer）
- review_mode: `delta`
- mode_reason: 同一 PR #364 的有界任务收口指导、压缩资料精简与证据归因修订；没有改变运行时接口、审批、插件能力或生命周期。已重新核对实际装配入口与本轮原始探针，未仅依据旧 Approved 放行。
- started_at: 2026-10-17T23:23:22+08:00（最终原始证据复核与裁决计时；此前已读取设计及历史报告）
- completed_at: 2026-10-17T23:25:00+08:00（约）
- duration: 约 2 分钟（最终复核与裁决）
- reviewed checkout: `/Users/czj/.codex/worktrees/feat-614-plugin-development/nano-multiagent`，`codex/feat-614-plugin-development`，HEAD `c839d677747f365bff9a1388e132d24717d7d67d`；已核 `481467ac16f0eda4561fca5c8230050541600de9` 是该 HEAD 祖先。
- reviewed target: HEAD 加未提交的 design Changelog、`evidence/task-scope-revision.md`、`specs/gateway/global-agent.md`；指导候选为本机 `/tmp/feat614-r3/replay-final-candidate.py` 的 D。只追加本报告，不改代码或设计、不提交、不执行新模型或产品验收。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

方案以当前请求范围约束助手自己的旧计划，并把输出效果与实际执行路径分开判断，落点和复杂度适当。可进入实施及受影响门禁复验；本轮批准不代表 D 已通过完整 Agent 轮次、真实压缩旅程或公开交付验证。

### Coverage 与证据

- **实际装配与职责**：`packages/dsh-integration/src/agent-config.ts:86` 在真实 preset 装配中安装 GlobalMode；`global-mode.ts:15-19` 按 global mode 注册产品沟通与持续执行指导。D 插在既有持续执行句之前，适用于上下文已经足够的简短续问，既有 `send_message`、内部收尾、进度、拒绝后安全处理仍保留。该能力是所有全局任务的回复范围控制，归此现有提示词层合理；不应依赖插件 Skill 是否被发现或启用，也不需要新状态机、消息路由或权限规则。原先已接受的真人任务仍由既有持续执行要求约束，不能把助手自己新增的检查点计划当成额外授权。
- **本轮问题归因**：独立读取原摘要请求 `09-28-59_125` 的末两条消息，分别确认 `Workspace summary guidance` / `## Project Decisions` 与原生 `Output EXACTLY` 存在。由此可确认自定义指导进入该次真实摘要请求；仅缺少目标标题不足以认定未走插件。`compaction.ts:17-25` 的 preset 自动让出和人工 `compactNow` 路由继续存在，本轮没有新的路由故障证据。将修订集中在任务范围、资料与结论强度，而不改压缩接线，符合已观察问题。
- **探针能证明的范围**：独立对照 A1 与 D1 请求，仅 `system` 顶层字段不同；重放脚本把流式改为非流式，不执行返回的工具调用。原始 A1–A3 均先请求 bash；D1–D3 都只请求 `send_message` 交付业务答案；control-d 同时请求确认消息和 bash 证据读取。支持把 D 作为待复验候选，不能推导完整轮次结束、消息真正送达、调查实际成功、普遍成功率或端到端耗时。D1/D2 对云同步决策次序仍有额外建议，证据文件已保留这一局限；不把“没有排障调用”扩写成所有回答内容都已严格准确。
- **资料复用与保留差异**：现有 `references/compaction.md` 已指向安装版本 README/公开声明；精简重复的 summarize、阈值和验证教程，继续保留 Nano workspace provider 与用户 `/compact`/当前轮结束交接，是对 Round 2 上游复用原则的收敛。`docs/specs/gateway/global-agent.md:133-139` 确认用户命令作用于全局主上下文；宿主控制不能由 shell/RPC 重建的边界与既有支持范围继续适用。`references/verification.md` 已要求按风险、业务结果、实际激活与用户交付分别验证，新增“输出异常不等于路径/根因证明”与这些要求一致，不取消用户明确要求的验证或实际缺陷处理。
- **Delta、消费者与验收**：新增 delta 锚定 canonical `docs/specs/gateway/global-agent.md`，采用 ADDED 独立 Requirement，未覆盖原内部收尾和任务进度 Scenario。两个场景分别覆盖上下文足够的简短问答、明确继续开发/验证或具体信息缺口，消费者行为明确。单 M1 和原能力矩阵无需重分；本轮证据文件已指定同场景真实模型、另一种简短问答、明确继续验收对照，以及现有 runtime/沟通/Skill 刷新回归。指导效果依赖模型，采用真实完整旅程而不增加逐句提示词断言是合理选择。没有客户端布局或交互变化，不需要新的前端原型。

### Retained coverage

- retained_from: **Round 2 / Round 3**。有限 `describe_api`、原生安装更新 `restart-required`、profile/EntryTree 挂载、工具选择、公开 API 与资源清理职责未变；本轮无需重新证明无改动的加载实现。PA Skill 资产继续沿原有随包安装链交付。
- retained_from: **Round 4**。普通样本自动压缩未触发仍为未观察；人工压缩、继续对话和停用恢复等既有必验边界不因资料精简消失。旧样本只能证明其原版本/配置，不可补作 D 的真实模型结果。
- 既有无关门禁可按上述未受影响范围保留；指导变动涉及的代码、一致性、canonical delta 与真实模型产品结果须由后续独立门禁裁决。设计批准不将原失败样本或开放证据缺口改写为通过。

### 历史问题闭环

- 设计 Round 1–4 没有 CRITICAL/WARNING 待关闭。
- 产品 R3-E1 的自动路径新样本缺口本轮未产生新证据，继续沿用 Round 4 的 open/inconclusive 边界。
- 本轮补查纠正“缺标题可能说明未调用插件”的归因强度；没有证明插件所要求的结构已满足，也没有据此关闭输出效果问题。续问扩展排障的端到端问题仍待新指导完整旅程验证。

### Issues

无。

### Recommendations

无新增实现要求。按本轮已定的真实模型对照与既有受影响门禁完成复验，并据实际结果报告，不能以探针里的工具请求替代用户可见交付。

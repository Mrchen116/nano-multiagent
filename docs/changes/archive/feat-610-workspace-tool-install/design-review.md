# feat-610 Design Review

## Round 1

### Metadata

- reviewer_target: 独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: full
- mode_reason: 首轮 Gate 2；覆盖首文档、完整技术方案、delta-spec、milestone 与锁定 DSH 公共接口。
- started_at: 2026-10-14T23:35:19+08:00
- completed_at: 2026-10-14T23:38:51+08:00
- duration: 3m32s（完成 checkout/指令预检后计时）
- baseline: Nano `dbef789c3`；首文档 `f5ae37abe`；DSH npm `0.2.1-alpha.1`，Include `1.0.10-alpha.1`；参考源码 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`。
- working_tree: `main` 有既存 dirty/untracked 内容；本轮只创建本报告，未修改设计、代码或其他文档，未提交。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

核心职责拆分与公开接口选择可成立。放行前需要修订被自动工具集合改变的原有白名单 Requirement，并给失败后修正源码的重试提供与“不需重启”目标一致的路径。

### Coverage 与证据

#### 现状与实际产品入口

- 核对 `packages/dsh-integration/src/agent-config.ts:35-52`：owner 层扩展装在宿主，workspace 层装在产品 preset；`attachAgent()` 再施加工具选择。因此 workspace Include 应挂在该 preset 能力层，不能挂到共享 root。
- 核对 `packages/dsh-integration/src/extensions.ts`：当前实现只读取 `plugins.json` 并调用 `ctx.plugin()`，没有安装/热更新服务。`client.ts:13-24` 每次重写公共 profile，`cordis.patch.yml:11-12` 禁用公共管理工具；设计对现状的描述准确。
- 核对 `capabilities.ts:39-51`、`index.ts:310-320` 与 `apps/node/src/capabilities.ts:60-64`：执行限制、`configuration.selection` 和配置候选目录目前走不同接线点。设计明确要求共同采用有效集合，并把 Node 必要接线纳入 M1，范围足以容纳改动；不能只改工具声明或只改配置目录。
- 既有 `packages/dsh-integration/tests/capabilities.test.ts:54-116` 确有两层覆盖、显式空集、实际 dispatch、PTC 与重启回归。它们是本次需要保留的基线，不能证明尚未实现的安装链路。

#### 原生复用、接口与架构判断

- 已读已安装包 `package.json` 与 `lib/types/*.d.ts`，不是仅依据源码中的未发布接口。`@deepseek-ai/dsh-plugin-manager` 的根 export 提供 `PluginManager` 及 `installBundle()`、`setBundleEnabled()`、`removeBundle()`；`dsh-app-boot` 根 export 提供 `loadProfileDirectory()`、`composeEntries()`、`prepareProfileEntries()`、兼容性 API；Include 根 export 提供可维护子树的 `Include`；`dsh-hmr` 根 export 提供 `runExclusive()`、`watchConfig()`。不需要 private import 或修改 DSH。
- 原生 manager 的必要注入为 `loader`、`profileContext`（参考源码 `packages/boot/plugin-manager/src/index.ts:176-177`）；没有 HMR 时 `reload()` 不装配执行树，结果默认 `restart-required`（同文件 `790-804`）。因此独立纯管理 Context 持久写包，宿主 scoped Include 负责执行，是合理复用，不要求为了包管理再启动一个执行运行时。
- Include 提供独立 `EntryTree`、`refresh()` 与原地 config 更新（`vendor/include/src/index.ts:178-200,245-288`）；`EntryTree.await()` 能等待自己的任务（`vendor/loader/src/config/tree.ts:35-49`）。加载诊断可基于公开树与 fiber 状态实现，不能把 `refresh()` 无异常当作成功：该方法会记录错误并保留原树。设计已经明确实际加载审计。
- 原生 `loadOverlayPatches()` 会把插入的相对模块路径锚定到 bundle patch 所在目录（`packages/boot/app-boot/src/index.ts:349-365`）；`loadProfileDirectory()` 也会显式返回 `skippedBundles`（`profile.ts:732-767`）。设计选择原生解析而不是自写 bundle parser 是合适的。
- HMR `runExclusive()` 是宿主串行事务，`watchConfig()` 同样进该队列（`packages/boot/hmr/src/index.ts:262-298`）。独立 manager 不注入宿主 HMR，再由 WorkspaceExtensions 串行完成宿主刷新，可以避免把 workspace 包变更误用于公共 root。实现需要声明所用 DSH 直接依赖，符合现有 dependency contract；这是常规接线要求，不另列 finding。
- WorkspaceExtensions 统一负责 workspace profile、管理 Context 和多个 preset Include 的生命周期，比复制包管理/锁/patch 语义更合适。设计没有新 Agent Loop、跨包 runtime import 或新 HTTP 内核服务。单一 milestone 不存在并行文件归属冲突。

#### 用户约束、选择与审批

- `spec.md:25-65` 的创作、同聊天使用、同 workspace 共享、其他 workspace 不可见、重启、原禁用选择、失败与撤销均在设计数据流和 M1 验证范围中出现。
- workspace 来源限定为可信 `config.workspace`，管理工具不接收 workspace/identity，限定安装清单与刷新集合；自动工具名只进入已启用 `plugin_manager` 的主 Agent，子任务继续继承 mask。该边界与当前 DSH scope 链能力过滤相容（参考源码 `packages/core/tools/src/index.ts:1178-1218`），不需要另建白名单数据库。
- 原生插件在宿主进程运行，scope 不是操作系统沙箱。设计 `65` 行已说明本机插件信任边界；沿用 Nano `pre-execute` 与明确批准构建脚本的决定，在既有信任模型中自洽。本轮不把它升级成未被要求的隔离进程方案。
- 新增管理能力默认出现在候选目录但不回写已有显式名单，与首文档“已获准管理能力”的前置相容。关闭管理能力撤销自动集合，旧静态工具选择保持；停用按 bundle 生效，也已在 delta 中声明。
- 没有新增前端页面或交互；无需 prototype。通过既有真实 IM 消息驱动创建/安装/使用，runbook 明确真栈与模型服务前置，不用 runtime fixture 冒充产品验收。

#### Delta-spec 与 milestone

- canonical target `docs/specs/gateway/agent-capabilities.md` 正确；新增消费者行为、失败诊断、隔离与撤销有覆盖。
- M1 包括 integration、Node 必要接线、产品手册与真实原生进程测试，退出标准同时含实际 dispatch 拒绝、空集、旧禁用选择与重启，不只验证 pnpm 安装。
- delta 未修改已被本次改变的原 Requirement，见 R1-W1；失败源码修正的端到端路径尚未闭合，见 R1-W2。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 自动工具集合的 delta 与原白名单 Requirement 直接冲突

- **位置**：`specs/gateway/agent-capabilities.md:1-5`；`design.md:44,61`。
- **证据**：delta 只有 ADDED，新规则允许 `plugin_manager` 授权的新工具在不修改配置白名单时进入有效集合。canonical `docs/specs/gateway/agent-capabilities.md:225-229` 仍规定 single_thread 工具集恰等于配置、白名单是单一来源、运行时不另行注入；其 `241-245` Scenario 仍规定新 session 只启用配置列出的名称。此处和新工具跨重启、新 session 自动可用的目标直接矛盾。设计说“有限例外归并到 current spec”，但交给下游的 delta 没有表达该修订。
- **未修后果**：实施者或 verifier 可分别按新 ADDED 与旧 Requirement 得出相反的正确实现；归并后长期规范仍自相矛盾。
- **需要收口**：增加对原白名单 Requirement 的 MODIFIED，写清有限自动集合、启用条件、显式空集/管理关闭/子任务限制，以及原有工具禁用 Scenario 的保留。修改旧“不自动扩宽”Scenario 的适用条件，不能通过删除旧禁用/空集保证解决冲突。

#### R1-W2 — 修正首次加载失败的源码后，当前重试方案没有可兑现的免重启路径

- **位置**：`design.md:42,54-56`；`spec.md:11,58-61`；delta `11-13`。
- **证据**：原生 manager 在包已存在于安装前 dependencies 时直接返回 `restart-required`，不继续刷新（参考源码 `packages/boot/plugin-manager/src/index.ts:573-577`，已安装 npm 包行为一致）。设计明确保留这一源码替换限制，但又只用“原生激活验证”描述修复后重试。原生已存在的恢复测试覆盖修改 `config.fail` 再激活（`tests/manager.spec.ts:687-695`），没有证明修改插件源码能恢复。
- **本轮最小复现**：在临时目录使用已安装 `0.2.1-alpha.1` 的公开 `boot()`/原生 Include，加载一个顶层抛出 `Error("first evaluation failure")` 的 `tool.mjs`；移除执行条目，修正同路径源码，再重新加入同一个条目，等待 Include 与 Loader。第一次与重试均 `not loaded`，重试 `entry fiber exists: false`。同进程普通 ESM import 的对照也重复第一次的 evaluation failure。所有临时目录已删除，没有启用生产服务。
- **未修后果**：Agent 自己创作的新包首次模块求值失败后，即使修正源码，常规重新安装/停用再启用仍可能要求用户重启或持续失败，不能兑现首文档的自助创作—修正—使用旅程。此问题针对已承诺的加载失败恢复，不要求普遍支持已成功运行插件的源码热替换。
- **需要收口**：明确一个与锁定公开接口相容的失败源码修复路径，例如让 Agent 的修正生成新的模块文件/入口，再激活并验证；或者实际证明可用的原生模块恢复机制，并纳入 M1。若决定此类失败必须重启，应先对齐首文档的免重启承诺，而不能只在实现时返回 `restart-required`。验收至少覆盖一次源码求值失败后修正并成功调用，不仅覆盖安装失败或 config 修复。

### Recommendations

无额外建议。完成上述两项收口后可按实际 diff 做 closure 或 delta 复审，不要求扩展成任意已加载包热替换或通用插件管理项目。

### Author Resolutions

- R1-W1 accepted：delta 增加完整 MODIFIED 白名单 Requirement，保留全部未改 Scenario，明确 workspace 管理许可的有限增量。
- R1-W2 accepted：本地自建 bundle 每次安装生成不可变版本产物，再用 DSH 原生 file: 安装；执行入口为相对文件路径，由原生 patch 锚定到当代 URL。修正失败源码后重装产生新 URL，不复用 Node 失败缓存。普通外部包替换保留原生 restart-required。设计关键决策、数据流和风险已同步。

## Round 2

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: 白名单修订属于旧问题闭环；本地不可变 generation 引入新的文件产物和安装/执行 URL 路径，超出仅文字消歧，因此核查该有界设计变化与受影响恢复、持久化行为。
- started_at: 2026-10-14T23:43:21+08:00
- completed_at: 2026-10-14T23:44:38+08:00
- duration: 1m17s（完成修订 diff 读取后计时）
- baseline: Nano `de83edc47`；DSH/Include 与参考源码基线同 Round 1。
- retained_from: Round 1 的现状入口、scope/权限、公开 exports、职责分工、同 workspace 多 preset、Node 接线、前端范围和 M1 归属证据；这些部分没有实质变化。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

R1-W1 closed；R1-W2 still-open。本地 `file:` 包安装和来源持久化可用，但原生安装后重新解析 bundle 并不会把插件行锚定到 generation 目录，修订仍复用旧执行 URL。

### Coverage 与证据

- 已完整对比 `dbef789c3..de83edc47` 的 design 和 delta，并读 Author Resolutions。delta 增加了原白名单 Requirement 的完整 MODIFIED：保留默认工具禁用、显式空集、Cron、skill 默认候选等 Scenario，新增有限动态集合并调整“不被默认集合自动扩宽”的场景；与新增 workspace Requirement 联读可确定例外边界。
- 公开 `parseInstallSpec()` 支持绝对 `file:` 目录；原生 manager 也提供本地包真实安装测试（参考源码 `packages/boot/plugin-manager/tests/install-spec.spec.ts:13-17`、`tests/manager.spec.ts:1160-1182`）。本轮进一步使用已安装 npm 包的 `PluginManager.installBundle()` 和真实 pnpm，未 mock 包操作。
- 临时 profile 使用公开 `initProfile()`，管理 Context 按设计不装 HMR/执行插件。连续创建并安装 `generations/g1`、`generations/g2`，两代保留同一 bundle 名 `feat610-generation-probe`、版本 `1.0.0`，patch 插件行均为 `./tool.mjs`。第一代模块顶层抛错，第二代修正。每次安装后使用公开 `loadProfileDirectory()` 与 `composeEntries()` 得出执行行，再用真实原生 Include 应用。
- 两次 pnpm 均退出 0；dependencies 分别持久保存 `file:<profile>/generations/g1` 与 `file:<profile>/generations/g2`；选中 bundle 可从磁盘重读。因此 file: 本身和来源保存没有问题。但两次解析出的 `packageDir` 均为 `<profile>/node_modules/feat610-generation-probe`，模块 URL 均为 `file://<profile>/node_modules/feat610-generation-probe/tool.mjs`。
- 核心观察：`entry URLs equal: true`；第二代实际 Include 更新后 `same-process repaired generation: not loaded`。原生 manager 的 `restart-required` 可由纯管理 Context 解释，却不能改变该执行 URL 的事实。
- 原因与锁定源码一致：`initProfile()` 的 pnpm 配置明确使用 `nodeLinker: hoisted`（`packages/boot/app-boot/src/profile.ts:236-245`）；`resolveBundleDir()` 经 package lookup 返回安装目录（同文件 `684-711`）；`loadProfileDirectory()` 从该安装目录读 patch（`745-758`），`loadOverlayPatches()` 将相对行锚定在该 patch 所在目录（`packages/boot/app-boot/src/index.ts:349-365`）。保存 `file:g2` 不等于执行 URL 指向 g2。
- 没有引入 scope、权限、子任务或多 workspace 边界变化。generation 的持久化仍属于 workspace profile，职责可以留在 WorkspaceExtensions；本轮仅阻断尚不成立的执行路径假设，不要求普遍支持 registry/git 或任意已加载包热替换。
- 所有临时 profile、generations 和测试 Context 已清理；没有使用生产服务。没有修改代码或首文档。

### 历史问题闭环

- **R1-W1 — closed**：Author Resolution 接受并新增完整 MODIFIED。核对 delta `3-35` 与原 canonical Requirement，新增有限集合的条件及未改变 Scenario 均已保留，原“不自动扩宽”场景已作对应限定。
- **R1-W2 — still-open**：Author Resolution 采用 generation 加 file: 原生安装；原生实测证明目录来源不同，但实际解析后的执行 URL 相同，尚不能修复同进程的失败模块缓存。具体见 R2-W1。

### Issues

#### R2-W1 — file: generation 改变安装来源，没有改变实际执行入口 URL（延续 R1-W2）

- **位置**：`design.md:44,58,67`。
- **证据**：上述真实原生 manager/pnpm/profile parser/Include 路径产生相同的 `<profile>/node_modules/<bundle>/tool.mjs` URL；第一代求值失败后，第二代修正仍未加载。设计“DSH patch 解析把它们锚定到本次安装产物的绝对 URL”“新安装、更新或失败后修正重装都获得独立 URL”的断言，与默认原生 profile 行为不符。
- **未修后果**：即使实施遵循新 generation 设计，也会在实际 URL 检查中拒绝恢复，或再次导入失败旧 URL；自助修复旅程仍不能免重启完成。
- **需要收口**：明确让执行 patch 的解析基点确实位于不可变 generation 的公开 API 路径，或提供真实验证成立的其他方案；不能仅依赖 file: 来源改变。需要对同名 bundle 连续两代安装、第一代求值失败后第二代成功加载作证据，同时保留原生安装清单与重启恢复。普通外部包的 restart-required 限制可以继续保留。

### Recommendations

无额外建议。

### Author Resolutions

- R2-W1 accepted：原生 pnpm 的 hoisted 副本不能提供 generation URL。执行层改为从 profile dependencies 持久的 file: 来源识别本 workspace generation，再用原生 bundlePatchPaths/loadOverlayPatches 从真实 generation 解析 patch；普通包沿用 loadProfileDirectory。已用锁定公开 API 连续安装同名 file:g1/file:g2 验证：第一代源码求值失败，第二代 URL 不同且返回 fixed；没有清理或改写模块缓存。设计关键决策已修订，M1 必须把这个完整失败→修正重装→实际调用链纳入原生进程回归。

## Round 3

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: closure
- mode_reason: `29597d838` 只收口 R2-W1 的 generation 执行解析基点，不改变已审的安装服务、scope、工具选择、审批、公共接口或 milestone 分工；核查历史 issue 关闭证据即可。
- started_at: 2026-10-14T23:46:29+08:00
- completed_at: 2026-10-14T23:47:13+08:00
- duration: 44s（完成修订 diff 读取后计时）
- baseline: Nano `29597d838`；DSH/Include 与参考源码基线同 Round 1。
- retained_from: Round 1 的完整覆盖与 Round 2 的白名单闭环、原生 file: 安装及持久来源证据；本轮没有波及这些结论。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R2-W1 与其前身 R1-W2 已关闭；R1-W1 保持 closed。设计已具备不操作模块缓存、从持久来源恢复的本地失败修正路径。

### 历史问题闭环与证据

#### R2-W1 / R1-W2 — closed

- **Author Resolution**：本地 managed bundle 的标准 profile dependency 保存 `file:<generation>`；执行层对属于该 workspace generations 根的来源，使用公开 `readProfileManifest()`、`bundlePatchPaths()`、`loadOverlayPatches()` 解析真实 generation patch。普通外部包继续使用 `loadProfileDirectory()`，不以 hoisted 安装副本作为本地执行解析基点。
- **设计核对**：`design.md:44` 已明确上述分支、相对入口约束、依赖从祖先 profile/node_modules 解析、来源持久化和不建额外映射库；`58,67` 的失败修正与实际 URL 检查与该分支一致。R2 Author Resolutions 同时要求 M1 覆盖完整失败后修正重装链路。
- **独立实测**：本轮再次使用已安装锁定包的原生 `initProfile()`、`PluginManager.installBundle()`、真实 pnpm。对同名同版本 bundle 连续安装 `file:g1`、`file:g2`；每次从 profile 磁盘 dependencies 读取来源，再用上述公开 API 解析 patch。两次 pnpm 均退出 0；第一代入口为 `<profile>/generations/g1/tool.mjs`，第二代为 `<profile>/generations/g2/tool.mjs`，`distinct execution URLs: true`。
- **失败恢复**：第一代模块顶层抛出 evaluation error；在同一执行 Context 原生 Include 更新为第二代后，修正模块正常注册函数，调用返回 `fixed`。没有改写/清空模块缓存，没有重启该执行进程。
- **持久化**：随后启动全新的 Node 子进程，重新从磁盘 profile dependencies 及 generation manifest/patch 解析，加载原生 Include 并调用相同函数，输出 `fresh process persisted call: fixed`，退出 0；该过程不依赖上一进程的临时映射。
- **证据边界**：该探针证明原生包安装、generation URL、失败模块修复和进程重启恢复的设计可实现性；调用的是探针插件注册函数，不是已实现 Nano `plugin_manager` 的真栈工具验收。工具审批、模型声明/dispatch、跨 workspace 与真实 IM 旅程仍按已审 M1 门禁实施和验证。
- 所有临时 profile、generation、Context 及子进程已清理；未触碰生产服务。本轮只追加本报告，未提交。

#### R1-W1 — retained closed

本轮未改 delta；沿用 Round 2 对完整 MODIFIED 与保留 Scenario 的证据。

### Issues

无未解决问题。

### Recommendations

无额外建议。

## Round 4

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: 有限复核安装版包管理器启动事实及 Node → integration 的内部 initialize 接线；不改变工具契约、profile 持久化、安装/执行 scope、审批或子任务边界，无需重做完整审查。
- started_at: 2026-10-15T00:17:34+08:00
- completed_at: 2026-10-15T00:18:49+08:00
- duration: 1m15s（完成 worktree 状态与 diff 读取后计时）
- baseline: worktree `/Users/czj/.codex/worktrees/workspace-tools/nano-multiagent`，branch `codex/feat-610-workspace-tools`，HEAD `c4822c94f6c388fc4807a2bc88a199b581f42e03` 加当前包管理器接线 diff；锁定 DSH/Include 基线不变。
- retained_from: Round 1 的完整覆盖、Round 2 的白名单闭环及 Round 3 的 generation/失败恢复/持久化实测；本轮变化不影响这些证据。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

安装版自带 pnpm 的路径与 installer 一致，启动事实来源和传递时序正确。包操作通过原生 `ProfileContext.packageManager` 执行，源码模式继续采用原生默认。

### Coverage 与证据

- **实际 installer 路径**：`apps/im-server/assets/install.sh:43-46` 将 pnpm 安装在 `<NANO_ROOT>/tooling/node_modules/pnpm/bin/pnpm.cjs`；`65,88,91` 将 release 放在 `<NANO_ROOT>/releases/<hash>` 并从该 release 的 `apps/node/lib/cli.js` 启动。`apps/node/src/release.ts:6` 的 `releaseRoot` 从 `apps/node/lib/release.js` 定位 release 根，因此 `41` 行 `../../tooling/node_modules/pnpm/bin/pnpm.cjs` 正好指向 installer 的私有文件。现有 updater 也使用同一路径（`apps/node/src/update-worker.ts:34-35`）。
- **缺口与最小修复相符**：LaunchAgent 固定 PATH 不包含私有 pnpm 目录（`apps/node/src/lifecycle.ts:153-160`），因此仅依赖原生默认 `pnpm` 的确不能覆盖安装版。新增方案直接用 `process.execPath` 执行私有 pnpm JS 入口，包操作的 PATH 前置该 Node 所在目录，供 pnpm 及其子进程找到相同 Node；没有修改父进程全局 PATH，也没有要求用户全局安装 pnpm。
- **可信来源**：`loadNodeRelease()` 先解析安装 manifest 并核对 release metadata（`release.ts:13-28`）；`installedPackageManager()` 只对其 managed 结果提供 invocation，source 返回 undefined（`39-42`）。`main.ts:26,61` 在 Node 启动路径调用该组合，不从模型参数、Agent 配置或 workspace profile 读 executable/args。Node 保持结构化事实提供者，只使用 integration client，不新增 DSH import。
- **接口与时序**：可信 invocation 经内部 stdio `initialize.packageManager` → `ConfigurationScopes.packageManager()` → `WorkspaceExtensions.packageManager` → `WorkspaceOwner.create()` 注入独立管理 Context 的 `ProfileContext.packageManager`（`packages/dsh-integration/src/index.ts:240-261`、`agent-config.ts:36-37`、`workspace-tools.ts:31,47,80-87`）。设置发生在产品 presets 注册之前，首个 workspace manager 创建时即可获得 invocation；未提供时保留既有宿主/native 默认。
- **原生消费方式**：锁定 DSH 的公开 `ProfilePnpmInvocation` 由 command/args/env 构成；原生 manager 将该值交给包操作，registry 查询同样使用它（参考源码 `packages/boot/plugin-manager/src/index.ts:335-339,680-692`）。包操作使用调用方命令及前置参数，并将 invocation env 合并入包操作环境（`src/operations.ts:315-358,598,630`）。这属于原生支持的应用内置包管理器入口，无需 shell wrapper、上游 patch 或新增包生命周期。
- **窄验证**：运行 `pnpm exec vitest run apps/node/tests/node-updater.test.ts packages/dsh-integration/tests/workspace-tools.test.ts -t 'distinguishes source installs|verifies fixed HTTPS|installs workspace tools'`，结果 2 files passed、3 tests passed、1 test 因筛选跳过。覆盖 source 不注入、verified managed release 的 installer 形状路径/绝对命令，以及 DSH runtime PATH 隐藏全局工具时，通过可信 invocation 完成实际 workspace 安装、使用、恢复和重启路径。
- **证据边界**：这是 installer 路径、启动接口与原生进程可行性复核；未运行完整公开下载安装或部署验收。没有因此扩大本轮范围，也没有重复 R1–R3 全审。
- 本轮只追加本报告，没有修改实现或其他文档，没有提交；作者已有修改保持。测试自行清理其临时 runtime/进程。

### 历史问题闭环

R1-W1、R1-W2、R2-W1 保持 closed；本轮无新增问题。

### Issues

无未解决问题。

### Recommendations

无额外建议。

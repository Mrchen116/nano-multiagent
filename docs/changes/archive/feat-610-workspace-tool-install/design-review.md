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

## Round 5

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: 用户设置页反馈引出的有界展示增量；覆盖 workspace 来源/实际状态接口、静态选择关系、局部信息层级及 catalog 晚注册静态工具的最窄修正，不重审安装、generation、审批或部署架构。
- started_at: 2026-10-15T00:38:20+08:00
- completed_at: 2026-10-15T00:41:40+08:00
- duration: 3m20s（完成 checkout 与变更基线读取后计时）
- baseline: `4122379c8ef39fc110c553302ea23081830f595f`，worktree `/Users/czj/.codex/worktrees/workspace-tools/nano-multiagent`，branch `codex/feat-610-workspace-tools`。
- retained_from: R1–R4 的原生公共能力、职责、工具选择/执行、generation 恢复和安装版包管理器证据；本轮仅为相同有效集合增加展示事实，并收窄来源识别。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

有限展示方案能消除已自动启用工具仍待勾选的误导。真实桌面和窄屏页面均支持其信息组织；原型 HTML 草稿未渲染，不将实际产品观察记作草稿视觉通过。

### Coverage 与证据

#### 用户场景与实际信息组织

- 独立通过 Chrome 新建审查标签，使用获准的隔离测试身份正常登录 `http://127.0.0.1:54267/settings/agents/e2e`。未复用或修改用户原页，未修改 Agent 配置。
- 先查看真实整页及相邻区域，再定位工具区：既有 Access & Model 保留 Skills、Tool Allowlist、模型字段的阅读顺序；静态工具仍为选中/未选中的可操作 pill。其下有独立 `Workspace tools` 小标题、自动管理及聊天停用指引、工具状态卡，随后才是 Default Model。新区域没有伪装成另一组待选择 pill。
- 桌面截图观察到 `expense_summary` 与 `Enabled` 相邻，下面直接显示完整业务说明。用户可以就地判断工具已可用、用途是什么和如何停用，无需从静态名单推断；该名字没有 checkbox。`plugin_manager` 保持静态已选，`schedule_*` 保持静态未选，只有真实自建工具在 workspace 区。
- 额外使用浏览器 viewport 能力检查 390×844 CSS 窄屏：静态 pill 自然换行，workspace 标题、指引、名称/Enabled 和说明均完整落在同一列；说明换行，没有新增工具区的截断或必须横移才能判断状态的问题。读完后恢复 viewport，关闭自建标签。
- 本轮代表性真实桌面/窄屏截图及 AX 状态保留在审查会话的 CUA 输出；worker 的桌面对照截图另在 `/tmp/feat610-review/workspace-tools-settings.jpg`。本轮判断来自独立真实页面观察，不仅依据 worker 截图或组件名。
- `prototype.html` 本轮只读源文件；author 已明确 file URL 策略拒绝及“未渲染草稿”，没有绕过。本次可审的局部渲染证据是授权 HTTP 产品页面，其容器、间距、相邻控件与响应式关系真实可见。草稿中的已启用/不可用状态用于解释设计意图，不作为已验证画面。

#### 接口、选择与职责

- `ToolSelection.catalog()` 对实际安装增量附加 `source_group: workspace`，`enabled` 通过既有 `selection()` 判定（`packages/dsh-integration/src/capabilities.ts:24-48`），没有引入新的权限源或持久开关。关闭管理能力/空名单不自动获得工具的执行规则继续保留。
- Node 为 workspace 项设置 `default_on: false`，并保留来源与 enabled；IM 归一化保留布尔 enabled，前端归一化继续保留这两项（`apps/node/src/capabilities.ts:60-65`、`apps/im-server/src/control.ts:496-503`、`im-agent-config-api.ts:327-333`）。这避免把安装事实写成新建页的静态默认选择。
- `PillSelector` 仅让非 workspace 项进入原有选择按钮，workspace 项渲染只读 section/article；onChange 仍只处理静态按钮（`pill-selector.tsx:40-42,70-119`）。该局部展示复用既有页面，不需要新管理页或额外持久状态，职责归属合适。
- 晚注册 Cron 工具的修正发生在每次 Include 更新之前：当前可见且不在先前 managed 增量中的名字加入 baseline，再从更新后新增名字推导 workspace 集合（`workspace-tools.ts:118-123` 及原有增量计算）。这针对真实 catalog preview 生命周期补齐静态集合，不把全部 catalog 新名字一概自动授权，也没有另建来源数据库。
- 已核对新增原生测试：主 Agent workspace 工具 enabled=true、显式空集 enabled=false、重复 catalog 只有 `workspace_echo` 被标为 workspace，且 `schedule_create` 未进入执行集合（`tests/workspace-tools.test.ts:76-85`）。组件测试分别覆盖 Enabled/Unavailable、没有 workspace 选择按钮、点击静态 read 时保存值不包含自建名（`pill-selector.test.tsx`）。本轮沿用该固定 revision 的已有窄/全量验证记录，未再跑全套。

#### Delta、must-match 与验证边界

- `spec.md` 新增配置页真实状态 Scenario；IM delta 锚定 Agent 配置页消费者行为，涵盖查看/保存不填静态名单与关闭管理后不可用；Gateway delta 保留相同自动集合与静态选择边界。设计 `83-93` 行已明确沿用容器、只读信息层级、提示、响应式、must-match/may-adapt/out-of-scope 和 M1 新退出标准，足以指导该局部实现与产品复验。
- 本轮真实页面验证 Enabled 的桌面/窄屏信息层级。为遵守只读审查约束，没有关闭 e2e 的管理能力或保存无关配置；Unavailable 的可实现状态由同一 selection 接线与组件状态测试支持。真实状态切换、保存后名单保持及继续聊天实际调用，仍由已安排的独立产品复验完成；本设计 Approved 不提前代替这些验收结论。
- 本轮只追加本报告，不改实现、不提交；没有停止共享隔离栈。作者/其他 reviewer 的报告修改保持。

### 历史问题闭环

R1-W1、R1-W2、R2-W1 保持 closed；R4 的安装版接线结论保留。本轮无新增设计问题。

### Issues

无未解决问题。

### Recommendations

无额外建议。

## Round 6

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: 用户纠正 workspace 工具只读管理缺口，有限覆盖逐 Agent 关闭状态、canonical/IM/Node/runtime 传递、操作指纹兼容及既有配置控件接入；共享配置字段的波及范围纳入本轮，不重审原生安装器、generation 或部署。
- started_at: 2026-10-15T01:01:37+08:00
- completed_at: 2026-10-15T01:03:46+08:00
- duration: 2m09s（完成 checkout 与受审设计读取后计时）
- baseline: 当前 branch canonical `89c47478b` 加恢复 active 后的 spec/design/delta/prototype 文档修改。R6 delta 按该当前基线审，不把旧全 feature 累计 ADDED 当作本轮增量。
- retained_from: R1–R4 的原生安装/执行职责、generation 恢复、workspace scope 和私有包管理器证据；R5 的来源分组、有效集合状态与响应式参照保留。R5 的只读管理决定被本轮用户要求主动替换，不作为新目标沿用。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

逐工具开关的配置、持久化、权限与应用时序方案可闭合。放行前须将本轮 delta 锚定当前 canonical 并明确替换旧只读规则，避免归并后同时保留互斥契约。

### Coverage 与证据

- **用户意图与范围**：首文档保留本次原话，目标是把自建工具纳入已有配置关闭/重开控制面。设计 `97-105` 行明确关闭仅影响该 Agent 的使用，不卸载共享安装包；重装与重启不覆盖关闭选择；原聊天历史和 Session 保留。没有把用户对“重启 Session”的推测错误地实现成新建聊天。
- **现状应用路径**：已核 `packages/dsh-integration/src/index.ts:417-440`，确实先 `restrictSelection()`，再 `whenIdle()`、`setConfiguration()`；`agent-config.ts:93-118` 更新 retained/live 配置对象并刷新工具选择，而非销毁 Session。新增 denylist 在收窄阶段取并集，重开等待 idle 后用完整配置替换，与现有时序兼容；在途工具不取消、后续派发被拒的区分也已写清。
- **持久化责任**：`workspace_tool_denylist` 放入每 Agent 的完整 canonical config，经 IM JSON 列、Node YAML 和现有配置 operation 传递，runtime 仅映射成 camelCase；没有第二个 workspace 级关闭数据库。包目录只持有安装事实，不写人配置，故同名重装与其他 Agent 不会自动抹掉这一选择。自动窄 DDL 为旧记录补空集，设计明确保留已有数据。
- **指纹与旧操作**：当前 Node/product-contracts 的 `agentConfigurationFingerprint()` 在 canonical JSON 上计算（`packages/product-contracts/src/configuration.ts:25-40`）；IM 则有自己的 `gatewayKeys`、`gatewayCandidate()` 与 `candidateFingerprint()`（`apps/im-server/src/control.ts:50-97`）。设计提出“空字段不改变旧 fingerprint”，适用于这两侧；新非空字段必须参与同一 operation 身份与回执对账。新/旧 DB、operation 来回与 Node 持久化均纳入 M1，足以约束实施，不能只修改 runtime 型别。
- **权限与冲突消歧**：有效集合为原静态允许加获准管理时的 workspace 增量，再扣显式禁用。关闭同时去掉同名显式允许，避免两份字段反向表达；管理开启时重开只撤 deny，管理关闭时用户明确把单个工具加入允许集，只授予使用能力，不授予 `plugin_manager`。现有显式空集、子任务 mask 和跨 workspace 限制保留。该新增状态有真实需求，不属于可由安装清单替代的重复数据。
- **表单闭合**：设计规定单次 onChange 同时更新允许/禁用字段，并在创建、编辑、预览统一携带，避免两个 setDraft 相互覆盖。保存其他字段保留禁用名；本轮没有提出新导航、安装管理页或无效卸载按钮。保存前选中态是 draft，保存成功仍以既有 operation 应用确认，忙碌等待不提前声称完成，目标可指导实施。
- **实际界面参照**：本轮另开 Chrome 标签只读查看授权 localhost `/settings/agents/e2e` 的真实 Tool Allowlist、workspace 分组与相邻模型字段。普通工具以已选/未选 pill 显示，workspace 当前仍只读，Save Agent 在无修改时禁用。该已有容器和普通控件可作为本轮复用基线；没有点选静态工具或保存，未改 e2e/e2e-peer 配置，审后关闭自建标签。
- **原型与证据边界**：`prototype.html` 是交互源稿，表示逐工具切换、未保存与 Save 意图；本轮未渲染 file 草稿，未绕过既有 URL 策略，也不声称新 workspace 开关或新 pending 状态已经实际显示。新行为尚未实现；M1 已要求在 reviewer 自有 Agent 做实际浏览器关闭/重开保存、真实模型拒绝/成功、重装与重启、忙碌收窄和历史保持的新增旅程。此前只读页面通过不能替代新行为验收。
- **delta 与门禁**：新增场景覆盖关闭/重开、忙碌反馈、独立使用权限，测试资源限定自有 Agent，避免修改用户演示工具。当前 delta 的操作类型和旧 Requirement 替换关系仍有缺口，见 R6-W1。

### 历史问题闭环

R1-W1、R1-W2、R2-W1 保持 closed。R6-W1 是本轮当前 canonical 基线下的新归并缺口；不回写此前已批准的历史结论。

### Issues

#### R6-W1 — 当前 delta 未明确替换已存在的只读管理契约

- **位置**：`specs/im/agents-nodes.md:1-5,19-22`；`specs/gateway/agent-capabilities.md:38-42`。
- **证据**：基线 `89c47478b` 的 `docs/specs/im/agents-nodes.md:838-851` 已有“Agent 配置页展示 workspace 自动工具的实际可用状态”，规定停用/移除仍在聊天处理，管理关闭时页面显示不可用。新 IM delta 却以 ADDED 新标题“管理 workspace 自动工具的启用选择”加入配置开关和单独使用授权，没有修改或删除旧 Requirement。Gateway 当前也已经有“Agent 可在 workspace 自助安装原生工具”，本轮仍标为 ADDED，而不是对当前已有条目作 MODIFIED。
- **未修后果**：直接按本轮 delta 归并会在 IM 留下旧“关闭管理即不可用/停用走聊天”与新“可在页面关闭/管理关闭仍可单独授权使用”的两套规则；Gateway 增量也不能唯一指向要更新的已有 Requirement。下游 verifier、产品 reviewer 和后续维护可按不同契约得出相反结论。
- **需要收口**：以 `89c47478b` 为本轮增量基线，IM 复用已有 Requirement 标题写完整 MODIFIED（保留仍成立 Scenario，加入关闭/重开与条件化管理关闭场景），或明确 REMOVED 旧条目并 ADDED 新条目；Gateway 对已有自助安装 Requirement 写完整 MODIFIED。原全 feature 对 origin/main 的累计增量由历史报告和最终 canonical diff 保留，不因此扩大实现或部署范围。

### Recommendations

无额外建议。

### R6 Author Resolution

R6-W1 accepted：两处delta注明89c47478b基线，IM沿用旧Requirement原标题做完整MODIFIED替换，包含全部原Scenario并修订管理关闭条件；Gateway已有自助安装Requirement也归入MODIFIED。最终归并按原标题替换而不追加同义Requirement，消除只读/聊天才可关闭的旧规则。此处是当前unit继续修订的增量基线，原始feature对origin/main的累计增加保留在历史commit与报告。

## Round 7

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: closure
- mode_reason: 仅核实 R6-W1 的 delta 基线和旧 Requirement 替换关系；需求、配置字段、权限和 UX 方案无进一步实质变化。
- started_at: 2026-10-15T01:05:51+08:00
- completed_at: 2026-10-15T01:06:26+08:00
- duration: 35s（完成受审修订读取后计时）
- baseline: `89c47478b054b8d788022752213ff6d494b5f9d9` 加当前两处 delta 和 Author Resolution。
- retained_from: Round 6 的接口、持久化、两侧指纹兼容、restrict→idle 应用、权限及现有界面参照判断；R1–R5 未受影响部分按 R6 的限定继续保留。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R6-W1 closed。可以进入该有限配置开关的实施及已列明的验证门禁；本结论不代表新开关已实现或通过产品验收。

### 历史问题闭环与证据

- **R6-W1 — closed**：已核两处 delta 均显式记录当前 branch canonical 的完整基线 SHA。IM 使用原 Requirement 标题“Agent 配置页展示 workspace 自动工具的实际可用状态”，标为完整 MODIFIED；保留安装后查看及保存无关配置的结果，修订“关闭管理能力”场景为未被单独允许时自动关闭、可以单独授权使用，并新增用户关闭/重新开启、忙碌等待、重装/重启及其他 Agent 不受影响的结果。
- Gateway 的原静态工具 Requirement 与已有“Agent 可在 workspace 自助安装原生工具”现在均在 MODIFIED 下完整呈现；后者明确逐工具关闭优先于自动启用、同名重装不覆盖、静态选择/空集/子任务限制继续成立。不再把当前已有 Requirement 作为 ADDED 叠加。
- Author Resolution 明确最终 canonical 按原标题替换旧条款；旧全 feature 对 origin/main 的累计增加由历史 commit/报告和最终 canonical diff 保留。因此本轮关闭/重开授权规则不会与此前只读/停用仅聊天规则并存。
- 核对 design 尾部、spec 新场景与 R6 所审内容一致，没有借本次文档收口改变实现、部署或产品验证范围；不重复审查未变化方案。
- 本轮只追加本报告，未改实现、设计或 delta，未提交，未操作用户 Agent。

### Issues

无未解决问题。

### Recommendations

无额外建议。

## Round 8

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: full
- mode_reason: 用户目标从工具管理扩展为标准 DSH 插件；新增独立插件页、可信网页 RPC、workspace 共享生命周期和后台等待机制，核心范围/共享接口/产品旅程均有实质变化，不能以 R7 Approved 或局部 closure 放行。
- started_at: 2026-10-15T01:25:07+08:00
- completed_at: 2026-10-15T01:32:03+08:00
- duration: 416s（完成受审文件预读后，按正式证据核对计时）
- baseline: HEAD `89c47478b054b8d788022752213ff6d494b5f9d9` 加本轮冻结 spec/design/prototype/两份 delta；DSH `0.2.1-alpha.1` 与参考源码 `5badb15009ae1756c3afe0ae0cef1faafc290ccc` 不变。
- working_tree: unit 恢复 active，另有两份未实施 denylist 红测待改写；本轮只追加报告，没有修改这些文件或产品代码。
- retained_from: R1–R4 已证明的公开包管理接口、workspace profile、generation URL 与私有 pnpm 接线；R5/R6 的现有真实设置页桌面/窄屏基线可作相邻界面参照。R6/R7 的逐工具 denylist 方案已被明确取代，其 Approved 不覆盖本轮插件方案。

### Verdict

**Issues Found — 0 CRITICAL / 4 WARNING。**

bundle 作为插件管理单位、原生目录和可信 owner 控制面的方向合理。尚需闭合服务 realm、空闲占位、异步退出完成，以及新增插件页的实际设计画面证据。

### Full Coverage 与架构判断

#### 用户目标、范围与 delta

- 新 spec 保留原始需求及用户关于“各种插件、独立插件开关、自主构思并保留服务”的最新授权。支持 workspace preset 可运行的工具、提示词及事件/服务组合，明确不做宿主 runtime/provider 替换、全局市场、OS 沙箱或 iOS 新页，范围有边界。
- 两份 delta 继续锚定当前 canonical `89c47478b`，以原 Requirement 标题 MODIFIED，保留安装/失败/重启/原工具禁用等仍成立 Scenario，并增加零工具插件、网页与模型管理同一原生状态、停用后更新保持关闭等结果。本轮没有重新引入已取代的 denylist 字段。
- 用户场景覆盖工具和零工具插件的真实效果、包目录、开关/卸载区分、workspace 共享、忙碌、离线/未知、失败修复和持久化。M1 追加 integration/Node/IM/Web/手册，仍单一交付，没有并行文件归属冲突；未实施红测要改写而不是作为产品已具备新能力的证据。

#### 现状与原生生命周期

- 已有 `workspace-tools.ts` 确实将标准 bundle 解析为 Cordis Include 子树，并没有只允许 tools 注册的类型检查；`systemPrompt.section()` 是原生 scope-aware 贡献（参考源码 `packages/core/system-prompt/src/index.ts:446-462`）。因此工具之外的提示词插件不需要另一套 Agent Loop。
- 原生 `PluginManager.listBundles()` 从 dependencies/selected bundles 读取，普通 bundle 不因零 tool schema 消失，错误包可携带原生诊断；`setBundleEnabled()` 保存选择，`removeBundle()` 负责原生包移除及保护检查（参考源码 `packages/boot/plugin-manager/src/index.ts:277-329,452-459,617-644`）。选择原生 bundle 而不是工具名或反复重装，是正确职责划分。
- generation 解析仍从可信持久 file: 来源使用公开 parser，外部包替换仍保留 restart-required；更新停用包时先读旧选择、在 owner 受控事务内恢复再刷新，可以沿用既有 changing/watcher 边界。网页不开任意安装参数，模型安装仍经既有审批与构建批准；原始静态工具权限/空集/子任务 mask 没被包开关替代。
- 标准 service 与异步 ctx.effect 使旧“当前树 audit 成功即已应用”的证据不再充分，独立原生探针发现 R8-W1 与 R8-W3。它们属于本轮明确支持的服务/资源生命周期，不是要求支持未托管任意定时器。

#### 可信控制面与忙碌协调

- 设计 `95-100` 行按真实 Agent 配置解析 workspace；IM 复用 human access session、`requireProfile()` 和所属 Node，Node 再核本机 Agent，integration 再查配置。现有身份函数的确分别核 access session/owner/space 与 Node 归属（`apps/im-server/src/identity.ts:326-342`、`control.ts:441-458,565-580`）。HTTP 不接收 workspace 路径、只开放 list/set/remove，符合 creation/management 权限与普通聊天使用权限分离。
- 原生队列/包锁仍由 integration 内 owner/native manager 管理，Node/IM 只转发并投影，不新增镜像插件数据库。无现存会话时 acquire preset、后台动作持有 scope 到终态的决定，避免 pending 返回后 prematurely disposing 子树，责任清楚。
- pending 登记在 owner、等待不占 HMR/管理队列、模型新变更 busy 快速失败、list 旁路，确实针对“本回合等插件队列而网页又等本回合”的自等待链提供了设计。已运行安装先完成，再处理网页动作，也避免包状态被交错写入。
- 但 `whenIdle()` 本身不占有空闲期，pending 只拒绝新管理命令，尚未约束正常消息、Cron 或新子 Agent 在随后异步原生文件操作中唤醒。该安全应用窗口缺口见 R8-W2；不是建议在等闲时持 HMR 锁。
- pending 只表示进程内接受/等待，断线或进程重启后重新读原生事实、允许重试，不声称未执行动作已持久完成；错误/忙碌不投影为空列表。该反馈契约方向成立。

#### 产品体验与可核实边界

- 独立插件页优于继续扩充工具 pills：零工具包、版本/诊断、整包开关和卸载需要自己的阅读空间。设计给出了入口、共享范围置顶、卡片主信息、次级详情、行内卸载确认、空/错/离线、即时操作与 pending 的顺序；关闭与卸载语义分开，未把包启用等同每个 Agent 的工具使用授权。
- 新页使用既有 Agent 身份/页签/卡片，目标桌面与 390 宽，原生 iOS 明确 out-of-scope；must-match 已覆盖零工具目录、共享作用域、等待终态、卸载及三种非正常读取状态。调用方补充插件页隐藏表单 Save 控件并保留 Open chat，与“即时插件操作不进入表单 draft”的决定一致。
- 现有真实产品基线在 R5/R6 已经独立查看（同一产品代码 HEAD），包括 Tool Allowlist、workspace 只读卡和桌面/390 窄屏；本轮没有把这些旧画面当作新插件页视觉通过。当前截图仅能支持相邻容器参照，无法证明新增页关键交互，见 R8-W4。
- Runbook 已落实当前隔离 HTTP、测试身份、聊天/插件场景、PID/cwd/listener 核对与保留服务要求，且区分真模型与 fixture。最终更新 PR #359/等待 CI/不自动合并，不混同部署或安装器发布。本轮未启动或停止这些服务，也未操作用户 tab。

### 历史问题闭环

R1-W1、R1-W2、R2-W1、R6-W1 维持 closed。新 findings 来自本轮范围扩大；旧工具版安装/只读展示通过并不能代替这些新证据。

### Issues

#### R8-W1 — preset scope 不会自动隔离普通 Cordis 服务贡献

- **位置**：`spec.md:23`；`design.md:89-91,95,98`。
- **证据**：DSH scope 用于 scope-aware 注册路由，普通 `ctx.provide()` 默认写 root service realm。原生 preset 首次挂载除 `auditRows()` 外还专门调用 `leakedServices()`，拒绝 root service leakage（参考源码 `packages/preset/agent-preset-registry/src/mount.ts:205-214`）。现有在线 workspace Include 只做当前树 audit，没有这项检查（本仓 `workspace-tools.ts:129-148`）。
- **独立探针**：使用已安装公开 Context/createScope/Loader/Include/auditRows/leakedServices，A scoped Include 加载普通 `ctx.provide("reviewWorkspaceService","A-private")` 插件；输出 `audit={failed:[],pending:[]}`、`workspaceB="A-private"`、`leaked=["reviewWorkspaceService"]`。该插件没有恶意绕过，也不涉及文件系统沙箱。
- **未修后果**：本轮声称支持的普通服务插件会被误报加载成功，却把贡献暴露给 B，或因同一服务名在另一个 preset 再次装配而冲突；“沿用 DSH scope”不足以兑现 workspace 贡献隔离。
- **需要收口**：明确服务 provider/consumer 的原生 isolate realm 约束，以及在线挂载时对 root-realm leakage 的拒绝/退役与诊断路径；可复用公开 `leakedServices()` 和原生 isolate/group 契约，不要新增第二套 service runtime。手册与非工具验证覆盖该明确边界，不能承诺任意 ctx.provide 自动隔离。

#### R8-W2 — whenIdle 观察完成后没有保留安全应用窗口

- **位置**：`design.md:99`；`spec.md:70-74`。
- **证据**：锁定原生 `whenIdle()` 只追随当前 activityDone（参考源码 `packages/core/agent-loop/src/agent.ts:237-242`）；公开 `runMaintenance()` 才同步占有 true-idle 并把后续唤醒留在 inbox（同文件 `183-202`、公开 `dsh-agent` 类型）。本仓 `update-barrier.ts:44-55` 已明确“不能 await whenIdle 再停止”，通过同步 maintenance 占位和新 admission 检查解决相同窗口。
- **未修后果**：网页等到 idle 后调用 native set/remove 仍有异步文件/包操作；正常消息、Cron 或新子任务可在其间开始，新回合运行中又被 Include 撤销贡献。当前 pending 只让管理命令 busy，不能兑现“不取消在途任务/空闲安全应用”。
- **需要收口**：明确 workspace 范围的 idle reservation 与新 Agent/admission 协调，复用既有 UpdateBarrier/native runMaintenance 原理；覆盖匹配 workspace 的 root/children，保持其他 workspace 可运行，释放/失败/关闭时不自等待。保留“等待阶段不持 HMR、模型管理 busy 快退”的既有防死锁决定。验证输入/Cron 在 idle 已观察到、原生应用未完成的窗口到达，而不只验证开始时 Agent 忙碌。

#### R8-W3 — 移除条目后的当前树 audit 不等待旧 fiber 异步退出

- **位置**：`design.md:54-55,89,98-99`。
- **证据**：原生 `EntryGroup.remove()` 调用 `fiber.dispose()` 后立即从 tree.store 删除，不等待返回值（参考源码 `vendor/loader/src/config/group.ts:37-45,48-64`）；`EntryTree.await()` 只遍历仍在树中的 entries（`tree.ts:35-48`）。现有 command 在 refresh/audit 后即可返回 applied，移除路径还会继续 pnpm remove（本仓 `workspace-tools.ts:195-214`）。
- **独立探针**：已安装原生 Include 加载一个使用 `ctx.effect` 异步释放的资源插件，再 `root.update([])` 与 `auditRows(tree)`；返回 `failed=[]/pending=[]` 时 `cleanupCompleted=false`、`removedFiberStillDraining=true`。等待原 retiring fiber 的公开 inertia 后，受管清理才完成。不是未托管定时器的假设。
- **未修后果**：页面可能已显示停用完成或把包从列表移除，生命周期管理资源却仍在退出；卸载甚至可能先删除清理逻辑仍需读取的包文件。该终态与新非工具/资源回收承诺不一致。
- **需要收口**：明确记录并等待本次被撤销/替换的旧 fiber 的 quiescent teardown，再结束 pending/报告完成，且在原生 remove 包文件前等待退出；错误保留诊断。可用公开 fiber/已有原生 quiescence 语义，不要求修改 DSH。补一项异步 ctx.effect 退出尚未完成时不出现成功终态的验证。

#### R8-W4 — 新独立插件页仍缺关键状态的实际渲染证据

- **位置**：`design.md:103-121`，尤其 `113`；`prototype.html`。
- **证据**：本轮明确为视觉未验证草稿，新页/开关等待/卸载确认没有实际渲染；旧截图仅为配置页只读工具卡。设计却将桌面/窄屏全路径视觉检查全部放到 UI 实施后。共同标准明确“给用户作为可评审成果前，实际渲染”，并要求不能“把必要视觉检查推迟到实施验收”（[`prototype-and-runbook.md`](../../../../.claude/skills/change-design-author/references/prototype-and-runbook.md):46-48；由 change-design-reviewer 引用）。
- **未修后果**：新页签位置、范围提示与卡片密度、等待保留旧状态、错误/卸载确认的相邻操作，以及窄屏主次关系只能按文字猜测；这次不是直接复用一个已渲染普通 pill 的局部变化，旧画面不能证明新体验成立。
- **需要收口**：在允许的呈现途径中提供新独立页及关键状态的实际渲染和局部走查证据，区分真实背景/新增/模拟；或在没有允许途径时继续明确保持草稿与未验证门禁，不能仅据标注“视觉未验证”宣称 Gate 2 已通过。不要求真实后端提前实现，不要求绕过已拒绝的 file URL 策略，也不要求重设计无关设置页。

### Recommendations

无额外建议。上述问题一次收口后按实际变化复审，不继续追逐任意插件兼容性或全产品重设计。

### Author Resolutions for R8

- R8-W1 accepted：独立探针证实 root service 泄漏。design 新增原生 group/isolate 约束、公开 leakedServices 失败退役，以及 named realm 按 mount 限定；手册与原生回归覆盖正反例。
- R8-W2 accepted：whenIdle 不能持有安全窗口。改为 ConfigurationScopes 用原生 runMaintenance 同步占位、fresh Agent 集合及新 attach gate，等待不占 HMR，finally 释放；保留 manager busy 快退。说明与整节点 UpdateBarrier 的责任差异。
- R8-W3 accepted：更新前捕获旧 fibers 并等待公开 inertia，旧树不可见不等于已清理；drain 完成后才报告 applied/移除文件，加入异步 teardown 与期间输入回归。
- R8-W4 accepted：旧只读页不能证明新设计。新增原生 imagegen 生成的独立静态状态板 design-assets/plugins-states.png，并实际查看四种状态；它不是被拒绝 HTML 的另路渲染，不访问/转发该文件。HTML 浏览器渲染继续明确未验证。design 记录状态板语义修正、真实背景与模拟界限，提请 reviewer 独立判断新静态视觉证据是否足以审查方案；不要求因作者声称解决而放行。


## Round 9

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: R8 后有界修订服务 realm、workspace 维护预约、异步退出完成边界，并新增静态视觉设计产物；检查四项问题及其波及范围，不重复未变化的 Full 范围。
- started_at: 2026-10-15T01:36:56+08:00
- completed_at: 2026-10-15T01:40:30+08:00
- duration: 214s
- baseline: HEAD `89c47478b054b8d788022752213ff6d494b5f9d9` 加 R8 后冻结文档与 design-assets；DSH `0.2.1-alpha.1`，参考源码 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`。
- retained_from: Round 8 的目标/范围、canonical delta、可信控制面与包管理职责、工具权限、零工具目录、持久化、交付 runbook 判断；R1–R5 未受影响证据按 R8 所述保留。R6/R7 旧 denylist 提案继续视为已取代。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R8-W1、R8-W2、R8-W3、R8-W4 均 closed。此结论允许按修订后的标准插件方案实施，不表示新产品功能、动态交互或真实响应式已验收。

### Delta Coverage 与历史问题闭环

#### R8-W1 — closed：明确原生服务 realm 与在线泄漏拒绝

- `design.md:105` 已区分 scope-aware tools/systemPrompt 与普通 Cordis service，不再声称所有 ctx.provide 自动 workspace 隔离。provider/consumer 同放原生 group 并使用本地 isolate realm，正确沿用 loader 的 context 继承。
- 已核参考源码 `vendor/loader/src/config/isolate.ts`：`true` 创建 entry LocalRealm，子条目继承 parent isolate map；字符串 label 则通过同一 loader 的 realm 表共享。为所有 workspace 插件行的 named labels 加当前 mount 独有前缀，能保留同一挂载内有意共享，并阻止不同 workspace/preset 的同名 label 共享；没有要求修改 Cordis service 实现。
- 已核公开 `leakedServices(ctx, mountFiber)` 检查实际 fiber 子树归属及 root symbol（`packages/preset/agent-preset-registry/src/mount.ts:69-84`），动态 Include 可以像原生初次 preset mount 一样调用。新方案将泄漏条目诊断为 failed 并退役，避免把旧探针中 audit 成功但 B 可见的结果当作加载成功。
- 正确 group/provider/consumer、root leakage 负例与 B 隔离已纳入手册/验证要求。该边界服务于本轮明确支持的标准插件，不扩张为任意插件代码的 OS 沙箱。

#### R8-W2 — closed：观察 idle 后同步占位，并覆盖新 attach

- `design.md:99,109` 现在由掌握真实 Agent 归属的 ConfigurationScopes 协调：等待包含 children 的 workspace Agent，重新枚举，并在同一同步段逐一 runMaintenance；某个占位失败则释放部分持有并重试。等待阶段不持 HMR 锁，pending 拒绝后续管理命令且 list 旁路，保留防自等待约束。
- 已复核锁定实现 `packages/core/agent-loop/src/agent.ts:183-202,211-242`：runMaintenance 同步检查并设置 maintenance phase，随后原生 inbox 的唤醒延迟至 finally 释放。其 API 出现在公开 Agent 类型，且本仓 `update-barrier.ts:44-55` 已复用相同同步占位原理；不需要新 Agent Loop。
- attach gate 限于实际维护期。尚未登记的新 Agent 等待外部 workspace gate，已进入 attach 的 Agent 在首次 await 前登记并被 fresh enumeration 捕获。当前 `agent-config.ts:79-85` 确有登记先于异步装配的落点；原生 `agent/created` 契约等待 listener 完成才放行输入（`packages/core/agent/src/runtime-types.ts:247-261`）。该方案未在 created listener 等待自身 whenIdle。
- finally 释放、其他 workspace 不阻塞及 teardown 期间新消息/Cron 的回归场景均已说明。整节点 UpdateBarrier 与 workspace 控制面的职责区分明确，避免误用全局暂停。

#### R8-W3 — closed：退出完成边界跟随旧 fiber

- `design.md:107` 已明确更新前捕获包括子条目的原 fibers；撤销/替换后等待其公开 inertia，不能在旧条目离开 tree.store 后只审新树。失败条目退役同样纳入，释放完成前不报告 applied，也不先删除包文件。
- 已复核原生 `packages/core/scope/src/index.ts:115-118` 的 quiesceFiber：raw dispose 后循环等待 inertia；`vendor/cordis/src/fiber.ts` 公开字段及 await 使用相同收敛语义。这能兑现 R8 原生异步 ctx.effect 探针发现的窗口，无须 fork loader 或重建资源调度器。
- 异步 cleanup 起止标记、pending 仍在、卸载不先删文件及维护释放后输入继续的验证已写入 `design.md:107,141`。未把当前树 audit 当成退休资源已经清理的证据。

#### R8-W4 — closed：实际查看独立静态状态板

- 本 reviewer 实际打开并检查 `design-assets/plugins-states.png` 的图像像素与 README，而非仅阅读生成提示词或相信作者“已查看”。它是独立概念视觉稿，包含 Normal、Pending、Confirm uninstall、Mobile web 四面板；不属于真实产品截图，也不是被拒绝 HTML 的另路渲染。
- 图中独立 Plugins 页签、卡片前共享 workspace 提示、工具与零工具插件同级目录、可读名称/说明和真实状态开关，足以指导新增页的信息组织。卸载确认落在具体卡片内，说明共享影响和保留源码；没有额外 Save，符合即时管理。窄屏示意保留标题/说明与开关的同卡关系，单列和换行能作为实施参照。
- 本次没有把旧只读工具卡当作新页通过证据。与此前实际查看的 Agent 设置页背景对照，新增内容有自己的阅读空间，次级详情折叠的方向合理，未要求重设计无关设置页。
- 图中 Pending 同时标在两张卡、Uninstall 常驻、额外导航图标及示意域名均有清晰的正文修正（`design.md:123`）：只有目标卡显示待执行状态，其余仅禁用操作；卸载放展开详情；沿用真实 header/返回逻辑。这些是明确的实施裁决，未留下需实现者自行猜测的范围分歧。
- 静态视觉证据已覆盖本轮新增入口、层级和关键状态；错误/空列表/离线与操作路径由 `design.md:115,125-132` 明确约束。HTML 仍为未渲染交互语义草稿，没有绕过 file URL 限制；真实按钮行为、等待恢复及响应式像素仍由产品验收证明，未提前声称通过。

### Issues

无未解决问题。

### Recommendations

无额外建议。实施应遵循本轮已明确的图稿校正与原生生命周期验证，不增加任意包兼容层或扩大产品范围。

### 工作边界

本轮只追加 design-review.md，保留 R1–R8 与 Author Resolutions；未修改产品代码、设计或 prototype，未提交，未操作用户 Agent/浏览器 tab，也未启停隔离服务。文档 diff whitespace 检查通过；本轮设计审查不以未实现测试代替原生接口及视觉证据。


## Round 10

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: 同一 PR 的真实第三方插件验收暴露 workspace 宿主依赖解析遗漏；仅审原生 resolution 接线、映射更新和多 workspace 关闭顺序，不重复已通过的产品界面及整体 Full 设计。
- started_at: 2026-10-15T10:58:49+08:00
- completed_at: 2026-10-15T11:02:15+08:00
- duration: 206s
- baseline: branch `codex/feat-610-workspace-tools`，HEAD `48ecbfec267343bf6df6f2d577c21fb1a8ea7733`；受审增量为 design.md:143-151。审查期间作者按发现修订了同一增量段，结论针对最终两阶段映射更新方案。
- retained_from: Round 9 及其保留的公开安装接口、generation URL、workspace 隔离、idle reservation、异步 teardown、可信 API、持久化、视觉设计和产品验收边界；归档位置变化不触发重复全审。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

原生宿主依赖解析接线及更新/退出边界已经收口。此结论允许实施该主线程修复；不代表第三方 rollover 插件的 preset/service 激活、工具调用或真实上下文切换已通过。

### Delta Coverage 与证据

- **现场根因独立复核**：读取 `/tmp/rollover-plugin-1015/report.md` 和 probe-resolution.mjs，并以两个独立 Node 子进程实际重跑。baseline 退出 1，复现同一已安装 dsh-context-rollover@0.2.2 导入 Cordis 的 ERR_MODULE_NOT_FOUND；native 退出 0，仅使用公开 createRuntimeResolution + PluginPackages 后 IMPORT_OK。DSH 仍为 0.2.1-alpha.1，解析到宿主 Cordis 4.0.5-alpha.1。未给插件补装依赖、升级包、改服务或激活该插件。
- **产品落点与公开边界**：当前 WorkspaceOwner.create 确实只在 managerRoot 提供 profileContext，启动 Loader/PluginManager 后将插件加载到宿主 scoped Include；没有安装 profile resolution。`@deepseek-ai/dsh-app-boot` 公开导出 createRuntimeResolution、PluginPackages、RuntimeResolution 类型，已安装包的独立 probe 也实际使用这些 exports；符合只能由 dsh-integration 接入 DSH 的仓库红线。
- **职责划分**：workspace owner 已掌握可信 profile 路径与执行树生命周期，故在此拥有原生 resolver 合理；Node/IM 无须新增依赖复制、加载器或安装协议。`home=profile dir` 明确限制原生 profilesDir 的拦截范围，真实 installAnchor 保证共享宿主类/库。不同 workspace 使用独立 profile 表，不以同一张活动 profile 表覆盖全部 workspace。
- **管理事务与解析发布**：原生 PluginManager 在安装、启用和移除路径会寻找 pluginPackages 并自动 refresh（参考源码 `packages/boot/plugin-manager/src/index.ts:452-458,575-577,643,781-787`）。最终设计明确将 owner 的 PluginPackages 放在独立 service realm，不让 manager 自动刷新提前撤销映射；owner 用公开 API 计算最新表并发布，不需要改动 DSH 或私有导入。
- **生命周期顺序的审中修订**：初稿“外部配置变更刷新后再加载 Include”会违背公开 RuntimeInterception.replace 的约束：profile mappings/local names/linked roots 应在使用它们的插件停止后才移除。该点已反馈并在本轮报告前修正为“新增映射先发布，同时保留待撤旧映射 → Include update 与旧 fiber inertia drain → 发布完整新表撤旧”。原生 PluginPackages.replace 接受完整 RuntimeResolution，并将保留映射的目录/版本/scope 交给原生检查，因此可用薄表投影完成，无须自写解析器。
- **替换诊断**：已核 `profile-resolution/resolver.ts:375-411`，原生 replace 会拒绝保留映射的目录/版本/scope 更换、installation 映射改变及同名 linked root 改向。设计保留这些诊断，不清模块缓存、不将所有初次安装都误报 restart-required，也不将原生替换拒绝覆盖为 applied。现有 generation 下执行入口的 distinct URL 决定继续保留；profile 内 generation 不属于被 linkedProfileRoots 收集的外部链接根，新增接线不要求回退到 hoisted 副本。
- **多 workspace 关闭**：已核原生 interception 的 dispose 只在当前 hook 仍是本层 wrapper 时恢复上层，因此必须按实际注册逆序释放，不能沿用当前 owners Map 的正序 close 作为正确证据。最终设计已明确先结束执行 fibers，再按注册逆序释放 resolver；这也是多 workspace 初始化与退出实施必须遵循的边界。resolver 属于 runtime owner，不随一个聊天或 Agent 短期卸载而提前销毁。
- **Worker 范围**：公开 PluginPackages 还维护原生 Worker 环境数据，而 registerWorkerResolution 只有进程级单表。最终设计明确本轮验证主线程 workspace 插件，未宣称多 workspace Worker 已兼容；当前第三方试用未用该路径，本轮不要求新增 Worker 协议。
- **范围与验证**：这是现有标准插件安装/依赖共享契约的接线修正，不新增 HTTP 权限或 UI 交互。现有真实子进程 fixture 追加 Cordis/LLM imports 可防止原来仅注入 tools 的测试漏检；安装后调用、失败修正、重启、停用/移除、跨 workspace 与异步退出要求继续适用。新 Agent/新 workspace/新 global session 的真实模型验收已写明，旧失败现场保留；导入通过与 preset/service 真正激活分开验证。

### 历史问题闭环

R8-W1–W4 维持 closed。审中映射撤销顺序已在最终受审设计纠正，无未解决 findings；本轮没有以 R9 Approved 代替新证据。

### Issues

无未解决问题。

### Recommendations

无额外建议。

### 工作边界

只追加本报告，未改实现、设计或测试，未提交，未操作用户 Agent/浏览器 tab，未启停隔离服务。两次 probe 均为独立进程中的模块导入对照，不属于真实插件激活或产品验收。`git diff --check` 通过。


## Round 11

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: 第二层真实安装反馈新增默认 compaction 与 preset 自有后端的选择规则，并将首次 workspace owner 初始化串行以兑现 resolver 栈的释放顺序；仅审该有界增量。
- started_at: 2026-10-15T11:12:15+08:00
- completed_at: 2026-10-15T11:13:40+08:00
- duration: 85s
- baseline: HEAD `48ecbfec267343bf6df6f2d577c21fb1a8ea7733`，design.md:153 新增段；resolver 顺序修正已有工作树代码，compaction 方案尚未实现。DSH 0.2.1-alpha.1 与第三方 dsh-context-rollover@0.2.2 不变。
- retained_from: Round 10 的原生 resolution、两阶段映射发布、替换诊断和 Worker 限定；R9 及之前未受影响的 scope/管理 API/异步退出/产品设计证据继续保留。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

公开 preset 服务查询与 compaction 接口足以实现该分工，无需修改第三方包或全局覆盖宿主引擎。首次初始化串行补齐实际 resolver 注册顺序与 owner 记录顺序的一致性。真实 rollover 效果仍属于后续验收。

### Delta Coverage 与证据

- **原生 scoped 用法属实**：已读取实际已安装包的默认 cordis.patch.yml、README 和 presets/standard-rollover/agent.cordis.yml。默认 patch 注册 root compaction；preset 用法则使用原生 cordis:group、isolate.compaction=true，内部 context-rollover 配置 modelSurface='always'（该文件 138-155 行）。profile user patch 依照此方式调整 workspace 条目，保留原包，是合理配置入口；不将上游 host patch 自动改写为另一套隐式兼容规则。
- **默认引擎实际冲突落点**：本仓 cordis.patch.yml 关闭原生 compaction-basic 并装配 host NanoCompaction；NanoCompaction 当前只增加 focus summarize，继承 BasicCompactionEngine 的自动监听。因此隔离服务能避免注册同名冲突，但若不让默认后端让出，host 与 scoped 后端仍会同时接收自动触发。
- **公开服务选择**：AgentPresetRegistry.serviceFor(agent,'compaction') 根据 Agent 所属实际 preset mount，再通过 fiber 归属查询其服务（参考源码 `packages/preset/agent-preset-registry/src/index.ts:324-326`、mount.ts:99-114）。它查询 mount 子树的隔离服务而非返回 host 默认服务，能覆盖 preset 内动态 Include 贡献，也不会以工具名或用户文本推断后端归属。
- **自动路径可窄覆盖**：BasicCompactionEngine 的 pre-step pressure 与 request-error overflow 均动态调用 this.compactIfNeeded（参考源码 `packages/compaction/compaction-basic/src/index.ts:145-164,205`）。NanoCompaction 在存在 preset 自有引擎时返回无处理结果，即可让出两条自动路径；没有时保持原 Basic 行为，不必改原生私有 listener。第三方自己的 compactionOwnedElsewhere 也使用公开 serviceFor 并比较真实服务实例，其 preset 实例不会把自己误判成另一个后端。
- **人工路径闭合**：真实 session 命令落在 model-policy.ts 的 compact 分支，经 whenIdle 调用 host NanoCompaction.compactFocused；在此选择 preset 自有引擎并调用公开 compactNow(agent,signal,commandId)，保留原生 idle maintenance、取消与命令关联。CompactionEngine 的公开抽象方法包含 compactNow（`packages/compaction/compaction/src/index.ts`）；第三方实际实现也采用此签名。自有引擎负责其压缩语义；只有默认 summarizer 使用原有 focus guidance，符合本轮明确裁决，不向第三方强塞 Nano 摘要实现。
- **停用回退与权限**：同一原生 workspace 管理流程在维护窗口撤销 scoped 服务并 drain；之后 serviceFor 不再返回该贡献，默认自动及人工摘要分支恢复。其他 workspace 的 Agent 对应不同 mount，保留默认逻辑。包开关继续独立于 tool_allowlist；modelSurface=always 提供 model-facing 注册，不自行授予静态禁用工具或 plugin_manager 权限。
- **resolver 顺序**：只有反转 Map 不能保证并发异步 create 的实际安装顺序。新设计明确首次 owner 初始化串行；当前接线落点是 WorkspaceExtensions.creating promise 链，记录 owner 后按该链创建，关闭时反转 owners。这样无需新解析器或复杂注册表就兑现 R10 的原生 LIFO 契约；已存在 owner 的查询/日常管理不需要因此串行全部 workspace。
- **验证边界**：新增真实 session compact 命令与 compaction 事件路由回归、其他 workspace 不变、停用回退与真实模型使用要求合理；自动回归应覆盖 pressure/overflow 的同一动态入口，不能只以人工 compact 成功推定双后端已消除。本轮只核设计与接口，未执行尚未实现的 compaction 修复，也未声称真实 rollover 已通过。

### 历史问题闭环

R8-W1–W4 及 R10 映射撤销顺序继续 closed。首次 owner 串行是 R10 逆序释放决定的有界落实；本轮未引入全局 service 覆盖、private import 或另一套 Agent Loop。

### Issues

无未解决问题。

### Recommendations

无额外建议。

### 工作边界

仅追加 design-review.md，未改产品代码、设计或测试，未提交；未操作第三方包、用户 Agent 或现存服务。`git diff --check` 通过。


## Round 12

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: 真实重启暴露 relay 启动前补发 global 输入回执导致启动失败；仅复核恢复顺序这一处有界变化。
- started_at: 2026-10-15T11:22:26+08:00
- completed_at: 2026-10-15T11:22:39+08:00
- duration: 13s
- baseline: HEAD `48ecbfec267343bf6df6f2d577c21fb1a8ea7733` 加当前工作树；design.md 最后一段和 apps/node/src/main.ts 单条件增量。
- retained_from: Round 10–11 的 resolver/compaction 及此前插件 scope 设计。此次不改变插件接口、持久化、权限或视觉设计，不重复全审。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

将首次 global 恢复延后至 relay ready，有现存回调承接；运行中 DSH 重启且 relay 已 ready 时仍立即恢复。无需删除持久输入或改变回执协议。

### Delta Coverage 与证据

- 已读 `/tmp/rollover-plugin-1015/start-stack.log`：错误确从 runtime onReady → GlobalAgent.recover → receipt → relay.request 传播，RelayDeliveryError 标为 not-sent；不是插件 scope 加载失败。
- 组装入口的真实顺序是 await runtime.start()，之后才 relay.start()（main.ts:286-291）。因此 startup onReady 直接执行需要联网回执的 recover 会阻止代码到达 relay.start；新增 relay.ready 条件切断此启动依赖环。
- 已核既有 relay.onState ready 回调仍调用 globalProduct.recover（main.ts:180）。WebRelayConnection.setState 先发布状态再异步触发回调，ready 属性读取该状态；首次连接后有可靠恢复入口。运行中 DSH 重启若 relay 已连，runtime onReady 保留同一 recover；若未连，则由后续连接 ready 承接。
- GlobalAgent.recover 仍执行 main/controls/reconcile/wake；回执确认位于 receipt 成功之后，持久 pending 输入没有因跳过早期调用而被确认或删除（global-agent.ts:106-109,324）。本次只改变调用时机，保留原数据、补发与 ACK 边界。
- 修复后原失败状态可启动并创建新 Agent 为作者报告的现场证据，本 reviewer 未独立启停服务或宣称第三方插件安装/rollover/重启验收已通过。新 GPT Agent 的真实安装仍按既有验收继续。

### Issues

无未解决问题。

### Recommendations

无额外建议。

### 工作边界

仅追加本报告，未修改产品/设计/数据，未提交，未干预正在运行的真实 Agent 测试。`git diff --check` 通过。


## Round 13

### Metadata

- reviewer_target: 同一独立 reviewer `/root/workspace_tools_design_review`（Codex）
- review_mode: delta
- mode_reason: R12 的整次 global recover 延后方案影响飞书离线自治，已弃用；本轮独立审查替代的 Web receipt 局部暂缓方案，不复审插件主体。
- started_at: 2026-10-15T11:23:42+08:00
- completed_at: 2026-10-15T11:24:22+08:00
- duration: 40s
- baseline: HEAD `48ecbfec267343bf6df6f2d577c21fb1a8ea7733` 加当前工作树；apps/node/src/main.ts 已还原，最终设计是 GlobalAgent.reconcile 中 Web receipt 条件暂缓。
- retained_from: R11 及此前未受影响结论；**R12 对已放弃 main.ts guard 的 Approved 结论 superseded，不可作为最终方案或实施依据。** 历史文本保留供追溯，以下结论取代它。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

最终方案仅在 relay.ready=false 时暂缓 Web 回执，保留 pending 且不 confirm；本地/飞书恢复照常。R12 只检查启动与重连调用链，遗漏了整次 recover 延后对 external 离线恢复的影响，本轮纠正这一判断。

### Delta Coverage 与证据

- 最终 design.md 最后一段已明确保留 global 本地/飞书离线恢复；main.ts 没有工作树 diff，startup 与 relay ready 的原 recover 入口全部保留，避免将外网 IM ready 变成飞书恢复的前置条件。
- 真实产品组装中 GlobalAgent 的 relay 是 ExternalChannels（main.ts:234），其 ready 反映 Web relay，但 `node.delivery_receipt` 的 `external:` 路径在 ExternalChannels.request 内独立本地处理并返回 ACK（external.ts:95-99）。因此仅跳过非 external: 回执符合实际通道责任；不能因为 Web 未连而跳过整个 GlobalAgent.recover。
- reconcile 在完成 turn 的 completedInputs 循环内暂缓相应 Web receipt，随后仍执行其他输入、工作投影、children 与 wake；未修改 main/controls/reconcile/wake 的整体恢复顺序。成功 receipt 后才 confirmReceipt 的顺序保留。
- 重连可重新处理已持久化 turn/end：reconcile 不只遍历新 observe 结果，还从 NodeStore 全部持久 events 生成 logicalEvents。InboxStore.completedInputs 只选择未写 receipts 记录的输入；离线跳过没有写确认，重连 ACK 后确认，正常重复 recover 不再投递已确认项（global-agent.ts:300-327；inbox.ts:151-154）。没有删除输入或伪造回执。
- 已查看 receipt-red.log：旧代码在离线 Web receipt 上抛错；receipt-green.log 显示当前全部 32 项通过。独立运行本轮新增 public GlobalAgent + 真实 InboxStore/NodeStore 回归，结果 **1 passed / 31 skipped**。用例验证离线 external 已处理而 Web 仍 pending，连接后 Web 投递并确认，再次 recover 无重复回执。这里证明正常成功 ACK 后的重复恢复行为，不扩大为未知网络结果的全局 exactly-once 保证。
- 此局部修正不改变原生插件 scope、resolver 或 compaction 设计；真实重启与第三方插件效果仍按既有产品验收执行。本轮未干预正在运行的新 Agent。

### 历史问题闭环

R12 已被本轮最终方案及审查结论取代。R10–R11 未受影响，继续 retained。

### Issues

无未解决问题。

### Recommendations

无额外建议。

### 工作边界

仅追加本报告，未改实现、设计或数据，未提交，未操作服务/用户 Agent。`git diff --check` 通过。

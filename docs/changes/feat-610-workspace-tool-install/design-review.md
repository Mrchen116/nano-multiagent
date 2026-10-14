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

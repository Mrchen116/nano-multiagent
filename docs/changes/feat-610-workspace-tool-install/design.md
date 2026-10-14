# feat-610: Agent 自助安装 workspace 工具 — 技术方案

> 对齐 spec.md。DSH 基线：锁定 npm 0.2.1-alpha.1；本地参考源码 5badb15009。

## Changelog

## 现状分析

### 涉及范围

- `packages/dsh-integration/src/extensions.ts` 只在 preset 装配时读取两层 `plugins.json`。
- `agent-config.ts` 为每个产品 Agent 的原生 preset 装配知识与工具；`capabilities.ts` 在执行与声明层强制工具选择。
- `client.ts` 每次准备公共 profile 都重写 `package.json` 和 patch，不能把 workspace 安装清单存进这个公共 profile。
- `cordis.patch.yml` 关闭 `tool-plugin-manager`，防止 Agent 修改同节点所有会话共用的 profile。
- 随包产品手册需说明新的 workspace 安装入口。

### 既有约束

仅在 dsh-integration 通过 DSH 公开 exports 使用运行时；不 fork、patch 或 private import 上游，不引入第二个 Agent Loop。保留现有 owner/workspace 两层工具及同名覆盖；保留用户工具选择与子任务继承限制。现有显式空工具集仍为空。

### 可复用能力

- 使用 `@deepseek-ai/dsh-plugin-manager` 的原生 `PluginManager` 服务：包安装、manifest 选择、兼容性检查、锁、安装取消、失败恢复、构建批准与移除。不开通公共 profile 的管理工具。
- 使用 `@deepseek-ai/dsh-app-boot` 的 `loadProfileDirectory`、`composeEntries`、bundle 解析和公开兼容性 API；不自己解析 bundle YAML。
- 使用 `@deepseek-ai/cordis-plugin-include` 的原生 Include 在各 workspace preset scope 挂载和更新插件树；使用宿主原生 HMR 的 `runExclusive`/`watchConfig` 串行刷新。热加载的是 workspace 子树，公共宿主及正在执行的管理工具不被卸载。
- 复用原生 tools 的 scope 层和 Nano 执行审批。自建工具依然通过原生 tools 执行，不通过脚本外壳逃开审批。

### 相关历史

refactor-581 保留了两层工具隔离但只实现静态声明装配。既有 capabilities 原生进程测试覆盖空白名单、跨 workspace 覆盖和重启，继续保留。新增安装测试保护静态装配测试尚未覆盖的在线安装、撤销和失败结果。

## 架构总览

每个 workspace 在 `<workspace>/.nanoassistant/dsh-plugins/` 保存标准 DSH profile（package.json、cordis.patch.yml、node_modules）。一个节点仍只有原有 DSH 执行进程；每个 workspace 的包管理服务是独立 Cordis Context 内的原生 PluginManager，没有模型或执行 loop。该管理 Context 的 Loader 不加载执行插件，因而它只负责持久包状态；执行插件交给宿主各 workspace preset 内的原生 Include。

WorkspaceExtensions 服务统一拥有 profile、管理 Context、对应 preset Includes 和刷新队列。多个同 workspace preset 共享安装清单并分别获得同一工具贡献；其他 workspace 的 scope 不在其刷新集合内。

## 关键决策

**复用原生管理服务，并在 Nano 边界提供 workspace 版 `plugin_manager`。** 保留原生操作名 `list_bundles`、`install_bundle`、`set_bundle`、`remove_bundle`，不提供可以修改公共宿主、其他 profile、preset 的动作。参数中不接受 workspace 或 Agent identity：它们由可信执行配置解析。

**包状态和执行 scope 分工明确。** 原生 manager 在未加载执行插件的管理 Context 工作，原生 package result 的 `restart-required` 只描述该 Context；Nano 完成所有相关 Include 的实际加载检查后才返回 `application: applied`。包安装失败沿用原始失败；加载失败返回 `application: failed` 与诊断，绝不能把 pnpm 退出 0 当作安装可用。

**本地自建 bundle 安装为不可变版本产物，修正后重新安装不复用旧模块 URL。** 管理入口接受 workspace 内本地 bundle 目录，将本次源文件复制到该 workspace profile 的独立 generation 目录（不复制 .git/node_modules），再用原生 `installBundle(file:<generation>)` 安装。自建 bundle 的插件行使用相对文件入口，DSH patch 解析把它们锚定到本次安装产物的绝对 URL。新安装、更新或失败后修正重装都获得独立 URL；不操作 Node 模块缓存、不缓存补丁、不自行实现 HMR。标准文件产物和依赖完全由原生 pnpm 安装。已安装 bundle 的 source 继续指向版本产物，因此重启仍可加载；用户源目录与已运行版本解耦。普通 registry/git 包替换若原生返回 restart-required 则保留它，不能假称已热加载。本地免重启路径限定 bundle 插件行的相对入口，拒绝本地源 bundle 中指向旧绝对模块或裸包入口的执行行并给出修改指引。

**安装许可与既有静态工具选择分开。** `plugin_manager` 是可选工具，默认候选开启，但已存在的显式名单不静默加入它。用户启用管理能力后，其 workspace 新安装的独立工具名自动进入有效工具集合，不修改其他静态工具选择。显式空集、关闭管理工具的 Agent、受限制子任务均不因此扩权。与安装前既有名称冲突的工具不自动获得授权。安装工具集按原生 scope 与选中的 bundle 重新推导，不维护第二份工具白名单数据库；停用/移除通过 `plugin_manager` 控制整个 bundle。该有限例外归并到 current spec，并在产品手册解释。

**沿用 Nano 的工具执行审批。** workspace 版管理动作和新工具走已有 pre-execute 审核；原生构建批准参数只用于用户明确批准的包。这里不另外叠一层原生 profile 全局权限升级，因为暴露的入口已经限定 workspace，且正常 Nano 审批对这一动作负责。Agent 创作使用正常 write/edit/bash，管理工具描述给出标准 bundle 的最小文件形态。

**持久初始化只创建缺失文件。** workspace profile 不随运行时启动重写；root profile 继续作为产品托管配置，不安装用户 bundle。相同 workspace 的多会话重启从同一清单装配。

## 接口与数据流

- `WorkspaceExtensions.attach(ctx, config)`：用真实 `config.workspace`（缺失时不启用）取得 owner，挂载 workspace 版管理工具与 Include，返回该 preset 当前新增工具名查询。相同 workspace 路径规范化，不由模型传入路径。
- `WorkspaceExtensions.tools(agentId)`：返回该 Agent 的 workspace 自动工具名；ToolSelection 只在主 Agent 选择含 `plugin_manager`（或未限制默认集）时并入。子任务仍由既有继承工具 mask 决定。
- 安装：管理工具已通过 Nano 审批 → 原生 manager.installBundle → 原生 profile 解析 → 各 scope Include 更新 → 等待 Loader 与 fibers、检查失败条目 → 返回实际应用状态、包诊断和新增工具名。
- 停用：先原生选择取消，再更新所有 Include 并等待退出；移除先停用/卸载执行树，再调用原生 removeBundle，避免删除仍在使用的文件。
- 失败：保持 manager 实际磁盘结果与诊断；无关 bundle 的 Include 条目不变化。修复本地源后再次 install_bundle 创建新 generation，由原生安装器更新依赖，再实际验证新 URL 的加载与调用；禁止重复导入失败旧 URL 并声称恢复。
- Node capabilities 与 configuration.selection 使用同一有效工具集合；公共 profile 的新增工具不影响其他 workspace。无需新增 IM API 或客户端 UI。

## 契约层增量

- gateway/agent-capabilities：workspace 自助安装、有限自动工具集合、在线启停和持久化，见 `specs/gateway/agent-capabilities.md`。

## 风险与回退

原生插件在节点进程内执行；workspace 隔离是能力发现、配置和调用 scope 隔离，沿用本机插件信任边界。管理工具不能借名单名称覆盖已禁用默认工具。非本地包替换仍受上游重启限制；本地产物每代路径不同，并验证文件 URL 确属当代产物。加载失败必须检查真实 Loader 状态；无关已用工具不受影响。关闭 plugin_manager 撤销自动获得的工具集合，已有标准 profile 文件保留以供恢复。

## Runbook for Reviewer

执行前读 `docs/development/worktree-runtime.md`。仅在 unit worktree 使用隔离 IM、Node、DSH、workspace、数据库和身份。启动 `./scripts/e2e-up.sh`，停止 `./scripts/e2e-down.sh`，具体 CLI 参数按脚本 help 和生成 manifest 操作，不触碰生产服务。

Review 驱动方式：不改客户端，用客户端真实的 IM 消息接口驱动端到端真栈。要求 Agent 在 A workspace 创作并安装简单确定性工具、立即调用、在另一个聊天调用；B 尝试不可见；正常重启该隔离节点后续聊；停用/移除；失败 bundle 返回明确结果。验收前置：隔离测试模型服务或真实已配置模型，不能把直接调用运行时工具等同真实聊天验收。真实进程回归 fixture 可作实现证据，不替代 reviewer 真栈。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-workspace-tools | 接通 workspace 原生安装与热装配 | 无 | 单组 | dsh-integration、Node capabilities 必要接线、产品手册、原生进程测试 | [reviewer] spec 全部场景；[worker] 锁定 DSH 原生服务和 loader 实际安装/启停/失败/重启测试，跨 workspace 不可发现及实际 dispatch 拒绝，旧工具禁用和空集保持，相关 typecheck/tests/docs-check 通过 |

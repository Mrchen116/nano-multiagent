# feat-610: Agent 自建 DSH 插件与 workspace 插件管理 — 技术方案

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

**本地自建 bundle 安装为不可变版本产物，执行 patch 从真实 generation 解析。** 管理入口接受 workspace 内本地 bundle 目录，将本次源文件复制到该 workspace profile 的独立 generation 目录（不复制 .git/node_modules），再用原生 `installBundle(file:<generation>)` 安装。原生 pnpm 使用 hoisted node_modules，因此不能从安装副本取得执行入口。执行层读取标准 profile dependencies 中本次保存的 `file:<generation>`，对确属本 workspace generations 根的来源使用公开 `readProfileManifest`、`bundlePatchPaths`、`loadOverlayPatches` 解析该 generation 的 patch；其他包继续使用原生 loadProfileDirectory 的 layer。自建 bundle 的插件行使用相对文件入口，原生 patch parser 将其锚定到真实 generation 文件 URL。新安装、更新或失败后修正重装由此获得独立 URL；不操作 Node 模块缓存、不自行实现 HMR。依赖仍由原生 pnpm 安装，并从 generation 的祖先 profile/node_modules 解析。持久 file: 来源决定重启时的执行 generation；不建立额外映射数据库。普通 registry/git 包替换若原生返回 restart-required 则保留它。本地免重启路径限定 bundle 插件行的相对入口，拒绝指向旧绝对模块或裸包入口的执行行并给出修改指引。

**安装许可与既有静态工具选择分开。** `plugin_manager` 是可选工具，默认候选开启，但已存在的显式名单不静默加入它。用户启用管理能力后，其 workspace 新安装的独立工具名自动进入有效工具集合，不修改其他静态工具选择。显式空集、关闭管理工具的 Agent、受限制子任务均不因此扩权。与安装前既有名称冲突的工具不自动获得授权。安装工具集按原生 scope 与选中的 bundle 重新推导，不维护第二份工具白名单数据库；停用/移除通过 `plugin_manager` 控制整个 bundle。该有限例外归并到 current spec，并在产品手册解释。

**沿用 Nano 的工具执行审批。** workspace 版管理动作和新工具走已有 pre-execute 审核；原生构建批准参数只用于用户明确批准的包。这里不另外叠一层原生 profile 全局权限升级，因为暴露的入口已经限定 workspace，且正常 Nano 审批对这一动作负责。Agent 创作使用正常 write/edit/bash，管理工具描述给出标准 bundle 的最小文件形态。

**持久初始化只创建缺失文件。** workspace profile 不随运行时启动重写；root profile 继续作为产品托管配置，不安装用户 bundle。相同 workspace 的多会话重启从同一清单装配。

## 接口与数据流

- `WorkspaceExtensions.attach(ctx, config)`：用真实 `config.workspace`（缺失时不启用）取得 owner，挂载 workspace 版管理工具与 Include，返回该 preset 当前新增工具名查询。相同 workspace 路径规范化，不由模型传入路径。
- `WorkspaceExtensions.tools(agentId)`：返回该 Agent 的 workspace 自动工具名；ToolSelection 只在主 Agent 选择含 `plugin_manager`（或未限制默认集）时并入。子任务仍由既有继承工具 mask 决定。
- 安装：管理工具已通过 Nano 审批 → 原生 manager.installBundle → 原生 profile 解析 → 各 scope Include 更新 → 等待 Loader 与 fibers、检查失败条目 → 返回实际应用状态、包诊断和新增工具名。
- 停用：先原生选择取消，再更新所有 Include 并等待退出；移除先停用/卸载执行树，再调用原生 removeBundle，避免删除仍在使用的文件。
- 失败：保持 manager 实际磁盘结果与诊断；无关 bundle 的 Include 条目不变化。修复本地源后再次 install_bundle 创建新 generation，由原生安装器更新依赖，再实际验证新 URL 的加载与调用；禁止重复导入失败旧 URL 并声称恢复。
- Node capabilities 与 configuration.selection 使用同一有效工具集合；公共 profile 的新增工具不影响其他 workspace。新增插件管理 RPC/API 与独立 Web 插件页签，见下节。

**安装版使用自带 pnpm。** Node 已验证为 managed release 时，initialize 传入安装器固定 tooling/pnpm 的绝对命令与私有 PATH 环境；integration 只把该可信启动事实传给原生 ProfileContext.packageManager。源码模式保留原生默认。workspace profile、插件选择与包生命周期不变；不要求全局 pnpm，不修改节点全局 PATH。

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

## 插件级管理修订（2026-10-15，取代工具 denylist 提案）

### 产品与职责裁决

采用 DSH 标准 bundle 作为用户可安装、开关和卸载的单位，UI 称“插件”；一个包可以包含多条 plugin entry，也可以没有 tools。列表来自原生 listBundles 的安装清单，不能靠工具 schema 反推插件存在。展开详情展示包名、版本、原生条目及诊断；优先使用原生 metadata 的可读名称、package description。Nano 仅负责 workspace scope、可信控制转发与状态投影，不再新增 workspace_tool_denylist 或第二份启用配置。

比较：工具过滤只能阻止调用，无法停止提示词/监听器/服务，故不作为插件开关；反复卸载/重装有安装成本且丢失包选择，故关闭使用原生 setBundleEnabled，卸载使用 removeBundle。Cordis Include 卸载 fiber 清理 ctx 注册及 ctx.effect 资源；作者需用生命周期 API，不能保证任意未托管定时器自动清理。

已接通的 loader 加载标准插件，没有只允许 tools 注册的类型检查；缺口是创作指引、包目录/API/UI 和非工具验收。更新 plugin_manager 描述及内置手册，给出工具与 systemPrompt.section + ctx.effect 两种最小模式。支持 preset scope 可用的原生能力；不安装新的全局执行 runtime，不提供修改宿主 profile 的入口。workspace 隔离沿用 DSH scope 与插件信任边界，不声称任意 Node.js 代码具备文件系统沙箱。

### 接口与状态

1. `WorkspaceExtensions` 仍唯一拥有 workspace profile、管理 Context、Include mounts 和原生队列；新增供可信控制面使用的 `manage(config, command)`，不从 HTTP 接受 workspace 路径。无现存会话时通过既有 preset acquire 装配 scope，再查询；后台动作持有 scope 到终态，不能在 RPC 返回 pending 时先卸载。
2. integration RPC `plugins.manage` 接受 `{agentId, action: list_bundles|set_bundle|remove_bundle, target?, enabled?}`。只查真实已配置 Agent；通过 ConfigurationScopes 调用同一 WorkspaceExtensions。模型工具仍支持 install_bundle，网页不开放随意包安装。
3. Node `node.plugins.request` 验证 agentId 在本节点并转发，返回 `node.plugins`。IM `GET /im/v1/agents/:agent_id/plugins` 和 `POST .../plugins`（仅 set_bundle/remove_bundle）使用现有用户认证、requireProfile 与归属 Node；拒绝多余 scope/路径参数、未知动作和无效 enabled。不存镜像插件数据库。Node/IM 不 import DSH。
4. 响应 `{workspace, entries, pending?, error?}`。条目包括 name/display_name/description/version/enabled/state/rows/removable/diagnostics；state 为 enabled/disabled/failed，只有真实 Include audit 后才可显示 enabled。pending 含 target/action/enabled，覆盖本 workspace 的控制面操作。异常包从安装清单保留；停用不依赖加载成功。共享影响文案始终可见。
5. 网页动作在 owner 内登记一个 pending 并后台串行执行。ConfigurationScopes 先等待当前 workspace 各 Agent（含子任务）的 whenIdle，再重新枚举当前 Agent，并在同一个同步段用公开 runMaintenance 占有每个 Agent 的原生空闲阶段；一个未真正空闲则释放已占部分后重新等待，不强行取消。维护期间新唤醒留在原生 inbox，现有回合不被中断。新 Agent 的 attachAgent 在登记前检查 workspace maintenance gate，维护期间等待 gate 释放后再附着并启动；已在附着的 Agent 在首次 await 前登记，故会被再次枚举捕获。只有完成原生操作、Include audit 与 retiring fibers drain 后释放。失败用 finally 释放，shutdown 不持有不可释放的锁。等待不持 HMR 锁。新管理动作（模型或网页）在 pending 期间明确返回 busy，list 不进入该队列，避免当前回合调用 manager 被自己等待的任务锁死。已经执行中的安装先完成，再执行用户动作。busy 的 Agent 不强制取消；首次 idle 安全边界应用，不阻断其他 workspace。
6. pending 是进程内执行状态，不宣称已保存。进程结束后尚未执行的操作需用户重试；前端以重新读取原生 profile 的状态为准，HTTP 成功接受不当作应用完成。完成状态/诊断可通过列表轮询，busy、离线与未知结果不变成空列表。Web 查询请求不受长操作阻塞；操作失败保留错误并允许重试。
7. install_bundle 更新同名已安装且停用的包时，未显式 enabled 参数默认保持停用（原生 listBundles 读取旧选择，安装后同一受控事务内恢复选择，再刷新执行 scope）；新包仍默认开启。已有静态工具选择逻辑保留：管理获准时自动并入不冲突的新工具名，空集和子任务 mask 不扩权。插件开关不改 tool_allowlist，也不自动授予 plugin_manager。

### 原生服务隔离与异步退出

DSH scope-aware 注册（tools、systemPrompt）按原生 scope 路由；普通 service provider 必须在本地 isolate realm 中，与 consumer 一起放入原生 group，例 `group:true,isolate:{expenseService:true},config:[provider,consumer]`。工具描述和手册明确这一写法，不声称任意 ctx.provide 自动隔离。在线 Include 更新除 auditRows 外，使用公开 `leakedServices(ctx, entry.fiber)` 检查根服务泄漏，泄漏条目作为 failed 退役并给出“use a local isolate group”诊断，不能作为 applied。所有 workspace 插件行的显式 named isolate labels 由薄 scope 适配加上当前 mount 独有前缀，保证同一 mount 内声明相同 label 的 provider/consumer 仍共享，其他 workspace/preset 不共享；`true` 沿用原生 LocalRealm。不重写服务实现或 fork loader。测试同时覆盖根泄漏失败、原生 group provider/consumer 成功与 B 无可见贡献。

每次更新前捕获现有条目 fibers（含子条目），更新及坏行退役后等待被撤销/替换 fibers 的公开 `inertia`，同时等待新树 audit。旧 fiber 即使已从 entries 移除也必须 drain 后才能返回 applied 或删除包文件。异步 ctx.effect teardown fixture 将 cleanup 起止写入 workspace 文件，在释放未完成时观察 pending，并验证卸载未先删文件。若 drain 抛错则保留失败诊断，不声称完成。这里复用公开 Cordis 生命周期，不重建资源调度器。

原生维护与 update-barrier 的区别：电脑更新需要拒绝整个 runtime 的 admission 并暂停所有 Cron；插件切换只维护一个 workspace，并让已有 Agent 的后续输入排在原生 inbox，其他 workspace 继续运行。因此复用 runMaintenance 的占位机制与既有模式，不直接使用会暂停整节点的 UpdateBarrier 实例。维护协调属于 ConfigurationScopes（掌握实际 Agent 归属）；包队列和 pending 属于 WorkspaceExtensions。

### 前端体验设计

入口：现有 `/settings/agents/:id` 顶部页签，紧邻“技能”新增“插件”，可直接访问 `?view=plugins`。配置 Access & Model 保留静态工具选择，workspace 工具只读块删除，放一个“管理 workspace 插件”的导航链接。沿用现有 Agent 标题、电脑身份、页签与卡片间距；插件操作独立即时生效，不进入 Save Agent 草稿。插件页隐藏表单 Save 控件并保留 Open chat。独立页签让来源说明、安装错误和卸载操作有足够空间，避免挤进密集工具 pills。

插件页阅读顺序：标题与说明 → workspace 共享范围 → 插件卡片。卡片左侧可读名称、描述与状态，右侧真实开关；次级详情折叠包含包名/版本/条目/诊断和卸载操作。卸载展开行内确认，说明保留源码且影响共享 workspace，确认/取消均明确。关闭不需要确认。pending 期间保留原状态，显示“等待空闲 / 正在应用”，相关操作禁用并定期刷新，完成后恢复；错误就近显示并可重试/刷新。刷新按钮始终可找到；空状态给一句自然语言示例，让用户回聊天创作。离线显示“暂时无法读取”，不冒充无插件。英文/中文沿用现有 i18n。

桌面使用单列卡片，长名字换行，次级信息折叠降低密度；窄屏标题/状态与开关保持同卡，详情和确认按钮可换行，无横向滚动。使用 role=switch 与 aria-checked，等待/错误使用 status/alert。页面最上方始终显示管理范围，防止误以为只影响当前 Agent。

### 原型与体验契约

本轮新增独立静态视觉设计稿 [plugins-states.png](design-assets/plugins-states.png)，由 imagegen 内置工具按本节体验要求生成，并直接查看图像检查了正常、等待、卸载确认与390宽移动 Web 的层级。它是概念状态板，不是产品截图或 HTML 渲染；不访问、代理或转发此前被拒绝的 file:// HTML。左侧 rail、Agent 身份和顶部页签是现有产品背景；插件内容、状态与确认框是本次增量；图内按钮不可操作，流程以本节和 HTML 草稿为准。现有真实基线为 `/tmp/feat610-review/plugins-baseline.jpg`，作者本轮在获准的真实 HTTP 产品页重新查看。

视觉走查：独立页签减少工具区拥挤；scope 提示在卡片前，用户先理解影响再操作；名称/说明为主、详情为次；等待保留已开启开关但降透明度；确认放在具体插件卡片内；窄屏单列允许说明换行。图稿需按明确约束校正：pending 文案只贴本次目标插件，其他卡片只禁用操作；卸载统一放在展开详情内，降低常驻危险操作的视觉权重；示意图中额外顶栏搜索/通知图标和移动浏览器域名不属于实施范围；真实移动 Web 继续现有 header 与返回逻辑。图像只证明状态信息组织，动态等待/恢复与响应式像素表现必须由真实客户端验收。

[prototype.html](prototype.html) 保留为交互语义草稿。file:// 呈现曾被策略拒绝，HTML 的浏览器视觉仍未验证，不把静态生成图称为已执行 HTML；可评审的视觉产物为新状态板。关键状态可通过图板连续阅读和 HTML 源码事件路径检查，真实按钮行为在产品验收独立观察。
| 区域/状态 | 裁决 | 真实入口与 viewport | 退出标准 |
|---|---|---|---|
| 插件独立入口与范围提示 | must-match | settings Agent，桌面和390宽 | 不借工具列表即可找到零工具插件并理解共享作用域 |
| 开关与等待/终态 | must-match | plugins 页，闲/忙 | 无额外 Save，等待不伪装已应用，真实行为停止/恢复 |
| 错误、空列表、离线 | must-match | 同页 | 三者可区分，失败插件保留可管理 |
| 卸载确认与结果 | must-match | 同页 | 确认具体包和共享影响，完成才从列表消失 |
| 卡片视觉细节 | may-adapt | 现有 im-agent-card 与按钮体系 | 长文换行，无水平溢出，主次明确 |
| 原生 iOS | out-of-scope | 现有设置继续运行 | 本次不新增原生管理页 |

### 验证与交付

M1 仍单一交付，不分层派 worker。追加范围 integration/Node/IM control/Web插件面板/内置手册。保持已有安装、坏包重试、持久化、空名单、跨 workspace 测试；把未实现 denylist 红测改成插件控制面的 busy→完成→停用→重启→重开→卸载。非工具 fixture 用原生 systemPrompt.section 注册独立标记，通过真实模型输入或 prompt assembly 证明 A 生效/B 不生效/停用撤销/重开恢复；ctx.effect 清理文件标记可补充资源回收。前端测试保护独立零工具目录、pending 与错误不谎报、卸载确认；IM 测试保护身份、节点归属、参数约束和错误透传。Node真实控制转发由 E2E 覆盖，不为私有转发函数增加 mock 镜像测试。

Reviewer runbook：保留既有隔离栈 http://127.0.0.1:54267、账号 nano/nano1234、Agent e2e、聊天 c_pp1ump8j。用当前 worktree 的 pnpm build 和 Web build 更新产物，先核对 .gateway-state.json/PID/cwd/命令与 listener 后仅重启隔离进程，保留数据库、workspace、端口和身份；不用会重建数据的 e2e-up。通过真实聊天让 LLM 创作一个零工具报销报告格式插件，与现有 expense_summary 组合使用；在专用浏览器 tab 操作开关并继续聊天对照。保留可体验的已启用插件、示例结果与测试服务；用户明确要求保留，最终不执行 e2e-down。终止仅限本次验收辅助进程。最终更新现有 PR #359 的标题/描述为实际插件范围，等待 CI 全绿，不自动合并。

R8 后追加验证：web pending 等待阶段仍可 list；在 teardown 被 gate 阻塞时再提交消息/Cron，新回合在维护释放后执行，B workspace 不受阻；async cleanup 完成前不显示 applied；root service leakage 报失败并移除，正确 isolate group 的服务/consumer 在 A 生效且 B 无贡献。既有故障修复 fixture 与 UI pending 测试承担这些边界，不增设相同失败原因的多层重复用例。

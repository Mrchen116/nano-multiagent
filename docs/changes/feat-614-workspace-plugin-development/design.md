# feat-614: Workspace 插件开发能力与指导 — 技术方案

> 对齐：[spec.md](spec.md)，含 2026-10-15 用户追加的完整实施与真实 Agent 轨迹验收要求。

## Changelog

- 2026-10-16：真实模型更新旅程暴露既有热更新缺陷：原生 loader 保留同 id 的已加载模块，单改 generation 路径不重载。integration 在公开 EntryGroup 生命周期内释放路径变化的旧条目、等待资源清理，再应用新条目；不修改或绕过 DSH。此修复兑现既定更新场景，不改变支持范围和架构决定。添加同名同版本更新后立即实调及同 workspace 共享回归。工具指导补足会话 cwd 和公开文件服务写入策略的查询提醒，来自真实失败。

## 现状分析

### 涉及范围

- `packages/dsh-integration/src/workspace-tools.ts` 注册 Nano 的 `plugin_manager`，持有可信 workspace 的 profile 与原生包生命周期；已有较长工具说明，但没有开发 API 发现动作。
- `packages/personal-assistant/assets/skills/` 随节点安装复制到 owner 技能目录，`nanoassistant-docs` 是产品手册而非插件开发入口。
- `apps/node/src/configuration.ts` 和 integration 的 `capabilities.ts` 管理技能目录与显式选择。维持现有发现与选择，不强行注入被禁用的 Skill。
- `workspace-tools.test.ts` 已覆盖安装、失败重试、热应用、共享与隔离、启停、重启和压缩 provider；`builtin-skills.test.ts` 覆盖随包支持文件刷新。

### 既有约束

仅 integration 消费 DSH 的已声明公开 exports；继续使用锁定版本，不 fork/patch 运行时。宿主职责和客户端边界见仓库 SPEC。可信插件不等于沙箱，资料不会承诺对任意 JS 的强隔离。本次不改客户端，无前端原型。

### 可复用能力

- 使用现有 bundle 管理、workspace overlay、隔离 service 与 scoped 工具注册，无新 loader。
- 使用随包技能安装与原生 Skill 目录/读取机制，无第二套提示词注入器。
- 使用安装包的公开 `package.json`、声明的 types、README 作为当前版本 API 依据；只返回支持主题需要的包，不复制整份 API 索引。
- 不使用原生 `cordis_inspect_*` 的完整 Host/Client inventory：它混合全局配置与 UI 插槽，当前需求仅需一个版本准确、主题有限的公开资料入口。
- `tools/result` 在锁定 DSH 的 tools 公开声明中注明 `Scope-filtered dispatch`、只读冻结结果、emit 模式；首版提供这个被动观察事件指导。`tools/change` 和 `system-prompt/change` 明确是全局通知，不作为局部事件模板。

### 相关历史

feat-610 已完成工作区管理与第三方依赖/压缩集成。本次补开发知识和可发现接口，保留其行为与测试；真实 Agent 曾需自行寻找包文档，本次应消除这条不必要的探索路径。

## 架构总览

用户目标 → 原生 Skill 目录发现 `nano-plugin-development` → 读取主题资料 → `plugin_manager.describe_api` 返回锁定安装版本的公开资料位置 → 原生 read 获取确切 API → 在 workspace 编写 bundle → 既有 install/update → 业务实调 → 验证与用户交付。

资料在 PA assets；运行时路径与版本发现只在 integration；Node 继续按现有流程安装 assets，不增加跨包依赖。插件源码、状态及生命周期仍归 workspace owner。

## 关键决策

1. **在已有管理工具上增加只读 `describe_api`，不增加独立工具或全局 inspection 权限。** 它与管理能力共用工具选择；不触发包安装、不枚举配置值、凭据、其他会话或 workspace。读取不因 workspace 变更 pending 而阻塞。
2. **返回资料入口而不是自制 API schema。** 针对有限主题解析已声明依赖的真实 package manifest，返回版本、包目录、存在的 README 和 manifest 中显式声明的公开 types 路径。Agent 用原生 read 读取并按需跟进声明内引用。缺少资料明确报错，不猜 `src/`。类型可读不意味着所有方法都在 Nano 支持范围；每个主题返回 supported surface 提示。
3. **文档先分流，模板只覆盖三个稳定模式。** 一次性计算用已有工具，可复用做法用 Skill，多步调度走 Workflow/Cron。持久执行扩展才写插件。提供 tool、prompt、isolated-service 三个可直接复制并安装的最小 bundle；events 与 compaction 用按需指南，避免把高风险策略藏在默认模板中。
4. **局部事件首版只推荐被动 `tools/result` 与插件自己拥有的文件监听。** 过滤自己关注的工具名；不保存敏感参数；不改冻结结果，不重新分发工具，不递归触发；文件监听必须有 cleanup 和明确目录。同 workspace 不同 Agent 各有 preset mount，禁止假定插件全节点只实例化一次；共享数据写入需按实际场景设计，不在模板造通用锁系统。
5. **压缩复用公开 BasicCompactionEngine 和隔离 compaction provider。** 指导先读当前配置与公开方法，优先配置/继承现有引擎，不重写事务和配对逻辑；保持自动与人工路径、停用恢复及失败可见。开发过程中不对真实生产历史实验。
6. **真实模型评估区分理解、安装、业务效果和持续行为。** 不在用户测试提示词里指定 Skill 名、工具参数、代码或成功操作顺序。保留首轮失败与修复轨迹，不以重跑成功掩盖原样本失败。仅在明确测试授权内通过产品审批，不改审批实现。

## 接口与数据流

### `plugin_manager` 开发查询

扩展 `PluginCommand.action` 为包含 `describe_api`；增加 `topic` 枚举 `tool | prompt | service | events | compaction`。该动作要求 topic，其余已有动作、参数和 UI 管理入口保持原语义；不将该动作加入网页 mutation 路径。

返回对象包含 `workspace`、`runtimeVersion`、`topic`、`supported`（适用能力与限制）、`packages`。包项含 `name`、`version`、`packageDir`、`readme`（存在才返回）、`types`（显式公开入口及绝对声明文件路径）。所有路径来自宿主已声明依赖的 manifest，非模型任意 package 名。未知主题拒绝。禁止返回 profile 依赖安装目录之外的任意文件内容或配置 secret。

主题映射：

| topic | 包 | 支持提示 |
|---|---|---|
| tool | dsh-tools | register、参数与 output 契约；不覆盖静态工具 |
| prompt | dsh-system-prompt | section/context；独立命名，不用 complete 或改宿主 section |
| service | cordis、cordis-plugin-loader | provide/effect 与 group isolate；资源释放 |
| events | cordis、dsh-tools、dsh-scope | 被动 tools/result；声明中的其他可见事件不自动获支持 |
| compaction | dsh-compaction、dsh-compaction-basic | 公开引擎与配置、隔离 provider、自动/人工及恢复 |

管理工具 description 只保留动作、Skill 路由、workspace 共享范围、真实生效判据和 build approval 约束。完整创建/配置教程移入 Skill refs。原生技能 disabled/allowlist 选择仍生效；工具路由写明仅在 Skill 可用时加载，不把 Skill 读取设成新的硬安装前置。

### Skill 资产

入口用中文写清触发（创建/安装/更新/配置/排障插件）与最短流程，技术名保持原文；按主题引用 bundle、tools、prompt、services-events、compaction、verification 资料以及三个模板。说明模板路径以 Skill 载入返回的 base 为准，不猜用户 home。模板包不携带第二份 DSH，复用宿主公开依赖；插件数据目录由 workspace 明确传入，不能写安装 generation。

`nanoassistant-docs` 保留产品操作、选择及信任边界摘要，开发内容链接专门 Skill，避免两份完整教程。随包 installBuiltinSkills 现有流程负责刷新，无需强制加入每个 Agent 的显式 allowlist。

## 契约层增量 (delta-spec)

- Gateway：新增“Agent 获得适用版本的 workspace 插件开发指导”，目标 `docs/specs/gateway/agent-capabilities.md`；[delta](specs/gateway/agent-capabilities.md)。既有生命周期条目不重写。
- IM：无 API/UI 变化，无 delta。

## 风险与回退

- 模板和锁定依赖漂移：真实安装三种模板，并让真实模型读取当前包资料；不写逐句文案测试。
- 读取公开类型可能接触未支持 API：返回适用边界、Skill 重申，产品试验包含宿主/UI 请求；这是可信代码的使用契约，不伪装安全沙箱。
- 事件资源泄漏/跨 scope：永久测试用两个 workspace、停用后再发事件，观察贡献变化；模板不绕过原生 ctx 生命周期。
- 真实模型无法发现/读懂资料：通过轨迹识别具体断点，修正提示入口或资料后在新场景复验；不手工替模型写成功插件。
- 回退移除新增发现动作与开发 Skill，恢复旧工具说明；不删除用户已创建插件或状态，不改变现有安装格式。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Node/DSH | `./scripts/e2e-down.sh --wt "$WT_ROOT"` | `PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-up.sh --wt "$WT_ROOT"` | 本次 `.e2e-ports.env` 的 IM `/openapi.json`、`pnpm pa status --config "$WT_ROOT/.gateway-config.yaml"` |

启动前 `pnpm install --frozen-lockfile`、`pnpm build`、前端构建；跨调用用受控长寿命进程运行。更新隔离配置后仅重启本次 Node，不重跑 up 覆盖数据。清理由启动者执行，验证端口和 Node/DSH 退出。

**Review 驱动方式**：端到端真栈，不改客户端，使用 Web IM 客户端同一登录、Agent 配置、聊天发送、消息/轨迹读取、审批、插件管理与压缩接口驱动；不绕过 IM 调用 runtime RPC 冒充产品验收。不宣称浏览器视觉或物理 iOS 验收。

**验收前置**：本机 `http://127.0.0.1:4000/health` 代理可用；模型从仓库 E2E config 目录选择，首选默认 DeepSeek，至少一个不同模型做创作交叉样本。不得读取生产 channel/凭据；默认无 Feishu。使用隔离测试账号、两个不同 workspace，另创建同 workspace Agent/聊天作共享对照。插件管理及文件读写通过产品配置开启，禁用一个无关工具保持对照。默认技能发现、正常 Auto 权限，人工审批只放行本次测试范围。

### 真实 Agent 旅程与轨迹证据

| 场景 | 自然语言目标 | 实际效果证据 |
|---|---|---|
| 工具 | 把 workspace 内几份报销 CSV 按月份/类别汇总，形成以后可重复使用的插件 | Agent 自行读指导/查 API/写包/安装并原生调用；两组人工已知总数正确 |
| 提示词 | 每次报销分析按固定结构输出，但不要修改每个聊天的提示 | 独立新聊天看到格式贡献，停用后贡献撤销，不靠旧聊天自述 |
| 服务和局部监听 | 建立资料检索插件，资料变化后能查到新内容，并记录该插件检索的次数 | 插件私有服务/数据、局部监听与 cleanup；其他 workspace 的调用不计数，停用后不再更新 |
| 压缩 | 创建适用于当前 workspace 的保留关键决策的压缩插件 | 真实压缩事务完成，自动及人工路由、保留信息、停用回落；无足够历史时不把 no-op 当成功 |
| 组合与边界 | 定时汇总业务数据；另问“能否给 iPhone 加按钮/修改审批/安装任意代码” | 既有调度/交付链、准确范围与信任说明 |
| 生命周期与失败 | 修改原插件、重启、关闭/移除；一次受控坏源码或实际自然失败后修复 | 实调与管理状态对账，同 workspace 共享、其他 workspace 隔离、既有选择保持 |

每条记录模型、时间、配置、会话/消息标识、首轮与修复次数、Skill/接口查询是否真实发生、关键文件及安装/业务结果、耗时和最终可见交付。日志/数据库/生成插件源码为本地证据不提交；unit 记录脱敏轨迹摘要与定位。独立 reviewer 自己驱动关键创作旅程并逐条覆盖 spec，不能仅复述主 Agent 报告。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-plugin-development | 开发入口、资料与真实创作闭环 | 无 | 无 | integration workspace-tools/开发查询、PA skills、相关 tests、current docs | [worker] 有意义的新查询红绿测试；有限主题解析公开安装包，未知主题拒绝、pending 只读可用；三个模板真实安装使用，事件作用域/撤销验证；已有生命周期测试 keep，无重复文案断言；构建、类型、CI 等价检查。[reviewer] spec 全部旅程；真实模型独立完成工具、提示词、服务/监听及压缩场景并观察轨迹，保留初次失败，不以安装成功代替业务生效；准确边界、跨 workspace 和生命周期不回归。 |

# Skill 禁用名单设计

## 方案与实际流程

用户在实现前确认 Workspace/全局均采用禁用名单。首版 design 在实现前记录了核心方案；两端体验契约、delta 与 runbook 在实现后的独立 Round 1 提出缺口后补齐。实现提交为 `11f3ceafc`，此前没有独立门禁。以下材料不补称事前审批。

`skills_selection_mode=explicit_denylist` 时，沿用 `skills` 字段存禁用名称，避免第二套同步、指纹或配置通道。原生 DSH provider/watcher/registry 继续负责发现和刷新，Nano 同时过滤 list/get，保持 roots、同名优先级与 Agent scope。目录 prompt 沿已有会话快照/重建边界，按名加载可在当前 Session 后续步骤使用新文件；不为新 Skill 自动重建缓存前缀。

Node 认证连接 IM 后请求 `/skills/migrate`。IM 验证 Gateway owner/node，以该 Agent 的完整真实候选减旧已选集合，通过既有 config operation/CAS 同步 YAML/runtime/profile。default 对应空禁用名单；已迁移不再转换；离线不猜候选。旧 allowlist 无候选历史，只能保迁移时已有候选的状态，不能推断上次配置后新复制的文件。失败保留旧模式，不应阻断其他 Agent 或已初始化 runtime 的恢复；已有 pending operation 先恢复再按当前 canonical profile 完成迁移。

已有 Session 对新增禁用立即收紧；放宽和其他配置沿已有 idle replacement。Skill 创建事实仅继续来源记录、后台通知与 acknowledge，不改启用配置。工具权限、自进化来源策略、F3 普通后台复盘和 F4 特定 Skill 使用记录专项复盘不变。

## 契约增量

- [Gateway delta](specs/gateway/agent-capabilities.md)：禁用名单替代旧 allowlist 规则，保留离线旧模式、蒸馏禁用、安全收口；完整保留被修改 Requirement 的其余场景。
- [IM delta](specs/im/agents-nodes.md)：新配置语义和首次编辑/认证迁移；只读 mirror 本身仍不写配置。
- 首版提前修改的 current specs 已恢复到实施基线；门禁通过且 final sync 后再按受审 delta 归并。旧显式清空保证改为“当时取消的名称持续禁用”，未来新名称默认启用；这是已确认的行为变化。

## 前端原型与体验契约

本次只改变选择语义与说明，沿用已有页面和操作。Web 从 Agent detail 的 Access & Model 区，按 Workspace/Global/Compatibility 分组辨认来源，pill 表示启用，组计数/混合态支持批量后微调；统一页级草稿/保存反馈避免误以为点击已生效。iOS 从 Agents → profile → Configuration → Skills，继续折叠来源组、名称/路径/说明和原生开关，顶部 Save 与页面保存结果确认变更。路径较长带来的行高是既有布局，本次不重做列表。

[prototype.html](prototype.html) 是实现后补充的局部状态对照，覆盖同一任务的 Web 和 iOS 呈现；外层明确标注模拟，不冒充真实产品。真实原生正常态见 [native-design.png](evidence/native-design.png)；Web 实现后独立观察见 [design-review](design-review.md) Round 1。没有旧版截图；“沿用旧布局”来自 scoped source diff，视觉观察明确来自本次实现后的客户端。

| 区域/状态 | 级别 | 内容关系与交互约束 | 入口/viewport | M1 投影 |
|---|---|---|---|---|
| Skills 说明与来源 | must-match | 选择之前可知勾选=启用、新名称默认可用；来源相邻，避免混淆 Workspace 与共享目录 | Web create/detail，1440/390px；iOS create/config，iPhone | [reviewer] 能辨认来源和动作后果；[worker] 两端截图/操作对照 |
| 单项与组选择 | must-match | Web pill/数量/混合态一致，组操作后可微调；iOS 各来源开关代表启用，顶部 Save 表达未提交 | 同上，正常/取消项 | [reviewer] 取消保存后重开仍关闭；[worker] 真实交互与 payload 一致 |
| 缺失禁用名称与目录失败 | must-match | 缺失名称不被静默启用或清除；Web 保留不可见的禁用名称，iOS 保留并以 stored/not reported 标注。能力失败明确显示重试，保留草稿，不把失败当空目录 | 编辑页，候选消失/加载失败 | [reviewer] 文件恢复后仍关闭；[worker] 原名称保留回归证据 |
| 保存/预览/聊天 | must-match | 沿用统一保存、冲突/等待反馈；成功后 preview 和 SlashPicker 排除禁用名称，失败不显示成功 | 两端编辑/预览，Web chat | [reviewer] 连续保存→重开→预览/候选；[worker] 消费者一致性测试 |
| 平台布局 | may-adapt | Web 保留分组 pill 和批量操作；iOS 保留折叠来源和开关，不新增 Web 式组按钮 | 两端各自原页面 | 各端真实画面对照 |
| 审批/自进化策略 | out-of-scope | 原有工具选择、F3/F4 来源规则不变 | 相邻 Tools/Features 区 | 回归不修改工具/进化配置 |

原型走查与后续真实验收证据分别记录，原型不证明持久化。原生正常态已观察；保存/缺失/冲突等动态状态交独立产品验收，不借单测判体验通过。

## Milestone

| ID | 依赖/并行组 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-selection | 无 / 单一端到端 | product-contracts、dsh-integration、PA、Node、IM、Web、iOS、specs/tests | [reviewer] 两端创建/编辑默认启用，取消保存→重开/刷新仍关闭；Workspace/global 新名称默认可用、同名重建仍禁用、其他 Workspace 不泄漏；preview/SlashPicker/显式调用一致；工具和进化选择不变。[worker] 原生 Session 内复制/加载/禁用/重启、迁移 default/allowlist/空名单/pending恢复/失败隔离、CAS指纹与镜像持久化、忙碌收紧及idle放宽、Web/iOS契约测试与真实画面对照证据成立。 |

## Runbook for Reviewer

环境由主 Agent集中准备，生命周期也由主 Agent负责；reviewer 不改生产/主仓/受版本控制配置。隔离契约见 [worktree-runtime](../../development/worktree-runtime.md)。

- 专属 checkout：`/Users/czj/.codex/worktrees/workspace-skill-denylist/nano-multiagent`。`pnpm build` / `pnpm typecheck`；Web `npx vite build`（完整 tsc 有基线 timer 类型问题，见 verification，不声称全绿）。
- 启动：`PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh --wt "$PWD"`。脚本隔离 IM端口/数据库/JWT、owner根、DSH home、node identity 与 Workspace。读取 `.e2e-ports.env` 的 IM_URL；`curl -fsS "$IM_URL/health"` 并核对测试账号 nodes online。已运行时只验证健康，不无条件重建。
- 测试账号来自 repo E2E config：nano / nano1234；仅本次隔离服务使用。Web 进入 `$IM_URL/settings/agents/e2e`；新建页同一导航。无需外部账号、Feishu、真机或其他外发资源。真实聊天/显式调用如需模型，只用 config/e2e 声明的本地代理，消息仅到隔离聊天。
- 测试 Skills 由主 Agent在 `.gateway-workspace/e2e/.nanoassistant/skills/` 和 `.gateway-owner/skills/` 放置有明确描述的 `review-workspace-note` / `review-global-note`；另一 workspace 的私有名称用于 scope 对照。reviewer 可在这些隔离临时资源内添加新名称、移走/恢复同名文件，保存常规配置；旧模式 fixture 的 YAML 只在节点停机后修改，Node重启后通过真实认证迁移。
- Node 单独重启：`pnpm pa stop --config .gateway-config.yaml` / `pnpm pa start --config .gateway-config.yaml`，不执行全栈 down/up（会清库）。重启后的 PID 由主 Agent更新，确认 profile/在线状态。
- 原生：`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`；build 脚本用 `NANO_IOS_BUILD_ROOT=/tmp/nano-skill-denylist-ios`。专用 iPhone17Pro Simulator `8BD1A09B-7349-44DB-85D3-24B764407C41`；安装其 Debug-iphonesimulator/NanoIM.app，`SIMCTL_CHILD_NANO_IM_BASE_URL="$IM_URL" xcrun simctl launch <UDID> win.nanoim.ios`。已登录 nano，Agents → e2e → Configuration → Skills。原生 CUA 的 AX滚动容器提供 Scroll Down；每次取新 AX索引，不复用旧编号。无真机验收声明。
- 旧配置、迁移指纹、busy-session 边界通过 verifier核对真实 runtime/HTTP回归证据；产品 reviewer 观察旧模式fixture上线后已有开关状态、后续新名称和禁用保留。不可观测内部协议不当作UI验收。
- 停止：主 Agent执行 `./scripts/e2e-down.sh --wt "$PWD"`，核对端口/Node/DSH进程释放；shutdown/delete 本次专用 Simulator。日志/数据库/截图缓存不提交，仓库 evidence 仅保留精选设计/验收画面。

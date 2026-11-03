# feat-703: PA 聊天创建 Agent — 技术方案

> 对齐: [spec.md](spec.md)，包括最终范围收口。

## Changelog

## 现状分析

### 涉及范围

- `apps/im-server/src/control-routes.ts` 持有节点能力读取和页面创建入口；`control.ts` 的 `ConfigOperations` 持有持久 configuration operation、Gateway apply 与恢复。
- `personal-agent.ts` 从已认证节点解析 PA binding，并以 `ownerMessage` 核对原始主人消息及当前访问资格。
- `packages/dsh-integration/src/personal-security.ts` 注册 PA 工具与身份指导；`packages/personal-assistant/src/global-agent.ts` 和 `personal-assistant.ts` 将可信执行身份经 Channels 送往 IM。
- 随包 Skill 位于 `packages/personal-assistant/assets/skills/`，发现和加载沿用当前 Skill 选择及原生加载机制。

### 既有约束

仅 integration 使用 DSH 公开 exports；Node 管理执行子进程，PA/IM 不 import DSH。主 PA 的产品管理权限不能被普通 Agent 或内部 child 继承。当前用户明确授权只做固定工具方案，不升级 DSH、不新增工具搜索或动态挂载。创建后的配置与工作区仍由既有 Gateway 契约校验。

### 可复用能力

- 用：节点能力缓存及其 owner/epoch/connection fencing、创建配置解析、Feature 依赖默认补齐、`ConfigOperations` 的队列与持久回执。
- 改：将页面创建准备与节点目录投影提取为 IM 内共享函数，Web 和 PA 共用；不经模拟 HTTP 身份或直写 Gateway 配置实现创建。
- 改：为 configuration create 支持宿主预先分配 operation id，让 PA 请求记录与实际创建操作建立精确关联。Web 不传此项，原行为保持。
- 不用：独立 Agent Loop、通用动态工具框架、第二套配置 apply/恢复状态机。

### 相关历史

feat-616 的 PA 主人来源边界和现有创建恢复契约继续适用；refactor-682 的目录缓存不被旁路。feat-703 已确认的电脑默认、创建前选项对齐和同次请求不重复批准均保持。

## 架构总览

`主 PA → agent_creation → ProductBridge → PA 产品处理器 → pa.agent.creation → IM PersonalAgents → 共享节点目录/Agent 创建服务 → 既有 Gateway configuration operation`

只有一项 milestone。无客户端代码变化；通过既有聊天发送、消息读取、Agent 列表/配置页完成用户旅程，不新增原型或界面控件。

## 关键决策

**1 个按需 Skill、1 个固定短 schema 工具。**

`nano-agent-creation` 说明选项对齐、配置组织、明确请求与失败恢复。`agent_creation` 始终使用同一 schema，不随 Skill 加载或选项查询增删定义。详细字段说明与真实候选由 options 返回。常驻工具描述保留“先确认选项、读取 Skill、结果未知先查原操作”所需最少指导。保持工具定义和顺序稳定只是前缀结构保证，不承诺服务端命中率。

**现有创建语义只维护一份。**

提取节点目录读取及 owner-scoped `createAgent` 服务供 Web 和 PA 使用。保持 Web 的参数省略、默认 Skills 固定、Feature 依赖、已有目录确认、ID 冲突及 durable operation 恢复语义。

**可信身份和创建请求分开。**

主 PA 身份由运行时 binding、根 session 与服务端有效 PA binding 校验；模型不传 owner、binding 或 node epoch。每次 create 必须带真实 `source_message_id`，IM 沿用 `ownerMessage` 核对未代发、PA 实际参与且有权读取的主人原文。对“创建”及配置选择的语义判断沿用当前主 PA 指导和普通工具执行权限，不新增语义分类器或关键词授权规则。观察文本不能建立新的创建授权。

**请求与 operation 精确绑定，状态不复制成第二套引擎。**

新增一张 `pa_agent_creations` 关联表，以 `(binding_id, request_key)` 唯一，保存节点、目标 Agent、冻结的输入和宿主 operation id。配置操作的 accepted/applied/committed/rejected 继续由既有表权威承载。相同 request_key 与不同配置/节点冲突；成功重试返回同一结果。状态读取只核对自己的关联操作，不把碰巧同 ID 的其他 Agent 当成成功。

## 接口与数据流

### 模型可见接口

固定参数：`action: options|create|status`、可选 `node_id`、`request_key`、`source_message_id`、`configuration`（object）。owner/binding/epoch/session 身份由宿主注入。

- `options`：返回本人电脑目录、PA 所在电脑为推荐项；选择的节点默认是 PA 节点。目标在线时返回该节点当前可用的 models/skills/tools/features、默认模型、默认工作区模板、审批继承信息与字段说明、推荐草稿。无可用节点/离线给明确错误或状态，不以空目录冒充成功。不查询或推荐他人节点；不擅自换机。
- `create`：必填 `request_key`、`source_message_id`、`configuration`。configuration 使用现有创建字段：agent_id、display_name、description、custom_prompt、work_mode、default_model、model_fallbacks、reasoning_effort、approval_mode、skills/skills_selection_mode、tool_allowlist、features、group_reply_policy、workspace_root、confirm_existing_workspace。未知字段不形成新权限。字段含义和候选不塞进常驻 schema。
- `status`：必填 `request_key`，仅处理该 binding 关联的既有操作；pending 使用同一 operation 恢复，不产生新意图。返回 `not_started|pending|created|rejected`，成功含 Agent 显示信息、实际电脑、配置与可用产品入口；错误保留稳定原因和原请求 key。status 不选择新的目标电脑。

### 创建过程与失败

1. 主 PA 因用户明确要求加载 Skill，调用 options；选项草稿和推荐值先在当前聊天与用户对齐，已明确的选择不重复询问。
2. create 在 PA 产品层拒绝非根 session；服务端复核 binding、原始主人消息、节点 owner。目标缺省采用 PA 节点。
3. 共享 per-Agent 队列内，冻结请求并分配持久 operation id；检查同 key 冲突和 ID 冲突。新操作在有效在线节点下才提交；先前已接受的 pending 操作沿既有恢复处理。
4. 共用创建准备和 `ConfigOperations`。真实 Gateway apply 后 IM commit profile 才返回 created；ACK 丢失或结果不明返回 pending，后续查原请求。
5. 节点、目录、模型、路径或能力校验拒绝时，准确返回失败字段/原因，不改成成功、不生成新 key 自动绕过、不静默切换节点。已有目录仍需要主人的明确确认，且保留已有文件。

### Context 消费与生命周期

Consumer 是主 PA；内部 child 和普通 Agent 均没有管理工具。创建 Skill 正文可通过当前允许的 Skill 机制按需加载，选项和结果作为普通工具历史保留，换窗按既有 history/Skill 路径恢复。新增 Skill 沿用显式选择/禁用，不能暗中绕过用户选择；工具描述提供加载入口和最少约束，Skill 不可用时如实说明指导不可用，不虚构已经加载。

Before：用户要求创建时，PA 只有页面创建知识和通用执行工具。After：Skill 目录有简短创建入口；实际加载后获得流程说明，再通过 options 获得目标电脑上的真实候选及完整字段说明。读取选项本身不是创建授权。

Validation：原生运行时捕获实际工具定义、Skill 目录/加载结果、options/create/status 结果以及调用后的产品状态。比较 options 前后 schema 与稳定提示词；真实模型从正常聊天请求完成明确交办、选项澄清、最终创建，并观察需求讨论不创建。受控 fixture 只证明接线与机制，不替代真实模型选择证据。

## 契约层增量 (delta-spec)

- Gateway PA：[specs/gateway/personal-agent.md](specs/gateway/personal-agent.md)，按明确要求创建、选项对齐、按需指导及固定工具入口。
- IM PA：[specs/im/personal-agent.md](specs/im/personal-agent.md)，长期 Agent 结果及主人/节点/请求恢复边界。已有 Agent 创建契约不复制。

## 风险与回退

共享创建提取可能影响页面路径：保留并运行原 control/configuration/catalog 覆盖。新增工具不能仅凭模型隐藏来保护：运行时、PA 产品层、IM authority 分层拒绝越权。未知结果必须保留原 request key/operation id。撤回发生在尚未提交时不创建；已经接受的配置操作如实确认实际状态，不伪造撤销。

回退代码和随包 Skill 即撤回新入口；保留关联记录及既有 configuration receipts，不删除已创建的 Agent、工作区或用户数据。

## 一次性部署迁移

无人工数据整理或依赖升级。关联表通过现有 IM schema 初始化机制增加；不改旧用户 Prompt、Skills 选择或既有 Agent 配置。Skill 可用性取决于当前选择，新增指导不强制覆盖用户选择。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Node/DSH | `./scripts/e2e-down.sh` | `./scripts/e2e-up.sh --profile daily` | 按 `.e2e-daily.json` 与 `.e2e-ports.env` 核对 IM、Node 和真实 PA |

**Review 驱动方式**：端到端真栈；不修改客户端面，使用客户端同一聊天 HTTP 接口代驱动，等待真实 PA 回复及实际创建结果；通过现有 Agent 列表和配置接口对账。

**验收前置**：先运行 `python3 scripts/dev_host.py check`；固定日常模板提供 P/E/Q+PA、真实模型和普通审批。为受测 PA 选择新增 Skill，保留其余日常配置。使用隔离节点、端口、workspace、数据和身份，不访问生产。缺少真实模型证据如实报告，不以 stub 充数。结束停止本次服务。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-create | 聊天创建闭环 | 无 | 无 | IM 共享创建/目录、PA 关联操作与协议、原生工具、随包 Skill、相关测试 | [reviewer] 明确要求后先问清真实选项、成功创建长期 Agent 并给出使用入口；普通讨论/撤回不创建；离线/冲突/未知结果如实说明；默认本机且不擅自换机。[worker] 原创建/目录回归通过；owner/观察/child/跨节点越权被拒；同 key 重试/重启/丢 ACK 恢复同 operation；原生请求证明 Skill 按需与固定 schema 不变；真实模型聊天旅程与隔离产品事实可复查；本地 CI、独立门禁通过。 |

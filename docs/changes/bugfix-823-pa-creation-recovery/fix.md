# bugfix-823: PA 创建失败回滚、悬停绑定自愈与未完成态入口收敛

Platform-Parity-Exempt: Web IM 与 Desktop 主窗口 WebView 共享本次聊天入口、欢迎页、创建恢复弹窗与助手列表修复；服务端 POST /im/v1/personal-agent 的确定性失败回滚与无在途操作 pending 绑定自愈对全端生效且保持既有协议结构；原生 iOS 已在 ChatListView、MeView、PersonalAssistantSetup 与 AgentsView 中按 creation == nil 守卫会话跳转，Node 运行时无客户端会话界面。

## Relations

- Related: feat-616, feat-773, feat-774, feat-799

## 原始报告

用户原始反馈：

> 用户私有化部署有问题，
>
> 他的弱agent给的分析说：
> ❌ 仍未解决（需上游继续跟进）
> #issue-j阻断--产品级pa-创建非原子失败后留下假会话--点不开--agents-页无此-agent Issue J（阻断 / 产品级）：PA 创建非原子，失败后留下"假会话 + 点不开 + Agents 页无此 agent"
> 现象：任何一次创建 Personal Agent 失败（catalog 超时 / 节点离线 / RPC 错误）后：
> 聊天页出现该助手（如"酷狗"）；
> Agents 页看不到这个 agent；
> 点聊天显示"聊天不可访问"。
> 根因：apps/im-server/src/personal-agent.ts 的 POST /im/v1/personal-agent 非原子：
> 先提交 personal_agent_bindings（status='pending'，含 conversation_id）；
> 随后 ops.recover/create 真正建 agent，可能失败；
> 失败后不回滚 pending binding；
> 前端把 pending binding 的 conversation 列为会话 → “假会话”；点进详情校验 agent/权限失败 → “聊天不可访问”；Agents 页按 agent_profiles 过滤 → 自然没有。
> 最新代码状态：personal-agent.ts 中未见创建失败回滚 pending binding 的逻辑（现有 pending 仅指 observation，不是 binding）。
> 影响面：所有用户只要创建失败一次就会复现，与本次 WSL 超时无关。
> 建议：创建原子化（失败回滚 pending binding/conversation），前端只展示 status='active' 的 binding，失败返回明确可重试错误。
>
> ---
> 帮我看看问题是啥。后面正式进入开发流程的时候，开subagent使用codex provider的gpt模型。

用户确认说明：

> ok可以。我意思不是你派gpt去做，而是说按照我们skill流程。派subagent的时候用gpt

## 现象 / 复现

1. 当个人助手（PA）创建请求未能完成激活——包括旧版私有化部署在能力探查超时/离线时遗留了 `status='pending'` 绑定记录，或当前版本在能力探查通过后执行节点创建操作被拒绝（如工作区初始化失败、能力依赖校验拒绝）或处于结果未确认状态（断连/超时）时：
   - 打开 Web 聊天页，左侧置顶个人助手入口已经显示该助手名字（如“酷狗”）和常规角色副标题，表现为已建好的助手会话；桌面端未选中会话时的欢迎页同样展示该助手卡片与快捷开场白。
   - 点击左侧置顶个人助手入口或欢迎页个人助手卡片，界面直接跳转到尚未创建的私聊地址，随即弹出红色错误提示“聊天不可访问”。
   - 打开 Web Agents 页，列表中没有该助手，仅显示一行静态文字“助手设置中”，没有继续或重试入口。
   - 若用户更换浏览器、清理本地缓存或从聊天页创建弹窗使用新的请求标识重新提交创建，服务端直接返回 `200` 且仍携带 `status='pending'` 的未完成绑定，创建弹窗误判成功并再次跳入“聊天不可访问”，同时存量遗留孤儿 `pending` 记录的用户无法换节点、改名或重试自愈。

### Requirement: 个人助手创建失败不遗留假会话且未确认态保持可恢复

#### Scenario: 确定性创建失败后干净回退并允许重新创建
- **WHEN** 用户首次创建个人助手时，节点离线、能力读取失败，或节点明确拒绝创建（如工作区或配置校验失败，不存在未确认的在途创建操作）
- **THEN** 客户端收到明确的可重试失败提示，不进入私人对话，也不在聊天列表、欢迎页或助手列表中留下半成品个人助手记录
- **AND** 用户随后可直接修改助手名字、头像、协作范围或选择在线电脑重新发起创建并正常完成

#### Scenario: 创建结果尚未确认时不展示假会话且支持原请求恢复
- **GIVEN** 个人助手创建请求已发往电脑但结果尚未确认（如网络断连或节点响应超时）
- **WHEN** 用户查看 Web 聊天页、工作区欢迎页或助手列表
- **THEN** 界面不会把未确认的个人助手当作已建立的私聊打开，不会触发“聊天不可访问”，而是明确提示助手尚未准备完成并提供继续/重试入口
- **AND** 当用户通过新请求尝试创建而原在途操作仍未确认时，系统先尝试确认原操作；若原操作已完成则直接激活并进入私聊，若仍未确认则返回明确提示而非假装创建成功

#### Scenario: 历史遗留孤儿未完成绑定的自愈恢复
- **GIVEN** 账号下存在历史遗留的未完成个人助手绑定（无在途节点创建操作且节点未建立该助手）
- **WHEN** 用户按原准备记录点击“重新准备”，或使用新的创建请求重新提交个人助手创建
- **THEN** 系统自动完成绑定更新与真实节点创建，成功后建立私人对话并正常进入聊天，不再永久卡在未完成状态

## 根因

1. **服务端未区分“在途未确认操作”与“确定性失败 / 孤儿 `pending` 绑定”，且对新 `request_key` 静默返回 `200` 未完成态**：
   - `feat-799`（`3086fcdd1` / `1642ad028`）已将 `readNodeCapabilitiesRaw` 移至插入 `personal_agent_bindings` 之前，消除了前置能力读取超时落库的问题；但在 `apps/im-server/src/personal-agent.ts` 的 `POST /im/v1/personal-agent` 中，写入 `personal_agent_bindings(status='pending')`、`pa_binding_scopes`、`pa_policies`、`pa_node_residencies` 之后调用 `await ops.create(...)` 仍缺乏失败分类处理。
   - 在 `apps/im-server/src/control.ts` 的 `ConfigOperations` 中，`ops.create` 存在两类结果：一类是节点通信未确认（`503 config_apply_pending`，`agent_config_operations` 处于 `pending` 或 `gateway_applied`），节点可能已经落盘创建；另一类是提交前校验抛错或节点明确返回 `status: 'rejected'`（`agent_config_operations` 标记为 `rejected`，`activeConfigOperation` 为空，`agent_profiles` 无记录），节点确定未创建该助手。当前代码在第二类确定性失败时不清理刚写入的 `pending` 绑定与策略表，导致无效 `pending` 状态永久残留。
   - 同时，`POST /im/v1/personal-agent` 开头的 `if (b && b.request_key !== input.request_key) return pa.state(u.owner_id);` 原本只适用于 `b.status === 'active'` 的幂等保护；当 `b.status === 'pending'` 时，任何携带新 `request_key` 的创建请求既不执行 `ops.recover` 也不报错，而是直接以 HTTP `200` 返回 `status='pending'`，既造成客户端误判创建成功，又锁死了历史遗留孤儿 `pending` 记录（含节点重新绑定后 `node_epoch` 推进的场景）的自愈路径。
2. **Web 前端多处把非 `active` 的 `binding` 当作已就绪会话使用**：
   - `conversations` 表实际在 `ops.create` 成功后才写入，但 `src/IM/frontend/src/features/chat/chat-workspace-page.tsx` 直接以 `const personalBinding = personalAgent.data?.binding` 驱动侧栏置顶项 `PersonalAgentEntry`、`showFirstUseWelcome` 与桌面端 `WorkspaceWelcome`（早年 `feat-616` `cf1befff9` 与 `feat-774` `f21b50686` 演进侧栏入口时漏掉了 `Agents` 页 `configuredPersonalAgent` 及 iOS `ChatListView` 已有的 `!state?.creation && state?.binding?.status === 'active'` 守卫）。
   - 因此 `status === 'pending'` 时侧栏仍展示助手名字并在点击时 `navigate('/chat/' + conversation_id)`，`GET /im/v1/conversations/:id` 返回 `404` 后被 `isAccessDenied` 判定并触发 `closeDeniedConversation`，弹出“聊天不可访问”。
   - `src/IM/frontend/src/features/personal-agent/personal-agent-dialog.tsx` 中 `create.onSuccess` 仅判断 `if (result.binding)` 即调用 `onCreated` 跳转会话，未校验 `result.binding.status === 'active'`；而 `recover.onSuccess` 在恢复成功转为 `active` 后又只刷新了 `['personal-agent']`，漏掉了刷新会话/联系人缓存并打开新建成的私聊。此外 Agents 页 `src/IM/frontend/src/features/settings/agents/personal-agent-entry.tsx` 在 `state?.creation` 存在时仅显示纯文本“助手设置中”，缺少继续设置入口。
3. **原始设计意图与修复必须保住的不变量**：
   - **原始设计意图**（源自 `feat-616`、`feat-773` `0ecde14e8` 与 `docs/specs/im/personal-agent.md`「刷新后恢复未完成的创建」「同次请求恢复与冲突」）：由于中心向 Gateway 节点下发 `agent.create` 时必须携带服务端分配的固定 `{ bindingId, ownerId, conversationId, epoch }`，一旦 RPC 发出后遇到断线、重启或回执丢失，服务端必须保留该次在途创建的身份锚点，使刷新重试能够通过 `ops.recover` 确认同一节点操作并收敛到同一个 `bindingId` 和 `conversationId`，不重复创建第二个 PA，也绝不在确认完成前打开尚未建立的私聊。
   - **修复必须保住的不变量**：
     1. 只要存在未决的在途配置操作（`activeConfigOperation` 为 `pending` / `gateway_applied`）或已落库的 `agent_profiles`，绝不回滚或覆盖 `personal_agent_bindings`，确保断连/超时后的同请求恢复幂等收敛。
     2. 已激活（`status === 'active'`）的 PA 保持唯一固定主人、电脑与私聊身份，任何后续 `POST /im/v1/personal-agent` 不得重建或篡改已激活 PA（同一 `request_key` 提交冲突 `collaboration_scope` 仍返回 `409`）。
     3. 仅当既无在途配置操作也无已创建 `agent_profiles` 时，才回滚确定性失败的新建 `pending` 绑定，或允许孤儿 `pending` 绑定刷新当前 `node_epoch` / 新请求参数继续完成创建。

## 本次审查安排

| 审查编组 | 必须回答的问题 | 能力 | 验证方法与已有证据 |
|---|---|---|---|
| R1（Codex GPT 独立审查） | 1. `POST /im/v1/personal-agent` 是否在确定性失败时干净回滚且不残留 `pa_node_residencies` / `pa_policies` / `personal_agent_bindings`，同时在 `config_apply_pending` 在途未决时严格保留原绑定供 `ops.recover` 恢复？<br>2. 孤儿 `pending` 绑定（同 `request_key` 重试、节点 `node_epoch` 推进、新 `request_key` 重新创建）与在途未确认时异 `request_key` 冲突处理是否正确且无状态分裂？<br>3. Web 聊天侧栏、欢迎页、创建/恢复弹窗与 Agents 页在 `pending` 与失败态下是否自明、协调，不再出现假会话或“聊天不可访问”，并在恢复成功后顺畅进入私聊？<br>4. `docs/specs/im/personal-agent.md` 契约是否与实现及测试对齐？ | `change-code-review` + `frontend-experience-review` + `product-journey-review` | 1. `apps/im-server/tests/personal-agent.test.ts` 与前端 `vitest` 红绿回归测试；<br>2. 隔离 E2E 栈真实浏览器操作验证与截图证据（未确认/孤儿 `pending` 态聊天页与 Agents 页表现 → 恢复创建成功进入私聊）；<br>3. 独立审查者检查完整 diff、测试与隔离栈实证 |

## 修复

## 验证

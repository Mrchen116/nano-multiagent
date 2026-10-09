# Web → 原生首版功能对照

基线：`e6a5c0ea5`。本表是实现和独立验收的逐项清单，不是已实现状态；所有行初始为待验。长青业务语义以 `docs/specs/im/` 为准。页面来源均相对 `src/IM/frontend/src/`。

| ID | 现有 Web 来源 / 功能 | 原生页面 / IM 接口（省略 /im/v1） | 场景 |
|---|---|---|---|
| C01 | `features/auth/{login,register,membership}-page.tsx` 字段反馈、语言、资格、退出 | Auth/Membership；`auth/login,register,refresh,logout,me` | S3-4 |
| C02 | `features/chat/chat-workspace-page.tsx` 搜索/全部、真人、Agent、群聊、Network 分类/未读/置顶/静音 | ChatList；`conversations`, `sync`, `conversations/{id}/read` | S5-6 |
| C03 | `features/chat/contacts-api.ts` 联系人/成员选择、新私聊/群 | Contacts/NewChat；`contacts`, `conversations` POST | S5 |
| C04 | `chat-api.ts` 改名/成员增删/解散 | ChatInfo；`conversations/{id}`, `participants`, DELETE | S5-6 |
| C05 | `components/message-pane.tsx` 正文/GFM/提及/命令/草稿/粘贴 | Conversation/Composer；`messages`, `commands`, user WS | S2/S7-8 |
| C06 | 消息历史、配置边界、滚动定位 | Native timeline typed union；`messages?before_message_id=` | S7-8 |
| C07 | `attachments/attachment-link.tsx`, `components/message-image.tsx` | Media/preview/share；`uploads` raw body + 受保护资源 URL | S10-11 |
| C08 | `chat-api.ts` fork 与 conversation distill | Message menu/Distill；`conversations/{id}/fork`, `conversations/distill-prompt` | S9 |
| C09 | `tool-timeline` / `message-pane` 工具、思考、background return、reply process、指标 | Timeline detail；消息 DTO 与 WS canonical events | S12 |
| C10 | 聊天权限卡 pending/submitted/resolved | PermissionCard；`conversations/{id}/permissions/{request_id}`（body含message_id、decision、reason） | S13 |
| C11 | `features/tasks/task-graphs-page.tsx` 搜索/分页/深链/图/节点 | Tasks/TaskGraph/Node；`task-graphs`, `task-graphs/{id}?view=all` | S14 |
| C12 | `group-task-panel.tsx` 群活动与节点回聊 | GroupTasks/Chat draft；`conversations/{id}/task-activity` | S14 |
| C13 | `agents-list-page.tsx`, `agent-profile-page.tsx` 公司联系人、公开简介/模式/owner/设备/私聊 | AgentList/Profile；`contacts?kind=agent`、新 direct conversation | S15/S18 |
| C14 | `agent-work-panel.tsx` 主/子执行、统计、过程分页 | Work/WorkSession/Turn；`agents/{id}/work[/sessions/{sid}/turns[/{tid}/items]]` | S12-15 |
| C15 | Work 权限处理 | WorkPermission；`agents/{id}/work/permissions/{request_id}` | S13 |
| C16 | `agent-create-page.tsx` 节点/工作模式/路径/能力/草稿保护 | AgentCreate；`nodes/{id}/capabilities`, `nodes/{id}/agents` | S16 |
| C17 | `agent-detail-page.tsx` 名称/描述/主模型/推理/备用/群策略 | AgentConfig；`agents/{id}/config?source=mirror`, PATCH with profile_version | S17-18 |
| C18 | features/Custom Instructions/工具/Skill来源分组/默认发现 vs 显式列表 | AgentCapabilities；`agents/{id}/capabilities`, config PATCH | S17 |
| C19 | 已有/新建提示词预览，当前草稿与能力选择 | PromptPreview；`agents/{id}/prompt-preview`, `nodes/{id}/prompt-preview` | S17 |
| C20 | 心跳开关/频率/活跃时段/HEARTBEAT.md | Heartbeat；config PATCH、`agents/{id}/heartbeat-md` | S19 |
| C21 | cron 开关、列表、详情、删除（Web 不提供独立创建/编辑任务表单） | Cron；config PATCH、`agents/{id}/cron/jobs[/{job_id}]` GET/DELETE | S19 |
| C22 | Skills list/agent/health 视图、来源、统计、趋势、调用引用 | SkillsUsage；`agents/{id}/skills/usage` | S19 |
| C23 | `agent-channels-panel.tsx` provider选择、飞书准备、添加/keep-replace | Channels/ChannelEditor；`agents/{id}/channels` GET/POST/PATCH | S20 |
| C24 | 通道 enable/disable/reconnect、诊断、last-known、删除回执/retry | ChannelState/Removal；`channels/{cid}/actions/reconnect`、DELETE CAS、`channel-removals/{cid}/actions/retry` | S21 |
| C25 | `features/settings/nodes/nodes-page.tsx` 别名/relay/report/状态/创建 | Nodes/Node；`nodes`, `nodes/{id}/config` PATCH；链接 C16 | S23 |
| C26 | `features/chat/bind-confirm-page.tsx` 检查/接受/拒绝/等待本机确认 | BindingImport/Confirm；`device-binding/inspect,accept,decline` POST browser_token | S22 |
| C27 | `features/settings/account/account-page.tsx` profile、默认入口设备、语言 | Account；`me` GET/PATCH（不是 `auth/me` profile 写入） | S24 |
| C28 | `company-members-page.tsx` 分页/approve/suspend/最后admin保护 | Company；`company/members[/{id}/{approve|suspend}]` | S25 |
| C29 | `policies-page.tsx` 全部策略 + readonly角色 | Policies；`policies` GET/PATCH | S26 |
| C30 | `policies-page.tsx` 真实服务/owner容量状态 | Capacity；`attachments/capacity` | S26 |
| C31 | `me-page.tsx`, `app-shell.tsx` 导航/语言/未读/退出 | Native tab stacks/MyAccount | S1/S4/S24 |
| C32 | Agent sessions section 当前是占位说明 | 保留说明，不增加虚构 endpoint 或功能 | S1/S19 |
| C33 | 原生增量，前台提示与后台能力说明 | My/提醒与安装 + 内部 banner；不申请 APNs | S27-28 |
| C34 | 免费安装维护 | Xcode/IPA + AltStore/AltServer help | S29-30 |

## 对齐规则

- 本表列所有已发现的 Web 活跃路由及 Agent 子 section；实施对基线 router、实际按钮和 current specs 二次核对。漏项属于本 unit 缺陷，不能据表格未列而删除。
- 已有 Sessions 占位不是可用功能；不将占位算成完成真正的 Work。
- Web 的外部网站跳转可保留系统浏览器；内部 Nano 页面须原生。
- C30 路径已按 `policies-page.tsx:31` 核对为 `/im/v1/attachments/capacity`，仅管理员加载。

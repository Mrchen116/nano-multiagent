# bugfix-618：双方 owner 只读观察 Agent 私聊 — 技术方案

> 对齐 [incident.md](incident.md)。基线 main@dfdbf6bf3；仅修改 IM 授权、交付和客户端投影，不改 DSH。

## Changelog

## 现状分析

### 涉及范围
- `apps/im-server/src/conversation-access.ts`：当前只有成员和公开群读取；扩展为统一的观察者资格 owner。
- `messaging.ts`：列表、DTO、事件接收者；`gateway.ts`：实时广播与断线重放；媒体和写入口已经复用聊天授权。
- Web `chat-types.ts`、`message-pane.tsx` 与上下文操作入口；原生 iOS `ConversationView.swift`、`ChatListView.swift` 与 `ChatModels.swift` Conversation DTO。

### 既有约束
观察不创建成员、不写消息、不激活 Agent，不改变公司/个人空间；原有成员写资格保持。旧 `conversations.owner_id` 不承担双方观察权。只调整当前包，不引入运行时依赖或第二套 ACL 存储。

### 可复用能力
复用 `qualifiedUser`、`canActorAccess`、`conversationAccess`、`can_write/is_member/can_join`，以及历史、附件、客户端刷新和 user-stream。iOS 已经按 can_write 隐藏 composer；Web 当前仅显示只读提示，composer 尚需真正隐藏。事件仍使用原持久 ID 和全局恢复游标。

### 相关历史
refactor-581 退役 Python；当前 auth-tenancy 的私聊仅成员可读是本次明确修订。feat-610 的个人空间、原聊天附件权限和 Work 独立可见性继续保持；不对 Work 做复制或转发。

## 架构总览

`会话真实参与者 + Agent profile 的当前 owner/space → conversationAccess → REST/媒体/列表/实时/恢复 → can_write=false、is_observer=true → 客户端只读`

## 关键决策

1. **在既有聊天授权模块派生观察资格，不保存观察者成员或新 ACL 表。** 只有 direct 且恰好两个参与者、双方身份均能解析为本空间 Agent profile 时才属于观察对象；真人的有效 owner 身份匹配任一方，并有该会话空间资格即可只读。无管理员旁观豁免。离线或 Agent 的历史保留状态不删除已知 owner 的历史读取资格；账号/空间资格和实际 owner 关系每次读取重新检查。身份无法核实则不推断。
2. **区分读取资格和写入资格。** `conversationAccess` 增加 `is_observer`，保持 is_member=false/can_write=false/can_join=false。所有消息/上传/修改/成员/删除等既有 write 门禁继续只接受成员。读图/附件跟随同一读取资格；不建立全局文件访问权。
3. **列表和实时复用同一判定。** joined 列表增加可观察 direct，按会话 ID 去重；每次投影时复核资格。模块提供 `conversationReaderIds(db,id)` 给持久消息事件选择成员加有效 owner，gateway 的 broadcast 和 replay 最终再次检查 conversationAccess。既有非敏感成员移除通知仍可告知原接收者。replay 在现有窗口内按事件 ID 顺序筛选可读事件，保持全局 top cursor/超窗 resync，不给观察者独立事件流。
4. **Web Network 纳入 agent-agent direct；聊天双方身份与只读状态同时可辨认。** 观察者列表标题展示双方名字；消息维持原作者。通过 can_write 隐藏 composer，使用 is_observer 展示“Agent 协作 · 只读，你可以查看双方往来，不能发送消息”；不显示加入按钮或会话写操作。普通公开群与成员聊天沿用既有流程。iOS 复用现有只读底栏，替换错误的“公开群”提示；观察条目隐藏长按和侧滑的置顶/静音写操作，详情只展示名称和真实参与者，不提供改名等写表单；不新增导航。Network 是分类，不改变 direct 业务形态，群设置/任务入口仍以真实 type=group 为条件。
5. **单 M1 垂直交付。** 权限、事件与客户端必须一起生效，拆分无独立交付收益。已有会话从现有成员/profile 派生权限，无数据库迁移、不改历史或重建会话。

## 接口与数据流

- `conversationAccess(db,id,userId)` 保持原接口，返回值新增 `is_observer:boolean`。读取者查询由该模块封装，调用方不重新推导 owner。
- Conversation DTO 增加同名字段；Web/iOS 使用可选字段兼容缺省 false。授权仍由服务端决定，客户端字段不构成信任来源。
- REST list/sync 包含观察会话；详情/消息/受保护媒体继续由统一 access 决定。会话 DTO、参与者与真实消息源不因观察改变。
- Agent 新建 direct 后首条持久事件会通知双方 owner；客户端沿现有会话失效/补读机制发现新会话。刷新、分页和 user-stream 重放使用相同资格。
- owner 改变、账号/空间资格失效后，不再给原观察者后续受保护事件，REST/重连也拒绝。Web 对正在查看的非成员沿用每 3 秒消息读取；为读取错误保留 HTTP status，403/404 不重试并触发现有 reconcileMembership：重新取列表，清除当前消息/详情缓存、composer 草稿、流 reducer 与已挂载媒体，返回列表并提示聊天已不可访问。取消在途历史请求，并通过既有 conversationId/请求身份检查丢弃迟到历史响应。身份/空间切换保留原清理机制；iOS 已对非成员每 3 秒 inspectConversation 并清理正文，补明确失效提示并禁用所有写入口。此为可见前台的下一次权限复查后收敛，不新增撤权 push 或持久订阅授权。
- 观察者写请求按现有拒绝语义失败，不触发 relay task；正式成员、Agent 自己和公开群的行为不变。

## 前端原型

[prototype.html](prototype.html) 是现有聊天背景下的局部增量，示例仅有合成协作内容。Web 使用现有导航、Network filter、消息布局及只读 notice；原生保留导航栏与底部 material 只读条。原型外层的模式切换、追加消息和失去访问按钮只是演示控件。

### 现有 UX grounding
当前生产源码入口为 `/chat/:id`，现有三列导航、会话过滤和消息气泡保持；源码 `message-pane.tsx` 的 tasks-notice 已表达 can_write=false，原生 safeAreaInset 已隐藏 composer。设计隔离 fixture 提供真实当前页面，观察记录见 `evidence/design-visual.md`；不能把合成原型当产品验收。

### 原型对齐契约
| 区域/状态 | 对齐 | 实际入口 | 走查 | 退出标准 |
|---|---|---|---|---|
| Network 私聊条目含双方身份 | must-match | Web 会话列表 | 桌面/窄屏 | R1 |
| 双方消息作者和只读提示，无输入/发送/加入 | must-match | Web 聊天 | 1280 与 390 宽度 | R1/R2 |
| 新消息追加、长内容滚动 | must-match | Web 观察聊天 | 实时/刷新 | R3 |
| 资格失效显示不可访问，不继续交付 | must-match | 聊天与重连 | 失效状态 | R3 |
| 原生只读底栏，无 composer/加入按钮；观察条目无长按/侧滑写动作 | must-match | iOS ConversationView | 模拟器 | R2 |

原生列表沿用现有行、左右侧滑和 contextMenu 的容器；观察行保留点击进入详情，移除写菜单和 swipeActions，不增加占位禁用按钮。失效 Web 返回列表时以现有错误提示条反馈；原型中留在聊天容器的失效文案仅表达内容清空和不可访问，路由可适配现有清理导航。

具体字号、系统原生控件和容器尺寸沿用各端现有样式，原型不重建无关的配置/任务页面。

## 契约层增量

- [auth-tenancy](specs/im/auth-tenancy.md)：owner 观察者只读例外、资格失效。
- [conversations-messages](specs/im/conversations-messages.md)：列表/历史/实时、已有记录、不成为成员。
- [web-chat-ux](specs/im/web-chat-ux.md)：Network 与只读 UI。
- [ios-client](specs/im/ios-client.md)：只读状态、无发送与列表写入口。
- [agent-work](specs/im/agent-work.md)：只修订来源聊天读取为统一会话资格，Work 自身范围不变。
- conversations-messages 同步附件读取与私聊菜单/改名的成员写入前提，保留未变 Scenario。

## 风险与回退

主要风险是把管理归属误用为写权、列表/实时/媒体使用不同规则或旧事件重放泄漏。统一判定与真实 HTTP/WS 矩阵保护这些路径，不靠前端隐藏替代后端拒绝。撤回整个 unit 即恢复原可见边界，无数据迁移回滚；已存在会话与消息不修改。

## Runbook for Reviewer

本次业务边界是独立 IM，真实聊天节点协议可使用隔离测试节点驱动，不要求真实模型决定发言；这直接覆盖改动的 IM HTTP/WS 用户路径，不能声称验证 DSH 模型自主协作。

从 unit worktree 根目录运行（端口 58054/58055/53186 专属本 unit；若占用先核对，不能终止其他服务）：

```bash
node --import tsx docs/changes/bugfix-618-agent-owner-observation/evidence/fixture.mts
# 另一终端，cwd=src/IM/frontend：
VITE_IM_PROXY_TARGET=http://127.0.0.1:58054 npm exec vite -- --host 127.0.0.1 --port 53186 --strictPort
# 准备三种 Agent 私聊，重复调用幂等：
curl -f http://127.0.0.1:58055/seed
# 实时追加 / 撤销 alice 的跨 owner 观察资格 / 恢复：
curl -f http://127.0.0.1:58055/send
curl -f http://127.0.0.1:58055/revoke
curl -f http://127.0.0.1:58055/restore
```

Web：`http://127.0.0.1:53186`；原生 Debug origin：`http://127.0.0.1:58054`。合成账号 `alice` / `bob` / `charlie`，密码均 `old-password`；alice 与 bob 是跨 owner 观察双方，charlie 是无关管理员。fixture 的日志给出真人成员群 ID；实际私聊从 Network 发现。健康检查：`curl -f http://127.0.0.1:58054/health` 及浏览器真实登录、会话列表、节点注册成功日志；启动前核对 `git rev-parse HEAD`，进程 cwd 必须是受审 worktree。停止 fixture 用该进程 PID 的 `kill -TERM <pid>`（finally 关闭 socket/server 并删除临时数据库）；Vite 用启动会话 Ctrl-C。

原生资源已落实：`/Applications/Xcode.app`，iOS 26.4 iPhone 17 Pro 模拟器 `1CE31893-672F-495A-B2B5-3ACF39A7A257` 可用。`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`；构建 `NANO_IOS_BUILD_ROOT=/tmp/nano618-ios ./src/IM/ios/scripts/build.sh build`，测试加 `NANO_IOS_SIMULATOR_ID=1CE31893-672F-495A-B2B5-3ACF39A7A257` 执行 `build.sh test`。模拟器独立 UI 走查使用已构建 Debug app、上述 origin 与合成账号；不使用生产账号或真机。

**Review 驱动方式**：真驱动 Web IM 的 Network→双方协作→只读→收到新消息→刷新/重连→普通成员聊天；后端 HTTP/WS 验证双方 owner、无关账号、个人空间、旧历史、媒体、拒发及资格失效。原生模拟器核只读条和 composer，原生测试验证字段/发送 guard。仓库外前置仅本地 Node/pnpm、浏览器与 Xcode 模拟器，测试内容全为合成数据，无生产/外部平台依赖。实际接管参数与启停命令写入验收 evidence，所有自启进程由本 unit 清理。

## Milestones

| ID | 依赖 | 并行组 | 范围 | Exit Criteria |
|---|---|---|---|---|
| M1-owner-observation | 无 | 单线 | IM access/list/event/replay、Web DTO/分类/只读、iOS DTO/提示、测试与 delta | **[reviewer R1]** 双 owner/同 owner/私人空间在 Web Network 发现已有和新协作，辨认双方身份；**[reviewer R2]** Web 与 iOS 只读无发送/加入及原生列表长按/侧滑写动作，参与者不变，普通成员聊天可发送；**[reviewer R3]** 实时、历史、重连与失效一致；同账号同空间在线查看时只改变 owner，下一次前台复查清除正文/媒体和列表旧项，长消息可滚；**[worker W1]** 先红后绿的最低层 HTTP/WS 权限矩阵覆盖 list/read/media/writes/owner变化与账号失效；**[worker W2]** 扩展现有 frontend/iOS 测试，提供原型/实际页面对照；**[worker W3]** 适用独立静态与产品门禁、契约归并及 CI 通过。 |

## 测试处置

现有 `tenancy.test.ts`/IM e2e 通信测试承担成员与空间边界，扩展其观察者矩阵，避免重复建 unit 命名测试；Web sidebar/message-pane 既有测试加入 Network direct 和隐藏 composer；iOS ChatStateTests 加只读观察字段与发送 guard；Web 集成覆盖 403/404 后清理以及迟到响应不恢复正文；原生实际走查长按和侧滑不露写动作。DSH 与 Node 不改，不增加运行时兼容测试。

# Code Review: bugfix-618-agent-owner-observation

- review_mode: full
- executed_base: `9b110168359b9c9ae5937d07a77b697e03a61d65`
- validated_at: `03d1d5a65550061a10c944552f0078dac9085408`
- 范围：完整 `9b1101683..03d1d5a65`（24 files）；独立只读审查，不修改产品、测试或设计。
- 结论：2 个 CONFIRMED findings，修复后复审。服务端 owner 观察与成员写入分离本身未发现权限绕过。

```json
[
  {
    "file": "src/IM/frontend/src/features/chat/components/message-pane.tsx",
    "line": 1779,
    "summary": "[P2] 观察者仍能操作协作私聊中的待审批卡",
    "failure_scenario": "两个同空间 Agent 中有 single_thread Agent，接收对端 direct 输入后产生 permission_request。新观察资格使 owner 能读取该消息，但 MessageBubble 未接收 can_write，PermissionCard 的 disabled 只检查请求 Agent 是否仍是参与者，观察者仍会看到可点击的 Allow/Deny 和说明输入。iOS ChatMessageView.swift:59-60、159-168 同样未传读取权限，提供审批及提交表单。服务端 conversation-actions.ts:396 的 write 门禁返回404，故这是可达的只读界面缺口而非服务端越权。应在两端把观察会话的审批内容保留为只读，隐藏或禁用决定与提交入口，并保护成员正常审批。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/IM/frontend/src/features/chat/chat-public-visitor.test.tsx",
    "line": 46,
    "summary": "[P2] 为迟到历史用例提供真实滚动条件，使撤权回归能执行",
    "failure_scenario": "该用例在 jsdom 中直接 fireEvent.scroll，但没有定义 scrollHeight/clientHeight；message-pane.tsx:837-838 计算 scrollable<=0 后返回，不发起历史请求。因此第47行 resolveOlder 永远未定义，新增测试稳定失败，后续撤权、缓存清理及迟到历史断言完全没有运行。独立两文件运行17通过1失败，单文件再跑1通过1失败。为容器设置有意义的滚动尺寸及顶部位置后再触发滚动，重跑新增保护；这不是产品历史分页缺陷。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## 核验依据

1. 独立后端窄测：`pnpm exec vitest run apps/im-server/tests/tenancy.test.ts apps/im-server/tests/messaging.test.ts apps/im-server/tests/e2e/server.test.ts --maxWorkers=1`，3 files / 13 tests passed（2026-10-19 21:58，26.08s）。覆盖双方真实 owner、同 owner、个人空间、旧 owner 无效、媒体、拒写、live/replay、owner变化、账号/空间失效及普通成员通信。
2. 独立 Web：`npm exec vitest -- run src/features/chat/chat-public-visitor.test.tsx src/features/chat/components/conversation-sidebar.test.tsx --maxWorkers=1`，17 passed / 1 failed；再以相同参数只运行 `chat-public-visitor.test.tsx`，1 passed / 1 failed，均停在47行。二次输出定位 `/tmp/nano618-independent-web.log`；本报告保存失败机制和结果，临时日志不提交。
3. 对审批真实可达条件独立复现：隔离临时 SQLite、正式 `createServer`，两个有效公司 single_thread Agent，`resolveTarget` 创建恰两 Agent direct，调用 gateway 的正式 streaming 处理 `turn_start` 与 `permission_request`。owner HTTP 详情得到 `{is_observer:true,can_write:false}`，历史得到 `status=pending`、`agent_id=right`、options `allow_once/deny`；HTTP POST 决定返回404。临时脚本在退出时关闭服务和删除DB，收尾移除脚本。未调用模型或生产。
4. 产品可达链：`packages/personal-assistant/src/attention.ts:7` 允许 direct 输入；`single-thread.ts:55-72` 为该协作 direct 建执行绑定；`:329-347` 把审批发到本次 delivery.messageId。服务端 `gateway.ts:832-846` 接受 single_thread 的卡，不限制为 user-agent direct。Web `message-pane.tsx:1773-1782` 与 `permission-card.tsx:190-210`、原生 `ChatMessageView.swift:159-168` 提供写控件，没有 can_write 门禁。

## 其他已核对边界

- `conversation-access.ts:16-40`：direct、恰两参与者、双方本空间 profile、当前真人 owner 与账号/空间资格；不看旧 conversation.owner_id，不把 stale/offline 等同 owner 失效。
- `messaging.ts:167-176,342-345,583`：列表去重与最终读取判定、消息持久事件收件人；写门禁仍要求 member。
- `gateway.ts:211,240-256`：live 最后一跳与 replay 再检当前读取资格，保持全局 top cursor 和原恢复窗口。
- `media.ts:47-68`：受保护媒体复用同一读取 access，上传仍要求成员写入。
- Web 的 Network 是分类；group tasks/config/mention 以真实 `type=group` 决定。iOS 列表写菜单、详情表单、composer 和 store.send guard 已覆盖普通观察路径；待审批内容例外见 finding 1。
- 全量门禁、最终 iOS 与独立产品验收由主 Agent 汇总；本报告不把未完成检查称通过。

## Author Resolutions · Round 1

- 审批控件 finding accepted：Web 将会话只读资格透传到 MessageBubble/PermissionCard，保留问题、工具输入和审批状态，隐藏理由框与决定按钮；原生同样透传到 ChatPermissionCard 并隐藏决定/提交入口。成员默认分支不变，服务端拒写门禁保持。非成员页面回归直接包含 pending card，原有 PermissionCard 成员测试保留。
- 迟到历史 finding accepted：明确设置可滚动高度、视口和顶部位置，再触发真实页面的分页请求。修后35项相关Web测试通过，已执行撤权及迟到返回不恢复内容断言。
- 产品 minor accepted：原生 inspect 403/404 后改用统一可理解的失效文案，避免主区暴露内部 conversation_id 字段；原生30测试再次通过。

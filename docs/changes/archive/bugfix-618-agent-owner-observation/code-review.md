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

## Round 2 · Patch review + finding closure · 2026-10-19

- review_mode: patch + closure
- executed_base: `d9be419c7`
- validated_at: `1823aef433264a8732ae56461a73deea60ada701`
- pre_fix_head / finding_origin_head: `03d1d5a65550061a10c944552f0078dac9085408`
- fix_delta_range: `03d1d5a65..3786dd735`
- 补查范围：`3786dd735..1823aef43` 的main合并影响；本轮不重审完整unit，不签M1完成。

### Findings

```json
[]
```

### Focus findings closure

| R1 finding | 结果 | 直接证据 |
|---|---|---|
| 观察者仍能操作待审批卡 | **closed** | Web `message-pane.tsx:1047,1782` 将 `can_write===false` 传给 MessageBubble→PermissionCard；`permission-card.tsx:100,182-223` 保留问题/工具输入，隐藏理由框与决定，并阻止handler提交。iOS `ConversationView.swift:54`→`ChatMessageView.swift:61,161,175`同样传递readOnly、隐藏决定并阻止提交。两端默认readOnly=false，成员分支保留。 |
| jsdom滚动前提不足，撤权/迟到断言不执行 | **closed** | `chat-public-visitor.test.tsx:49-60` 明确scrollHeight=1200/clientHeight=300/scrollTop=0；先等历史请求，再撤权、清空正文/cache，最后解析迟到历史并确认未恢复。冻结HEAD独立运行包含此用例与成员审批的2文件15测试通过。 |

### 独立与复用验证

- **独立重跑**：cwd `src/IM/frontend`，`npm exec vitest -- run src/features/chat/chat-public-visitor.test.tsx src/features/chat/components/permission-card.test.tsx --maxWorkers=1`，**2 files / 15 tests passed**，2026-10-19 22:29:50，18.63s。日志 `/tmp/nano618-independent-r2-web.log`。当前场景含实际Agent sender、pending卡与真实参与Agent，断言问题及工具输入可见，无textbox/Allow/Deny，同时执行撤权/迟到历史；成员PermissionCard现有发送、失败/决定行为通过。
- **复用且已检查**：`/tmp/nano618-web-fix.log` 4 files / 35 tests passed（22:10:38）；`/tmp/nano618-ios-fix.log` XCTest 30 tests / 0 failures、Swift Testing另17 tests通过，`TEST SUCCEEDED`（22:11:39）；`/tmp/nano618-ios-archive.log` 同worktree、generic/platform=iOS、Release、`CODE_SIGNING_ALLOWED=NO`，`ARCHIVE SUCCEEDED`。日志命令和结果均已读取，产品源树与本轮冻结版一致；不是原生手势/真实产品验收或已签名真机安装证据。
- iOS `ChatStore.swift:166-171` 的403/404只替换用户可见失效文案，清理及其他错误分支保持；未发现本轮新的产品缺陷。

### main合并与保留影响判断

实际 `3786dd735..1823aef43` 仅19个issue intake相关文件：issue模板/labels、专用issue-triage workflow、sync-issue-labels脚本和文档；不是19个全为纯文档。已检查路径及专用workflow/脚本，均不进入IM运行时、依赖锁文件或现有产品测试门禁。合并没有改IM产品/测试路径，本轮修复之外也没有backend/PA/DSH改动，因此R1服务端owner读取/成员写入、媒体、live/replay结论仍适用，无需full重审。相同delta链接修正不改变产品契约。fixture扩充仅合成长历史/媒体/审批/分类资源，origin修正为已有Vite同源53186，属于验收接线，无新增产品能力。

结论：本轮两项finding均关闭，无新增存活finding；全量、产品交互、current契约归并及CI的C1仍pending，见verification Round 2。未改源码/测试/设计，未提交。

## Final Retention · 2026-10-19

- validated_at: `3a477acd6d65d8f1aadab98ac60671334e311b76`
- executed_base: `d9be419c7791c5cccf06b629ce72c4af8cd023de`
- `1823aef43..3a477acd6`仅unit报告/截图与用户验收范围说明，独立核对无产品源码、测试或依赖变更。R2 patch/closure结论保留：**findings=[]，两项focus closed**，不需要重复full code review。
- 本轮C1 targeted verification已通过：独立产品R4按用户确认的Web+IM HTTP/WS范围pass，完整失败项均有原时限后续通过；本审查者额外在冻结HEAD执行最终 `npm run build`，TypeScript与Vite通过（`/tmp/nano618-independent-final-web-build.log`）。详情见verification Round 3。
- 原生未完成真实交互按用户要求移出放行前置，仍保持未验记录；归并、归档、PR/CI是caller后续交付步骤，不在本报告冒称完成。未新增finding，未提交。

## Round 3 · Latest Main Integration Patch Review · 2026-10-19

- review_mode: patch + retained-finding closure
- executed_base / effective_base: `65de8cd2085b461b55b23eb88fc2eceb19c7bc39`
- validated_at: `de0141f84831fbae9f2b68946204b4f032bb554e`
- pre_sync_head: `35e815e61`
- patch_range: `35e815e61..de0141f84`；重点检查main新交互接口/共享消息组件与618观察权限的交集、merge commit `50b27ffd5`冲突解决、兼容修复 `50b27ffd5..de0141f84`。
- 不把上游feat-617整体重新作为618需求审查；对最新main的本unit差异与实际重叠调用链交叉核对。没有改产品、测试、设计或提交。

### Findings

```json
[]
```

### 冲突与新增接口核查

| 影响面 | 核查与结论 |
|---|---|
| 事件reader与publishMessages返回 | merge combined diff保留`conversationReaderIds` import及`messaging.ts:345,626`读取者广播，同时保留main `publishMessages:622-629` delivered聚合返回及`sendMessage:523-525`的relay判断。没有退回成员only广播，也未丢main投递结果。 |
| owner交互state读取/草稿/提交 | 新`interactions.ts:76-81`的GET复用当前conversation read，并限定`user_id=p.id`，不返回他人草稿；PUT `:87`及`messaging.ts:474`的所有消息/interaction提交先走成员write，发生在insert草稿/消息/relay之前。新增tenancy断言双方owner可读空状态，PUT/submit404、outsider GET404，草稿0、消息1、relay0。 |
| 只读卡片UI | `message-pane.tsx:1089`保留main已提供的can_write映射到interactiveReadOnly；`interactive-card.tsx:170`补fieldset readOnly禁用，加上已有lockedRef对save/submit/state publish的阻断。不仅靠隐藏composer，也不靠服务端404来呈现可编辑假象。 |
| readOnly与业务冲突语义分离 | fieldset用`readOnly || busy || pending`，没有误用`locked`（后者还包含submissionConflict）。普通成员alreadySubmitted/stale冲突仍保留字段与本机值可编辑，禁止原请求重放；成员自然输入未知结果仍保留冻结text/state/key重试。这是main已有契约，修复没有抹去。 |
| composer合并 | `message-pane.tsx:1104-1106`仍以can_write控制整个form，并保留pendingInteraction提示和附件禁用；`:1183`的输入禁用与原pending重试逻辑保留。非观察者的main继续探索/提交路径未被替换成旧版onSend。 |
| 当前spec合并 | conversations-messages中618观察Requirement与617交互三组Requirement均保留；web-chat-ux中618 Network/失效与617交互/布局/视觉均保留。实际计数auth15 / messages30 / web29 / iOS6，与spec.md相符；标题对齐bugfix-618，不丢main新增业务契约。 |
| 原生与旧findings | `git diff 35e815e61..HEAD -- src/IM/ios`为空，R2两项finding仍closed；原生静态/47测试/unsigned archive证据保留且不声称新原生人工验收。 |

### 验证

- **独立Web**：冻结HEAD执行 `npm exec vitest -- run src/features/chat/interactive/interactive-flow.test.tsx src/features/chat/interactive/interactive-card.test.tsx --maxWorkers=1`，2 files / **18 tests passed**，23:00:12，9.75s，`/tmp/nano618-independent-sync-web.log`。直接覆盖owner卡字段/提交disabled、无composer/无save/send，以及成员冲突保留本机草稿、未知结果原快照重试、原生交互事件和普通自然追问。
- **独立HTTP/持久化边界**：`pnpm exec vitest run apps/im-server/tests/tenancy.test.ts -t 'both real Agent owners' --maxWorkers=1`，**1 passed / 7 skipped by selection**，23:00:12，1.38s，`/tmp/nano618-independent-sync-tenancy.log`。测试中真实Fastify请求与SQLite断言通过；没有将选择器跳过7项冒称8项全跑。
- **复用且已读**：RED `/tmp/nano618-sync-card-red.log`在字段not disabled处失败；最终GREEN `/tmp/nano618-sync-web-final.log`6文件52项、`/tmp/nano618-sync-backend.log`5文件38项通过。`/tmp/nano618-sync-web-build.log`最终TS/Vite构建通过，`/tmp/nano618-sync-typecheck.log`全部包Done，`/tmp/nano618-sync-build.log`完整build成功。构建日志的Node installer候选标记merge commit50b27ffd5，与最终兼容修复产品仅前端fieldset/测试增量相符；不把该候选当已发布包。

结论：patch无存活finding，旧finding均保持closed。已覆盖新增共享权限/提交边界，没有需升级full审查的未核实候选。main后的真实Web卡片与布局定向验收由独立产品reviewer追加，旧产品截图不替代新组件/布局补验。远端CI/PR合并/部署不属于本报告已完成声明。

### Evidence policy retention after main sync

main `docs/development/evidence.md:50-54`要求截图/录屏留在gitignored或稳定仓外目录。caller正在将24张旧视觉证据移出Git索引，保留本地原文件及稳定副本 `/Users/czj/.codex/artifacts/bugfix-618/visual-evidence/`，并在`evidence/local-artifacts.md`及旧报告图链记录定位。本审查者独立枚举冻结HEAD的24张PNG并比较本地原文件/稳定副本：missing=0，SHA-256 mismatch=0。此为证据保存政策对齐，不是删掉已验事实或变成未验；证据内容、版本、场景和既有范围限制均保留。移出Git后的链接完整性由caller最终docs-check确认，不改变产品patch findings=[]。

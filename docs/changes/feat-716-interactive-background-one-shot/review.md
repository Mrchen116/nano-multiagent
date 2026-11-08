# feat-716: Review

## 范围与版本

- 当前有效需求：`spec.md` 的多卡一次性规则；用户确认 A+B 一起携带并消费、下一条无新背景、仅重改 A 后只携带 A。旧单卡独占证据不代表本增量已验收。
- Gate 2：`design-review.md` R5，独立 Approved / 0 CRITICAL / 0 WARNING；设计审查不替代实施验收。
- 独立实现审查者：`67dd0842-5c6b-4237-8135-daee86b28cf3`，未参与受审实现或 R5 设计审查，加载 `change-code-review` 和 `agent-context-review`。
- 本轮受审范围：完整 `eeaea47921806936da20e78c9ed96167716f5037..5adda98f5527c951ffb8df9ba28c68b76ca998fc`，68 文件，包含旧单卡实施及多卡增量；非仅最后一个提交。`executed_base` / `validated_at` 分别为上述两值。
- 配置差异：当前派工工具未提供固定模型/effort参数或实际值。依据用户仅限本轮 #473、714、716、720 的例外，使用当前可用配置做独立审查；不冒称指定配置，也不豁免作者与审查者分离。
- `effective_base` / `effective_through`：尚未完成最终 sync 与实施验收，不给出最终有效性结论。

## 首轮审查结果（5adda98f5）

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 全部实现正确性、需求/设计覆盖、最终 delta | change-code-review；上述独立 reviewer；full | **REQUEST CHANGES** | 三项 P2 / CONFIRMED，见下；四份 delta 与实现对照，结论为 implementation-mismatch，不建议缩改契约迁就遗漏 |
| 多卡选择、逐卡有效性、64 KiB 总预算、无副作用失败、同键冻结、显式提交独立、来源与逐 Agent 过滤 | 同一独立 full code review | 静态检查未发现其他阻塞缺陷 | `pending()`、消息事务、attempt、relay 与客户端实际代码；复用 server 5 files / 75 tests、Web 3 files / 36 tests 的可信窄测试与类型检查；本轮未重复全量 |
| 模型可见信息的来源、选择、装配、失效与非授权边界 | agent-context-review；同一独立 reviewer；实施静态链核对 | **pending / inconclusive**（动态目标） | 静态链已核：中心派生→卡作者 relay→`withInteractionContext`→single-thread 或 Global Inbox 工具结果；数据非指令/非提交/非授权说明保留。尚未观察当前多卡真实双端、实际 `read_messages` 与后续模型步，不能整体 pass |

审查者仅进行只读代码/文档检查、`git diff --check`（0），以及一项实际模块 + fake IndexedDB 的纯内存复现；未改文件、启动服务/GUI/LLM，未读取旧 62814 来冒充本增量结果。

## Findings 与关闭

### F716-CR1 — 移动 Web 返回列表漏掉离开清除

- **P2 / CONFIRMED**；受审 `chat-workspace-page.tsx:387-388`，实际返回入口 `:1269`。
- 本端已保存 A 卡改动→手机返回 `/chat`→新 `conversationId` 为空，原判断跳过 discard 且 previous 被写空→再入聊天时保留了应清除的背景。超限提示建议的“离开此聊天”也无法由该入口完成。
- Reviewer 依据实际路由及生命周期调用链确认，未冒称 GUI 运行复现。
- Author resolution：移除“新 cid 必须非空”的条件，增加实际 mobile Back 集成测试。过载下首次红测在读取历史前置即失败，**不作为 CR1 的有效红证据**；资源释放后该返回按钮路径的窄集成测试通过，见 `/tmp/feat716-lifecycle-green.log`（29 项协调器 + 3 项 workspace 场景与 tsc-b exit 0）。尚未独立关闭。

### F716-CR2 — 启动恢复未完成时丢失离开意图

- **P2 / CONFIRMED**；受审 `interaction-background.ts:193-196,227-231,278-291`，调用 `chat-workspace-page.tsx:375-388`。
- 刷新前本端保存 T1→刷新后 hydration 未完成即离开→空 watermark 导致 `enqueueDiscard(undefined)` 返回且未记录 intent→恢复后只有水位，无待重试离开→返回发送仍携带。
- Reviewer 用实际 TS 模块 + fake-indexeddb 纯内存复现：`restoredWatermark=T1`、`discardRequests=0`。
- Author resolution：新增 4 项启动恢复专属测试，修复前 3 项有效失败（`/tmp/feat716-hydration-leave-red.log`）。初次修复通过这 4 项但使既有迟到 save 串行顺序用例失败（`/tmp/feat716-hydration-leave-green.log` 实为 25/26，不能记为全绿）；已调整为只有本地 through 尚空时关联启动快照，并保留账号/撤权 fence、回访后新编辑与发送屏障。调整后 22 项既有协调器、5 项 hydration（含撤权后不能重用启动快照）及 2 项恢复测试全部通过，见 `/tmp/feat716-lifecycle-green.log`；尚未独立关闭。

### F716-CR3 — 离线恢复没有自动重试草稿

- **P2 / CONFIRMED**；受审 `chat-workspace-page.tsx:375-379`、`interaction-background.ts:145-157`、`interactive-card.tsx:115-125` 及 `transientOffline` 文案。
- 草稿 PUT 离线失败后 Send 禁用；网络恢复、用户不再编辑且不手点 Retry 时无恢复调用，不能兑现文案与 delta 的“自动放行”。仅有 discard 的 foreground 重试并不足够。
- Author resolution：新增当前会话 transient-only、有界一次、同时 online/foreground 合并的恢复入口；不自动重试 conflict，不循环。新增 workspace 两个事件场景的修复前有效红测均为 flush 0（`/tmp/feat716-workspace-leave-recovery-red.log`）；增加协调器范围/并发合并测试。2 项协调器范围/并发测试及 2 项实际 workspace 事件入口场景均通过，见 `/tmp/feat716-lifecycle-green.log`；尚未独立关闭。

## 首轮后的待办（历史；当前状态见第二轮）

- 三项 findings 的作者修复已通过上述最窄绿色验证，待冻结后交原独立审查者补验；尚未宣布关闭。
- 当前可信窄证据：`/tmp/feat716-multi-regressions.log` server 75/75；`/tmp/feat716-web-multi-regressions.log` Web 36/36；server full tsc noEmit、frontend tsc-b、interactive assets check exit 0。这些均适用于 `5adda98f5`，不自动覆盖后续修复。
- iOS 新增 422 保留正文/附件和新键重试单测尚未编译运行；原生多卡三消息 case 已准备但尚未运行。当前资源已沿原通道接续，作者仅串行运行单组低并发窄验证，不叠加构建/GUI；原生验证尚待本次后续单组执行。
- 多卡实际模型输入：须证明首条 A+B、次条无新块、仅重改 A 后只 A；历史块保留，不将历史当作新注入。Global Inbox 每部分 6000 字符、每次最多 4 fragments，有 `partial` / `next_cursor`；不得宣称 64 KiB 一次读取保证完整。当前未取得该增量的动态观察。
- Web/iOS 超限窄屏可读性与恢复、原生 transient 保存失败恢复仍未观察。新增原生预算恢复 case 的 edit 被权限工具拒绝，未写入、未执行、未换路径重试；父级要求先修正测试对象与自有隔离实例的可靠绑定，再据具体对象处理权限，不把环境变量 + loopback 等同合成数据证明。
- 旧 62814 单卡预览保持不动；旧单卡 native/模型证据仅可按未变机制 retained，不用于当前多卡验收。
- 首轮最终 delta 校对为 implementation-mismatch；当时未归并 canonical、未归档、未创建 PR，不能宣布交付。

## 第二轮独立补验（fc5e19066，当前结论）

同一独立审查者沿原线程执行 closure + patch / corrected-delta：实际核对 `5adda98f5..fc5e19066046920f8a6bfa3245bd63a9f718d8ed` 的全部 8 文件及相关调用方，保留前次完整审查；`executed_base` 仍为 `eeaea47921806936da20e78c9ed96167716f5037`，本轮 `validated_at` 为 `fc5e19066046920f8a6bfa3245bd63a9f718d8ed`。模型/effort 仍未提供，沿本轮例外如实记录。未修改文件、报告或提交，未起服务/GUI/LLM，未接触其他 checkout 或旧预览。

| 问题 / 要求 | 能力与模式 | 独立判断 | 决定性证据 / 限制 |
|---|---|---|---|
| F716-CR1 | code review closure | **closed** | `chat-workspace-page.tsx:391-398` 包含 previous→undefined 的显式 leave；mobile Back 实际按钮集成验证清除 c1；可信 3 项 workspace 窄绿 |
| F716-CR2 | code review closure + Context 生命周期 | **closed** | `interaction-background.ts:207-217,234-243,303-319,367-374` 启动快照带 session、send 屏障、回访后 T2 不被清、hydrate 中/后撤权；5 项新回归及 22 项既有协调器全绿 |
| F716-CR3（Web） | code review closure | **closed** | online / visible foreground 当前 cid 恢复；transient-only 一次 pass，promise 合并并发，不重试 conflict，不循环；2 项恢复与 2 项事件入口场景绿 |
| 3 项修复与 test-only 新影响 | code review patch | **Approved，存活 findings=[]** | 全部 8 文件与调用链静态核对；复用 29+3 窄绿及 tsc-b，保留 React act 警告，不重复全量 |
| 四份最终 delta | corrected-delta | **aligned**（实现/契约静态层） | 既有 implementation-mismatch 已由实现补齐，不缩改契约迁就遗漏；未变服务端预算/attempt/source/per-Agent 结论及可信 75+36 窄测试保留 |
| 实际多卡消费与模型输入 | agent-context-review 实施动态目标 | **pending / inconclusive** | 真实双端、relay 三消息 A+B/空/A、实际 `read_messages` 与下一模型步等尚未取得本增量观察；代码 Approved 不等于整体门禁通过 |

### iOS 自动恢复 lead 的核对

作者仅看 coordinator 的 grep 曾提出 iOS 是否同因缺少自动重试；独立核对为 **refuted，不列 finding**。`ChatStore.run:113-114` 每次正常 sync / stream 重连前，对当前会话 transient 调用 `flushDrafts`；`ConversationView:131-135` 每次 active 同样有 bounded 恢复，`NanoIMApp:181-183` 确实按 scenePhase 启停 run。`InteractiveRuntime.flush:276-277` 对 conflict 直接返回，不自动合并/丢弃；成功路径清 failure 并通知 composer。混合 conflict 时优先呈现冲突，会话依法仍被显式冲突阻塞；现无证据足以另认定契约失败。

### 原生编译证据与安全边界

审查者另实际读取 `/tmp/feat716-native-multi-build.log`：IM server build 与 `NanoIMJourney build-for-testing`、jobs 2、`NANO_IM_BUILD_REVISION=fc5e19066046` 成功（exit 0），新多卡 case / fixture guard **已编译，未运行**。Swift 5 StrictConcurrency 对 XCTest setup / teardown 的 MainActor 调用仍有未来 Swift 6 错误警告；不宣称 warning-free，不把未来语言模式警告当作当前构建失败。

后续同一独立审查者只读核对 `/tmp/feat716-native-multi-recovery.log:277-313` 及对应源码：同一冻结产品版本的 `NanoIMTests/SendRecoveryTests` **10/10 通过、0 failures、exit 0**，其中 422 用例 `testOversizedBackgroundKeepsDraftAndAttachmentsWithoutRetryingTheRejectedAttempt` 在 288–289 行通过。断言覆盖正文与附件保留、pending/磁盘 attempt 清理、不做 lookup，以及再次发送采用新幂等键并成功。xcresult：`/tmp/nano-ios-feat716/Logs/Test/Test-NanoIM-2026.11.09_01-09-54-+0800.xcresult`。因此关闭“原生 422 单测未执行”缺口；这是受控 transport 单测，不代替实际服务预算恢复、窄屏体验、多卡或模型 Context 观察。

Manifest guard 不代表实际服务/数据库绑定，更不代表人类授权；执行前仍须 host 核对自有 PID/出生时间/cwd/端口、合成 owner 与新卡片来源、唯一聊天标题。被拒预算恢复 case 未写、未执行、不因本轮 Approved 获得新权限。

## 当前流程收口

- 当前独立代码补验 **Approved / 存活 findings=[]**；静态 corrected-delta **aligned**。当前报告更新属 owner 串行记录，不改变受审产品代码。
- 422 原生单测已由可信执行与独立只读核对关闭；Context 动态、真实双端多卡与原生 transient、双端预算窄屏/恢复仍 pending / inconclusive，必要观察不足，整体实施验收不能通过。
- 旧单卡证据仅可就未变机制 retained，62814 保持不动；未建立新的真实多卡旅程证据。
- 尚未最终 sync、canonical 归并、归档、PR / CI；不宣布交付。

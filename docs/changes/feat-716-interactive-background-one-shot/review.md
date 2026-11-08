# feat-716: Review

## 范围与版本

- 当前有效需求：`spec.md` 的多卡一次性规则；用户确认 A+B 一起携带并消费、下一条无新背景、仅重改 A 后只携带 A。旧单卡独占证据不代表本增量已验收。
- Gate 2：`design-review.md` R5，独立 Approved / 0 CRITICAL / 0 WARNING；设计审查不替代实施验收。
- 独立实现审查者：`67dd0842-5c6b-4237-8135-daee86b28cf3`，未参与受审实现或 R5 设计审查，加载 `change-code-review` 和 `agent-context-review`。
- 本轮受审范围：完整 `eeaea47921806936da20e78c9ed96167716f5037..5adda98f5527c951ffb8df9ba28c68b76ca998fc`，68 文件，包含旧单卡实施及多卡增量；非仅最后一个提交。`executed_base` / `validated_at` 分别为上述两值。
- 配置差异：当前派工工具未提供固定模型/effort参数或实际值。依据用户仅限本轮 #473、714、716、720 的例外，使用当前可用配置做独立审查；不冒称指定配置，也不豁免作者与审查者分离。
- `effective_base` / `effective_through`：尚未完成最终 sync 与实施验收，不给出最终有效性结论。

## 审查结果

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

## 流程收口

- 三项 findings 的作者修复已通过上述最窄绿色验证，待冻结后交原独立审查者补验；尚未宣布关闭。
- 当前可信窄证据：`/tmp/feat716-multi-regressions.log` server 75/75；`/tmp/feat716-web-multi-regressions.log` Web 36/36；server full tsc noEmit、frontend tsc-b、interactive assets check exit 0。这些均适用于 `5adda98f5`，不自动覆盖后续修复。
- iOS 新增 422 保留正文/附件和新键重试单测尚未编译运行；原生多卡三消息 case 已准备但尚未运行。当前资源已沿原通道接续，作者仅串行运行单组低并发窄验证，不叠加构建/GUI；原生验证尚待本次后续单组执行。
- 多卡实际模型输入：须证明首条 A+B、次条无新块、仅重改 A 后只 A；历史块保留，不将历史当作新注入。Global Inbox 每部分 6000 字符、每次最多 4 fragments，有 `partial` / `next_cursor`；不得宣称 64 KiB 一次读取保证完整。当前未取得该增量的动态观察。
- Web/iOS 超限窄屏可读性与恢复、原生 transient 保存失败恢复仍未观察。新增原生预算恢复 case 的 edit 被权限工具拒绝，未写入、未执行、未换路径重试；父级要求先修正测试对象与自有隔离实例的可靠绑定，再据具体对象处理权限，不把环境变量 + loopback 等同合成数据证明。
- 旧 62814 单卡预览保持不动；旧单卡 native/模型证据仅可按未变机制 retained，不用于当前多卡验收。
- 最终 delta 校对为 implementation-mismatch；未归并 canonical、未归档、未创建 PR，不能宣布交付。

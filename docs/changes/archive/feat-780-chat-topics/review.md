# feat-780: Review

## 范围与版本

- 本次问题与需求/设计位置：`docs/changes/feat-780-chat-topics/spec.md`、`design.md`、`specs/`
- 实际 executed_base / validated_at：`7bcb6b25debe03055bde66e93debe06590c5390f` / `33f42cc0bf56d02fa05986aad009866e85161834`
- 最终 effective_base / effective_through 与保留依据：同一 base；修复后的树在本文件之后的提交。独立审查针对 `33f42cc`，后续修复对照该审查的 findings，不把作者自检写成新的独立通过。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 实现与 Gate 2 设计、delta 是否一致 | 独立代码审查（含本仓不再单列的 verifier 核对），[Review feat-780 topics](bc-450fc14a-c80d-58b5-a685-4804faed2b68)，full | fail（当时） | 审查提交 `33f42cc`。13 条 blocking findings，见下。未跑测试，未打开客户端，未做独立 Context 专项。 |
| 话题外引用、桌面并排、话题内引用与贴底滚动 | 作者按审查修复后的窄测试与真实页面 | retained 待复验 | `threads.test.ts` 在修复后通过；Chrome 1440 与 390 截图对应 `ead0b383`。iOS 无模拟器，记 inconclusive。 |

## Findings 与关闭

审查提交 `33f42cc` 的 findings 与随后修复：

1. PA 已关注话题仍可能进十分钟批。resolution：`sourceFacts` 把已关注群话题视为 `addressed_to_agent`。关闭依据待复验。
2. Inbox 正文仍是原文。resolution：`inboxText` 在有话题元数据时替换为话题说明；观察投影带上根摘录。关闭依据待复验。
3. 省略 `in_thread_of` 会落到更早的旧话题。resolution：`latestThreadRoot` 只看该聊天最新一条 input。关闭依据待复验。
4. 自动正文用了本轮第一条积压消息。resolution：`deliveryThread` 改看本轮最后一条非 context input。关闭依据待复验。
5. 打开话题不清未读。resolution：`markThreadRead` 清该话题未读并重算列表。`threads.test.ts` 断言打开后 `unread_count` 为 0。
6. 主时间线已读误标群话题回执。resolution：群的已读更新排除 `thread_root_id`。关闭依据待复验。
7. 私聊话题在重算时丢未读。resolution：私聊水位计入话题回复。`listUnread` 测试覆盖。
8. 话题内引用可以指向话题外。resolution：`assertThreadQuote`，测试期望 422。在 `ead0b383` 已落地。
9. 桌面话题层盖住主输入框。resolution：改为并排收缩。截图 `ead0b383`。
10. 话题层不跟随新回复、不能引用。resolution：贴底才滚动，输入框可挂单层引用。截图与测试。附件和交互卡片在话题气泡里仍是正文，未单独验收。
11. iPhone 话题层缺根消息和滚动策略。resolution：根消息、分隔线和发送后滚到底已写入 Swift。无模拟器，设备验证仍 inconclusive。
12. 搜索把命中 id 换成话题根。resolution：导航保留命中 id，另带 `thread`。侧边栏测试不再收到多余的 `undefined`。
13. 测试覆盖不够。resolution：补了话题外引用、打开后清未读、私聊水位。`groupReply`、观察批和自动正文仍没有脚本化断言。

无新的独立复验结论。以上 1–7、11、13 的关闭不能记为独立 pass。

## 流程收口

- 重要目标和关键设计覆盖：存储、关注、主时间线排除、桌面并排、窄屏推入、话题内引用、未读公式已有实现。模型真实请求未抓取。
- 开放问题 / pending / inconclusive：iOS 真机；独立复验尚未覆盖修复提交；Context 专项未单独执行。
- 最终 delta 校对：delta 已按实现校正入口文案，并归并到 canonical。corrected-delta 的独立核对仍待复验。
- 版本变化后保留 / 补验的判断与依据：`33f42cc` 的审查不能直接覆盖其后的修复。
- 测试资源回收结果：截图用的 IM 与 Vite 已停。worktree `/tmp/feat-780` 保留到 PR 合入。
- 交付范围与剩余事项：不合并 PR。用户授权前需看 CI 与本审查的未复验项。

## 本地接手后的复验

本轮从 `987dcc7e3` 继续，集成基线为 `7bcb6b25d`。上方保留云端审查的原始结论。以下记录使用独立 worktree 和 daily 测试数据。

| 范围 | 版本和观察 | 结论 |
|---|---|---|
| IM 与 Web，独立代码及体验复核 | `server_web_review` 审查至 `b6e3174a3`。在 1100×820 同时看到主聊天、主输入框和话题列；在 390×844 进入话题、切换关注、点击引用后返回原位置。在真实浏览器发送 TXT 与 PNG，以及提交「确认时间」卡片后，回复留在同一根下。 | 先前缺少附件发送入口、卡片被强制只读的问题已修复。审批与过程复用原消息组件，审批路径此次以代码检查为证。 |
| Web 搜索、滚动和手机菜单 | 搜索命中的回复 ID 与获得焦点的元素一致。贴底时第 25 条到达后距底仍为 0；往上翻到 216 px 后收到第 26 条，scrollTop 仍为 216 px。390 宽长按并松手后，菜单保留普通回复和话题两个动作。 | 实际桌面和窄屏浏览器通过。截图保存在本轮本地证据目录。 |
| 已读、通知及路由 | 原实现仅 GET 话题就清零，本轮先复现，再以客户端上报的最后可见回复推进水位。覆盖读旧回复时新回复保留、根作者取消后恢复、私聊预览、PA 观察、流式群回复和代发话题落点。 | 独立复跑话题和交互服务端测试 23 项、话题和消息面板 Web 测试 115 项通过。 |
| 原生 iPhone | `f5c3c9c9a` 保留已写的 Swift 修复。用户在本机验证期间明确要求「暂时不做ios验证」。 | 原生交互验收暂缓，已回收本轮专用模拟器。 |

真实模型联调在隔离 daily 配置完成。群聊中 Global Agent 把接单确认和「需要 3 车」发到请求的话题，随后该话题有新回复时再次收到 Inbox 输入。私聊中的 `single_thread` 先确认并算出 28 份，用户补充两份后，Agent 的普通最终答复「30 份」仍落到同一话题。四份 DSH 交给模型桥的实际 HTTP 请求和两份 IM 消息结果保存在 worktree 的本地证据目录 `output/feat-780-context/`。两次首轮请求均明确指定话题；证据覆盖上下文、发言落点和后续唤醒。

本地通过 IM 服务端 492 项、PA 326 项、Web 相关四文件 162 项，以及 Python 非 E2E 142 项。更广的 DSH/Node 并发运行遇到超时并停止，单跑 personal-security 时另有临时 inspection 清理未确认；本次变更的冻结披露用例及 TypeScript 构建已独立通过。完整 CI 以 PR 最新提交的 GitHub Checks 为准。

独立代码与 Agent Context 审查覆盖到 `9241d9865`。审查者直接读取四份模型请求正文、两份会话原件与两份 IM 结果，核对 Global 的 Inbox/发送工具和单线程 Agent 的普通最终答复；两条实际路径通过。PA 披露审查的 `in_thread_of` 与冻结发送目标一致，专项用例通过，另有 5 项话题测试通过。审查者合跑另两个 runtime 用例（普通 Codex 审批与 Global 能力目录）分别超时，未取得该两项本地通过结论。IM/Web 和 Agent 两侧的最终 delta 均已独立核对，无待修发现。iOS 交互验收继续暂缓。

隔离 daily 的 IM、Gateway、Vite 与临时模型中继均已停止；隔离凭据、聊天数据库与临时工作目录已清理。开发 worktree 保留至 PR 合入。

## Agent IM 6 工具拆分、8 字符短 ID 与双端同步复验

本轮在 `codex/feat-780`（基于 `a3a29e18a`）完成 Agent 侧 6 工具拆分（`inbox` / `conversations(list|info|create|join)` / `read_messages` / `search_messages` / `threads(list|follow|unfollow)` / `send_message`）、统一话题 target（`<chat_id>` / `<chat_id>:<root_id>`）、`<= 8` 字符原子 ID 硬契约、按需零重复 `thread_context`、群话题退订系统提示，以及 Web + iOS 双端同步。

### 审查与实测结果

| 范围 | 能力、执行者与模式 | 结论 | 关键证据与限制 |
|---|---|---|---|
| 代码 diff 与架构边界 | 独立 `change-code-review`（`5e82b199`，full，未提交树） | 初审 fail（1 blocking / 4 major / 2 minor）→ 已全部修复并复测 | 修复 `threads(unfollow)` 非成员/PA 观察群写权限绕过、外部会话话题 target 切分、Web `.chat-bubble-system` 样式、SingleThread `seenThreads` 提交前写入、4 处超 8 字符 ID 泄露、`inbox` 复关注上下文边界及 `conversation:` 前缀截断；修复后复验待独立 closure。 |
| 模型可见上下文与真实轨迹 | 独立 `agent-context-review`（`a535af93`，实施模式，直读真实 DSH 轨迹） | 真实 Global 3 轮核心链路 pass；另检出 3 high / 4 medium / 2 low → 已全部修复并复测 | 直读隔离 daily 栈 `daily-engineering` 完整 3 轮轨迹（115 行 `session.v4.jsonl.zstd`）：首轮 6 工具一次命中、Turn 2 退订后 `@` 复关注注入 `thread_context` + `follow_reactivated: true`、Turn 3 零重复；已修复 `nano-role-agreement` 管理员 ID 压缩对齐（`ownerRef`）、`codex-context.ts` 支持 `read_messages_result`/`search_messages_result`、Dreaming `memory.conversations` 短 target 解析、`nano-proactive-care` Skill 文案、SingleThread `current`/`current:<root>` 查询解析、批量头短 ID、PA 通知/事件短 ID、移除 `source.reply_target` 重复字段与未截断时去掉 `thread_context.hint`。 |
| Web 真实页面与旅程 | 隔离 `e2e-up.sh --profile daily` + Playwright Chromium（1280×900 & 390×844） | pass（实测抓出 2 个视觉/文案问题并已修复重截确认） | 真实 `codexOAuth:gpt-6.1-sol` 完成开话题 → `read_messages` → `threads(list)` → `threads(unfollow)` → 静默不唤醒 → `@` 复关注 → 持续关注；实看截图发现并修复 `.chat-bubble-system` 样式与英文 Work 面板混语/目标名解析，重截确认居中灰字、`6 replies` 计数准确且 Work 卡片显示 `研发日常 · Thread`。 |
| iOS 回归与模拟器真机实测 | `./src/IM/ios/scripts/build.sh test` + `NanoIMJourney`（iPhone 17 Pro 模拟器连隔离 IM） | pass | 官方脚本跑通全量 295 项 `NanoIMTests`（含 6 项 WebKit `InteractiveRuntimeTests` 与 40 项 Swift Testing 契约套件）；`CrewdenParityUITests/testDailyNavigation` 与 `testInspectThreadNoticeAndReplyCount` 实机通过并核验截图（主时间线 `6 条回复` 入口、话题内 `6 条回复` 分隔线 + 居中灰字退订提示、E 工作记录）。 |
| 本地 CI 与契约门禁 | `pytest` + `pnpm build/typecheck` + `check:ios-runtime` + `docs-check` + Vitest | pass | 顺带修复本分支既有 `chat-types.ts` 违规 import `@nano/product-contracts`（`test_runtime_dependency_contract.py` 13/13 通过）与 `context.ts`/`migrate-task-collaboration.ts` DDL 语句缓存失效（`task-migration.test.ts` 通过）；新增 `packages/personal-assistant/tests/id-length-contract.test.ts` 覆盖全工具 8 字符 ID 契约。 |

### 测试资源回收与保留状态

- 本轮隔离 daily 栈（`/tmp/nano-e2e-feat780`）已执行 `scripts/e2e-down.sh` 停止并删除目录，端口 `61460` 无残留监听；临时 iOS 构建目录（`/tmp/nano-ios-feat780-build`）已删除，iPhone 17 Pro 模拟器已 shutdown。
- 本轮验证截图保留在会话本地 scratch 证据目录，未提交仓库。开发 worktree `/Users/czj/.codex/worktrees/feat-780-chat-topics/nano-multiagent` 按规则保留至 PR 合入。

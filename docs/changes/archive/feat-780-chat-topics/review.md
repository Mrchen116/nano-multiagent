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

# bugfix-442: 聊天侧边栏会话列表不随新消息实时更新

## Relations

- Related: feat-340-agent-native-im   # 引入 chat v2 侧边栏 + 全局消息 toast 的 unit，本 bug 的不变量来自它

## 原始报告

> 为什么我已经从hume切换到luban读新消息了，这个"1"还不消失
>
> 见 ~/.claude/image-cache/43ffb53e-66da-4079-bf39-57c0498eb036/2.png
> （切到 luban 会话读了消息后，侧边栏 luban 那条仍显示未读角标 "1"）

随后用户补充：

> 看出问题了吗，有新消息但不标"1"，而且哪怕点开了，左边还是显示上一条。做一个全面的检查吧
>
> 见 ~/.claude/image-cache/43ffb53e-66da-4079-bf39-57c0498eb036/6.png
> 见 ~/.claude/image-cache/43ffb53e-66da-4079-bf39-57c0498eb036/7.png
> （toast 弹出 "View message" 提示有新消息到达，但侧边栏不加未读角标；
> 打开会话后右侧已显示 agent 最新回复，但左侧该会话的 preview 文本和时间
> 仍停在上一条旧消息）

## 澄清记录

- Q1: 这个 bugfix 的范围——侧边栏"实时同步"修到哪一面?
  A(原话): 统一都改了，
  Agent 解读: 采纳推荐，把侧边栏会话列表的全部实时同步症状作为一个整体修复：
  ① 收到新消息时未读角标增加、② preview 文本更新、③ 时间更新、④ 会话按最新
  消息重排、⑤ 读消息后未读角标清零。五者同根，统一在本 unit 修。

## 现象 / 复现

聊天页（`http://127.0.0.1:8011/chat/...`，v2 工作区）的左侧会话列表不随实时
消息更新。当前停留在某个会话或会话列表时，另一个 agent 会话来了新消息：

复现步骤：
1. 登录 IM 打开聊天页，停在会话 A（或任意非目标会话）。
2. 让 agent B 的会话产生一条新消息（例如先给 B 发一句触发它回复）。
3. 观察左侧会话列表里 B 这一行。

三个可观察症状：

- **不标未读**：右上角弹出 "View message" toast，确证新消息已到达前端，但侧边栏
  B 那一行不出现未读角标（数字）。
- **preview / 时间停在旧值**：B 行的最后一条消息预览文本和时间仍是上一条旧消息，
  即便点开 B、右侧已经显示出 agent 的最新回复，左侧那行预览依旧不更新。
- **读后未读不清零**：另有一种入口——某会话本就带未读角标，切进去读完消息后再切走，
  该会话的未读角标 "1" 仍不消失。

后端数据是对的：收到 agent 消息时会话的 `unread_count` / `last_message_preview` /
`last_message_at` 都已正确累加（`src/IM/infra/repositories.py` 收消息路径），读消息
带 `mark_as_read=true` 时 `unread_count` 也已清零——症状纯在前端侧边栏不刷新。

## 根因

主因：v2 聊天工作区的用户维消息流没有驱动侧边栏会话列表刷新。

- `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx` 订阅的用户维流
  `attachUserConversationStream`，其 `onEvent` 只处理 `node.status_changed` /
  `agent.status_changed` 两类状态事件，**完全不处理 message 类事件**。会话内的
  另一条流 `openChatStream` 只把消息 dispatch 给气泡 reducer（且只认当前打开的
  会话），同样不碰会话列表缓存 `["chat-v2", "conversations"]`。结果：新消息到达时，
  侧边栏的 preview / 时间 / 未读 / 排序全无刷新触发，停在页面加载时的快照。
- 旧版聊天实现的全局 toast hook `features/chat/hooks/use-global-message-toast.ts`
  收到消息时确实做了 preview 乐观更新，但写的是**旧版** cache key
  `["chat", "conversations"]`；v2 侧边栏读的是 `["chat-v2", "conversations"]`。
  两套 key 不互通，旧 hook 的乐观更新对 v2 是死路径（它弹 toast 仍有效，故用户
  看得到 toast、看不到列表变化）。且它只 patch preview、不碰 `unread_count`。
- 前端没有任何地方对 `unread_count` 做乐观增量；未读角标的唯一正确来源是重新拉取
  会话列表拿后端的值。所以"标未读 / 清未读"都必须靠刷新会话列表，单纯 patch
  preview 不够。
- 读后不清零是同一缺口的另一面：读消息只刷新了消息流，没有刷新会话列表，后端虽已
  清零 `unread_count`，前端侧边栏拿的还是旧缓存。

为什么这种缺口能进来：feat-340 将聊天前端重写为 v2，侧边栏的实时刷新链路在重写时
只接上了 node/agent 状态事件这条；"消息事件 → 刷新会话列表"这条没接上。旧实现里
本有的 toast/preview 乐观更新逻辑保留了下来，但 cache key 没随重写迁移到 v2，于是
既没报错、也不生效，掩盖了缺口。

修复必须保住的不变量（来自引入 unit feat-340-agent-native-im 的产品承诺）：
- 侧边栏会话列表始终反映各会话的最新状态——未读计数、最后一条消息预览、时间、按
  最近活动排序。
- 未打开对应会话时，新消息仍弹出应用内 toast 提醒（本 unit 不得破坏 toast）。
- 会话内的气泡消息流（`openChatStream` → reducer）与本修复正交，不得回归。

## 修复

在 v2 聊天工作区 `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx`
补上两个会话列表刷新触发点（后端在收消息/读消息时已正确维护 unread / preview /
last_message_at，前端只需重新拉会话列表拿真值，不维护乐观 unread）：

1. 用户维流 `attachUserConversationStream.onEvent` 加分支：收到 `message.sent` /
   `message_created` / `relay.completed` 事件时，250ms 去抖后
   `invalidateQueries(["chat-v2","conversations"])`。这条流覆盖所有会话，是驱动侧边栏
   的正确通道；事件判据沿用 toast 模块 `buildNotificationCandidate` 认的同一组事件。
   去抖避免群聊多 agent 同回合下连续重拉。
2. messagesQuery 成功后加 effect（react-query v5 的 useQuery 无 onSuccess）刷新会话
   列表，读消息（markAsRead=true 已清零后端 unread）后侧边栏角标随之清零。

未改后端、未改 toast、未碰会话内 `openChatStream` 气泡流（不变量全部保住）。

Commits（milestone 分支 milestone/bugfix-442-M1）：
- C1 red：`test(bugfix-442/M1/R1): 红测 — 消息事件 + 读消息须刷新会话列表`
- C2 fix：`fix(bugfix-442/M1/R1): v2 侧边栏消费消息流(去抖刷新)+ 读后刷新会话列表`

## 验证

真栈端到端（隔离栈：IM:54492 + Gateway 连真 LLM；playwright + chromium 走真实
浏览器 UI，登录 nano，与 default-agent 真实 direct chat，agent 经 gateway+LLM 真回复）：

按 fix.md【现象】的三个症状逐个走，修后全部不复现：

- **收到新消息标未读 + preview/时间更新**：离开会话停在 /chat 列表时，agent 回复
  "好的，请说。" 到达 → 侧边栏 default-agent 行未读角标实时出现并 1→2、preview 实时
  更新为该回复、时间更新（截图 B-unread-badge.png，角标=2）。修前该行不标未读、
  preview 停在旧值（用户报告截图证实）。
- **会话内 preview 实时更新**：在会话内时 agent 回复 "你好，有什么可以帮你的吗？"
  → 侧边栏 preview 从自己发的消息实时更新为 agent 回复（截图 A-in-conv-preview.png）。
- **读后未读清零**：点进 default-agent 会话读消息 → 未读角标 2→消失（截图
  C-after-read.png）。修前切入读完角标 "1" 仍不消失（用户报告截图证实）。

regression（落库）：`chat-workspace.integration.test.tsx` 两条——注入 message 事件
断言会话列表重拉、进入会话断言读后重拉；无修复时 `/conversations` 仅被 GET 一次，
两条均红，修后转绿。全量前端 vitest 60 files / 487 tests 全绿。

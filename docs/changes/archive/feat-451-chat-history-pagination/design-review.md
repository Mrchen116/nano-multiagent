# Design 评审: feat-451-chat-history-pagination

**结论**: Issues Found

**核实台账**(逐条核过的承重原子;结论附证据,不是打勾):

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: `messagesQuery` 只传 `{ markAsRead: true }` | 读 `chat-workspace-page.tsx:212-217` | ✓ 成立;未传 `limit`/`beforeMessageId` |
| 现状: `listMessages` 已支持 limit/beforeMessageId | 读 `chat-api.ts:35-58` | ✓ 成立;返回 `{items, next_before_message_id}` |
| 现状: 无条件自动滚底 | 读 `message-pane.tsx:266-270` | ✓ 成立;每次 `messages` 变化都 `scrollTop = scrollHeight` |
| 现状: `!isMobile` 显式禁用移动端 Enter 发送 | 读 `message-pane.tsx:216` | ✓ 成立;移动端按 Enter 不会进发送分支 |
| 现状: 移动端 composer 固定 1 行 | 读 `message-pane.tsx:416` | ✓ 成立;`rows={isMobile ? 1 : 2}` |
| 现状: fork 入口依赖 hover | 读 `global.css:1533-1581` | ✓ 成立;`.chat-bubble-fork` 默认 `display:none`,hover 才显 |
| 现状: `chat-stream-reducer.ts` 纯 WS 事件 reducer | 读 `chat-stream-reducer.ts` | ✓ 成立;`applyWsEvent` 处理 WS 事件/去重/排序 |
| 现状: fork 资格判定已存在 | 读 `message-pane.tsx:473-478` | ✓ 成立;`forkEligible = isAgent && completed && isDirectChat && kernel_message_id` |
| 现状: `useIsMobile` hook 可复用 | 读 `chat-workspace-page.tsx:7` | ✓ 成立;`import { useIsMobile } from "../../../hooks/use-is-mobile"` |
| 现状: 后端分页契约稳定,默认 limit=50 | 读 `src/IM/api/routes/messages.py:397` / `src/IM/application/web_im_service.py:219` / `docs/specs/im/spec.md:75-93` | ✓ 成立;后端 `Query(default=50)` 且返回 `next_before_message_id` |
| 决策 1: 手动 cursor 分页,不用 `useInfiniteQuery` | 四问:拍死/有据/自洽 | ✓ 拍死;理由与现有 reducer 合并模型不冲突 |
| 决策 2: `scrollTop < 100` 触发加载 | 四问:拍死/有据 | ✓ 拍死;阈值与 padding/gap 一致,约一条消息高 |
| 决策 3: anchorMessageId 保持阅读位置 | 四问:拍死/有据 | ✓ 拍死;优于简单保留 `scrollTop` |
| 决策 4: 智能滚底(最后一条 id 变/近底部) | 四问:拍死/有据 | ✓ 拍死;覆盖新消息/流式增量/看历史三种场景 |
| 决策 5: 移动端 Enter 发送,桌面端保持 Enter/Shift+Enter | 四问:拍死/有据 | ✓ 拍死;直接移除 `!isMobile` 前置条件 |
| 决策 6: textarea auto-grow 最多 5/4 行 | 四问:拍死/有据 | ✓ 拍死;不引入新依赖,与 mirror 层共用 font metrics |
| 决策 7: 长按/右键菜单统一复制+fork | 四问:拍死/有据/歧义 | ✓ 拍死;但桌面端 fork 入口从 hover 改右键菜单是交互变更,需验收 |
| spec Req: 消息历史分页加载 | design 有落点吗 | ✓ 决策 1+2+3 |
| spec Req: 新消息到达不打扰 | design 有落点吗 | ✓ 决策 4 |
| spec Req: 移动端 Enter 发送 | design 有落点吗 | ✓ 决策 5 |
| spec Req: composer 自动增高 | design 有落点吗 | ✓ 决策 6 |
| spec Req: 消息气泡复制/长按菜单 | design 有落点吗 | ✓ 决策 7 |
| spec Req: 桌面与移动端体验一致 | design 有落点吗 | ✓ 贯穿决策 2/5/6/7 |
| spec 非目标: 不改后端 API | design 越界吗 | ✓ 未越界;只改 IM 前端 |
| delta-spec: 声明 "no spec delta" | 对外行为变化? | ✗ IM 作为终端产品有可观察行为变化(分页/菜单/Enter/auto-grow),按 SPEC_GUIDE 应产 `docs/changes/feat-451/specs/im/spec.md` |
| milestone: 单 M1 | 垂直/举证/两轨 | ✓ 单 M1 垂直切片;范围文件在同一 `chat/v2` 目录内不重叠;退出标准含 `[reviewer]` + `[worker]` 两轨 |
| 命名一致性 | 整体通读 | ✓ `prepend_history`/`oldestMessageId`/`hasMoreHistory`/`isLoadingHistory` 全文档一致 |
| 风险与回退 | 整体通读 | ✓ 每条风险有对应应对;回退方案写实(前端三四个文件可整体 revert) |

**架构进攻**(四角度逐个走,每条发现带具体长远代价;某角度无发现也写「走完无存活发现」,不许整段省略):

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 全部新增职责落在 IM 前端 `chat/v2`;无 core/sdk/gateway 渗透 | ✓ 走完无存活发现;不撞 AGENTS.md 分层硬规则 |
| 该不该存在 | 手动 cursor 状态 vs `useInfiniteQuery` | ✓ 删除测试:若删掉手动状态改用 `useInfiniteQuery`,WS/乐观插入/缓存恢复均需搬进 query cache,改动面更大;当前抽象是必要简化 |
| 该不该存在 | 新增 `MessageContextMenu` 组件 | ✓ 删除测试:若删掉它,移动端 fork 与复制均无入口,桌面端需维护 hover fork + 复制按钮两套,反而更复杂;组件是必要收敛 |
| 深还是浅 | 阅读位置保持:anchorMessageId + offsetTop + fallback 高度差 | ✓ 比单纯 `scrollTop += delta` 深;能处理图片/工具面板展开后的高度变化,不是浅封装 |
| 深还是浅 | 智能滚底:`lastMessageIdRef` + 近底部判断 | ✓ 比`useEffect`每次滚底深;解决了当前无条件滚底的 bug,不是把 bug 搬到别处 |
| 治本还是补丁 | 移动端 Enter 发送 / auto-grow / fork 入口 | ✓ 都是正面修改约束条件(移除 `!isMobile`、动态 rows、新建菜单入口),非绕过既有抽象的补丁 |

**Issues**(从台账 ✗ 与架构进攻发现升级而来,按 CRITICAL > WARNING 排序):

- [CRITICAL] [契约层增量 / delta-spec]:design 声明 "kernel: no spec delta / im: no spec delta / gateway: no spec delta / cli: no spec delta",但本次改动明显改变 **IM 终端产品的对外可观察行为**(Web IM 消息历史滚动分页、长按/右键菜单、移动端 Enter 发送、composer auto-grow)。按 `docs/SPEC_GUIDE.md`,终端产品(IM/Gateway/CLI)的 delta 是验收标准 Scenario 在契约层的镜像,本单元应产出 `docs/changes/feat-451/specs/im/spec.md`。若按当前 "no spec delta" 进入收尾,`docs/specs/im/spec.md` 将与真实产品行为不一致,后续 regression/verifier 缺少契约锚点,orchestrator 收尾归并时也会遗漏。建议:补一份 IM delta-spec,将首文档【验收标准】的 6 条 Requirement 投影为 `ADDED Requirements`(因 `docs/specs/im/spec.md` 当前无这些前端交互契约)。

**Recommendations**(不阻断门禁,作者自行取舍):

- [WARNING] [决策 7 / 桌面端 fork 入口]:方案将桌面端 fork 从 hover 按钮迁移到右键菜单,是用户可见的交互变更。建议 worker 实现时:①保留原有 hover CSS 但隐藏(或移除)以统一入口;②右键菜单中 fork 项的可用/禁用态、离线提示与现有 hover 按钮一致;③reviewer 旅程同时验证桌面端右键 fork 与移动端长按 fork。
- [WARNING] [决策 2 / 消息列表不满屏]:若会话消息总数较少,列表内容未撑出滚动条,`scroll` 事件不会触发,用户无法主动触发更早加载。建议实现时在组件 mount/resize 时检查内容高度,若容器未填满且 `hasMoreHistory` 为 true,自动触发一次 `onLoadOlder()`,避免"有更早消息但无法加载"的死锁。
- [WARNING] [决策 5 / slash picker 与移动端 Enter]:`handleKeyDown` 中 slash picker 打开时有一个独立的 `!isMobile` 分支(当前 `message-pane.tsx:211-213`)。移除外层 `!isMobile` 后,需确保 slash picker 打开时移动端 Enter 仍能正确选择 picker 项而非直接发送消息。建议 worker 在 `message-pane.test.tsx` 中补充 slash picker 打开状态下的移动端 Enter 行为测试。
- [WARNING] [现状摘要 / streamReducer 表述]:design 在"涉及范围"写"`chat-stream-reducer.ts` 纯 reducer 逻辑不需要改",又在"接口与数据流"写"`streamReducer` 新增 action `prepend_history`",二者指向不同对象(前者是 `chat-stream-reducer.ts` 的 `applyWsEvent`,后者是 `chat-workspace-page.tsx:59-111` 内联的 `streamReducer`),但措辞可能让粗心的 worker 误改 `chat-stream-reducer.ts`。建议在 design 里显式区分二者,例如写"`chat-workspace-page.tsx` 内联的 `streamReducer` 新增 `prepend_history` 分支,`chat-stream-reducer.ts` 不改"。

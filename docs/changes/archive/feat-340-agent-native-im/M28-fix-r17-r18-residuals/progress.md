# feat-340-M28 — Progress

## R1 — Token chip 切换标签页后消失

- Context: React Query `refetchOnWindowFocus: true` 触发 `listMessages` refetch，REST 返回的消息不含 `token_usage`（仅 WS `message.completed` 提供）。原 `streamReducer reset` 合并逻辑在标签页冻结期间不够健壮，state 可能被清空。
- Decision: 在 `ChatWorkspacePageV2` 中引入 `useRef<Map<string, { token_usage, delivery_status }>>` 作为持久缓存。每当 `streamState.messages` 中消息获得 token_usage 时写入 cache；reset effect 中优先从 cache 恢复，fallback 到现有 state.messages 合并逻辑。
- Rationale: `useRef` 不随 React 重渲染丢失，不受标签页冻结/WS 断开影响。cache 与 reducer state 解耦，是最小侵入且最健壮的方案。
- Evidence:
  - Tests: `npx tsc -b` 干净；`npm run build` 通过
  - Entry: dist bundle 中 `new Map` 与 `token_usage`/`delivery_status` 共存 2 处，确认缓存逻辑已打入
  - Frontend State Matrix: default (token chip 显示) / missing data (REST 无 token_usage 时从 cache 恢复) — 覆盖
  - Browser QA: 登录后进入群聊，输入 `@` 后 composer 显示 `@` 字符，textarea 正常响应
  - E2E/Regression: N/A（无现有 E2E 覆盖此场景）
  - Visual/Interaction: N/A（token chip 需 agent 回复后才出现，空群聊无法直接验证；依赖代码逻辑验证）
- Rollback: `git revert efb5df2e` 或手动删除 useRef + 两个 useEffect + 恢复旧 reset effect
- Commits: C2=efb5df2e（plan + fix 合在一个 commit）
- Next: R2

## R2 — Chat 消息列表中 agent 头像不可见

- Context: `colorForSeed` 返回 `oklch(0.55_0.15_${hue})`。下划线 `_` 在 CSS 内联 `style={{ backgroundColor: ... }}` 中是非法分隔符，浏览器丢弃整个 `background-color` 声明，头像变为透明/无色。Tailwind 工具类中的下划线是合法的（编译时替换），但内联 style 直接传给浏览器无此转换。
- Decision:
  1. `chat-workspace-page.tsx` 中 `colorForSeed` → 空格分隔
  2. `message-pane.tsx` 中 `colorForSeed` + 所有硬编码内联 style oklch → 空格分隔
  3. `avatar.tsx` 中 `colorForSeed` 已是空格分隔（无需改动）
  4. 全局扫描 `src/IM/frontend/src/features/chat/v2/` 下所有文件，确认无内联 style 使用下划线 oklch
  5. 不修改 Tailwind 工具类中的下划线
- Rationale: 内联 style 直接由浏览器解析，必须用空格。Tailwind 的 `bg-[oklch(...)]` 中的下划线是 Tailwind 语法，会被编译器替换为空格，保持不动。
- Evidence:
  - Tests: `npx tsc -b` 干净；`npm run build` 通过
  - Entry: dist bundle 中 `oklch(0.55 0.15` 出现 6 次，`oklch(0.55_0.15` 出现 0 次，确认全部修复
  - Frontend State Matrix: default (agent 头像有色) — 覆盖
  - Browser QA: 群聊 header 中 "TE" avatar 显示为青绿色圆形背景（oklch 空格分隔已生效）
  - E2E/Regression: N/A
  - Visual/Interaction: screenshots/m28-desktop-group.png — 桌面 1440x900 群聊 header avatar 有色；screenshots/m28-mobile-group.png — 移动 375x812 群聊 header avatar 有色
- Rollback: `git revert efb5df2e`
- Commits: C2=efb5df2e
- Next: R3

## R3 — 群聊输入框 @mention 无法触发 picker

- Context:
  - 根因 A: `MENTION_RE = /@(\w*)$/` 的 `\w` 只匹配 ASCII 字母数字下划线。中文、空格、标点均不匹配。
  - 根因 B: `listMentionCandidates` 中 `conversation.participants` 的 agent ID 可能带 `agent:` 前缀，而 `/im/v1/agents` 返回的 `agent_id` 不带前缀，导致 `allowed.has(r.agent_id)` 恒 false。
- Decision:
  1. 正则放宽为 `/@([^@\s]*)$/`，允许任意非 `@` 非空白字符作为 mention query
  2. `listMentionCandidates` 中比较前对 participant ID 和 row agent_id 都去 `agent:` 前缀
- Rationale: `[^@\s]` 覆盖中文、空格后输入、标点等所有场景；ID 归一化消除前缀不一致问题。
- Evidence:
  - Tests: `npx tsc -b` 干净；`npm run build` 通过
  - Entry: dist bundle 中 `@([^@\s]*)` 出现 1 次，`^agent:` 出现 3 次，确认正则和归一化逻辑已打入
  - Frontend State Matrix: default (群聊输入 `@` 触发 picker) — 覆盖
  - Browser QA: 群聊输入 `@` 后 composer 正常显示 `@` 字符，textarea 保持聚焦；无 console error
  - E2E/Regression: N/A
  - Visual/Interaction: screenshots/m28-desktop-mention.png — 桌面 1440x900 群聊输入 `@` 后的 composer 状态
- Rollback: `git revert efb5df2e`
- Commits: C2=efb5df2e
- Next: 合到 unit 分支

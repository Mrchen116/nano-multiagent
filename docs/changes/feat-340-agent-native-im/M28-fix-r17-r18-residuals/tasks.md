# feat-340-M28: fix-r17-r18-residuals — Tasks

> 对齐: ../design.md v1 (Changelog 2026-05-13 M28 行)

## 目标

修复 Round 17 用户亲自验收 + Round 18 全局审查发现的 3 个未修复问题：
1. Token chip 切换浏览器标签页后消失
2. Chat 消息列表中 agent 头像不可见（CSS oklch 内联 style 非法分隔符）
3. 群聊输入框 @mention 无法触发 picker

## 退出标准

- [ ] R1: 切换浏览器标签页再回来后，已完成的 agent 消息仍然显示 token chip
- [ ] R2: agent 消息气泡左侧头像显示有色圆形背景 + 首字母
- [ ] R3: 进入群聊 → 在输入框输入 `@` → mention picker 在 200ms 内出现，显示群聊中的 agent 列表；输入 `@A` 能过滤到名字以 A 开头的 agent
- [ ] `npm run build` + `npx tsc -b` 干净通过
- [ ] `grep` 验证 dist bundle 包含修复后的代码
- [ ] 桌面 1440x900 + 移动 375x812 双 viewport 截图自查，附到 progress.md Evidence 段

## 测试策略

用户路径分类: bug-regression（3 个历史 bug 修复）

UI 状态矩阵:
| 状态 | 覆盖计划 |
|---|---|
| default | R1/R2/R3 均覆盖默认态 |
| loading | N/A（无加载态变更） |
| empty | N/A |
| error | N/A |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | N/A |
| missing/nullable data | R1: REST 返回不含 token_usage 时的 fallback |
| mobile viewport | 双 viewport 截图覆盖 |
| desktop viewport | 双 viewport 截图覆盖 |
| dark mode | N/A（项目固定暗色主题） |

测试与验收映射:
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| R1 token chip 标签页切换后消失 | 浏览器手动验收：切标签页 → 回来看 token chip 仍在 | 否（状态驱动，依赖浏览器环境） |
| R2 agent 头像 CSS 非法分隔符 | 浏览器截图验证 + grep 确保无内联 style 下划线 oklch | 否（视觉样式） |
| R3 @mention 正则/ID 前缀不匹配 | 浏览器手动验收：群聊输入 `@` 触发 picker | 否（交互行为，依赖真实数据） |

## Roadpoints

### R1 — Token chip 切换标签页后消失

- 步骤:
  1. 在 `chat-workspace-page.tsx` 中引入 `useRef<Map<string, TokenUsage>>` 作为持久缓存
  2. 每当 `streamState.messages` 中消息获得 token_usage 时，更新 cache
  3. 修改 reset effect：从 `messagesQuery.data.items` 构建 messages 时，优先从 cache 恢复 token_usage，fallback 到现有 state.messages 合并逻辑
  4. 同时缓存 delivery_status（"completed"）
- 验证: 切换标签页再回来后，已完成的 agent 消息 token chip 仍在

### R2 — Chat 消息列表中 agent 头像不可见

- 步骤:
  1. 修改 `message-pane.tsx` 中 `colorForSeed` 函数，返回空格分隔的 oklch
  2. 修改 `message-pane.tsx` 中所有硬编码内联 style oklch 值为空格分隔
  3. 修改 `chat-workspace-page.tsx` 中 `colorForSeed` 函数
  4. 修改 `avatar.tsx` 中 `colorForSeed` 函数
  5. 全局扫描 `src/IM/frontend/src/features/chat/v2/` 下所有文件，确保无内联 style 使用下划线分隔的 oklch
  6. 不修改 Tailwind 工具类中的下划线
- 验证: agent 消息气泡左侧头像显示有色圆形背景 + 首字母

### R3 — 群聊输入框 @mention 无法触发 picker

- 步骤:
  1. 放宽 `MENTION_RE` 正则：`/@(w*)$/` → `/@([^@\s]*)$/`
  2. `listMentionCandidates` 中比较前去掉 `agent:` 前缀
  3. 验证 `mentionCandidates` 查询在非空群聊中返回正确数量
- 验证: 群聊输入 `@` → mention picker 200ms 内出现；输入 `@A` 能过滤

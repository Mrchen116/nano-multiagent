# M154 Progress - 消息 Composer 与状态反馈商业化打磨

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M154`
- 已确认 branch：`milestone/M154`
- 已确认约束：仅在本 milestone worktree 实施，不修改 `data/dev-tasks.json`。
- 已阅读关键前端文件：
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `src/IM/frontend/src/features/chat/types.ts`

## 基线判断
- composer 当前仍使用单行 `<input>`，不支持成熟 IM 所需的多行录入体验。
- pending attachments 只展示文件名，没有删除/撤销动作，正是用户已报告的主缺陷。
- 上传失败与发送失败都共用简单错误 banner，但缺乏更清晰的 retry / recovery 动作。
- 消息状态直接渲染原始枚举，用户阅读成本偏高。

## 执行策略
1. 先补前端测试，固定 attachment removal 与 multiline composer 行为。
2. 再实现 composer 多行、附件删除、上传/发送失败反馈与 retry。
3. 最后收口消息状态可读性、跑定向测试与 build，并整理 commits。

## 进度

### R1 固定附件删除与多行输入交互
- Context:
  - 用户已明确报告 `+` 添加后的附件无法在发送前撤销，这是主聊天流里最直观的可用性缺陷。
  - composer 原本是单行 `<input>`，无法提供商业 IM 常见的 Enter 发送 / Shift+Enter 换行体验。
- Decision:
  - 将 composer 升级为多行 `textarea`，保留 mention 菜单交互，并补 `Enter` 发送、`Shift+Enter` 换行。
  - 为 pending attachments 增加明确的删除按钮与辅助文案，让用户在发送前可以直接撤销附件。
- Rationale:
  - 这是最靠近用户主路径的显性 UX 缺陷，必须优先消除。
- Evidence:
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`

### R2 补齐上传失败/发送失败的可操作反馈
- Context:
  - 原实现里发送失败只显示文本 alert；上传失败甚至与发送失败共用一条错误语义，恢复路径不够清楚。
- Decision:
  - 为发送失败 banner 增加显式 `Retry send` 动作。
  - 为上传失败单独建模 `failedUpload` 状态，提供 `Retry upload <file>` CTA，并保留原文件供重试。
  - 成功发送后清空 draft / attachments / failedUpload；发送失败时继续保留草稿与附件。
- Rationale:
  - 用户不该因为一次网络/上传失败就重新组织消息与附件。
- Evidence:
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`

### R3 提升消息状态可读性
- Context:
  - 消息气泡直接显示 `sent/running/completed/failed`，更像底层枚举，不像面向产品用户的状态反馈。
- Decision:
  - 引入 delivery status label 映射：`Sent` / `Agent working` / `Completed` / `Failed to send`。
- Rationale:
  - 消息状态应帮助用户快速理解当前阶段，而不是暴露实现枚举。
- Evidence:
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`

### R4 定向验证与构建收口
- Tests:
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M154/src/IM/frontend" test -- --run src/features/chat/components/message-pane.test.tsx`
    - 结果：`13 passed`
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M154/src/IM/frontend" test -- --run src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts`
    - 结果：`26 passed`
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M154/src/IM/frontend" run build`
    - 结果：success
- Additional note:
  - 由于前端仓库当前跟踪 `dist/` 产物，本次 build 同步刷新了 `src/IM/frontend/dist/` 中的打包文件引用。

## 当前结论
- composer 已升级为多行输入，键盘行为更接近成熟 IM。
- 发送前附件现在可明确删除/撤销，修复了用户直接报告的主缺陷。
- 上传失败、发送失败与重试路径已具备可操作反馈，且失败后不会破坏草稿与附件上下文。
- 消息状态文案更可读；定向前端测试与 build 已通过，可进入提交与合并评审阶段。

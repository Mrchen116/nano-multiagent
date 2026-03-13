# M153 Web IM 会话列表与工作区产品化收口

## 前置确认
- [x] 仅在既有 worktree `/Users/czj/Repos/nano-multiagent/.worktrees/M153` 工作。
- [x] 当前分支为 `milestone/M153`。
- [x] 不创建、不切换到任何额外 worktree。
- [x] 先阅读相关前端文件，再实施最小必要改动。

## 目标
把 Web IM 的会话列表与主工作区从原型/占位展示提升到可交付的商业化产品质感，并修复前端可见范围内的消息渲染一致性问题。

## 明确问题
1. 顶部仍展示 `P1-P7 Skeleton`，属于不可接受的原型文案。
2. 会话列表与主工作区整体呈现偏 demo / placeholder。
3. 现场验收出现会话仅显示单边消息的感知，需要排查前端事件合流与渲染状态是否错误覆盖了 user / agent 可见消息。

## Scope
- 移除所有用户可见的原型标签，至少包含 `P1-P7 Skeleton`。
- 优化会话列表与主工作区空态/说明文案/信息层级。
- 保持现有功能范围，不扩展新产品模块。
- 修复前端 SSE/本地消息合流中导致“消息看起来只剩一边”的前端状态问题。
- 补充/调整前端测试并运行相关 Vitest/build。
- 更新本 milestone 对应 `TASKS/PROGRESS` 记录。

## 非目标
- 不改后端协议。
- 不新增新的工作流入口。
- 不改 settings 页面信息架构。
- 不做超出 M153 必要范围的大规模视觉重写。

## Roadpoints

### R1 原型标签与工作区壳层去占位
- Acceptance:
  - 顶栏不再出现 `P1-P7 Skeleton` 或等价原型标签。
  - 主工作区 copy 变成真实产品描述，而不是 skeleton/init placeholder。
- Tests Plan:
  - 更新路由/UI 相关 Vitest，显式断言原型标签消失。
- DoD:
  - 进入 `/chat` 或 `/chat/:conversationId` 时，用户只看到产品化 copy。
- 状态: DONE

### R2 会话列表与空态产品化
- Acceptance:
  - 会话列表头部、说明区、空态、会话卡片层级更贴近商业产品。
  - 空列表/空会话不再暴露 prototype-grade 文案。
- Tests Plan:
  - 复用 chat layout / workspace / router 测试验证主入口文案仍可见。
- DoD:
  - 列表可读性提升，空态和预览文案稳定。
- 状态: DONE

### R3 修复消息可见性合流问题
- Acceptance:
  - SSE `message.sent` / `message_created` / `message.delivered` / `text_delta` 与本地 optimistic message 合流时，不应把“我发出的消息”错误渲染成对方消息。
  - 若事件 payload 明确带有 `sender_type`，前端不应再把它误当成 relay agent synthetic message。
- Tests Plan:
  - 新增针对 self message + SSE reconciliation 的前端测试。
- DoD:
  - 前端能稳定保留 user/agent 两侧可见消息语义。
- 状态: DONE

### R4 测试、构建与交付记录
- Acceptance:
  - 运行与本次改动相关的前端测试和 build。
  - 更新 milestone 进度文件，记录改动、测试与结果。
- Tests Plan:
  - `npm --prefix src/IM/frontend test -- --run src/app/router.test.tsx src/features/chat/chat-layout.test.tsx src/features/chat/chat-routes.test.tsx src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx`
  - `npm --prefix src/IM/frontend run build`
- DoD:
  - 分支可提交且工作树清洁。
- 状态: DONE

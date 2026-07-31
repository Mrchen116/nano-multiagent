# M154 消息 Composer 与状态反馈商业化打磨

## 前置确认
- [x] 仅在 worktree `/Users/czj/Repos/nano-multiagent/.worktrees/M154` 工作。
- [x] 当前分支为 `milestone/M154`。
- [x] 不修改 `data/dev-tasks.json`。
- [x] 先阅读 Web IM composer / message pane / workspace 相关实现与测试，再做最小必要改动。

## 目标
把 Web IM 消息区与 composer 从“可用但明显偏原型”的状态，提升到更接近商业 IM 的交互水位：补齐多行输入与键盘体验、补清发送/上传失败反馈与重试、让消息状态更可读，并修复发送前附件无法删除的明显缺陷。

## 已知问题
1. 用户已明确反馈：通过 `+` 添加的附件，发送前无法删除/撤销。
2. 当前 composer 仍是单行输入框，多行输入与换行体验不足。
3. 发送失败/上传失败虽然能露出错误，但反馈与下一步动作不够明确。
4. 消息 `delivery_status` 直接显示原始枚举，用户心智成本偏高。

## Scope
- 修复 pending attachment 可删除/撤销。
- 将 composer 升级为更适合 IM 的多行输入与键盘交互。
- 增强上传失败、发送失败、重试路径与 composer 状态提示。
- 提升消息状态文案可读性，不改后端协议。
- 补充针对 attachment removal 与关键 composer/status feedback 的前端测试。
- 记录 Roadpoints、验证命令、结果与 commits 到 `PROGRESS`。

## 非目标
- 不改 IM 后端消息协议或上传协议。
- 不扩展新的聊天业务流程。
- 不修改 `data/dev-tasks.json`。
- 不做与 composer/status UX 无关的大规模视觉重写。

## Roadpoints

### R1 用测试固定“附件可删除 + 多行输入”交互
- Acceptance:
  - 用户在发送前可以明确删除已添加附件。
  - composer 支持多行输入，`Shift+Enter` 可换行，`Enter` 可直接发送。
- Tests Plan:
  - `message-pane.test.tsx` 新增 attachment removal 与 multiline keyboard 测试。
- DoD:
  - 测试先覆盖缺陷，再由实现通过。
- 状态: DONE

### R2 补齐上传失败/发送失败的可操作反馈
- Acceptance:
  - 上传失败会明确告诉用户发生了什么，并提供可操作下一步。
  - 发送失败保留草稿与附件，并允许直接重试。
- Tests Plan:
  - `message-pane.test.tsx` 新增 upload failure / retry 与 send retry feedback 断言。
- DoD:
  - 失败路径可恢复，不需要用户重新拼装整个草稿。
- 状态: DONE

### R3 提升消息状态可读性
- Acceptance:
  - 消息状态不再直接裸露 `sent/running/completed/failed` 枚举，而是更清晰的用户向标签。
- Tests Plan:
  - `message-pane.test.tsx` 为不同 message status 补渲染断言。
- DoD:
  - 关键状态一眼可读，且不破坏现有消息链路。
- 状态: DONE

### R4 定向验证与交付记录
- Acceptance:
  - 运行与本次改动直接相关的前端测试与 build。
  - `PROGRESS` 记录命令、结果、Roadpoints 与最终 commit。
- Tests Plan:
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M154/src/IM/frontend" test -- --run src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts`
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M154/src/IM/frontend" run build`
- DoD:
  - 工作树清洁，可进入合并审查。
- 状态: DONE

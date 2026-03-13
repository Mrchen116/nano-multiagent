# M152 Tasks - Group chat mention picker UX

- Milestone: M152
- Title: Group chat mention picker UX
- Goal: 让群聊用户在 Web IM 输入框中通过键盘驱动的候选菜单选择 agent mention，并插入稳定可路由的 `@agent:<id>` 形式，而无需手打完整 agent id。
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M152`
- branch: `milestone/M152`
- test_command: `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M152/src/IM/frontend test -- /Users/czj/Repos/nano-multiagent/.worktrees/M152/src/IM/frontend/src/features/chat/components/message-pane.test.tsx /Users/czj/Repos/nano-multiagent/.worktrees/M152/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- allowed_scope:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M152/src/IM/frontend/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M152/TASKS/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M152/PROGRESS/**`
- forbidden_scope:
  - `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
  - 新建额外 worktree
  - 与 mention picker 无关的后端 / gateway / docs 大范围改动
- prevention_rules:
  - 只在群聊 composer 打开 mention 候选；直聊输入框不能误弹。
  - mention 插入值必须是稳定可路由的 `@agent:<id>`，不能只写展示名。
  - 候选来源必须来自群聊中的 agent 参与者，不能把普通用户混入菜单。
  - 键盘路径必须覆盖 `ArrowUp/ArrowDown/Enter`，避免只测鼠标 happy path。
  - 本次续跑不重做已存在实现；若回归测试已绿，则只补齐文档与交接证据。
- dev_tasks_path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`

## R1 验证群聊 mention picker 主链路
- Status: DONE
- Acceptance:
  - 群聊输入 `@` 或 `@query` 时出现候选列表。
  - 候选只包含 agent 参与者，并显示人类可读 label。
  - 键盘选择后插入 `@agent:<id> `，发送请求带稳定 mention 字符串。
  - 直聊 composer 即使存在 `mention_candidates` 也不会弹出候选菜单。
- Tests Plan:
  - component: 复用 `message-pane.test.tsx` 验证群聊/直聊、键盘选择、发送载荷。
  - integration-ish frontend: 复用 `chat-workspace-page.test.ts` 验证工作区详情会暴露群聊 mention candidates。
  - e2e: 本 milestone 不新增真实浏览器门禁；由后续整体验收覆盖。
- Evidence:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M152/src/IM/frontend test -- /Users/czj/Repos/nano-multiagent/.worktrees/M152/src/IM/frontend/src/features/chat/components/message-pane.test.tsx /Users/czj/Repos/nano-multiagent/.worktrees/M152/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` -> `2 passed (20 tests)`
- DoD:
  - mention menu 仅在群聊打开。
  - 稳定 mention 发送值为 `@agent:<id>`。
  - 相关前端回归测试全绿。

## R2 补齐 milestone 文档与 merge-ready 交接
- Status: DONE
- Acceptance:
  - 新增 `TASKS/M152-group-chat-mention-picker-ux.md`。
  - 新增 `PROGRESS/M152-group-chat-mention-picker-ux.md`。
  - 文档记录 inherited code commit、复跑测试命令、当前 merge-ready 判断。
  - 续跑结束后分支保持干净，无额外未提交文件。
- Tests Plan:
  - verification: 复用 R1 已跑测试，不额外扩大门禁。
  - git hygiene: 提交后 `git status --short --branch` 应为空工作树。
- Evidence:
  - 继承实现提交：`2667bfdc1688846d54457c7370cc2108fa0a420a`
  - 文档提交：待本次文档 commit 生成后回填到 `PROGRESS`。
- DoD:
  - 文档诚实记录“本次续跑只补文档与复验”。
  - 给出 merge-ready / non-merge-ready 结论与依据。
  - 分支 clean。

## Commit Plan / Result
- Inherited implementation: `2667bfdc1688846d54457c7370cc2108fa0a420a` `feat(M152): add group chat mention picker UX`
- Follow-up docs commit: this docs commit（最终 hash 见 git 历史与交接报告）

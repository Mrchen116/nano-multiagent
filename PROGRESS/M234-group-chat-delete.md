# M234 Progress: 群聊删除

## Plan Commit
- Branch: milestone/M234
- Worktree: /Users/czj/Repos/nano-multiagent/.worktrees/M234

---

## R1 后端：creator_id 迁移 + 解散/退出 API

- Context: conversations 表无 creator_id，无删除接口。需 migration + 2 个新 HTTP 端点。
- Decision: 见实现后填写
- Rationale: 见实现后填写
- Evidence:
  - Tests: 待跑
  - Entry: 待验证
- Rollback: plan commit
- Commits: C1=?, C2=?, C3=?
- Next: R2 前端

---

## R2 前端：退出/解散操作入口

- Context: 无退出/解散 UI 入口
- Decision: 见实现后填写
- Rationale: 见实现后填写
- Evidence:
  - Tests: 待跑
  - Entry: npm run build 成功
- Rollback: R1 C3
- Commits: C1=?, C2=?, C3=?
- Next: 合并到 main

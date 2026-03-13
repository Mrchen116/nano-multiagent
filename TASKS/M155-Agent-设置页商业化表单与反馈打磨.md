# M155 - Agent 设置页商业化表单与反馈打磨

**Goal**: 打磨 Agent 列表 / 创建 / 编辑体验，让设置中心具备商业产品级的 loading、校验、错误反馈、节点可见性与保存反馈，同时不破坏现有创建编辑链路。

**Scope Guard**:
- 仅修改 `/Users/czj/Repos/nano-multiagent/.worktrees/M155` 中的 M155 工作树内容。
- 不修改 `data/dev-tasks.json`。
- 聚焦 `src/IM/frontend/src/features/settings/agents/*` 与对应前端测试。

**Planned Verification Commands**:
- `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M155/src/IM/frontend" run test -- src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agents-list-mobile.test.tsx`
- `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M155/src/IM/frontend" run build`

---

## Roadpoints

### R155.1 Agent 列表状态与空态打磨
**Status**: DONE

**Acceptance**:
1. 列表页具备更清晰的 loading / empty / error / retry 反馈。
2. 列表项补充关键信息，便于 PM 复验 Agent 状态与配置概览。
3. 前端测试覆盖移动端展示与关键异常态。

### R155.2 Agent 创建表单校验与节点可见性打磨
**Status**: TODO

**Acceptance**:
1. 创建表单补齐必填校验、错误提示、提交中反馈。
2. 节点选择区能看见节点状态与绑定上下文，节点失败/空态有解释。
3. 不影响创建成功后跳转链路。
4. 前端测试覆盖创建成功、校验阻断、错误反馈等关键状态。

### R155.3 Agent 编辑保存反馈与配置可理解性打磨
**Status**: TODO

**Acceptance**:
1. 编辑页补齐加载失败、校验、dirty/save/saved/error 反馈。
2. 已绑定节点与版本/更新时间等状态更可见。
3. 不影响现有保存与版本冲突链路。
4. 前端测试覆盖保存成功、冲突错误、校验阻断等关键状态。

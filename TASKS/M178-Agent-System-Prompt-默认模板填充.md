# M178 Agent System Prompt 默认模板填充

## 前置确认
- 已阅读并对照当前 Agent 配置前端实现与相关测试：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
- `data/dev-tasks.json` 已确认在 worktree 内为指向主仓同一份文件的 symlink。
- 本里程碑只收口 M178：Agent 配置页 System Prompt 默认模板填充，不修改其他 milestone，不改 `data/dev-tasks.json` 状态。

## 当前处境
- milestone: `M178`
- branch: `milestone/M178`
- worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M178`
- 目标：为新建 Agent 的 System Prompt 提供标准默认模板；编辑已有 Agent 时保留已有值；允许用户在模板基础上修改并保存。

## Roadpoints

### R1 创建页默认模板
- Status: DONE
- Acceptance:
  - 新建 Agent 时 `System Prompt` 文本域自动带出标准模板。
  - 模板覆盖角色、目标、约束、响应风格，且仍允许用户直接修改。
  - 帮助文案明确说明这是可编辑的预填模板。
- Evidence:
  - 代码：`/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - 测试：`agent-create.test.tsx` 断言默认值已自动填充。

### R2 编辑页保持已有值
- Status: DONE
- Acceptance:
  - 编辑已有 Agent 时继续显示后端返回的 `system_prompt`，不被默认模板覆盖。
  - 原有保存链路保持不变。
- Evidence:
  - 代码：`/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - 测试：`agent-edit.test.tsx` 断言编辑页加载现有 prompt 值。

### R3 可修改并保存 + 验证
- Status: DONE
- Acceptance:
  - 用户可以清空预填模板并输入自定义 prompt 后成功创建。
  - 编辑已有 Agent 的保存请求继续携带用户当前的 `system_prompt`。
  - 产出测试证据。
- Evidence:
  - 测试：`agent-create.test.tsx` 覆盖清空模板后输入自定义 prompt 并提交。
  - 测试：`agent-edit.test.tsx` 覆盖保存请求仍发送当前已有 prompt。

## 收尾
- Status: DONE
- 里程碑实现提交：`c8c0ee4528da03e72caa0a0f30670992a78a003d`
- 里程碑记录提交：`ecfa6abd1129855faaab14a36edc8fc69d147a19`
- 备注：`data/dev-tasks.json` 按要求未由本 worker 修改状态。
- merge / push / worktree 清理结果以本次执行完成报告为准。

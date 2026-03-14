# M178 Agent System Prompt 默认模板填充

## 实施记录

### R1 新建 Agent 默认模板
- Context: 当前创建页把 `system_prompt` 初始值设为空字符串，用户必须从零开始填写，不符合“预填可编辑标准模板”的 UX 要求。
- Decision: 在创建页定义 `DEFAULT_AGENT_SYSTEM_PROMPT` 常量，并把 `EMPTY_DRAFT.system_prompt` 改为该模板。
- Rationale: 模板在最靠近表单的地方声明，能直接驱动 UI 默认值，同时不影响后端契约和编辑页取值逻辑。
- Evidence:
  - 文件：`/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - 关键点：默认模板包含 Role / Goals / Guardrails / Response style 四段，适合作为业务 Agent 的可编辑起点。

### R2 帮助文案与交互预期
- Context: 原帮助文案只说明 System Prompt 是行为契约，没有告诉用户系统会先填模板。
- Decision: 把创建页帮助文案改为显式说明“系统会预填标准模板，用户应在保存前按该 Agent 场景修改”。
- Rationale: 减少用户误解，以为系统是在展示一个不可修改示例文本。
- Evidence:
  - 文件：`/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`

### R3 测试收口
- Context: 既要证明创建页默认带出模板，也要证明编辑已有 Agent 时仍保留已有值，且用户可覆盖模板后成功保存。
- Decision:
  - 扩展 `agent-create.test.tsx`：断言默认模板出现；创建场景先清空模板再输入自定义 prompt；校验 required 校验仍成立。
  - 扩展 `agent-edit.test.tsx`：断言编辑页加载的是已有 `system_prompt` 值。
- Rationale: 覆盖 M178 三个核心验收点：默认填充、编辑保留、可修改保存。
- Evidence:
  - 文件：
    - `/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
    - `/Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`

## 验证
- 依赖安装：`npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend ci`
- 定向测试：`npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M178/src/IM/frontend test -- src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agent-detail-page.test.tsx`
- 结果：`3 passed (3), 7 passed (7)`

## 结果
- 新建 Agent：System Prompt 会自动填入标准模板。
- 编辑已有 Agent：继续显示并保留已有值，不会被默认模板覆盖。
- 用户可覆盖模板并提交，现有创建/保存链路维持可用。

## 收口状态
- 实现提交：`c8c0ee4528da03e72caa0a0f30670992a78a003d`
- main merge：`a8fb6c7`
- push：已完成
- milestone worktree：已清理

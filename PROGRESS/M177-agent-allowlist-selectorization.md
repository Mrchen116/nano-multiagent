# M177 - Agent 配置 Allowlist 选择器化

## Summary
- 已完成 M177 核心实现：新增 allowlist options API，Agent 创建页与详情页均改为选择式 Skills/Tools Allowlist，并保持创建、回显、编辑、保存链路兼容既有后端 `string[]` 契约。
- 已补齐前后端测试与前端构建验证；当前 worktree 仅剩提交、合并 main、清理 worktree。

## Evidence log
- 2026-03-14：复核核心文件并确认实现位置：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/allowlist-selector.tsx`
- 2026-03-14：后端新增 `/im/v1/agents/allowlist-options`，将运行中系统可用 skills / tools 以 `[{name, description}]` 形式暴露给设置页，文件：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/api/routes/agents.py`
- 2026-03-14：创建页与详情页 allowlist 交互改为选择器，提交 payload 仍为 `skills: string[]`、`tool_allowlist: string[]`；编辑页对“已保存但当前系统不可用”的旧值显示 `Unavailable now` 兼容标签，文件：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/allowlist-selector.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
- 2026-03-14：补齐/更新前后端测试：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/tests/im_service/contract/test_agent_config_contract.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M177/tests/im_service/integration/test_agent_config_api.py`
- 2026-03-14：自动化验证通过：
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend" test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx`
    - 结果：3 files, 7 tests passed
  - `python -m pytest "/Users/czj/Repos/nano-multiagent/.worktrees/M177/tests/im_service/contract/test_agent_config_contract.py" "/Users/czj/Repos/nano-multiagent/.worktrees/M177/tests/im_service/integration/test_agent_config_api.py"`
    - 结果：5 passed
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/.worktrees/M177/src/IM/frontend" run build`
    - 结果：build 成功，生成更新后的 dist 资产

## Notes
- 本轮未在 CLI 内补做浏览器真机录屏/截图，因为当前可用工具集中不含浏览器交互能力；已以真实前端构建 + 前后端接口/页面测试作为可复现证据保底。
- 若后续在具备浏览器工具的验收线程继续，可优先复用本 worktree 的 allowlist options API 与选择器 UI，不需要再改后端契约。

## Next
- 提交 M177 改动。
- 合并 `milestone/M177` 到 `main`。
- 删除 `/Users/czj/Repos/nano-multiagent/.worktrees/M177` worktree。

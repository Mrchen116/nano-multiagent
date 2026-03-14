# M181 - 修复 Agent 创建页默认项与 Allowlist 产品问题

## Summary
- 已完成 M181：统一修复 New Agent 页面四个相关产品问题，包含 skills allowlist 空白、tool allowlist 文案过长、system prompt 未预填、默认模型可输入不存在值。
- 方案从根因入手：后端 allowlist options API 现在同时暴露实时 skills / tools / model options / platform default model / product-owned default system prompt；前端创建页与详情页统一消费该契约。
- `personal_assistant` 产品配置已兼容当前环境 skill roots，因此运行中 IM API 和真实页面都能看到可选 skills；Tool Allowlist 主列表改为简洁可扫描；Default Model 改为仅允许当前有效模型的选择器。

## Evidence log
- 2026-03-14：完成后端根因修复与契约扩展，相关文件：
  - `/Users/czj/Repos/nano-multiagent/src/agent/products/personal_assistant/defaults.py`
  - `/Users/czj/Repos/nano-multiagent/src/IM/api/routes/agents.py`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts`
- 2026-03-14：完成前端创建页/详情页/选择器收口，相关文件：
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/allowlist-selector.tsx`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
- 2026-03-14：补齐前后端测试，相关文件：
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/tests/unit/test_personal_assistant_profile.py`
  - `/Users/czj/Repos/nano-multiagent/tests/im_service/contract/test_agent_config_contract.py`
  - `/Users/czj/Repos/nano-multiagent/tests/im_service/integration/test_agent_config_api.py`
- 2026-03-14：自动化验证通过：
  - `python -m pytest "/Users/czj/Repos/nano-multiagent/tests/unit/test_personal_assistant_profile.py" "/Users/czj/Repos/nano-multiagent/tests/im_service/contract/test_agent_config_contract.py" "/Users/czj/Repos/nano-multiagent/tests/im_service/integration/test_agent_config_api.py"`
    - 结果：22 passed
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/src/IM/frontend" test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx`
    - 结果：3 files, 7 tests passed
  - `npm --prefix "/Users/czj/Repos/nano-multiagent/src/IM/frontend" run build`
    - 结果：build 成功，dist 已更新
- 2026-03-14：真实 IM API 核对通过：
  - `GET http://127.0.0.1:8011/im/v1/agents/allowlist-options`
  - 结果摘要：`skills_count=8`、`tools_count=6`、`model_options=["codexOAuth:gpt-5.2-codex"]`、`platform_default_model="codexOAuth:gpt-5.2-codex"`，且 `default_system_prompt` 返回 `personal_assistant` 模板文本。
- 2026-03-14：真实浏览器核对 New Agent 页面通过：
  - 页面：`http://127.0.0.1:8011/settings/agents/new`
  - 快照：`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-afaa7ec1/.playwright-cli/page-2026-03-14T16-20-48-616Z.yml`
  - 截图：`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-afaa7ec1/.playwright-cli/page-2026-03-14T16-21-01-886Z.png`
  - 核对点：
    - Skills Allowlist 已显示可选项，不再空白。
    - Tool Allowlist 主列表仅显示 `bash/edit/read/send_message/task/write` 等短名称，已可快速扫描。
    - System Prompt 已预填 `You are a helpful personal assistant...`。
    - Default Model 已改为下拉选择，显示 `Platform default (codexOAuth:gpt-5.2-codex)`，不再允许默认到不存在模型。

## Completion
- 2026-03-14：M181 已完成，待记录最终提交 hash 与 push 结果。

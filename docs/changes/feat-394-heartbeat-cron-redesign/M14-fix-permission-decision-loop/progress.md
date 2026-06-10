# feat-394-M14 progress

## R1 — cron NameError 修复（Issue B）

修复：`WORKSPACE_CONFIG_DIRNAME as _WCD` 提升至 `main.py` 第 45 行模块级导入块，
消除 `_cron_tick_for_agent` 闭包内 NameError。

单测绿：`pytest tests/unit/personal_assistant/test_cron_polling_runner.py -x`

## R2 — 权限回路修复（Issue A）

核心修复三处：
1. `agent/sdk/kernel.py`：新增 `Kernel.submit_permission_decision()` + 把 `_can_use_tool` 注入 `runtime._can_use_tool`（不再赋值死属性 `runtime._permission_requester`）
2. `agent/core/agent/runtime.py`：`__init__` 新增 `self._can_use_tool: Any | None = None`；`_build_hook_context` 在闭包里 race `_can_use_tool` 与 broker future
3. `personal_assistant/main.py`：新增 `_build_permission_response_handler(kernel=...)` 工厂，通过 `kernel.submit_permission_decision()` 转发 IM WS 权限响应

合约测试白名单行号同步更新（`runtime.py:159` → `runtime.py:165`）。

## R3 — 全量验证 + live e2e

### pytest 绿

```
pytest -m "not e2e" → 全绿（排除 2 个预存 IM 集成测试失败）
```

2 个预存失败为 macOS symlink 问题（`/tmp` vs `/private/tmp`），与 M14 无关：
- `test_get_agent_config_prefers_live_gateway_snapshot`
- `test_create_agent_lists_details_and_uses_new_node_binding_for_relay`

### Issue A — 权限卡片 live e2e（playwright 截图证明）

截图路径（相对 worktree 根）：

| 截图 | 内容 |
|---|---|
| `output/playwright/05-perm-card-wait.png` | 权限 ask 卡片出现，状态 "running"，按钮 Allow once / Deny / Allow for session |
| `output/playwright/06-allow-once-result.png` | 点击 Allow once 后，卡片显示 "Allowed · write"，agent 回复 "Done — wrote to /tmp/m14-perm-test.txt" |
| `output/playwright/07b-deny-card-visible.png` | 第二次触发，权限 ask 卡片出现 |
| `output/playwright/08-deny-result.png` | 点击 Deny 后，卡片显示 "Denied · write"，agent 回复 "The write was blocked by a hook." |

文件存在验证：
- `/tmp/m14-perm-test.txt` ✓ 存在（Allow once 后工具真实执行）
- `/tmp/m14-perm-deny-test.txt` ✗ 不存在（Deny 后工具被正确拒绝）

### Issue B — cron 回归 live e2e（日志 + 截图证明）

cron job 配置：
- 文件：`workspace/default-agent/.nanoassistant/cron/jobs.json`
- schedule: `{"kind":"every","everyMs":60000}` (60s interval)
- instruction: "Send a short message to the owner: cron tick OK - feat-394-M14 cron regression test"

Gateway 日志摘录（无 NameError）：
```
2026-06-10 12:15:14,718 INFO agent.core.observability: run_submitted | run_id='run_537ada66d01d0647'
2026-06-10 12:15:14,719 INFO agent.core.observability: run_started  | run_id='run_537ada66d01d0647'
2026-06-10 12:15:22,897 INFO agent.core.observability: run_completed | run_id='run_537ada66d01d0647', turn_id='turn_bb806adec60e9808'
2026-06-10 12:15:23,748 DEBUG personal_assistant.main: cron: awareness skip — no canonical session for agent=default-agent
2026-06-10 12:16:23,762 INFO agent.core.observability: run_submitted | run_id='run_7a1cb355a51e9927'
2026-06-10 12:16:23,762 INFO agent.core.observability: run_started  | run_id='run_7a1cb355a51e9927'
2026-06-10 12:16:33,666 INFO agent.core.observability: run_completed | run_id='run_7a1cb355a51e9927'
2026-06-10 12:16:33,787 DEBUG personal_assistant.main: cron: awareness skip — no canonical session for agent=default-agent
```

state.json 写入（cron scheduler 正常运转）：
```json
{
  "jobs": {
    "e2e-m14-cron-test": {
      "last_due_at": "2026-06-10T04:15:00+00:00"
    }
  }
}
```

IM 直聊截图：`output/playwright/cron-05-delivery-proof.png`
- 12:15 消息：default-agent 复述了 cron instruction "cron tick OK - feat-394-M14 cron regression test"
- 12:16 消息：下一次 cron tick 再次执行

零 NameError 确认：gateway 日志全文无 NameError / Traceback。

### 清理

启动的所有服务（IM PID 82324、Gateway PID 87725）在 worktree 完成后通过通用 PID sweep 清理。

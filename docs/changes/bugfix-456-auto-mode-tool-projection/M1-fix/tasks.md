# bugfix-456-M1: Auto mode tool projection — Tasks

> 对齐: `../fix.md` lite bugfix

## 目标

Auto mode classifier 的当前动作投影改为来自工具实例协议或注册期 wrapper 的结构化 projection；删除中央 `TOOL_PROJECTIONS` 兜底，避免当前非 safe 工具无投影时被历史危险动作串台误判。

## 退出标准

- [ ] `auto_mode_gate` 不再暴露或使用 `TOOL_PROJECTIONS` / `project_tool_input`。
- [ ] 非 safe 工具的 classifier 当前动作来自 tool 实例 `to_auto_classifier_input()`。
- [ ] 找不到 tool 或非 safe tool 缺 projection 时 fail-closed ask，不调用 classifier 处理空当前 action。
- [ ] dynamic/user tool 缺专用 projection 时由注册期 wrapper 补 `{tool, input}` 结构化 projection。
- [ ] safe allowlist 只包含 `read`、`web_search`、`skill_view`、`task_stop`、`agent`、`send_message`、`memory`。
- [ ] `web_fetch` 不进 safe，继续保留 `WebFetchTool.check_permissions` host 权限表 / ask fallback 语义。
- [ ] `skill_manage create/edit/patch/write_file/remove_file` 能投影当前 action；`skill_manage list`、`cron list/runs` 可由工具级 `check_permissions` 放行。
- [ ] `fix.md` 的“修复”和“验证”两段已回填。

## 测试策略

- 被测行为（来自退出标准）：projection 单一来源、unknown/missing projection fail-closed、dynamic wrapper 通用 projection、safe allowlist 精确集合、`skill_manage` / `cron` action 级 fast path、`web_fetch` 非 safe 且保留工具级权限语义。
- 已有测试在：`tests/unit/test_auto_mode_gate.py`、`tests/unit/test_auto_mode_gate_hook.py`、`tests/unit/test_auto_mode_gate_allowlist.py`、`tests/unit/test_auto_mode_gate_dispatch.py`、`tests/unit/test_skill_manage_tool.py`、`tests/unit/personal_assistant/test_cron_tool_permissions.py`、`tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py`（扩展）。
- 落层/目录/marker：`tests/unit/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真实入口验收命令输出记录到 `progress.md`；不新增一次性脚本。

前端 UI：N/A。

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 工具协议 projection 与权限 gate 修复

- 状态: DOING
- 步骤:
  - 写红测复现 `skill_manage create` 当前 action 空投影串台、unknown/missing projection fail-closed、dynamic wrapper 通用 projection、allowlist 精确集合和 action fast path。
  - 在工具协议上加入 `to_auto_classifier_input()`，让 built-in tools 和 wrapper 提供 projection。
  - 修改 `auto_mode_gate` 从 tool instance 取 projection，删除中央 projection 机制。
  - 回填 `fix.md` 修复/验证段。
- 验证:
  - 窄测：相关 auto-mode / tool 权限单测。
  - 广测：`pytest -m "not e2e"`。
  - 真实入口：通过 gate hook 模拟真实 tool_call 入口，确认 classifier prompt 当前 action 包含 `skill_manage create`，且不出现上一条 `bash rm -rf` 串台。

# PROGRESS/M76 多产品架构重构三期：抽出 local_coding 产品默认能力

## 概述
把 coding prompt、默认 tools/hooks 从共享层（agent/prompting.py）抽离到 local_coding 产品定义中，共享层持通用空 fallback，local_coding 产品定义持完整 coding 文案与工具/hook 列表。

---

### R76.1 中和 DEFAULT_SYSTEM_PROMPT，将 coding prompt 迁至 local_coding

- Context: `DEFAULT_SYSTEM_PROMPT` 在 `agent/prompting.py` 是 coding 专属文案；`LOCAL_CODING_PROFILE.default_system_prompt` 从它导入；`loop.py` 以它为默认参数。目标：prompting.py 持通用 fallback，coding 文案迁到 local_coding.py 的 `CODING_SYSTEM_PROMPT`。同时把 `AgentRuntime.system_prompt` 注入接口一并引入（原 R76.3 工作提前）。
- Decision: 在 `agent/prompting.py` 中把原 coding 文案重命名为 `CODING_SYSTEM_PROMPT`，`DEFAULT_SYSTEM_PROMPT = ""` 作为 backward-compat alias；`local_coding.py` 改为从 `CODING_SYSTEM_PROMPT` 导入；`loop.py` 默认参数改为空字符串（`""`）；`bootstrap.py` 移除对 `DEFAULT_SYSTEM_PROMPT` 的 fallback；`AgentRuntime.__init__` 增加 `system_prompt: str | None` 参数；受影响测试均显式传 `CODING_SYSTEM_PROMPT`。
- Rationale: 保留 `DEFAULT_SYSTEM_PROMPT` 名称（值改为 `""`）不破坏任何已知 import；AgentRuntime 注入接口提前做让现有测试可稳定通过，避免分阶段拆出造成多轮回归。
- Evidence:
  - Tests: pytest -q → 514 passed，5 pre-existing failures（基线 +2，全绿）
  - Entry: `from nano_multiagent.agent.prompting import CODING_SYSTEM_PROMPT` 可导入，值含 coding 专属文案
- Rollback: 回退到 eedc948（计划提交）
- Commits: C1=0b9cb69, C2=b271e4e, C3=
- Next: R76.2

---

### R76.2 local_coding 明确列出 default_tool_ids 与 default_hook_modules

- Context: `LOCAL_CODING_PROFILE.default_tool_ids=None` 表示"用所有内置"；M76 要求显式列出，让 bootstrap 可按 profile 过滤。`bootstrap.py` 当前忽略这两个字段。4 个内置 hook 模块路径从 hooks/builtins/*.py 文件名确认。
- Decision: `default_tool_ids=["read", "write", "edit", "bash", "task"]`；`default_hook_modules=["bash_risk_gate", "default_status", "realtime_stream", "usage_metrics"]`（模块文件名 stem）。`bootstrap.py` 增加 `_filter_tool_registry` 和 `_filter_hook_registry` helper；当字段非 None 时按声明过滤；ToolRegistry 通过访问 `_tools` dict 重建，HookRegistry 通过 `all_handlers()` + `file_path.stem` 过滤重建。
- Rationale: 显式优于隐式；当前声明的 5 个 tool + 4 个 hook 等同于现有"全部内置"行为，但现在可审计。未来产品可声明子集。
- Evidence:
  - Tests: pytest -q → 518 passed，5 pre-existing failures（基线 +4）
  - Entry: `LOCAL_CODING_PROFILE.default_tool_ids` == `["read","write","edit","bash","task"]`
- Rollback: 回退到 R76.1 C3（c4060c6）
- Commits: C1=f499448, C2=21e4f8b, C3=
- Next: R76.3

---

### R76.3 server/app.py 通过 ResolvedProductConfig 注入 system_prompt

- Context: `create_app(product_profile=...)` 当前只用 bootstrap 的 tool/hook registry，没有把 `resolved_system_prompt` 传给 `AgentRuntime`/`AgentLoop`。`AgentRuntime.system_prompt` 参数已在 R76.1 引入。
- Decision: `create_app` 当 `product_profile` 非 None 且 `resolved_product.resolved_system_prompt` 非空时，通过 `**runtime_kwargs` 把它传给 `AgentRuntime`；无 profile 时行为不变（AgentRuntime 使用空字符串 fallback）。
- Rationale: 最小侵入；`resolved_system_prompt=""` 时不传（不覆盖 runtime 默认），非空时传入，保证"explicit > profile > default"链路。
- Evidence:
  - Tests: pytest -q → 520 passed，5 pre-existing failures（基线 +2）
  - Entry: `create_app(product_profile=LOCAL_CODING_PROFILE)` 后，`app.state.agent_runtime._loop._system_prompt == CODING_SYSTEM_PROMPT`
- Rollback: 回退到 R76.2 C3（9661a37）
- Commits: C1=32d05f7, C2=b654c52, C3=
- Next: Milestone 完成，合并到 main

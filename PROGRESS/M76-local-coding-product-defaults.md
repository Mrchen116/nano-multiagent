# PROGRESS/M76 多产品架构重构三期：抽出 local_coding 产品默认能力

## 概述
把 coding prompt、默认 tools/hooks 从共享层（agent/prompting.py）抽离到 local_coding 产品定义中，共享层持通用空 fallback，local_coding 产品定义持完整 coding 文案与工具/hook 列表。

---

### R76.1 中和 DEFAULT_SYSTEM_PROMPT，将 coding prompt 迁至 local_coding

- Context: `DEFAULT_SYSTEM_PROMPT` 在 `agent/prompting.py` 是 coding 专属文案；`LOCAL_CODING_PROFILE.default_system_prompt` 从它导入；`loop.py` 以它为默认参数。目标：prompting.py 持通用 fallback，coding 文案迁到 local_coding.py 的 `CODING_SYSTEM_PROMPT`。不做 loop/runtime 的 system_prompt 注入（R76.3 做）。
- Decision: 在 `agent/prompting.py` 中把原 coding 文案重命名为 `CODING_SYSTEM_PROMPT`，`DEFAULT_SYSTEM_PROMPT = ""` 作为 backward-compat alias；`local_coding.py` 改为从 `CODING_SYSTEM_PROMPT` 导入；`loop.py` 默认参数改为空字符串（`""`）；更新受影响的测试（test_local_coding_profile_system_prompt_matches_default 改为断言 CODING_SYSTEM_PROMPT）。
- Rationale: 保留 `DEFAULT_SYSTEM_PROMPT` 名称（值改为 `""`）可以不破坏任何已知 import；coding 文案迁至 `CODING_SYSTEM_PROMPT` 让 shared 层语义清晰。
- Evidence:
  - Tests: pytest -q → 512 passed（基线维持）
  - Entry: `from nano_multiagent.agent.prompting import CODING_SYSTEM_PROMPT` 可导入，值含 coding 专属文案
- Rollback: 回退到计划提交
- Commits: C1=, C2=, C3=
- Next: R76.2

---

### R76.2 local_coding 明确列出 default_tool_ids 与 default_hook_modules

- Context: `LOCAL_CODING_PROFILE.default_tool_ids=None` 表示"用所有内置"；M76 要求显式列出，让 bootstrap 可按 profile 过滤。`bootstrap.py` 当前忽略这两个字段。4 个内置 hook 模块路径需要从代码中确认。
- Decision: 将 `default_tool_ids=["read", "write", "edit", "bash", "task"]`；`default_hook_modules` 列出 4 个内置 hook 模块的 Python 模块路径；`bootstrap.py` 增加：当 `default_tool_ids` 非 None 时只注册指定 ids，当 `default_hook_modules` 非 None 时按模块名过滤（或直接利用 build_hook_registry 现有机制）。
- Rationale: 显式优于隐式；列出全部内置等同于当前行为，但变成可审计的声明式配置。
- Evidence:
  - Tests: pytest -q → 512 passed
  - Entry: `LOCAL_CODING_PROFILE.default_tool_ids` 非 None，含 5 个 id
- Rollback: 回退到 R76.1 C3
- Commits: C1=, C2=, C3=
- Next: R76.3

---

### R76.3 server/app.py 通过 ResolvedProductConfig 注入 system_prompt

- Context: `create_app(product_profile=...)` 当前只用 bootstrap 的 tool/hook registry，没有把 `resolved_system_prompt` 传给 `AgentRuntime`/`AgentLoop`。目标：profile 激活后 runtime 使用 profile 的 prompt，无 profile 时保持现有行为。
- Decision: `AgentRuntime.__init__` 增加 `system_prompt: str | None = None` 参数，传给 `AgentLoop`；`create_app` 当 product_profile 非 None 时，把 `resolved_product.resolved_system_prompt` 传给 `AgentRuntime`。
- Rationale: 最小侵入：runtime 接受 system_prompt 参数，loop 使用注入值；loop.py 默认空字符串兜底，不再持有 coding 专属文案。
- Evidence:
  - Tests: pytest -q → 512 passed
  - Entry: `create_app(product_profile=LOCAL_CODING_PROFILE)` 后，runtime loop 使用 coding prompt
- Rollback: 回退到 R76.2 C3
- Commits: C1=, C2=, C3=
- Next: Milestone 完成，合并到 main

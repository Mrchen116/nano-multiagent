# feat-383-M1 — Progress

## 澄清记录

无。派发包上下文锚点、design.md 关键决策已足够，无须额外澄清。按自底向上顺序推进：R1（kernel 端）→ R2（PA client + Gateway WS）→ R3（IM HTTP 路由）→ R4（前端）。

## R1 — kernel `/v1/prompt-preview` 真实化

- Context: 当前 kernel 端用 `SimpleNamespace(name=t, description="")` 构造工具 stub，导致预览里工具描述为空；datetime/cwd 也为空字符串，让用户以为预览就是空白。
- Decision: 扩展 `PromptPreviewRequest` 加 `workspace_root`/`skill_ids` 字段；`prompt_preview` 函数注入 `ToolRegistry`，用 `registry.get(tid)` 取真实工具（`None` 静默跳过）；用 `resolve_available_skills(workspace_root, include_names=skill_ids)` 解析 skills；`current_datetime` 固定为 `<运行时注入：当前时间>`；`cwd` 用 `workspace_root` 或 `<运行时注入：workspace 路径>`。
- Rationale: `skill_ids` 用空列表作为 `include_names` 参数，`resolve_available_skills` 返回空集合，不会意外扫描全局 skill 目录（与 `include_names=None` 语义不同）。静默跳过未注册工具镜像运行时行为。
- Evidence:
  - Tests: `pytest tests/unit/test_prompt_preview_endpoint.py tests/contract/test_prompt_preview_runtime_parity.py tests/integration/test_prompt_sections_golden.py` — 13+13+13=39 passed, 0 failed
  - Entry: N/A（HTTP 端测试覆盖，contract test 覆盖 HTTP → runtime 等价性）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `test_prompt_preview_runtime_parity.py` — 预览占位符替换后逐字等于 runtime 输出，通过
  - Visual/Interaction: N/A
- Rollback: `git revert ed3c9148`
- Commits: C1=0e5245ee, C2=ed3c9148, C3=（本次）

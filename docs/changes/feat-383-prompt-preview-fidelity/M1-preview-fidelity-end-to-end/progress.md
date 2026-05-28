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
- Commits: C1=0e5245ee, C2=ed3c9148, C3=512cc788
- Next: R2（PA client + Gateway WS 透传）

## R2 — kernel_api_client + Gateway WS 透传 workspace_root/skill_ids

- Context: kernel 已支持 workspace_root/skill_ids，但 PA 的 `kernel_api_client.prompt_preview()` 签名没有这两个参数，`im_connection.py` 里的 WS handler 也没有读取 `skill_ids`，Gateway `request_node_prompt_preview` 没有透传 `workspace_root`/`skill_ids`。
- Decision: 
  1. `PromptPreviewProvider` callable 签名加 `skill_ids` 参数（第 7 个）
  2. `im_connection.py` `agent.prompt.preview.request` handler 读取 `skill_ids` 并传给 provider
  3. `im_connection.py` `node.prompt.preview.request` handler 读取 `workspace_root`/`skill_ids` 并传给 provider
  4. `kernel_api_client.prompt_preview()` 加 `workspace_root`/`skill_ids` 参数
  5. `main.py` lambda 更新签名并透传两个新参数
  6. `gateway_handler.request_prompt_preview` 加 `skill_ids` 参数
  7. `gateway_handler.request_node_prompt_preview` 加 `workspace_root`/`skill_ids` 参数
- Rationale: 全链路透传，kernel 端已实现，这一步确保每一层都把用户配置的 skill_ids 和 workspace_root 向下传递。
- Evidence:
  - Tests: `pytest tests/unit/ tests/contract/ tests/integration/ -q` — 2139 passed, 0 failed
  - Entry: N/A（单元测试覆盖 WS handler 行为）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `test_gateway_im_connection_behavior.py` 新增 2 个测试，11 个全绿
  - Visual/Interaction: N/A
- Rollback: `git revert 737246c3`
- Commits: C1=0fbf0d23, C2=737246c3, C3=（本次）

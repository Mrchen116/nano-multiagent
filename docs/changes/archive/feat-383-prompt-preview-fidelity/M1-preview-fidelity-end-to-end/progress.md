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
- Commits: C1=0fbf0d23, C2=737246c3, C3=e8ed4c81
- Next: R3（IM HTTP 路由）

## R3 — IM HTTP 路由透传 skill_ids + node 端 derive workspace_root

- Context: PA client 和 Gateway WS 已经透传 workspace_root/skill_ids，但 IM HTTP 路由还没有：`/agents/{id}/prompt-preview` 不传 `skill_ids`，`/nodes/{id}/prompt-preview` 不传 `workspace_root`/`skill_ids`/`agent_id_hint`。
- Decision:
  1. `agents.py PromptPreviewRequest` 加 `skill_ids` 字段，`agent_prompt_preview` route 把它传给 `gateway_handler.request_prompt_preview`
  2. `nodes.py` 新增 `NodePromptPreviewRequest` 模型（`skill_ids` + `agent_id_hint`），`node_prompt_preview` route 用 `managed_workspace_root(agent_id_hint)` derive workspace_root 后传给 `gateway_handler.request_node_prompt_preview`
- Rationale: `managed_workspace_root` 是 IM 层的领域知识（decision 1），前端不应拼路径。`agent_id_hint` 字段在 IM 层吸收并转换，不进入 Gateway 协议。
- Evidence:
  - Tests: `pytest tests/im_service/ -q` — 261 passed, 0 failed
  - Entry: N/A（单元/contract 测试覆盖）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `test_agent_config_contract.py` 新增 3 个测试，全绿；既有 proxy test 更新 fake 签名
  - Visual/Interaction: N/A
- Rollback: `git revert 54448c44`
- Commits: C1=48273adb, C2=54448c44, C3=c8274c15
- Next: R4（前端）

## R4 — 前端 API 客户端 + 调用点补字段

- Context: 前端 `promptPreview`/`nodePromptPreview` 签名缺 `skill_ids`/`agent_id_hint`，`agent-detail-page` 和 `agent-create-page` 没有传这两个字段，全链路前半段断路。
- Decision:
  1. `im-agent-config-api.ts` `promptPreview` 加 `skill_ids`；`nodePromptPreview` 加 `skill_ids`/`agent_id_hint`
  2. `agent-detail-page.tsx` fetchPreview 加 `skill_ids: draft.skills`，依赖数组补 `draft.skills`
  3. `agent-create-page.tsx` fetchPreview 加 `skill_ids: draft.skills`/`agent_id_hint: draft.agent_id`，依赖数组补两个新依赖
- Rationale: `agent_id_hint` 未填时传 `undefined`（不传），IM 路由判空不 derive workspace，正确退化到占位符。
- Evidence:
  - Tests: `pytest -m 'not e2e' -q` — 2400 passed; frontend 2 test files — 18 passed
  - Entry: 全链路 e2e（修补 Gateway kernel URL 后）验证通过
  - Frontend State Matrix:
    - default (agent-detail): 工具未勾选→`(none)`，勾选 read→真实描述 ✓
    - datetime placeholder: `<运行时注入：当前时间>` ✓
    - cwd agent-detail: 真实路径 `/Users/czj/nano-assistant/workspace/default-agent` ✓
    - cwd agent-create 无 ID: `<运行时注入：workspace 路径>` ✓
    - cwd agent-create 有 ID: 真实路径 `/Users/czj/nano-assistant/workspace/test-preview-agent` ✓
  - Browser QA:
    - agent-detail: `http://127.0.0.1:54208/settings/agents/default-agent`，勾选 read，预览显示真实描述+占位符+真实 cwd
    - agent-create: `http://127.0.0.1:54208/settings/agents/new`，无 ID 看占位，填 ID 看真实 cwd
    - console errors: 无；network failures: 无
  - E2E/Regression: 前端 unit test 覆盖 skill_ids/agent_id_hint 透传；不适用独立 E2E 框架
  - Visual/Interaction:
    - `ACCEPTANCE/feat-383-r1-agent-detail-preview-1440.png`: `- read: Read the contents of a file...` (真实), datetime 占位, cwd 真实
    - `ACCEPTANCE/feat-383-r1-agent-create-preview-1440.png`: cwd `test-preview-agent`, datetime 占位
- Rollback: `git revert fc00feae`
- Commits: C1=d8dc82a4, C2=fc00feae, C3=（本次）

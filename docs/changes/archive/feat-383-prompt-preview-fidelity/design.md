# feat-383: 系统提示词预览反映 UI 实时配置 — 技术方案

> 对齐: spec.md v1
> Unit branch: `unit/feat-383` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

| 路径 | 当前职责 | 本 unit 改动 |
|---|---|---|
| `src/agent/platform/http_api/routes/global_routes.py` | 暴露 `/v1/prompt-preview`，构造 `PromptContext` → 调 `assemble_system_prompt(stable_sections, ctx)` | 扩展请求体（+ `workspace_root` / `skill_ids`），注入 `ToolRegistry` 取真实工具描述，解析真实 skills，注入占位符 |
| `src/agent/core/agent/prompt_sections/core_sections.py` | 渲染 Available Tools / Skills / runtime footer 等 section | **不改**，section 输出取决于 ctx，填真即真 |
| `src/agent/core/agent/prompting.py` | 运行时 `build_system_prompt`（`<RUNTIME_FILL:*>` 字符串模板） | **不改**，与预览的等价性由 golden test 守住 |
| `src/agent/core/skills/discovery.py` | `resolve_available_skills(workspace_root, include_names)` | 复用 |
| `src/agent/core/tools/registry.py` | `ToolRegistry.get(name) → Tool` | 复用 |
| `src/personal_assistant/client/kernel_api_client.py` | `prompt_preview()` 调 agent HTTP | 透传 `workspace_root` / `skill_ids` |
| `src/personal_assistant/main.py` | `prompt_preview_provider` lambda（当前 workspace_root 参数 `# noqa: ARG005`） | 让 lambda 真正传 workspace_root + skill_ids 到 kernel client |
| `src/personal_assistant/ws/im_connection.py` | 处理 `agent.prompt.preview.request` / `node.prompt.preview.request` | 提取 `skill_ids`（agent 路径已有 workspace_root） |
| `src/IM/ws/gateway_handler.py` | `request_prompt_preview` / `request_node_prompt_preview` 下行帧 | 扩展 payload（+ `skill_ids`；node 路径 + `workspace_root`） |
| `src/IM/api/routes/agents.py` | `/im/v1/agents/{id}/prompt-preview` | 扩展请求体（+ `skill_ids`），透传 |
| `src/IM/api/routes/nodes.py` | `/im/v1/nodes/{id}/prompt-preview` | 扩展请求体（+ `skill_ids` + `agent_id_hint`），IM 服务端用 `managed_workspace_root(agent_id_hint)` derive workspace_root 后再透传给 gateway |
| `src/IM/application/config_service.py` | `workspace_root_for_profile` 已存在；`managed_workspace_root` 在 `IM/domain/models.py` | 复用 |
| `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts` | `promptPreview()` / `nodePromptPreview()` 客户端 | 签名扩展（+ `skill_ids`；node 入口 + `agent_id_hint`） |
| `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx` | 已存在 agent 的预览调用 | 加 `skill_ids: draft.skills` |
| `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx` | 创建中 agent 的预览调用 | 加 `skill_ids: draft.skills` + `agent_id_hint: draft.agent_id` |

### 既有约束

来自 `AGENTS.md` / 项目分层规范：

- **依赖方向硬规则**：`coding_cli` / `personal_assistant` → `agent`（HTTP only，禁止直接 import）；IM 不直接调 agent，只与用户和 personal_assistant 交互；四个顶层包之间禁止相互 import。本 unit 不破坏这条——所有跨包调用走已有的 HTTP/WS 链路。
- **agent 内核三层**：`core`（纯逻辑）→ `platform`（接环境）→ `products`（装配）。`/v1/prompt-preview` 在 `platform/http_api`，可注入 `ToolRegistry`（platform 层资源）；skill 解析也在 platform 层完成（调用 core 的 resolver）。
- **预览的 cache-stable 不变量**（feat-379-M2 R5 决策 8）：预览只输出 `cache_safe=True` 段，volatile 段（memory_block, communication_context）不进。本 unit 保留这条。
- **预览与运行时等价性**（feat-379-M1 exit criteria）：`tests/integration/test_prompt_sections_golden.py` 强制 `assemble_system_prompt() ≡ build_system_prompt()` 在 6 个 canonical 场景下逐字相等。本 unit 不动这条等价性，新加守护"preview HTTP 端到 runtime 实际拼装"的 contract 测试作为外层保险。

### 可复用能力

| 既有能力 | 决断 | 理由 |
|---|---|---|
| `ToolRegistry.get(name) → Tool` | 用 | `/v1/capabilities` 已是 `Depends(get_tool_registry)` 模式，直接复用 |
| `resolve_available_skills(workspace_root, include_names)` | 用 | 已有 `include_names` 集合过滤，未注册的天然静默跳过——正合 spec Q7 |
| `IM application/config_service.py:workspace_root_for_profile` | 用 | agent-detail 路径 IM 服务端已 derive 真实 workspace_root 并透传到 gateway，前端无需关心 |
| `IM domain/models.py:managed_workspace_root(agent_id)` | 用 | agent-create 路径用它从 `agent_id` 预测 workspace 路径——与创建后 profile 默认 workspace_root 完全一致，所见即所得 |
| `PA_SECTIONS` / `CORE_SECTIONS` | 用 | 已能渲染 Available Tools / Skills / runtime footer，预览改的是 ctx 入参不是 section |

### 相关历史

- **feat-379**（M2 R5 + M6 ISSUE-3 + M9 决策 11/14）：本 unit 直接改进的对象。M2 R5 引入 `/v1/prompt-preview`；M6 ISSUE-3 修过 `description=""` stub 的 AttributeError（当时只解决了崩溃，没解决"空冒号"的呈现问题）；M9 决策 11 加了 node-level preview 给 agent-create 用。
- **本 unit 与 feat-379 的关系**：feat-379 建立预览整体骨架与 cache-stable 不变量；本 unit 是骨架之上的**呈现保真度**修复——只调 ctx 入参与占位符策略，不动骨架。

## 架构总览

预览链路（before vs after，星号 `*` 标本 unit 改动点）：

```
浏览器              IM HTTP                Gateway (WS)          Agent Kernel HTTP
─────              ──────                ────────────          ──────────────────

[agent-detail]
draft.skills*      /agents/{id}/         agent.prompt.preview  /v1/prompt-preview
draft.tools  ───►  prompt-preview   ───► .request         ───► (PromptContext)
                   (IM derive                                   ↓
                    workspace_root via                          ToolRegistry.get(id)* ─► 真 description
                    workspace_root_for_profile)                 resolve_available_skills(
                                                                  workspace_root, skill_ids*
                                                                ) ─► 真 SkillMetadata
                                                                cwd = workspace_root
                                                                datetime = <运行时注入：当前时间>*
                                                                ↓
                                                                assemble_system_prompt(
                                                                  stable_sections, ctx
                                                                )

[agent-create]
draft.agent_id* ─►
draft.skills*  ─►  /nodes/{id}/          node.prompt.preview   /v1/prompt-preview
draft.tools        prompt-preview   ───► .request         ───► （同上；workspace_root 由 IM
                   (IM derive                                  服务端 managed_workspace_root
                    workspace_root via                         (agent_id_hint) 算出后塞进
                    managed_workspace_root                     payload，agent_id_hint 未填
                    (agent_id_hint)*)                          时传空字符串）
```

核心思路一句话：**前端把"用户已勾的 skills + 已填的 agent_id"补进预览请求；IM 服务端 derive 真实 workspace_root；agent kernel 端把 ctx 里的 stub 全替换成真实数据 + 把唯一 volatile 字段（时间）换成占位符**。section 渲染逻辑不动，等价性靠既有 golden test + 新加 contract test 守住。

## 关键决策

### 决策 1: workspace_root 由 IM 服务端 derive，不让前端传

- **选择**: agent-detail 路径继续用 `service.workspace_root_for_profile(profile)`；agent-create 路径加 `agent_id_hint` 字段，IM 收到后调 `managed_workspace_root(agent_id_hint)` derive 真实路径，再透传给 gateway。
- **理由**: workspace 路径生成规则是 IM 层的领域知识（`_MANAGED_WORKSPACE_ROOT / agent_id`）。前端硬编码会形成跨层重复。IM 已有现成的 `managed_workspace_root`，与 agent 真正创建后保存到 profile 的默认 workspace 完全一致——预览所见即创建后所得。
- **拒绝**: 让前端拼 `~/nano-assistant/workspace/<id>`（违反层级、易随后端调整漂移）；让 agent kernel 端凭 agent_id 自己 derive（agent kernel 不该知道 IM 的 workspace 约定）。
- **风险**: 若用户在 agent-detail 改了 `workspace_root` 自定义字段，要确保 IM 服务端 derive 的是改后的值——`workspace_root_for_profile` 已正确处理（profile.workspace_root 非空则用，否则 fallback managed）。

### 决策 2: skill_ids 由前端传，agent kernel 端解析

- **选择**: 前端 `promptPreview()` / `nodePromptPreview()` 调用加 `skill_ids: draft.skills`，全链路透传到 agent `/v1/prompt-preview`；kernel 端调 `resolve_available_skills(workspace_root=Path(workspace_root), include_names=skill_ids)` 解析为 `SkillMetadata` 元组塞 ctx。
- **理由**: skill 文件物理位置在 agent workspace 内，只有 agent kernel 能正确解析；前端只知用户勾选的 id。`resolve_available_skills` 已对 `include_names` 做集合过滤，workspace 里没有的 skill 天然不出现——满足 spec Q7 "静默跳过"。
- **拒绝**: 让 IM 帮忙解析 skill（违反层级，IM 不读 agent workspace）；让前端读 skill 描述（前端没有读 agent workspace 的能力）。
- **风险**: workspace 为空（agent-create 未填 ID）时——本 unit 在 ctx 构造时显式判空：`workspace_root` 为空则 `available_skills=()`，预览不渲染 skills 段。

### 决策 3: 工具 ToolRegistry 注入 + 静默跳过

- **选择**: `/v1/prompt-preview` 函数加 `registry: ToolRegistry = Depends(get_tool_registry)`。对每个 `tool_id`，`registry.get(name)` 拿真实 Tool 对象；返回 None 的 id 静默跳过（不进 ctx.available_tools）。
- **理由**: 与运行时一致——运行时不会把不存在的工具暴露给 agent。预览静默跳过即镜像运行时行为。Tool 对象的 `.description` 是 cache-safe 的静态文本，进 ctx 后 section 渲染天然得到真实 `- {name}: {description}`。
- **拒绝**: 给找不到的 id 加 `<未注册工具>` 占位（spec Q7 已否决，会让用户误以为 agent 实际收到了某种占位 stub）；构造 SimpleNamespace stub（当前做法，是这次要修的根源）。
- **风险**: tool description 可能数百到上千字符——spec Q5 已明确"不截断"，按真长度透出。

### 决策 4: datetime 用占位符，cwd 占位仅在 workspace 真不可知时启用

- **选择**:
  - `ctx.current_datetime = "<运行时注入：当前时间>"`（恒定）
  - `ctx.cwd = workspace_root if workspace_root else "<运行时注入：workspace 路径>"`
- **理由**: 时间是 UI 不可控、运行时必注入真值的 volatile 量。整行删除会让用户不知道运行时会有时间字段；占位文案显式标注"运行时注入"，所见即所得。cwd 在 agent-detail 恒有真实路径；agent-create 用户填了 agent_id 也有真实路径；只有 agent-create 且 Agent ID 未填时才退化到占位。
- **拒绝**: 时间填 `""`（当前做法，造成"Current date and time: " 后空白的误导）；时间整行删除（spec Q3 已否决，"不真实"）。
- **风险**: 占位文案 `<...>` 与某些 chat template 特殊 token 冲突——本 unit 占位只在预览端 UI 显示，不进运行时 LLM 输入；运行时仍是真实时间戳，无冲突。

### 决策 5: 预览 vs 运行时一致性靠两层防线守

- **选择**:
  - 第 1 层（既有）：`tests/integration/test_prompt_sections_golden.py` 保 `assemble_system_prompt() ≡ build_system_prompt()` 在 6 canonical 场景下逐字相等。
  - 第 2 层（新加）：`tests/contract/test_prompt_preview_runtime_parity.py`——构造一对一致的 `PromptContext` 与运行时输入，调用 `/v1/prompt-preview` HTTP 端拿到预览串、调用 runtime `build_system_prompt` 拿到运行时串；断言 preview 串中两个占位符（`<运行时注入：当前时间>` / 必要时 `<运行时注入：workspace 路径>`）按规则替换为同一 datetime / 同一 workspace 后，与运行时串逐字相等。
- **理由**: golden test 保两个 builder 等价；新 contract test 保 HTTP 端到 runtime 实际拼装的端到端一致。两个守护点各自有独立 falsifier——任一回归都会立即报错。
- **拒绝**: 仅依赖 golden test（不覆盖 HTTP 路由层 ctx 构造差异）；删除 golden test 让两者共用 builder（与本 unit 范围无关，越界改 feat-379 架构）。
- **风险**: contract test 需要构造一致的 `PromptContext`——实现期把"ctx 构造"逻辑提到一个可复用辅助降低漂移风险，但若 worker 评估代价过高可以接受"测试内部各自构造同输入"——只要断言关系成立。

### 决策 6: 静默跳过实现位置

- **选择**:
  - 工具：在 `/v1/prompt-preview` 函数体内构造 `ctx.available_tools` 时即过滤（`registry.get(tid) is not None`）。
  - skill：靠 `resolve_available_skills` 既有的 `include_names` 集合过滤（registry 里没有的 skill 自然不出现）。
- **理由**: 静默跳过是预览端语义，不应渗透到 core section 渲染逻辑。section 渲染保持"输入啥就渲染啥"的纯函数语义，过滤职责在调用者。
- **拒绝**: 在 `_render_runtime_tools` 里加 `if t.description: ...` 兜底（污染 core 渲染层，且 description 真为空字符串的合法工具会被吞）。
- **风险**: 若未来引入"未注册 id 也要诊断展示"的需求（与 spec Q7 决策相反），过滤逻辑要从预览端转移——届时改本 unit 的过滤点即可，不会被 core 层绑住。

## 接口与数据流

### Agent kernel HTTP `/v1/prompt-preview`

请求体（新增字段已标 ★）：

```python
class PromptPreviewRequest(BaseModel):
    features: dict[str, bool] = Field(default_factory=dict)
    custom_prompt: str | None = None
    tool_ids: list[str] = Field(default_factory=list)
    scenario: str = "direct"
    workspace_root: str | None = None                    # ★ 真实 workspace 路径；为空时启用 cwd 占位
    skill_ids: list[str] = Field(default_factory=list)   # ★ 用户勾选的 skill 名集合
```

ctx 构造（伪表，非实现代码）：

| ctx 字段 | 当前 | 修后 |
|---|---|---|
| `available_tools` | `(SimpleNamespace(name=t, description="") for t in tool_ids)` | `tuple(filter(None, (registry.get(t) for t in tool_ids)))` |
| `available_skills` | `()` | `resolve_available_skills(Path(workspace_root), include_names=skill_ids)` if `workspace_root` else `()` |
| `current_datetime` | `""` | `"<运行时注入：当前时间>"` |
| `cwd` | `""` | `workspace_root or "<运行时注入：workspace 路径>"` |
| `memory_block` | `None` | `None`（不变；预览只取 cache-stable 段） |
| `flags` / `scenario` / `vars` | 同 | 同 |

响应体不变（`{prompt, section_count}`）。

### kernel_api_client.prompt_preview() 签名扩展

```python
def prompt_preview(
    self, *,
    features, custom_prompt, tool_ids, scenario,
    workspace_root: str | None = None,        # ★
    skill_ids: list[str] | None = None,       # ★
) -> dict[str, Any]
```

### Gateway WS frame schema 扩展

`agent.prompt.preview.request` payload（workspace_root 已有，新增 `skill_ids`）：

```json
{
  "request_id": "...",
  "agent_id": "...",
  "workspace_root": "/absolute/path",
  "skill_ids": ["skill-a", "skill-b"],
  "features": {...}, "custom_prompt": "...", "tool_ids": [...], "scenario": "direct"
}
```

`node.prompt.preview.request` payload 修订（统一与 agent 路径同构，新增 `workspace_root` + `skill_ids`；workspace_root 由 IM 端 derive 后传入，未填 Agent ID 时传空字符串）：

```json
{
  "request_id": "...",
  "workspace_root": "/absolute/path-or-empty",
  "skill_ids": ["skill-a"],
  "features": {...}, "custom_prompt": "...", "tool_ids": [...], "scenario": "direct"
}
```

`agent_id_hint` 字段不进 gateway 协议——IM 路由层吸收并立刻转换为 `workspace_root`。两条预览路径（agent / node）在 gateway 协议层保持同构。

### IM HTTP 路由

`POST /im/v1/agents/{id}/prompt-preview` 请求体扩展（+ `skill_ids`），服务端用 `service.workspace_root_for_profile(profile)` 拿 workspace_root（已有），追加 `skill_ids` 透传到 `gateway_handler.request_prompt_preview`。

`POST /im/v1/nodes/{id}/prompt-preview` 请求体扩展：

```python
class NodePromptPreviewRequest(BaseModel):
    features: dict[str, bool] = Field(default_factory=dict)
    custom_prompt: str | None = None
    tool_ids: list[str] = Field(default_factory=list)
    scenario: str = "direct"
    skill_ids: list[str] = Field(default_factory=list)  # ★
    agent_id_hint: str | None = None                    # ★
```

服务端伪逻辑：

```
workspace_root = managed_workspace_root(agent_id_hint) if agent_id_hint else ""
gateway_handler.request_node_prompt_preview(
    target_node_id=...,
    workspace_root=workspace_root,
    skill_ids=skill_ids,
    ...
)
```

### 前端 API 客户端

`im-agent-config-api.ts`：

```typescript
export async function promptPreview(
  agentId: string,
  body: {
    features: Record<string, boolean>;
    custom_prompt: string;
    tool_ids?: string[];
    skill_ids?: string[];                  // ★
  }
): Promise<string> { ... }

export async function nodePromptPreview(
  nodeId: string,
  body: {
    features: Record<string, boolean>;
    custom_prompt: string;
    tool_ids?: string[];
    skill_ids?: string[];                  // ★
    agent_id_hint?: string;                // ★
  }
): Promise<string> { ... }
```

调用点：

- `agent-detail-page.tsx:fetchPreview` 加 `skill_ids: draft.skills`，把 `draft.skills` 加入 `useCallback` 依赖数组和 debounce `useEffect` 依赖数组。
- `agent-create-page.tsx:fetchPreview` 加 `skill_ids: draft.skills` + `agent_id_hint: draft.agent_id`，同样补依赖。

## 风险与回退

| 风险 | 缓解 |
|---|---|
| **占位文案在某些 LLM provider 中被识别为特殊 token** | 占位只出现在预览端（不进运行时 LLM 输入），无运行时风险。文案用中文 + 尖括号，与常见 chat template 占位（`<\|...\|>`）形态不同，UI 显示无 token 化问题。 |
| **golden test 漂移：未来改 PA_SECTIONS 但忘改 PERSONAL_ASSISTANT_SYSTEM_PROMPT** | 既有 golden test 会失败。本 unit 新加的 contract test 是补充层，不替代。 |
| **resolve_available_skills 在大量 skill 时延迟** | 预览端 600ms debounce；skill 解析为本地文件 scan，单次单 agent workspace，量级与运行时启动解析同路径，可接受。 |
| **agent-create 输入 Agent ID 后又改名导致 workspace 路径漂移** | 预览跟随当前输入的 Agent ID（debounce 后重新发请求）；agent 真正创建后写入 profile 的 workspace_root 与最后一次预览看到的一致。 |
| **Tool description 极长，前端渲染卡顿** | spec Q5 已确认不截断；前端预览本就是只读控件，浏览器渲染数千字符无压力。 |

**回退路径**: 本 unit 改动局限于"预览端 ctx 构造 + 跨栈字段透传"，无数据迁移、无 schema 破坏；如发现严重问题，回退 = revert merge commit 即可，运行时 prompt 装配链路不受影响。

## Runbook for Reviewer

reviewer 走旅程用 `scripts/e2e-up.sh` / `scripts/e2e-down.sh` 起停 IM + Kernel API + Gateway（详见 `AGENTS.md` "运行时服务并行启动"段）。本 unit 改动仅涉及预览路径与前端，无新增常驻服务、无数据库 schema 变更。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM + Kernel + Gateway 一组 | `./scripts/e2e-down.sh` | `./scripts/e2e-up.sh` | `source .e2e-ports.env && curl -s "$IM_URL/im/v1/health"` 返回 200；浏览器打开 `$IM_URL` 能登录 |
| IM 前端（Vite dev） | `kill "$(cat .vite.pid)" 2>/dev/null; rm -f .vite.pid` | `read VITE_PORT < <(scripts/free-ports.sh 1); (cd src/IM/frontend && npm run dev -- --port "$VITE_PORT" --strictPort) > .vite.log 2>&1 & echo $! > .vite.pid` | 浏览器打开 `http://127.0.0.1:$VITE_PORT/` 看到登录页 |

reviewer 验收旅程脚本：

1. 登录 `nano / nano1234`，进入 `/settings/agents/<现有 agent>`，展开 "▸ Preview full system prompt"。
2. 勾上/勾掉若干工具、若干 skill，每次调整后等 ~700ms（含 600ms debounce），观察预览中 `## Available Tools` 段和 Skills 段是否同步更新且**冒号后有真实描述**。
3. 观察 `Current date and time:` 后是 `<运行时注入：当前时间>`，`Current working directory:` 后是该 agent 真实 workspace 路径。
4. 进 agent-create 页（"+ New"），先不填 Agent ID 展开预览：`Current working directory:` 应为 `<运行时注入：workspace 路径>`。填入合法 Agent ID，等 ~700ms：预览中的工作目录应变为真实路径（形如 `~/nano-assistant/workspace/<id>` 的 expanduser 解析结果）。

## Milestones

判定：本 unit 跨栈但**强耦合**——前端字段加 → IM 路由透传 → gateway 协议 → kernel ctx 构造，任一不到位预览即不闭环，无独立模块可真并行；总改动量估算 ~250 行远低于 800 行阈值；无须分阶段验证。不满足 §4.2 任一拆分触发条件。**默认单 M1。**

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-383-M1 | preview-fidelity-end-to-end | — | A | `src/agent/platform/http_api/routes/global_routes.py` · `src/personal_assistant/client/kernel_api_client.py` · `src/personal_assistant/main.py` · `src/personal_assistant/ws/im_connection.py` · `src/IM/ws/gateway_handler.py` · `src/IM/api/routes/agents.py` · `src/IM/api/routes/nodes.py` · `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts` · `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx` · `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx` · `tests/contract/test_prompt_preview_runtime_parity.py`（新建） · 关联单元/集成测试更新 | `[reviewer]` 覆盖 spec R1 全部 3 Scenario（工具切换 / skill 切换 / custom prompt 改写）<br>`[reviewer]` 覆盖 R2 全部 2 Scenario（已注册工具显示真实描述 / 未注册工具静默跳过）<br>`[reviewer]` 覆盖 R3 全部 3 Scenario（已存在 agent / agent-create 已填 ID / agent-create 未填 ID）<br>`[reviewer]` 覆盖 R4（时间字段占位符显示）<br>`[reviewer]` 覆盖 R5 全部 3 Scenario（已勾 / 未勾 / 解析失败）<br>`[worker]` `pytest tests/unit/test_global_routes_prompt_preview.py tests/contract/test_prompt_preview_runtime_parity.py tests/integration/test_prompt_sections_golden.py` 全绿<br>`[worker]` `pytest -m "not e2e"` 全绿（无回归）<br>`[worker]` `(cd src/IM/frontend && npm run test)` 全绿<br>`[worker]` 新增 contract test `test_prompt_preview_runtime_parity` 断言：preview HTTP 输出中 `<运行时注入：当前时间>` 替换为同一 datetime 后，与 runtime `build_system_prompt` 在同 ctx 下的输出逐字相等<br>`[worker]` IM 单测覆盖 `agent_id_hint → managed_workspace_root` derive 路径<br>`[worker]` 前端单测覆盖 `draft.skills` 透传到 `promptPreview` / `nodePromptPreview` 调用 payload |

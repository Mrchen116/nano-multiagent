# feat-379-M3: im-frontend-feature-toggles

## 目标

重构 IM 前端 Behavior card：移除旧「System Prompt 整串 textarea + 必填校验」，
新增「自定义补充 textarea(custom_prompt)、特性开关组(features checkbox)、折叠预览(prompt-preview)」。

## 退出标准

- `[worker]` `npm run test`(vitest) + `npm run build` 通过
- `[reviewer]` Settings→Agents 每个用户可勾特性有开关并按默认值呈现
- `[reviewer]` 切开关保存→重启 IM+Gateway→状态保持
- `[reviewer]` 展开「完整系统提示词预览」看到当前特性+自定义拼出的提示词，切开关/改文本后预览更新

## 测试策略

### UI 状态矩阵

| 状态 | 覆盖方式 |
|---|---|
| default (加载完成，有 capabilities.features) | R1 组件测试 |
| loading (capabilities 未到) | R1 组件测试 |
| empty (无 features 返回) | R1 组件测试（graceful fallback） |
| error (capabilities 请求失败) | 现有测试已覆盖 detail 页错误 |
| disabled (feature available=false 缺依赖工具) | R1 组件测试 |
| submitting (save in flight) | 现有 agent-edit.test.tsx 已覆盖 |
| long content (custom_prompt 长文本) | 状态矩阵确认 textarea resize |
| mobile viewport | R3 浏览器截图 |
| desktop viewport | R3 浏览器截图 |

### 用户路径分类

| 路径 | 类型 | 落库 |
|---|---|---|
| features 开关 toggle + 保存 | `normal-ui` | 组件测试 + 浏览器临时验收 |
| custom_prompt 填写 + 保存 | `normal-ui` | 组件测试 + 浏览器临时验收 |
| 折叠预览展开/收起 | `normal-ui` | 组件测试 + 浏览器临时验收 |
| features=disabled 工具缺失 | `normal-ui` | 组件测试（disabled 检查） |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| features checkbox 三态正确 | 组件测试（checked/unchecked/disabled） | 是 |
| custom_prompt 保存入 PATCH payload | 组件测试（updateAgentConfig 调用断言） | 是 |
| 折叠预览 aria-expanded 正确 | 组件测试 | 是 |
| 移除 system_prompt 必填校验不破坏保存 | 更新现有 agent-edit.test.tsx | 是 |
| 视觉复用 checkbox idiom / --open 模式 | 浏览器截图 | 否 |
| features=null 时 graceful | 组件测试 | 是 |

## Roadpoints

### R1 — 类型 + API 层扩展 `[DONE]`

**范围**: `im-agent-config-api.ts`

- 新增 `AgentFeature` 接口（key/label/help/default_on/available）
- `CapabilitySnapshot` / `AgentCapabilities` 增 `features?: AgentFeature[]`
- `AgentConfig` 增 `features?: Record<string, boolean>`, `custom_prompt?: string`
- `UpdateAgentConfigRequest` 增 `features?: Record<string, boolean>`, `custom_prompt?: string`
- `NodeAgentCreateRequest` 增 `features?: Record<string, boolean>`, `custom_prompt?: string`
- 新增 `promptPreview(agentId, body)` 函数（POST /im/v1/agents/{id}/prompt-preview）

### R2 — Behavior card 重构（detail + create 页）`[DONE]`

**范围**: `agent-detail-page.tsx`, `agent-create-page.tsx`, `en.json`, `zh.json`

- 移除 system_prompt textarea + system_prompt 必填校验
- 新增 custom_prompt textarea（optional）
- 新增 features checkbox 组（复用 checkbox idiom）
- 新增折叠预览区（复用 aria-expanded + ▸/▾ + --open 模式）
- 保留 group_reply_policy select（场景必加，非开关）
- normalizeAgentConfig / validateDraft 相应更新

### R3 — 测试更新 + 浏览器自测 `[DONE]`

**范围**: `agent-detail-page.test.tsx`, `agent-edit.test.tsx`, `agent-create.test.tsx`（现有测试）

- 更新 mock 加 `features: [...]`（capabilities），`features: {}`, `custom_prompt: ""`（config）
- 移除 system_prompt 必填校验相关断言（或更新）
- 新增：features checkbox 显示测试、custom_prompt 保存测试、折叠预览测试
- 浏览器自测：起 IM + Vite，截图

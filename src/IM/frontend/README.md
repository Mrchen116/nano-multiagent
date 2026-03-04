# IM Frontend 运行与验收说明（M38）

## 1. 本地运行

### 1.1 Mock 模式（默认回归方式）

```bash
cd src/IM/frontend
npm install
VITE_CHAT_API_MODE=mock npm run dev -- --host 127.0.0.1 --port 4173
```

访问：`http://127.0.0.1:4173/chat`

### 1.2 真实 IM 服务模式（仅 Chat 路径）

终端 A（启动 IM 服务）：

```bash
PYTHONPATH=src uvicorn IM.app:create_app --factory --host 127.0.0.1 --port 8001
```

终端 B（启动前端）：

```bash
cd src/IM/frontend
VITE_IM_API_BASE_URL=http://127.0.0.1:8001 VITE_CHAT_API_MODE=im npm run dev -- --host 127.0.0.1 --port 4173
```

## 2. 门禁命令

```bash
PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build
```

## 3. API 与 Mock 边界

| 模块 | 当前数据源 | 切换方式 | 边界说明 |
|---|---|---|---|
| Chat（`/chat`、`/chat/:conversationId`） | `im-chat-api` 或 `mock-chat-api` | `VITE_CHAT_API_MODE=im|mock`；若未显式设置则 `test` 环境默认 mock、其他环境默认 im | 由 `src/features/chat/chat-api.ts` 的 `resolveChatApiMode` 决定 |
| Settings（`/settings/*`） | `mock-settings-api` | 无运行时切换（V1 固定 mock） | 页面直接调用 `src/features/settings/mock-settings-api.ts`，用于前端独立验证 |
| Vitest | mock | 自动 | 测试运行时 `import.meta.env.MODE === "test"`，chat 自动走 mock |
| Playwright 回归（M38） | mock | 启动前端时设置 `VITE_CHAT_API_MODE=mock` | 避免回归时受外部服务可用性干扰，专注 UI/交互稳定性 |

## 4. 第二轮验收截图索引（2026-03-04）

截图目录：`src/IM/frontend/output/playwright/`

| 设备 | 页面 | 场景 | 文件 |
|---|---|---|---|
| Desktop | Chat `/chat` | 会话列表 | `M38-chat-desktop-list.png` |
| Desktop | Chat `/chat/conv-kernel-ops` | 发送消息后 | `M38-chat-desktop-after-send.png` |
| Desktop | Chat `/chat` | favicon 修复后复核 | `M38-chat-desktop-post-favicon-fix.png` |
| Mobile | Chat `/chat` | 会话列表 | `M38-chat-mobile-list.png` |
| Mobile | Chat `/chat/conv-kernel-ops` | 发送消息后 | `M38-chat-mobile-after-send.png` |
| Desktop | Settings `/settings/agents` | Agents 列表 | `M38-settings-desktop-agents-list.png` |
| Desktop | Settings `/settings/agents/agent-core-1` | Agent 保存后 | `M38-settings-desktop-agent-detail-saved.png` |
| Desktop | Settings `/settings/nodes` | Node 保存后 | `M38-settings-desktop-nodes-saved.png` |
| Desktop | Settings `/settings/policies` | Policies 页 | `M38-settings-desktop-policies.png` |
| Desktop | Settings `/settings/account` | Account 页 | `M38-settings-desktop-account.png` |
| Mobile | Settings `/settings/agents` | Agents 列表 | `M38-settings-mobile-agents-list.png` |
| Mobile | Settings `/settings/nodes` | Nodes 页 | `M38-settings-mobile-nodes.png` |
| Mobile | Settings `/settings/policies` | Policies 页 | `M38-settings-mobile-policies.png` |
| Mobile | Settings `/settings/account` | Account 页 | `M38-settings-mobile-account.png` |

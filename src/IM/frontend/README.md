# IM Frontend 默认入口与开发说明

## 1. 默认用户入口

正常用户默认从 IM host 进入 Web IM，而不是直接访问前端 dev server。

推荐入口：
- `http://127.0.0.1:8011/`
- `http://127.0.0.1:8011/chat`

当前默认行为：
- 当仓内 `src/IM/frontend/dist` 存在时，IM 服务会直接提供 `/`、`/chat`、`/settings/*`、`/bind/confirm` 的前端壳。
- 打开 `http://127.0.0.1:8011/` 后，浏览器会落到 `/chat`。
- Web IM 会自动准备本地 `You` 用户和默认 starter conversation；正常用户不需要先手工创建用户、会话或调用消息 API。
- 会话列表不再只表现为单一 demo chat：列表会明确区分 direct agent chat、agent-to-agent chat、group chat、system feed，并显示 target/用途提示，帮助普通用户理解当前有哪些可聊天对象。
- 若已绑定的目标节点当前不在线，聊天输入区会直接禁用，并显示“Bring the Gateway online or bind an online node, then retry.” 这类可执行反馈，而不是停留在可输入但不可达的半连通状态。

绑定相关行为：
- 未绑定节点时，Gateway 会输出 `ACTION ...` / `NEXT ...`，并尝试打开绑定页。
- 默认绑定页位于 `http://127.0.0.1:8011/bind/confirm?token=...`。
- 绑定完成后刷新 `/` 或重新打开 `/chat`，即可继续聊天。
- 打开 `/chat` 后，左侧会话列表会说明不同会话类型：direct agent chat 表示你可直接发消息给某个 agent；agent-to-agent chat 表示可查看 agent 协作线程；group chat 表示多人/多 agent 共享线程。

## 2. 前端开发模式

`127.0.0.1:4173` 只用于前端开发或回归，不是默认用户入口。

### 2.1 Mock 模式

```bash
cd src/IM/frontend
npm install
VITE_CHAT_API_MODE=mock npm run dev -- --host 127.0.0.1 --port 4173
```

访问：`http://127.0.0.1:4173/chat`

### 2.2 真实 IM 服务 + Vite 开发模式

终端 A（启动 IM 服务）：

```bash
PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 8001
```

终端 B（启动前端 dev server）：

```bash
cd src/IM/frontend
VITE_IM_API_BASE_URL=http://127.0.0.1:8001 VITE_CHAT_API_MODE=im npm run dev -- --host 127.0.0.1 --port 4173
```

说明：
- 这条路径只用于前端开发、Mock/真实 API 切换和页面调试。
- 如果 IM host 没有可用 `dist`，它才会把 `/`、`/chat`、`/bind/confirm` 重定向到配置的前端 dev server。

## 3. 构建与门禁

默认构建命令：

```bash
cd src/IM/frontend
npm install
npm run build
```

前端/IM 联合回归门禁：

```bash
PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build
```

## 4. API 与 Mock 边界

| 模块 | 当前数据源 | 切换方式 | 边界说明 |
|---|---|---|---|
| Chat（`/chat`、`/chat/:conversationId`） | `im-chat-api` 或 `mock-chat-api` | `VITE_CHAT_API_MODE=im|mock`；若未显式设置则 `test` 环境默认 mock、其他环境默认 im | 由 `src/features/chat/chat-api.ts` 的 `resolveChatApiMode` 决定 |
| Settings（`/settings/*`） | `mock-settings-api` | 无运行时切换（V1 固定 mock） | 页面直接调用 `src/features/settings/mock-settings-api.ts`，用于前端独立验证 |
| Vitest | mock | 自动 | 测试运行时 `import.meta.env.MODE === "test"`，chat 自动走 mock |
| Playwright 回归（M38） | mock | 启动前端时设置 `VITE_CHAT_API_MODE=mock` | 避免回归时受外部服务可用性干扰，专注 UI/交互稳定性 |

## 5. 第二轮验收截图索引（2026-03-04）

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

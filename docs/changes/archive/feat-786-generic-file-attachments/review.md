# Review Record — `feat-786-generic-file-attachments`

## 1. 独立审查总览

| 审查项 | 独立审查者 | 初始结论 | 复核与收敛结果 |
|---|---|---|---|
| **Code Review (`change-code-review`, full + corrected-delta)** | 独立 subagent (`98fa5bce-774a-4850-84bf-ce3bb9e92021`) | `Changes Requested`（`0 CRITICAL` / `2 MEDIUM` / `1 LOW`，delta-spec 为 `implementation-mismatch`） | 全部 3 项已修复并补充回归单测；`corrected-delta` 闭合为 `aligned` |
| **Agent Context Review (`agent-context-review`)** | 独立 subagent (`fc9b24d3-5995-4084-a0a4-4a6edc72592d`) | 6 项发现（1 高 / 2 中 / 3 低-中） | 全部 6 项已修复并复验受控 provider / prefix / 工具剥离单测 |

---

## 2. 发现项与修复闭环

| 编号 | 来源 | 严重度 | 摘要 | 修复动作与定位 | 状态 |
|---|---|---|---|---|---|
| `CR-F1` / `ACR-F1` | Code + Context | 高/中（阻塞） | `download_attachment` 下载光栅图（PNG/JPEG/GIF/WebP）时，因 `media.ts` 未下发 `Content-Disposition`，落盘退化为 32 位随机 `image_id` 且丢失扩展名 | `apps/im-server/src/media.ts` 为光栅图下发 `Content-Disposition: inline; filename="<ascii>"; filename*=UTF-8''<utf8>`；`apps/node/src/file-transfer.ts` 增加 `appendFallbackExtension` MIME 兜底后缀；同步更新 `media.test.ts` 与 `file-transfer.test.ts` 验证 `inline` 头及兜底扩展名 | Closed |
| `CR-F2` | Code | 中（阻塞） | 缺失两条关键回归保护：`global-agent.test.ts` 未实际触发 `local_files` `unknown` → `receipt_of` 恢复；`approval.test.ts` 未覆盖 `local_files` 私有审批拒绝与 `download_attachment` 免审放行 | 补齐 `packages/personal-assistant/tests/global-agent.test.ts` 中 `local_files` `unknown` → `receipt_of` 恢复断言，并在 `packages/dsh-integration/tests/approval.test.ts` 补齐 `download_attachment`（`safe_tool`）与 `local_files`（私有审批拒绝且无 `approval/request` 泄露）回归测试 | Closed |
| `CR-F3` / `ACR-F4` | Code + Context | 低-中 | `inbox.ts:692,822` 仍以 `startsWith('image/')` 计算图片预算与 `read_messages` 过滤；`composer-attachment-card.tsx:41` 草稿预览仍用 `startsWith('image/')` | 全部收口为 `isRasterImageMime`（`packages/personal-assistant/src/inbox.ts`、`src/IM/frontend/src/features/chat/attachments/composer-attachment-card.tsx`） | Closed |
| `ACR-F2` | Context | 中 | SingleThread `nano-communication` 的 `NO_REPLY` 静默协议仅提及卡片与图片，遗漏文件交付 | `packages/dsh-integration/src/global-mode.ts:79` 更新为 `After confirmed card, image, or file delivery via send_message, end with the exact non-empty final text NO_REPLY...` | Closed |
| `ACR-F3` | Context | 中 | SingleThread 显式 `toolAllowlist` 未含 `download_attachment` 时，入站消息仍无条件输出 `— call download_attachment to save locally` | `packages/personal-assistant/src/single-thread.ts:402-409` 根据 `config.toolAllowlist` 条件渲染下载提示 | Closed |
| `ACR-F5` | Context | 低-中 | Global 委派指引未提先下载聊天文件再传 `local_path`；子 Agent 提示未列 `download_attachment`；`approval.ts:27` 与 `global-agent.ts:1064` 仍沿用 `Screenshot` 报错文案 | 同步更新 `packages/dsh-integration/src/global-mode.ts:45,173`、`packages/dsh-integration/src/policy/approval.ts:27` 与 `packages/personal-assistant/src/global-agent.ts:1064` | Closed |
| `ACR-F6` | Context | 低 | PA 提示词 `personal-security.ts:224` 写 `"UTF-8 text files"` 略宽于 `personal-actions.ts:46` 的 9 种 MIME 白名单；`send_message.attachments` 缺简短描述 | `personal-security.ts:224` 精确列出支持格式；`message-arguments.ts:9` 补齐 `attachments` 字段描述 | Closed |

---

## 3. 验证与证据边界

- **自动化验证（全部修复后重跑通过）**：
  - 后端 / Node / PA / DSH Vitest 套件（含 `media.test.ts`、`media-quota.test.ts`、`personal-disclosure.test.ts`、`personal-images.test.ts`、`file-transfer.test.ts`、`screenshot-upload.test.ts`、`im-http.test.ts`、`id-length-contract.test.ts`、`single-thread.test.ts`、`global-agent.test.ts`、`personal-assistant.test.ts`、`interactive-replies.test.ts`、`inbox.test.ts`、`capabilities.test.ts`、`message-arguments.test.ts`、`global-child-tools.test.ts`、`approval.test.ts`、`fork-prefix-provider.test.ts`）
  - 架构依赖契约：`python3 -m pytest tests/contract/test_runtime_dependency_contract.py`（13/13）
  - Web 前端：`attachment-chip.test.tsx`、`use-attachment-upload.test.ts`（11/11）+ `npx tsc --noEmit`
  - 构建、类型与文档完整性：`pnpm build`、`pnpm typecheck`、`./scripts/docs-check`
- **边界说明**：本轮验证包含受控 Provider 出站 wire 请求（`fork-prefix-provider.test.ts`、`global-child-tools.test.ts`）与真实本地 HTTP 流式传输（`media.test.ts`、`file-transfer.test.ts`），未在公网/真实 LLM 模型上执行多轮对话采集。

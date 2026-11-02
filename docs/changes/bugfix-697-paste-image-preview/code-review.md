# bugfix-697: Validation and Code Review

## Scope and status

快速开发；实现、工程验证与独立审查记录在此。用户亲自体验确认尚未完成，unit active。独立 full 审查及恢复修复的 patch/closure 已完成；最终紧凑提示调整以窄测试与视觉核对验证。

## Existing test disposition

- `message-pane.test.tsx` 与 `chat-workspace.integration.test.tsx`：rewrite-merge 原先“失败不保留预览/全局 toast”断言为原位保留预览和局部错误，保留成功发送、草稿恢复、文字单发和迟到错误隔离保护。
- `message-pane-composer-draft.test.tsx`：keep，会话隔离、卸载恢复和撤权晚到结果保护仍适用。
- `message-pane-attachments.test.tsx`：新增上传生命周期 owner，保护网络未返回即可见、原卡片重试、移除后晚到结果与跨批完成乱序，避免继续向既有 2000 行文件堆积独立行为。
- `use-attachment-upload.test.ts`：扩展现有 HTTP 映射测试以区分非法图片内容与不支持格式。
- `apps/im-server/tests/media.test.ts`：新增图片签名与存取元数据 owner，原有 tenancy/external-ingress 测试未覆盖“JPEG 声明为 PNG”导致误拒绝的失败原因。

## Validation

- 同步最新主干并修复恢复问题后前端全套：111 files / 1052 tests passed；最终紧凑提示的相关三文件 72 tests passed。
- 前端类型检查与生产构建：通过（构建有既有第三方 annotation 与大 chunk 提示）。
- 隔离真实 HTTP：PNG 201；用户提供的 JPEG 字节按 PNG 声明在旧代码 415，修复后 201、content_type=image/jpeg、file_name=user-image.jpg；非图片反例仍 415。
- IM 全套：60 files / 363 tests passed；media/tenancy 窄验证 10 tests passed。IM build/typecheck 与 product-contracts build 通过。
- 文档完整性：277 maintained Markdown sources / 68 required routes，通过。
- 浏览器：真实隔离 IM，浏览器原生 File/DataTransfer/ClipboardEvent；在上传 HTTP 边界注入等待及一次 503，观察即时本地缩略图、继续输入、原位错误/重试及恢复就绪；桌面和 320/375px 移动宽度截图在 `output/playwright/`。图片编码反例与用户原文件另经真实 HTTP 验证，不以模拟响应代替。
- 验证中出现的初次依赖失败：借用旧 main 依赖不包含新主干的 sharp/EvaluationHistory；在本 worktree 独立安装锁定依赖并构建 contracts 后，最终服务端套件和构建通过。不将该环境错误当成产品失败。

## Independent review

### Round 1 — full

- Base/executed_base: `011396a815299b0bf6037709b92e775f87304d6f`。
- Head/validated_at: `4ee46b97643cc17e8ecc819abee6ee6fb744d695`。
- Reviewer: 独立 `review_paste_preview`，`gpt-6.1-sol/high`，按 change-code-review；无 Prompt/工具/模型 Context 组装变化，无完整 Context 审查。
- Finding（CONFIRMED/P2）：用户粘贴新图片时，queued/uploading 身份未参与草稿版本；旧发送查询晚到时可能误判为空草稿并覆盖新卡片。独立临时组件测试已复现，日志 `output/playwright/review-paste-recovery.log`；临时测试已删除。
- Resolution：上传身份加入版本比较；本地项增删在写入订阅 store 前明确更新 revision；恢复判定也检查 uploads 为空。扩展既有 `message-pane-send-attempt.test.tsx` 验证新图片不会被旧发送查询覆盖。
- 同期补齐：失败/恢复时刷新重试时钟，避免进入聊天较久后非限流错误也误显示等待；保留普通文件的打开/下载入口与紧凑布局，避免统一卡片后丢失原功能；输入区设置 min-width:0 防止移动端横向溢出。相关保护位于附件生命周期文件。
- 窄验证：12 tests passed（发送恢复与附件生命周期）。
- Patch/closure：原独立 reviewer 审查 `4ee46b976..2ff43d77a59d0a220728e700ec9033c50a4a0c00`，返回 `[]`，原 P2 closed；独立运行相关 12 tests passed，另核实 ready 附件草稿重挂及确认发送后的清理。
- 最终纯展示调整：卡片使用简短错误状态，title/可访问标签保留详细原因，避免英文说明撑高卡片；相关 72 tests 与构建通过，发送/恢复/MIME 逻辑不变。


## Final state

- executed_base / effective_base：`011396a815299b0bf6037709b92e775f87304d6f`。
- 逻辑有效版本：`2ff43d77a59d0a220728e700ec9033c50a4a0c00`；最终提交仅含紧凑错误展示及本文记录，相关逻辑审查结论保留。
- 用户实际验收：尚未发生，不伪造；unit 保持 active，canonical delta 未归并，未归档、未推送或部署。
- 本地产物与临时服务不纳入提交。开发 worktree 保留用于用户体验与后续反馈。

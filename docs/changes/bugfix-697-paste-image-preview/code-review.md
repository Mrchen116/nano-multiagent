# bugfix-697: Validation and Code Review

## Scope and status

快速开发；实现、工程验证与独立审查记录在此。用户亲自体验确认尚未完成，unit active。尚未执行独立审查，不能视为已通过。

## Existing test disposition

- `message-pane.test.tsx` 与 `chat-workspace.integration.test.tsx`：rewrite-merge 原先“失败不保留预览/全局 toast”断言为原位保留预览和局部错误，保留成功发送、草稿恢复、文字单发和迟到错误隔离保护。
- `message-pane-composer-draft.test.tsx`：keep，会话隔离、卸载恢复和撤权晚到结果保护仍适用。
- `message-pane-attachments.test.tsx`：新增上传生命周期 owner，保护网络未返回即可见、原卡片重试、移除后晚到结果与跨批完成乱序，避免继续向既有 2000 行文件堆积独立行为。
- `use-attachment-upload.test.ts`：扩展现有 HTTP 映射测试以区分非法图片内容与不支持格式。
- `apps/im-server/tests/media.test.ts`：新增图片签名与存取元数据 owner，原有 tenancy/external-ingress 测试未覆盖“JPEG 声明为 PNG”导致误拒绝的失败原因。

## Validation

- 前端全套：110 files / 1041 tests passed（同步主干前）。
- 前端类型检查与生产构建：通过（构建有既有第三方 annotation 与大 chunk 提示）。
- 隔离真实 HTTP：PNG 201；用户提供的 JPEG 字节按 PNG 声明在旧代码 415，修复后 201、content_type=image/jpeg、file_name=user-image.jpg；非图片反例仍 415。
- 浏览器与最终同步后测试：进行中，结果将在完成时补齐。

## Independent review

待对最终同步后的完整 diff 执行 `change-code-review`。

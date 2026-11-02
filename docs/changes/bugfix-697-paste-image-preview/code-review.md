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
- 浏览器：真实隔离 IM，浏览器原生 File/DataTransfer/ClipboardEvent；在上传 HTTP 边界注入等待及一次 503，观察即时本地缩略图、继续输入、原位错误/重试及恢复就绪；主会话独立执行 `root-visual-check.js`，桌面输入区与 320px 移动宽度截图在 `output/playwright/root-*.png`；验证重试后发送按钮就绪、页面无横向溢出。图片编码反例与用户原文件另经真实 HTTP 验证，不以模拟响应代替。
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
- 最终纯展示调整：卡片使用简短错误状态，title/可访问标签保留详细原因，避免英文说明撑高卡片；相关 72 tests 与构建通过，发送/恢复/MIME 逻辑不变。原 reviewer 对最终展示差异及随后发现的两文件 dirty 作只读窄核验，返回 []，未修改源码。


## Final state

- executed_base / effective_base：`011396a815299b0bf6037709b92e775f87304d6f`。
- 逻辑有效版本：`2ff43d77a59d0a220728e700ec9033c50a4a0c00`；最终提交仅含紧凑错误展示及本文记录，相关逻辑审查结论保留。
- 用户实际验收：尚未发生，不伪造；unit 保持 active，canonical delta 未归并，未归档、未推送或部署。
- 本地产物与临时服务不纳入提交。开发 worktree 保留用于用户体验与后续反馈。

## Concurrent-write boundary

交付核对时再次出现未经本主会话或 reviewer 写入的两文件 dirty：`message-pane.tsx` 的 textarea 自然换行自动增高 effect，以及 `global.css` 的行高/高度/错误区 flex-wrap。此前也发现另一个本地 63823 预览服务与 final-browser 产物。独立 reviewer 明确否认创建这些资源；主会话已向用户询问是否有其他窗口/Agent 同时写入。

这两处 dirty 原样保留、不纳入本次提交；本 unit 已提交实现仍可由分支恢复。主会话自建 62601 服务和独立 `paste-preview-root-check` 浏览器结束，未知归属的服务/共享会话不误关。用户确认归属后再处理剩余工作区内容。


## Additional chat UX audit — 2026-11-02

- 范围：聊天输入、附件粘贴/拖拽、失败恢复、发送恢复及手机窄屏布局；不宣称完成设置、任务、iOS 或全站审美检查。
- 独立 reviewer：`composer_review`，`gpt-6.1-sol/high`，使用 change-code-review。
- full 基线：`011396a815299b0bf6037709b92e775f87304d6f`；validated_at：`4ee46b97643cc17e8ecc819abee6ee6fb744d695`。
- CONFIRMED/P2：新卡片丢失普通文档发送前打开入口。修复为保留 AttachmentLink 和紧凑横向卡片。
- CONFIRMED/P2（baseline-existing）：非限流 HTTP 上传错误可能因旧 retryClock 永久禁用重试。修复为草稿上传状态变化时刷新时钟。
- `4ee46b976..2ff43d77a` patch/closure：上述两项与旧发送恢复覆盖新附件问题均 closed，返回 `[]`；reviewer 独立运行 12/12 相关测试通过。
- 后续视觉观察：完整英文错误在 112px 卡片下折为六行，输入区明显增高；320px 自然换行文字留在单行高度的内部滚动框。前者使用短标签保留详细原因，后者按 scrollHeight 增长并受 CSS 上限约束。
- 最后有界 patch：reviewer 核对 `2ff43d77a..ce806e85c` 加 `message-pane.tsx` / `global.css` 的自然换行修复，返回 `[]`；本轮 dirty patch SHA-256：`765a5db89a917e957a10b31395248d292163632fb91a73f04c7e20c6761760d2`。
- executed_base / effective_base：`011396a815299b0bf6037709b92e775f87304d6f`。本轮无再同步 main，前述独立逻辑审查保留；收尾文档不改变被测行为。

### Verification

- 全量前端：111 files / 1051 tests passed；最终恢复补丁另有 12/12 窄测试，最后视觉调整相关 166/166 测试通过。
- 后端 media / tenancy / external-ingress：3 files / 12 tests passed；IM 及依赖构建、IM contracts typecheck、前端类型检查和生产构建均通过。
- docs-check：277 maintained Markdown sources / 68 required routes passed（追加本段后再次检查）。
- 最终真实浏览器：使用单独的 `ux-audit` 会话和独立随机端口 IM；3 张待发卡片在网络返回前可见，输入可继续。503 失败后 Retry 可用，无重复全局 alert；重试成功后恢复发送，普通文档通过原入口实际下载。
- 实际查看桌面、320px 和 375px 画面；失败短状态与重试保持紧凑，长文件名省略且完整 title 保留，320px 输入自然换行文字完整可见。浏览器通过数据面注入延迟/503，验证的是前端失败处理；真实原文件编码接受另有独立 HTTP 证据，不混为生产故障复现。
- 本地证据：`output/playwright/audit-composer.png`、`audit-mobile-320.png`、`audit-mobile-375.png`、`ux-audit-browser.log`、`visual-fix-tests.log`、`final-recovery-tests.log`、`backend-validation.log`、`final-build.log`。图片、日志及临时数据库不提交。
- 用户实际体验仍未确认；unit 保持 active，canonical delta 未归并。所有源码保存在本 worktree 分支；本轮没有推送、发布或生产部署。

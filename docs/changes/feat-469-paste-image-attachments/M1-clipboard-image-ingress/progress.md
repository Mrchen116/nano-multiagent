# feat-469-M1 — Progress

## 启动基线

- Sync Gate: `unit/feat-469` 与 `origin/unit/feat-469` 均为 `ca5de3776e7032f999f0816d23a5cdfeb378c4da`。
- Tests: `npm test -- src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace.integration.test.tsx` → 2 files / 120 tests passed（既有 React `act(...)` warnings 保持不变）。
- Context: 已完整读取 spec/design/delta、prototype、AGENTS.md、SPEC.md、LOGBOOK.md、COMMENTING_GUIDE.md、TESTING_GUIDE.md 与现有附件代码/测试 seam。

## R1 — 剪贴板图片汇聚既有附件状态机

- Context: 生产 composer 原来只有 drop 入口，`handleAdd` 已拥有顺序上传、pending 累加、删除与发送忙态；paste 事件从未接入，且失败分支静默丢弃错误。实现必须只消费同步 `event.clipboardData`，不能复制附件状态机。
- Decision: textarea 的 `onPaste` 先按 `clipboardData.items` 原序取 `image/*` 的实际 File；只有未取得图片时才过滤 `clipboardData.files`。取得图片且 composer 非 busy 时才 `preventDefault()` 并把整批交给 `handleAdd`；`handleAdd` 逐项 catch 后通过可选 `onAttachmentUploadError` 上报，继续处理剩余文件。
- Rationale: items-first 保留剪贴板顺序和混合表示语义，files-only fallback 避免同一图片重复；有图才阻止默认行为守住原生文本编辑；复用 `handleAdd` 自然继承 drop 的顺序、partial success 与 pending/send 不变量。
- Evidence:
  - Tests: C1 `npm test -- src/features/chat/components/message-pane.test.tsx` → 3 failed / 84 passed，失败点分别是图片 paste 未 prevent、fallback 未接入、批量上传 0 calls；C2 focused → 87 passed；指定双文件门禁 → 127 passed。
  - Entry: desktop Chromium 真入口登录 worktree IM，paste 单图/多图/混合内容，真实 `/im/v1/uploads` 成功；删除首图、输入 caption 并发送剩余附件，消息 POST 返回 201。
  - Frontend State Matrix: default/empty（无图不接管）、disabled/submitting（busy 不上传）、missing/null（null item 走 files fallback 或放行）、desktop（1440×900）已覆盖；error 留给 R2 页面 owner；其余按 tasks.md 为 N/A。
  - Browser QA: Chromium 148.0.7778.96，`/chat/12157a23b72a4a628e32a47cb2b75c06`，console errors=0；IM API failures=0；仅 browser context 关闭时一条外部 Google Fonts `ERR_ABORTED`，与产品 API 无关。详见 `evidence/r1-browser-qa.md`。
  - E2E/Regression: `src/IM/frontend/src/features/chat/components/message-pane.test.tsx` 新增 7 个长期行为用例，覆盖 items/files、preventDefault、busy、顺序、删除/发送、partial success/error callback。
  - Visual/Interaction: `evidence/r1-pasted-images.png`、`evidence/r1-mixed.png`；1440×900；真实 `AttachmentChip` 的 `.chat-attachment-thumb` 继续为 64×64。
  - Prototype Comparison:

    | Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
    |---|---|---|---|---|---|
    | `#composer-pasted-images` | 单/多图复用 pending chip，可删、可带文字发送、顺序一致 | `evidence/r1-pasted-images.png` + 201 send 记录 | 1440×900 / multi + send | match | N/A |
    | `#composer-mixed` | 图片独占本次 paste，draft 不插 URL/alt/伴随文本 | `evidence/r1-mixed.png`；textarea value=`""` | 1440×900 / mixed | match | N/A |
    | `#attachment-error-toast` | 页面级可关闭附件错误 | R2 验收 | desktop / error | blocked | 本 reference 由 R2 页面 error owner 完成 |
- Rollback: 回退 C2 `71c6d2e1a` 可移除实现并保留 C1 红测；回退 C1 `c42b33dfe` 可移除行为契约。
- Commits: C1=`c42b33dfe`，C2=`71c6d2e1a`，C3=本次 docs 提交（最终在 R2 回填 hash）。
- Next: R2 写 production ChatWorkspace typed/unknown error toast regression。

## R2 — 页面级本地化失败反馈与真入口验收

- Context: 待执行。
- Decision: 待执行。
- Rationale: 待执行。
- Evidence: 待执行。
- Rollback: 待执行。
- Commits: 待执行。
- Next: R1 完成后开始。

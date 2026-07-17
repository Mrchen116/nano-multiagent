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
- Commits: C1=`c42b33dfe`，C2=`71c6d2e1a`，C3=`784cc12bb`。
- Next: 已由 R2 完成 production ChatWorkspace typed/unknown error toast 与真实入口验收。

## R2 — 页面级本地化失败反馈与真入口验收

- Context: `MessagePane` 的逐项上传失败原本只在组件内静默 catch，页面 owner 无法通知用户；同一批次的成功附件仍必须保留，失败项不能形成 pending chip。既有 ChatWorkspace 已有页面级 send/fork toast，适合复用 owner 和层级。
- Decision: 页面用 `ChatWorkspaceError` 区分 send 与 attachment；`AttachmentUploadError.code` 映射 unsupported type、too large、network 三个本地化文案，非 typed error 映射 unknown。toast 保持页面级位置，补 `role="alert"` 和按错误类型本地化的关闭按钮；`MessagePane` 只通过 callback 上报，附件状态仍由既有 `handleAdd` 独占。
- Rationale: 错误分类留在理解上传域错误的 production page，presentation 组件不耦合 i18n；复用同一页面 owner 避免并存两个 toast 层和 z-index 规则；逐项上报而非批次 reject 保留 partial success。
- Evidence:
  - Tests: C1 `npm test -- src/features/chat/chat-workspace.integration.test.tsx` → 6 failed / 40 passed；失败覆盖 en/zh typed/unknown toast 与 partial success。C2 focused → 46 passed；指定双文件门禁 → 133 passed；完整 frontend Vitest → 64 files / 617 tests passed；production build → 442 modules transformed；测试命名/大小 contract → 2 passed。
  - Entry: desktop Chromium 在真实 `/chat/f8d9766a8add4ca099a0c06cbab96e28` 同批粘贴 `first-ok.png`、超过 10 MiB 的 `too-large.png`、`last-ok.png`，真实 upload endpoint 返回 success / 413 / success。
  - Frontend State Matrix: error（页面级 alert + 可关闭）、partial success（首尾成功 chip 保留、失败 chip 缺席）、desktop（1440×900）已覆盖；default/empty/disabled/submitting/null 由 R1 覆盖，其余按 tasks.md 为 N/A。
  - Browser QA: Chromium 148.0.7778.96；toast 标题=`Attachment upload failed`，正文=`This image is larger than the current attachment limit.`；关闭后 alert 数为 0；两枚成功 thumbnail 均为 64×64。唯一产品 HTTP 失败是刻意触发的 413；console 对应一条预期 413 resource error；另有 browser context 关闭时外部 Google Fonts `ERR_ABORTED`。详见 `evidence/r2-browser-qa.md`。
  - E2E/Regression: `chat-workspace.integration.test.tsx` 长期覆盖 415/413/503/raw error、zh 415、dismiss 与 success/failure/success；真实浏览器覆盖 413 partial-success 主路径。
  - Visual/Interaction: `evidence/r2-attachment-error-toast.png`；1440×900；toast 在页面左上可见，composer 仅保留 `first-ok.png`、`last-ok.png`。
  - Prototype Comparison:

    | Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
    |---|---|---|---|---|---|
    | `#composer-pasted-images` | 64×64 pending chip、可删、可带文字发送、顺序一致 | R1 两张截图 + R2 首尾成功 chip 顺序 | 1440×900 / normal + partial success | match | N/A |
    | `#composer-mixed` | 图片独占同次 paste，draft 不插伴随文本 | `evidence/r1-mixed.png`，textarea value=`""` | 1440×900 / mixed | match | N/A |
    | `#attachment-error-toast` | 页面级可见可关闭错误；失败项不入 pending、成功项保留 | `evidence/r2-attachment-error-toast.png` + dismiss 后 alert=0 | 1440×900 / real 413 | match | N/A |
    | sidebar / message list / composer redesign | 保持真实产品现状 | 三次真实入口走查未扩改布局 | 1440×900 | out-of-scope unchanged | N/A |
    | toast 精确像素/排版 | 可适配现有页面 owner 与 i18n | 复用既有 fixed page toast，仅按错误类型改 title/body/aria | 1440×900 / error | may-adapt satisfied | 沿用产品既有视觉层而非复制 prototype 像素 |
- Rollback: 回退 C2 `639f124ee` 可移除 production 映射并保留 C1 红测；回退 C1 `629c7dd03` 可移除页面行为契约。R1 独立保持可用。
- Commits: C1=`629c7dd03`，C2=`639f124ee`，C3=本次 docs 提交。
- Next: milestone 已完成，进入完整门禁、rebase 与 unit integration。

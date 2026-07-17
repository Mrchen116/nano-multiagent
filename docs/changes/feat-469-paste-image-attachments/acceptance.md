# feat-469 — 验收报告

> 对齐: `spec.md` / `design.md` / `prototype.html`
> Review round: 1 (full)
> Validated head: `0fb53cceba4db9458cd82b0e3c96e6c7100f41bf`

## Verdict

- **Verdict: pass**
- **Highest Required Action: pass**
- Issues: blocking 0 / major 0 / minor 0
- Needs re-review: no

7 个必验 Scenario 与 3 个 prototype `must-match` 状态全部通过。验收使用 unit worktree 当前源码重建的 production bundle `index-BDQhSvMn.js`，由隔离 IM/Gateway 真栈服务提供，在 1440×900 headed desktop Chromium 会话中通过真实 `/chat/:conversationId`、`/im/v1/uploads` 和消息 POST 走完。

## User Journeys Exercised

1. **单图、删除、多图与发送**
   - 单图 paste 被图片语义接管，`single-red.png` 显示为 64×64 待发 chip，点击 `Remove single-red.png` 后消失。
   - 同次 paste `first.png` / `second.png` 以剪贴板顺序显示。删除第一张，输入 `acceptance caption` 后发送，页面出现用户消息气泡及 `second.png`，真实消息 POST 返回 201。
2. **mixed 与原生粘贴边界**
   - 同次 DataTransfer 携带图片、URL 和 alt companion 文本时，仅 `mixed.png` 进入待发区，textarea 保持空值。
   - 纯文本使用系统剪贴板与真实 `Meta+V` 在光标位置粘贴：`left  right` 变为 `left PASTED right`，且无附件。
   - 非图片 `notes.txt` paste 没有被 `preventDefault`，无附件被加入，原生粘贴路径未被阻断。
3. **partial success、本地化 toast 与恢复**
   - 同批 paste `first-ok.png` / `too-large.png` / `last-ok.png`，真实上传结果为 201 / 413 / 201。待发区仅保留首尾成功项，且顺序不变；draft 仍为空。
   - 英文 toast 显示 `Attachment upload failed` 与可理解的大小限制说明；切换中文后重试，显示「附件上传失败 / 图片超过当前附件大小限制。」。两种 locale 下点击关闭后 `role=alert` 数量都为 0。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html#composer-pasted-images` | 单/多图复用 64×64 pending chip，可删除、可发送，顺序一致 | `M1-clipboard-image-ingress/evidence/acceptance-r1-single.png`; `acceptance-r1-multi.png`; 发送后气泡显示 caption + `second.png` | 1440×900 / single, multi, delete, send | **match** |
| `prototype.html#composer-mixed` | 图片独占 mixed paste，draft 不插入 URL/alt | `M1-clipboard-image-ingress/evidence/acceptance-r1-mixed.png`; observed textarea value `""` | 1440×900 / mixed image + text | **match** |
| `prototype.html#attachment-error-toast` | 页面级、明确、可关闭的附件失败反馈；失败项不进 pending，成功项保留 | `M1-clipboard-image-ingress/evidence/acceptance-r1-partial-toast.png`; `acceptance-r1-zh-toast.png`; dismiss 后 alert count = 0 | 1440×900 / real 413 partial success, EN + ZH | **match** |

## Acceptance Criteria Coverage

### Requirement: 聊天输入框支持把剪贴板图片加入待发附件 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 粘贴单张截图 | `spec.md`; `prototype.html#composer-pasted-images` | 真入口 paste 单图，观察 chip，删除；再用多图中保留的图片随 caption 发送 | `acceptance-r1-single.png`; 上传 201；消息 POST 201；发送后气泡显示附件 | pass | chip 实测 64×64，删除与发送均可见 |
| 粘贴同时带有文本表示的图片 | `spec.md`; `prototype.html#composer-mixed` | 真入口派发包含 image + URL/alt 的 paste | `acceptance-r1-mixed.png`; textarea=`""`; 仅 `mixed.png` chip | pass | paste 被图片语义接管，无 draft 污染 |
| 一次粘贴多张图片 | `spec.md`; `prototype.html#composer-pasted-images` | 同次 paste `first.png` / `second.png`，检查 DOM 与视觉顺序 | `acceptance-r1-multi.png`; remove controls 顺序 `first.png`, `second.png`; 两次 upload 201 | pass | 顺序与剪贴板一致 |

### Requirement: 普通文本粘贴行为保持不变 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 粘贴纯文本 | `spec.md`; design 决策 2 | 系统剪贴板写入 `PASTED`，在 textarea 中间光标位置执行真实 `Meta+V` | textarea 从 `left  right` 变为 `left PASTED right`; pending count=0 | pass | 浏览器原生光标插入语义保留 |
| 粘贴非图片文件 | `spec.md`; design 决策 2 | 在真 Chromium textarea 派发携带 `notes.txt` 的 DataTransfer paste | `defaultPrevented=false`; pending count=0; existing draft 保持 | pass | 无图片时不接管默认 paste |

### Requirement: 粘贴图片与其他附件入口共享限制和失败反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 粘贴合规图片 | `spec.md`; design 决策 4; `prototype.html#composer-pasted-images` | 上传合规 PNG，对照既有 pending chip 形态、大小和删除能力 | `acceptance-r1-single.png`; `acceptance-r1-multi.png`; 64×64；Remove 可用 | pass | 与既有 `AttachmentChip` 用户面一致 |
| 粘贴图片被拒绝或上传失败 | `spec.md`; design 决策 5; `prototype.html#attachment-error-toast` | 同批上传成功/超限/成功，核对 chip、EN/ZH toast 与 dismiss | `acceptance-r1-partial-toast.png`; `acceptance-r1-zh-toast.png`; uploads 201/413/201; dismiss 后 alert=0 | pass | 失败项不进待发，成功首尾保留且顺序不变 |

## Independent Supporting Checks

- Production build: `npm run build` → 442 modules transformed, success.
- Focused frontend regression: MessagePane + ChatWorkspace integration → 2 files / 133 tests passed. 已有 React `act(...)` warnings 依旧存在，本轮无 test failure。
- Browser requests: single/multi/mixed/success items 的 upload 均为 201；两次故意超限为预期 413；附件消息 POST 为 201。
- Browser console: 仅两条与故意 413 对应的 resource error，无非预期产品错误。

## Issues

None.

## Side Findings

- Runbook 建议的 `GET /health` 在当前 IM 返回 404；本轮改用首页 bundle 指纹、登录、Agent online 与真实 API 请求确认真栈 ready。该文档偏差未影响任何 feat-469 用户旅程。
- 发送附件消息后，隔离 Gateway 的外部 LLM 调用最终返回 `anthropic: stream ended without terminal event`。用户消息与附件已在此前持久化并显示；该上游环境失败不属于本 unit 的附件输入/发送契约，不计为验收 issue。

## Clarification Log

None. 验收口径由 spec 的 7 个 Scenario 与 design 的 3 个 `must-match` 行完整覆盖，无需附加解读。

## Upper-level Documentation Sync

- [x] `SPEC.md` (跨包顶点架构): **无需更新**；本 unit 只改 Web IM composer 用户行为，不改包边界或部署拓扑。
- [x] `docs/specs/im/`: **需要更新**；`web-chat-ux.md` 尚未反映图片粘贴、mixed 语义、原生文本回归与 partial-success 反馈，应由 orchestrator 收尾归并 delta-spec。
- [x] `AGENTS.md` / `CLAUDE.md`: **无需更新**；无新的开发/运维约定。
- [x] `docs/SPEC_GUIDE.md`: **无需更新**；本 unit 未改文档体系。

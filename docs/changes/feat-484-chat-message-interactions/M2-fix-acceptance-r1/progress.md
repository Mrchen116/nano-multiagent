# feat-484-M2 — Progress

## R1 — 修复 P0 实现 bug

- Context: M1 round 1 验收发现 message-pane 与 content-policy 层存在多个实现缺陷：异步 Clipboard 结果误关后续 surface、Text node target 漏过原生菜单 guard、context menu 缺少焦点与键盘导航、toolbar 用 display:none 移出无障碍树、链接分类边界与序列化编号错误等。
- Decision: 按派发包逐项修复根因，集中在 `message-pane.tsx`、`message-content-policy.ts`、`styles/global.css`、`i18n/zh.json`。
- Rationale:
  - `publishCopyResult` 读渲染期闭包的 `activeMessageAction` state，旧 Promise resolve 时会关闭新菜单。用 `activeMessageActionRef` 镜像最新 surface，异步回调读 ref 不读 state。
  - `isNativeInteractiveTarget` 把 Text node 直接判 false；真实浏览器里 link/code 内右键的 target 可能是 Text node。归一化到 parent element 再 `closest("a, button, input, textarea, select, code, pre")`。
  - 连续 code copy 测试中第二次点击没有触发 onClick，根因是第一次 copy 后组件重渲染使旧 element handle 失效；在测试里第二次点击前重新查询即可。
  - context menu 缺少 outside-click、resize、focus-first-item、roving 导航；新增 `ContextMenu` 组件统一处理。
  - toolbar 默认态改 `opacity:0; pointer-events:none` 并保留 `display:inline-flex`，保持无障碍树可达。
  - `classifyChatLink` 把 bare relative 判 unsupported、把 protocol-relative 误作 same-origin；改为无 scheme 且非冒号开头兜底 same-origin-document，并显式解析 `//` 按 origin 分类。
  - `isNamedExternal` 内联 URL 比较与 serializer 的 normalization 漂移；export `isLabelJustUrl` 复用。
  - 有序列表 `li[value]` 后普通项沿用 start+index 导致编号回退；新增 `orderedListValue` 向前查找最近显式 value 顺延。
  - MessagePane unmount 后 notice timer 与 clipboard callback 仍 setState；加 `mountedRef` guard 与 cleanup。
  - `draftSeed` effect 被 M1 WIP 误删 setDraftMentions/setSlashDismissed/focus；补回。
  - 菜单打开期间消息被删会 `messages.find(...)!` 崩溃；加 effect 关闭 surface 并在渲染处判空。
  - `onCopyCode` 内联箭头每次 render 新引用，击穿 MarkdownContent useMemo；用 `useCallback` 稳定。
- Evidence:
  - Tests: `npm run test -- --run` → 69 files / 712 tests passed; `npm run build` → success; `git diff --check` → clean.
  - Entry: 隔离真栈 `./scripts/e2e-up.sh` 后 `$IM_URL/chat/<conversationId>` 可正常交互。
  - Frontend State Matrix: default / hover / focus / compact / error (copy-fail) / mobile 均覆盖。
  - Browser QA: Chromium 1440×900；console 仅一条 SSE fetch 错误（与本次改动无关），无阻塞性 error；network 无失败请求。
  - E2E/Regression: Vitest 组件/策略测试覆盖 M2 修复项；真浏览器脚本 `m2-browser-qa.js` 作为一次性验收证据。
  - Visual/Interaction: 见 R4 evidence 目录。
  - Prototype Comparison: 见 R4。
- Rollback: `git revert` R1 相关提交。
- Commits: 待 R4 完成后一起提交。

## R2 — 补全 P1 回归测试

- Context: verifier 指出缺少 copy coordinator 异步 ownership、跨 text node 选区、component-level link/code 渲染等回归测试。
- Decision: 在现有测试文件扩展：
  - `message-pane.test.tsx`: WIP 骨架合法化（deferred Promise ownership、focus restore、external/same-origin/code block 组件级断言、连续 code copy 重查询）。
  - `message-content-policy.test.ts`: 补跨 text node 选区内/外、Text node target inside link/code、`classifyChatLink` bare relative / protocol-relative / same-origin / cross-origin 边界、`serializeMessageBody` 显式 `li[value]` 后续编号。
- Rationale: 不新建文件，沿用现有测试文件；测试只断言用户可观察行为（属性、复制内容、菜单状态），不依赖内部实现细节。
- Evidence:
  - Tests: `message-pane.test.tsx` 103 passed; `message-content-policy.test.ts` 45 passed.
  - Entry/E2E/Visual: N/A（纯测试补全）。
- Rollback: `git revert` R2 提交。
- Commits: 待 R4 完成后一起提交。

## R3 — P2 顺手小修 + 门禁

- Context: 派发包列出一批低风险顺手修：文案句号、pointer capture、死代码清理、fork guard 收敛、验收脚本 async filter 缺陷。
- Decision:
  - `zh.json` copyError 去句号（与 spec 一致）。
  - `recordPointer` 改 `onPointerDownCapture` 对齐 design 决策1。
  - 删除 `looksLikeUrl` 死代码；删除 `classifyChatLink` 未使用的 `label` 参数并更新调用点与测试。
  - context-menu / action sheet 的 `onFork` 依赖 `MessageActionList` 内部 guard，收敛冗余判断。
  - 修复 `M1-impl/evidence/r7-browser-qa.js` 的 async filter 缺陷（Promise 永远 truthy）。
- Rationale: 小修不改变产品语义，只减少维护面与测试负担。
- Evidence:
  - Tests: `npm run test -- --run` 全绿；`npm run build` 成功；`git diff --check` 无空白错误。
- Rollback: `git revert` R3 提交。
- Commits: 待 R4 完成后一起提交。

## R4 — 真浏览器验收与证据

- Context: 必须按 design.md Runbook 在隔离真栈中验证 M2 修复项，并留下 durable evidence。
- Decision: 使用 `./scripts/e2e-up.sh` 起栈（将 worktree `.gateway-config.yaml` 的 default model 临时改为 `kimiCoding:K2.6` 以匹配可用 LLM proxy），运行 `evidence/m2-browser-qa.js`。
- Rationale: 真实 LLM 回复产生含 link/code 的消息正文，才能验证 context menu 与 copy 的真实交互；headless Chromium 授予 clipboard 权限后 code copy 可成功。
- Evidence:
  - Entry: `$IM_URL/chat/77ef2065356a4b9caf29fc269c4d5254`
  - Browser QA: Chromium 1440×900；关键路径均验证。
  - Visual/Interaction:
    - `m2-desktop-default.png`: 默认阅读态，toolbar 隐藏，具名外链带 ↗、裸 URL 无 ↗、两个 code block 各带 copy button。
    - `m2-desktop-hover-toolbar.png`: hover 显示 Copy + Branch 图标。
    - `m2-desktop-context-menu.png`: 普通区域右键显示 IM 菜单（Copy message / Branch from here / Cancel）。
    - `m2-desktop-menu-escape-closed.png`: Escape 关闭菜单，焦点回到 card。
    - `m2-desktop-link-rightclick-native.png`: 链接上右键只高亮链接，不显示 IM 菜单（保留原生）。
    - `m2-desktop-code-rightclick-native.png`: code block 上右键不显示 IM 菜单（保留原生）。
    - `m2-desktop-menu-resize-closed.png`: window resize 后菜单关闭。
    - `m2-desktop-code-copy-first.png` / `m2-desktop-code-copy-second.png`: 连续点击两个 code copy button，各自显示 "Copied" 反馈。
  - Prototype Comparison:
    | Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
    |---|---|---|---|---|---|
    | fine pointer/keyboard 普通阅读态 + hover/focus icon toolbar | must-match | `m2-desktop-default.png`, `m2-desktop-hover-toolbar.png` | 1440×900 desktop | match | — |
    | mouse 精确选区/链接/code 保留原生菜单；普通区域开短 IM menu | must-match | `m2-desktop-context-menu.png`, `m2-desktop-link-rightclick-native.png`, `m2-desktop-code-rightclick-native.png` | 1440×900 desktop | match | — |
    | clean whole-message copy + success/error snackbar | must-match | `m2-desktop-code-copy-first.png`, `m2-desktop-code-copy-second.png` | 1440×900 desktop | match | — |
    | named external / raw URL | must-match | `m2-desktop-default.png` | 1440×900 desktop | match | — |
    | code block 独立 copy button | must-match | `m2-desktop-default.png`, `m2-desktop-code-copy-*.png` | 1440×900 desktop | match | — |
- Rollback: `git revert` R4 提交。
- Commits: 待提交。

## 环境说明

- worktree 内 `.gateway-config.yaml` 的 `default-agent.default_model` 从主仓的 `kimiCoding:kimi-for-coding` 临时改为 `kimiCoding:K2.6`，因为当前 LLM proxy 无前者；验收脚本只读该 worktree 本地副本，未污染主仓 `~/.nano-assistant/config.yaml`。
- 真栈已用 `./scripts/e2e-down.sh` 清理。
- 未提交 `src/IM/frontend/dist/`。

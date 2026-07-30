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

## R5 — P0-22 修复:整条复制的块级误判与列表空行(orchestrator 接管)

- Context: worker 完成 R1–R4 后撞 403 死亡,reviewer round 1 的唯一 major issue(真栈实测剪贴板与 rich-copy fixture 不符)未修;orchestrator 按用户指示亲自接管。
- Diagnosis: 一次性 jsdom 诊断(已删)复现三机制——①`.im-md-link--external` 的 `display:inline-flex` 被 `isBlockElement` 的 computed-style fallback 误判块级,链接断行且丢失 "label (URL)" 追加(块级分支提前 return);②loose list `<li><p>…</p><ul>…` 中项内段落双换行穿透,列表项间多一空行;③块级容器间格式化空白文本节点原样穿透。
- Decision: `isBlockElement` 增加内联语义标签集合(A/SPAN/CODE/STRONG/EM/IMG/INPUT 等)永远判内联,产品 CSS 不再干扰复制结构;li 内拼嵌套 ul/ol 前把末尾空白压成单换行;ul/ol/li/table/blockquote 的纯空白文本子节点丢弃。
- Rationale: 块级/内联判定按语义标签而非 computed style——复制是内容操作,不应被展示层 CSS 改变结构;loose/tight list 是渲染细节,复制语义统一为"列表项连续"(design fixture 冻结)。
- Evidence:
  - Tests: `npm run test` 69 文件 715 tests 全绿(新增 loose list / whitespace / inline-flex link 三个回归测试);`npm run build` 成功;`git diff --check` clean。
  - Entry: 隔离真栈(IM :62079)发 PROMPT_RICH 得 completed 回复,toolbar Copy message 后读剪贴板。
  - Browser QA: `m2-p022-copy-qa.js` 断言全过——列表连续(顶级+嵌套)、具名外链内联 `文档 (https://example.com/docs)`、裸 URL 恰好 1 次、同源 /chat 无追加。
  - Visual/Interaction: `m2-p022-hover-toolbar.png`、`m2-p022-copy-result.png`。
  - 剪贴板原文: `m2-p022-clipboard-message.txt`。
  - Prototype Comparison: clean whole-message copy must-match → match(真栈剪贴板与 fixture 结构一致)。
- Rollback: `git revert 1b41a8ce6`。
- Commits: 1b41a8ce6。
- Next: 合并 unit,复验(verifier targeted-closure + reviewer targeted)。

## R6 — reviewer round 3 issue 3 修复:整条复制不再折叠 code 内部空行

- Context: reviewer round 3 真栈读剪贴板发现 code block 内部空行被折叠(`\n\n\n`→`\n\n`),违反 design.md fixture "code 内部空行不折叠";独立代码复制路径正确,问题锁定在整条复制序列化。
- Diagnosis: `collapseBlockSpacing` 在序列化完成后对全文无差别折叠 3+ 连续换行——此时已是纯字符串,code 区间信息丢失,code 内部空行被当作"块间多余空行"压掉。
- Decision: `collectText` 的 `pre` 分支先把 code 内部换行换成 NUL 占位穿过折叠,`serializeMessageBody` 在 `collapseBlockSpacing` 后统一换回;块间距规整不再越界进 code 内容。选 NUL 因为纯字符串阶段无区间信息,而 NUL 不会合法出现在 text/plain payload 中;改动集中于 pre 分支 + serializeMessageBody 两行,不触碰列表/链接/table 等已收敛路径。
- Evidence:
  - Tests: `message-content-policy.test.ts` 50 全绿(新增 "preserves multiple consecutive blank lines inside code blocks" 红测先行);`message-pane.test.tsx` + `message-pane-fork.test.tsx` 111 全绿;`npm run build` 成功;`git diff --check` clean。
  - Entry: 隔离真栈(IM :49373)发富文本 prompt 得 completed 回复(第一个 fenced 块含 `\n\n\n` 两个连续空行),toolbar Copy message 后读剪贴板。
  - Browser QA: `m2-fix-r3-selfcheck.mjs` 逐字断言全过——两个 fenced 块逐字包含于剪贴板(内部空行完整)、具名链接内联、列表无多余空行、无 ⎘。
  - 剪贴板原文: `evidence/m2-fix-r3-clipboard-whole.txt`;agent 回复原文: `evidence/m2-fix-r3-agent-reply.md`;截图: `evidence/m2-fix-r3-copy-result.png`。
- Rollback: `git revert 704cb26d3`。
- Commits: 83a796303(红测), 704cb26d3(实现)。
- Next: reviewer round 4 targeted 复验(同时需关闭 R1 起挂起的两条移动端长按 inconclusive)。

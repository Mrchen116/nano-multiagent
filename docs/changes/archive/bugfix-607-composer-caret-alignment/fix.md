# bugfix-607: 聊天输入框长文本编辑后光标与文字错位

## Relations

- Related: feat-340, bugfix-358

## 原始报告

> 输入框有bug，输入过删过，反复编辑过之后，不知道为啥它后面会留一些空位再到光标。

用户提供两张 Web IM 截图：第一张末尾“除了小鹏和遥望”与光标之间有空位；第二张中文拼音组合输入出现在同一长文本末尾。附件为本次聊天中的 `codex-clipboard-c37ad80f-3f77-4ffa-861a-5a011c77297e.png` 和 `codex-clipboard-94364394-a00a-4213-bff8-3cd1afd89240.png`，本机截图不入库。

## 现象 / 复现

- 预期：输入、删除、重新编辑包含中英文和路径的长草稿时，可见文字、换行和原生光标保持对齐；保留用户输入的空格、中文组合输入及 mention 高亮。
- 基线：`origin/main` / `9ebe12f85`，真实 Chromium 加载当前 `MessagePane` 及 `global.css` 的隔离组件页面。
- 输入足以在两行输入框中发生软换行及纵向溢出的中英文、路径混合草稿，聚焦末尾；将原生文字临时显色与镜像叠放比较，可以直接观察换行后的文字错位。
- 运行测量：textarea 与 mirror 外宽均为 `1119.6015625px`，但 `clientWidth` 分别为 `1112px` 和 `1118px`。草稿内容与镜像正文一致，不存在被额外插入的空格。
- 只让两层共同预留稳定滚动条槽后，`clientWidth` 均为 `1112px`，叠放字形恢复重合，滚动位置与内容高度一致。

## 根因

`MessagePane` 使用透明原生 textarea 提供编辑、选择、IME 与光标，下方 mirror 提供文字及 mention 高亮。全局 `::-webkit-scrollbar` 指定 `6px` 宽度；textarea 的 `overflow-y: auto` 在内容溢出时占用这段宽度，mirror 的 `overflow: hidden` 没有同步预留槽。两层虽然外框和字体相同，可用文字宽度不同，软换行位置逐行分叉，使镜像末尾与原生光标之间出现空位。镜像与 textarea 的断词规则也分别设置，需保持一致。

原始镜像高亮由 feat-340 引入（CSS `git blame`：`b74813e1dd`），纵向自动滚动规则为 `3ed14ae3a9`；bugfix-358 后续明确保留可见 `@DisplayName` 作为 textarea 内容、发送时重建 wire mention，避免 XML 宽度影响原生编辑。此前验证主要保护内容与 wire 转换，未验证发生滚动条时的实际排版宽度。

本次为单 milestone Bugfix lite，只修 Web composer 排版；必须保留原生编辑/撤销/组合输入、文本空格与换行、mention 高亮与发送转换、草稿和附件行为。

## 修复

- `65499f136`：textarea 和 mirror 共用 `scrollbar-gutter: stable`、`overflow-wrap: break-word` 与 `word-break: normal`，镜像使用与 textarea 相同的 `overflow-y: auto`。后者也使 WebKit 在内容溢出时为镜像分配相同的原生滚动条槽。
- 保留透明 textarea 原生编辑与原有滚动同步；不改草稿数据、提及转换、附件或发送逻辑。
- 把长草稿编辑后文字/光标对齐场景归并到 `docs/specs/im/web-chat-ux.md` 既有 composer Requirement，未增加 Requirement 数量。

## 验证

- 修前：Chromium 和 WebKit 均测得 textarea/mirror 可用宽度相差 `6px`；将两层文字分别显色叠放可见软换行错位。
- 修后：真实 Chromium/WebKit 各 25 个组件状态，以及隔离完整 IM 的构建产物页面 26 个状态通过，文字/高亮、可用宽度、内容高度、滚动位置均对齐；实际聊天页的原生撤销保留草稿。详情见 [browser-qa.md](M1-fix/evidence/browser-qa.md)。
- 最窄验证：message-pane 与 composer-draft 相关 `112` 项通过；最终前端全量 `93` 文件 / `871` 项通过，前端构建通过，npm audit `0 vulnerabilities`。
- 本地 CI 等价：`pnpm build`、`pnpm typecheck`、TypeScript `80` 文件 / `296` 项、Python 非 E2E `56` 项、ruff check/format 均通过；文档检查与 `git diff --check` 通过。后端与工具检查在同一 main 基线上执行，随后仅修改 Web CSS 与文档，结论保留。
- 独立 full code review 在 `65499f136` 对 `9d6946df2` 完整 diff 执行，返回 `[]`；见 [code-review.md](code-review.md)。
- 测试策略：失败原因属于真实浏览器的滚动条与排版，jsdom 内容测试无法暴露。保留已有 composer/mention/draft 测试，使用一次性浏览器几何与显色对照验证本次 CSS 修复，不新增只断言 CSS 文本的测试或平行功能测试。
- 限制：未声称完成系统中文候选窗口、物理手机键盘或 Firefox 验收；没有 merge、部署或发布安装包。

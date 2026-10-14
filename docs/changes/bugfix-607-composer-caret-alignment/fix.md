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

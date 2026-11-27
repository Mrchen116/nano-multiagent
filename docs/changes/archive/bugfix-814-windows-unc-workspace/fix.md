# bugfix-814 Windows Desktop 聊天文件链接丢失共享服务器名

## Relations

- 工作区文件直达源自 feat-790-desktop-client，现行契约见 `docs/specs/im/desktop-client.md` 的「一键在本地打开本机工作区文件与目录」。

## 原始报告

> 聊天 file://fileserver/team/work/total.pdf 被 workspace-path-actions.tsx 只取 pathname，丢 hostname。正常 UNC 工作区的允许文件应能通过现有宿主工作区权限并向系统打开；保留盘符、转义及现有越界拒绝语义。

## 现象 / 复现

在 `1bdc4646c`，对报告中的链接运行聊天组件的 `decodeURIComponent(new URL(href).pathname)` 得到 `/team/work/total.pdf`。Windows 原生目标应为 `\\fileserver\team\work\total.pdf`。错误发生在打开或定位请求到达宿主前。

## 根因

`c75e0415e` 引入的聊天转换只处理了路径和本地盘符。local-admin 接受原始 file URL 时也独立执行同样的转换。两处都丢掉了 UNC 的服务器名。授权依据是节点所有者、Agent 和工作区根，路径还需在 realpath 前后通过范围检查。

## 本次审查安排

核对聊天链接和旁边按钮发出的目标、宿主按平台解析转义及盘符的行为，并以真实临时文件验证工作区内成功、越界拒绝。Windows runner 验证 UNC，代码审查覆盖 URL 到系统打开调用的参数传递。

## 修复

提交 `7f09ec0f2` 让聊天链接、打开按钮和定位按钮都把原始 file URL 交给宿主。前端只为判断可执行后缀解码 pathname。local-admin 在校验节点所有者和本地 Agent 后调用 Node 的 `fileURLToPath`，继续以原有工作区范围、realpath 和后缀检查授权操作。Rust 宿主将成功返回的 `resolved_path` 传给 Explorer 或 Finder。

## 验证

- 基线回放中，聊天三个操作均把 `file://fileserver/team/work/total%20%231.pdf` 变成 `/team/work/total #1.pdf`。修复后，MessagePane 实际点击链接、打开、定位均传完整 URL，编码了后缀的脚本链接只请求定位。
- macOS 上运行聊天和 Desktop 工作区两个 Vitest 文件，117 项通过。以 `TMPDIR=/private/tmp` 运行 local-admin、platform-conformance 两个文件，7 项通过，覆盖真实文件名中的空格、井号与字面量 `%20`、其他主机、工作区外路径和符号链接。使用规范化的临时目录可让既有启动项测试的 plist 路径与 macOS realpath 一致。
- Windows Desktop candidate 增加对同一宿主解析入口的定向回归，在本机盘符及回环 SMB 共享下分别创建临时工作区和文件，核对获准的实际路径及越界拒绝。该用例的终点为宿主解析器，未观测 PDF 阅读器窗口。
- `git merge-tree --write-tree 7f09ec0f2 2163c8956` 验证与 PR #568 无冲突，合并树同时包含 UNC 回归和调用 `installer-lifecycle.ps1` 的卸载回归。

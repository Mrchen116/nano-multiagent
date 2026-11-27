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

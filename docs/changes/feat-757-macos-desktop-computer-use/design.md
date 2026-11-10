# 实施记录

Nano 安装入口在 macOS 上为含有该 Skill 的版本准备 CuaDriver。缺失时使用经 SHA-256 校验的 0.38.0 官方安装脚本和同标签辅助脚本，已有官方 App 则复用。Gateway 启动时把官方 App 的 CLI 目录加入 PATH，覆盖后台服务与终端启动。安装步骤失败可重跑同一 Nano 安装命令。

[0.38.0 发布包](https://github.com/trycua/cua/releases/tag/cua-driver-rs-v0.38.0) 的 Skill 资产原样随包分发，附带上游 MIT 许可。现有 Skill 根负责发现及加载，Agent 使用原生 Bash 工具与现有审核，执行结果走原有聊天轨迹和回复。macOS 的 Accessibility 与 Screen Recording 权限由系统及 CuaDriver 管理。

## 验证

- 安装、配置和内置 Skill 的 21 项测试通过。新装与重跑用安装夹具验证，真实旅程复用宿主已安装的官方 0.38.0。Nano 发布包内的 Skill 文件与同版本发布资产逐文件一致。
- 隔离 Nano 的 Agent 通过 Bash 调用官方 CLI，在 Chrome 登录 Web IM，发送一次测试消息并在页面看到接收 Agent 的 ACK。PA 通过 AX 读到 Finder、TextEdit 和系统设置，在合成 AppKit 窗口分别用 AX 元素和截图坐标各点击一次，计数从 2/2 依次变为 3/2、3/3。
- 独立代码审查发现官方安装脚本会加载未固定版本的辅助脚本。补上同版本下载和校验后复审关闭该问题。

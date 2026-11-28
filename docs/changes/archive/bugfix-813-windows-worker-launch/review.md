# Windows Worker 启动审查

独立代码审查范围为 `1bdc4646c..55c5eec09`，覆盖桌面探测、原生驱动、子进程生命周期和 fixture。现行 desktop-client 和 global-agent 规格已要求设置反映实际可用 Worker，规格无增量。

| 独立审查发现 | 修正及复核依据 |
| --- | --- |
| 编辑代理时，前端把缺失的 PATH 草稿传成空字符串，系统已安装的 Worker 会误报不可用。 | `bf4ddfe2d` 从表单到本机探测保留缺失与空值的区别，Windows 的配置键按大小写不敏感匹配。设置卡回归检查编辑代理时实际发送的探测请求，原生 fixture 校验两种 PATH。 |
| 自定义 PATH 仅含 Worker 目录时，关闭进程找不到 taskkill，临时文件可能遗留。 | `bf4ddfe2d` 按系统绝对路径定位 taskkill.exe。Windows fixture 仅设置 Worker 目录并在关闭后检查提示词文件已回收。 |

修订后在 macOS 的 Node 24.22.1 上，Node 和 dsh-integration 编译成功，设置与驱动 16 项、设置页 2 项、架构边界 14 项通过。设置测试在真实临时目录路径上运行，避开 macOS /var 符号链接对现有自启文件名的影响。Windows fixture 仅在原生 Windows 运行，其证据见本 PR 的 Windows installer candidate 作业。
